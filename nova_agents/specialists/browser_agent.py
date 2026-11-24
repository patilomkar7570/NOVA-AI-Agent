"""Adapter that exposes the existing browser engine as a specialist agent."""
from __future__ import annotations

import io
import os
import sys
import re
import time
from contextlib import redirect_stdout
from typing import Any

from ..contracts import AgentResult, TaskRequest
from ..language import detect_language_from_text, language_instruction, normalize_language
from ..policy import classify_action_risk


class BrowserTab:
    """Represents a named browser tab handle preserving DOM state and history."""
    def __init__(self, name: str, url: str = "about:blank", page: Any = None):
        self.name = name
        self.url = url
        self.page = page
        self.title = name
        self.created_at = time.time()
        self.last_active = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "title": self.title,
            "has_page": self.page is not None,
        }


class _TeeOutput(io.TextIOBase):
    """Capture task output while preserving the API's live event streaming."""
    def __init__(self, target):
        self.target = target
        self.buffer = io.StringIO()

    def write(self, text: str) -> int:
        if not text:
            return 0
        self.buffer.write(text)
        try:
            self.target.write(text)
        except UnicodeEncodeError:
            try:
                encoding = getattr(self.target, "encoding", None) or "ascii"
                self.target.write(text.encode(encoding, errors="replace").decode(encoding))
            except Exception:
                pass
        except Exception:
            pass
        return len(text)

    def flush(self) -> None:
        try:
            self.target.flush()
        except Exception:
            pass


class BrowserAgent:
    name = "browser"

    def __init__(self, agent_module, memory=None):
        self.agent = agent_module
        self.memory = memory
        self._tabs: dict[str, BrowserTab] = {}
        self._active_tab: str = "default"
        # Register initial default tab
        self._tabs["default"] = BrowserTab(
            name="default",
            url="about:blank",
            page=getattr(self.agent, "_page", None),
        )

    def open_tab(self, name: str, url: str = "about:blank") -> dict[str, Any]:
        """Open a new named tab handle and set it as active, preserving DOM sessions."""
        clean_name = name.strip().lower()
        page_handle = None
        pw_context = getattr(self.agent, "_browser_context", None)
        if pw_context is None and hasattr(self.agent, "_page"):
            page_obj = getattr(self.agent, "_page")
            pw_context = getattr(page_obj, "context", None)

        if pw_context is not None and callable(getattr(pw_context, "new_page", None)):
            try:
                page_handle = pw_context.new_page()
                if url and url != "about:blank":
                    page_handle.goto(url, timeout=10000)
            except Exception:
                pass

        tab = BrowserTab(name=clean_name, url=url, page=page_handle)
        self._tabs[clean_name] = tab
        self._active_tab = clean_name
        return {
            "action": "open_tab",
            "name": clean_name,
            "url": url,
            "active_tab": clean_name,
            "total_tabs": len(self._tabs),
        }

    def switch_tab(self, name: str) -> dict[str, Any]:
        """Switch active focus to a named tab handle preserving DOM state."""
        clean_name = name.strip().lower()
        if clean_name not in self._tabs:
            raise KeyError(f"Tab '{clean_name}' does not exist. Open tabs: {list(self._tabs.keys())}")
        self._active_tab = clean_name
        self._tabs[clean_name].last_active = time.time()
        tab = self._tabs[clean_name]
        if tab.page is not None and callable(getattr(tab.page, "bring_to_front", None)):
            try:
                tab.page.bring_to_front()
            except Exception:
                pass
        return {
            "action": "switch_tab",
            "active_tab": clean_name,
            "url": tab.url,
            "title": tab.title,
        }

    def close_tab(self, name: str) -> dict[str, Any]:
        """Close a named tab and fallback active focus to an available tab."""
        clean_name = name.strip().lower()
        if clean_name not in self._tabs:
            raise KeyError(f"Tab '{clean_name}' does not exist.")
        tab = self._tabs.pop(clean_name)
        if tab.page is not None and callable(getattr(tab.page, "close", None)):
            try:
                tab.page.close()
            except Exception:
                pass
        if self._active_tab == clean_name:
            self._active_tab = next(iter(self._tabs.keys()), "default")
            if self._active_tab not in self._tabs:
                self._tabs[self._active_tab] = BrowserTab(self._active_tab)
        return {
            "action": "close_tab",
            "closed": clean_name,
            "active_tab": self._active_tab,
            "remaining_tabs": list(self._tabs.keys()),
        }

    def list_tabs(self) -> list[dict[str, Any]]:
        """List all managed tabs with active status."""
        return [
            {
                **tab.to_dict(),
                "is_active": (tab.name == self._active_tab),
            }
            for tab in self._tabs.values()
        ]

    @staticmethod
    def detect_security_checkpoint(page_text: str = "", page_title: str = "", html_sample: str = "") -> dict[str, Any] | None:
        """Inspects live DOM and text for anti-bot challenges, CAPTCHAs, or 2FA verification gates.
        
        Returns structured gate metadata if detected; None otherwise.
        """
        combined = f"{page_title} {page_text} {html_sample}".lower()
        
        # Check Cloudflare Turnstile / Bot challenge
        if any(k in combined for k in ["cloudflare", "turnstile", "checking your browser", "cf-challenge", "please wait while we verify"]):
            return {
                "detected": True,
                "type": "cloudflare_turnstile",
                "label": "Cloudflare Bot Verification / Turnstile",
                "requires_pause": True,
                "guidance": "Please solve or verify the Cloudflare security gate in your browser. NOVA will pause and resume automatically.",
            }
        
        # Check reCAPTCHA / hCaptcha / Arkose
        if any(k in combined for k in ["recaptcha", "hcaptcha", "arkose", "verify you are human", "select all squares with", "complete the puzzle"]):
            return {
                "detected": True,
                "type": "interactive_captcha",
                "label": "Interactive CAPTCHA (reCAPTCHA / hCaptcha)",
                "requires_pause": True,
                "guidance": "Interactive CAPTCHA detected. Complete the verification in the browser tab to continue.",
            }

        # Check Two-Factor Authentication / OTP screen
        if any(k in combined for k in ["two-factor authentication", "2-step verification", "enter verification code", "enter otp", "authenticator app", "sms verification code"]):
            return {
                "detected": True,
                "type": "two_factor_auth",
                "label": "Two-Factor Authentication / OTP Screen",
                "requires_pause": True,
                "guidance": "2FA / OTP verification code required. Enter your authentication code in the browser.",
            }

        return None

    def check_and_handle_checkpoint(self, page_text: str = "", page_title: str = "") -> dict[str, Any] | None:
        """Evaluates whether page is blocked by a security gate and prepares a safe paused response."""
        gate = self.detect_security_checkpoint(page_text=page_text, page_title=page_title)
        if gate:
            return {
                "status": "paused",
                "checkpoint": gate,
                "message": f"Paused at {gate['label']}. {gate['guidance']}",
            }
        return None

    @staticmethod
    def _parse_tab_command(command: str) -> tuple[str, str, str | None] | None:
        cmd = command.strip().lower()
        m = re.match(r"^(?:open|create|new)\s+tab\s+([a-zA-Z0-9_\-]+)(?:\s+(?:at|to|with|for\s+)?\s*(https?://\S+))?$", cmd)
        if m:
            return "open", m.group(1), m.group(2)
        m = re.match(r"^switch\s+(?:to\s+)?tab\s+([a-zA-Z0-9_\-]+)$", cmd)
        if m:
            return "switch", m.group(1), None
        m = re.match(r"^close\s+tab\s+([a-zA-Z0-9_\-]+)$", cmd)
        if m:
            return "close", m.group(1), None
        if cmd in ("list tabs", "show tabs", "get tabs"):
            return "list", "", None
        return None

    @staticmethod
    def _is_informational_request(command: str) -> bool:
        cmd = command.lower().strip()
        info_keywords = (
            "summarize", "summarise", "summary", "explain", "tell me",
            "what is", "what are", "who is", "breakthrough", "breakthroughs",
            "news", "updates", "findings", "find out", "research", "details",
            "overview", "look up", "how to", "why does", "what does",
            "article", "content", "information", "latest"
        )
        return any(k in cmd for k in info_keywords) or cmd.endswith("?")

    def _synthesize_page_findings(self, command: str, observed: dict) -> str:
        if not isinstance(observed, dict):
            return ""
        ai_overview = str(observed.get("ai_overview") or "").strip()
        search_results = observed.get("search_results") or []
        article_content = str(observed.get("article_content") or "").strip()
        page_title = str(observed.get("title") or "").strip()

        evidence_blocks = []
        if ai_overview:
            evidence_blocks.append(f"AI OVERVIEW / DIRECT SUMMARY:\n{ai_overview}")
        if search_results and isinstance(search_results, list):
            res_lines = []
            for item in search_results[:6]:
                if not isinstance(item, dict):
                    continue
                t = str(item.get("title") or "").strip()
                s = str(item.get("snippet") or "").strip()
                if t or s:
                    res_lines.append(f"- {t}: {s}")
            if res_lines:
                evidence_blocks.append("SEARCH RESULTS & SOURCES:\n" + "\n".join(res_lines))
        if article_content:
            evidence_blocks.append(f"ARTICLE CONTENT:\n{article_content[:4000]}")

        if not evidence_blocks:
            interactive = observed.get("interactive") or []
            if isinstance(interactive, list) and interactive:
                inter_items = []
                for item in interactive[:8]:
                    if isinstance(item, dict):
                        role = item.get("role", "element")
                        txt = str(item.get("text") or item.get("aria_label") or "").strip()
                        if txt:
                            inter_items.append(f"- [{item.get('nova_id')}] {role}: {txt}")
                if inter_items:
                    evidence_blocks.append("PAGE INTERACTIVE ELEMENTS:\n" + "\n".join(inter_items))

        if not evidence_blocks:
            body_text = str(observed.get("text") or "").strip()
            if len(body_text) > 80:
                evidence_blocks.append(f"PAGE EXCERPT:\n{body_text[:3000]}")

        if not evidence_blocks:
            return ""

        combined_evidence = "\n\n".join(evidence_blocks)

        # 1. Try fast model synthesis if available
        chat_fn = getattr(self.agent, "chat", None)
        if callable(chat_fn):
            try:
                model_name = str(getattr(self.agent, "FAST_CHAT_MODEL", getattr(self.agent, "MODEL", "qwen3:8b")))
                response = chat_fn(
                    model=model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are NOVA's real-time web synthesis specialist. Provide a clear, structured, well-formatted "
                                "Markdown summary directly answering the user's request from the observed web page evidence. "
                                "Use concise bullet points and a brief **Summary:** line. Do NOT output raw input commands or action logs."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"USER REQUEST:\n{command}\n\nOBSERVED WEB PAGE EVIDENCE:\n{combined_evidence}",
                        },
                    ],
                    think=False,
                    keep_alive="20m",
                    options={"num_predict": 300, "num_ctx": int(getattr(self.agent, "QWEN_CONTEXT", 2048)), "temperature": 0.2},
                )
                content = str(getattr(getattr(response, "message", None), "content", "") or "").strip()
                if content and len(content) > 30:
                    return content
            except Exception:
                pass

        # 2. Deterministic high-quality structured response
        title_heading = f"### {page_title or 'Web Findings'} 🚀\n\n"
        sections = []
        if ai_overview:
            sections.append(f"**Key Overview:**\n{ai_overview}\n")
        if search_results and isinstance(search_results, list):
            sections.append("**Top Highlights & Breakthroughs:**")
            for item in search_results[:5]:
                if not isinstance(item, dict):
                    continue
                t = str(item.get("title") or "").strip()
                s = str(item.get("snippet") or "").strip()
                if t and s:
                    sections.append(f"- **{t}**: {s}")
                elif t:
                    sections.append(f"- **{t}**")
        elif article_content:
            sections.append(f"**Article Summary:**\n{article_content[:900]}...")

        if sections:
            return title_heading + "\n".join(sections) + f"\n\n**Summary:** Successfully scanned {page_title or 'the page'} and synthesized the latest findings."
        return ""


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
            last = action_results[-1].strip()
            # Clean up URLs for natural voice/chat feedback when URL is raw
            url_match = re.search(r"^Opened\s+(https?://[^\s]+)$", last, re.I)
            if url_match:
                from urllib.parse import urlsplit, parse_qs
                parsed = urlsplit(url_match.group(1))
                domain = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("en.").removeprefix("m.")
                if "google." in domain and parsed.path.startswith("/search"):
                    qs = parse_qs(parsed.query)
                    q = (qs.get("q") or [""])[0]
                    clean_term = q.replace("+", " ").strip()
                    return f"### Web Search: {clean_term}\n\nOpened search results for **{clean_term}**. Top findings and live links are displayed on screen." if clean_term else "Searched Google and displayed top results."
                domain_names = {
                    "youtube.com": "YouTube",
                    "github.com": "GitHub",
                    "reddit.com": "Reddit",
                    "twitter.com": "X",
                    "x.com": "X",
                    "wikipedia.org": "Wikipedia",
                    "amazon.com": "Amazon",
                    "netflix.com": "Netflix",
                    "discord.com": "Discord",
                    "whatsapp.com": "WhatsApp",
                }
                site_name = domain_names.get(domain) or (domain.split(".")[0].capitalize() if domain else "page")
                return f"Opened {site_name}."
            return "Done — " + last
        return "The browser task finished, but the page did not provide a separate answer."

    def execute(self, request: TaskRequest) -> AgentResult:
        result = AgentResult(
            task_id=request.task_id,
            agent=self.name,
            status="failed",
            message="Browser task did not complete.",
        )

        # First-class Multi-Tab Named Handles (Fix 2.1)
        tab_action = self._parse_tab_command(request.command)
        if tab_action:
            action_type, tab_name, tab_url = tab_action
            if action_type == "open":
                res = self.open_tab(tab_name, tab_url or "about:blank")
                result.status = "completed"
                result.message = f"Opened tab '{tab_name}' at {tab_url or 'about:blank'}."
                result.data = {"tab_action": res, "tabs": self.list_tabs(), "active_tab": self._active_tab}
                return result.finish()
            elif action_type == "switch":
                try:
                    res = self.switch_tab(tab_name)
                    result.status = "completed"
                    result.message = f"Switched to tab '{tab_name}'."
                    result.data = {"tab_action": res, "tabs": self.list_tabs(), "active_tab": self._active_tab}
                    return result.finish()
                except KeyError as e:
                    result.status = "failed"
                    result.message = str(e)
                    return result.finish()
            elif action_type == "close":
                try:
                    res = self.close_tab(tab_name)
                    result.status = "completed"
                    result.message = f"Closed tab '{tab_name}'. Active tab is now '{self._active_tab}'."
                    result.data = {"tab_action": res, "tabs": self.list_tabs(), "active_tab": self._active_tab}
                    return result.finish()
                except KeyError as e:
                    result.status = "failed"
                    result.message = str(e)
                    return result.finish()
            elif action_type == "list":
                tabs = self.list_tabs()
                result.status = "completed"
                result.message = f"Active tabs ({len(tabs)}): " + ", ".join(f"[{t['name']}{' *' if t['is_active'] else ''}]" for t in tabs)
                result.data = {"tabs": tabs, "active_tab": self._active_tab}
                return result.finish()

        # STRICT SANDBOX GUARD: In test/sandbox mode, never launch live browser if using real agent module
        if os.environ.get("NOVA_TEST_MODE") == "1" or os.environ.get("NOVA_SANDBOX_MODE") == "1":
            import types
            if isinstance(self.agent, types.ModuleType):
                run_task_attr = getattr(self.agent, "run_task", None)
                if not hasattr(run_task_attr, "assert_called") and not hasattr(self.agent, "_mock_return_value"):
                    result.status = "completed"
                    result.message = f"[Sandbox Mock] Browser task completed: {request.command}"
                    result.data = {
                        "verified": True,
                        "sandbox": True,
                        "verification": {"external_effect_confirmed": False, "level": "mock"},
                    }
                    return result

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
            if page is not None:
                try:
                    # Wait briefly for dynamic results (e.g. Gemini AI Overview, search listings) to settle
                    page.wait_for_load_state("domcontentloaded", timeout=2000)
                except Exception:
                    pass

            observed_page_text = ""
            observed_dict: dict[str, object] = {}
            observer = getattr(self.agent, "observe_page", None)
            if callable(observer):
                try:
                    observed = observer()
                    if isinstance(observed, dict):
                        observed_dict = observed
                        observed_page_text = str(observed.get("text") or "")[:12000]
                except Exception:
                    pass

            if page is not None:
                try:
                    is_closed = bool(page.is_closed()) if callable(getattr(page, "is_closed", None)) else False
                    if not is_closed:
                        current_url = str(getattr(page, "url", "") or "")
                        title_value = page.title() if callable(getattr(page, "title", None)) else ""
                        title = str(title_value or "")[:300]
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

            som_candidates = observed_dict.get("interactive") or []
            som_count = len(som_candidates) if isinstance(som_candidates, list) else 0
            verification.update({
                "som_count": som_count,
                "has_search_results": bool(observed_dict.get("search_results")),
                "has_ai_overview": bool(observed_dict.get("ai_overview")),
                "has_article_content": bool(observed_dict.get("article_content")),
            })
            if observed_dict.get("search_results") and isinstance(observed_dict.get("search_results"), list):
                for res in observed_dict["search_results"][:5]:
                    if isinstance(res, dict) and (res.get("url") or res.get("title")):
                        evidence.append({
                            "type": "search_result",
                            "url": str(res.get("url") or "")[:2000],
                            "title": str(res.get("title") or "")[:200],
                            "snippet": str(res.get("snippet") or "")[:300],
                        })

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
                orig_cmd = str(request.context.get("original_command") or request.command)
                wants_info = self._is_informational_request(orig_cmd)
                final_ans = self._final_answer(output)

                if "📌 ANSWER" in output and final_ans:
                    result.message = final_ans
                else:
                    synthesized = ""
                    if wants_info and observed_dict:
                        synthesized = self._synthesize_page_findings(orig_cmd, observed_dict)
                    if synthesized:
                        result.message = synthesized
                    else:
                        result.message = final_ans
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
