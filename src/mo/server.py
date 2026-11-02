"""MO's MCP server for ChatGPT, plus the MO box's direct line and the local trace (DESIGN §8–9).

ChatGPT's tools only ever request an MO box (or, later, hand over generated content). Each box
receives a per-box key in the tool result's hidden `_meta` and sends the HUMAN USER's input
straight to MO, signed with it (`mo.direct`). ChatGPT has no tool that records input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from mo import boxes, chats, direct, events, profiles, runs, tunes
from mo.events import CHATGPT, MO

BOX_MIME = "text/html;profile=mcp-app"
LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]")
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"}
HERE = Path(__file__).parent


def box_uri(public_url: str) -> str:
    """ChatGPT caches the window by URI. Its allowlist holds MO's (changing) address, and its code
    changes as MO does, so the URI carries a tag of both: either change means a fresh window."""
    tag = hashlib.sha256(public_url.encode() + (HERE / "box.html").read_bytes()).hexdigest()[:8]
    return f"ui://mo/box-{tag}.html"


def chat_of(ctx: Context | None) -> str | None:
    """The chat a call came from: `openai/session`, which ChatGPT's app (not the model) attaches to
    every tool call. None if absent (e.g. tests, other hosts)."""
    try:
        meta = ctx.request_context.meta if ctx is not None else None
    except ValueError:  # called outside a request (e.g. tests)
        meta = None
    chat = meta.get("openai/session") if isinstance(meta, dict) else None
    return chat if isinstance(chat, str) and chat else None


def create_server(public_url: str) -> MCPServer:
    """`public_url` is the origin the MO box calls directly, e.g. https://abc.trycloudflare.com."""
    server = MCPServer("MO", title="Modus Operandi", instructions=(
        "When the user writes '@MO' followed by a request, answer it through MO: write your full answer, call "
        "mo_output with it (that opens the MO window), and follow MO's replies exactly. '@MO help' opens MO's help window; plain '@MO', "
        "'@MO config', '@MO profile', and '@MO seed' open MO's config window; '@MO tune' opens MO's tune window. "
        "Only clicks in an MO window count; never choose a voice, a profile, or a variant yourself."))
    uri = box_uri(public_url)
    csp = {"connectDomains": [public_url], "resourceDomains": []}

    @server.resource(uri, name="mo-box", mime_type=BOX_MIME,
                     meta={"ui": {"csp": csp, "prefersBorder": True},
                           "openai/widgetCSP": {"connect_domains": [public_url], "resource_domains": []}})
    def mo_box() -> str:
        return (HERE / "box.html").read_text()

    def show_box(tool: str, kind: str, text: str, ctx: Context | None, profile: str | None = None,
                 chat: str | None = None, snapshot: Any = None, **view: str) -> CallToolResult:
        """`snapshot`, if given, is called with the new window's id and returns what the window shows
        first (so the snapshot can already know it is the newest window)."""
        # A box knows its chat (from ChatGPT's app); it reads that chat's voice when it needs it.
        chat = chat or chat_of(ctx)
        box, key = boxes.open_box(kind, chat=chat, **view)
        events.record(CHATGPT, "tool_call", tool=tool, box=box["id"], chat=chat,
                      **({"profile": profile} if profile else {}))
        snapshot = snapshot(box["id"]) if snapshot else None
        return CallToolResult(
            content=[TextContent(type="text", text=text)],
            structured_content={"box": box["id"], "view": kind, **view},
            meta={"mo/key": key, "mo/endpoint": public_url, "mo/chat": chat,
                  # what the window shows first, so it draws instantly (hidden from the model)
                  **({"mo/snapshot": snapshot} if snapshot else {})},
        )

    box_meta = {"ui": {"resourceUri": uri}, "openai/outputTemplate": uri}
    # Honest hints for ChatGPT's approval review: windows and "what's next?" only read; drafting steps
    # never touch the user's profile (only the user's confirm click in an MO window does that).
    READ = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    DRAFT = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)
    config_text = "Showing the MO config window. The user does everything there by clicking and typing."

    # Three windows: Help, Config (Profiles · Seeds), Output. These tools only open a window;
    # ChatGPT never creates, deletes, or picks profiles or voices, or passes along seeds.

    @server.tool(title="MO help", meta=box_meta, annotations=READ)
    def mo_help(ctx: Context) -> CallToolResult:
        """Use when the user says '@MO help'. Shows MO's help window."""
        return show_box("mo_help", "help", "Showing MO's help window.", ctx)

    @server.tool(title="MO config", meta=box_meta, annotations=READ)
    def mo_config(ctx: Context) -> CallToolResult:
        """Use when the user types '@MO' with nothing after it, '@MO config', or '@MO profile(s)', or wants
        to see, create, or delete MO profiles or pick the voice for this chat. Shows MO's config window on
        its Profiles tab; the user does everything there. (Anything else after '@MO' is a request for output.)"""
        return show_box("mo_config", "config", config_text, ctx, tab="profiles")

    @server.tool(title="MO seed", meta=box_meta, annotations=READ)
    def mo_seed(ctx: Context) -> CallToolResult:
        """Use when the user says '@MO seed' or wants to give MO a perfect writing example. Shows MO's
        config window on its Seeds tab; the user pastes the example there. Never paste, summarize, or pass
        along the example yourself."""
        return show_box("mo_seed", "config", config_text, ctx, tab="seeds")

    # Output: `@MO` + anything. ChatGPT only hands over content; MO keeps the books.

    def refuse(reason: str, **where: Any) -> ToolError:
        events.record(MO, "refused", reason=reason, **where)
        return ToolError(reason)

    def find_run(run: str, tool: str, ctx: Context) -> dict[str, Any]:
        try:
            found = runs.find(run)
        except ValueError as exc:
            raise refuse(str(exc), tool=tool) from exc
        chat = chat_of(ctx)
        if found.get("chat") and chat and found["chat"] != chat:
            raise refuse("That MO run belongs to another chat.", tool=tool, run=found["id"])
        return found

    @server.tool(title="MO output", meta=box_meta, annotations=DRAFT)
    def mo_output(initial: str, request: str, ctx: Context) -> CallToolResult:
        """Use when the user writes '@MO' followed by any request (explain, summarize, analyze, write…),
        but not '@MO help', '@MO config', '@MO profile', or '@MO seed'. First write your full, normal
        answer to the request, then call this with it as `initial` and a one-line description of the
        request as `request`. This opens the MO window, which updates itself. MO replies with what to do
        next; follow it exactly."""
        chat = chat_of(ctx)
        for gone in tunes.expire_open():
            events.record(MO, "tune_expired", tune=gone, reason="not confirmed within 24 h")
        for gone in runs.expire_waiting():
            events.record(MO, "run_expired", run=gone, reason="no voice picked within 24 h")
        voice = chats.voice(chat)
        try:
            run = runs.start(voice, initial, request, chat)
        except ValueError as exc:
            raise refuse(str(exc), tool="mo_output", chat=chat) from exc
        events.record(CHATGPT, "output_started", run=run["id"], words=len(run["initial"].split()), chat=chat,
                      **({"profile": voice, "passes": len(run["batches"])} if voice else {"waiting_for": "voice"}))
        if voice:
            text = runs.next_step(run)
        else:
            text = ("This chat has no MO voice yet. The MO window is asking the user to pick one. Stop now and "
                    "wait: the window posts a message when the voice is set.")
        return show_box("mo_output", "output", text, ctx, profile=voice, chat=chat, run=run["id"])

    @server.tool(title="MO output continue", annotations=READ)
    def mo_output_continue(run: str, ctx: Context) -> str:
        """Use when the user (through an MO window, e.g. "Continue · continue MO run …") asks you to continue an
        MO run. Read-only: returns what to do next; follow it exactly."""
        found = find_run(run, "mo_output_continue", ctx)
        if not runs.ready(found):
            raise refuse("This run is still waiting for the user to pick the chat's voice in the MO window.",
                         tool="mo_output_continue", run=found["id"])
        events.record(CHATGPT, "output_continued", profile=found["profile"], run=found["id"], chat=chat_of(ctx))
        return runs.next_step(found)

    @server.tool(title="MO output pass", annotations=DRAFT)
    def mo_output_pass(run: str, pass_number: int, ctx: Context, version: str | None = None,
                       no_change_reason: str | None = None) -> str:
        """One MO pass: send the full rewritten text as `version`, or a one-line `no_change_reason` if the
        current version already reads like the examples. Only call this as MO's instructions say. Drafts only: nothing changes the user's profile until they confirm in the MO window."""
        found = find_run(run, "mo_output_pass", ctx)
        try:
            entry = runs.submit(found, pass_number, version, no_change_reason)
        except ValueError as exc:
            raise refuse(str(exc), tool="mo_output_pass", run=found["id"], profile=found["profile"]) from exc
        events.record(CHATGPT, "output_pass", profile=found["profile"], run=found["id"], pass_number=entry["pass"],
                      changed=entry["changed"], no_change="no_change" in entry, chat=chat_of(ctx))
        return runs.next_step(found)

    # Tune: `@MO tune`, or "Tune voice profile" in an Output window. The whole UI is the MO window;
    # ChatGPT only writes the A/B/C variants.

    def live_window(tune: dict[str, Any]):
        """For show_box: make the new window the tune's live one, then snapshot it (so it knows it's live)."""
        def snapshot(box_id: str) -> dict[str, Any]:
            tunes.set_window(tune, box_id)
            return tunes.summary(tune)
        return snapshot

    def find_tune(tune: str, tool: str, ctx: Context) -> dict[str, Any]:
        try:
            found = tunes.find(tune)
        except ValueError as exc:
            raise refuse(str(exc), tool=tool) from exc
        chat = chat_of(ctx)
        if found.get("chat") and chat and found["chat"] != chat:
            raise refuse("That MO tune belongs to another chat.", tool=tool, tune=found["id"])
        return found

    @server.tool(title="MO tune", meta=box_meta, annotations=DRAFT)
    def mo_tune(ctx: Context) -> CallToolResult:
        """Use when the user says '@MO tune'. Opens MO's tune window on this chat's last MO output (or asks
        the user to paste text). The user does everything there; then follow MO's messages."""
        chat = chat_of(ctx)
        for gone in tunes.expire_open():
            events.record(MO, "tune_expired", tune=gone, reason="not confirmed within 24 h")
        unfinished = tunes.open_for_chat(chat)
        if unfinished:  # one tune at a time per chat: reopening resumes it
            events.record(MO, "tune_resumed", profile=unfinished["profile"], tune=unfinished["id"], chat=chat)
            result = show_box("mo_tune", "tune", "Showing MO's tune window, resuming the unfinished tune. Wait for "
                              "the window to post a message.", ctx, profile=unfinished["profile"], chat=chat,
                              snapshot=live_window(unfinished), tune=unfinished["id"])
            return result
        last = tunes.last_output(chat)
        if last is None:
            return show_box("mo_tune", "tune", "Showing MO's tune window. The user pastes the text to tune there.",
                            ctx, chat=chat, tune=None)
        tune = tunes.start(last["profile"], chat, runs.current(last), run=last["id"])
        events.record(MO, "tune_started", profile=tune["profile"], tune=tune["id"], chat=chat, from_run=last["id"])
        result = show_box("mo_tune", "tune", "Showing MO's tune window on this chat's last MO output. Wait for the "
                          "window to post a message.", ctx, profile=tune["profile"], chat=chat,
                          snapshot=live_window(tune), tune=tune["id"])
        return result

    @server.tool(title="MO tune work", annotations=READ)
    def mo_tune_work(tune: str, ctx: Context) -> str:
        """Use when the user (through an MO window, e.g. "Picked B · continue MO tune …") asks you to continue
        an MO tune. Read-only: returns what to do next; follow it exactly."""
        found = find_tune(tune, "mo_tune_work", ctx)
        events.record(CHATGPT, "tune_work", profile=found["profile"], tune=found["id"], status=found["status"],
                      chat=chat_of(ctx))
        return tunes.instructions(found)

    @server.tool(title="MO tune variants", meta=box_meta, annotations=DRAFT)
    def mo_tune_variants(tune: str, round_number: int, a: str, b: str, c: str, ctx: Context) -> CallToolResult:
        """Send this round's three variants for the user to choose from. Only call this as MO's instructions say. Drafts only: nothing changes the user's profile until they confirm in the MO window."""
        found = find_tune(tune, "mo_tune_variants", ctx)
        try:
            tunes.variants(found, round_number, a, b, c)
        except ValueError as exc:
            raise refuse(str(exc), tool="mo_tune_variants", tune=found["id"], profile=found["profile"]) from exc
        events.record(CHATGPT, "tune_variants", profile=found["profile"], tune=found["id"], round=round_number,
                      chat=chat_of(ctx))
        # This round's window is drawn right here, at the bottom of the chat, already filled in.
        result = show_box("mo_tune_variants", "tune", "Recorded: the MO window below shows A, B, C. Reply with "
                          "nothing, or at most one word, so the chat stays short.", ctx, profile=found["profile"],
                          chat=found.get("chat"), snapshot=live_window(found), tune=found["id"])
        return result

    @server.custom_route("/box/{box_id}/event", methods=["POST", "OPTIONS"], include_in_schema=False)
    async def box_event(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=CORS)
        box_id = request.path_params["box_id"]
        try:
            body = await request.json()
        except json.JSONDecodeError:
            body = {}
        box = boxes.verify(box_id, body.get("key"))
        if box is None:
            events.record(MO, "refused", reason="bad box key", box=box_id, action=body.get("action"))
            return JSONResponse({"error": "not signed by this box"}, status_code=403, headers=CORS)
        status, reply = direct.handle(box, body)
        return JSONResponse(reply, status_code=status, headers=CORS)

    @server.custom_route("/trace", methods=["GET"], include_in_schema=False)
    async def trace_page(request: Request) -> Response:
        if not _local(request):
            return Response(status_code=404)
        return HTMLResponse((HERE / "trace.html").read_text())

    @server.custom_route("/trace/events", methods=["GET"], include_in_schema=False)
    async def trace_events(request: Request) -> Response:
        if not _local(request):
            return Response(status_code=404)
        q = request.query_params
        found = events.read(actor=q.get("actor"), type=q.get("type"), box=q.get("box"))
        if (profile := q.get("profile")) is not None:
            # profile=none selects events that belong to no profile
            found = [e for e in found if e.get("profile") == (None if profile == "none" else profile)]
        return JSONResponse(found)

    @server.custom_route("/trace/profiles", methods=["GET"], include_in_schema=False)
    async def trace_profiles(request: Request) -> Response:
        if not _local(request):
            return Response(status_code=404)
        return JSONResponse(profiles.list_all())

    @server.custom_route("/trace/profiles/{name}", methods=["GET"], include_in_schema=False)
    async def trace_profile(request: Request) -> Response:
        """One profile's store, full text included (this computer only)."""
        if not _local(request):
            return Response(status_code=404)
        try:
            name = request.path_params["name"]
            return JSONResponse({**profiles.summary(name), "seeds": profiles.seeds(name), "runs": runs.list_for(name),
                                 "tunes": tunes.all_for(name)})
        except (ValueError, FileNotFoundError):
            return JSONResponse({"error": "no such profile"}, status_code=404)

    return server


def _local(request: Request) -> bool:
    """The trace holds the human user's text: this computer only, never through the tunnel."""
    host = request.headers.get("host", "")
    if host.startswith("["):
        return host.startswith("[::1]")
    return host.rsplit(":", 1)[0] in LOCAL_HOSTS


def secret() -> str:
    """A stable secret for the public MCP path, standing in for sign-in during development."""
    if env := os.environ.get("MO_SECRET"):
        return env
    path = events.mo_home() / "secret"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_urlsafe(24) + "\n")
        path.chmod(0o600)
    return path.read_text().strip()


def serve(public_host: str, port: int, bind: str = "127.0.0.1", show_link: bool = True) -> None:
    """Serve MO at https://<public_host>/mcp/<secret>. Locally (make run) the link is printed; hosted
    (make deploy) it isn't, so the secret never lands in the host's logs (`make link` shows it)."""
    public_url = f"https://{public_host}"
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*", public_host]
    origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*", public_url]
    path = f"/mcp/{secret()}"
    if show_link:
        print(f"\nMO is reachable at:  {public_url}{path}   ← for ChatGPT (keep private)\n"
              f"Trace:               http://127.0.0.1:{port}/trace   ← for you (this computer only)\n", flush=True)
    else:
        print(f"MO is serving {public_url} (link: make link · trace: make trace)", flush=True)
    create_server(public_url).run(
        transport="streamable-http", host=bind, port=port, streamable_http_path=path,
        transport_security=TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins),
    )


def main() -> None:
    """Hosted entry point (`mo-server`); `make run` uses `mo.dev` instead."""
    parser = argparse.ArgumentParser(description="Run MO's server.")
    parser.add_argument("--public-host", required=True, help="e.g. mo-yourname.fly.dev")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--bind", default="127.0.0.1", help="0.0.0.0 inside a container")
    parser.add_argument("--hide-link", action="store_true", help="don't print the secret link (hosted)")
    args = parser.parse_args()
    serve(args.public_host.removeprefix("https://").rstrip("/"), args.port, args.bind, not args.hide_link)
