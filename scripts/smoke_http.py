"""Smoke test a hosted server: list tools and read one trámite over streamable HTTP.

Usage: MUNICERCA_AUTH_TOKEN=... uv run python scripts/smoke_http.py https://host/mcp
"""

from __future__ import annotations

import asyncio
import os
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import TextContent


async def smoke(url: str) -> None:
    headers = {"Authorization": f"Bearer {os.environ['MUNICERCA_AUTH_TOKEN']}"}
    async with (
        streamablehttp_client(url, headers=headers) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = [t.name for t in (await session.list_tools()).tools]
        print(f"tools: {tools}")
        result = await session.call_tool("get_tramite", {"tramite_id": "poda-arboles"})
        text = "".join(c.text for c in result.content if isinstance(c, TextContent))
        print(f"get_tramite(poda-arboles): {text[:160]}...")
        assert len(tools) == 5 and not result.isError


if __name__ == "__main__":
    asyncio.run(smoke(sys.argv[1]))
