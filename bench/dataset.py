"""Build the benchmark's query set from Databricks Dolly-15k (CC BY-SA 3.0), never from our own prompts.

    uv run python -m bench.dataset            # → bench/queries.jsonl (300 queries, fixed seed)

A stratified sample from the categories that match what MO is for (explaining and writing):
open_qa, general_qa, creative_writing, summarization. Rows whose context is over MAX_CONTEXT_WORDS
are left out (cost control); that rule, the seed, and the source row of every query are recorded,
so anyone can rebuild the exact same set.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import httpx

URL = "https://huggingface.co/datasets/databricks/databricks-dolly-15k/resolve/main/databricks-dolly-15k.jsonl"
HERE = Path(__file__).parent
RAW = HERE / "data" / "databricks-dolly-15k.jsonl"
OUT = HERE / "queries.jsonl"
CATEGORIES = ("open_qa", "general_qa", "creative_writing", "summarization")
MAX_CONTEXT_WORDS = 600
SEED = 15


def download() -> list[dict]:
    if not RAW.exists():
        RAW.parent.mkdir(parents=True, exist_ok=True)
        r = httpx.get(URL, follow_redirects=True, timeout=120)
        r.raise_for_status()
        RAW.write_bytes(r.content)
    return [json.loads(line) for line in RAW.read_text().splitlines() if line.strip()]


def query_text(row: dict) -> str:
    """What the user types in ChatGPT: '@MO' + the instruction, with the context pasted below if any."""
    text = f"@MO {row['instruction'].strip()}"
    return f"{text}\n\n{row['context'].strip()}" if row.get("context", "").strip() else text


def build(rows: list[dict], n: int = 300, seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    per = n // len(CATEGORIES)
    picked = []
    for category in CATEGORIES:
        pool = [(i, r) for i, r in enumerate(rows) if r["category"] == category
                and len(r.get("context", "").split()) <= MAX_CONTEXT_WORDS]
        picked += rng.sample(pool, per)
    rng.shuffle(picked)
    return [{"id": f"dolly-{i}", "category": r["category"], "query": query_text(r)} for i, r in picked]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-n", type=int, default=300)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    queries = build(download(), args.n, args.seed)
    OUT.write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in queries))
    counts = {c: sum(q["category"] == c for q in queries) for c in CATEGORIES}
    print(f"{len(queries)} queries → {OUT} (seed {args.seed}, context ≤ {MAX_CONTEXT_WORDS} words): {counts}")


if __name__ == "__main__":
    main()
