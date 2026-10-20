"""Text utilities: tokenisation, a dependency-free hashed TF-IDF embedding, token counting.

NOTE: there is no pretrained embedding model here (no network to model hubs). This is a
lexical embedding (word unigrams/bigrams + char trigrams, hashed). It is deliberately weak on
synonyms; a real sentence-embedding model should only improve the semantic part of affinity.
"""
from __future__ import annotations

import json
import math
import re
import zlib

import numpy as np

DIM = 4096
_SPLIT = re.compile(r"[^a-z0-9]+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
STOP = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are", "was", "were",
    "be", "by", "with", "from", "at", "as", "that", "this", "it", "its", "me", "my", "i", "you",
    "what", "which", "who", "whom", "whose", "s", "whats", "give", "show", "tell", "please",
    "optionally", "filtered", "like",
}


def stem(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 5 and w.endswith("ing"):
        return w[:-3]
    if len(w) > 4 and w.endswith("ed"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def words(text: str) -> list[str]:
    text = _CAMEL.sub(" ", str(text)).lower()
    out = []
    for w in _SPLIT.split(text):
        if not w or w in STOP:
            continue
        out.append(stem(w))
    return out


def _h(s: str) -> int:
    return zlib.crc32(s.encode()) % DIM


def feats(text: str) -> dict[int, float]:
    ws = words(text)
    f: dict[int, float] = {}
    for w in ws:
        f[_h("w:" + w)] = f.get(_h("w:" + w), 0.0) + 1.0
        if len(w) >= 4:
            p = f"^{w}$"
            for i in range(len(p) - 2):
                k = _h("c:" + p[i:i + 3])
                f[k] = f.get(k, 0.0) + 0.25
    for a, b in zip(ws, ws[1:]):
        k = _h(f"b:{a}_{b}")
        f[k] = f.get(k, 0.0) + 0.7
    return f


class Embedder:
    """Hashed TF-IDF. IDF is fit on a corpus (the tool catalog)."""

    def __init__(self, corpus: list[str]):
        df = np.zeros(DIM, dtype=np.float32)
        for doc in corpus:
            for k in feats(doc):
                df[k] += 1
        n = max(1, len(corpus))
        self.idf = (np.log((n + 1) / (df + 1)) + 1.0).astype(np.float32)
        self._cache: dict[str, np.ndarray] = {}

    def embed(self, text: str) -> np.ndarray:
        v = self._cache.get(text)
        if v is not None:
            return v
        v = np.zeros(DIM, dtype=np.float32)
        for k, c in feats(text).items():
            v[k] += c * self.idf[k]
        nrm = float(np.linalg.norm(v))
        if nrm > 0:
            v /= nrm
        if len(self._cache) < 200000:
            self._cache[text] = v
        return v


def cos(a: np.ndarray, b: np.ndarray) -> float:
    return float(a @ b)


def ntok(obj) -> int:
    """Token estimate (~3.5 chars/token for JSON-ish text). Relative comparisons only."""
    s = obj if isinstance(obj, str) else json.dumps(obj, separators=(",", ":"), default=str)
    return max(1, int(round(len(s) / 3.5)))
