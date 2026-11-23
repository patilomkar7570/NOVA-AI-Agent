"""Model Context Protocol (MCP) Client and Skill Directory Loader for NOVA.

Provides standard JSON-RPC 2.0 interoperability with external MCP servers
(e.g., PostgreSQL, GitHub, Notion, Brave Search, FileSystem) and hot-reloading
of local markdown skills from a `skills/` directory.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import time
from typing import Any


class MCPClient:
    """Lightweight stdio JSON-RPC 2.0 client for Model Context Protocol servers."""

    def __init__(self, server_command: list[str], name: str = "mcp_server"):
        self.server_command = server_command
        self.name = name
        self._request_id = 0
        self._proc: subprocess.Popen | None = None

    def start(self) -> None:
        """Start the MCP server subprocess."""
        if self._proc is None:
            self._proc = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

    def stop(self) -> None:
        """Stop the MCP server subprocess."""
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            finally:
                self._proc = None

    def _send_rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send JSON-RPC request and wait for reply."""
        self.start()
        if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            raise RuntimeError("MCP server process is not available.")

        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        line = json.dumps(payload) + "\n"
        self._proc.stdin.write(line)
        self._proc.stdin.flush()

        # Read JSON-RPC response
        resp_line = self._proc.stdout.readline()
        if not resp_line:
            raise RuntimeError("MCP server closed connection without response.")
        return json.loads(resp_line)

    def list_tools(self) -> list[dict[str, Any]]:
        """Query server for available tools via `tools/list`."""
        try:
            resp = self._send_rpc("tools/list")
            return resp.get("result", {}).get("tools", [])
        except Exception:
            return []

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke a tool via `tools/call`."""
        return self._send_rpc("tools/call", {"name": tool_name, "arguments": arguments})


class SkillManager:
    """Discovers and parses local skills from a `skills/` directory."""

    def __init__(self, skills_dir: Path | str = "skills"):
        self.skills_dir = Path(skills_dir).resolve()
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._cached_skills: dict[str, dict[str, Any]] = {}

    def scan_skills(self) -> dict[str, dict[str, Any]]:
        """Scans the skills directory for `SKILL.md` or `.md` definitions."""
        found: dict[str, dict[str, Any]] = {}
        for skill_file in self.skills_dir.rglob("*.md"):
            try:
                content = skill_file.read_text(encoding="utf-8", errors="replace")
                skill_info = self._parse_skill_markdown(skill_file.stem, content, skill_file)
                if skill_info:
                    found[skill_info["id"]] = skill_info
            except Exception:
                continue
        self._cached_skills = found
        return found

    @staticmethod
    def _parse_skill_markdown(default_id: str, content: str, file_path: Path) -> dict[str, Any] | None:
        """Parses YAML frontmatter and markdown body of a skill definition."""
        skill_id = default_id.lower()
        title = default_id.title()
        description = ""
        tags = []

        # Parse YAML frontmatter if present (between --- and ---)
        frontmatter_match = re.match(r"^---\s*[\r\n]+([\s\S]+?)[\r\n]+---\s*[\r\n]+([\s\S]*)$", content)
        body = content
        if frontmatter_match:
            frontmatter_text = frontmatter_match.group(1)
            body = frontmatter_match.group(2)
            for line in frontmatter_text.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    k = key.strip().lower()
                    v = val.strip().strip("'\"")
                    if k in {"name", "title"}:
                        title = v
                    elif k == "id":
                        skill_id = v.lower()
                    elif k == "description":
                        description = v
                    elif k in {"tags", "capabilities"}:
                        tags = [t.strip() for t in v.split(",") if t.strip()]

        if not description:
            # Extract first non-heading line as description
            for line in body.splitlines():
                clean = line.strip().lstrip("#").strip()
                if clean:
                    description = clean[:180]
                    break

        return {
            "id": skill_id,
            "title": title,
            "description": description or f"Custom workflow for {title}",
            "tags": tags,
            "file_path": str(file_path),
            "instructions": body.strip(),
        }

    def match_skill(self, command: str) -> dict[str, Any] | None:
        """Find best matching skill for a user command."""
        skills = self.scan_skills()
        cmd_lower = command.lower()
        for skill in skills.values():
            if skill["id"] in cmd_lower or skill["title"].lower() in cmd_lower:
                return skill
            if any(tag.lower() in cmd_lower for tag in skill.get("tags", [])):
                return skill
        return None
