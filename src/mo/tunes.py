"""`@MO tune`: A/B/C rounds until the human user confirms "I like this voice" (DESIGN §4).

A tune works on one part of a text: an MO output from this chat, or text the human user pasted
into the window. The whole UI is the MO window; ChatGPT only writes variants. The human user clicks
the sentences they don't like (or "Choose for Me": MO takes the opening, the first 3 sentences),
optionally saying what's wrong. Each round, ChatGPT writes three variants of the current base; MO
locks them; the human user clicks A, B, or C, and the next round varies that pick (C → C1, C2, C3 →
…), until they click Done, which keeps the last pick. A note is always optional ("I don't like the
word debauchery"): it only informs the next round. The whole decision tree is stored, verbatim.

    ~/.mo/tunes/<id>.json                 an open tune (dropped after 24 h if never confirmed)
    ~/.mo/profiles/<name>/tunes/<id>.json a confirmed tune, part of the voice
"""

from __future__ import annotations

import json
import re
import secrets
import time
from pathlib import Path
from typing import Any

from mo import profiles
from mo.events import mo_home

PROMPT_VERSION = "tune-v1"
PROMPTS = Path(__file__).parent / "prompts"
STALL_SECONDS = 90  # same as runs.STALL_SECONDS
PICKUP_SECONDS = 20  # ChatGPT hasn't even started on the user's last click → offer Retry sooner
OPEN_EXPIRES = 24 * 3600
SKIP_SENTENCES = 3
_ID_RE = re.compile(r"^[0-9a-f]{8}$")
_SENTENCE_END = re.compile(r"[.!?…]+[\"')\]]*\s+")

# What the tune is doing, and who it's waiting for.
PART = "part"             # human user: click the part (or Choose for Me)
VARY = "vary"             # ChatGPT: write A/B/C
CHOOSE = "choose"         # human user: click A, B, or C (or Done)
SEALED = "sealed"


def sentences(text: str) -> list[str]:
    """The text cut into sentences, exactly as written (joined back, they are the text)."""
    out, start = [], 0
    for match in _SENTENCE_END.finditer(text):
        out.append(text[start:match.end()])
        start = match.end()
    if start < len(text):
        out.append(text[start:])
    return out


def opening(text: str, count: int = SKIP_SENTENCES) -> str:
    """Choose for Me: MO takes the opening of the text, its first few sentences (exactly as written)."""
    return "".join(sentences(text)[:count]).strip()


def _open_path(tune_id: str) -> Path:
    return mo_home() / "tunes" / f"{tune_id}.json"


def _path(tune: dict[str, Any]) -> Path:
    if tune["status"] == SEALED:
        return profiles._dir(tune["profile"]) / "tunes" / f"{tune['id']}.json"
    return _open_path(tune["id"])


def _save(tune: dict[str, Any]) -> None:
    path = _path(tune)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tune, ensure_ascii=False))


def find(tune_id: Any) -> dict[str, Any]:
    if not isinstance(tune_id, str) or not _ID_RE.match(tune_id):
        raise ValueError(f"Unknown MO tune {tune_id!r}")
    for path in [_open_path(tune_id), *profiles._root().glob(f"*/tunes/{tune_id}.json")]:
        if path.exists():
            return json.loads(path.read_text())
    raise ValueError(f"Unknown MO tune {tune_id!r}")


def start(profile: str, chat: str | None, text: str, run: str | None = None) -> dict[str, Any]:
    """A new tune of `text` (an output's best version, or pasted text) in `profile`'s voice."""
    if not text.strip():
        raise ValueError("There's no text to tune")
    now = time.time()
    tune = {"id": secrets.token_hex(4), "profile": profile, "chat": chat, "started": now, "active": now,
            "prompt": PROMPT_VERSION, "source": {"run": run, "text": text}, "status": PART,
            "descriptions": [], "target": None, "how": None, "rounds": [], "final": None, "sent": {}}
    _save(tune)
    return tune


def set_window(tune: dict[str, Any], box_id: str) -> None:
    """The newest window showing this tune; older ones fold up into a stub."""
    tune["window"] = box_id
    _save(tune)


def touch(tune: dict[str, Any]) -> None:
    tune["active"] = time.time()
    _save(tune)


def picked_up(tune: dict[str, Any]) -> None:
    """ChatGPT asked MO for this tune's next step (mo_tune_work)."""
    tune["picked_up"] = time.time()
    _save(tune)


def waiting_for_pickup(tune: dict[str, Any]) -> bool:
    """The user handed work to ChatGPT and ChatGPT hasn't asked MO for it yet."""
    return tune["status"] == VARY and tune.get("picked_up", 0) < tune["active"]


def stalled(tune: dict[str, Any], now: float | None = None) -> bool:
    """Waiting on ChatGPT too long: 20 s if it never picked up the user's click, else 90 s."""
    if tune["status"] != VARY:
        return False
    waited = (now or time.time()) - max(tune["active"], tune.get("picked_up", 0))
    return waited > (PICKUP_SECONDS if waiting_for_pickup(tune) else STALL_SECONDS)


def _need(tune: dict[str, Any], *statuses: str) -> None:
    if tune["status"] not in statuses:
        raise ValueError(f"This tune is at '{tune['status']}', not {' or '.join(repr(s) for s in statuses)}")


# --- the human user's steps (over the window's direct line)

def select(tune: dict[str, Any], first: Any, last: Any, note: Any = None) -> None:
    """The human user clicked the sentences they don't like (first..last), optionally saying why."""
    _need(tune, PART)
    parts = sentences(tune["source"]["text"])
    if not (isinstance(first, int) and isinstance(last, int) and 0 <= first <= last < len(parts)):
        raise ValueError("Click the sentences you want to tune")
    _set_part(tune, "".join(parts[first:last + 1]).strip(), "clicked", note)


def choose_for_me(tune: dict[str, Any], note: Any = None) -> None:
    """Choose for Me: MO picks the opening (first 3 sentences)."""
    _need(tune, PART)
    _set_part(tune, opening(tune["source"]["text"]), "chosen by MO", note)


def _set_part(tune: dict[str, Any], target: str, how: str, note: Any) -> None:
    if isinstance(note, str) and note.strip():
        tune["descriptions"].append(note.strip())
    tune.update(status=VARY, target=target, how=how)
    touch(tune)


def base(tune: dict[str, Any]) -> str:
    """What the next variants are variants of: the last pick, or else the target itself."""
    for r in reversed(tune["rounds"]):
        if r.get("pick"):
            return r["variants"][r["pick"]]
    return tune["target"]


def choose(tune: dict[str, Any], pick: Any, comment: Any, final: bool) -> None:
    """Record the human user's answer to the current round. `final` confirms the pick."""
    _need(tune, CHOOSE)
    current = tune["rounds"][-1]
    pick = pick or None
    comment = comment.strip() if isinstance(comment, str) else ""
    if pick is not None and pick not in current["variants"]:
        raise ValueError("Pick A, B, or C")
    if final and pick is None:
        raise ValueError("Pick the one you like before confirming")
    current.update(pick=pick, comment=comment or None, answered=time.time(), final=bool(final))
    if final:
        tune.update(status=SEALED, final=current["variants"][pick], sealed=time.time())
        _open_path(tune["id"]).unlink(missing_ok=True)
    else:
        tune["status"] = VARY
    touch(tune)


# --- ChatGPT's step (content only): write the variants

def variants(tune: dict[str, Any], round_number: Any, a: Any, b: Any, c: Any) -> dict[str, Any]:
    """ChatGPT's three variants for this round. Locked once recorded."""
    _need(tune, VARY)
    expected = len(tune["rounds"]) + 1
    if round_number != expected:
        raise ValueError(f"This is round {expected}, not {round_number!r}")
    texts = [t.strip() if isinstance(t, str) else "" for t in (a, b, c)]
    if not all(texts):
        raise ValueError("Send three variants: a, b, and c")
    if len(set(texts)) < 3:
        raise ValueError("The three variants must differ")
    entry = {"round": expected, "from": base(tune), "variants": dict(zip("ABC", texts)), "at": time.time()}
    tune["rounds"].append(entry)
    tune["status"] = CHOOSE
    touch(tune)
    return entry


def instructions(tune: dict[str, Any]) -> str:
    """What ChatGPT should do next for this tune (or why it should wait)."""
    status = tune["status"]
    block = lambda t: f"<<<\n{t}\n>>>"  # noqa: E731
    if status == VARY:
        k = len(tune["rounds"]) + 1
        text = tune["source"]["text"]
        start = text.find(tune["target"])
        before = text[max(0, start - 600):start] if start >= 0 else ""
        after = text[start + len(tune["target"]):][:600] if start >= 0 else ""
        history = "\n\n".join(
            f"Round {r['round']}: " + ", ".join(f"{k_}: {block(v)}" for k_, v in r["variants"].items())
            + f"\n  The user picked: {r.get('pick') or 'none'}" + (f"\n  The user said: {block(r['comment'])}" if r.get("comment") else "")
            for r in tune["rounds"]) or "(first round)"
        seeds = profiles.seeds(tune["profile"])
        said = "\n".join(block(d) for d in tune["descriptions"]) or "(nothing)"
        prompt = ((PROMPTS / f"{PROMPT_VERSION}.txt").read_text().format(k=k, tune=tune["id"])
                  + f"\n\nPART:\n{block(base(tune))}\n\nBEFORE IT:\n{block(before)}\n\nAFTER IT:\n{block(after)}"
                  + f"\n\nWHAT THE USER SAID ABOUT THIS PART:\n{said}"
                  + f"\n\nSO FAR:\n{history}\n\nEXAMPLES:\n" + "\n\n".join(block(s['text']) for s in seeds))
        tune["sent"].setdefault(str(k), prompt)
        _save(tune)
        return prompt
    if status == SEALED:
        return "This tune is done. Reply with one short line, like \"Tuned.\""
    return "Wait: the MO window is waiting for the user. It posts a message when there's work for you."


def done(tune: dict[str, Any]) -> None:
    """✓ Done: keep the last pick and seal. The round on screen when they clicked stays unanswered."""
    _need(tune, CHOOSE, VARY)
    picks = [r for r in tune["rounds"] if r.get("pick")]
    if not picks:
        raise ValueError("Pick A, B, or C first")
    last = picks[-1]
    last["final"] = True
    tune.update(status=SEALED, final=last["variants"][last["pick"]], sealed=time.time())
    _open_path(tune["id"]).unlink(missing_ok=True)
    touch(tune)


def discard(tune: dict[str, Any]) -> None:
    """Start over: an open tune is dropped, storing nothing."""
    if tune["status"] == SEALED:
        raise ValueError("This tune is already confirmed")
    _open_path(tune["id"]).unlink(missing_ok=True)


def open_for_chat(chat: str | None) -> dict[str, Any] | None:
    """The chat's unfinished tune, if any (one at a time: reopening resumes it)."""
    folder = mo_home() / "tunes"
    if not chat or not folder.is_dir():
        return None
    found_ = [json.loads(p.read_text()) for p in folder.glob("*.json")]
    found_ = [t for t in found_ if t.get("chat") == chat]
    return max(found_, key=lambda t: t["started"], default=None)


def tuned_text(tune: dict[str, Any]) -> str | None:
    """After confirming: the source text with the tuned part swapped in (a plain text replacement)."""
    if tune["status"] != SEALED or tune["target"] is None:
        return None
    return tune["source"]["text"].replace(tune["target"], tune["final"], 1)


def answered(tune: dict[str, Any]) -> int:
    """Rounds the user actually answered (a round on screen when they clicked Done doesn't count)."""
    return sum(1 for r in tune["rounds"] if r.get("answered"))


def rejected(tune: dict[str, Any]) -> list[str]:
    """Every variant the human user passed over, across the whole decision tree. (A round left
    unanswered when they clicked Done wasn't rejected, just not needed.)"""
    return [v for r in tune["rounds"] if r.get("answered") for k, v in r["variants"].items() if k != r.get("pick")]


def notes(tune: dict[str, Any]) -> list[str]:
    return [*tune["descriptions"], *(r["comment"] for r in tune["rounds"] if r.get("comment"))]


def summary(tune: dict[str, Any]) -> dict[str, Any]:
    """What the Tune window shows."""
    return {"tune": tune["id"], "profile": tune["profile"], "status": tune["status"], "stalled": stalled(tune),
            "picked_up": not waiting_for_pickup(tune), "source": tune["source"]["text"], "sentences": sentences(tune["source"]["text"]),
            "target": tune["target"], "how": tune["how"],
            "descriptions": tune["descriptions"], "rounds": tune["rounds"], "base": base(tune) if tune["target"] else None,
            "final": tune["final"], "tuned": tuned_text(tune), "answered": answered(tune),
            "window": tune.get("window")}


def sealed_for(profile: str) -> list[dict[str, Any]]:
    """A voice's confirmed tunes, ranked for output: most rounds first, then newest."""
    folder = profiles._dir(profile) / "tunes"
    found_ = [json.loads(p.read_text()) for p in folder.glob("*.json")] if folder.is_dir() else []
    found_ = [t for t in found_ if t.get("status") == SEALED]
    return sorted(found_, key=lambda t: (-answered(t), -t["sealed"]))


def all_for(profile: str) -> list[dict[str, Any]]:
    """Every tune in a voice, open or confirmed, newest first (for the local trace)."""
    open_dir = mo_home() / "tunes"
    open_ = [json.loads(p.read_text()) for p in open_dir.glob("*.json")] if open_dir.is_dir() else []
    sealed = sealed_for(profile)
    return sorted([t for t in open_ if t["profile"] == profile] + sealed, key=lambda t: -t["started"])


def delete(profile: str, ids: Any) -> list[str]:
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise ValueError("Pick the tunes to delete")
    gone = []
    for tune_id in ids:
        path = profiles._dir(profile) / "tunes" / f"{tune_id}.json"
        if _ID_RE.match(tune_id) and path.exists():
            path.unlink()
            gone.append(tune_id)
    return gone


def forget_profile(name: str) -> int:
    """After a profile is deleted, drop its open tunes too (confirmed ones went with the profile)."""
    folder = mo_home() / "tunes"
    gone = 0
    for path in folder.glob("*.json") if folder.is_dir() else []:
        if json.loads(path.read_text()).get("profile") == name:
            path.unlink()
            gone += 1
    return gone


def expire_open(now: float | None = None) -> list[str]:
    folder = mo_home() / "tunes"
    gone = []
    for path in folder.glob("*.json") if folder.is_dir() else []:
        tune = json.loads(path.read_text())
        if (now or time.time()) - tune["started"] > OPEN_EXPIRES:
            path.unlink()
            gone.append(tune["id"])
    return gone


def last_output(chat: str | None) -> dict[str, Any] | None:
    """The chat's most recent finished MO output, if any."""
    from mo import runs  # noqa: PLC0415 (runs imports tunes)
    if not chat:
        return None
    candidates = []
    for path in profiles._root().glob("*/runs/*.json") if profiles._root().is_dir() else []:
        run = json.loads(path.read_text())
        if run.get("chat") == chat and runs.done(run):
            candidates.append(run)
    return max(candidates, key=lambda r: r["started"], default=None)
