import anyio
import pytest
from starlette.testclient import TestClient

from mo import events
from mo.dev import tunnel_host
from mo.server import box_uri, create_server

PUBLIC = "https://abc.trycloudflare.com"


@pytest.fixture(autouse=True)
def mo_home(tmp_path, monkeypatch):
    monkeypatch.setenv("MO_HOME", str(tmp_path))
    return tmp_path


def spike(server):
    result = anyio.run(server.call_tool, "mo_spike", {})
    assert not result.is_error, result.content
    return result


def test_key_goes_only_into_hidden_meta():
    result = spike(create_server(PUBLIC))
    key = result.meta["mo/key"]
    assert result.meta["mo/endpoint"] == PUBLIC
    # What the model sees (content and structured content) never contains the key.
    assert key not in str(result.content) and key not in str(result.structured_content)
    assert events.read(actor=events.CHATGPT)[0]["box"] == result.structured_content["box"]


def test_box_template_is_linked_and_allowlists_mo():
    server = create_server(PUBLIC)
    [tool] = [t for t in anyio.run(server.list_tools) if t.name == "mo_spike"]
    assert tool.meta["ui"]["resourceUri"] == box_uri(PUBLIC)
    [resource] = anyio.run(server.list_resources)
    assert str(resource.uri) == box_uri(PUBLIC)
    assert resource.meta["ui"]["csp"]["connectDomains"] == [PUBLIC]
    assert box_uri(PUBLIC) != box_uri("https://other.trycloudflare.com")  # new address, fresh box


def test_only_signed_clicks_count_as_the_human_user():
    server = create_server(PUBLIC)
    result = spike(server)
    box, key = result.structured_content["box"], result.meta["mo/key"]
    client = TestClient(server.streamable_http_app())
    assert client.post(f"/box/{box}/event", json={"key": "forged", "choice": "A"}).status_code == 403
    ok = client.post(f"/box/{box}/event", json={"key": key, "choice": "B"})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "*"
    assert [e["choice"] for e in events.read(actor=events.HUMAN_USER)] == ["B"]
    assert events.read(type="refused")[0]["reason"] == "bad box key"


def test_trace_is_local_only():
    client = TestClient(create_server(PUBLIC).streamable_http_app())
    assert client.get("/trace", headers={"host": "127.0.0.1:8000"}).status_code == 200
    assert client.get("/trace/events", headers={"host": "localhost:8000"}).json() == []
    assert client.get("/trace", headers={"host": "abc.trycloudflare.com"}).status_code == 404


def test_reads_the_tunnel_address_from_cloudflared_output():
    lines = ["INF Requesting new quick Tunnel", "INF |  https://brave-new-words.trycloudflare.com  |"]
    assert tunnel_host(lines) == "brave-new-words.trycloudflare.com"
