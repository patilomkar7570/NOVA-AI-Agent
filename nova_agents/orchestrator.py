"""Safety-hardened planner execution with durable per-step journaling."""
from __future__ import annotations

from dataclasses import replace
import math
import threading
import time
from pathlib import Path
from typing import Any

from .contracts import AgentResult, ExecutionPlan, PlanStep, is_valid_task_transition
from .memory import SharedMemory
from .planner import TaskPlanner
from .policy import classify_action_risk
from .registry import agent_capabilities, agent_ids
from .router import TaskRouter
from .specialists import BrowserAgent, ChatAgent, ResearchAgent
from .specialists.reaction_agent import ReactionAgent


_ALLOWED_AGENTS = frozenset(agent_ids())
_DEFAULT_TIMEOUTS = {
    "reaction": 8.0,
    "chat": 75.0,
    "browser": 150.0,
    "research": 150.0,
}
# Browser actions are not automatically retried: a failed response does not
# prove that a click/navigation had no external side effect.
_DEFAULT_RETRIES = {"reaction": 0, "chat": 1, "browser": 0, "research": 1}
_MAX_PLAN_STEPS = 3


class Orchestrator:
    def __init__(self, agent_module, event_callback=None, memory=None, approval_callback=None):
        self.agent = agent_module
        self.router = TaskRouter()
        project_root = Path(getattr(agent_module, "__file__", __file__)).resolve().parent
        db_path = Path(__import__("os").environ.get(
            "NOVA_MEMORY_DB", str(project_root / "nova_shared_memory.sqlite3")
        ))
        self.memory = memory or SharedMemory(db_path)
        self.planner = TaskPlanner(agent_module, memory=self.memory)
        self.event_callback = event_callback or (lambda kind, message: None)
        self.approval_callback = approval_callback
        self._active_cancel_event: threading.Event | None = None
        self._current_task_id: str | None = None
        self._task_state = "queued"
        self._browser_runtime_ready = False
        self.specialists = {
            "reaction": ReactionAgent(agent_module, memory=self.memory),
            "chat": ChatAgent(agent_module, memory=self.memory),
            "browser": BrowserAgent(agent_module, memory=self.memory),
            "research": ResearchAgent(agent_module, memory=self.memory),
        }
        registered = set(agent_ids())
        wired = set(self.specialists)
        if registered != wired:
            missing = sorted(registered - wired)
            unregistered = sorted(wired - registered)
            raise RuntimeError(
                "NOVA specialist registry and Orchestrator wiring differ. "
                f"Missing implementations: {missing}; unregistered implementations: {unregistered}."
            )

    def _event(
        self, message: str, kind: str = "log", *, task_id: str | None = None,
        agent: str | None = None, step: int | None = None, event: str | None = None,
    ) -> None:
        metadata = {
            "task_id": task_id or self._current_task_id,
            "agent": agent,
            "step": step,
            "event": event or kind,
        }
        try:
            self.event_callback(kind, message, metadata)
        except TypeError:
            # Backwards-compatible callback contract for integrations that still
            # accept only (kind, message).
            try:
                self.event_callback(kind, message)
            except Exception:
                pass
        except Exception:
            pass

    def _set_state(self, state: str, message: str, *, agent: str | None = None, step: int | None = None) -> None:
        if not is_valid_task_transition(self._task_state, state):
            self._event(
                f"Execution state transition rejected: {self._task_state} → {state}.",
                kind="warning", agent=agent, step=step, event="invalid_state_transition",
            )
            return
        self._task_state = state
        # State transitions are part of the durable execution journal, not just
        # transient UI events. A process restart can therefore identify the last
        # known stage and mark it interrupted without replaying external actions.
        if self._current_task_id:
            try:
                self.memory.update_execution_state(self._current_task_id, state)
            except Exception as exc:
                self._event(
                    f"Execution state could not be persisted: {type(exc).__name__}.",
                    kind="warning", agent=agent, step=step, event="state_persist_failed",
                )
        self._event(message, kind="state", agent=agent, step=step, event=state)

    def _stop_event(self):
        return getattr(self.agent, "stop_event", None)

    def _stop_requested(self) -> bool:
        for event in (self._active_cancel_event, self._stop_event()):
            try:
                if event is not None and event.is_set():
                    return True
            except Exception:
                continue
        return False

    def _set_stop_requested(self) -> None:
        for event in (self._active_cancel_event, self._stop_event()):
            try:
                if event is not None and hasattr(event, "set"):
                    event.set()
            except Exception:
                continue

    def _ensure_specialist_available(self, agent_name: str) -> tuple[bool, str]:
        """Start the browser runtime only for Browser/Research tasks.

        Chat and Reaction remain available even when Brave or Playwright cannot
        start. The worker thread remains the single owner of the browser session.
        """
        if agent_name not in {"browser", "research"}:
            return True, ""
        starter = getattr(self.agent, "start_agent", None)
        if not callable(starter):
            return True, ""
        if self._browser_runtime_ready and getattr(self.agent, "_page", None) is not None:
            return True, ""
        try:
            started = starter()
        except Exception as exc:
            return False, f"Browser runtime could not start: {type(exc).__name__}: {exc}"
        if started is False:
            self._browser_runtime_ready = False
            return False, "Brave/Playwright could not start. Chat and Reaction remain available."
        self._browser_runtime_ready = True
        return True, ""

    @staticmethod
    def _validate_plan(plan: ExecutionPlan, task_id: str | None = None) -> str | None:
        if not isinstance(plan, ExecutionPlan):
            return "Planner returned an invalid plan object."
        if task_id and plan.task_id != task_id:
            return "Planner returned a plan for a different task ID."
        if not isinstance(plan.steps, list) or not plan.steps:
            return "Planner did not produce any executable steps."
        if len(plan.steps) > _MAX_PLAN_STEPS:
            return f"Execution plans are limited to {_MAX_PLAN_STEPS} steps."
        try:
            confidence = float(plan.confidence)
        except (TypeError, ValueError):
            return "Planner confidence must be a number between 0 and 100."
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 100.0:
            return "Planner confidence must be a finite number between 0 and 100."
        if not isinstance(plan.clarification_required, bool):
            return "Planner clarification_required must be a boolean."
        seen_steps: set[tuple[str, str]] = set()
        for index, step in enumerate(plan.steps):
            if not isinstance(step, PlanStep):
                return f"Planner step {index + 1} has an invalid structure."
            name = str(step.agent or "").strip().lower()
            if name not in _ALLOWED_AGENTS:
                return f"Planner selected an unavailable specialist: {name or 'unknown'}."
            if not isinstance(step.objective, str) or not step.objective.strip():
                return f"Planner step {index + 1} has no objective."
            if not isinstance(step.input_data, dict):
                return f"Planner step {index + 1} has invalid hand-off input."
            if not isinstance(step.expected_output, str):
                return f"Planner step {index + 1} has an invalid expected_output contract."
            if not isinstance(step.required_capabilities, tuple) or any(
                not isinstance(capability, str) for capability in step.required_capabilities
            ):
                return f"Planner step {index + 1} has invalid required capabilities."
            identity = (name, " ".join(step.objective.casefold().split()))
            if identity in seen_steps:
                return f"Planner repeated the same specialist objective in step {index + 1}."
            seen_steps.add(identity)
            if not isinstance(step.dependencies, tuple) or any(
                not isinstance(dep, int) or dep < 0 or dep >= index for dep in step.dependencies
            ):
                return f"Planner step {index + 1} has invalid dependencies; only earlier steps may be referenced."
            allowed_capabilities = agent_capabilities(name)
            if any(capability not in allowed_capabilities for capability in step.required_capabilities):
                return f"Planner step {index + 1} requests a capability not registered to {name}."
            if step.risk_level not in {"low", "medium", "high"}:
                return f"Planner step {index + 1} has an unsupported risk level."
        return None

    def _approval(
        self, request, step: PlanStep, reason: str,
        risk_level: str = "high", risk_category: str = "high_impact_action",
    ) -> tuple[bool, str]:
        payload = {
            "task_id": request.task_id,
            "command": request.command[:2000],
            "agent": step.agent,
            "objective": step.objective[:2000],
            "reason": reason,
            "risk_level": risk_level,
            "risk_category": risk_category,
            "expected_output": step.expected_output[:500],
        }
        self._event(
            f"🛡️ Approval required before Browser Agent can proceed: {step.objective[:220]}",
            kind="approval_required",
        )
        if not callable(self.approval_callback):
            return False, "No approval interface is connected; the action was blocked by default."
        try:
            decision = self.approval_callback(payload)
        except Exception as exc:
            return False, f"The approval request failed safely: {exc}"
        if isinstance(decision, dict):
            approved = bool(decision.get("approved", False))
            detail = str(decision.get("reason") or "").strip()
        else:
            approved = bool(decision)
            detail = ""
        return approved, detail or ("Approved by the user." if approved else "Approval was declined or expired.")

    def _timeout_for(self, step: PlanStep) -> float:
        raw = step.timeout_seconds
        if raw is None:
            raw = _DEFAULT_TIMEOUTS.get(step.agent, 90.0)
        try:
            return max(0.05, min(float(raw), 600.0))
        except (TypeError, ValueError):
            return _DEFAULT_TIMEOUTS.get(step.agent, 90.0)

    def _retry_budget(self, step: PlanStep) -> int:
        raw = step.max_retries
        if raw is None:
            raw = _DEFAULT_RETRIES.get(step.agent, 0)
        try:
            return max(0, min(int(raw), 2))
        except (TypeError, ValueError):
            return _DEFAULT_RETRIES.get(step.agent, 0)

    def execute(
        self,
        command: str,
        conversation_id: str | None = None,
        task_id: str | None = None,
        cancellation_event: threading.Event | None = None,
        response_callback=None,
        language: str = "auto",
    ) -> AgentResult:
        self._active_cancel_event = cancellation_event or threading.Event()
        from .language import normalize_language
        request = self.router.route(command, conversation_id=conversation_id)
        request = replace(request, context={**dict(request.context or {}), "language": normalize_language(language, default="auto")})
        if task_id:
            request = replace(request, task_id=str(task_id)[:128])
        self._current_task_id = request.task_id
        self._task_state = "queued"
        started = time.time()
        try:
            self.memory.start_execution(
                task_id=request.task_id,
                conversation_id=request.conversation_id,
                command=request.command,
            )
        except Exception as exc:
            self._event(f"⚠️ Could not start execution journal: {exc}")

        if self._stop_requested():
            self._set_state("cancelled", "Task cancelled before planning began.")
            final_result = AgentResult(
                task_id=request.task_id, agent="orchestrator", status="stopped",
                message="The task was stopped before planning began.",
            ).finish()
            self._finalise(request, final_result)
            return final_result

        self._set_state("planning", "NOVA is understanding the request and planning the next step.")
        self._event("🧭 Router: request validated; analysing intent.", event="request_validated")
        plan = self.planner.create_plan(request)
        if plan.source == "reaction-keyword":
            self._event("⚡ Reaction Router: exact social phrase matched; Qwen was bypassed.")
        elif plan.source == "fast-chat-route":
            self._event("⚡ Fast Chat: Planner inference skipped; Chat is answering directly.", event="fast_chat_route")
        elif plan.source == "qwen-clarification":
            self._event("🧠 Qwen Planner: intent is ambiguous; Chat will ask for clarification.")
        elif plan.source == "qwen":
            self._event("🧠 Qwen Planner: intent analysed; returning the plan to the Orchestrator.")
        else:
            self._event("⚠️ Planner fallback: using conservative local routing rules.")

        self._set_state("validating", "Orchestrator is validating the execution plan.")
        plan_error = self._validate_plan(plan, request.task_id)
        if plan_error:
            self._set_state("failed", "Orchestrator rejected the execution plan during validation.")
            final_result = AgentResult(
                task_id=request.task_id, agent="planner", status="failed",
                message="NOVA could not safely execute the Planner's proposed plan.",
                errors=[plan_error],
            ).finish()
            self._finalise(request, final_result)
            return final_result

        try:
            self.memory.update_execution_plan(request.task_id, {
                "schema_version": 2,
                "source": plan.source,
                "confidence": plan.confidence,
                "clarification_required": plan.clarification_required,
                "explanation": plan.explanation,
                "steps": [
                    {
                        "agent": step.agent, "objective": step.objective, "reason": step.reason,
                        "expected_output": step.expected_output,
                        "required_capabilities": list(step.required_capabilities),
                        "dependencies": list(step.dependencies), "risk_level": step.risk_level,
                    }
                    for step in plan.steps
                ],
            })
        except Exception as exc:
            self._event(f"⚠️ Could not persist execution plan: {exc}")

        self._set_state("executing", "NOVA has a plan and is starting the required work.")
        self._event(f"🧭 Orchestrator: accepted plan — {plan.explanation} [source: {plan.source}]")
        final_result: AgentResult | None = None
        previous_results: list[dict[str, Any]] = []
        completed_steps: list[dict[str, Any]] = []

        for step_index, step in enumerate(plan.steps):
            if self._stop_requested():
                final_result = AgentResult(
                    task_id=request.task_id, agent="orchestrator", status="stopped",
                    message="The task was stopped before the next specialist could start.",
                ).finish()
                break

            specialist = self.specialists.get(step.agent)
            if specialist is None:
                final_result = AgentResult(
                    task_id=request.task_id, agent="orchestrator", status="failed",
                    message=f"Unknown specialist: {step.agent}",
                    errors=[f"No specialist registered for '{step.agent}'."],
                ).finish()
                break

            approval_audit = {"required": False, "approved": None}
            if step.agent == "browser":
                risk_assessment = classify_action_risk(request.command, step.objective)
                if risk_assessment.get("blocked"):
                    final_result = AgentResult(
                        task_id=request.task_id, agent="policy", status="stopped",
                        message=str(risk_assessment["reason"]),
                        errors=["Critical browser action blocked by local NOVA policy."],
                        data={"risk_assessment": risk_assessment},
                    ).finish()
                    self._event(
                        str(risk_assessment["reason"]), kind="warning",
                        agent=step.agent, step=step_index, event="critical_action_blocked",
                    )
                    break
                if risk_assessment["requires_approval"]:
                    risk = str(risk_assessment["reason"])
                    approval_started = time.time()
                    self._set_state("awaiting_approval", "Waiting for your approval before the browser action can continue.", agent=step.agent, step=step_index)
                    self._event(
                        f"🛡️ Browser action classified as {risk_assessment['risk_level']} impact; waiting for explicit user approval.",
                        agent=step.agent, step=step_index, event="approval_required",
                    )
                    approved, detail = self._approval(
                        request, step, risk,
                        risk_level=str(risk_assessment["risk_level"]),
                        risk_category=str(risk_assessment["category"]),
                    )
                    approval_audit = {
                        "required": True,
                        "approved": bool(approved),
                        "risk_level": risk_assessment["risk_level"],
                        "risk_category": risk_assessment["category"],
                        "reason": detail[:500],
                    }
                    try:
                        self.memory.record_execution_step(
                            task_id=request.task_id, step_index=step_index,
                            attempt=0, agent=step.agent, objective=step.objective,
                            status="approval_approved" if approved else "approval_denied",
                            started_at=approval_started, finished_at=time.time(),
                            result={"approval": approval_audit}, errors=[] if approved else [detail],
                        )
                    except Exception as exc:
                        self._event(f"⚠️ Could not journal approval decision: {exc}")
                    if not approved:
                        final_result = AgentResult(
                            task_id=request.task_id,
                            agent="orchestrator",
                            status="stopped",
                            message=(
                                "I did not perform that browser action because it was not approved. "
                                + detail
                            ),
                            data={"approval": approval_audit},
                        ).finish()
                        break
                    self._set_state("executing", "Approval received. NOVA is continuing the task.", agent=step.agent, step=step_index)
                    self._event("✅ User approved the high-impact browser action.", agent=step.agent, step=step_index, event="approval_granted")

            available, unavailable_reason = self._ensure_specialist_available(step.agent)
            if not available:
                final_result = AgentResult(
                    task_id=request.task_id, agent=step.agent, status="failed",
                    message=unavailable_reason, errors=[unavailable_reason],
                    data={"capability_unavailable": True},
                ).finish()
                completed_steps.append({"agent": step.agent, "status": "failed", "message": unavailable_reason, "attempts": 0})
                self._event(unavailable_reason, kind="error", agent=step.agent, step=step_index)
                break

            if step_index > 0:
                self._set_state("handing_off", f"Passing the previous result to {step.agent.title()} Agent.", agent=step.agent, step=step_index)
            if step.agent == "chat" and previous_results:
                self._set_state("synthesising", "Chat Agent is preparing the final response.", agent=step.agent, step=step_index)
            else:
                self._set_state("executing", f"{step.agent.title()} Agent is working on your request.", agent=step.agent, step=step_index)
            self._event(f"🧠 Planner: assigning task to {step.agent.title()} Agent.", agent=step.agent, step=step_index)
            timeout_seconds = self._timeout_for(step)
            retry_budget = self._retry_budget(step)
            timeout_hit = threading.Event()
            step_started = time.time()
            last_result: AgentResult | None = None

            for attempt in range(retry_budget + 1):
                if self._stop_requested():
                    break
                attempt_started = time.time()
                try:
                    self.memory.record_execution_step(
                        task_id=request.task_id, step_index=step_index,
                        attempt=attempt + 1, agent=step.agent,
                        objective=step.objective, status="running",
                        started_at=attempt_started,
                    )
                except Exception as exc:
                    self._event(f"⚠️ Could not journal step start: {exc}")

                step_context = dict(step.input_data or {})
                step_context.update({
                    "original_command": request.command,
                    "previous_results": list(previous_results),
                    "step_index": step_index,
                    "total_steps": len(plan.steps),
                    "attempt": attempt + 1,
                    "language": request.context.get("language", "auto"),
                })
                if step.agent == "chat" and callable(response_callback):
                    # This callback is an in-process runtime hook, not user input
                    # or persisted task data. Browser/Research never receive it.
                    step_context["stream_callback"] = response_callback
                specialist_request = replace(
                    request,
                    command=step.objective or request.command,
                    context=step_context,
                )

                def mark_timeout() -> None:
                    timeout_hit.set()
                    self._set_stop_requested()

                timer = threading.Timer(timeout_seconds, mark_timeout)
                timer.daemon = True
                timer.start()
                try:
                    raw_result = specialist.execute(specialist_request)
                except Exception as exc:
                    raw_result = AgentResult(
                        task_id=request.task_id, agent=step.agent, status="failed",
                        message=f"{step.agent.title()} Agent encountered an error.",
                        errors=[f"{type(exc).__name__}: {exc}"],
                    ).finish()
                finally:
                    timer.cancel()

                if not isinstance(raw_result, AgentResult):
                    raw_result = AgentResult(
                        task_id=request.task_id, agent=step.agent, status="failed",
                        message="The specialist returned an invalid result contract.",
                        errors=["Expected an AgentResult instance."],
                    ).finish()

                if raw_result.finished_at is None:
                    raw_result.finish()
                if not isinstance(raw_result.data, dict):
                    raw_result.data = {}
                if not isinstance(raw_result.errors, list):
                    raw_result.errors = ["Specialist errors field was invalid."]
                if not isinstance(raw_result.metadata, dict):
                    raw_result.metadata = {}
                contract_issues = raw_result.validated(task_id=request.task_id, expected_agent=step.agent)
                if contract_issues:
                    raw_result.status = "failed"
                    raw_result.errors.extend(contract_issues)
                    if not raw_result.message:
                        raw_result.message = "The specialist returned an invalid output."

                if timeout_hit.is_set():
                    raw_result.status = "timed_out"
                    raw_result.message = (
                        f"{step.agent.title()} Agent exceeded its time budget of {timeout_seconds:.1f} seconds. "
                        "The timeout signal was sent; a currently blocking operation may only stop when it yields."
                    )
                    raw_result.errors.append("Step time budget exceeded.")
                elif self._stop_requested() and raw_result.status == "completed":
                    raw_result.status = "stopped"
                    raw_result.message = "The task was stopped before this step could be accepted as complete."

                last_result = raw_result
                try:
                    self.memory.record_execution_step(
                        task_id=request.task_id, step_index=step_index,
                        attempt=attempt + 1, agent=step.agent,
                        objective=step.objective, status=raw_result.status,
                        started_at=attempt_started, finished_at=raw_result.finished_at or time.time(),
                        duration_ms=raw_result.duration_ms,
                        result=raw_result.to_handoff(), errors=raw_result.errors,
                    )
                except Exception as exc:
                    self._event(f"⚠️ Could not journal step result: {exc}")

                if (
                    raw_result.status == "failed"
                    and attempt < retry_budget
                    and not self._stop_requested()
                    and not timeout_hit.is_set()
                ):
                    self._set_state("retrying", f"{step.agent.title()} Agent encountered a temporary issue. Retrying.", agent=step.agent, step=step_index)
                    self._event(
                        f"🔁 {step.agent.title()} Agent failed without a confirmed completion; "
                        f"retrying once ({attempt + 1}/{retry_budget}).",
                        agent=step.agent, step=step_index, event="retry",
                    )
                    continue
                break

            final_result = last_result
            if final_result is None:
                final_result = AgentResult(
                    task_id=request.task_id, agent="orchestrator", status="stopped",
                    message="The step was not started because cancellation was requested.",
                ).finish()
                break

            final_result.data.setdefault("routing", {
                "agent": step.agent,
                "reason": step.reason,
                "planner_source": plan.source,
                "planner_confidence": step.input_data.get("planner_confidence"),
                "needs_clarification": bool(step.input_data.get("needs_clarification", False)),
                "plan": plan.explanation,
                "step_index": step_index,
                "total_steps": len(plan.steps),
                "attempts": min(retry_budget + 1, attempt + 1),
                "timeout_seconds": timeout_seconds,
                "approval_required": bool(approval_audit.get("required")),
                "approval_approved": approval_audit.get("approved"),
                "expected_output": step.expected_output,
                "risk_level": step.risk_level,
                "required_capabilities": list(step.required_capabilities),
            })
            completed_steps.append({
                "agent": step.agent,
                "status": final_result.status,
                "message": final_result.message,
                "attempts": min(retry_budget + 1, attempt + 1),
                "duration_ms": final_result.duration_ms,
            })
            self._event(f"✅ {step.agent.title()} Agent returned: {final_result.status}.", agent=step.agent, step=step_index, event="specialist_result")
            if final_result.status in {"completed", "partial"}:
                previous_results.append(final_result.to_handoff())
            if final_result.status != "completed":
                break

        # One bounded recovery/synthesis step is allowed after partial work. It is
        # deliberately Chat-only: it explains the verified progress and limits,
        # and can never repeat a browser side effect or silently resume execution.
        followup_builder = getattr(self.planner, "create_partial_followup_plan", None)
        followup_plan = followup_builder(request, previous_results) if callable(followup_builder) else None
        if followup_plan is not None:
            followup_error = self._validate_plan(followup_plan, request.task_id)
            if followup_error or len(followup_plan.steps) != 1 or followup_plan.steps[0].agent != "chat":
                self._event(
                    "Orchestrator ignored an invalid or non-Chat partial-recovery plan.",
                    kind="warning", event="followup_plan_rejected",
                )
                followup_plan = None
        if (
            final_result is not None
            and final_result.status == "partial"
            and followup_plan is not None
            and final_result.agent != "chat"
            and len(plan.steps) < _MAX_PLAN_STEPS
            and not self._stop_requested()
        ):
            self._set_state("synthesising", "Chat Agent is explaining the partial result and what remains incomplete.", agent="chat", step=len(plan.steps))
            followup_started = time.time()
            try:
                self.memory.update_execution_plan(request.task_id, {
                    "schema_version": 2,
                    "source": plan.source,
                    "confidence": plan.confidence,
                    "explanation": plan.explanation + " | " + followup_plan.explanation,
                    "steps": [
                        {
                            "agent": step.agent, "objective": step.objective,
                            "reason": step.reason, "expected_output": step.expected_output,
                            "required_capabilities": list(step.required_capabilities),
                            "dependencies": list(step.dependencies), "risk_level": step.risk_level,
                        }
                        for step in [*plan.steps, *followup_plan.steps]
                    ],
                })
            except Exception as exc:
                self._event(f"⚠️ Could not persist recovery plan: {exc}")
            followup_request = replace(
                request,
                command="Prepare a transparent user-facing summary of the partial result. State what was completed, what was not completed, and what evidence or blockers remain. Do not claim an action succeeded unless the specialist result verifies it.",
                context={
                    "original_command": request.command,
                    "previous_results": list(previous_results),
                    "step_index": len(plan.steps),
                    "total_steps": len(plan.steps) + 1,
                    "bounded_followup": True,
                },
            )
            try:
                followup_result = self.specialists["chat"].execute(followup_request)
                if isinstance(followup_result, AgentResult):
                    if followup_result.finished_at is None:
                        followup_result.finish()
                    self.memory.record_execution_step(
                        task_id=request.task_id, step_index=len(plan.steps), attempt=1,
                        agent="chat", objective=followup_request.command,
                        status=followup_result.status, started_at=followup_started,
                        finished_at=followup_result.finished_at,
                        duration_ms=followup_result.duration_ms,
                        result=followup_result.to_handoff(), errors=followup_result.errors,
                    )
                    if followup_result.status == "completed" and followup_result.message.strip():
                        prior_result = final_result
                        final_result = followup_result
                        final_result.status = "partial"  # preserve the incomplete execution truth
                        final_result.data["partial_execution"] = {
                            "agent": prior_result.agent,
                            "status": prior_result.status,
                            "message": prior_result.message[:3000],
                            "errors": list(prior_result.errors[:8]),
                        }
                        completed_steps.append({
                            "agent": "chat", "status": "completed",
                            "message": "Summarised partial execution without replaying external actions.",
                            "attempts": 1, "duration_ms": followup_result.duration_ms,
                        })
            except Exception as exc:
                self._event(f"⚠️ Partial-result synthesis failed: {type(exc).__name__}: {exc}", kind="warning", agent="chat")

        if final_result is None:
            final_result = AgentResult(
                task_id=request.task_id,
                agent="orchestrator",
                status="failed",
                message="The Planner did not execute a specialist.",
            ).finish()
        if not isinstance(final_result.data, dict):
            final_result.data = {}
        final_result.data["execution_steps"] = completed_steps
        final_result.data["execution_journal"] = {
            "schema_version": 2,
            "durable": True,
            "steps_recorded": len(completed_steps),
        }
        final_state = {
            "completed": "completed", "partial": "partial", "failed": "failed",
            "stopped": "cancelled", "timed_out": "timed_out",
        }.get(final_result.status, "failed")
        self._set_state(final_state, f"NOVA finished the task with status: {final_state}.", agent=final_result.agent)

        final_result.started_at = started
        final_result.finished_at = time.time()
        self._finalise(request, final_result)
        return final_result

    def _finalise(self, request, result: AgentResult) -> None:
        try:
            self.memory.finish_execution(
                task_id=request.task_id,
                status=result.status,
                final_agent=result.agent,
                final_message=result.message,
                state={
                    "completed": "completed", "partial": "partial", "failed": "failed",
                    "stopped": "cancelled", "timed_out": "timed_out",
                }.get(result.status, "failed"),
            )
        except Exception as exc:
            self._event(f"⚠️ Execution journal finalisation failed: {exc}")
        try:
            self.memory.record_task(
                task_id=request.task_id,
                conversation_id=request.conversation_id,
                command=request.command,
                agent=result.agent,
                status=result.status,
                result=result.message,
                duration_ms=result.duration_ms,
            )
        except Exception as exc:
            self._event(f"⚠️ Shared memory write failed: {exc}")
