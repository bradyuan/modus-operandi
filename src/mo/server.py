"""MO's MCP server: a harness that supplies state to the host AI and checks its output.

MO makes no LLM calls (AGENTS.md, core design item 1). The host writes; MO hands it
kits, checks drafts, records the user's picks and edits, and manages profiles.
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

from mo import checks, kits, style
from mo.store import (
    REGISTERS,
    PendingSamples,
    Profile,
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
    """Surface validation errors to the host: the SDK hides plain exceptions' text."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


server = MCPServer(
    "MO",
    title="Modus Operandi",
    instructions=(
        "MO keeps the user's persistent profile of how they write and read. Call mo_write before "
        "writing anything for the user, follow the kit's steps, and call mo_check before showing a "
        "draft. Use mo_profile to list, create, or switch profiles, save the user's own writing "
        "samples, or run diagnostics. MO never writes text itself; you do, using the kit."
    ),
)


@server.tool(
    title="Write in the user's voice",
    description=(
        "Use whenever the user wants something written (essay, cover letter, email, article, notes), "
        "including casual requests like 'write an essay about X @MO'. Call this BEFORE drafting. "
        "Returns a kit: the user's voice rules, exemplars of their own writing, and steps to follow. "
        "Pass the user's own words for this piece as `seed` (verbatim), facts about them (resume, notes) "
        "as `facts`, and the job description or assignment as `requirements`. Omit `profile` to use "
        "the active one."
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
    log_call("mo_check", {"profile": p.name, "register": register, "status": result["status"],
                          "flags": [f["type"] for f in result["flags"]]})
    return result


@server.tool(
    title="Record feedback",
    description=(
        "Call when the user picks between versions ('variations': pass chosen, rejected, passed_over, "
        "and what was varied) or edits a draft ('edit': pass before and after). Use 'system' for "
        "failed checks, which are not preferences. Store only the relevant span, not whole documents."
    ),
)
@user_errors
def mo_record(
    kind: Literal["variations", "edit", "rating", "system"],
    data: dict[str, Any],
    task: Literal["writing", "reading"] = "writing",
    register: Register | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    p = resolve_profile(profile)
    case = {"type": kind, "task": task, "register": validate_register(register) if register else None, "data": data}
    case_id = p.append_case(case)
    log_call("mo_record", {"profile": p.name, "kind": kind, "task": task, "diagnostic": bool(data.get("diagnostic"))})
    return {"recorded": case_id, "profile": p.name}


@server.tool(
    title="Manage the user's profile",
    description=(
        "Use for '@MO profile' and anything about the user's MO profiles: list them ('list'), create one "
        "('create', name), switch ('use', name), or see what's in one ('show'). To save the user's OWN "
        "writing as a sample, call 'add_sample' (register, text): it saves nothing yet and returns a code; "
        "ask the user the returned question, and only after they say yes call 'confirm' with the code. "
        "Never add text you wrote, and never confirm for the user. Remove a sample with 'remove_sample' "
        "(register, sample). To calibrate, call 'diagnostic' (kind 'writing' or 'reading'; for reading, "
        "pass the blog or paper as `source`) and follow its steps."
    ),
)
@user_errors
def mo_profile(
    action: Literal["list", "create", "use", "show", "add_sample", "confirm", "remove_sample", "diagnostic"],
    name: str | None = None,
    register: Register | None = None,
    text: str | None = None,
    sample: str | None = None,
    code: str | None = None,
    kind: Literal["writing", "reading"] = "writing",
    round: int = 1,
    source: str | None = None,
) -> dict[str, Any]:
    result = _profile_action(action, name, register, text, sample, code, kind, round, source)
    log_call("mo_profile", {"action": action, "profile": result.get("profile")})
    return result


def _profile_action(action, name, register, text, sample, code, kind, round_number, source) -> dict[str, Any]:
    if action == "list":
        return {"profiles": list_profiles(), "active": active_profile(), "profile": active_profile()}

    if action == "create":
        p = Profile(_require(name, "name"))
        if p.exists:
            raise ValueError(f"Profile {p.name!r} already exists; use action 'use' to switch to it")
        p.root.mkdir(parents=True)
        set_active_profile(p.name)
        return {"profile": p.name, "active": True,
                "next": "Seed it: paste writing samples the user wrote (add_sample), or run a diagnostic."}

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
        words = len(style.words(body))
        pending_code = PendingSamples().add(p.name, reg, sample or f"{reg}-sample", body)
        return {
            "status": "needs_confirmation",
            "profile": p.name,
            "code": pending_code,
            "preview": body[:200] + ("…" if len(body) > 200 else ""),
            "ask_user": f"Save this {words}-word {reg.replace('_', ' ')} as your own writing in profile "
                        f"'{p.name}'? Only save text you wrote yourself.",
            "steps": ["Ask the user `ask_user` word for word and wait for a clear yes.",
                      "Only then call mo_profile(action='confirm', code=<code>). Never confirm for the user."],
        }

    if action == "confirm":
        item = PendingSamples().pop(_require(code, "code"))
        if item is None:
            raise ValueError("Unknown or expired code; call add_sample again")
        p = Profile(item["profile"])
        saved = p.add_exemplar(item["register"], item["name"], item["text"])
        return {"profile": p.name, "saved": saved, "register": item["register"]}

    if action == "remove_sample":
        p = resolve_profile(name)
        reg = validate_register(_require(register, "register"))
        if not p.remove_exemplar(reg, _require(sample, "sample")):
            raise ValueError(f"No {reg} sample named {sample!r} in profile {p.name!r}")
        return {"profile": p.name, "removed": sample, "register": reg}

    if action == "diagnostic":
        if round_number < 1:
            raise ValueError("round starts at 1")
        return kits.diagnostic_kit(resolve_profile(name), kind, round_number, source)

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
        print(f"\nMO is reachable at: https://{host}{path}\nKeep this link private: it gives access to your profile.\n", flush=True)
    security = TransportSecuritySettings(allowed_hosts=local_hosts, allowed_origins=local_origins)
    server.run(transport="streamable-http", port=args.port, streamable_http_path=path, transport_security=security)


if __name__ == "__main__":
    main()
