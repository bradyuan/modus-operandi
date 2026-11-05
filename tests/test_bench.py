"""The benchmark harness, end to end against two real local MO servers, with a scripted model in
place of OpenAI (plumbing only: the latency numbers come from real runs, never from this)."""

import argparse
import asyncio
import json
import re
import time

from bench import harness
from mo import profiles, tunes

TUNES = 12


class ScriptedModel:
    """Answers, calls mo_output, then does every pass MO hands out, in order."""

    name = "scripted"

    async def respond(self, instructions, items, tools, previous):
        names = {t["name"] for t in tools}
        assert names == set(harness.OUTPUT_TOOLS)
        if previous is None:
            return harness.Reply("r0", [("c0", "mo_output", {"initial": "Sleep matters because the body repairs.",
                                                              "request": items[0]["content"]})], 10, 10)
        text = items[0]["output"]
        step = re.search(r"MO pass (\d+) of \d+", text)
        run = re.search(r'run="([0-9a-f]{8})"', text)
        if not step:
            return harness.Reply("rN", [], 1, 1)
        k = int(step.group(1))
        return harness.Reply(f"r{k}", [(f"c{k}", "mo_output_pass", {
            "run": run.group(1), "pass_number": k, "version": f"Version {k}: sleep repairs the body."})], 10, 10)


def frozen_profile(home):
    """One seed and TUNES sealed tunes, the way MO stores them."""
    profiles.create("voice")
    profiles.add_seed("voice", "Short sentences. Plain words. One idea at a time.", box="b")
    folder = home / "profiles" / "voice"
    for i in range(TUNES):
        tune = {"id": f"{i:08x}", "profile": "voice", "chat": None, "started": 1.0, "active": 1.0,
                "status": tunes.SEALED, "sealed": time.time() - i, "final": f"Tuned part {i}.",
                "descriptions": [], "rounds": [{"answered": True, "pick": "A", "variants": {
                    "A": f"Tuned part {i}.", "B": "No.", "C": "Nope."}}], "source": {"text": "x"}}
        (folder / "tunes" / f"{tune['id']}.json").write_text(json.dumps(tune))
    return folder


def test_the_harness_runs_both_schedules_on_the_same_queries(mo_home, tmp_path):
    profile = frozen_profile(mo_home)
    queries = tmp_path / "queries.jsonl"
    queries.write_text("".join(json.dumps({"id": f"q{i}", "category": "open_qa", "query": f"@MO question {i}"}) + "\n"
                               for i in range(3)))
    args = argparse.Namespace(profile_dir=str(profile), schedule=["A=1,3,10,30", "B=10,30,100"], queries=str(queries),
                              limit=3, concurrency=2, out_dir=str(tmp_path / "bench"),
                              instructions=harness.mo_instructions())
    out = asyncio.run(harness.run_all(args, ScriptedModel()))

    rows = [json.loads(line) for line in out.read_text().splitlines()[1:]]
    assert len(rows) == 6 and all(r["status"] == "finished" for r in rows)
    # 1 seed pass, then 12 tunes: A = 1 + 3 + 8 (3 passes), B = 10 + 2 (2 passes)
    assert {r["schedule"]: r["passes"] for r in rows} == {"A": 4, "B": 3}
    assert {r["schedule"]: r["model_calls"] for r in rows} == {"A": 5, "B": 4}
    assert all(r["initial"] <= r["first_voiced"] <= r["e2e"] for r in rows)
    summary = harness.report(out)
    assert "A 1,3,10,30" in summary and "p95" in summary and "faster" in summary


def test_percentiles_are_nearest_rank():
    values = [float(v) for v in range(1, 101)]
    assert [harness.percentile(values, p) for p in (50, 95, 99)] == [50.0, 95.0, 99.0]
    assert harness.percentile([3.0], 99) == 3.0 and harness.percentile([], 50) is None
