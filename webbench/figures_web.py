"""results/fig_web_noise.png, results/fig_web_cost.png from results/web_runs.json"""
from __future__ import annotations

import json
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

R = json.load(open("results/web_runs.json"))
C = {"ligand_cold": "#0072B2", "sim_full": "#E69F00", "sim": "#7a7a7a", "no_shape": "#D55E00", "no_verify": "#009E73"}
LAB = {"ligand_cold": "Ligand-Web (cold)", "sim_full": "similarity, knows held-out words", "sim": "similarity (dev words)", "no_shape": "Ligand - shape typing", "no_verify": "Ligand - verify"}
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold", "axes.titlesize": 11, "figure.dpi": 130, "savefig.bbox": "tight"})
L = sorted({r["level"] for r in R})


def rate(cfg, split, level, what="ok"):
    by = defaultdict(list)
    for r in R:
        if r["cfg"] == cfg and r["split"] == split and r["level"] == level:
            by[r["seed"]].append(r["out"] == what)
    v = [np.mean(x) for x in by.values()]
    return np.mean(v), (np.std(v) if len(v) > 1 else 0)


fig, axes = plt.subplots(1, 3, figsize=(14, 3.8))
for ax, (split, what, title) in zip(axes, (("test", "ok", "Held-out sites: success"), ("test", "wrong", "Held-out sites: silent wrong answers"), ("dev", "ok", "Dev sites: success"))):
    for c in C:
        mu = [rate(c, split, l, what)[0] for l in L]
        sd = [rate(c, split, l, what)[1] for l in L]
        ax.errorbar(L, mu, yerr=sd, marker="o", color=C[c], lw=2, capsize=3, label=LAB[c])
    ax.set_xticks(L)
    ax.set_xticklabels(["L0 clean", "L1 popups\n+decoys", "L2 + flaky\n+shuffle+ads", "L3 + JS render\n+pagination"][: len(L)], fontsize=8)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_title(title)
    if what == "ok":
        ax.set_ylim(0, 1.02)
axes[0].legend(frameon=False, fontsize=7.5, loc="lower left")
fig.savefig("results/fig_web_noise.png")
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.6))
cfgs = ["ligand_cold", "sim_full", "sim"]
for ax, (key, title) in zip(axes, (("loads", "Page loads per task (held-out)"), ("ptok", "Page tokens a DOM-reading agent would see"))):
    vals = [np.mean([r[key] for r in R if r["cfg"] == c and r["split"] == "test"]) for c in cfgs]
    ax.bar(range(len(cfgs)), vals, color=[C[c] for c in cfgs])
    ax.set_xticks(range(len(cfgs)))
    ax.set_xticklabels([LAB[c] for c in cfgs], rotation=15, ha="right", fontsize=8)
    ax.set_title(title)
mt = np.mean([r["emit_tok"] for r in R if r["cfg"] == "ligand_cold" and r["split"] == "test"])
axes[1].axhline(mt, color=C["ligand_cold"], ls="--", lw=1)
axes[1].text(2.4, mt * 1.15, f"Ligand-Web: {mt:.0f} tokens reach the model", ha="right", fontsize=8, color=C["ligand_cold"])
fig.savefig("results/fig_web_cost.png")
plt.close(fig)
print("web figures written")
