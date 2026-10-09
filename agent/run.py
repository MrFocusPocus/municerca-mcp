"""Agent harness: one resident message through Claude with the MCP tools, one JSONL trace.

Usage: uv run python -m agent.run "¿Qué necesito para el permiso de circulación?"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast

import anthropic
from anthropic.types import MessageParam, ToolParam, ToolResultBlockParam
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client
from mcp.types import TextContent

from agent.pricing import cost_usd
from agent.prompts import DEFAULT_PROMPT, PROMPTS
from municerca_mcp.redaction import redact_text

MAX_TURNS = 6
MAX_TOKENS = 1024


def agent_model() -> str:
    return os.environ.get("MUNICERCA_AGENT_MODEL", "claude-haiku-5-5")


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    is_error: bool
    result: str


@dataclass
class Trace:
    case_id: str
    model: str
    prompt_version: str
    message: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None
    final_answer: str = ""
    stopped_reason: str = ""
    error: str | None = None


def serialize_trace(trace: Trace) -> str:
    """The exact line that is written to disk, redacted as a whole (Ley 19.628).

    Redacting the serialized line covers every field at once: the resident's message,
    tool arguments, tool results and the final answer.
    """
    return redact_text(json.dumps(asdict(trace), ensure_ascii=False))


def write_trace(trace: Trace, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(serialize_trace(trace) + "\n")


def _thinking_kwargs() -> dict[str, Any]:
    # Some providers think by default. MUNICERCA_THINKING=disabled turns it off.
    if os.environ.get("MUNICERCA_THINKING") == "disabled":
        return {"thinking": {"type": "disabled"}}
    return {}


async def _agent_loop(
    session: ClientSession, client: anthropic.AsyncAnthropic, trace: Trace, system: str
) -> None:
    listed = await session.list_tools()
    tools = [
        ToolParam(name=t.name, description=t.description or "", input_schema=t.inputSchema)
        for t in listed.tools
    ]
    messages: list[MessageParam] = [{"role": "user", "content": trace.message}]
    for _ in range(MAX_TURNS):
        response = await client.messages.create(
            model=trace.model,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=tools,
            messages=messages,
            **_thinking_kwargs(),
        )
        trace.input_tokens += response.usage.input_tokens
        trace.output_tokens += response.usage.output_tokens
        trace.stopped_reason = response.stop_reason or ""
        trace.final_answer = "".join(b.text for b in response.content if b.type == "text")
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            return
        messages.append({"role": "assistant", "content": cast(Any, response.content)})
        results: list[ToolResultBlockParam] = []
        for use in tool_uses:
            arguments = cast(dict[str, Any], use.input)
            outcome = await session.call_tool(use.name, arguments)
            text = "\n".join(c.text for c in outcome.content if isinstance(c, TextContent))
            trace.tool_calls.append(ToolCall(use.name, arguments, bool(outcome.isError), text))
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": use.id,
                    "content": text,
                    "is_error": bool(outcome.isError),
                }
            )
        messages.append({"role": "user", "content": results})
    trace.stopped_reason = "max_turns"


async def run_conversation(
    message: str,
    *,
    case_id: str,
    db_path: Path,
    trace_path: Path,
    prompt_version: str = DEFAULT_PROMPT,
) -> Trace:
    trace = Trace(
        case_id=case_id, model=agent_model(), prompt_version=prompt_version, message=message
    )
    # The server gets a minimal environment: no API key crosses the process boundary.
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "municerca_mcp.server"],
        env={**get_default_environment(), "MUNICERCA_DB": str(db_path)},
    )
    client = anthropic.AsyncAnthropic(timeout=90.0, max_retries=2)
    started = time.perf_counter()
    try:
        async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            await _agent_loop(session, client, trace, PROMPTS[prompt_version])
    except anthropic.APIError as exc:
        # Class name only: provider error bodies can echo the resident's text.
        trace.error = type(exc).__name__
    trace.latency_ms = int((time.perf_counter() - started) * 1000)
    trace.cost_usd = cost_usd(trace.model, trace.input_tokens, trace.output_tokens)
    write_trace(trace, trace_path)
    return trace


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message")
    parser.add_argument("--case-id", default="manual")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, choices=sorted(PROMPTS))
    parser.add_argument("--db", type=Path, default=Path("municerca.db"))
    parser.add_argument("--trace", type=Path, default=Path("traces/manual.jsonl"))
    args = parser.parse_args()
    trace = asyncio.run(
        run_conversation(
            args.message,
            case_id=args.case_id,
            db_path=args.db,
            trace_path=args.trace,
            prompt_version=args.prompt,
        )
    )
    print(trace.final_answer or f"[error: {trace.error}]")
    cost = "unknown" if trace.cost_usd is None else f"USD {trace.cost_usd:.6f}"
    print(
        f"\n[{trace.model}] tools={[c.name for c in trace.tool_calls]} "
        f"latency={trace.latency_ms}ms tokens={trace.input_tokens}/{trace.output_tokens} "
        f"cost={cost}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
