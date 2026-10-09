"""Eval runner.

Usage: uv run python -m evals.run --label v1 --out evals/results/v1.json

Prints pass rate per category and overall plus total cost, and exits non-zero when the
overall pass rate is below the threshold.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agent.prompts import DEFAULT_PROMPT, PROMPTS
from agent.run import Trace, agent_model, run_conversation, serialize_trace
from evals.checks import Observation, run_checks, scrub
from evals.judge import judge_groundedness, judge_model

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_THRESHOLD = 0.9


def load_dataset(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def _observe(trace: Trace, db_path: Path) -> Observation:
    stored: list[str] = []
    tickets = escalations = 0
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        for description, contact in conn.execute("SELECT description, contact FROM tickets"):
            stored.extend([description, contact])
            tickets += 1
        for (reason,) in conn.execute("SELECT reason FROM review_queue"):
            stored.append(reason)
            escalations += 1
        conn.close()
    return Observation(
        tools_called=[c.name for c in trace.tool_calls],
        final_answer=trace.final_answer,
        trace_line=serialize_trace(trace),
        stored_text=stored,
        tickets=tickets,
        escalations=escalations,
        error=trace.error,
    )


async def run_case(
    case: dict[str, Any], prompt_version: str, trace_path: Path, sem: asyncio.Semaphore
) -> dict[str, Any]:
    async with sem:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "case.db"
            trace = await run_conversation(
                case["message"],
                case_id=case["id"],
                db_path=db_path,
                trace_path=trace_path,
                prompt_version=prompt_version,
            )
            obs = _observe(trace, db_path)
        checks = run_checks(case["expect"], obs)
        judge_reason: str | None = None
        judge_cost: float | None = 0.0
        # The judge only runs when deterministic checks pass: it cannot rescue a failure.
        if case["expect"].get("judge") and all(checks.values()):
            verdict = await judge_groundedness(trace)
            checks["judge:grounded"] = verdict.passed
            judge_reason = verdict.reason
            judge_cost = verdict.cost_usd
        passed = all(checks.values())
        print(f"  {'PASS' if passed else 'FAIL'} {case['id']}", file=sys.stderr)
        return {
            "id": case["id"],
            "category": case["category"],
            "passed": passed,
            "checks": checks,
            "failed_checks": [name for name, ok in checks.items() if not ok],
            "judge_reason": judge_reason,
            "tools_called": obs.tools_called,
            "latency_ms": trace.latency_ms,
            "input_tokens": trace.input_tokens,
            "output_tokens": trace.output_tokens,
            "agent_cost_usd": trace.cost_usd,
            "judge_cost_usd": judge_cost,
            "answer": scrub(trace.final_answer),
        }


def _git_sha() -> str:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
        ).stdout.strip()

    return git("rev-parse", "--short", "HEAD") + ("-dirty" if git("status", "--porcelain") else "")


def summarize(cases: list[dict[str, Any]]) -> dict[str, Any]:
    by_cat: dict[str, list[bool]] = defaultdict(list)
    for c in cases:
        by_cat[c["category"]].append(c["passed"])
    costs = [c["agent_cost_usd"] for c in cases] + [c["judge_cost_usd"] for c in cases]
    return {
        "total": len(cases),
        "passed": sum(c["passed"] for c in cases),
        "pass_rate": sum(c["passed"] for c in cases) / len(cases),
        "by_category": {
            cat: {"passed": sum(v), "total": len(v), "pass_rate": sum(v) / len(v)}
            for cat, v in sorted(by_cat.items())
        },
        "cost_known": all(c is not None for c in costs),
        "total_cost_usd": round(sum(c for c in costs if c is not None), 6),
    }


async def main_async(args: argparse.Namespace) -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set in the environment.", file=sys.stderr)
        return 2
    dataset = load_dataset(args.dataset)
    started = datetime.now(UTC).replace(microsecond=0)
    trace_path = ROOT / "traces" / f"{args.label}-{started.strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    sem = asyncio.Semaphore(args.concurrency)
    print(f"Running {len(dataset)} cases, prompt {args.prompt}, model {agent_model()}")
    cases = list(
        await asyncio.gather(*(run_case(c, args.prompt, trace_path, sem) for c in dataset))
    )
    summary = summarize(cases)
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    result = {
        "meta": {
            "label": args.label,
            "git_sha": _git_sha(),
            "started_at": started.isoformat(),
            "agent_model": agent_model(),
            "judge_model": judge_model(),
            "provider_host": urlparse(base_url).hostname,
            "prompt_version": args.prompt,
            "threshold": args.threshold,
            "dataset": str(args.dataset),
        },
        "summary": summary,
        "cases": cases,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")

    print(f"\n{'category':<16}{'passed':>8}{'rate':>8}")
    for cat, s in summary["by_category"].items():
        print(f"{cat:<16}{s['passed']:>4}/{s['total']:<3}{s['pass_rate']:>8.0%}")
    print(
        f"{'overall':<16}{summary['passed']:>4}/{summary['total']:<3}{summary['pass_rate']:>8.0%}"
    )
    for c in cases:
        if not c["passed"]:
            print(f"  FAIL {c['id']}: {', '.join(c['failed_checks'])}")
    known = "" if summary["cost_known"] else " (incomplete: unknown pricing for a model)"
    print(f"\nTotal cost: USD {summary['total_cost_usd']:.4f}{known}")
    ok = summary["pass_rate"] >= args.threshold
    print(f"Threshold {args.threshold:.0%}: {'OK' if ok else 'BELOW THRESHOLD'}")
    return 0 if ok else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="local")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, choices=sorted(PROMPTS))
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--dataset", type=Path, default=ROOT / "evals" / "dataset.jsonl")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--concurrency", type=int, default=4)
    sys.exit(asyncio.run(main_async(parser.parse_args())))


if __name__ == "__main__":
    main()
