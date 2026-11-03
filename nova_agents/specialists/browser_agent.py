"""Adapter that exposes the existing browser engine as a specialist agent."""
from __future__ import annotations

import io
import sys
import re
from contextlib import redirect_stdout

from ..contracts import AgentResult, TaskRequest
from ..language import detect_language_from_text, language_instruction, normalize_language
from ..policy import classify_action_risk


class _TeeOutput(io.TextIOBase):
    """Capture task output while preserving the API's live event streaming."""
    def __init__(self, target):
        self.target = target
        self.buffer = io.StringIO()

    def write(self, text: str) -> int:
        if not text:
            return 0
        self.buffer.write(text)
        self.target.write(text)
        return len(text)

    def flush(self) -> None:
        self.target.flush()


class BrowserAgent:
    name = "browser"

    def __init__(self, agent_module, memory=None):
        self.agent = agent_module
        self.memory = memory

    @staticmethod
    def _final_answer(output: str) -> str:
        """Prefer the browser planner's explicit ANSWER, then its last action result."""
        answer_match = re.search(
            r"📌\s*ANSWER\s*\n(.*?)(?=\n\s*🎉\s*Task complete|\Z)",
            output,
            flags=re.DOTALL,
        )
        if answer_match:
            answer = answer_match.group(1).strip()
            if answer:
                return answer

        action_results = re.findall(r"(?:^|\n)\s*✅\s*(.+)", output)
        action_results = [
            item.strip() for item in action_results
            if item.strip() and item.strip().lower() not in {"task complete.", "task complete"}
        ]
        if action_results:
            return "Done — " + action_results[-1]
        return "The browser task finished, but the page did not provide a separate answer."

    def execute(self, request: TaskRequest) -> AgentResult:
        result = AgentResult(
            task_id=request.task_id,
            agent=self.name,
            status="failed",
            message="Browser task did not complete.",
        )
        stream = _TeeOutput(sys.stdout)
        try:
            # The API's one persistent worker owns Playwright. This adapter runs
            # inside that same worker; it never creates a second browser thread.
            with redirect_stdout(stream):
                import inspect
                run_task = self.agent.run_task
                run_parameters = inspect.signature(run_task).parameters
                if "language" in run_parameters or any(item.kind == inspect.Parameter.VAR_KEYWORD for item in run_parameters.values()):
                    run_task(request.command, language=request.context.get("language", "auto"))
                else:
                    run_task(request.command)
            output = stream.buffer.getvalue()
            verification: dict[str, object] = {
                "completion_marker": "🎉 Task complete." in output or "Task complete." in output,
                "level": "console_marker",
                "page_observed": False,
            }
            evidence: list[dict[str, str]] = []
            page = getattr(self.agent, "_page", None)
            observed_page_text = ""
            if page is not None:
                try:
                    is_closed = bool(page.is_closed()) if callable(getattr(page, "is_closed", None)) else False
                    if not is_closed:
                        current_url = str(getattr(page, "url", "") or "")
                        title_value = page.title() if callable(getattr(page, "title", None)) else ""
                        title = str(title_value or "")[:300]
                        observer = getattr(self.agent, "observe_page", None)
                        if callable(observer):
                            try:
                                observed = observer()
                                observed_page_text = str(observed.get("text") or "")[:12000] if isinstance(observed, dict) else ""
                            except Exception:
                                observed_page_text = ""
                        verification.update({
                            "page_observed": bool(current_url),
                            "level": "live_page_observation" if current_url else "console_marker",
                            "final_url": current_url[:2000],
                            "page_title": title,
                        })
                        if current_url:
                            evidence.append({"type": "page", "url": current_url[:2000], "title": title})
                except Exception as verify_exc:
                    verification["verification_warning"] = f"Could not inspect final page: {type(verify_exc).__name__}"
            result.data = {
                "console_output": output[-12000:],
                "verification": verification,
                "evidence": evidence,
                "warnings": [str(verification["verification_warning"])] if verification.get("verification_warning") else [],
            }
            result.metadata["verification_level"] = verification["level"]

            if getattr(self.agent, "stop_event", None) is not None and self.agent.stop_event.is_set():
                result.status = "stopped"
                result.message = "I stopped the browser task. You can give me a revised instruction whenever you're ready."
            elif "🎉 Task complete." in output or "Task complete." in output:
                result.status = "completed"
                result.message = self._final_answer(output)
                risk = classify_action_risk(
                    str(request.context.get("original_command") or request.command), request.command
                )
                if risk.get("requires_approval"):
                    confirmation_patterns = (
                        r"\b(message|email) sent\b", r"\b(post|publication) published\b",
                        r"\b(comment|review) (?:posted|published|submitted)\b",
                        r"\b(rating|vote) (?:saved|recorded|submitted)\b",
                        r"\b(thank you for your feedback|your feedback has been recorded)\b",
                        r"\b(successfully submitted|submission successful)\b",
                        r"\b(order confirmed|purchase successful|payment successful|payment confirmed)\b",
                        r"\b(reservation confirmed|booking confirmed|reservation has been made|booking successful)\b",
                        r"\b(deletion complete|successfully deleted|account closed|account deleted)\b",
                        r"\b(changes saved|settings updated successfully|password updated|profile saved)\b",
                        r"\b(your post is live|published successfully)\b",
                    )
                    confirmation_text = (output + "\n" + observed_page_text).lower()
                    confirmed = any(re.search(pattern, confirmation_text, re.I) for pattern in confirmation_patterns)
                    verification["external_effect_confirmed"] = confirmed
                    verification["external_effect_confirmation"] = "observed_confirmation_text" if confirmed else "not_found"
                    result.data["verification"] = verification
                    if not confirmed:
                        result.status = "partial"
                        result.message = (
                            "The browser flow reached its completion step, but NOVA could not find a "
                            "clear confirmation from the website that the external action succeeded. "
                            "Please verify the result on the website before relying on it."
                        )
                        result.data.setdefault("warnings", []).append(
                            "Approval allowed the attempt; external completion was not independently confirmed."
                        )
            elif any(marker in output for marker in ("❌", "⚠️ Maximum actions reached", "Maximum replans reached")):
                result.status = "partial"
                result.message = "I made partial progress. " + self._final_answer(output)
                result.errors.append("The browser task did not reach an explicit completion step.")
            else:
                result.status = "partial"
                result.message = self._final_answer(output)
        except Exception as exc:
            result.errors.append(str(exc))
            result.message = f"I couldn't complete that browser action.\n\nDetails: {exc}"
        if result.status in {"completed", "partial"} and result.message:
            selected_language = normalize_language(request.context.get("language", "auto"), default="auto")
            target_language = selected_language
            if target_language == "auto":
                target_language = detect_language_from_text(request.command, fallback="en") or "en"
            if target_language not in {"auto", "en"}:
                try:
                    response = self.agent.chat(
                        model=str(getattr(self.agent, "MODEL", "qwen3:8b")),
                        messages=[
                            {"role": "system", "content": "Translate the supplied NOVA browser-task summary faithfully into the requested language. Preserve URLs, website names, action status and all factual details. Do not add claims. " + language_instruction(target_language)},
                            {"role": "user", "content": result.message},
                        ],
                        think=False, keep_alive="20m",
                        options={"num_predict": 120, "num_ctx": int(getattr(self.agent, "QWEN_CONTEXT", 2048)), "temperature": 0},
                    )
                    translated = str(getattr(getattr(response, "message", None), "content", "") or "").strip()
                    if translated:
                        result.message = translated
                        if isinstance(result.data, dict):
                            result.data["reply"] = translated
                except Exception as language_error:
                    result.metadata["language_warning"] = f"Browser summary could not be translated: {type(language_error).__name__}"
        return result.finish()
