"""Sign-in and per-user scoping (HOSTING.md §2–3). Plumbing only: the human user's test in ChatGPT decides."""

from conftest import TOKENS, USER, Chat, sign_in


def test_no_token_or_a_bad_one_is_refused(client):
    with client:
        r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                        headers={**Chat.HEADERS, "authorization": "Bearer forged"})
        assert r.status_code == 401
        assert "resource_metadata" in r.headers["www-authenticate"]


def test_each_user_only_ever_sees_their_own_profiles(client, mo_home):
    with client:
        mine, theirs = Chat(client, "chat-1"), Chat(client, "chat-2", token="token-other")
        assert USER in mine.text("mo_whoami") and TOKENS["token-other"] in theirs.text("mo_whoami")
        assert mine.box("mo_config")("create", name="mine").status_code == 200
        assert theirs.box("mo_config")("create", name="theirs").status_code == 200
        names = lambda chat: [p["name"] for p in chat.box("mo_config")("list").json()["profiles"]]  # noqa: E731
        assert names(mine) == ["mine"] and names(theirs) == ["theirs"]
        assert (mo_home / "profiles" / "mine").is_dir()
        assert not (mo_home.parent / "user_other" / "profiles" / "mine").exists()


def test_a_window_acts_only_for_the_user_who_opened_it(client, mo_home):
    with client:
        theirs = Chat(client, "chat-2", token="token-other").box("mo_config")
        theirs("create", name="theirs")
        assert not (mo_home / "profiles" / "theirs").exists()
        assert (mo_home.parent / "user_other" / "profiles" / "theirs").is_dir()


def test_an_admin_can_open_any_users_trace_read_only(client, monkeypatch):
    from mo import auth
    monkeypatch.setattr(auth, "is_admin", lambda user: user == USER)
    with client:
        Chat(client, "chat-2", token="token-other").box("mo_config")("create", name="theirs")
        sign_in(client, "user_other")                                   # not an admin
        assert client.get("/trace/users").status_code == 403
        assert client.get(f"/trace/events?user={USER}").status_code == 403
        sign_in(client)                                                 # an admin
        assert {u["user"] for u in client.get("/trace/users").json()} == {"user_other"}
        assert [p["name"] for p in client.get("/trace/profiles?user=user_other").json()] == ["theirs"]
        assert client.get("/trace/profiles?user=user_nobody").status_code == 403
        assert client.post("/trace/events?user=user_other").status_code == 405   # read-only


def test_the_trace_window_shows_only_this_chats_activity(client):
    with client:
        here, there = Chat(client, "chat-1"), Chat(client, "chat-2")
        there.box("mo_config")("create", name="elsewhere")
        recent = here.box("mo_trace")("recent").json()["events"]
        assert [e["type"] for e in recent] == ["tool_call"] and recent[0]["tool"] == "mo_trace"
