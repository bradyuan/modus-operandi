import anyio

from conftest import PUBLIC, USER, box_call, open_box, sign_in
from mo import events, web
from mo.server import box_uri


def test_key_goes_only_into_hidden_meta(server):
    box, key, result = open_box(server, "mo_config")
    assert result.meta["mo/endpoint"] == PUBLIC
    # What the model sees (content and structured content) never contains the key.
    assert key not in str(result.content) and key not in str(result.structured_content)
    assert events.read(actor=events.CHATGPT)[0]["box"] == box


WINDOW_TOOLS = {"mo_help", "mo_config", "mo_seed", "mo_tune", "mo_trace"}


def test_chatgpt_can_never_pass_a_profile_or_voice(server):
    tools = {t.name: t for t in anyio.run(server.list_tools)}
    for name in WINDOW_TOOLS:
        assert not tools[name].input_schema.get("properties"), f"{name} lets ChatGPT pass arguments"
    for tool in tools.values():  # output tools carry content only
        props = tool.input_schema.get("properties") or {}
        assert "profile" not in props and "voice" not in props and "chat" not in props, tool.name


def test_box_template_is_linked_and_allowlists_mo(server):
    boxed = {t.name for t in anyio.run(server.list_tools) if (t.meta or {}).get("ui", {}).get("resourceUri") == box_uri(PUBLIC)}
    assert boxed == WINDOW_TOOLS | {"mo_output", "mo_tune_variants"}   # only these draw a window
    [resource] = anyio.run(server.list_resources)
    assert str(resource.uri) == box_uri(PUBLIC)
    assert resource.meta["ui"]["csp"]["connectDomains"] == [PUBLIC]
    assert box_uri(PUBLIC) != box_uri("https://other.trycloudflare.com")  # new address, fresh box


def test_unsigned_calls_are_refused_and_logged(server, client):
    box, key, _ = open_box(server, "mo_config")
    assert box_call(client, box, "forged", "create", name="evil").status_code == 403
    assert box_call(client, "deadbeef", key, "create", name="evil").status_code == 403  # another box's key
    assert [e["reason"] for e in events.read(type="refused")] == ["bad box key", "unknown box"]
    assert events.read(actor=events.HUMAN_USER) == []
    r = box_call(client, box, key, "list")
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "*"


def test_trace_needs_sign_in(client):
    assert "Sign in" in client.get("/trace").text                       # signed out: the sign-in page
    assert client.get("/trace/events").status_code == 401
    real = web.make_session(USER)
    client.cookies.set(web.COOKIE, real[:-1] + ("1" if real[-1] == "0" else "0"))   # a tampered cookie
    assert client.get("/trace/events").status_code == 401
    sign_in(client)
    assert "MO trace" in client.get("/trace").text and client.get("/trace/events").json() == []


def test_three_windows(server):
    views = {}
    for tool in ("mo_help", "mo_config", "mo_seed"):
        _, _, result = open_box(server, tool)
        views[tool] = (result.structured_content["view"], result.structured_content.get("tab"))
    assert views == {"mo_help": ("help", None), "mo_config": ("config", "profiles"), "mo_seed": ("config", "seeds")}


def test_the_chat_id_comes_from_chatgpts_app_metadata(chats):
    from mo import boxes
    result = chats("a").call("mo_config")
    assert result["_meta"]["mo/chat"] == "chat-a"
    [event] = events.read(tool="mo_config")
    assert event["chat"] == "chat-a" and boxes.load(event["box"])["chat"] == "chat-a"


def test_an_older_window_address_still_gets_the_current_window(server):
    """After a deploy, ChatGPT may ask for a window address it cached before (seen 2026-11-03)."""
    old = anyio.run(server.read_resource, "ui://mo/box-38ebf9b1.html")
    current = anyio.run(server.read_resource, box_uri(PUBLIC))
    assert list(old)[0].content == list(current)[0].content
