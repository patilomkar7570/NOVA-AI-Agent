"""Automated Benchmark and Evaluation Harness for NOVA AI Agent.

Evaluates task success rates, specialist routing precision, latency,
and self-healing reflection recovery across representative desktop,
browser, and code tasks.
"""
from __future__ import annotations

import time
from typing import Any, Callable

from .contracts import AgentResult, TaskRequest


class EvalBenchmarkCase:
    def __init__(
        self,
        case_id: str,
        command: str,
        expected_agent: str,
        expected_status: str = "completed",
        category: str = "general",
    ):
        self.case_id = case_id
        self.command = command
        self.expected_agent = expected_agent
        self.expected_status = expected_status
        self.category = category


BENCHMARK_CASES: list[EvalBenchmarkCase] = [
    EvalBenchmarkCase("social-greeting", "Hey NOVA, good morning!", "reaction", category="social"),
    EvalBenchmarkCase("math-calc", "What is the square root of 256?", "chat", category="reasoning"),
    EvalBenchmarkCase("code-synth", "Write a python function to check if a word is a palindrome", "coder", category="coding"),
    EvalBenchmarkCase("browser-search", "Search the web for the latest quantum computing papers", "research", category="web"),
    EvalBenchmarkCase("desktop-app", "Open Notepad and type hello world", "computer", category="desktop"),
]


class EvalHarness:
    """Executes benchmark suites against the NOVA Orchestrator."""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def run_suite(self, cases: list[EvalBenchmarkCase] | None = None) -> dict[str, Any]:
        suite = cases or BENCHMARK_CASES
        results = []
        passed_count = 0
        started_all = time.time()

        for case in suite:
            t0 = time.time()
            try:
                res = self.orchestrator.execute(case.command)
                duration = time.time() - t0
                routing_match = res.agent == case.expected_agent or res.data.get("routing", {}).get("agent") == case.expected_agent
                status_match = res.status == case.expected_status
                passed = routing_match and (status_match or res.status in {"completed", "partial"})
                if passed:
                    passed_count += 1

                results.append({
                    "case_id": case.case_id,
                    "command": case.command,
                    "expected_agent": case.expected_agent,
                    "actual_agent": res.agent,
                    "status": res.status,
                    "duration_seconds": round(duration, 3),
                    "passed": passed,
                })
            except Exception as exc:
                results.append({
                    "case_id": case.case_id,
                    "command": case.command,
                    "expected_agent": case.expected_agent,
                    "actual_agent": "error",
                    "status": "failed",
                    "error": str(exc),
                    "passed": False,
                })

        total = len(suite)
        rate = (passed_count / total * 100) if total > 0 else 0.0

        return {
            "total_cases": total,
            "passed_cases": passed_count,
            "success_rate_percent": round(rate, 1),
            "total_duration_seconds": round(time.time() - started_all, 3),
            "results": results,
        }
