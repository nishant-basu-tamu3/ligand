"""Run the unseen-web benchmark.  python -m webbench.run_web [--seeds 1] [--levels 0 1 2 3] [--quick]"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from multiprocessing import Pool

from playwright.sync_api import sync_playwright

from ligand.text import ntok
from .lweb import Env, LigandWeb, Memory, SimBrowser, WANT_CONCEPT
from .sitegen import SHAPE, Web, canon_disp, make_world

CONFIGS = ["ligand", "ligand_cold", "no_shape", "no_gate", "no_verify", "no_memory", "sim", "sim_nb", "sim_full"]
EMIT_TOKENS = 290          # the one-tool definition the model reads once per session
OUT = "results/web_runs.json"


def judge(task, rows):
    if not rows:
        return "none"
    got = Counter(tuple(canon_disp(SHAPE[k], c) for k, c in zip(task.want_keys, r)) for r in rows)
    gold = Counter(tuple(g[k] for k in task.want_keys) for g in task.gold)
    return "ok" if got == gold else "wrong"


def make_chooser(site, task):
    def chooser(want_name, opts):
        i = None
        for j, w in enumerate(task.want[0]):
            if w == want_name or task.want[1][j] == want_name:
                i = j
        if i is None:
            return None
        gold = site.lab(task.want_keys[i])
        return next((o for o in opts if o == gold), None)
    return chooser


def job(args):
    cfg, level, seed, quick = args
    sites = make_world(seed)
    if quick:
        sites = [s for s in sites if s.id[-1] in "01"]
    web = Web(sites, level, seed)
    mem = Memory()
    runs = []
    seen_test = False
    with sync_playwright() as p:
        br = p.chromium.launch()
        order = 0
        for site in sites:
            if site.split == "test" and not seen_test:
                seen_test = True
                if cfg == "ligand_cold":
                    mem = Memory()
            lig = None if cfg.startswith("sim") else LigandWeb(mem, shape=cfg != "no_shape", gate=cfg != "no_gate", verify=cfg != "no_verify",
                                                               use_mem=cfg not in ("no_memory",))
            for ti, task in enumerate(site.tasks):
                for phr in (0, 1):
                    ctx = br.new_context()
                    ctx.route("**/*", web.route)
                    page = ctx.new_page()
                    env = Env(page, web)
                    r0 = web.requests
                    t0 = time.time()
                    err = ""
                    try:
                        if lig is not None:
                            res = lig.run(env, f"http://{site.host}{task.start}", task.have, task.want[phr], task.want[phr], make_chooser(site, task), site.host)
                        else:
                            res = SimBrowser(backtrack=cfg != "sim_nb", full=cfg == "sim_full").run(env, f"http://{site.host}{task.start}", task.have, task.want[phr], task.want[phr], task.goal[phr])
                    except Exception as e:                      # a crashed attempt is a failed attempt
                        from .lweb import Result
                        res, err = Result(note="crash"), repr(e)[:120]
                    ms = (time.time() - t0) * 1000
                    out = judge(task, res.rows)
                    if lig is not None:
                        lig.feedback(res, [WANT_CONCEPT.get(w.lower(), w.lower()) for w in task.want[phr]], out == "ok")
                        if out == "ok" and lig.use_mem and res.sig:
                            mem.recipes[site.host] = res.sig
                    emit_tok = EMIT_TOKENS + ntok({"goal": task.goal[phr], "have": task.have, "want": task.want[phr]}) + ntok(res.rows or []) + res.ask * 60
                    runs.append(dict(cfg=cfg, level=level, seed=seed, tid=task.tid, site=site.id, arch=site.arch, split=site.split, ti=ti, phr=phr, order=order,
                                     out=out, asks=res.ask, loads=env.loads, steps=env.steps, ms=round(ms), ptok=env.ptok, emit_tok=emit_tok, retries=env.retries,
                                     err=err, layout=site.layout, label_style=site.label_style, link_style=site.link_style))
                    order += 1
                    ctx.close()
        br.close()
    return runs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--levels", type=int, nargs="*", default=[0, 1, 2, 3])
    ap.add_argument("--cfgs", nargs="*", default=CONFIGS)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    jobs = [(c, l, s, a.quick) for s in range(1, a.seeds + 1) for l in a.levels for c in a.cfgs]
    t0 = time.time()
    allruns = []
    with Pool(2) as pool:
        for i, runs in enumerate(pool.imap_unordered(job, jobs)):
            allruns += runs
            json.dump(allruns, open(a.out, "w"))
            print(f"[{i + 1}/{len(jobs)}] {runs[0]['cfg']} L{runs[0]['level']} s{runs[0]['seed']}: {sum(r['out'] == 'ok' for r in runs)}/{len(runs)} ok  ({time.time() - t0:.0f}s)", flush=True)
    json.dump(allruns, open(a.out, "w"))
    print("wrote", a.out, len(allruns))
