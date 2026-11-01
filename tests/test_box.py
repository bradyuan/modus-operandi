import anyio

from conftest import PUBLIC, box_call, open_box
from mo import events
from mo.dev import tunnel_host
from mo.server import box_uri


def test_key_goes_only_into_hidden_meta(server):
    box, key, result = open_box(server, "mo_profiles")
    assert result.meta["mo/endpoint"] == PUBLIC
    # What the model sees (content and structured content) never contains the key.
    assert key not in str(result.content) and key not in str(result.structured_content)
    assert events.read(actor=events.CHATGPT)[0]["box"] == box


def test_chatgpt_tools_take_no_arguments(server):
    for tool in anyio.run(server.list_tools):
        assert not tool.input_schema.get("properties"), f"{tool.name} lets ChatGPT pass arguments"


def test_box_template_is_linked_and_allowlists_mo(server):
    for tool in anyio.run(server.list_tools):
        assert tool.meta["ui"]["resourceUri"] == box_uri(PUBLIC)
    [resource] = anyio.run(server.list_resources)
    assert str(resource.uri) == box_uri(PUBLIC)
    assert resource.meta["ui"]["csp"]["connectDomains"] == [PUBLIC]
    assert box_uri(PUBLIC) != box_uri("https://other.trycloudflare.com")  # new address, fresh box


def test_unsigned_calls_are_refused_and_logged(server, client):
    box, key, _ = open_box(server, "mo_profiles")
    assert box_call(client, box, "forged", "create", name="evil").status_code == 403
    assert box_call(client, "deadbeef", key, "create", name="evil").status_code == 403  # another box's key
    assert [e["reason"] for e in events.read(type="refused")] == ["bad box key", "bad box key"]
    assert events.read(actor=events.HUMAN_USER) == []
    r = box_call(client, box, key, "list")
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "*"


def test_trace_is_local_only(client):
    assert client.get("/trace", headers={"host": "127.0.0.1:8000"}).status_code == 200
    assert client.get("/trace/events", headers={"host": "localhost:8000"}).json() == []
    assert client.get("/trace", headers={"host": "abc.trycloudflare.com"}).status_code == 404


def test_reads_the_tunnel_address_from_cloudflared_output():
    lines = ["INF Requesting new quick Tunnel", "INF |  https://brave-new-words.trycloudflare.com  |"]
    assert tunnel_host(lines) == "brave-new-words.trycloudflare.com"
