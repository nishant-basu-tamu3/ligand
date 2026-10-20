"""Figures from results/results.json -> results/fig_*.png"""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .report import CONDS, NAMES, costs, pick

C = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73", "red": "#D55E00", "purple": "#CC79A7", "sky": "#56B4E9", "grey": "#7a7a7a", "black": "#222222"}
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold", "axes.titlesize": 11,
                     "figure.dpi": 130, "savefig.bbox": "tight"})


def fig_cost(R):
    cs = costs(R, "safe", "test")
    order = ["raw_mcp", "cli_unfamiliar", "tool_search", "code_mode", "ligand_with_fallback", "ligand", "cli_familiar"]
    lab = {"raw_mcp": "Raw MCP\n(all 37 tools in context)", "cli_unfamiliar": "CLI, unfamiliar\n(--help discovery)", "tool_search": "MCP + tool search",
           "code_mode": "MCP + code mode", "ligand": "Ligand", "ligand_with_fallback": "Ligand + fallback\n(on failure)", "cli_familiar": "CLI, familiar\n(oracle, no discovery)"}
    col = {"raw_mcp": C["grey"], "cli_unfamiliar": C["grey"], "tool_search": C["grey"], "code_mode": C["grey"], "ligand": C["blue"],
           "ligand_with_fallback": C["sky"], "cli_familiar": C["orange"]}
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.4))
    for ax, (key, title) in zip(axes, (("raw_in", "Billed input tokens per task"), ("cost", "Cost proxy per task (cached prefix, output 5x)"))):
        vals = [cs[k][key] for k in order]
        y = np.arange(len(order))[::-1]
        ax.barh(y, vals, color=[col[k] for k in order], height=0.62)
        for yi, v in zip(y, vals):
            ax.text(v + max(vals) * 0.012, yi, f"{v:,.0f}", va="center", fontsize=9)
        ax.set_yticks(y)
        ax.set_yticklabels([lab[k] for k in order], fontsize=8.5)
        ax.set_title(title)
        ax.set_xlim(0, max(vals) * 1.15)
    fig.subplots_adjust(wspace=0.5)
    fig.suptitle("Cold-start cost on the untouched TEST split (baselines are oracle agents; Ligand's routing is real)", fontsize=10, y=1.02)
    fig.savefig("results/fig_cost.png")
    plt.close(fig)


def fig_learning(R):
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    series = [("no_memory", "no memory", C["grey"], "-"), ("clean", "memory", C["blue"], "-"), ("noise30", "memory, 30% noisy feedback", C["red"], "--"),
              ("center", "memory + centering (post-hoc)", C["green"], "-")]
    for ax, (m, title, fmt) in zip(axes, (("ask_rate", "Clarification rate (extra turn)", "{:.0%}"), ("success", "Success rate (online, before learning from the emit)", "{:.0%}"),
                                           ("cost", "Cost proxy per task", "{:,.0f}"))):
        for name, label, color, ls in series:
            rows = pick(R["learning"], name=name)
            if not rows:
                continue
            P = len(rows[0]["per_pass"])
            arr = np.array([[r["per_pass"][p][m] for p in range(P)] for r in rows])
            mu, sd = arr.mean(0), arr.std(0)
            x = np.arange(1, P + 1)
            ax.plot(x, mu, color=color, ls=ls, lw=2, label=label)
            ax.fill_between(x, mu - sd, mu + sd, color=color, alpha=0.12, lw=0)
        ax.set_title(title)
        ax.set_xlabel("pass over the 40-task suite")
        ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2))
        if m != "cost":
            ax.set_ylim(0, 1.02)
            ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
        else:
            rows = pick(R["learning"], name="clean")
            ax.axhline(np.mean([r["baseline_cost"] for r in rows]), color=C["black"], lw=1, ls=":")
            ax.text(1, np.mean([r["baseline_cost"] for r in rows]) * 1.01, "MCP + tool search", fontsize=8)
    axes[0].legend(frameon=False, fontsize=8, loc="upper right")
    fig.savefig("results/fig_learning.png")
    plt.close(fig)


def fig_scaling(R):
    sizes = sorted({r["n_tools"] for r in R["scaling"]})
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    ax = axes[0]
    raw = [np.mean([r["costs"]["raw_mcp"]["raw_in"] for r in R["scaling"] if r["n_tools"] == n and r["name"] == "safe"]) for n in sizes]
    cli = [np.mean([r["costs"]["cli_unfamiliar"]["raw_in"] for r in R["scaling"] if r["n_tools"] == n and r["name"] == "safe"]) for n in sizes]
    ts = [np.mean([r["costs"]["tool_search"]["raw_in"] for r in R["scaling"] if r["n_tools"] == n and r["name"] == "safe"]) for n in sizes]
    lg = [np.mean([r["costs"]["ligand"]["raw_in"] for r in R["scaling"] if r["n_tools"] == n and r["name"] == "safe"]) for n in sizes]
    for v, lab, c in ((raw, "Raw MCP", C["grey"]), (cli, "CLI, unfamiliar", C["orange"]), (ts, "MCP + tool search", C["purple"]), (lg, "Ligand", C["blue"])):
        ax.plot(sizes, v, marker="o", color=c, lw=2)
        ax.text(sizes[-1] + 4, v[-1], lab, color=c, va="center", fontsize=9)
    ax.set_xlabel("tools in the catalog")
    ax.set_ylabel("billed input tokens per task")
    ax.set_title("Context cost vs catalog size")
    ax.set_xlim(0, sizes[-1] * 1.5)
    ax = axes[1]
    for nm, lab, c in (("safe", "Ligand (shape + meaning)", C["blue"]), ("semantic_only", "plain embedding tool-search", C["red"])):
        mu = [np.mean([r["overall"]["success"] for r in R["scaling"] if r["n_tools"] == n and r["name"] == nm]) for n in sizes]
        sd = [np.std([r["overall"]["success"] for r in R["scaling"] if r["n_tools"] == n and r["name"] == nm]) for n in sizes]
        ax.errorbar(sizes, mu, yerr=sd, marker="o", color=c, lw=2, capsize=3)
        ax.text(sizes[-1] + 4, mu[-1], lab, color=c, va="center", fontsize=9)
    ax.set_ylim(0, 1.02)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_xlabel("tools in the catalog (extra tools are plausible distractors)")
    ax.set_title("Cold-start routing success vs catalog size")
    ax.set_xlim(0, sizes[-1] * 1.7)
    fig.savefig("results/fig_scaling.png")
    plt.close(fig)


if __name__ == "__main__":
    R = json.load(open("results/results.json"))
    fig_cost(R)
    fig_learning(R)
    fig_scaling(R)
    print("figures written")
