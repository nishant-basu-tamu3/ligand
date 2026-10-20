"""Ligand engine: intent -> binding -> execution -> shaped result, with outcome memory.

The agent emits   goal (free text) + have (known values) + want (fields it needs).
The engine scores 'affinity' between that intent and every receptor (a wrapped tool):
  * shape complementarity: can the tool(s) accept what the agent HAS and produce what it WANTS?
    (chains of up to 3 tools are discovered by wiring output fields into input params)
  * semantic match between goal text and tool description
  * learned success on similar goals (outcome memory) and compiled 'reflexes'
Everything between emit and result happens outside the model's context.
"""
from __future__ import annotations

import json
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .text import Embedder, cos, ntok, words
from .world import Tool


_HEAD_SPLIT = re.compile(r"\b(?:of|for|in|that|which|is|like|from)\b")


def head(desc: str) -> str:
    """Head phrase of a description = its 'type': 'github login of the pull request author' -> 'github login'."""
    h = _HEAD_SPLIT.split(desc, maxsplit=1)[0].strip()
    return h or desc


def toks(name: str) -> frozenset:
    return frozenset(words(name.replace("_", " ")))


@dataclass
class Cfg:
    # similarity thresholds (tuned on dev templates only, then frozen)
    th_in: float = 0.55       # have-key -> tool param
    th_link: float = 0.55     # earlier output field -> tool param
    th_out: float = 0.70      # want field -> output field
    th_filter: float = 0.70   # have-key -> output field (post-filter)
    pool_all: int = 60        # catalogs up to this size are searched exhaustively
    pool_k: int = 16
    max_depth: int = 3
    # scoring
    sem_floor: float = 0.20
    len_pen: float = 0.90
    unused_pen: float = 0.35
    filter_pen: float = 0.70
    sem_max_w: float = 0.8
    margin: float = 0.20      # relative margin below which Ligand asks the agent to pick
    max_cands: int = 3
    # memory
    memory: bool = True
    kernel_floor: float = 0.30
    boost_lo: float = 0.70
    boost_span: float = 0.70
    reflex: bool = True
    center: bool = False      # post-hoc mitigation: mean-center goal vectors in memory similarity (see RESULTS)
    reflex_n: int = 3
    fast_reflex: bool = False
    tau_fast: float = 0.80
    # ablations
    io_shape: bool = True     # False -> semantic top-1 tool + bind params (what plain tool-search does)
    ask: bool = True
    hints: bool = True
    allow_write: bool = False
    fanout_cap: int = 12
    row_cap: int = 25


def cfg_safe(**kw) -> Cfg:
    """Operating point selected on DEV: asks the agent when the top two bindings are close."""
    return Cfg(**kw)


def cfg_fast(**kw) -> Cfg:
    """Second DEV-selected operating point: fewer clarifications, more risk of a wrong binding."""
    return Cfg(**{**dict(margin=0.06, sem_floor=0.10, sem_max_w=0.5, th_link=0.65), **kw})


@dataclass
class Receptor:
    tool: Tool
    doc_vec: np.ndarray
    @property
    def fq(self): return self.tool.fq
    @property
    def kind(self): return self.tool.kind


@dataclass
class Step:
    r: Receptor
    args: dict            # param -> ("have", key) | ("link", step_idx, field)
    sims: list            # sims of the bindings
    used_have: set


@dataclass
class Chain:
    steps: list
    key: tuple
    want_map: dict        # want name -> (step_idx, field, sim)
    filters: dict         # step_idx -> list[(field, key)]
    unused: int
    missing: list = field(default_factory=list)
    score: float = 0.0
    sem: float = 0.0
    io: float = 0.0


@dataclass
class Emission:
    status: str                      # ok | ask | none
    ticket: str
    rows: list = field(default_factory=list)
    chain_key: tuple = ()
    cands: list = field(default_factory=list)
    n_calls: int = 0
    router_ms: float = 0.0
    response: str = ""
    fast: bool = False
    missing: list = field(default_factory=list)
    fields: list = field(default_factory=list)


class Engine:
    def __init__(self, tools: list[Tool], backend: Callable[[str, dict], object], cfg: Cfg | None = None, embedder: Embedder | None = None):
        self.cfg = cfg or Cfg()
        self.backend = backend
        docs = [self._doc(t) for t in tools]
        self.emb = embedder or Embedder(docs)
        self.recs: list[Receptor] = [Receptor(t, self.emb.embed(d)) for t, d in zip(tools, docs)]
        self.by_fq = {r.fq: r for r in self.recs}
        self._c_have: dict = {}
        self._c_link: dict = {}
        self._c_out: dict = {}
        self._pv: dict = {}   # (fq, name) -> (name_vec, full_vec)
        # memory
        self.episodes: dict[tuple, list] = defaultdict(list)   # chain_key -> [(goal_vec, ok)]
        self.stats: dict[tuple, dict] = {}
        self.reflexes: dict[tuple, np.ndarray] = {}
        self.pending: dict[str, dict] = {}
        self.log: list = []
        self.gsum = None
        self.gn = 0
        self.reflex_mean: dict = {}
        self._tick = 0
        self.fast_fires = 0

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _doc(t: Tool) -> str:
        return f"{t.name.replace('_', ' ')} {t.desc} {t.server} " + " ".join(o.name.replace("_", " ") for o in t.outs)

    def _vecs(self, fq: str, name: str, desc: str):
        k = (fq, name)
        v = self._pv.get(k)
        if v is None:
            v = (self.emb.embed(name.replace("_", " ")), self.emb.embed(f"{name.replace('_', ' ')} {desc}"))
            self._pv[k] = v
        return v

    def _sim(self, a_name: str, b_fq: str, b_name: str, b_desc: str, guard_doc: frozenset | None = None) -> float:
        """Similarity of an agent-chosen name (a) to a tool-defined field/param name (b).
        Token-set aware: identical sets = 1.0; a more specific than b ('pr_title' vs 'title') = 0.85;
        b more specific than a ('email' vs 'owner_email') = 0.62; otherwise lexical cosine."""
        nv, fv = self._vecs(b_fq, b_name, b_desc)
        av = self.emb.embed(a_name.replace("_", " "))
        lex = max(cos(av, nv), 0.85 * cos(av, fv))
        sa, sb = toks(a_name), toks(b_name)
        if sa and sa == sb:
            return 1.0
        if sa and sb:
            if sa > sb:
                if guard_doc is None or (sa - sb) <= guard_doc:
                    return max(lex, 0.85)
            elif sb > sa:
                return max(lex, 0.62)
        return lex

    def sim_have_param(self, key, r: Receptor, p):
        k = (key, r.fq, p.name)
        v = self._c_have.get(k)
        if v is None:
            v = self._sim(key, r.fq, p.name, p.desc)
            self._c_have[k] = v
        return v

    def sim_have_out(self, key, r: Receptor, o):
        """have-key -> output field, used for post-filters. Extra tokens in the key must be explained by the tool's own vocabulary."""
        k = ("F", key, r.fq, o.name)
        v = self._c_have.get(k)
        if v is None:
            v = self._sim(key, r.fq, o.name, o.desc, guard_doc=frozenset(words(r.tool.name.replace("_", " ") + " " + r.tool.desc + " " + r.tool.server)))
            self._c_have[k] = v
        return v

    def sim_link(self, ra: Receptor, o, rb: Receptor, p):
        """Can output field o of tool ra feed param p of tool rb? True when they share a *type*:
        identical names, or the head phrases of their descriptions ('github login') are close."""
        k = (ra.fq, o.name, rb.fq, p.name)
        v = self._c_link.get(k)
        if v is None:
            ov = self._vecs(ra.fq, o.name, o.desc)
            pv = self._vecs(rb.fq, p.name, p.desc)
            hv = cos(self.emb.embed(head(o.desc)), self.emb.embed(head(p.desc)))
            same = 0.95 if toks(o.name) == toks(p.name) else 0.0
            v = max(same, hv, 0.8 * cos(ov[0], pv[0]))
            self._c_link[k] = v
        return v

    def sim_want_out(self, w, r: Receptor, o):
        k = (w, r.fq, o.name)
        v = self._c_out.get(k)
        if v is None:
            v = self._sim(w, r.fq, o.name, o.desc)
            self._c_out[k] = v
        return v

    def _observe(self, gv):
        self.gsum = gv.copy() if self.gsum is None else self.gsum + gv
        self.gn += 1

    def _csim(self, a, b) -> float:
        """Similarity used by memory. With cfg.center, subtract the mean of all goals seen so far so that words shared by every
        goal (templates like 'email address of') cancel and the discriminative words dominate."""
        if not self.cfg.center or self.gn < 5:
            return cos(a, b)
        m = self.gsum / self.gn
        x, y = a - m, b - m
        nx, ny = float(np.linalg.norm(x)), float(np.linalg.norm(y))
        return float(x @ y / (nx * ny)) if nx > 1e-6 and ny > 1e-6 else 0.0

    # ---------------------------------------------------------------- binding
    def _bind(self, r: Receptor, have_keys: list, avail: list) -> Step | None:
        """Bind a receptor's params from have-keys (preferred) or earlier outputs. avail: [(step_idx, Receptor, Out)]."""
        cfg = self.cfg
        cand = []
        for p in r.tool.params:
            for k in have_keys:
                s = self.sim_have_param(k, r, p)
                if s >= cfg.th_in:
                    cand.append((s + 0.05, p.name, "have", k, s))
            for si, ra, o in avail:
                s = self.sim_link(ra, o, r, p)
                if s >= cfg.th_link:
                    cand.append((s, p.name, "link", (si, o.name), s))
        cand.sort(key=lambda c: -c[0])
        used_p, used_k, args, sims, used_have = set(), set(), {}, [], set()
        for _, pn, typ, src, s in cand:
            if pn in used_p:
                continue
            if typ == "have":
                if src in used_k:
                    continue
                used_k.add(src)
                args[pn] = ("have", src)
                used_have.add(src)
            else:
                args[pn] = ("link", src[0], src[1])
            used_p.add(pn)
            sims.append(s)
        for p in r.tool.params:
            if p.required and p.name not in args:
                return None
        return Step(r, args, sims, used_have)

    def _finish(self, steps: list, have_keys: list, want: list, goal_vec) -> Chain | None:
        cfg = self.cfg
        if len(steps) > 1:
            for i in range(1, len(steps)):
                if not any(a[0] == "link" for a in steps[i].args.values()):
                    return None
        used_have = set().union(*[s.used_have for s in steps])
        filters: dict = defaultdict(list)
        unused = 0
        for k in have_keys:
            if k in used_have:
                continue
            best = None
            for si, st in enumerate(steps):
                for o in st.r.tool.outs:
                    s = self.sim_have_out(k, st.r, o)
                    if s >= cfg.th_filter and (best is None or s > best[0]):
                        best = (s, si, o.name)
            if best:
                filters[best[1]].append((best[2], k))
            else:
                unused += 1
        want_map, missing = {}, []
        for w in want:
            best = None
            for si, st in enumerate(steps):
                for o in st.r.tool.outs:
                    s = self.sim_want_out(w, st.r, o)
                    if s >= cfg.th_out and (best is None or (round(s, 2), -si) > (round(best[0], 2), -best[1])):
                        best = (s, si, o.name)
            if best is None:
                missing.append(w)
                continue
            want_map[w] = (best[1], best[2], best[0])
        if want and not want_map:
            return None
        used_steps = {m[0] for m in want_map.values()} | set(filters)
        for st in steps:
            for a in st.args.values():
                if a[0] == "link":
                    used_steps.add(a[1])
        if len(used_steps) < len(steps):
            return None
        sims_in = [s for st in steps for s in st.sims] or [1.0]
        io = 0.5 * (float(np.mean(sims_in)) + float(np.mean([m[2] for m in want_map.values()] or [1.0])))
        key = tuple(st.r.fq for st in steps)
        ch = Chain(steps, key, want_map, dict(filters), unused, missing=missing)
        ch.io = io
        return ch

    def _score(self, ch: Chain, goal_vec) -> float:
        cfg = self.cfg
        sems = [cos(goal_vec, st.r.doc_vec) for st in ch.steps]
        sem = cfg.sem_max_w * max(sems) + (1 - cfg.sem_max_w) * float(np.mean(sems))
        if cfg.memory and cfg.reflex and ch.key in self.reflexes:
            ref = self.reflex_mean[ch.key] if cfg.center else self.reflexes[ch.key]
            sem = max(sem, self._csim(goal_vec, ref))
        ch.sem = sem
        a = (cfg.sem_floor + sem) * (0.5 + 0.5 * ch.io) * (cfg.len_pen ** (len(ch.steps) - 1))
        if ch.unused:
            a *= cfg.unused_pen ** ch.unused
        nf = sum(len(v) for v in ch.filters.values())
        if nf:
            a *= cfg.filter_pen ** nf
        if cfg.memory:
            a *= self._boost(ch.key, goal_vec)
        ch.score = a
        return a

    def _boost(self, key, goal_vec) -> float:
        eps = self.episodes.get(key)
        if not eps:
            return 1.0
        num, den = 0.0, 0.0
        for g, ok in eps:
            w = max(0.0, self._csim(goal_vec, g) - self.cfg.kernel_floor)
            num += w * (1.0 if ok else 0.0)
            den += w
        S = (num + 0.5 * 0.3) / (den + 0.3)
        return self.cfg.boost_lo + self.cfg.boost_span * S

    # ---------------------------------------------------------------- search
    def _pool(self, goal_vec, want) -> list[Receptor]:
        cfg = self.cfg
        recs = [r for r in self.recs if cfg.allow_write or not r.tool.writes]
        if len(recs) <= cfg.pool_all:
            return recs
        sc = sorted(recs, key=lambda r: -cos(goal_vec, r.doc_vec))
        pool = {r.fq: r for r in sc[: cfg.pool_k]}
        ws = []
        for r in recs:
            best = max((self.sim_want_out(w, r, o) for w in want for o in r.tool.outs), default=0)
            ws.append((best, r))
        ws.sort(key=lambda x: -x[0])
        for _, r in ws[: cfg.pool_k // 2]:
            pool[r.fq] = r
        for key in self.reflexes:
            if cos(goal_vec, self.reflexes[key]) > 0.4:
                for fq in key:
                    if fq in self.by_fq:
                        pool[fq] = self.by_fq[fq]
        return list(pool.values())

    def search(self, goal_vec, have_keys, want) -> tuple[list[Chain], list[Chain]]:
        """Returns (complete chains, partial chains). Partial = valid wiring but some wanted fields have no match."""
        cfg = self.cfg
        pool = self._pool(goal_vec, want)
        found: dict[tuple, Chain] = {}
        part: dict[tuple, Chain] = {}

        def rec(steps, avail):
            if steps:
                ch = self._finish(steps, have_keys, want, goal_vec)
                if ch is not None:
                    self._score(ch, goal_vec)
                    store = part if ch.missing else found
                    if ch.key not in store or ch.score > store[ch.key].score:
                        store[ch.key] = ch
            if len(steps) >= cfg.max_depth:
                return
            for r in pool:
                if any(s.r is r for s in steps):
                    continue
                st = self._bind(r, have_keys, avail)
                if st is None:
                    continue
                if steps and not any(a[0] == "link" for a in st.args.values()):
                    continue
                if not steps and any(a[0] == "link" for a in st.args.values()):
                    continue
                si = len(steps)
                rec(steps + [st], avail + [(si, r, o) for o in r.tool.outs])

        rec([], [])
        key = lambda c: (-c.score, c.key)
        return sorted(found.values(), key=key), sorted(part.values(), key=key)

    def semantic_top1(self, goal_vec, have_keys, want) -> Chain | None:
        """Ablation: what plain embedding tool-search does. Best-matching tool by description, bind params, no chaining."""
        pool = self._pool(goal_vec, want)
        for r in sorted(pool, key=lambda r: -cos(goal_vec, r.doc_vec)):
            st = self._bind(r, have_keys, [])
            if st is None:
                continue
            want_map = {}
            for w in want:
                best = max(((self.sim_want_out(w, r, o), o.name) for o in r.tool.outs), default=(0, None))
                want_map[w] = (0, best[1], best[0])
            return Chain([st], (r.fq,), want_map, {}, 0, score=1.0)
        return None

    # ---------------------------------------------------------------- execution
    def run_chain(self, ch: Chain, have: dict, want: list):
        cfg = self.cfg
        rows = [[]]
        calls = 0
        for si, st in enumerate(ch.steps):
            new = []
            for row in rows:
                args = {}
                for pn, src in st.args.items():
                    raw = have[src[1]] if src[0] == "have" else row[src[1]].get(src[2])
                    ptype = next((p.type for p in st.r.tool.params if p.name == pn), "string")
                    if ptype == "integer":
                        try:
                            raw = int(raw)
                        except (TypeError, ValueError):
                            pass
                    args[pn] = raw
                res = self.backend(st.r.fq, args)
                calls += 1
                items = res if st.r.kind == "list" else ([res] if res else [])
                for fld, key in ch.filters.get(si, []):
                    val = str(have[key]).lower()
                    items = [it for it in items if (val in [str(x).lower() for x in it.get(fld)] if isinstance(it.get(fld), list)
                                                    else str(it.get(fld)).lower() == val)]
                for it in items:
                    new.append(row + [it])
                if calls >= 40:
                    break
            rows = new[: cfg.fanout_cap]
            if not rows:
                break
        out, seen = [], set()
        for row in rows:
            rec = {w: row[m[0]].get(m[1]) for w, m in ch.want_map.items() if m[0] < len(row)}
            k = json.dumps(rec, sort_keys=True, default=str)
            if k not in seen:
                seen.add(k)
                out.append(rec)
        return out[: cfg.row_cap], calls

    # ---------------------------------------------------------------- public API
    def emit(self, goal: str, have: dict, want: list, prev: tuple | None = None) -> Emission:
        t0 = time.perf_counter()
        cfg = self.cfg
        if prev is not None:
            self.feedback(*prev)
        self._tick += 1
        ticket = f"t{self._tick}"
        gv = self.emb.embed(goal)
        self._observe(gv)
        have_keys = list(have.keys())

        fast = False
        if not cfg.io_shape:
            ch = self.semantic_top1(gv, have_keys, want)
            chains = [ch] if ch else []
        else:
            chains = []
            if cfg.memory and cfg.reflex and cfg.fast_reflex and self.reflexes:
                best = max(((cos(gv, c), k) for k, c in self.reflexes.items()), default=None)
                if best and best[0] >= cfg.tau_fast:
                    ch = self._fixed(best[1], have_keys, want, gv)
                    if ch is not None:
                        chains, fast = [ch], True
                        self.fast_fires += 1
            if not chains:
                chains, partial = self.search(gv, have_keys, want)
                if not chains and partial and cfg.hints:
                    best = partial[0]
                    fields: list = []
                    for st in reversed(best.steps):
                        for o in st.r.tool.outs:
                            if o.name not in fields:
                                fields.append(o.name)
                    fields = fields[:18]
                    resp = json.dumps({"t": ticket, "need": best.missing, "fields": fields}, separators=(",", ":"))
                    return Emission("need", ticket, router_ms=(time.perf_counter() - t0) * 1e3, response=resp,
                                    missing=best.missing, fields=fields)
        ms = lambda: (time.perf_counter() - t0) * 1e3
        if not chains:
            return Emission("none", ticket, router_ms=ms(), response=json.dumps({"t": ticket, "rows": [], "err": "no receptor binds"}))
        top = chains[0]
        ambiguous = (cfg.io_shape and cfg.ask and not fast and len(chains) > 1
                     and (top.score - chains[1].score) / top.score < cfg.margin)
        if ambiguous:
            cands = [c for c in chains[: cfg.max_cands] if c.score >= 0.8 * top.score]
            self.pending[ticket] = {"chains": cands, "gv": gv, "have": have, "want": want, "goal": goal}
            desc = [{"k": i, "via": ">".join(c.key)} for i, c in enumerate(cands)]
            resp = json.dumps({"t": ticket, "ask": desc}, separators=(",", ":"))
            return Emission("ask", ticket, cands=[c.key for c in cands], router_ms=ms(), response=resp)
        return self._exec(ticket, top, have, want, gv, t0, fast=fast, goal=goal)

    def _fixed(self, key, have_keys, want, gv) -> Chain | None:
        steps, avail = [], []
        for fq in key:
            r = self.by_fq.get(fq)
            if r is None:
                return None
            st = self._bind(r, have_keys, avail)
            if st is None:
                return None
            avail = avail + [(len(steps), r, o) for o in r.tool.outs]
            steps.append(st)
        ch = self._finish(steps, have_keys, want, gv)
        if ch is not None:
            self._score(ch, gv)
        return ch

    def pick(self, ticket: str, k: int) -> Emission:
        t0 = time.perf_counter()
        p = self.pending.pop(ticket)
        if k is None or k < 0 or k >= len(p["chains"]):
            return Emission("none", ticket, response=json.dumps({"t": ticket, "rows": []}))
        return self._exec(ticket, p["chains"][k], p["have"], p["want"], p["gv"], t0, goal=p.get("goal", ""))

    def _exec(self, ticket, ch: Chain, have, want, gv, t0, fast=False, goal: str = "") -> Emission:
        rows, calls = self.run_chain(ch, have, want)
        self.pending[ticket] = {"chain": ch, "gv": gv, "goal": goal}
        resp = json.dumps({"t": ticket, "rows": rows}, separators=(",", ":"), default=str)
        return Emission("ok", ticket, rows=rows, chain_key=ch.key, n_calls=calls, router_ms=(time.perf_counter() - t0) * 1e3,
                        response=resp, fast=fast)

    # ---------------------------------------------------------------- learning
    def feedback(self, ticket: str, ok: bool):
        p = self.pending.pop(ticket, None)
        if not p or "chain" not in p or not self.cfg.memory:
            return
        self._record(p["goal"], p["gv"], p["chain"].key, ok)

    def _record(self, goal: str, gv, key: tuple, ok: bool, log: bool = True):
        if log:
            self.log.append({"goal": goal, "chain": list(key), "ok": bool(ok)})
        self.episodes[key].append((gv, bool(ok)))
        st = self.stats.setdefault(key, {"succ": 0, "goals": [], "recent": deque(maxlen=4)})
        st["recent"].append(bool(ok))
        if ok:
            st["succ"] += 1
            st["goals"].append(gv)
            if self.cfg.reflex and st["succ"] >= self.cfg.reflex_n:
                c = np.mean(st["goals"], axis=0)
                n = float(np.linalg.norm(c))
                self.reflexes[key] = (c / n if n else c).astype(np.float32)
                self.reflex_mean[key] = c.astype(np.float32)
        else:
            if key in self.reflexes and list(st["recent"]).count(False) >= 2:
                del self.reflexes[key]
                self.reflex_mean.pop(key, None)
                st["succ"], st["goals"] = 0, []

    # ---------------------------------------------------------------- persistence (memory survives sessions)
    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.log, f)

    def load(self, path: str):
        with open(path) as f:
            for e in json.load(f):
                self._record(e["goal"], self.emb.embed(e["goal"]), tuple(e["chain"]), e["ok"])
