"""Cold-start probe on the DEV split only (used for threshold tuning). Usage: python -m bench.probe [seeds] [--v]"""
from __future__ import annotations

import sys
from dataclasses import replace

from ligand.engine import Cfg
from ligand.world import World

from .runner import make_engine, run_sequence, summarize
from .tasks import make_tasks


def probe(cfg: Cfg, seeds=range(3), verbose=False, split="dev"):
    allrecs = []
    for s in seeds:
        w = World(s)
        tools = w.tools()
        tasks = [t for t in make_tasks(w) if t["split"] == split]
        idx = {t["id"]: i for i, t in enumerate(tasks)}
        eng = make_engine(w, tools, cfg)
        order = [(i, pi) for i in range(len(tasks)) for pi in range(4)]
        recs = run_sequence(eng, tasks, order, learn=False)
        allrecs += recs
        if verbose and s == seeds[0]:
            for r in recs:
                if not r.ok:
                    t = tasks[idx[r.task]]
                    print(f"  FAIL {r.task} p{r.pi} status={r.status} asked={r.asked} got={r.chain} gold={r.gold_chain}\n     {t['phr'][r.pi]['goal']} | have={t['phr'][r.pi]['have']} want={t['phr'][r.pi]['want']}")
    return allrecs


if __name__ == "__main__":
    verbose = "--v" in sys.argv
    recs = probe(Cfg(), seeds=[0, 1, 2], verbose=verbose)
    print(summarize(recs))
    by = {}
    for r in recs:
        by.setdefault(r.pi, []).append(r)
    for pi, rs in sorted(by.items()):
        print("phrasing", "ABCD"[pi], {k: round(v, 3) for k, v in summarize(rs).items() if k in ("success", "ask_rate", "need_rate", "wrong_bind", "none_rate")})
