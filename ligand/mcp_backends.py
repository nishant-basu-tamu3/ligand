"""Plain, unmodified-style MCP servers (stdio) that expose the simulated company tools.
Run one:  python -m ligand.mcp_backends github 0
These know nothing about Ligand; they are ordinary MCP servers with inputSchema/outputSchema."""
from __future__ import annotations

import asyncio
import sys

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from .world import World

SERVERS = ["github", "slack", "notion", "calendar", "files", "crm"]


def build(server_name: str, seed: int) -> Server:
    tools = [t for t in World(seed).tools() if t.server == server_name]
    tm = {t.name: t for t in tools}
    srv = Server(f"acme-{server_name}")

    @srv.list_tools()
    async def _list() -> list[types.Tool]:
        return [types.Tool(name=t.name, description=t.desc, inputSchema=t.input_schema(), outputSchema=t.output_schema(),
                           annotations=types.ToolAnnotations(readOnlyHint=not t.writes)) for t in tools]

    @srv.call_tool()
    async def _call(name: str, arguments: dict):
        t = tm[name]
        res = t.fn(arguments or {})
        return {"items": res} if t.kind == "list" else res

    return srv


async def main(server_name: str, seed: int):
    srv = build(server_name, seed)
    async with stdio_server() as (r, w):
        await srv.run(r, w, srv.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0))
