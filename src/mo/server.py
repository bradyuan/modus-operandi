"""MO's MCP server: a harness that supplies state to the host AI and checks its output.

MO makes no LLM calls (AGENTS.md, core design item 1). The host writes; MO hands it
kits, checks drafts, runs tune rounds, records the user's feedback, and manages profiles.
"""

from __future__ import annotations

import argparse
import functools
import os
import secrets
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

from mo import checks, kits, style, tune
from mo.store import (
    REGISTERS,
    Profile,
    RecentDrafts,
    active_profile,
    list_profiles,
    log_call,
    mo_home,
    resolve_profile,
    set_active_profile,
    validate_register,
)

Register = Literal["email", "essay", "cover_letter", "article", "notes", "other"]
assert set(REGISTERS) == set(Register.__args__)  # keep the tool schema in sync with storage


def user_errors(fn):
    """Surface validation errors to the host (the SDK hides plain exceptions' text) and log them."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as exc:
            log_call(fn.__name__, {"action": kwargs.get("action"), "error": str(exc)})
            raise ToolError(str(exc)) from exc

    return wrapper


server = MCPServer(
    "MO",
    title="Modus Operandi",
    instructions=(
        "MO keeps the user's persistent profile of how they write and read. Call mo_write before "
        "writing anything for the user, follow the kit's steps, and call mo_check before showing a "
        "draft. When the user wants changes or variations, use mo_tune and follow its replies exactly. "
        "Use mo_profile to list, create, or switch profiles and to save the user's own writing. MO "
        "never writes text itself; you do, using the kit."
    ),
)


@server.tool(
    title="Write in the user's voice",
    description=(
        "Use whenever the user wants something written (essay, cover letter, email, article, notes), "
        "including casual requests like 'write an essay about X @MO'. Call this BEFORE drafting. "
        "Returns a kit: the user's voice rules, exemplars of their own writing, and steps to follow. "
        "IMPORTANT: if the user gave ANY of their own words for this piece (notes, bullets, a rough line, "
        "why they want the job), pass them verbatim as `seed`. Facts about them (resume, notes) go in "
        "`facts`, and the job description or assignment in `requirements`. Omit `profile` to use the "
        "active one."
    ),
)
@user_errors
def mo_write(
    register: Register,
    seed: str | None = None,
    facts: str | None = None,
    requirements: str | None = None,
    keywords: list[str] | None = None,
    modifiers: list[str] | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    p = resolve_profile(profile)
    kit = kits.writing_kit(p, register, seed, facts, requirements, keywords, modifiers)
    log_call("mo_write", {"profile": p.name, "register": register, "seed_source": kit["seed_source"],
                          "exemplars": len(kit["exemplars"]), "rules": len(kit["rules"])})
    return kit


@server.tool(
    title="Check a draft",
    description=(
        "Call on every draft before showing it to the user. Runs deterministic checks: generic AI "
        "wording, phrases copied from the source text, numbers not in the facts, the user's checkable "
        "rules, keyword coverage, and voice metrics. If status is 'failed_checks', fix ONLY the items "
        "in `fix` (at most 2 tries), keep the version with the fewest flags, and show any remaining "
        "flags to the user rather than hiding them."
    ),
)
@user_errors
def mo_check(
    draft: str,
    register: Register,
    seed: str | None = None,
    facts: str | None = None,
    source_text: str | None = None,
    keywords: list[str] | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    p = resolve_profile(profile)
    exemplars, _ = kits.select_exemplars(p, validate_register(register))
    result = checks.run_checks(
        draft,
        rules=p.rules(),
        seed=seed,
        facts=facts,
        source_text=source_text,
        keywords=keywords,
        exemplars=exemplars,
    )
    RecentDrafts().remember(draft)
    log_call("mo_check", {"profile": p.name, "register": register, "status": result["status"],
                          "flags": [f["type"] for f in result["flags"]]})
    return result


@server.tool(
    title="Tune: variations until one fits",
    description=(
        "Use for '@MO tune', 'I don't like this', 'give me alternatives', or to calibrate the user's "
        "profile. action='start' with mode='draft' to fix part of a draft (pass that part as `target`), "
        "or mode='diagnostic' to calibrate (task 'writing', or 'reading' with the blog or paper as "
        "`source`). Then pass every user answer with action='answer', the session id, and outcome: "
        "'picked' (with chosen A/B/C), 'none_fit' if they reject all three, or 'skipped' if they want to "
        "move on. MO decides what happens next; follow its reply exactly."
    ),
)
@user_errors
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
    if action == "start":
        p = resolve_profile(profile)
        result = tune.start(p, task, mode, validate_register(register) if register else None, target, source)
    else:
        result = tune.answer(_require(session, "session"), _require(outcome, "outcome"), chosen, note)
    log_call("mo_tune", {"action": action, "profile": result["profile"], "mode": mode if action == "start" else None,
                         "outcome": outcome, "status": result["status"]})
    return result


@server.tool(
    title="Record feedback",
    description=(
        "Call when the user edits a draft themselves ('edit': pass the changed span before and after) "
        "or rates something ('rating'). Use 'system' for failed checks, which are not preferences. "
        "Picks between variations are recorded by mo_tune, not here. Store only the relevant span."
    ),
)
@user_errors
def mo_record(
    kind: Literal["edit", "rating", "system"],
    data: dict[str, Any],
    task: Literal["writing", "reading"] = "writing",
    register: Register | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    p = resolve_profile(profile)
    case = {"type": kind, "task": task, "register": validate_register(register) if register else None, "data": data}
    case_id = p.append_case(case)
    log_call("mo_record", {"profile": p.name, "kind": kind, "task": task})
    return {"recorded": case_id, "profile": p.name}


@server.tool(
    title="Manage the user's profile",
    description=(
        "Use for '@MO profile' and anything about the user's MO profiles: list them ('list'), create one "
        "('create', name), switch ('use', name), or see what's in one ('show'). When the user says to use "
        "or save text as a sample of their writing, call 'add_sample' (register, text) right away: their "
        "request is the confirmation. Never add text you wrote. Remove a sample with 'remove_sample' "
        "(register, sample)."
    ),
)
@user_errors
def mo_profile(
    action: Literal["list", "create", "use", "show", "add_sample", "remove_sample"],
    name: str | None = None,
    register: Register | None = None,
    text: str | None = None,
    sample: str | None = None,
) -> dict[str, Any]:
    result = _profile_action(action, name, register, text, sample)
    log_call("mo_profile", {"action": action, "profile": result.get("profile")})
    return result


def _profile_action(action, name, register, text, sample) -> dict[str, Any]:
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
        return {"profile": p.name, "active": p.name == active_profile(), "samples": samples,
                "rules": len(data["rules"]), "candidates": len(data["candidates"]), "cases": len(p.cases())}

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

    raise ValueError(f"Unknown action {action!r}")


def _require(value: Any, field: str) -> Any:
    if value in (None, ""):
        raise ValueError(f"'{field}' is required for this action")
    return value


def _secret() -> str:
    """A stable secret for the public URL path, standing in for sign-in during development."""
    if env := os.environ.get("MO_SECRET"):
        return env
    path = mo_home() / "secret"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_urlsafe(24) + "\n")
        path.chmod(0o600)
    return path.read_text().strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MO's MCP server.")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--public-host", help="tunnel hostname to accept, e.g. abc.trycloudflare.com; "
                                              "serves at a secret path instead of /mcp")
    args = parser.parse_args()

    if args.transport == "stdio":
        server.run()
        return

    local_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    local_origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    path = "/mcp"
    if args.public_host:
        host = args.public_host.removeprefix("https://").rstrip("/")
        local_hosts.append(host)
        local_origins.append(f"https://{host}")
        path = f"/mcp/{_secret()}"
        print(f"\nMO is reachable at: https://{host}{path}\nKeep this link private: it gives access to your profile.\n",
              flush=True)
    security = TransportSecuritySettings(allowed_hosts=local_hosts, allowed_origins=local_origins)
    server.run(transport="streamable-http", port=args.port, streamable_http_path=path, transport_security=security)


if __name__ == "__main__":
    main()
