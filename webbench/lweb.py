"""Ligand-Web and a similarity-only baseline, driving a real (headless Chromium) browser.

Shared by every agent (not part of what is being compared): perception (forms, links, record sets, overlays), overlay dismissal,
503 retry, pagination following. Compared: how an intent {have, want} is *bound* to the page.

Ligand-Web binds by shape (receptor complementarity):
  inputs  - a have-value only fits a field whose widget can hold it (value in <select> options, ISO date -> date field, ...);
            a form with a required field nothing binds to is rejected
  outputs - a wanted field binds to the result column whose *values* have the right shape (money, time, percent, temperature, phone, ...);
            columns that merely echo a have-value are excluded; a single leftover text column binds by elimination
  verify  - an attempt only counts if the result page yields every wanted field; otherwise it backs off and tries the next affordance
  ask     - near-ties between columns are returned as an `ask` (the agent picks); picks are remembered as vocabulary
The baseline binds by label similarity only (the same vocabulary the dev sites use), then fills/reads whatever scores best."""
from __future__ import annotations

import itertools
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ligand.text import ntok
from .sitegen import V

# ------------------------------------------------------------------------------------------------ vocabulary
TERMS: dict[str, list[str]] = defaultdict(list)       # concept -> phrases (dev vocabulary only: V[k][:3] + canonical names + task phrasings)
for _k, _v in V.items():
    TERMS[_k] += [x.lower() for x in _v[:3]] + [_k]
for _k, _extra in {"airline": ["carrier"], "price": ["fare", "cost", "last price", "amount"], "temperature": ["degrees", "temp"], "phone": ["telephone"],
                   "company": ["employer"], "salary": ["pay"], "restoname": ["name", "restaurant"], "change": ["percent change", "% change"],
                   "population": ["inhabitants"], "capital": ["capital city"], "stock": ["units in stock", "units"], "shelf": ["location"],
                   "status": ["availability"], "city": ["location"], "title_q": ["title"], "keyword": ["job title", "role"]}.items():
    TERMS[_k] += _extra
HAVE_CONCEPT = {"origin": "origin", "destination": "destination", "date": "date", "city": "city", "location": "city", "title": "title_q", "product": "product",
                "category": "product", "keyword": "keyword", "cuisine": "cuisine", "ticker": "ticker", "term": "term"}
WANT_CONCEPT = {}
for _c, _ts in TERMS.items():
    for _t in _ts:
        WANT_CONCEPT.setdefault(_t, _c)
WANT_CONCEPT.update({"name": "restoname", "location": "shelf", "price": "price", "title": "title", "status": "status", "temp": "temperature"})
SHAPE_OF = {"price": "money", "salary": "money", "temperature": "temp", "humidity": "percent", "change": "percent", "phone": "phone", "population": "int",
            "stock": "int", "rating": "rating", "shelf": "code", "depart": "time", "sku": "code"}

RX = [("money", r"[$€£]\s?\d|\d\s?USD|USD\s?\d"), ("time", r"^\d{1,2}:\d{2}(\s?[AP]M)?$"), ("percent", r"^-?\d+(\.\d+)?\s?%$"),
      ("temp", r"^-?\d+(\.\d+)?\s?°\s?C?$"), ("phone", r"^(\+1-)?555-\d{4}$"), ("rating", r"^★ \d(\.\d)?$|^\d(\.\d)?/5$|^\d\.\d$"),
      ("int", r"^\d{1,3}(,\d{3})+$|^\d+$"), ("code", r"^[A-Z]-\d+$|^[A-Z]\d{4}$")]
RXC = [(n, re.compile(p)) for n, p in RX]


def vshape(v: str) -> str:
    v = v.strip()
    for n, rx in RXC:
        if rx.search(v):
            return n
    return "text"


def toks(s: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z]+", s.lower()):
        out.append(w[:-1] if len(w) > 3 and w.endswith("s") else w)
    return out


TERMS_FULL: dict[str, list[str]] = defaultdict(list)
for _k, _v in V.items():
    TERMS_FULL[_k] += [x.lower() for x in _v] + [_k]
for _k, _v in TERMS.items():
    TERMS_FULL[_k] += _v


def lexsim(label: str, concept: str, vocab: dict | None = None, full: bool = False) -> float:
    if vocab:
        w = vocab.get(" ".join(toks(label)), {})
        if concept in w:
            return 1.0
    a = set(toks(label))
    if not a:
        return 0.0
    best = 0.0
    for t in (TERMS_FULL if full else TERMS).get(concept, []):
        b = set(toks(t))
        if b:
            best = max(best, len(a & b) / max(len(a), len(b)))
    return best


# ------------------------------------------------------------------------------------------------ perception (shared)
PERCEIVE_JS = r"""
() => {
 const txt = e => (e.innerText||e.textContent||'').replace(/\s+/g,' ').trim();
 const vis = e => { const r=e.getBoundingClientRect(); const s=getComputedStyle(e); return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'; };
 window.__lw = window.__lw||0;
 const tag = e => { if(!e.dataset.lw) e.dataset.lw = String(++window.__lw); return e.dataset.lw; };
 const isAd = e => /sponsored|promoted/i.test(txt(e));
 const forms = [...document.querySelectorAll('form')].filter(vis).map(f => {
   const fields = [...f.querySelectorAll('input,select,textarea')].filter(e => !['hidden','submit','button'].includes(e.type) && vis(e)).map(e => {
     let label = '';
     if (e.id) { const l = document.querySelector('label[for="'+e.id+'"]'); if (l) label = txt(l); }
     if (!label) { const w = e.closest('label'); if (w) { const c = w.cloneNode(true); c.querySelectorAll('select,input').forEach(x=>x.remove()); label = txt(c); } }
     if (!label && e.previousElementSibling && ['SPAN','DIV','LABEL'].includes(e.previousElementSibling.tagName)) label = txt(e.previousElementSibling);
     const aria = e.getAttribute('aria-label')||'', ph = e.getAttribute('placeholder')||'';
     if (!label) label = aria; if (!label) label = ph;
     if (!label && e.tagName==='SELECT' && e.options.length && !e.options[0].value) label = txt(e.options[0]).replace(/^select\s+/i,'');
     const opts = e.tagName==='SELECT' ? [...e.options].map(o=>o.value).filter(v=>v) : [];
     return {lw: tag(e), type: e.tagName==='SELECT' ? 'select' : e.type, label, ph, opts, req: e.required};
   });
   const b = f.querySelector('button,[type=submit]');
   return {lw: tag(f), action: f.getAttribute('action')||'', fields, submit: b ? tag(b) : null, btn: b ? txt(b) : ''};
 });
 // record sets: repeated containers with label/value pairs
 const recs = [];
 const link = el => { const a = [...el.querySelectorAll('a')].find(a => !/sponsored/i.test(txt(a))); return a ? {href: a.href, lw: tag(a)} : null; };
 document.querySelectorAll('main table').forEach(t => {
   const hs = [...t.querySelectorAll('thead th')].map(txt);
   t.querySelectorAll('tbody tr').forEach(tr => { const tds = [...tr.querySelectorAll('td')]; const cells = {}; hs.forEach((h,i) => { if (h && tds[i]) cells[h] = txt(tds[i]); });
     recs.push({cells, ad: isAd(tr), link: link(tr), el: tag(tr)}); }); });
 document.querySelectorAll('main .card').forEach(c => { const cells = {}; c.querySelectorAll('.kv').forEach(kv => { const k = kv.querySelector('.k'), v = kv.querySelector('.v'); if (k && v) cells[txt(k)] = txt(v); });
   recs.push({cells, ad: isAd(c), link: link(c), el: tag(c)}); });
 document.querySelectorAll('main ul > li').forEach(li => { const cells = {}; let cur = null;
   li.childNodes.forEach(n => { if (n.nodeName==='B') cur = txt(n).replace(/:$/,''); else if (n.nodeType===3 && cur) { const v = n.textContent.replace(/·/g,'').trim(); if (v) { cells[cur] = v; cur = null; } } });
   if (Object.keys(cells).length) recs.push({cells, ad: isAd(li), link: link(li), el: tag(li)}); });
 document.querySelectorAll('main dl').forEach(dl => { const cells = {}; const dts = [...dl.querySelectorAll('dt')], dds = [...dl.querySelectorAll('dd')]; dts.forEach((d,i) => { if (dds[i]) cells[txt(d)] = txt(dds[i]); });
   const host = dl.parentElement; recs.push({cells, ad: isAd(host), link: link(host), el: tag(host)}); });
 const recEls = new Set(recs.map(r => document.querySelector('[data-lw="'+r.el+'"]')));
 const inRec = a => { let p = a; while (p) { if (recEls.has(p)) return true; p = p.parentElement; } return false; };
 const lastRec = recs.length ? document.querySelector('[data-lw="'+recs[recs.length-1].el+'"]') : null;
 const links = [...document.querySelectorAll('a')].filter(a => vis(a) && !inRec(a)).map(a => {
   const afterRec = lastRec && (lastRec.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING) && !!a.closest('main');
   return {text: txt(a), aria: a.getAttribute('aria-label')||'', href: a.href, lw: tag(a), ad: /sponsored|win a free/i.test(txt(a)), pager: !!afterRec};
 });
 const h1 = document.querySelector('h1');
 return {forms, recs: recs.filter(r => Object.keys(r.cells).length), links, h1: h1 ? txt(h1) : '', loading: /Loading results/.test(document.body.innerText), empty: /No results/i.test(document.body.innerText)};
}
"""

OVERLAY_JS = r"""
() => {
 let n = 0;
 document.querySelectorAll('body *').forEach(e => {
   const s = getComputedStyle(e);
   if (s.position === 'fixed' && parseInt(s.zIndex||0) >= 1000 && e.getBoundingClientRect().width >= innerWidth*0.9) {
     const bs = [...e.querySelectorAll('button,a,[role=button]')];
     const pick = bs.find(b => /reject|close|no thanks|dismiss|×/i.test((b.innerText||'')+(b.getAttribute('aria-label')||''))) || bs[0];
     if (pick) { pick.click(); n++; } else { e.remove(); n++; }
   }
 });
 return n;
}
"""


class Env:
    """One browser page + counters (page loads, tokens a raw-DOM agent would have read)."""

    def __init__(self, page, web):
        self.page, self.web = page, web
        self.loads = 0
        self.steps = 0
        self.ptok = 0
        self.retries = 0
        self.t0 = time.time()
        page.set_default_timeout(1500)
        self._seen = None

    def settle(self):
        pg = self.page
        for i in range(30):
            try:
                n = pg.evaluate(OVERLAY_JS)
                st = pg.evaluate("()=>[/Loading results/.test(document.body.innerText), document.querySelector('h1')?document.querySelector('h1').innerText:'']")
            except Exception:
                pg.wait_for_timeout(40)
                continue
            if st[1].startswith("503"):
                self.retries += 1
                if self.retries > 12:
                    return
                self.loads += 1
                pg.wait_for_timeout(30)
                pg.reload()
                continue
            if not n and not st[0]:
                break
            pg.wait_for_timeout(50)
        try:
            self.ptok += ntok(pg.content())
        except Exception:
            pass

    def goto(self, url):
        self.loads += 1
        self.steps += 1
        self.page.goto(url, wait_until="domcontentloaded")
        self.settle()
        self.view()            # (re)tag elements: ids are deterministic by document order, so earlier affordances stay addressable after a reload

    def view(self):
        for _ in range(3):
            try:
                return self.page.evaluate(PERCEIVE_JS)
            except Exception:
                self.page.wait_for_timeout(60)
        return {"forms": [], "recs": [], "links": [], "h1": "", "loading": False, "empty": True}

    def click_nav(self, sel):
        self.steps += 1
        for k in range(3):
            before = self.web.requests
            try:
                self.page.click(sel, timeout=1000)
                break
            except Exception as e:
                if "intercept" not in str(e):
                    break
                self.page.evaluate(OVERLAY_JS)
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=2500)
        except Exception:
            pass
        self.loads += max(0, self.web.requests - before)
        self.settle()
        return self.web.requests > before

    def submit(self, form, assign: dict):
        """assign: field lw -> value. Returns True if the browser navigated."""
        pg = self.page
        for lw, (typ, val) in assign.items():
            sel = f'[data-lw="{lw}"]'
            self.steps += 1
            for k in range(3):
                try:
                    if typ == "select":
                        pg.select_option(sel, value=val, timeout=300)
                    else:
                        pg.fill(sel, val, timeout=800)
                    break
                except Exception as e:
                    if k == 2 or "intercept" not in str(e):
                        return False
                    pg.evaluate(OVERLAY_JS)
        if form["submit"] is None:
            return False
        return self.click_nav(f'[data-lw="{form["submit"]}"]')


# ------------------------------------------------------------------------------------------------ memory
@dataclass
class Memory:
    vocab: dict = field(default_factory=lambda: defaultdict(dict))     # normalized label -> {concept: weight}
    recipes: dict = field(default_factory=dict)                        # host -> form signature that worked

    def learn(self, label: str, concept: str, w: float = 1.0):
        k = " ".join(toks(label))
        if k:
            self.vocab[k][concept] = self.vocab[k].get(concept, 0) + w

    def forget(self, label: str, concept: str):
        k = " ".join(toks(label))
        self.vocab.get(k, {}).pop(concept, None)


def fsig(form) -> str:
    return form["action"] + "|" + ",".join(sorted(f["type"] for f in form["fields"]))


# ------------------------------------------------------------------------------------------------ binding helpers
def have_compat(val: str, f: dict) -> float:
    """0 = the field cannot hold this value; >0 = fits."""
    v = str(val)
    iso = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v))
    if f["type"] == "select":
        return 1.0 if v.lower() in [o.lower() for o in f["opts"]] else 0.0
    if f["type"] == "date":
        return 1.0 if iso else 0.0
    if f["type"] == "email":
        return 1.0 if "@" in v else 0.0
    if f["type"] in ("text", "search", "textarea"):
        if iso:
            return 1.0 if re.search(r"yyyy|date", (f["ph"] or "").lower()) else 0.4
        return 0.6
    return 0.3


def bind_form(form, have: dict, vocab, gate: bool, shape: bool = True):
    """best assignment of have-values to fields -> (score, {lw: (type, value)}, used_haves) or None."""
    fields, keys = form["fields"], list(have)
    if not fields:
        return None
    best = None
    for perm in itertools.permutations(range(len(fields)), min(len(keys), len(fields))):
        s, assign, ok = 0.0, {}, True
        for ki, fi in zip(keys, perm):
            f = fields[fi]
            c = have_compat(have[ki], f) if gate else 0.6
            if gate and c == 0:
                ok = False
                break
            lx = lexsim(f["label"], HAVE_CONCEPT.get(ki, ki), vocab)
            s += c + 0.75 * lx
            val = str(have[ki])
            if f["type"] == "select":
                val = next((o for o in f["opts"] if o.lower() == val.lower()), val)
            assign[f["lw"]] = (f["type"], val)
        if not ok:
            continue
        used = {f["lw"] for f in fields if f["lw"] in assign}
        if gate and any(f["req"] and f["lw"] not in used for f in fields):
            continue
        s -= 0.6 * (len(keys) - len(assign))                       # unconsumed have-values
        if best is None or s > best[0]:
            best = (s, assign, len(assign))
    return best


def col_info(recs, have_vals):
    cols = defaultdict(list)
    for r in recs:
        for k, v in r["cells"].items():
            cols[k].append(v)
    info = {}
    for k, vals in cols.items():
        sh = Counter(vshape(v) for v in vals).most_common(1)[0]
        info[k] = {"shape": sh[0] if sh[1] / len(vals) >= 0.75 else "mixed", "echo": any(v.strip().lower() in have_vals for v in vals)}
    return info


def pick_cols(recs, wants: list[str], have: dict, vocab, shape: bool):
    """wants: list of canonical concepts. Returns [(label|None, score, margin)] aligned with wants, and per-want candidate lists."""
    hv = {str(v).lower() for v in have.values()}
    info = col_info(recs, hv)
    cand = []
    for c in wants:
        want_shape = SHAPE_OF.get(c, "text")
        L = []
        for lab, i in info.items():
            lx = lexsim(lab, c, vocab)
            if shape:
                if want_shape != "text":
                    if i["shape"] != want_shape:
                        continue
                    base = 1.0
                else:
                    if i["shape"] != "text" or i["echo"]:
                        continue
                    base = 0.25
            else:
                if lx <= 0:
                    continue
                base = 0.0
            L.append((base + 0.75 * lx, lab))
        L.sort(reverse=True)
        cand.append(L)
    best, bs = None, -1
    opts = [c_[:4] or [(0.0, None)] for c_ in cand]
    for combo in itertools.product(*opts):
        labs = [x[1] for x in combo if x[1] is not None]
        if len(labs) != len(set(labs)):
            continue
        s = sum(x[0] for x in combo)
        if s > bs:
            best, bs = combo, s
    out = []
    for i, c_ in enumerate(cand):
        if best is None or best[i][1] is None:
            out.append((None, 0.0, 0.0, c_))
            continue
        sc, lab = best[i]
        rivals = [x for x in c_ if x[1] != lab and x[1] not in [b[1] for j, b in enumerate(best) if j != i]]
        out.append((lab, sc, sc - (rivals[0][0] if rivals else 0.0), c_))
    return out


def rows_of(recs, have: dict, echo_filter: bool = True):
    rs = [r for r in recs if not r["ad"]]
    if not echo_filter:
        return rs
    hv = {str(v).lower() for v in have.values()}
    keep = [r for r in rs if any(c.strip().lower() in hv for c in r["cells"].values())]
    return keep or rs


# ------------------------------------------------------------------------------------------------ agents
@dataclass
class Result:
    rows: list | None = None
    ask: int = 0
    note: str = ""
    path: str = ""
    cols: dict = field(default_factory=dict)       # want name -> column label (for memory feedback)
    sig: str = ""


class LigandWeb:
    def __init__(self, mem: Memory | None, shape=True, gate=True, verify=True, use_mem=True, echo=True):
        self.mem, self.shape, self.gate, self.verify, self.use_mem, self.echo = mem or Memory(), shape, gate, verify, use_mem, echo

    @property
    def vocab(self):
        return self.mem.vocab if self.use_mem else None

    # ---- affordances: forms and links ranked by input fit
    def affordances(self, view, have, host):
        out = []
        for f in view["forms"]:
            b = bind_form(f, have, self.vocab, self.gate)
            if b is None:
                continue
            s = b[0] + (2.0 if self.use_mem and self.mem.recipes.get(host) == fsig(f) else 0.0)
            out.append((s, "form", f, b[1]))
        hv = [str(v) for v in have.values()]
        for lk in view["links"]:
            if lk["ad"] or lk["pager"]:
                continue
            t = lk["text"].strip().lower()
            sc = 0.0
            for v in hv:
                vl = v.lower()
                if t == vl:
                    sc = max(sc, 1.2)
                elif vl in t:
                    sc = max(sc, 0.5)
            if sc:
                out.append((sc, "link", lk, None))
        out.sort(key=lambda x: -x[0])
        return out

    def run(self, env: Env, start: str, have: dict, wants: list[str], want_names: list[str], chooser, host: str) -> Result:
        concepts = [WANT_CONCEPT.get(w.lower(), w.lower()) for w in wants]
        env.goto(start)
        res = Result()
        view = env.view()
        tried = 0
        affs = self.affordances(view, have, host)
        for s, kind, obj, assign in affs[: (4 if self.verify else 1)]:
            tried += 1
            if kind == "form":
                if not env.submit(obj, assign):
                    if env.page.url.rstrip("/") == start.rstrip("/") or True:
                        env.goto(start) if env.page.url != start else None
                    continue
                sig = fsig(obj)
            else:
                if not env.click_nav(f'[data-lw="{obj["lw"]}"]'):
                    env.goto(start)
                    continue
                sig = ""
            out = self.extract(env, have, concepts, want_names, chooser, res)
            if out is not None:
                res.rows, res.sig = out, sig
                res.path = kind
                return res
            if self.verify:
                env.goto(start)
        res.note = "no affordance produced the wanted fields"
        return res

    def extract(self, env: Env, have, concepts, want_names, chooser, res: Result):
        view = env.view()
        recs = rows_of(view["recs"], have, self.echo)
        if not recs:
            return None
        picks = pick_cols(recs, concepts, have, self.vocab, self.shape)
        weak = [i for i, p in enumerate(picks) if p[0] is None or p[1] < 0.6]
        if weak and any(r["link"] for r in recs) and self.verify:
            # some wanted field is not on this page: follow the matched record's link and merge the detail fields
            merged = []
            for r in recs[:4]:
                if not r["link"]:
                    merged.append(r)
                    continue
                env.goto(r["link"]["href"])
                dv = env.view()
                d = dv["recs"][0]["cells"] if dv["recs"] else {}
                merged.append({"cells": {**{k: v for k, v in r["cells"].items()}, **{k: v for k, v in d.items() if k not in r["cells"]}}, "ad": False, "link": None})
            recs = merged
            picks = pick_cols(recs, concepts, have, self.vocab, self.shape)
            weak = [i for i, p in enumerate(picks) if p[0] is None or p[1] < 0.6]
            pager = []
        else:
            pager = [l for l in view["links"] if l["pager"] and not l["ad"]]
        # all wants need at least an elimination-level binding
        if any(p[0] is None or p[1] < 0.2 for p in picks):
            return None
        # near-ties -> ask
        labels = []
        for i, (lab, sc, mg, cand) in enumerate(picks):
            if lab is not None and len(cand) > 1 and lexsim(lab, concepts[i], self.vocab) < 0.9 and mg < 0.5:
                res.ask += 1
                opts = [x[1] for x in cand[:3]]
                ch = chooser(want_names[i], opts) if chooser else None
                if ch is not None:
                    lab = ch
                    if self.use_mem:
                        self.mem.learn(lab, concepts[i], 1.0)
            labels.append(lab)
        if len(set(labels)) != len(labels):
            return None
        res.cols = dict(zip(want_names, labels))
        rows = [[r["cells"].get(l, "") for l in labels] for r in rows_of(recs, have, self.echo)]
        for _ in range(4):
            if not pager:
                break
            env.click_nav(f'[data-lw="{pager[0]["lw"]}"]')
            v2 = env.view()
            r2 = rows_of(v2["recs"], have, self.echo)
            if not r2:
                break
            rows += [[r["cells"].get(l, "") for l in labels] for r in r2]
            pager = [l for l in v2["links"] if l["pager"] and not l["ad"]]
        return rows

    def feedback(self, res: Result, concepts, ok: bool):
        if not self.use_mem:
            return
        if ok:
            for (w, lab), c in zip(res.cols.items(), concepts):
                if lab and lexsim(lab, c, None) < 0.5:
                    self.mem.learn(lab, c, 0.6)
        else:
            for (w, lab), c in zip(res.cols.items(), concepts):
                if lab:
                    self.mem.forget(lab, c)


class SimBrowser:
    """Baseline: bind by lexical similarity alone (same vocabulary as the dev sites). No value-shape typing, no input gate,
    no echo exclusion, no learning. `backtrack`: if the attempt yields no records, try the next-best form/link."""

    def __init__(self, backtrack=True, full=False):
        self.backtrack, self.full = backtrack, full

    def run(self, env: Env, start: str, have: dict, wants: list[str], want_names: list[str], goal: str, chooser=None, host="") -> Result:
        concepts = [WANT_CONCEPT.get(w.lower(), w.lower()) for w in wants]
        env.goto(start)
        view = env.view()
        res = Result()
        gt = set(toks(goal))
        affs = []
        for f in view["forms"]:
            if not f["fields"]:
                continue
            used, assign, score = set(), {}, 0.0
            for k, v in have.items():
                best = None
                for fl in f["fields"]:
                    if fl["lw"] in used:
                        continue
                    sim = lexsim(fl["label"], HAVE_CONCEPT.get(k, k), None, self.full)
                    if best is None or sim > best[0]:
                        best = (sim, fl)
                if best:
                    used.add(best[1]["lw"])
                    assign[best[1]["lw"]] = (best[1]["type"], str(v))
                    score += best[0]
            affs.append((score, "form", f, assign))
        for lk in view["links"]:
            if lk["ad"] or lk["pager"]:
                continue
            lt = set(toks(lk["text"]))
            if lt and gt:
                affs.append((len(lt & gt) / len(lt | gt), "link", lk, None))
        affs.sort(key=lambda x: -x[0])
        for s, kind, obj, assign in affs[: (4 if self.backtrack else 1)]:
            if kind == "form":
                if not env.submit(obj, assign):
                    env.goto(start)
                    continue
            else:
                if not env.click_nav(f'[data-lw="{obj["lw"]}"]'):
                    env.goto(start)
                    continue
            out = self.extract(env, have, concepts, want_names, res)
            if out is not None:
                res.rows = out
                return res
            if self.backtrack:
                env.goto(start)
        res.note = "none"
        return res

    def pick(self, recs, concepts):
        labs = []
        cols = {k for r in recs for k in r["cells"]}
        for c in concepts:
            best = max(((lexsim(l, c, None, self.full), l) for l in cols), default=(0, None))
            labs.append(best[1] if best[0] > 0 else None)
        return labs

    def extract(self, env, have, concepts, want_names, res):
        view = env.view()
        recs = rows_of(view["recs"], have, echo_filter=False)
        if not recs:
            return None
        labs = self.pick(recs, concepts)
        pager = [l for l in view["links"] if l["pager"] and not l["ad"]]
        if any(l is None for l in labs):
            r0 = next((r for r in recs if r["link"]), None)
            if r0 is None:
                return None
            env.goto(r0["link"]["href"])
            dv = env.view()
            recs = [{"cells": {**recs[0]["cells"], **(dv["recs"][0]["cells"] if dv["recs"] else {})}, "ad": False, "link": None}]
            labs = self.pick(recs, concepts)
            pager = []
            if any(l is None for l in labs):
                return None
        res.cols = dict(zip(want_names, labs))
        rows = [[r["cells"].get(l, "") for l in labs] for r in recs]
        for _ in range(4):
            if not pager:
                break
            env.click_nav(f'[data-lw="{pager[0]["lw"]}"]')
            v2 = env.view()
            r2 = rows_of(v2["recs"], have, echo_filter=False)
            if not r2:
                break
            rows += [[r["cells"].get(l, "") for l in labs] for r in r2]
            pager = [l for l in v2["links"] if l["pager"] and not l["ad"]]
        return rows
