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
    """What ChatGPT gets (the result) and what only the box gets (its key, from hidden _meta)."""
    result = anyio.run(server.call_tool, tool, {})
    assert not result.is_error, result.content
    return result.structured_content["box"], result.meta["mo/key"], result


def box_call(client, box, key, action, **data):
    """A HUMAN USER action, as the MO box sends it."""
    return client.post(f"/box/{box}/event", json={"key": key, "action": action, **data})
