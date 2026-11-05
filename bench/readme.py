"""The README's "Performance Benchmarks" section, generated from result files only (never typed in).

    uv run python -m bench.readme bench/results/<a>.jsonl [<b>.jsonl …]
      → prints the Markdown section and writes docs/images/benchmark.svg

One row per (model, schedule) in the given files. The chart shows each row's end-to-end latency:
a solid bar to p50, a lighter extension to p95, and a tick at p99.
"""

from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

from bench.harness import percentile

ROOT = Path(__file__).parent.parent
SVG = ROOT / "docs" / "images" / "benchmark.svg"


def rows_from(paths: list[Path]) -> tuple[list[dict], dict]:
    rows, meta = [], {}
    for path in paths:
        lines = path.read_text().splitlines()
        meta = json.loads(lines[0])["meta"]
        runs = [json.loads(line) for line in lines[1:] if line.strip()]
        for label, batches in meta["schedules"].items():
            mine = [r for r in runs if r["schedule"] == label]
            ok = [r for r in mine if r["status"] == "finished"]
            e2e = [r["e2e"] for r in ok]
            mean = lambda k: sum(r[k] for r in ok) / len(ok) if ok else 0  # noqa: E731
            rows.append({"model": meta["model"], "reasoning": meta.get("reasoning"), "schedule": batches,
                         "finished": len(ok), "runs": len(mine), "date": meta["started"][:8],
                         "p50": percentile(e2e, 50), "p95": percentile(e2e, 95), "p99": percentile(e2e, 99),
                         "first": percentile([r["first_voiced"] for r in ok if r["first_voiced"]], 50),
                         "passes": mean("passes"), "calls": mean("model_calls"), "out": mean("output_tokens")})
    return rows, meta


def svg(rows: list[dict]) -> str:
    """A static image GitHub can show (no script), readable in light and dark mode."""
    label_w, bar_w, row_h, top = 230, 420, 46, 58
    width, height = label_w + bar_w + 70, top + row_h * len(rows) + 34
    top_value = max((r["p99"] or 0) for r in rows) or 1
    step = next(s for s in (1, 2, 5, 10, 15, 20, 30, 60, 120, 300, 600) if top_value / s <= 6)
    ticks = list(range(0, int(top_value // step + 2) * step, step))
    scale = bar_w / ticks[-1]
    x = lambda v: label_w + v * scale  # noqa: E731
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
           'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" role="img" '
           'aria-label="End-to-end latency per model: p50, p95, p99">',
           "<style>.bg{fill:#fcfcfb}.t1{fill:#0b0b0b}.t2{fill:#52514e}.grid{stroke:#e4e3df}"
           ".p50{fill:#2a78d6}.p95{fill:#2a78d6;fill-opacity:.35}.p99{stroke:#0b0b0b}"
           "@media (prefers-color-scheme:dark){.bg{fill:#1a1a19}.t1{fill:#f0efec}.t2{fill:#c3c2b7}"
           ".grid{stroke:#3a3a37}.p50{fill:#3987e5}.p95{fill:#3987e5;fill-opacity:.4}.p99{stroke:#f0efec}}</style>",
           f'<rect class="bg" width="{width}" height="{height}" rx="8"/>',
           f'<text class="t1" x="16" y="26" font-size="15" font-weight="600">End-to-end latency, seconds</text>'
           + (f'<text class="t1" x="{width - 16}" y="26" font-size="13" font-weight="600" text-anchor="end">'
              f'p50 −{100 * (1 - rows[1]["p50"] / rows[0]["p50"]):.0f}% · p95 −{100 * (1 - rows[1]["p95"] / rows[0]["p95"]):.0f}%</text>'
              if len(rows) == 2 and rows[0]["p50"] and rows[1]["p50"] else ""),
           f'<text class="t2" x="16" y="44" font-size="12">bar = p50 · lighter = to p95 · tick = p99</text>']
    for t in ticks:
        out.append(f'<line class="grid" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{top - 6}" y2="{height - 28}"/>'
                   f'<text class="t2" x="{x(t):.1f}" y="{height - 12}" font-size="11" text-anchor="middle">{t}</text>')
    for i, r in enumerate(rows):
        y = top + i * row_h
        name = escape(f"tunes {r['schedule'].replace(',', ', ')}")
        sub = escape(f"{r['model']} · {r['calls']:.0f} model calls")
        out.append(f'<text class="t1" x="16" y="{y + 17}" font-size="13" font-weight="600">{name}</text>'
                   f'<text class="t2" x="16" y="{y + 33}" font-size="11">{sub}</text>')
        if r["p50"] is None:
            continue
        mid = y + 13
        out.append(f'<rect class="p95" x="{x(0):.1f}" y="{mid}" width="{(r["p95"] or r["p50"]) * scale:.1f}" height="16" rx="4"/>'
                   f'<rect class="p50" x="{x(0):.1f}" y="{mid}" width="{r["p50"] * scale:.1f}" height="16" rx="4"/>'
                   f'<line class="p99" x1="{x(r["p99"]):.1f}" x2="{x(r["p99"]):.1f}" y1="{mid - 4}" y2="{mid + 20}" stroke-width="2"/>'
                   f'<text class="t1" x="{x(r["p99"]) + 8:.1f}" y="{mid + 12}" font-size="11">'
                   f'{r["p50"]:.0f} / {r["p95"]:.0f} / {r["p99"]:.0f}</text>')
    out.append("</svg>")
    return "\n".join(out)


def markdown(rows: list[dict], meta: dict) -> str:
    fmt = lambda v: f"{v:.1f} s" if v is not None else "–"  # noqa: E731
    n = max(r["runs"] for r in rows)
    lines = ["## Performance Benchmarks", "",
             f"End-to-end latency of `@MO` + a request: from the query being sent to the last pass accepted "
             f"(100% voice loaded). **{n} queries** from [Databricks Dolly-15k]"
             "(https://huggingface.co/datasets/databricks/databricks-dolly-15k) (open QA, general QA, creative "
             "writing, summarization), each run through MO's real MCP tool loop with the OpenAI Responses API "
             f"standing in for ChatGPT, on one real profile (`{meta.get('profile')}`). "
             "How to reproduce: [bench/README.md](bench/README.md).", "",
             "![End-to-end latency per model](docs/images/benchmark.svg)", "",
             "| Model | Tune batches | Finished | p50 | p95 | p99 | First voiced (p50) | Model calls | Output tokens |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        model = r["model"] + (f" ({r['reasoning']})" if r["reasoning"] else "")
        lines.append(f"| {model} | {r['schedule']} | {r['finished']}/{r['runs']} | {fmt(r['p50'])} | {fmt(r['p95'])} | "
                     f"{fmt(r['p99'])} | {fmt(r['first'])} | {r['calls']:.1f} | {r['out']:,.0f} |")
    return "\n".join(lines)


def main() -> None:
    rows, meta = rows_from([Path(p) for p in sys.argv[1:]])
    SVG.parent.mkdir(parents=True, exist_ok=True)
    SVG.write_text(svg(rows))
    print(markdown(rows, meta))
    print(f"\n(chart written to {SVG})", file=sys.stderr)


if __name__ == "__main__":
    main()
