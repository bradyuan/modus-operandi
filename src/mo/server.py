"""MCP adapter: exposes ``mo.api`` as MCP tools. No MO logic lives here."""

from __future__ import annotations

import argparse
import functools
import inspect
import os
import secrets
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from mo import api, trace
from mo.store import mo_home, read_trace

server = MCPServer("MO", title="Modus Operandi", instructions=api.INSTRUCTIONS)


def _as_tool_errors(fn):
    """The SDK hides plain exceptions' text; ToolError carries MO's message to the host."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


for _fn in api.TOOLS:
    server.tool(title=api.TITLES[_fn.__name__], description=inspect.cleandoc(_fn.__doc__))(_as_tool_errors(_fn))


LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]")


def _local(request: Request) -> bool:
    """The trace holds the user's full text: serve it to this computer only, never through the tunnel."""
    host = request.headers.get("host", "")
    return host.rsplit(":", 1)[0] in LOCAL_HOSTS if not host.startswith("[") else host.startswith("[::1]")


@server.custom_route("/trace", methods=["GET"], include_in_schema=False)
async def trace_page(request: Request) -> Response:
    if not _local(request):
        return Response(status_code=404)
    return HTMLResponse(Path(__file__).with_name("trace.html").read_text())


@server.custom_route("/trace.json", methods=["GET"], include_in_schema=False)
async def trace_data(request: Request) -> Response:
    if not _local(request):
        return Response(status_code=404)
    return JSONResponse(trace.runs(read_trace()))


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

    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    path = "/mcp"
    if args.public_host:
        host = args.public_host.removeprefix("https://").rstrip("/")
        hosts.append(host)
        origins.append(f"https://{host}")
        path = f"/mcp/{_secret()}"
        print(f"\nMO is reachable at: https://{host}{path}\nKeep this link private: it gives access to your profile.\n",
              flush=True)
    security = TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins)
    server.run(transport="streamable-http", port=args.port, streamable_http_path=path, transport_security=security)


if __name__ == "__main__":
    main()
