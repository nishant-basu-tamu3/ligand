"""Tables from results/web_runs.json -> results/metrics_web.md.  python -m webbench.report_web [runs.json]"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

import numpy as np

SRC = sys.argv[1] if len(sys.argv) > 1 else "results/web_runs.json"
R = json.load(open(SRC))
CFG = ["ligand", "ligand_cold", "no_shape", "no_gate", "no_verify", "no_memory", "sim", "sim_nb", "sim_full"]
NAME = {"ligand": "Ligand-Web (warm: saw dev sites)", "ligand_cold": "Ligand-Web (cold on held-out)", "no_shape": "- value-shape typing", "no_gate": "- input gate",
        "no_verify": "- verify/backtrack", "no_memory": "- memory", "sim": "Similarity browser (+backtrack)", "sim_nb": "Similarity browser (no backtrack)", "sim_full": "Similarity browser, lexicon incl. held-out words (ceiling)"}


def sel(**kw):
    return [r for r in R if all(r[k] == v for k, v in kw.items())]


def rate(rs, what="ok"):
    return sum(r["out"] == what for r in rs) / max(1, len(rs))


def seeds_sd(cfg, split, level, what="ok"):
    by = defaultdict(list)
    for r in sel(cfg=cfg, split=split, level=level):
        by[r["seed"]].append(r)
    v = [rate(x, what) for x in by.values()]
    return float(np.mean(v)) if v else float("nan"), float(np.std(v)) if len(v) > 1 else 0.0


def f(x):
    return f"{100 * x:.1f}%"


def main():
    L = sorted({r["level"] for r in R})
    out = []
    out.append("# Unseen-web results (generated)\n")
    n = len(sel(cfg="ligand", level=L[0]))
    out.append(f"{n} runs per config per noise level per seed ({len(sel(cfg='ligand', level=L[0], split='dev'))} dev / {len(sel(cfg='ligand', level=L[0], split='test'))} held-out). Seeds: {sorted({r['seed'] for r in R})}.\n")
    for split, title in (("test", "Held-out sites (archetypes, vocabulary and layouts never used in dev)"), ("dev", "Dev sites (the vocabulary the baseline's lexicon was built from)")):
        out.append(f"\n## Success, {title}\n")
        out.append("| config | " + " | ".join(f"noise L{l}" for l in L) + " | mean |\n|---|" + "---|" * (len(L) + 1))
        for c in CFG:
            vals = [seeds_sd(c, split, l)[0] for l in L]
            if any(np.isnan(vals)):
                continue
            out.append(f"| {NAME[c]} | " + " | ".join(f(v) for v in vals) + f" | {f(np.mean(vals))} |")
        out.append("")
    out.append("\n## Silent wrong answers, held-out\n")
    out.append("| config | " + " | ".join(f"L{l}" for l in L) + " |\n|---|" + "---|" * len(L))
    for c in CFG:
        vals = [seeds_sd(c, "test", l, "wrong")[0] for l in L]
        if any(np.isnan(vals)):
            continue
        out.append(f"| {NAME[c]} | " + " | ".join(f(v) for v in vals) + " |")
    out.append("\n## Cost per task, held-out (mean over noise levels)\n")
    out.append("| config | page loads | wall ms | asks/task | model-visible tokens* | raw-DOM tokens a DOM-reading LLM would see |\n|---|---|---|---|---|---|")
    for c in CFG:
        rs = [r for r in R if r["cfg"] == c and r["split"] == "test"]
        if not rs:
            continue
        mt = np.mean([r["emit_tok"] for r in rs]) if c.startswith("ligand") or c.startswith("no_") else float("nan")
        out.append(f"| {NAME[c]} | {np.mean([r['loads'] for r in rs]):.1f} | {np.mean([r['ms'] for r in rs]):.0f} | {np.mean([r['asks'] for r in rs]):.2f} | "
                   f"{'-' if np.isnan(mt) else f'{mt:.0f}'} | {np.mean([r['ptok'] for r in rs]):.0f} |")
    out.append("\n*Ligand variants: tool definition + call + returned rows (+60 per ask turn). The page text never enters the model.\n")
    out.append("\n## By archetype, held-out, Ligand-Web cold vs similarity browser (mean over levels)\n")
    out.append("| archetype | Ligand-Web (cold) | Ligand-Web (warm) | similarity+backtrack |\n|---|---|---|---|")
    for a in sorted({r["arch"] for r in R if r["split"] == "test"}):
        out.append(f"| {a} | " + " | ".join(f(rate([r for r in R if r["cfg"] == c and r["arch"] == a])) for c in ("ligand_cold", "ligand", "sim")) + " |")
    out.append("\n## By layout feature, held-out (all levels), Ligand-Web cold vs similarity+backtrack\n")
    out.append("| feature | value | Ligand-Web | similarity |\n|---|---|---|---|")
    for key in ("label_style", "layout", "link_style"):
        for v in sorted({r[key] for r in R if r["split"] == "test"}):
            out.append(f"| {key} | {v} | " + " | ".join(f(rate([r for r in R if r["cfg"] == c and r["split"] == "test" and r[key] == v])) for c in ("ligand_cold", "sim")) + " |")
    out.append("\n## Revisit and transfer (held-out sites, Ligand-Web cold vs no_memory)\n")
    out.append("Task index within a site (0 = first visit, 1-2 = revisits of the same site with a new question):\n")
    out.append("| config | task 0 success | task 1 success | task 2 success | loads t0 | loads t2 | asks t0 | asks t2 |\n|---|---|---|---|---|---|---|---|")
    for c in ("ligand_cold", "no_memory"):
        rs = [r for r in R if r["cfg"] == c and r["split"] == "test"]
        cells = [f(rate([r for r in rs if r["ti"] == t])) for t in (0, 1, 2)]
        lo = [np.mean([r["loads"] for r in rs if r["ti"] == t]) for t in (0, 2)]
        ak = [np.mean([r["asks"] for r in rs if r["ti"] == t]) for t in (0, 2)]
        out.append(f"| {NAME[c]} | " + " | ".join(cells) + f" | {lo[0]:.2f} | {lo[1]:.2f} | {ak[0]:.2f} | {ak[1]:.2f} |")
    out.append("\nAcross sites of the same archetype (site order within archetype, asks per task):\n")
    out.append("| config | 1st site | 2nd | 3rd | 4th |\n|---|---|---|---|---|")
    for c in ("ligand_cold", "no_memory"):
        row = []
        for k in range(4):
            rs = [r for r in R if r["cfg"] == c and r["split"] == "test" and r["site"].endswith(f"x{k}")]
            row.append(f"{np.mean([r['asks'] for r in rs]):.2f} asks, {f(rate(rs))}")
        out.append(f"| {NAME[c]} | " + " | ".join(row) + " |")
    crashes = sum(1 for r in R if r["err"])
    out.append(f"\nCrashed runs (counted as failures): {crashes} of {len(R)}.")
    open("results/metrics_web.md", "w").write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
