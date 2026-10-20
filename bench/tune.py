"""Grid-tune routing hyper-parameters on the DEV split ONLY (templates t01-t10). Test split is never touched here."""
from __future__ import annotations
import itertools, json
from dataclasses import replace
from ligand.engine import Cfg
from .probe import probe
from .runner import summarize

if __name__ == "__main__":
    base = Cfg()
    grid = {
        "sem_floor": [0.05, 0.1, 0.2],
        "len_pen": [0.8, 0.9],
        "margin": [0.06, 0.12, 0.2],
        "filter_pen": [0.7, 0.85],
        "th_link": [0.55, 0.65],
        "sem_max_w": [0.5, 0.8],
    }
    keys = list(grid)
    rows = []
    for vals in itertools.product(*[grid[k] for k in keys]):
        cfg = replace(base, **dict(zip(keys, vals)))
        recs = probe(cfg, seeds=[0, 1, 2], split="dev")
        sm = summarize(recs)
        obj = sm["success"] - 0.15 * sm["ask_rate"] - 0.5 * sm["wrong_bind"]
        rows.append((obj, dict(zip(keys, vals)), sm))
    rows.sort(key=lambda r: -r[0])
    for obj, cfgd, sm in rows[:8]:
        print(round(obj, 3), cfgd, {k: round(sm[k], 3) for k in ("success", "ask_rate", "wrong_bind", "none_rate")})
    print("default:", [round(o, 3) for o, c, s in rows if c == {k: getattr(base, k) for k in keys}])
    json.dump(rows[0][1], open("bench/tuned.json", "w"), indent=1)
