"""Aggregate results/results.json into tables (printed + markdown) and figures."""
from __future__ import annotations

import json
import sys
from collections import defaultdict

import numpy as np

CONDS = ["raw_mcp", "tool_search", "code_mode", "cli_unfamiliar", "cli_familiar"]
NAMES = {"raw_mcp": "Raw MCP (all tools in context)", "tool_search": "MCP + tool search", "code_mode": "MCP + code mode",
         "cli_unfamiliar": "CLI (unfamiliar, needs --help)", "cli_familiar": "CLI (familiar, no discovery)",
         "ligand": "Ligand", "ligand_with_fallback": "Ligand + fallback to tool search on failure"}


def ms(xs, nd=3):
    xs = np.asarray(xs, dtype=float)
    return f"{xs.mean():.{nd}f}±{xs.std():.{nd}f}" if len(xs) > 1 else f"{xs.mean():.{nd}f}"


def load(path="results/results.json"):
    return json.load(open(path))


def pick(rows, **kw):
    return [r for r in rows if all(r.get(k) == v for k, v in kw.items())]


def table_cold(R, name="safe", n_tools=37):
    rows = pick(R["cold"], name=name)
    out = []
    for key, label in (("overall", "all"), ("dev", "dev"), ("test", "test")):
        get = (lambda r, m: r["overall"][m]) if key == "overall" else (lambda r, m, k=key: r["by_split"][k][m])
        out.append((label, {m: ms([get(r, m) for r in rows]) for m in ("success", "ask_rate", "need_rate", "wrong_bind", "none_rate", "turns", "router_ms")}))
    return out


def costs(R, name="safe", split=None):
    rows = pick(R["cold"], name=name)
    keys = CONDS + ["ligand", "ligand_with_fallback"]
    res = {}
    for k in keys:
        vals = defaultdict(list)
        for r in rows:
            c = (r["costs"] if split is None else r["costs_by_split"][split])[k]
            for m, v in c.items():
                vals[m].append(v)
        res[k] = {m: float(np.mean(v)) for m, v in vals.items()}
    return res


def main():
    R = load()
    print("== COLD (safe) ==")
    for label, d in table_cold(R, "safe"):
        print(label, d)
    print("== COLD (fast) ==")
    for label, d in table_cold(R, "fast"):
        print(label, d)
    for nm in ("semantic_only", "no_ask", "no_hints"):
        print(f"== COLD ({nm}) ==")
        for label, d in table_cold(R, nm):
            print(label, d)
    print("== by phrasing (safe), test split ==")
    rows = pick(R["cold"], name="safe")
    for p in "ABCD":
        print(p, ms([r["by_split_phr"][f"test/{p}"]["success"] for r in rows]), "dev", ms([r["by_split_phr"][f"dev/{p}"]["success"] for r in rows]))
    print("== COSTS (safe, all) ==")
    for k, v in costs(R, "safe").items():
        print(f"{k:22s}", {m: round(x, 1) for m, x in v.items()})
    print("== COSTS (safe, test) ==")
    for k, v in costs(R, "safe", "test").items():
        print(f"{k:22s}", {m: round(x, 1) for m, x in v.items()})
    print("== SCALING ==")
    for n in sorted({r["n_tools"] for r in R["scaling"]}):
        for nm in ("safe", "semantic_only"):
            rows = [r for r in R["scaling"] if r["n_tools"] == n and r["name"] == nm]
            c = [r["costs"] for r in rows]
            print(n, nm, "succ", ms([r["overall"]["success"] for r in rows]), "ask", ms([r["overall"]["ask_rate"] for r in rows]),
                  "wrong", ms([r["overall"]["wrong_bind"] for r in rows]), "ms", ms([r["overall"]["router_ms"] for r in rows], 1),
                  "raw_in raw_mcp", round(np.mean([x["raw_mcp"]["raw_in"] for x in c])), "ligand", round(np.mean([x["ligand"]["raw_in"] for x in c])))
    print("== LEARNING (success per pass) ==")
    for nm in ("clean", "noise10", "noise30", "no_memory", "fast_reflex"):
        rows = pick(R["learning"], name=nm)
        P = len(rows[0]["per_pass"])
        for m in ("success", "ask_rate", "turns", "router_ms", "reflexes", "fast_rate", "cost"):
            print(nm, m, [round(float(np.mean([r["per_pass"][p][m] for r in rows])), 3) for p in range(P)])
    print("== HELDOUT ==")
    H = R["heldout"]
    for k in ("cold", "warm", "warm_AB_newparams"):
        print(k, {m: ms([h[k][m] for h in H]) for m in ("success", "ask_rate", "wrong_bind", "none_rate")})
    print("reflexes", ms([h["reflexes"] for h in H], 1))


if __name__ == "__main__":
    main()
