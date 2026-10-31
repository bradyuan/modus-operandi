"""Calibrate MO's voice checks on real authors.

Usage: uv run python evals/calibrate_voice.py <corpus-dir>

The corpus is plain-text books named <author>-<title>.txt (e.g. Project Gutenberg
downloads); it is never committed. For each author with two books, a "profile" of 3
short passages comes from one book; "drafts" are ~200-word passages from the other book
(same author) and from other authors (different author). Reports how well voice distance
separates them (AUC: 0.5 = chance, 1.0 = perfect) and how often the habit checks wrongly
flag an author's own writing.

Result on 16 Gutenberg books (2026-10-31): AUC 0.65 on 200-word drafts, so voice distance is
reported, never flagged; habit checks wrongly flagged under 1% of the authors' own passages.
"""

from __future__ import annotations

import collections
import random
import re
import statistics
import sys
from pathlib import Path

from mo import checks, style
from mo.store import Exemplar

PROFILE_SAMPLES, PROFILE_WORDS, DRAFT_WORDS, DRAFTS_PER_BOOK = 3, 300, 200, 30


def body(text: str) -> str:
    start = re.search(r"\*\*\* ?START OF.*?\*\*\*", text)
    end = re.search(r"\*\*\* ?END OF", text)
    text = text[start.end() if start else 0 : end.start() if end else len(text)]
    return re.sub(r"\s+", " ", text)


def passages(text: str, words: int, count: int, rng: random.Random) -> list[str]:
    tokens = text.split(" ")
    lo, hi = len(tokens) // 20, len(tokens) - words  # skip front matter
    return [" ".join(tokens[i : i + words]) for i in (rng.randrange(lo, hi) for _ in range(count))]


def auc(same: list[float], diff: list[float]) -> float:
    wins = sum((s < d) + 0.5 * (s == d) for s in same for d in diff)
    return wins / (len(same) * len(diff))


def main(corpus: Path) -> None:
    rng = random.Random(7)
    books: dict[str, list[str]] = {}
    for path in sorted(corpus.glob("*.txt")):
        books.setdefault(path.stem.split("-")[0], []).append(body(path.read_text(errors="ignore")))
    authors = [a for a, bs in books.items() if len(bs) >= 2]

    drafts = {a: passages(bs[-1], DRAFT_WORDS, DRAFTS_PER_BOOK, rng) for a, bs in books.items()}
    same, diff, false_flags = [], [], collections.Counter()
    for author in authors:
        profile = [Exemplar("essay", f"{author}{i}", p, 0.0)
                   for i, p in enumerate(passages(books[author][0], PROFILE_WORDS, PROFILE_SAMPLES, rng))]
        for other, texts in drafts.items():
            for draft in texts:
                (same if other == author else diff).append(checks.voice_distance(draft, profile))
                if other == author:
                    false_flags.update(f["detail"].split(":")[0] for f in checks.check_voice_habits(draft, profile))

    print(f"authors with 2 books: {', '.join(authors)}")
    print(f"same-author drafts: {len(same)}, different-author drafts: {len(diff)}")
    print(f"voice distance AUC: {auc(same, diff):.3f}")
    print(f"median distance: same {statistics.median(same):.3f}, different {statistics.median(diff):.3f}")
    rates = {k: f"{v / len(same):.1%}" for k, v in false_flags.items()} or "none"
    print(f"habit checks wrongly flagging the author's own drafts: {rates}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
