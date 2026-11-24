"""Golden Macro Compilation & Zero-Token Fast-Path Execution Engine (Fix 5.1).

Compiles verified successful execution plans (+100 reward) into deterministic,
zero-token native action sequences that execute in < 1ms without calling LLMs.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from .contracts import AgentResult, ExecutionPlan, PlanStep, TaskRequest


class MacroCompiler:
    """Compiles golden execution paths into zero-token replayable macros."""

    def __init__(self, memory=None):
        self.memory = memory
        self._in_memory_cache: dict[str, dict[str, Any]] = {}

    @staticmethod
    def normalize_command(command: str) -> str:
        """Normalize command string for canonical macro lookup."""
        cmd = command.strip().lower()
        while True:
            new_cmd = re.sub(r"^(?:hey\s+nova[,!\s]*|nova[,!\s]*|please\s+|can\s+you\s+)", "", cmd).strip()
            if new_cmd == cmd:
                break
            cmd = new_cmd
        return " ".join(cmd.split())

    def compile(
        self,
        command: str,
        plan: ExecutionPlan,
        result: AgentResult,
        duration_ms: float = 0.0,
    ) -> dict[str, Any] | None:
        """Compile a verified successful execution plan into a fast-path macro."""
        if result.status != "completed":
            return None

        # Do not compile social reactions or single trivial chat steps
        if plan.source == "reaction-keyword" or (len(plan.steps) == 1 and plan.steps[0].agent == "reaction"):
            return None

        canonical = self.normalize_command(command)
        macro_id = "macro_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

        serialized_steps = [
            {
                "agent": step.agent,
                "objective": step.objective,
                "reason": step.reason,
                "input_data": step.input_data,
                "risk_level": step.risk_level,
            }
            for step in plan.steps
        ]

        macro = {
            "id": macro_id,
            "command_pattern": canonical,
            "steps": serialized_steps,
            "success_count": 1,
            "avg_latency_ms": duration_ms,
            "created_at": time.time(),
            "updated_at": time.time(),
        }

        self._in_memory_cache[canonical] = macro

        if self.memory is not None and hasattr(self.memory, "save_compiled_macro"):
            try:
                self.memory.save_compiled_macro(
                    macro_id=macro_id,
                    command_pattern=canonical,
                    steps=serialized_steps,
                    latency_ms=duration_ms,
                )
            except Exception:
                pass

        return macro

    def match_fast_path(self, command: str) -> dict[str, Any] | None:
        """Find a compiled golden macro in < 0.01ms."""
        canonical = self.normalize_command(command)
        if canonical in self._in_memory_cache:
            return self._in_memory_cache[canonical]

        if self.memory is not None and hasattr(self.memory, "get_compiled_macro"):
            try:
                macro = self.memory.get_compiled_macro(canonical)
                if macro:
                    self._in_memory_cache[canonical] = macro
                    return macro
            except Exception:
                pass

        return None

    def execute_fast_path(
        self,
        macro: dict[str, Any],
        request: TaskRequest,
        specialists: dict[str, Any],
    ) -> AgentResult:
        """Replay compiled macro sequence with 0 LLM tokens and sub-millisecond dispatch."""
        t0 = time.perf_counter()
        steps_data = macro.get("steps") or []
        completed_results = []
        last_result = None

        for idx, step_info in enumerate(steps_data):
            agent_name = step_info.get("agent")
            specialist = specialists.get(agent_name)
            if not specialist:
                return AgentResult(
                    task_id=request.task_id,
                    agent="macro_engine",
                    status="failed",
                    message=f"Specialist '{agent_name}' unavailable for compiled macro.",
                ).finish()

            step_req = TaskRequest(
                task_id=f"{request.task_id}-macro-{idx}",
                command=step_info.get("objective", request.command),
                conversation_id=request.conversation_id,
                context={
                    **dict(step_info.get("input_data") or {}),
                    "original_command": request.command,
                    "previous_results": completed_results,
                    "is_macro_replay": True,
                },
            )

            res = specialist.execute(step_req)
            last_result = res
            if res.status != "completed":
                return AgentResult(
                    task_id=request.task_id,
                    agent=agent_name,
                    status=res.status,
                    message=f"Macro execution stalled at step #{idx + 1}: {res.message}",
                    data={"macro_id": macro.get("id"), "failed_step": idx},
                ).finish()

            completed_results.append(res.to_handoff())

        total_duration_ms = (time.perf_counter() - t0) * 1000
        message = last_result.message if last_result else "Macro execution completed successfully."

        return AgentResult(
            task_id=request.task_id,
            agent="macro_compiler",
            status="completed",
            message=message,
            data={
                "zero_token_fast_path": True,
                "macro_id": macro.get("id"),
                "steps_replayed": len(steps_data),
                "duration_ms": total_duration_ms,
                "token_cost": 0.0,
            },
        ).finish()
