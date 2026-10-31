"""`@MO tune`: variation rounds whose flow is decided by MO's code, not the host.

A session targets one part (a sentence, a paragraph, a section of a source). The user
answers each round with one of three outcomes (AGENTS.md, core design item 3):

    picked    record the pick; draft mode is done, diagnostic mode moves to the next round
    none_fit  stay on the SAME target; try another dimension; ask what's off after 2 misses
    skipped   record no preference; move on
"""

from __future__ import annotations

import json
import re
import secrets
from typing import Any

from mo.store import Profile, mo_home

MAX_DIAGNOSTIC_ROUNDS = 5
ASK_AFTER = 2
WHATS_OFF = "What's off with it: what it says, the wording, or the angle? A few words is enough."

AXES = {
    "reading": [
        ("opening", ["mechanism first (how it works)", "analogy first (from a field the user knows)",
                     "concrete example first"]),
        ("order", ["bottom line first", "build up to the point", "start from a question"]),
        ("depth", ["short (3–4 sentences)", "medium (a paragraph or two)", "deep (full detail)"]),
        ("format", ["plain prose", "bullet points", "a small diagram or table plus prose"]),
        ("background", ["no background", "one line of background", "full historical context"]),
    ],
    "writing": [
        ("tone", ["plain and direct", "vivid and concrete", "punchy and confident"]),
        ("rhythm", ["short sentences", "mixed short and long", "long, flowing sentences"]),
        ("opening", ["start with a story or scene", "start with the main point", "start with a question"]),
        ("formality", ["casual", "neutral", "formal"]),
        ("detail", ["lean: only what matters", "some supporting detail", "rich detail and specifics"]),
    ],
}

_ID_RE = re.compile(r"^[0-9a-f]{8}$")


def _path(session_id: str):
    if not _ID_RE.match(session_id):
        raise ValueError(f"Unknown tune session {session_id!r}; start a new one with action 'start'")
    return mo_home() / "sessions" / f"{session_id}.json"


def _load(session_id: str) -> dict[str, Any]:
    path = _path(session_id)
    if not path.exists():
        raise ValueError(f"Unknown tune session {session_id!r}; start a new one with action 'start'")
    return json.loads(path.read_text())


def _save(session: dict[str, Any]) -> None:
    path = _path(session["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session, ensure_ascii=False))


def start(
    profile: Profile,
    task: str,
    mode: str,
    register: str | None = None,
    target: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    session = {
        "id": secrets.token_hex(4),
        "profile": profile.name,
        "task": task,
        "mode": mode,
        "register": register,
        "target": target,
        "source": source,
        "round": 1,
        "tried_axes": [],
        "axis": _first_axis(task, 1),
        "misses": 0,
        "rejected": [],
        "notes": [],
        "done": False,
    }
    _save(session)
    return _plan(session)


def answer(session_id: str, outcome: str, chosen: str | None = None, note: str | None = None) -> dict[str, Any]:
    session = _load(session_id)
    if session["done"]:
        raise ValueError("This tune session is finished; start a new one with action 'start'")
    profile = Profile(session["profile"])
    axis_name, options = AXES[session["task"]][session["axis"]]
    labels = dict(zip("ABC", options))

    if outcome == "picked":
        if chosen not in labels:
            raise ValueError("outcome 'picked' needs chosen = 'A', 'B', or 'C'")
        _record(profile, session, axis_name, labels, "picked", chosen, note)
        if session["mode"] == "draft":
            return _finish(session, f"Use variation {chosen} ({labels[chosen]}) for the target part.")
        return _advance(session)

    if outcome == "none_fit":
        _record(profile, session, axis_name, labels, "none_fit", None, note)
        session["misses"] += 1
        session["rejected"] += [f"{axis_name}: {o}" for o in options]
        if note:
            session["notes"].append(note)
        session["tried_axes"].append(session["axis"])
        session["axis"] = _next_untried_axis(session)
        _save(session)
        return _plan(session)

    if outcome == "skipped":
        if session["mode"] == "draft":
            return _finish(session, "Keep the target part as it was.")
        return _advance(session)

    raise ValueError(f"Unknown outcome {outcome!r}; use 'picked', 'none_fit', or 'skipped'")


def _first_axis(task: str, round_number: int) -> int:
    return (round_number - 1) % len(AXES[task])


def _next_untried_axis(session: dict[str, Any]) -> int:
    count = len(AXES[session["task"]])
    for step in range(1, count + 1):
        candidate = (session["axis"] + step) % count
        if candidate not in session["tried_axes"]:
            return candidate
    # Every dimension has missed on this target: cycle, steered by the rejected list and notes.
    return (session["axis"] + 1) % count


def _advance(session: dict[str, Any]) -> dict[str, Any]:
    if session["round"] >= MAX_DIAGNOSTIC_ROUNDS:
        return _finish(session, "Diagnostic complete. Thank the user; their picks are recorded.")
    session.update(round=session["round"] + 1, tried_axes=[], misses=0, rejected=[], notes=[], target=None)
    session["axis"] = _first_axis(session["task"], session["round"])
    _save(session)
    return _plan(session)


def _finish(session: dict[str, Any], instruction: str) -> dict[str, Any]:
    session["done"] = True
    _save(session)
    return {"session": session["id"], "profile": session["profile"], "status": "done", "next": instruction}


def _record(profile, session, axis_name, labels, outcome, chosen, note) -> None:
    profile.append_case({
        "type": "variations",
        "task": session["task"],
        "register": session["register"],
        "data": {
            "mode": session["mode"],
            "outcome": outcome,
            "axis": axis_name,
            "options": labels,
            "chosen": chosen,
            "passed_over": [k for k in labels if k != chosen],
            "attempt": session["misses"] + 1,
            "target": session["target"],
            "note": note,
        },
    })


def _plan(session: dict[str, Any]) -> dict[str, Any]:
    axis_name, options = AXES[session["task"]][session["axis"]]
    labels = dict(zip("ABC", options))

    if session["mode"] == "draft":
        what = ("Rewrite ONLY the target part three ways. Keep everything else in the draft unchanged.")
    elif session["task"] == "reading":
        what = ("Pick one short, meaty section of the source and explain that same section three times. "
                "Keep using the same section until the user picks one.")
    else:
        what = ("Write the same short paragraph three times from the user's notes (if there are none, ask for "
                "2–3 lines of rough notes). Use only those notes.")

    steps = [
        what,
        f"Keep the content identical; vary ONLY the {axis_name}: "
        + "; ".join(f"{k} = {v}" for k, v in labels.items()) + ".",
    ]
    if session["rejected"]:
        steps.append("The user already rejected these approaches for this same part, so make all three clearly "
                     "different from them: " + "; ".join(session["rejected"]) + ".")
    if session["notes"]:
        steps.append("The user said what's off: " + " | ".join(session["notes"]) + ". Fix exactly that.")
    steps += [
        "Show them labeled A, B, C, followed by two more choices: 'None of these work' and 'Skip'. "
        "Don't say which you prefer.",
        f"Pass the user's answer to mo_tune(action='answer', session='{session['id']}', outcome=..., chosen=..., "
        "note=...): outcome='picked' with chosen='A'|'B'|'C'; 'none_fit' if they reject all three; 'skipped' if "
        "they want to move on. Never decide the next step yourself; MO's reply tells you what comes next.",
    ]

    plan = {
        "session": session["id"],
        "profile": session["profile"],
        "status": "regenerate" if session["misses"] else "show_variations",
        "task": session["task"],
        "mode": session["mode"],
        "target": session["target"],
        "source": session["source"],
        "axis": axis_name,
        "variations": labels,
        "steps": steps,
    }
    if session["mode"] == "diagnostic":
        plan.update(round=session["round"], of=MAX_DIAGNOSTIC_ROUNDS)
    if session["misses"] >= ASK_AFTER and not session["notes"]:
        plan["ask_user"] = WHATS_OFF
        steps.insert(0, f"Before writing new versions, ask the user: '{WHATS_OFF}' Write the new versions to fix "
                        "what they say, and pass their answer as `note` when you report the outcome.")
    return plan
