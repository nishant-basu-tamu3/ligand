"""The Ligand MCP server. An agent connects to THIS server only and sees ONE tool: emit.
Behind it, Ligand connects to ordinary MCP servers, reads their tool schemas, and routes intents.

  python -m ligand.mcp_server [--seed 0] [--memory path.json] [--v1 | --fast]
"""
from __future__ import annotations

import argparse
import asyncio
import json

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from .engine import Engine, cfg_fast, cfg_safe, cfg_v2
from .mcp_backends import SERVERS
from .mcp_bridge import McpBackends
from .protocol import EMIT_DEF


def build(engine: Engine, memory_path: str | None) -> Server:
    srv = Server("ligand")

    @srv.list_tools()
    async def _list() -> list[types.Tool]:
        return [types.Tool(**EMIT_DEF)]

    @srv.call_tool()
    async def _call(name: str, arguments: dict):
        if name != "emit":
            raise ValueError(f"unknown tool {name}")
        a = arguments or {}

        def work() -> str:
            if a.get("pick"):
                em = engine.pick(a["pick"]["t"], int(a["pick"]["k"]))
            else:
                prev = tuple(a["prev"]) if a.get("prev") else None
                em = engine.emit(a.get("goal", ""), a.get("have") or {}, list(a.get("want") or []), prev=prev)
            if memory_path and engine.log:
                engine.save(memory_path)
            return em.response

        text = await asyncio.to_thread(work)
        return [types.TextContent(type="text", text=text)]

    return srv


async def amain(args):
    bridge = McpBackends(SERVERS, args.seed).start()
    cfg = cfg_fast() if args.fast else (cfg_safe() if args.v1 else cfg_v2())
    engine = Engine(bridge.tools, bridge.call, cfg)
    if args.memory:
        try:
            engine.load(args.memory)
        except FileNotFoundError:
            pass
    srv = build(engine, args.memory)
    try:
        async with stdio_server() as (r, w):
            await srv.run(r, w, srv.create_initialization_options())
    finally:
        bridge.stop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--memory", default=None)
    ap.add_argument("--fast", action="store_true", help="v1 low-clarification operating point")
    ap.add_argument("--v1", action="store_true", help="use the v1 engine instead of v2 (type gate, index, bidding, contrastive memory)")
    asyncio.run(amain(ap.parse_args()))
