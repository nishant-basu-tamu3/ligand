"""v2 experiments: v1 vs address / bid / full v2, at 37-500 tools, on dev / test / test2 splits.
Usage: python -m bench.run_v2 [--quick]  ->  results/results_v2.json

Split provenance: dev (t01-t10) used to tune v1 thresholds; test (t11-t20) was seen when diagnosing v1 failures at scale,
so it is NOT clean for v2; test2 (t21-t30) was written before v2 existed and never used for tuning or diagnosis."""
from __future__ import annotations

import json
import os
import random
import sys
import time
from dataclasses import replace
from multiprocessing import Pool

import numpy as np

from ligand.distractors import make_distractors
from ligand.engine import cfg_safe, cfg_v2
from ligand.world import World

from .baselines import EMIT_DEF_TOK, baseline_costs, ligand_cost
from .run_bench import CONDS, _cost_summary
from .runner import make_engine, run_sequence, summarize
from .tasks import make_tasks

SPLITS = ("dev", "test", "test2")
CFGS = {
    "v1": lambda: cfg_safe(),
    "address": lambda: cfg_safe(address=True, index=True, prune=True),                 # type gate + index + goal-directed search, one global search
    "bid": lambda: cfg_safe(bid=True, abstain=True),                                   # per-server bidding only (v1 scoring, no type gate/index)
    "v2": lambda: cfg_v2(),                                                            # address + bid + abstain + contrastive memory
    "v2_nocontrast": lambda: cfg_v2(contrastive=False),
}


def catalog(world, n_total):
    tools = world.tools()
    extra = make_distractors(n_total - len(tools)) if n_total > len(tools) else []
    return tools, tools + extra


def run_cold2(args):
    seed, name, n_total = args
    w = World(seed)
    tools, cat = catalog(w, n_total)
    tasks = make_tasks(w)
    idx = {t["id"]: i for i, t in enumerate(tasks)}
    eng = make_engine(w, cat, CFGS[name]())
    rng = random.Random(seed)
    order = [(i, pi) for i in range(len(tasks)) for pi in range(4)]
    rng.shuffle(order)
    recs = run_sequence(eng, tasks, order, learn=False)
    half = len(recs) // 2
    base = baseline_costs(tasks, tools, eng, cat)
    lig = [ligand_cost(r, tasks[idx[r.task]], EMIT_DEF_TOK) for r in recs]
    res = {"name": name, "seed": seed, "n_tools": len(cat), "overall": summarize(recs),
           "by_split": {s: summarize([r for r in recs if r.split == s]) for s in SPLITS},
           "by_split_phr": {f"{s}/{'ABCD'[p]}": summarize([r for r in recs if r.split == s and r.pi == p])["success"] for s in SPLITS for p in range(4)},
           "by_tid": {t: summarize([r for r in recs if r.tid == t])["success"] for t in sorted({r.tid for r in recs})},
           "router_ms_warm": float(np.mean([r.router_ms for r in recs[half:]])), "par_ms_warm": float(np.mean([r.par_ms for r in recs[half:]])),
           "index_ms": eng.index_ms,
           "costs": {sp: _cost_summary(base, lig, recs, tasks, idx, sp) for sp in SPLITS},
           "costs_all": _cost_summary(base, lig, recs, tasks, idx, None),
           "fails": [{"task": r.task, "pi": r.pi, "status": r.status, "got": list(r.chain), "gold": list(r.gold_chain)} for r in recs if not r.ok]}
    return res


def run_learning2(args):
    seed, name, passes, noise = args
    w = World(seed)
    tools = w.tools()
    tasks = make_tasks(w)
    eng = make_engine(w, tools, CFGS[name]())
    rng = random.Random(seed * 7 + 1)
    per_pass = []
    for p in range(passes):
        ids = list(range(len(tasks)))
        rng.shuffle(ids)
        recs = run_sequence(eng, tasks, [(i, (p + i) % 4) for i in ids], learn=True, noise=noise, rng=rng)
        sm = summarize(recs)
        sm["success_test2"] = summarize([r for r in recs if r.split == "test2"])["success"]
        per_pass.append(sm)
    return {"name": name, "noise": noise, "seed": seed, "per_pass": per_pass}


def run_heldout2(args):
    """Train on instantiation k=0, wording A/B; test on instantiation k=1, wording C/D (new parameters AND new wording)."""
    seed, name, train_passes = args
    w = World(seed)
    tools = w.tools()
    tasks = make_tasks(w)
    k0 = [i for i, t in enumerate(tasks) if t["k"] == 0]
    k1 = [i for i, t in enumerate(tasks) if t["k"] == 1]
    test_order = [(i, pi) for i in k1 for pi in (2, 3)]
    out = {"seed": seed, "name": name}
    cold = make_engine(w, tools, CFGS[name]())
    r0 = run_sequence(cold, tasks, test_order, learn=False)
    out["cold"] = summarize(r0)
    warm = make_engine(w, tools, CFGS[name]())
    rng = random.Random(seed + 99)
    for p in range(train_passes):
        ids = k0[:]
        rng.shuffle(ids)
        run_sequence(warm, tasks, [(i, p % 2) for i in ids], learn=True, rng=rng)
    r1 = run_sequence(warm, tasks, test_order, learn=False)
    out["warm"] = summarize(r1)
    out["warm_by_split"] = {s: summarize([r for r in r1 if r.split == s]) for s in SPLITS}
    out["cold_by_split"] = {s: summarize([r for r in r0 if r.split == s]) for s in SPLITS}
    return out


def main(quick=False):
    t0 = time.time()
    seeds = [0, 1] if quick else [0, 1, 2, 3, 4]
    passes = 6 if quick else 16
    os.makedirs("results", exist_ok=True)
    R = {}
    with Pool(2) as pool:
        jobs = []
        for s in seeds:
            for n in (37, 100, 217, 500):
                jobs += [(s, "v1", n), (s, "v2", n)]
            jobs += [(s, "address", 217), (s, "bid", 217), (s, "v2_nocontrast", 217)]
        # biggest jobs first for load balance
        jobs.sort(key=lambda j: -(j[2] * (3 if j[1] != "v1" else 1)))
        R["cold"] = pool.map(run_cold2, jobs, chunksize=1)
        print("cold done", round(time.time() - t0), "s", flush=True)
        lj = []
        for s in seeds:
            lj += [(s, "v1", passes, 0.0), (s, "v2", passes, 0.0), (s, "v2_nocontrast", passes, 0.0),
                   (s, "v1", passes, 0.3), (s, "v2", passes, 0.3)]
        R["learning"] = pool.map(run_learning2, lj, chunksize=1)
        print("learning done", round(time.time() - t0), "s", flush=True)
        R["heldout"] = pool.map(run_heldout2, [(s, n, 8) for s in seeds for n in ("v1", "v2", "v2_nocontrast")], chunksize=1)
        print("heldout done", round(time.time() - t0), "s", flush=True)
    R["meta"] = {"seeds": seeds, "passes": passes, "seconds": time.time() - t0}
    json.dump(R, open("results/results_v2.json", "w"))
    print("wrote results/results_v2.json in", round(time.time() - t0), "s")


if __name__ == "__main__":
    main("--quick" in sys.argv)
