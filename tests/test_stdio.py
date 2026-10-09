"""End to end over stdio with a real MCP client. No LLM."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client
from mcp.types import TextContent


async def _roundtrip(db: Path) -> tuple[list[str], str, bool]:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "municerca_mcp.server"],
        env={**get_default_environment(), "MUNICERCA_DB": str(db)},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = [t.name for t in (await session.list_tools()).tools]
        ok = await session.call_tool("get_tramite", {"tramite_id": "poda-arboles"})
        bad = await session.call_tool("get_ticket_status", {"ticket_id": "OIRS-2026-999999"})
        text = "".join(c.text for c in ok.content if isinstance(c, TextContent))
        return tools, text, bool(bad.isError)


def test_stdio_roundtrip(tmp_path: Path) -> None:
    tools, text, unknown_ticket_is_error = asyncio.run(_roundtrip(tmp_path / "stdio.db"))
    assert len(tools) == 5
    assert '"horario": null' in text or '"horario":null' in text
    assert unknown_ticket_is_error
