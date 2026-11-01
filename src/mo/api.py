"""MO's core API: the tools the host AI calls, independent of any protocol.

Adapters (``mo.server`` for MCP today, a GPT integration later) only expose these
functions. Each function's signature is its input schema, and its docstring is the
description the host AI reads to decide when to call it. Errors are ``ValueError``
with a message meant for the host. MO makes no LLM calls (AGENTS.md, item 1).
"""

from __future__ import annotations

import functools
import inspect
from typing import Any, Literal

from mo import checks, kits, style, tune
from mo.store import (
    REGISTERS,
    Profile,
    RecentDrafts,
    active_profile,
    list_profiles,
    log_call,
    resolve_profile,
    set_active_profile,
    trace_call,
    tracing,
    validate_register,
)

Register = Literal["email", "essay", "cover_letter", "article", "notes", "other"]
assert set(REGISTERS) == set(Register.__args__)  # keep the schema in sync with storage

TITLES = {
    "mo_read": "Explain something the way the user understands",
    "mo_write": "Write in the user's voice",
    "mo_check": "Check a draft",
    "mo_tune": "Tune: variations until one fits",
    "mo_record": "Record feedback",
    "mo_profile": "Manage the user's profile",
}
INSTRUCTIONS = (
    "MO keeps the user's persistent profile of how they write and read. Call mo_read before explaining "
    "anything the user wants to understand and mo_write before writing anything for them, follow the kit's steps, and call mo_check before showing a draft. When the "
    "user wants changes or variations, use mo_tune and follow its replies exactly. Use mo_profile to list, "
    "create, or switch profiles, to save the user's own writing, and to save rules the user approves. MO never writes text itself; you do, "
    "using the kit."
)


def logged(fn):
    """Log failures too, so problems show up in calls.jsonl (successes log their own details).
    In dev (MO_TRACE=1), also trace every call in full for the trace page."""
    signature = inspect.signature(fn)

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        try:
            result = fn(*args, **kwargs)
        except ValueError as exc:
            log_call(fn.__name__, {"action": kwargs.get("action"), "error": str(exc)})
            if tracing():
                trace_call(fn.__name__, bound.arguments, error=str(exc))
            raise
        if tracing():
            trace_call(fn.__name__, bound.arguments, result)
        return result

    return wrapper


@logged
def mo_read(
    source: str | None = None,
    question: str | None = None,
    modifiers: list[str] | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """Use whenever the user wants to understand something: '@MO read', 'explain this', 'ELI5', a blog
    post, paper, article, or topic. Call this BEFORE explaining. Returns a kit: the user's reading rules
    and steps to follow. Pass the link, title, or topic as `source` and what they want to know as
    `question`. Omit `profile` to use the active one."""
    p = resolve_profile(profile)
    kit = kits.reading_kit(p, source, question, modifiers)
    log_call("mo_read", {"profile": p.name, "rules": len(kit["rules"])})
    return kit


@logged
def mo_write(
    register: Register,
    seed: str | None = None,
    facts: str | None = None,
    requirements: str | None = None,
    keywords: list[str] | None = None,
    modifiers: list[str] | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """Use whenever the user wants something written (essay, cover letter, email, article, notes),
    including casual requests like 'write an essay about X @MO'. Call this BEFORE drafting. Returns a
    kit: the user's voice rules, exemplars of their own writing, and steps to follow. IMPORTANT: if the
    user gave ANY of their own words for this piece (notes, bullets, a rough line, why they want the
    job), pass them verbatim as `seed`. Facts about them (resume, notes) go in `facts`, and the job
    description or assignment in `requirements`. Omit `profile` to use the active one."""
    p = resolve_profile(profile)
    kit = kits.writing_kit(p, register, seed, facts, requirements, keywords, modifiers)
    log_call("mo_write", {"profile": p.name, "register": register, "seed_source": kit["seed_source"],
                          "exemplars": len(kit["exemplars"]), "rules": len(kit["rules"])})
    return kit


@logged
def mo_check(
    draft: str,
    register: Register,
    seed: str | None = None,
    facts: str | None = None,
    source_text: str | None = None,
    keywords: list[str] | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """Call on every draft before showing it to the user. Runs deterministic checks: generic AI
    wording, phrases copied from the source text, numbers not in the facts, habits the author never
    uses (compared with their own samples), the user's checkable rules, and keyword coverage. If status
    is 'failed_checks', fix ONLY the items in `fix` (at most 2 tries), keep the version with the fewest
    flags, and show any remaining flags to the user rather than hiding them."""
    p = resolve_profile(profile)
    exemplars, _ = kits.select_exemplars(p, validate_register(register))
    result = checks.run_checks(draft, rules=p.rules(), seed=seed, facts=facts, source_text=source_text,
                               keywords=keywords, exemplars=exemplars)
    RecentDrafts().remember(draft)
    log_call("mo_check", {"profile": p.name, "register": register, "status": result["status"],
                          "flags": [f["type"] for f in result["flags"]], "metrics": result["metrics"]})
    return result


@logged
def mo_tune(
    action: Literal["start", "answer"],
    session: str | None = None,
    outcome: Literal["picked", "none_fit", "skipped"] | None = None,
    chosen: Literal["A", "B", "C"] | None = None,
    note: str | None = None,
    mode: Literal["draft", "diagnostic"] = "draft",
    task: Literal["writing", "reading"] = "writing",
    register: Register | None = None,
    target: str | None = None,
    source: str | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """Use for '@MO tune', 'I don't like this', 'give me alternatives', or to calibrate the user's
    profile. action='start' with mode='draft' to fix part of a draft (pass that part as `target`), or
    mode='diagnostic' to calibrate (task 'writing', or 'reading' with the blog or paper as `source`).
    Then pass every user answer with action='answer', the session id, and outcome: 'picked' (with chosen
    A/B/C), 'none_fit' if they reject all three, or 'skipped' if they want to move on. MO decides what
    happens next; follow its reply exactly."""
    if action == "start":
        p = resolve_profile(profile)
        result = tune.start(p, task, mode, validate_register(register) if register else None, target, source)
    else:
        result = tune.answer(_require(session, "session"), _require(outcome, "outcome"), chosen, note)
    log_call("mo_tune", {"action": action, "profile": result["profile"], "mode": mode if action == "start" else None,
                         "outcome": outcome, "status": result["status"]})
    return result


@logged
def mo_record(
    kind: Literal["edit", "rating", "system"],
    data: dict[str, Any],
    task: Literal["writing", "reading"] = "writing",
    register: Register | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """Call when the user edits a draft themselves ('edit': pass the changed span before and after) or
    rates something ('rating'). Use 'system' for failed checks, which are not preferences. Picks between
    variations are recorded by mo_tune, not here. Store only the relevant span."""
    p = resolve_profile(profile)
    case_id = p.append_case({"type": kind, "task": task,
                             "register": validate_register(register) if register else None, "data": data})
    log_call("mo_record", {"profile": p.name, "kind": kind, "task": task})
    return {"recorded": case_id, "profile": p.name}


@logged
def mo_profile(
    action: Literal["list", "create", "use", "show", "add_sample", "remove_sample",
                    "add_rule", "remove_rule"],
    name: str | None = None,
    register: Register | None = None,
    text: str | None = None,
    sample: str | None = None,
    task: Literal["reading", "writing", "both"] = "both",
) -> dict[str, Any]:
    """Use for '@MO profile' and anything about the user's MO profiles: list them ('list'), create one
    ('create', name), switch ('use', name), or see what's in one ('show'). When the user says to use or
    save text as a sample of their writing, call 'add_sample' (register, text) right away: their request
    is the confirmation. Never add text you wrote. Remove a sample with 'remove_sample' (register,
    sample). When the user states or approves a rule ('always use short sentences'), call 'add_rule'
    (text = the rule in a few words, task = reading, writing, or both); 'remove_rule' (text) drops one."""
    result = _profile_action(action, name, register, text, sample, task)
    log_call("mo_profile", {"action": action, "profile": result.get("profile")})
    return result


TOOLS = [mo_read, mo_write, mo_check, mo_tune, mo_record, mo_profile]


def host_guide() -> str:
    """Everything the host needs in one text: for hosts that take instructions separately from tools,
    like a Custom GPT's Instructions field."""
    tools = "\n\n".join(f"{fn.__name__}: {inspect.cleandoc(fn.__doc__)}" for fn in TOOLS)
    return f"{INSTRUCTIONS}\n\nWhen to call each MO action:\n\n{tools}"


def _profile_action(action, name, register, text, sample, task="both") -> dict[str, Any]:
    if action == "list":
        return {"profiles": list_profiles(), "active": active_profile(), "profile": active_profile()}

    if action == "create":
        p = Profile(_require(name, "name"))
        if p.exists:
            raise ValueError(f"Profile {p.name!r} already exists; use action 'use' to switch to it")
        p.root.mkdir(parents=True)
        set_active_profile(p.name)
        return {"profile": p.name, "active": True,
                "next": "Seed it: save writing the user wrote (add_sample), or calibrate with mo_tune "
                        "(mode='diagnostic')."}

    if action == "use":
        p = Profile(_require(name, "name"))
        if not p.exists:
            raise ValueError(f"No profile named {p.name!r}; existing: {', '.join(list_profiles()) or 'none'}")
        set_active_profile(p.name)
        return {"profile": p.name, "active": True}

    if action == "show":
        p = resolve_profile(name)
        samples = {
            r: [{"sample": e.name, "words": len(style.words(e.text)), "source": e.source} for e in p.exemplars(r)]
            for r in p.registers_with_exemplars()
        }
        data = p.load()
        rules = [{"rule": r["rule"], "task": r.get("scope", ["reading", "writing"])} for r in data["rules"]]
        return {"profile": p.name, "active": p.name == active_profile(), "samples": samples,
                "rules": rules, "candidates": len(data["candidates"]), "cases": len(p.cases())}

    if action == "add_sample":
        p = resolve_profile(name)
        reg = validate_register(_require(register, "register"))
        body = _require(text, "text").strip()
        if RecentDrafts().similarity(body) >= RecentDrafts.MATCH:
            raise ValueError(
                "Not saved: this closely matches a draft MO checked recently, so it looks AI-written. Only "
                "save writing the user wrote themselves. If they rewrote it, save their rewritten version."
            )
        saved = p.add_exemplar(reg, sample or f"{reg}-sample", body)
        return {"profile": p.name, "saved": saved, "register": reg, "words": len(style.words(body))}

    if action == "remove_sample":
        p = resolve_profile(name)
        reg = validate_register(_require(register, "register"))
        if not p.remove_exemplar(reg, _require(sample, "sample")):
            raise ValueError(f"No {reg} sample named {sample!r} in profile {p.name!r}")
        return {"profile": p.name, "removed": sample, "register": reg}

    if action == "add_rule":
        p = resolve_profile(name)
        scope = ["reading", "writing"] if task == "both" else [task]
        rule = p.add_rule(_require(text, "text").strip(), scope, [register] if register else None)
        return {"profile": p.name, "reinforced" if rule.get("reinforced") else "added": rule["rule"],
                "task": rule["scope"]}

    if action == "remove_rule":
        p = resolve_profile(name)
        if not p.remove_rule(_require(text, "text").strip()):
            raise ValueError(f"No rule {text!r} in profile {p.name!r}; see action 'show'")
        return {"profile": p.name, "removed": text}

    raise ValueError(f"Unknown action {action!r}")


def _require(value: Any, field: str) -> Any:
    if value in (None, ""):
        raise ValueError(f"'{field}' is required for this action")
    return value
