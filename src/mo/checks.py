"""Deterministic checks run on host-written drafts (see docs/DESIGN.md §10, §11.6).

No LLM calls. Every flag carries a concrete fix the host can act on.
"""

from __future__ import annotations

import difflib
import re
from typing import Any

from mo import style
from mo.store import Exemplar
from mo.weights import rule_weight, strength

AI_TELLS = (
    "leverage", "leveraging", "delve", "delving", "tapestry", "testament to", "in today's fast-paced",
    "fast-paced environment", "i'm excited to", "i am excited to", "navigate the complexities",
    "seamless", "seamlessly", "synergy", "game-changer", "unlock the potential", "elevate",
    "it's worth noting", "in conclusion", "a rich history", "plays a pivotal role", "pivotal",
    "robust", "cutting-edge", "spearheaded", "passionate about",
)
COPY_NGRAM = 4

_NUMBER_RE = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?%?")


def _phrase_re(phrase: str) -> re.Pattern[str]:
    return re.compile(r"(?<![\w'])" + re.escape(phrase) + r"(?![\w'])", re.IGNORECASE)


def _ngrams(tokens: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def _numbers(text: str) -> set[str]:
    # "40%" and "40 percent" should match, so compare bare numbers.
    return {m.replace(",", "").rstrip("%") for m in _NUMBER_RE.findall(text or "")}


def check_ai_tells(draft: str) -> list[dict[str, Any]]:
    flags = []
    for phrase in AI_TELLS:
        if _phrase_re(phrase).search(draft):
            flags.append({
                "type": "ai_tell",
                "severity": "fix",
                "detail": phrase,
                "fix": f"Replace '{phrase}' (generic AI wording) with how the author would say it.",
            })
    return flags


def check_copied_phrases(
    draft: str, source_text: str, keywords: list[str], own_text: str
) -> list[dict[str, Any]]:
    """Flag runs of words shared with the source, except approved keywords and the user's own words."""
    draft_tokens = style.words(draft)
    source = _ngrams(style.words(source_text), COPY_NGRAM)
    own = _ngrams(style.words(own_text), COPY_NGRAM)
    allowed = {w for kw in keywords for w in style.words(kw)} | set(style.FUNCTION_WORDS)

    hits = [False] * len(draft_tokens)
    for i in range(len(draft_tokens) - COPY_NGRAM + 1):
        gram = tuple(draft_tokens[i : i + COPY_NGRAM])
        if gram in source and gram not in own and not set(gram) <= allowed:
            for j in range(i, i + COPY_NGRAM):
                hits[j] = True

    flags, i = [], 0
    while i < len(hits):
        if hits[i]:
            j = i
            while j < len(hits) and hits[j]:
                j += 1
            phrase = " ".join(draft_tokens[i:j])
            flags.append({
                "type": "copied_phrase",
                "severity": "fix",
                "detail": phrase,
                "fix": f"Rewrite '{phrase}' in the author's words; it's copied from the source text.",
            })
            i = j
        else:
            i += 1
    return flags


def check_unsupported_numbers(draft: str, supported_text: str) -> list[dict[str, Any]]:
    supported = _numbers(supported_text)
    return [
        {
            "type": "unsupported_fact",
            "severity": "fix",
            "detail": n,
            "fix": f"Remove or correct '{n}': it isn't in the facts or the author's notes.",
        }
        for n in sorted(_numbers(draft) - supported)
    ]


def check_rules(draft: str, rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enforce checkable rules (rules with a `check` field) that are strong enough to apply."""
    flags = []
    for rule in rules:
        check = rule.get("check")
        if not check or strength(rule_weight(rule)) is None:
            continue
        kind, value = check.get("type"), check.get("value")
        if kind == "banned_phrase" and _phrase_re(str(value)).search(draft):
            flags.append({"type": "rule", "severity": "fix", "detail": rule["rule"],
                          "fix": f"Remove '{value}' (the author's rule: {rule['rule']})."})
        elif kind == "max_words" and len(style.words(draft)) > int(value):
            flags.append({"type": "rule", "severity": "fix", "detail": rule["rule"],
                          "fix": f"Cut to {value} words or fewer (now {len(style.words(draft))})."})
        elif kind == "max_count":
            count = len(re.findall(re.escape(str(check["pattern"])), draft))
            if count > int(value):
                flags.append({"type": "rule", "severity": "fix", "detail": rule["rule"],
                              "fix": f"Use '{check['pattern']}' at most {value} times (now {count})."})
    return flags


def check_keywords(draft: str, keywords: list[str]) -> list[dict[str, Any]]:
    return [
        {"type": "keyword_missing", "severity": "warn", "detail": kw,
         "fix": f"Work in '{kw}' naturally, if it fits."}
        for kw in keywords
        if not _phrase_re(kw).search(draft)
    ]


def seed_retention(seed: str, draft: str) -> float:
    seed_words = style.words(seed)
    if not seed_words:
        return 1.0
    matcher = difflib.SequenceMatcher(None, seed_words, style.words(draft), autojunk=False)
    kept = sum(block.size for block in matcher.get_matching_blocks())
    return round(kept / len(seed_words), 2)


def voice_distance(draft: str, exemplars: list[Exemplar]) -> float | None:
    if not exemplars:
        return None
    center = style.centroid([style.style_vector(e.text) for e in exemplars])
    return round(style.distance(style.style_vector(draft), center), 3)


def run_checks(
    draft: str,
    *,
    rules: list[dict[str, Any]] | None = None,
    seed: str | None = None,
    facts: str | None = None,
    source_text: str | None = None,
    keywords: list[str] | None = None,
    exemplars: list[Exemplar] | None = None,
) -> dict[str, Any]:
    keywords = keywords or []
    own_text = "\n".join(filter(None, [seed, facts]))

    flags = check_ai_tells(draft)
    if source_text:
        flags += check_copied_phrases(draft, source_text, keywords, own_text)
    flags += check_unsupported_numbers(draft, own_text)
    flags += check_rules(draft, rules or [])
    flags += check_keywords(draft, keywords)

    metrics: dict[str, Any] = {
        "word_count": len(style.words(draft)),
        "ai_tell_count": sum(f["type"] == "ai_tell" for f in flags),
        "voice_distance": voice_distance(draft, exemplars or []),
    }
    if seed:
        metrics["seed_retention"] = seed_retention(seed, draft)

    failed = any(f["severity"] == "fix" for f in flags)
    return {
        "status": "failed_checks" if failed else "passed",
        "fix": [f["fix"] for f in flags if f["severity"] == "fix"],
        "flags": flags,
        "metrics": metrics,
    }
