"""Run all experiments. Usage: python -m bench.run_bench [--quick]  ->  results/results.json"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from dataclasses import asdict, replace
from multiprocessing import Pool

import numpy as np

from ligand.distractors import make_distractors
from ligand.engine import cfg_fast, cfg_safe
from ligand.protocol import EMIT_DEF
from ligand.text import ntok
from ligand.world import World

from .baselines import EMIT_DEF_TOK, baseline_costs, ligand_cost
from .runner import make_engine, run_sequence, summarize
from .tasks import make_tasks

SEEDS = [0, 1, 2, 3, 4]
CONDS = ["raw_mcp", "tool_search", "code_mode", "cli_unfamiliar", "cli_familiar"]


def catalog(world, n_total):
    tools = world.tools()
    extra = make_distractors(n_total - len(tools)) if n_total > len(tools) else []
    return tools, tools + extra


def _cost_summary(base, lig, recs, tasks, idx, split=None):
    keep_t = [i for i, t in enumerate(tasks) if split is None or t["split"] == split]
    keep_r = [j for j, r in enumerate(recs) if split is None or r.split == split]
    m = lambda xs: float(np.mean(xs))
    out = {}
    for c in CONDS:
        cs = [base[c][i] for i in keep_t]
        out[c] = {"raw_in": m([x.raw_in for x in cs]), "out": m([x.out for x in cs]), "turns": m([x.turns for x in cs]),
                  "cost": m([x.cost for x in cs]), "peak_ctx": m([x.peak_ctx for x in cs])}
    ls = [lig[j] for j in keep_r]
    out["ligand"] = {"raw_in": m([x.raw_in for x in ls]), "out": m([x.out for x in ls]), "turns": m([x.turns for x in ls]),
                     "cost": m([x.cost for x in ls]), "peak_ctx": m([x.peak_ctx for x in ls])}
    # Ligand with fallback: a failed emit costs the attempt PLUS a full tool-search run for that task
    fb_raw, fb_cost, fb_turns = [], [], []
    for j in keep_r:
        r, l = recs[j], lig[j]
        if r.ok:
            fb_raw.append(l.raw_in); fb_cost.append(l.cost); fb_turns.append(l.turns)
        else:
            b = base["tool_search"][idx[r.task]]
            fb_raw.append(l.raw_in + b.raw_in); fb_cost.append(l.cost + b.cost); fb_turns.append(l.turns + b.turns)
    out["ligand_with_fallback"] = {"raw_in": m(fb_raw), "cost": m(fb_cost), "turns": m(fb_turns)}
    return out


def run_cold(args):
    seed, name, cfg_kind, n_total, overrides = args
    w = World(seed)
    tools, cat = catalog(w, n_total)
    tasks = make_tasks(w)
    idx = {t["id"]: i for i, t in enumerate(tasks)}
    cfg = (cfg_fast if cfg_kind == "fast" else cfg_safe)(**overrides)
    eng = make_engine(w, cat, cfg)
    rng = random.Random(seed)
    order = [(i, pi) for i in range(len(tasks)) for pi in range(4)]
    rng.shuffle(order)
    recs = run_sequence(eng, tasks, order, learn=False)
    base = baseline_costs(tasks, tools, eng, cat)
    lig = [ligand_cost(r, tasks[idx[r.task]], EMIT_DEF_TOK) for r in recs]
    res = {"name": name, "seed": seed, "n_tools": len(cat), "overall": summarize(recs),
           "by_split": {s: summarize([r for r in recs if r.split == s]) for s in ("dev", "test")},
           "by_phr": {"ABCD"[p]: summarize([r for r in recs if r.pi == p]) for p in range(4)},
           "by_split_phr": {f"{s}/{'ABCD'[p]}": summarize([r for r in recs if r.split == s and r.pi == p]) for s in ("dev", "test") for p in range(4)},
           "by_tid": {t: summarize([r for r in recs if r.tid == t]) for t in sorted({r.tid for r in recs})},
           "costs": _cost_summary(base, lig, recs, tasks, idx),
           "costs_by_split": {sp: _cost_summary(base, lig, recs, tasks, idx, sp) for sp in ("dev", "test")}}
    # failures (for the report): chain chosen vs gold
    res["fails"] = [{"task": r.task, "pi": r.pi, "status": r.status, "asked": r.asked, "got": list(r.chain), "gold": list(r.gold_chain)}
                    for r in recs if not r.ok]
    return res


def run_learning(args):
    seed, name, passes, noise, memory, fast_reflex, center = args
    w = World(seed)
    tools = w.tools()
    tasks = make_tasks(w)
    idx = {t["id"]: i for i, t in enumerate(tasks)}
    cfg = replace(cfg_safe(), memory=memory, fast_reflex=fast_reflex, center=center)
    eng = make_engine(w, tools, cfg)
    base = baseline_costs(tasks, tools, eng, tools)
    rng = random.Random(seed * 7 + 1)
    per_pass = []
    for p in range(passes):
        ids = list(range(len(tasks)))
        rng.shuffle(ids)
        order = [(i, (p + i) % 4) for i in ids]
        recs = run_sequence(eng, tasks, order, learn=True, noise=noise, rng=rng)
        lig = [ligand_cost(r, tasks[idx[r.task]], EMIT_DEF_TOK) for r in recs]
        sm = summarize(recs)
        sm["cost"] = float(np.mean([l.cost for l in lig]))
        sm["raw_in"] = float(np.mean([l.raw_in for l in lig]))
        sm["reflexes"] = len(eng.reflexes)
        sm["fast_fires"] = eng.fast_fires
        sm["fast_rate"] = sum(r.fast for r in recs) / len(recs)
        sm["success_test"] = summarize([r for r in recs if r.split == "test"])["success"]
        sm["success_dev"] = summarize([r for r in recs if r.split == "dev"])["success"]
        per_pass.append(sm)
    return {"name": name, "seed": seed, "per_pass": per_pass,
            "baseline_cost": float(np.mean([c.cost for c in base["tool_search"]])),
            "raw_cost": float(np.mean([c.cost for c in base["raw_mcp"]]))}


def run_heldout(args):
    """Train on instantiation k=0 with phrasings A/B only; test on k=1 with phrasings C/D (new params AND new wording)."""
    seed, train_passes, center = args
    w = World(seed)
    tools = w.tools()
    tasks = make_tasks(w)
    k0 = [i for i, t in enumerate(tasks) if t["k"] == 0]
    k1 = [i for i, t in enumerate(tasks) if t["k"] == 1]
    test_order = [(i, pi) for i in k1 for pi in (2, 3)]
    out = {"seed": seed}
    cold = make_engine(w, tools, cfg_safe())
    r0 = run_sequence(cold, tasks, test_order, learn=False)
    out["cold"] = summarize(r0)
    out["cold_by_split"] = {s: summarize([r for r in r0 if r.split == s]) for s in ("dev", "test")}
    warm = make_engine(w, tools, cfg_safe(center=center))
    rng = random.Random(seed + 99)
    for p in range(train_passes):
        ids = k0[:]
        rng.shuffle(ids)
        run_sequence(warm, tasks, [(i, p % 2) for i in ids], learn=True, rng=rng)
    r1 = run_sequence(warm, tasks, test_order, learn=False)
    out["warm"] = summarize(r1)
    out["warm_by_split"] = {s: summarize([r for r in r1 if r.split == s]) for s in ("dev", "test")}
    out["reflexes"] = len(warm.reflexes)
    # same-wording control: test on k=1 with A/B (new params only)
    r2 = run_sequence(warm, tasks, [(i, pi) for i in k1 for pi in (0, 1)], learn=False)
    out["warm_AB_newparams"] = summarize(r2)
    return out


def main(quick=False):
    t0 = time.time()
    seeds = SEEDS[:2] if quick else SEEDS
    passes = 6 if quick else 16
    os.makedirs("results", exist_ok=True)
    R = {}
    with Pool(2) as pool:
        cold_jobs = []
        for s in seeds:
            cold_jobs += [(s, "safe", "safe", 37, {}), (s, "fast", "fast", 37, {}),
                          (s, "semantic_only", "safe", 37, {"io_shape": False}),
                          (s, "no_ask", "safe", 37, {"ask": False}), (s, "no_hints", "safe", 37, {"hints": False})]
        R["cold"] = pool.map(run_cold, cold_jobs)
        print("cold done", round(time.time() - t0), "s", flush=True)
        scale_jobs = []
        for s in seeds:
            for n in ((37, 100) if quick else (37, 100, 217)):
                scale_jobs += [(s, "safe", "safe", n, {}), (s, "semantic_only", "safe", n, {"io_shape": False})]
        R["scaling"] = pool.map(run_cold, scale_jobs)
        print("scaling done", round(time.time() - t0), "s", flush=True)
        learn_jobs = []
        for s in seeds:
            learn_jobs += [(s, "clean", passes, 0.0, True, False, False), (s, "noise10", passes, 0.10, True, False, False),
                           (s, "noise30", passes, 0.30, True, False, False), (s, "no_memory", passes, 0.0, False, False, False),
                           (s, "fast_reflex", passes, 0.0, True, True, False), (s, "center", passes, 0.0, True, False, True),
                           (s, "center_noise30", passes, 0.30, True, False, True)]
        R["learning"] = pool.map(run_learning, learn_jobs)
        print("learning done", round(time.time() - t0), "s", flush=True)
        R["heldout"] = pool.map(run_heldout, [(s, 8, False) for s in seeds])
        R["heldout_center"] = pool.map(run_heldout, [(s, 8, True) for s in seeds])
        print("heldout done", round(time.time() - t0), "s", flush=True)
    R["meta"] = {"seeds": seeds, "passes": passes, "emit_def_tokens": EMIT_DEF_TOK, "seconds": time.time() - t0}
    json.dump(R, open("results/results.json", "w"))
    print("wrote results/results.json in", round(time.time() - t0), "s")


if __name__ == "__main__":
    main("--quick" in sys.argv)
