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

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from mo import boxes, direct, events, profiles
from mo.events import CHATGPT, MO

BOX_MIME = "text/html;profile=mcp-app"
LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]")
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"}
HERE = Path(__file__).parent


def box_uri(public_url: str) -> str:
    """ChatGPT caches the box by URI, and the box's allowlist includes MO's (changing) address,
    so the URI carries a tag of that address."""
    return f"ui://mo/box-{hashlib.sha256(public_url.encode()).hexdigest()[:8]}.html"


def create_server(public_url: str) -> MCPServer:
    """`public_url` is the origin the MO box calls directly, e.g. https://abc.trycloudflare.com."""
    server = MCPServer("MO", title="Modus Operandi",
                       instructions="MO shows its own box for every step. Only clicks in the MO box count.")
    uri = box_uri(public_url)
    csp = {"connectDomains": [public_url], "resourceDomains": []}

    @server.resource(uri, name="mo-box", mime_type=BOX_MIME,
                     meta={"ui": {"csp": csp, "prefersBorder": True},
                           "openai/widgetCSP": {"connect_domains": [public_url], "resource_domains": []}})
    def mo_box() -> str:
        return (HERE / "box.html").read_text()

    def show_box(tool: str, kind: str, label: str, text: str) -> CallToolResult:
        box, key = boxes.open_box(kind)
        events.record(CHATGPT, "tool_call", tool=tool, box=box["id"])
        return CallToolResult(
            content=[TextContent(type="text", text=text)],
            structured_content={"box": box["id"], "view": kind, "label": label},
            meta={"mo/key": key, "mo/endpoint": public_url},
        )

    box_meta = {"ui": {"resourceUri": uri}, "openai/outputTemplate": uri}

    @server.tool(title="MO profiles", meta=box_meta)
    def mo_profiles() -> CallToolResult:
        """Use when the user says '@MO profiles' or wants to see, create, or delete MO profiles. Shows
        the MO profiles box; the user does everything by clicking and typing in the box. You never
        create, delete, or choose profiles yourself."""
        return show_box("mo_profiles", "profiles", "MO · Profiles",
                        "Showing the MO profiles box. The user manages profiles in the box.")

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


def serve(public_host: str, port: int) -> None:
    public_url = f"https://{public_host}"
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*", public_host]
    origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*", public_url]
    path = f"/mcp/{secret()}"
    print(f"\nMO is reachable at:  {public_url}{path}   ← for ChatGPT (keep private)\n"
          f"Trace:               http://127.0.0.1:{port}/trace   ← for you (this computer only)\n", flush=True)
    create_server(public_url).run(
        transport="streamable-http", port=port, streamable_http_path=path,
        transport_security=TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MO's server (normally started by `make run`).")
    parser.add_argument("--public-host", required=True, help="e.g. abc.trycloudflare.com")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    serve(args.public_host.removeprefix("https://").rstrip("/"), args.port)
