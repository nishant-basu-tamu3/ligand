"""v2 figures -> results/fig_v2_scale.png, results/fig_v2_learning.png"""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .report_v2 import load, m, sd, sel

C = {"v1": "#7a7a7a", "v2": "#0072B2", "red": "#D55E00", "green": "#009E73", "orange": "#E69F00"}
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold", "axes.titlesize": 11,
                     "figure.dpi": 130, "savefig.bbox": "tight"})
SIZES = (37, 100, 217, 500)


def fig_scale(R):
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.9))
    ax = axes[0]
    for name, lab in (("v1", "v1"), ("v2", "v2")):
        mu = [m([r["by_split"]["test2"]["success"] for r in sel(R["cold"], name=name, n_tools=n)]) for n in SIZES]
        s_ = [sd([r["by_split"]["test2"]["success"] for r in sel(R["cold"], name=name, n_tools=n)]) for n in SIZES]
        ax.errorbar(SIZES, mu, yerr=s_, marker="o", color=C[name], lw=2, capsize=3)
        ax.text(SIZES[-1] + 12, mu[-1], lab, color=C[name], va="center", fontsize=10)
    ax.set_ylim(0.6, 1.0)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("tools in the catalog")
    ax.set_title("Success on the fresh test2 split")
    ax.set_xlim(0, 590)
    ax = axes[1]
    for name in ("v1", "v2"):
        mu = [m([r["overall"]["wrong_bind"] for r in sel(R["cold"], name=name, n_tools=n)]) for n in SIZES]
        ax.plot(SIZES, mu, marker="o", color=C[name], lw=2)
        ax.text(SIZES[-1] + 12, mu[-1], name, color=C[name], va="center", fontsize=10)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("tools in the catalog")
    ax.set_title("Silent wrong answers (wrong binding)")
    ax.set_xlim(0, 590)
    ax.set_ylim(0, None)
    ax = axes[2]
    for name, key, ls, lab in (("v1", "router_ms_warm", "-", "v1"), ("v2", "router_ms_warm", "-", "v2, one machine"), ("v2", "par_ms_warm", "--", "v2, servers in parallel*")):
        mu = [m([r[key] for r in sel(R["cold"], name=name, n_tools=n)]) for n in SIZES]
        col = C[name]
        ax.plot(SIZES, mu, marker="o", color=col, lw=2, ls=ls)
        ax.text(SIZES[-1] + 12, mu[-1], lab, color=col, va="center", fontsize=8.5)
    ax.set_xlabel("tools in the catalog")
    ax.set_ylabel("router ms per emit (warm)")
    ax.set_title("Routing time")
    ax.set_xlim(0, 700)
    fig.text(0.99, -0.03, "*simulated: max over per-server search times; servers were not actually run concurrently", ha="right", fontsize=8, color="#555")
    fig.savefig("results/fig_v2_scale.png")
    plt.close(fig)


def fig_learning(R):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    series = [("v1", 0.0, "v1", C["v1"], "-"), ("v2_nocontrast", 0.0, "v2 without contrastive memory", C["orange"], "-"), ("v2", 0.0, "v2", C["v2"], "-"),
              ("v1", 0.3, "v1, 30% wrong feedback", C["v1"], "--"), ("v2", 0.3, "v2, 30% wrong feedback", C["v2"], "--")]
    for ax, (key, title) in zip(axes, (("ask_rate", "Clarification rate (extra turn)"), ("wrong_bind", "Wrong-binding rate"))):
        for name, noise, lab, col, ls in series:
            rows = [r for r in R["learning"] if r["name"] == name and r["noise"] == noise]
            if not rows:
                continue
            P = len(rows[0]["per_pass"])
            arr = np.array([[r["per_pass"][p][key] for p in range(P)] for r in rows])
            ax.plot(np.arange(1, P + 1), arr.mean(0), color=col, ls=ls, lw=2, label=lab)
        ax.set_title(title)
        ax.set_xlabel("pass over the 60-task suite")
        ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2))
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
        ax.set_ylim(0, None)
    axes[0].legend(frameon=False, fontsize=8)
    fig.savefig("results/fig_v2_learning.png")
    plt.close(fig)


if __name__ == "__main__":
    R = load()
    fig_scale(R)
    fig_learning(R)
    print("v2 figures written")
