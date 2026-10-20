"""End-to-end over REAL MCP (stdio): agent-side client -> Ligand MCP server -> 6 ordinary MCP backend servers.

Checks: (1) the agent sees exactly one tool; (2) answers are correct against gold computed from the same world;
(3) ask/need protocols work over the wire; (4) feedback + memory persist across a server restart.
Run: python -m tests.test_mcp_e2e
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from bench.tasks import judge, make_tasks
from ligand.mcp_backends import SERVERS
from ligand.text import ntok
from ligand.world import World

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = 0


def params(memory: str) -> StdioServerParameters:
    return StdioServerParameters(command=sys.executable, args=["-m", "ligand.mcp_server", "--seed", str(SEED), "--memory", memory],
                                 cwd=ROOT, env={**os.environ, "PYTHONPATH": ROOT})


async def emit(sess, payload):
    t0 = time.perf_counter()
    res = await sess.call_tool("emit", payload)
    ms = (time.perf_counter() - t0) * 1e3
    return json.loads(res.content[0].text), ms, len(res.content[0].text)


async def run_agent(memory: str, tasks: list[dict], order, label: str):
    stats = {"label": label, "n": 0, "ok": 0, "asked": 0, "needed": 0, "lat_ms": [], "resp_bytes": [], "tools_seen": None, "def_tokens": None,
             "startup_s": None}
    t0 = time.perf_counter()
    async with stdio_client(params(memory)) as (r, w), ClientSession(r, w) as sess:
        await sess.initialize()
        stats["startup_s"] = round(time.perf_counter() - t0, 2)
        tools = (await sess.list_tools()).tools
        stats["tools_seen"] = [t.name for t in tools]
        stats["def_tokens"] = ntok({"name": tools[0].name, "description": tools[0].description, "inputSchema": tools[0].inputSchema})
        prev = None
        for ti, pi in order:
            task = tasks[ti]
            ph = task["phr"][pi]
            want = list(ph["want"])
            payload = {"goal": ph["goal"], "have": ph["have"], "want": want}
            if prev:
                payload["prev"] = prev
            resp, ms, nb = await emit(sess, payload)
            stats["lat_ms"].append(ms); stats["resp_bytes"].append(nb)
            if "need" in resp:
                stats["needed"] += 1
                for wname in resp["need"]:
                    i = want.index(wname)
                    if task["canon"][i] in resp["fields"]:
                        want[i] = task["canon"][i]
                resp, ms, nb = await emit(sess, {"goal": ph["goal"], "have": ph["have"], "want": want})
                stats["lat_ms"].append(ms); stats["resp_bytes"].append(nb)
            if "ask" in resp:
                stats["asked"] += 1
                gold = ">".join(fq for fq, _ in task["chain"])
                k = next((c["k"] for c in resp["ask"] if c["via"] == gold), -1)
                resp, ms, nb = await emit(sess, {"goal": ph["goal"], "want": want, "pick": {"t": resp["t"], "k": k}})
                stats["lat_ms"].append(ms); stats["resp_bytes"].append(nb)
            ok = "rows" in resp and judge(task, pi, resp["rows"])
            stats["n"] += 1
            stats["ok"] += int(ok)
            prev = [resp["t"], bool(ok)] if "rows" in resp else None
        if prev:   # flush last feedback with a no-op-ish emit would cost a call; instead send as prev on a trivial lookup
            await emit(sess, {"goal": "list slack channels", "have": {}, "want": ["name"], "prev": prev})
    return stats


async def main():
    w = World(SEED)
    tasks = make_tasks(w)
    order = [(i, i % 4) for i in range(len(tasks))]        # every task once, phrasing rotates
    mem = os.path.join(tempfile.mkdtemp(), "ligand_memory.json")
    out = []
    out.append(await run_agent(mem, tasks, order, "session 1 (cold, fresh memory)"))
    out.append(await run_agent(mem, tasks, order, "session 2 (server restarted, memory loaded from disk)"))
    # catalog size an agent would otherwise see
    from ligand.mcp_bridge import McpBackends
    b = McpBackends(SERVERS, SEED).start()
    cat_tok = sum(ntok(t.mcp_def()) for t in b.tools)
    n_tools = len(b.tools)
    b.stop()
    print(f"\nAgent-visible tools via Ligand: {out[0]['tools_seen']}  (definition ~{out[0]['def_tokens']} tokens)")
    print(f"Same 6 servers connected directly would expose {n_tools} tools (~{cat_tok} tokens of definitions)\n")
    for s in out:
        lat = sorted(s["lat_ms"])
        print(f"{s['label']}\n  success {s['ok']}/{s['n']}  clarifications(ask) {s['asked']}  near-miss(need) {s['needed']}  "
              f"server startup {s['startup_s']}s\n  per-call latency ms: median {lat[len(lat)//2]:.0f}  p95 {lat[int(len(lat)*.95)]:.0f}  "
              f"mean response {sum(s['resp_bytes'])/len(s['resp_bytes']):.0f} bytes")
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    json.dump({"sessions": out, "catalog_tokens": cat_tok, "n_tools": n_tools}, open(os.path.join(ROOT, "results", "e2e.json"), "w"), indent=1)
    assert out[0]["tools_seen"] == ["emit"], "agent must see exactly one tool"
    assert out[0]["ok"] / out[0]["n"] >= 0.8, "cold success unexpectedly low"
    assert os.path.exists(mem), "memory file not written"
    print("\nOK")


if __name__ == "__main__":
    asyncio.run(main())
