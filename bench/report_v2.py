"""Aggregate results/results_v2.json -> printed tables + results/metrics_v2.md"""
from __future__ import annotations

import json
from collections import defaultdict

import numpy as np

SPL = ("dev", "test", "test2")


def load(path="results/results_v2.json"):
    return json.load(open(path))


def sel(rows, **kw):
    return [r for r in rows if all(r.get(k) == v for k, v in kw.items())]


def m(xs):
    return float(np.mean(xs)) if len(xs) else float("nan")


def sd(xs):
    return float(np.std(xs)) if len(xs) else float("nan")


def pct(x):
    return f"{100 * x:.1f}%"


def headline(R):
    lines = ["| tools | engine | success dev | success test* | success **test2** | wrong-bind | ask rate | router ms (seq) | router ms (servers in parallel**) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for n in (37, 100, 217, 500):
        for name in ("v1", "v2"):
            rows = sel(R["cold"], name=name, n_tools=n)
            if not rows:
                continue
            lines.append(f"| {n} | {name} | {pct(m([r['by_split']['dev']['success'] for r in rows]))} | {pct(m([r['by_split']['test']['success'] for r in rows]))} | "
                         f"**{pct(m([r['by_split']['test2']['success'] for r in rows]))}** ± {100 * sd([r['by_split']['test2']['success'] for r in rows]):.1f} | "
                         f"{pct(m([r['overall']['wrong_bind'] for r in rows]))} | {pct(m([r['overall']['ask_rate'] for r in rows]))} | "
                         f"{m([r['router_ms_warm'] for r in rows]):.0f} | {m([r['par_ms_warm'] for r in rows]):.0f} |")
    return "\n".join(lines)


def ablation(R, n=217):
    lines = ["| engine (217 tools) | success dev | success test* | success test2 | wrong-bind | ask rate | router ms (seq) |", "|---|---|---|---|---|---|---|"]
    label = {"v1": "v1 (baseline)", "address": "+ type gate, index, goal-directed search", "bid": "+ per-server bidding only (no type gate)",
             "v2_nocontrast": "v2 without contrastive memory", "v2": "v2 (all)"}
    for name in ("v1", "address", "bid", "v2_nocontrast", "v2"):
        rows = sel(R["cold"], name=name, n_tools=n)
        if not rows:
            continue
        lines.append(f"| {label[name]} | {pct(m([r['by_split']['dev']['success'] for r in rows]))} | {pct(m([r['by_split']['test']['success'] for r in rows]))} | "
                     f"{pct(m([r['by_split']['test2']['success'] for r in rows]))} | {pct(m([r['overall']['wrong_bind'] for r in rows]))} | "
                     f"{pct(m([r['overall']['ask_rate'] for r in rows]))} | {m([r['router_ms_warm'] for r in rows]):.0f} |")
    return "\n".join(lines)


def learning(R):
    lines = ["| engine | feedback | ask rate (passes 3-16) | success (passes 3-16) | wrong-bind (passes 3-16) |", "|---|---|---|---|---|"]
    for name, noise in (("v1", 0.0), ("v2_nocontrast", 0.0), ("v2", 0.0), ("v1", 0.3), ("v2", 0.3)):
        rows = [r for r in R["learning"] if r["name"] == name and r["noise"] == noise]
        if not rows:
            continue
        g = lambda k: m([np.mean([p[k] for p in r["per_pass"][2:]]) for r in rows])
        lines.append(f"| {name} | {'clean' if noise == 0 else '30% wrong'} | {pct(g('ask_rate'))} | {pct(g('success'))} | {pct(g('wrong_bind'))} |")
    return "\n".join(lines)


def heldout(R):
    lines = ["| engine | cold success | trained success | cold wrong-bind | trained wrong-bind | cold ask | trained ask |", "|---|---|---|---|---|---|---|"]
    for name in ("v1", "v2_nocontrast", "v2"):
        rows = sel(R["heldout"], name=name)
        if not rows:
            continue
        g = lambda w, k: m([r[w][k] for r in rows])
        lines.append(f"| {name} | {pct(g('cold','success'))} | {pct(g('warm','success'))} | {pct(g('cold','wrong_bind'))} | {pct(g('warm','wrong_bind'))} | "
                     f"{pct(g('cold','ask_rate'))} | {pct(g('warm','ask_rate'))} |")
    return "\n".join(lines)


def tokens(R, n=37, split="test2"):
    rows = sel(R["cold"], name="v2", n_tools=n)
    out = {}
    for k in ("raw_mcp", "tool_search", "code_mode", "cli_unfamiliar", "cli_familiar", "ligand"):
        out[k] = (m([r["costs"][split][k]["raw_in"] for r in rows]), m([r["costs"][split][k]["cost"] for r in rows]))
    rows1 = sel(R["cold"], name="v1", n_tools=n)
    out["ligand_v1"] = (m([r["costs"][split]["ligand"]["raw_in"] for r in rows1]), m([r["costs"][split]["ligand"]["cost"] for r in rows1]))
    return out


def per_template(R, n=217):
    t = defaultdict(lambda: defaultdict(list))
    for name in ("v1", "v2"):
        for r in sel(R["cold"], name=name, n_tools=n):
            for tid, s in r["by_tid"].items():
                t[tid][name].append(s)
    return {tid: {k: m(v) for k, v in d.items()} for tid, d in sorted(t.items())}


def main():
    R = load()
    out = []
    out.append("### Cold start, v1 vs v2\n" + headline(R))
    out.append("### Ablation at 217 tools\n" + ablation(R))
    out.append("### Learning (16 passes, online)\n" + learning(R))
    out.append("### Held-out wording (train: new parameters absent, wording A/B; test: new parameters, wording C/D)\n" + heldout(R))
    toks = tokens(R)
    out.append("### Tokens per task, 37 tools, test2 split (cold)\n" + "\n".join(f"{k:14s} input {v[0]:7.0f}  cost {v[1]:7.0f}" for k, v in toks.items()))
    pt = per_template(R)
    out.append("### Per-template success at 217 tools (v1 -> v2)\n" + "\n".join(f"{t}: {pct(d.get('v1', float('nan')))} -> {pct(d.get('v2', float('nan')))}" for t, d in pt.items()))
    meta = R["meta"]
    out.append(f"(seeds {meta['seeds']}, passes {meta['passes']}, {meta['seconds']:.0f}s)")
    txt = "\n\n".join(out)
    print(txt)
    open("results/metrics_v2.md", "w").write(txt + "\n")


if __name__ == "__main__":
    main()
