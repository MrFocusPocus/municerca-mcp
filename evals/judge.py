"""LLM judge for groundedness. Used only where deterministic checks cannot decide."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import anthropic

from agent.pricing import cost_usd
from agent.run import Trace

RUBRIC = (Path(__file__).parent / "rubric.md").read_text("utf-8")


def judge_model() -> str:
    return os.environ.get("MUNICERCA_JUDGE_MODEL", "claude-sonnet-5-5")


@dataclass
class Verdict:
    passed: bool
    reason: str
    cost_usd: float | None


async def judge_groundedness(trace: Trace) -> Verdict:
    tool_log = "\n".join(
        f"- {c.name}({json.dumps(c.arguments, ensure_ascii=False)}) "
        f"{'ERROR' if c.is_error else 'OK'}: {c.result}"
        for c in trace.tool_calls
    )
    prompt = (
        f"<resident_message>\n{trace.message}\n</resident_message>\n\n"
        f"<tool_results>\n{tool_log or '(no tool was called)'}\n</tool_results>\n\n"
        f"<final_answer>\n{trace.final_answer}\n</final_answer>"
    )
    client = anthropic.AsyncAnthropic(timeout=90.0, max_retries=2)
    model = judge_model()
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=2000,
            system=RUBRIC,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as exc:
        return Verdict(False, f"judge error: {type(exc).__name__}", None)
    text = "".join(b.text for b in response.content if b.type == "text")
    cost = cost_usd(model, response.usage.input_tokens, response.usage.output_tokens)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        return Verdict(False, "judge returned no JSON", cost)
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return Verdict(False, "judge returned invalid JSON", cost)
    return Verdict(parsed.get("verdict") == "pass", str(parsed.get("reason", "")), cost)
