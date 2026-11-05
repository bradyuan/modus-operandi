"""Output runs (`@MO` + anything): ChatGPT writes, MO keeps the books (DESIGN §6).

A run starts from ChatGPT's INITIAL answer, in the chat's voice (a profile). If the chat has no
voice yet, the run waits until the human user picks one in the Output window. MO then hands out the
profile's seeds in fixed batches;
each pass, ChatGPT sends back a rewritten version (or declares "no change" with a reason). MO
diffs every version against the current one, and refuses identical text and out-of-order passes.
The Output window always shows the best version so far with "x% voice loaded" (availability over
consistency, AGENTS.md item 6). MO never writes or judges text, and never retries on its own.

    ~/.mo/profiles/<name>/runs/<id>.json   (a run waiting for its voice: ~/.mo/runs/<id>.json)
"""

from __future__ import annotations

import difflib
import json
import re
import secrets
import time
from pathlib import Path
from typing import Any

from mo import profiles, tunes
from mo.events import mo_home

PROMPT_VERSION = "pass-v1"       # seed passes
TUNES_PROMPT_VERSION = "tunes-v1"  # tune passes
PROMPT = (Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.txt").read_text()
TUNES_PROMPT = (Path(__file__).parent / "prompts" / f"{TUNES_PROMPT_VERSION}.txt").read_text()
BATCH_WORDS = 3000
TUNE_BATCHES = (10, 30, 100)    # tunes per pass, then ×3 each pass: passes grow ~log₃ N (was 1, 3, 10, 30)
PICKUP_SECONDS = 20         # ChatGPT hasn't even started on the user's Continue → offer Retry sooner
STALL_SECONDS = 90          # no next step from ChatGPT for this long → the window offers "Continue?"
WAITING_EXPIRES = 24 * 3600  # a run that never got a voice is dropped after this
_ID_RE = re.compile(r"^[0-9a-f]{8}$")


def batches(seeds: list[dict[str, Any]], budget: int = BATCH_WORDS) -> list[list[str]]:
    """Seed ids in fixed batches: oldest first, about `budget` words each (a longer seed is its own batch)."""
    out: list[list[str]] = []
    words = budget
    for seed in seeds:
        if words + seed["words"] > budget and out and out[-1]:
            out.append([])
            words = 0
        if not out:
            out.append([])
            words = 0
        out[-1].append(seed["id"])
        words += seed["words"]
    return [b for b in out if b]


def tune_batches(ids: list[str]) -> list[list[str]]:
    """Ranked tune ids in batches of 10, 30, 100, then ×3 each pass (300, 900, …): ~log₃ N passes."""
    out, i, k, size = [], 0, 0, 0
    while i < len(ids):
        size = TUNE_BATCHES[k] if k < len(TUNE_BATCHES) else size * 3
        out.append(ids[i:i + size])
        i, k = i + size, k + 1
    return out


def tune_words(tune: dict[str, Any]) -> int:
    """Words a tune contributes to a pass: its final, the user's notes, and what they turned down."""
    return sum(len(t.split()) for t in [tune["final"], *tunes.notes(tune), *tunes.rejected(tune)])


def changed(before: str, after: str) -> int:
    """Percent of words that differ between two versions (a fact, not a judgment)."""
    a, b = before.split(), after.split()
    if not a and not b:
        return 0
    same = sum(block.size for block in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return round(100 * (1 - same / max(len(a), len(b))))


def _path(profile: str | None, run_id: str) -> Path:
    if not _ID_RE.match(run_id or ""):
        raise ValueError(f"Unknown MO run {run_id!r}")
    return (profiles._dir(profile) if profile else mo_home()) / "runs" / f"{run_id}.json"


def _save(run: dict[str, Any]) -> None:
    path = _path(run["profile"], run["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, ensure_ascii=False))


def find(run_id: Any) -> dict[str, Any]:
    """A run by id, in whichever profile holds it."""
    if not isinstance(run_id, str) or not _ID_RE.match(run_id):
        raise ValueError(f"Unknown MO run {run_id!r}")
    for path in [*profiles._root().glob(f"*/runs/{run_id}.json"), mo_home() / "runs" / f"{run_id}.json"]:
        if path.exists():
            return json.loads(path.read_text())
    raise ValueError(f"Unknown MO run {run_id!r}")


def start(profile: str | None, initial: Any, request: Any, chat: str | None) -> dict[str, Any]:
    """A new run. With no profile, it waits for `assign` (the human user picking the chat's voice)."""
    if not isinstance(initial, str) or not initial.strip():
        raise ValueError("Send your full answer as `initial`")
    now = time.time()
    run = {"id": secrets.token_hex(4), "profile": None, "chat": chat, "started": now, "active": now,
           "request": str(request or "")[:300], "initial": initial.strip(), "prompt": PROMPT_VERSION,
           "batches": [], "batch_words": [], "passes": []}
    if profile:
        return assign(run, profile)
    _save(run)
    return run


def assign(run: dict[str, Any], profile: str) -> dict[str, Any]:
    """Give a waiting run its voice: lock the profile and fix the seed batches."""
    if run["profile"]:
        raise ValueError("This run already has a voice")
    waiting = _path(None, run["id"])
    seeds = profiles.seeds(profile)
    ranked = tunes.sealed_for(profile)
    words = {s["id"]: s["words"] for s in seeds} | {t["id"]: tune_words(t) for t in ranked}
    seed_batches, tune_batches_ = batches(seeds), tune_batches([t["id"] for t in ranked])
    fixed = seed_batches + tune_batches_
    run.update(profile=profile, batches=fixed, batch_kinds=["seeds"] * len(seed_batches) + ["tunes"] * len(tune_batches_),
               batch_words=[sum(words[i] for i in b) for b in fixed], active=time.time())
    _save(run)
    waiting.unlink(missing_ok=True)
    return run


def rerun(run: dict[str, Any], profile: str) -> dict[str, Any]:
    """A new run from the same initial, in another voice."""
    return start(profile, run["initial"], run["request"], run.get("chat"))


def ready(run: dict[str, Any]) -> bool:
    return run["profile"] is not None


def touch(run: dict[str, Any]) -> None:
    """The user asked ChatGPT to carry on (resets the stall clock and waits for ChatGPT to pick it up)."""
    run["active"] = run["asked"] = time.time()
    _save(run)


def picked_up(run: dict[str, Any]) -> None:
    """ChatGPT asked MO for this run's next step (mo_output_continue)."""
    run["picked_up"] = time.time()
    _save(run)


def waiting_for_pickup(run: dict[str, Any]) -> bool:
    return run.get("picked_up", 0) < run.get("asked", 0)


def voice_loaded(run: dict[str, Any]) -> int:
    """Percent of the run's seed words already passed through: a count, not a judgment."""
    total = sum(run.get("batch_words") or [])
    if not ready(run):
        return 0
    if not total:
        return 100
    return round(100 * sum(run["batch_words"][: len(run["passes"])]) / total)


def stalled(run: dict[str, Any], now: float | None = None) -> bool:
    """No next step from ChatGPT: 20 s if it never picked up the user's Continue, else 90 s."""
    if not ready(run) or done(run):
        return False
    waited = (now or time.time()) - max(run.get("active", run["started"]), run.get("picked_up", 0))
    return waited > (PICKUP_SECONDS if waiting_for_pickup(run) else STALL_SECONDS)


def expire_waiting(now: float | None = None) -> list[str]:
    """Drop runs that never got a voice within WAITING_EXPIRES. Returns their ids."""
    folder = mo_home() / "runs"
    gone = []
    for path in folder.glob("*.json") if folder.is_dir() else []:
        run = json.loads(path.read_text())
        if (now or time.time()) - run["started"] > WAITING_EXPIRES:
            path.unlink()
            gone.append(run["id"])
    return gone


def current(run: dict[str, Any]) -> str:
    for p in reversed(run["passes"]):
        if p.get("version") is not None:
            return p["version"]
    return run["initial"]


def done(run: dict[str, Any]) -> bool:
    return ready(run) and len(run["passes"]) == len(run["batches"])


def submit(run: dict[str, Any], pass_number: Any, version: Any, no_change_reason: Any) -> dict[str, Any]:
    """Record one pass. Exactly one of `version` or `no_change_reason`."""
    expected = len(run["passes"]) + 1
    if not ready(run):
        raise ValueError("This run is waiting for the user to pick the chat's voice in the MO box")
    if done(run):
        raise ValueError("All passes are already in; the MO window shows the result")
    if pass_number != expected:
        raise ValueError(f"This is pass {expected}, not {pass_number!r}")
    has_version = isinstance(version, str) and version.strip() != ""
    has_reason = isinstance(no_change_reason, str) and no_change_reason.strip() != ""
    if has_version == has_reason:
        raise ValueError("Send either the full rewritten `version` or a one-line `no_change_reason`, not both")
    before = current(run)
    entry: dict[str, Any] = {"pass": expected, "at": time.time(), "seeds": run["batches"][expected - 1],
                             "kind": kind(run, expected)}
    if has_version:
        text = version.strip()
        if text == before:
            raise ValueError("This is identical to the current version. If you mean no change, send "
                             "`no_change_reason` instead.")
        entry.update(version=text, changed=changed(before, text))
    else:
        entry.update(no_change=no_change_reason.strip()[:300], changed=0)
    run["passes"].append(entry)
    run["active"] = run["picked_up"] = time.time()
    _save(run)
    return entry


def kind(run: dict[str, Any], k: int) -> str:
    """'seeds' or 'tunes' for pass k (runs from before tunes have only seed passes)."""
    kinds = run.get("batch_kinds") or ["seeds"] * len(run["batches"])
    return kinds[k - 1]


def payload(run: dict[str, Any]) -> str:
    """What ChatGPT gets for the next pass: the fixed prompt, INITIAL, CURRENT, and this batch's
    EXAMPLES (seed passes) or TUNED parts with their NOTES and REJECTED versions (tune passes)."""
    k = len(run["passes"]) + 1
    block = lambda t: f"<<<\n{t}\n>>>"  # noqa: E731
    head = f"\n\nINITIAL:\n{block(run['initial'])}\n\nCURRENT:\n{block(current(run))}"
    ids = run["batches"][k - 1]
    if kind(run, k) == "seeds":
        by_id = {s["id"]: s for s in profiles.seeds(run["profile"])}
        examples = [by_id[i]["text"] for i in ids if i in by_id]  # a deleted seed drops out
        text = (PROMPT.format(k=k, n=len(run["batches"]), run=run["id"]) + head + "\n\nEXAMPLES:\n"
                + "\n\n".join(block(e) for e in examples))
    else:
        by_id = {t["id"]: t for t in tunes.sealed_for(run["profile"])}
        parts = []
        for t in (by_id[i] for i in ids if i in by_id):  # a deleted tune drops out
            parts.append(f"TUNED:\n{block(t['final'])}"
                         + "".join(f"\nNOTE: {block(n)}" for n in tunes.notes(t))
                         + "".join(f"\nREJECTED: {block(r)}" for r in tunes.rejected(t)))
        text = TUNES_PROMPT.format(k=k, n=len(run["batches"]), run=run["id"]) + head + "\n\n" + "\n\n".join(parts)
    # Keep exactly what was handed out for each pass, so the trace is a true record.
    sent = run.setdefault("sent", {})
    if str(k) not in sent:
        sent[str(k)] = text
        _save(run)
    return text


def summary(run: dict[str, Any]) -> dict[str, Any]:
    """What the Output window shows: always the best version so far, and how much voice is in it."""
    return {"run": run["id"], "profile": run["profile"], "done": done(run), "stalled": stalled(run), "picked_up": not waiting_for_pickup(run),
            "best": current(run), "voice_loaded": voice_loaded(run), "seeds": bool(run["batches"]),
            "passes": len(run["passes"]), "of": len(run["batches"]),
            "changed": changed(run["initial"], current(run))}


DONE = ("Done: the MO window above shows the result. Reply with one short line, like "
        "\"Here's the MO output.\" Don't repeat the text.")


def next_step(run: dict[str, Any]) -> str:
    """What ChatGPT should do next for a run that has its voice."""
    if done(run):
        if not run["batches"]:
            return f"The voice {run['profile']!r} has no seeds, so there are no passes. " + DONE
        return "All passes are in. " + DONE
    return payload(run)


def list_for(profile: str) -> list[dict[str, Any]]:
    """Every run in a profile, newest first, full text included (for the local trace)."""
    folder = profiles._dir(profile) / "runs"
    found = [json.loads(p.read_text()) for p in folder.glob("*.json")] if folder.is_dir() else []
    return sorted(found, key=lambda r: r["started"], reverse=True)
