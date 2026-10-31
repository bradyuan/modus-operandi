"""Lightweight, deterministic stylometry.

Features are chosen to be mostly topic-independent: function-word rates, sentence
length, and punctuation habits. Good enough to rank exemplars and report drift;
not an authorship classifier.
"""

from __future__ import annotations

import math
import re

FUNCTION_WORDS = (
    "the a an and but or so because if then that this these those it its i me my we our "
    "you your he she they them of in on at to for with from by as is was are were be been "
    "not no just really very also only even still about like what which who when where how"
).split()

_WORD_RE = re.compile(r"[A-Za-z']+|\d[\d,.]*")
_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]*")


def words(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.findall(text) if s.strip()]


def style_vector(text: str) -> dict[str, float]:
    ws = words(text)
    n = max(len(ws), 1)
    sents = sentences(text) or [text]
    lengths = [len(words(s)) for s in sents]
    vec = {
        # Scaled so each feature lands roughly in 0..1.
        "sentence_length": (sum(lengths) / len(lengths)) / 40,
        "comma_rate": text.count(",") / n * 10,
        "em_dash_rate": (text.count("—") + text.count(" - ")) / n * 20,
        "question_rate": text.count("?") / len(sents),
    }
    for fw in FUNCTION_WORDS:
        vec[f"fw:{fw}"] = ws.count(fw) / n * 10
    return vec


def centroid(vectors: list[dict[str, float]]) -> dict[str, float]:
    keys = vectors[0].keys()
    return {k: sum(v[k] for v in vectors) / len(vectors) for k in keys}


def distance(a: dict[str, float], b: dict[str, float]) -> float:
    return math.sqrt(sum((a[k] - b[k]) ** 2 for k in a)) / math.sqrt(len(a))
