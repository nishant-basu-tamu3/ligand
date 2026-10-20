"""Agent-side driver: emits intents to a Ligand engine, resolves clarifications with an oracle agent,
judges results against gold, and records per-emit metrics. Feedback (optionally noisy) is piggybacked on the next emit."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field

from ligand.engine import Cfg, Engine
from ligand.text import ntok
from ligand.world import World

from .tasks import judge, make_tasks

EMIT_OVERHEAD = 14   # tool-call wrapper tokens (name, braces)


@dataclass
class Rec:
    task: str
    tid: str
    split: str
    pi: int
    ok: bool
    asked: bool
    status: str
    out_tok: int          # tokens the agent writes (emit + optional pick)
    in_tok: int           # tokens the agent reads back from Ligand (responses)
    turns: int            # model turns spent on Ligand calls
    n_calls: int
    router_ms: float
    chain: tuple
    fast: bool = False
    gold_chain: tuple = ()
    needed: bool = False
    par_ms: float = 0.0


def make_engine(world: World, tools, cfg: Cfg | None = None) -> Engine:
    tm = {t.fq: t for t in tools}

    def backend(fq, args):
        return tm[fq].fn(args)
    return Engine(tools, backend, cfg)


def agent_emit(eng: Engine, task: dict, pi: int, prev=None) -> tuple[Rec, str]:
    ph = task["phr"][pi]
    want = list(ph["want"])
    payload = {"goal": ph["goal"], "have": ph["have"], "want": want}
    if prev is not None:
        payload["prev"] = [prev[0], prev[1]]
    out_tok = ntok(payload) + EMIT_OVERHEAD
    em = eng.emit(ph["goal"], ph["have"], want, prev=prev)
    in_tok = ntok(em.response)
    turns = 1
    needed = False
    if em.status == "need":
        # near-miss: Ligand returned the field names it does have; the (oracle) agent re-emits with the right ones
        needed = True
        fixed = list(want)
        for w in em.missing:
            i = want.index(w)
            if task["canon"][i] in em.fields:
                fixed[i] = task["canon"][i]
        want = fixed
        out_tok += ntok({"goal": ph["goal"], "have": ph["have"], "want": want}) + EMIT_OVERHEAD
        em = eng.emit(ph["goal"], ph["have"], want)
        in_tok += ntok(em.response)
        turns += 1
    asked = em.status == "ask"
    gold_chain = tuple(fq for fq, _ in task["chain"])
    router_ms = em.router_ms
    par_ms = em.par_ms
    n_calls = em.n_calls
    if asked:
        k = next((i for i, key in enumerate(em.cands) if key == gold_chain), -1)
        out_tok += ntok({"pick": k, "t": em.ticket}) + EMIT_OVERHEAD
        em2 = eng.pick(em.ticket, k)
        in_tok += ntok(em2.response)
        turns += 1
        router_ms += em2.router_ms
        par_ms += em2.router_ms
        n_calls += em2.n_calls
        em = em2
    ok = em.status == "ok" and judge(task, pi, em.rows)
    rec = Rec(task["id"], task["tid"], task["split"], pi, ok, asked, em.status, out_tok, in_tok, turns, n_calls, router_ms,
              em.chain_key, em.fast, gold_chain, needed, par_ms)
    return rec, em.ticket


def run_sequence(eng: Engine, tasks: list[dict], order: list[tuple], learn: bool, noise: float = 0.0, rng: random.Random | None = None) -> list[Rec]:
    """order: [(task_index, phrasing_index)]. If learn, outcome feedback is piggybacked on the next emit."""
    rng = rng or random.Random(0)
    recs, prev = [], None
    for ti, pi in order:
        rec, ticket = agent_emit(eng, tasks[ti], pi, prev if learn else None)
        recs.append(rec)
        if learn and rec.status in ("ok",):
            fb = rec.ok if rng.random() >= noise else (not rec.ok)
            prev = (ticket, fb)
        else:
            prev = None
    if learn and prev is not None:
        eng.feedback(*prev)
    return recs


def summarize(recs: list[Rec]) -> dict:
    n = len(recs) or 1
    return {
        "n": len(recs),
        "success": sum(r.ok for r in recs) / n,
        "ask_rate": sum(r.asked for r in recs) / n,
        "need_rate": sum(r.needed for r in recs) / n,
        "none_rate": sum(r.status in ("none", "need") for r in recs) / n,
        "wrong_bind": sum((r.status == "ok") and not r.ok for r in recs) / n,
        "turns": sum(r.turns for r in recs) / n,
        "out_tok": sum(r.out_tok for r in recs) / n,
        "in_tok": sum(r.in_tok for r in recs) / n,
        "router_ms": sum(r.router_ms for r in recs) / n,
        "par_ms": sum(r.par_ms for r in recs) / n,
    }
