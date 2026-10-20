"""Bridge: connect to ordinary MCP servers (stdio), turn their live list_tools() into Ligand receptors,
and expose a synchronous call(fq, args) for the engine. Runs its own asyncio loop in a thread."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from .world import Out, Param, Tool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def to_tool(server: str, t, fn) -> Tool:
    """MCP tool definition -> Ligand Tool. Output fields come from outputSchema (if a server has none, outputs are unknown)."""
    props = (t.inputSchema or {}).get("properties", {})
    req = set((t.inputSchema or {}).get("required", []))
    params = [Param(n, p.get("description", ""), n in req, p.get("type", "string")) for n, p in props.items()]
    osch = t.outputSchema or {}
    kind, fields = "object", osch.get("properties", {})
    if "items" in fields and fields["items"].get("type") == "array":
        kind, fields = "list", fields["items"].get("items", {}).get("properties", {})
    outs = [Out(n, p.get("description", "")) for n, p in fields.items()]
    ann = getattr(t, "annotations", None)
    writes = bool(ann is not None and ann.readOnlyHint is False)
    return Tool(server, t.name, t.description or "", params, outs, kind, fn, writes)


class McpBackends:
    def __init__(self, servers: list[str], seed: int = 0):
        self.servers, self.seed = servers, seed
        self.tools: list[Tool] = []
        self.sessions: dict = {}
        self._ready = threading.Event()
        self._err: Exception | None = None
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.n_calls = 0

    def start(self, timeout: float = 90):
        self.thread.start()
        self._ready.wait(timeout)
        if self._err:
            raise self._err
        return self

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._main())

    async def _main(self):
        self._stop = asyncio.Event()
        try:
            async with AsyncExitStack() as stack:
                for name in self.servers:
                    params = StdioServerParameters(command=sys.executable, args=["-m", "ligand.mcp_backends", name, str(self.seed)],
                                                   cwd=ROOT, env={**os.environ, "PYTHONPATH": ROOT})
                    r, w = await stack.enter_async_context(stdio_client(params))
                    sess = await stack.enter_async_context(ClientSession(r, w))
                    await sess.initialize()
                    self.sessions[name] = sess
                    for t in (await sess.list_tools()).tools:
                        fq = f"{name}.{t.name}"
                        self.tools.append(to_tool(name, t, (lambda a, fq=fq: self.call(fq, a))))
                self._ready.set()
                await self._stop.wait()
        except Exception as e:  # surface startup errors to the caller
            self._err = e
            self._ready.set()

    async def _call(self, server: str, name: str, args: dict):
        res = await self.sessions[server].call_tool(name, args)
        if res.isError:
            raise RuntimeError(f"{server}.{name}: {res.content}")
        if res.structuredContent is not None:
            return res.structuredContent
        return json.loads(res.content[0].text)

    def call(self, fq: str, args: dict):
        server, name = fq.split(".", 1)
        self.n_calls += 1
        out = asyncio.run_coroutine_threadsafe(self._call(server, name, args), self.loop).result(30)
        if isinstance(out, dict) and set(out) == {"items"}:
            return out["items"]
        return out

    def stop(self):
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self._stop.set)
        self.thread.join(10)
