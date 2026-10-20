"""Token/turn cost models for the baselines, driven by REAL tool results from executing each task's reference chain.

IMPORTANT ASSUMPTIONS (all favour the baselines):
  * baseline agents are ORACLES: they always pick the right tools/arguments first time (100% success by construction);
  * code-mode code is correct on the first try;
  * only Ligand's routing is actually exercised (its success is measured, not assumed).
Token counts are estimates (~3.5 chars/token); only relative comparisons are meaningful.
Cost proxy: cache read = 0.1x input, new input = 1.0x, output = 5x (typical API price ratios).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from ligand.protocol import EMIT_DEF
from ligand.text import cos, ntok

from .tasks import run_gold_chain

SYS = 300            # system prompt tokens, identical across conditions
CALL_OVH = 14        # per tool-call wrapper tokens
SEARCH_DEF = {"name": "tool_search", "description": "Search the tool catalog by keyword and load the matching tool definitions.",
              "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "keywords"}}, "required": ["query"]}}
CODE_DEFS = [
    {"name": "search_docs", "description": "Search available API functions and return their TypeScript signatures.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "keywords"}}, "required": ["query"]}},
    {"name": "execute_code", "description": "Run TypeScript that calls the API functions; console.log the result.",
     "inputSchema": {"type": "object", "properties": {"code": {"type": "string", "description": "TypeScript source"}}, "required": ["code"]}},
]
BASH_DEF = {"name": "bash", "description": "Run a shell command and return stdout.",
            "inputSchema": {"type": "object", "properties": {"command": {"type": "string", "description": "command line"}}, "required": ["command"]}}


@dataclass
class Cost:
    raw_in: int      # total input tokens billed across turns, no caching
    out: int
    turns: int
    cost: float      # cost proxy with prefix caching
    peak_ctx: int


def conversation(static: int, task_tok: int, turns: list[tuple[int, int]]) -> Cost:
    """turns: [(assistant_out_tokens, tool_result_tokens)], last turn is the final answer (result 0)."""
    ctx = static + task_tok
    raw_in, cost, out_total, peak = 0, 0.0, 0, 0
    prev_ctx = 0
    for i, (o, r) in enumerate(turns):
        raw_in += ctx
        peak = max(peak, ctx)
        new = ctx - prev_ctx
        cost += 0.1 * prev_ctx + 1.0 * new + 5.0 * o
        out_total += o
        prev_ctx = ctx
        ctx += o + r
    return Cost(raw_in, out_total, len(turns), cost, peak)


def _call(fq, args):
    return ntok({"name": fq, "arguments": args}) + CALL_OVH


def _sig(tool) -> str:
    ps = ", ".join(f"{p.name}{'' if p.required else '?'}: {p.type}" for p in tool.params)
    os_ = ", ".join(o.name for o in tool.outs)
    return f"{tool.fq.replace('.', '_')}({{{ps}}}): Promise<{{{os_}}}>"


def _nearest(eng, tmap, goal, exclude, k):
    gv = eng.emb.embed(goal)
    cand = sorted((r for r in eng.recs if r.fq not in exclude), key=lambda r: -cos(gv, r.doc_vec))
    return [tmap[r.fq] for r in cand[:k]]


def baseline_costs(tasks, tools, eng, catalog_tools) -> dict[str, list[Cost]]:
    """catalog_tools: the full catalog the agent is connected to (may include distractors)."""
    tmap = {t.fq: t for t in catalog_tools}
    gold_map = {t.fq: t for t in tools}
    all_defs = sum(ntok(t.mcp_def()) for t in catalog_tools)
    n = len(catalog_tools)
    out: dict[str, list[Cost]] = {k: [] for k in ("raw_mcp", "tool_search", "code_mode", "cli_unfamiliar", "cli_familiar")}
    for task in tasks:
        steps = run_gold_chain(gold_map, task)
        goal = task["phr"][0]["goal"]
        tt = ntok(goal)
        final = (ntok(task["gold"]) + 12, 0)
        step_turns = []   # (out, result) per sequential step, raw JSON
        for step in steps:
            o = sum(_call(fq, a) for fq, a, _ in step)
            r = sum(ntok(res) for _, _, res in step)
            step_turns.append((o, r))
        shaped = ntok(task["gold"])
        gold_fqs = {fq for fq, _ in task["chain"]}

        # raw MCP: every definition in context
        out["raw_mcp"].append(conversation(SYS + all_defs, tt, step_turns + [final]))

        # tool search: one search turn returns 5 definitions
        near = _nearest(eng, tmap, goal, gold_fqs, 5 - len(gold_fqs)) if len(gold_fqs) < 5 else []
        loaded = [tmap[f] for f in gold_fqs] + near
        search_turn = (ntok({"query": goal[:40]}) + CALL_OVH, sum(ntok(t.mcp_def()) for t in loaded))
        out["tool_search"].append(conversation(SYS + ntok(SEARCH_DEF), tt, [search_turn] + step_turns + [final]))

        # code mode: search signatures, then one program, then answer
        sigs = [tmap[f] for f in gold_fqs] + _nearest(eng, tmap, goal, gold_fqs, max(0, 5 - len(gold_fqs)))
        t1 = (ntok({"query": goal[:40]}) + CALL_OVH, sum(ntok(_sig(t)) for t in sigs))
        code_tok = 45 + 55 * len(task["chain"])
        t2 = (code_tok + CALL_OVH, shaped)
        out["code_mode"].append(conversation(SYS + sum(ntok(d) for d in CODE_DEFS), tt, [t1, t2, final]))

        # CLI: results are human formatted text (~0.85x JSON)
        cli_steps = [(ntok({"command": " ".join([step[0][0].split('.')[0], step[0][0].split('.')[1]] + [f"--{k} {v}" for k, v in step[0][1].items()])}) * max(1, len(step)),
                      int(0.85 * r)) for step, (o, r) in zip(steps, step_turns)]
        listing = (CALL_OVH + 6, 30 + 12 * n)
        helps = []
        for step in steps:
            tool = gold_map[step[0][0]]
            helps.append((CALL_OVH + 8, 40 + 12 * len(tool.params)))
        unf = [listing]
        for h, c in zip(helps, cli_steps):
            unf += [h, c]
        out["cli_unfamiliar"].append(conversation(SYS + ntok(BASH_DEF), tt, unf + [final]))
        out["cli_familiar"].append(conversation(SYS + ntok(BASH_DEF), tt, cli_steps + [final]))
    return out


def ligand_cost(rec, task, emit_def_tok: int) -> Cost:
    """Per-emit record -> conversation cost. Turns on Ligand split evenly; plus the final answer turn."""
    k = max(1, rec.turns)
    turns = [(rec.out_tok // k, rec.in_tok // k)] * k
    final = (ntok(task["gold"]) + 12, 0)
    return conversation(SYS + emit_def_tok, ntok(task["phr"][rec.pi]["goal"]), turns + [final])


EMIT_DEF_TOK = ntok(EMIT_DEF)
