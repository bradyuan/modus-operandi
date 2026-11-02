import json

import anyio
import pytest
from starlette.testclient import TestClient

from mo.server import create_server

PUBLIC = "https://abc.trycloudflare.com"


@pytest.fixture(autouse=True)
def mo_home(tmp_path, monkeypatch):
    monkeypatch.setenv("MO_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def server():
    return create_server(PUBLIC)


@pytest.fixture
def client(server):
    return TestClient(server.streamable_http_app())


def open_box(server, tool):
    """What ChatGPT gets (the result) and what only the box gets (its key, from hidden _meta).
    Called outside a real request, so the box has no chat."""
    result = anyio.run(server.call_tool, tool, {})
    assert not result.is_error, result.content
    return result.structured_content["box"], result.meta["mo/key"], result


def box_call(client, box, key, action, **data):
    """A HUMAN USER action, as the MO box sends it."""
    return client.post(f"/box/{box}/event", json={"key": key, "action": action, **data})


class Chat:
    """One ChatGPT chat talking to MO over MCP HTTP: every call carries this chat's `openai/session`,
    the way ChatGPT's app attaches it."""

    HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json",
               "host": "127.0.0.1:8000"}

    def __init__(self, client, chat_id):
        self.client, self.chat_id, self.ids = client, chat_id, 10
        r, _ = self._rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "chatgpt", "version": "1"}}})
        self.session = r.headers.get("mcp-session-id")
        self._rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _rpc(self, body):
        headers = dict(self.HEADERS, **({"mcp-session-id": self.session} if getattr(self, "session", None) else {}))
        r = self.client.post("/mcp", json=body, headers=headers)
        data = [json.loads(line[5:]) for line in r.text.splitlines() if line.startswith("data:")]
        return r, data[0] if data else None

    def call(self, tool, **args):
        """The tool result: {content, structuredContent, _meta, isError}."""
        self.ids += 1
        _, res = self._rpc({"jsonrpc": "2.0", "id": self.ids, "method": "tools/call",
                            "params": {"name": tool, "arguments": args, "_meta": {"openai/session": self.chat_id}}})
        return res["result"]

    def text(self, tool, **args):
        result = self.call(tool, **args)
        assert not result.get("isError"), result["content"]
        return result["content"][0]["text"]

    def error(self, tool, **args):
        result = self.call(tool, **args)
        assert result.get("isError"), result
        return result["content"][0]["text"]

    def box(self, tool, **args):
        """Open an MO window in this chat; returns a function that acts in it as the HUMAN USER."""
        result = self.call(tool, **args)
        assert not result.get("isError"), result["content"]
        box, key = result["structuredContent"]["box"], result["_meta"]["mo/key"]
        return lambda action, **data: box_call(self.client, box, key, action, **data)


@pytest.fixture
def chats(client):
    """Open chats on demand: chats("a") is one chat, chats("b") another."""
    with client:
        opened = {}
        yield lambda name: opened.setdefault(name, Chat(client, f"chat-{name}"))
