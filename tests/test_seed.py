import json

from mo import chats as chat_voices
from mo import events, profiles


def config(chat):
    return chat.box("mo_config")


def test_each_chat_has_its_own_voice_set_only_in_its_windows(chats):
    a, b = chats("a"), chats("b")
    in_a = config(a)
    in_a("create", name="shakespear")
    in_a("create", name="essay")
    assert in_a("state").json()["voice"] is None                     # a new chat has no voice
    assert in_a("set_voice", name="shakespear").json()["voice"] == "shakespear"
    in_b = config(b)
    assert in_b("state").json()["voice"] is None                     # nothing inherited from chat a
    in_b("set_voice", name="essay")
    assert config(a)("state").json()["voice"] == "shakespear"        # it stays until changed in chat a
    assert [(e["chat"], e["profile"]) for e in events.read(type="voice_set")] == [("chat-a", "shakespear"),
                                                                                  ("chat-b", "essay")]
    assert all(e["actor"] == events.HUMAN_USER for e in events.read(type="voice_set"))


def test_a_window_without_a_chat_cant_set_a_voice(server, client):
    from conftest import box_call, open_box
    box, key, _ = open_box(server, "mo_config")                     # no chat id reached MO
    box_call(client, box, key, "create", name="essay")
    assert box_call(client, box, key, "set_voice", name="essay").status_code == 400


def test_seeds_go_into_the_chats_voice_as_plain_text(chats, mo_home):
    win = config(chats("a"))
    win("create", name="essay")
    assert win("add_seed", text="hello").status_code == 400          # no voice yet: pick one first
    win("set_voice", name="essay")
    saved = win("add_seed", text="First line,\r\nsecond line.\r\n\r\nA new   paragraph.").json()["saved"]
    stored = json.loads((mo_home / "profiles" / "essay" / "seeds" / f"{saved['id']}.json").read_text())
    assert stored["text"] == "First line,\nsecond line.\n\nA new   paragraph."   # only line breaks unified
    assert saved["words"] == 7 and saved["profile"] == "essay"
    assert "paragraph" not in json.dumps(events.read())               # the trace holds no seed text
    assert win("add_seed", text="   ").status_code == 400
    assert win("add_seed", text="word " * 60_000).json()["saved"]["words"] == 60_000   # no size limit


def test_seed_list_and_delete_follow_the_chats_voice(chats):
    a, b = config(chats("a")), config(chats("b"))
    a("create", name="shakespear")
    a("create", name="essay")
    a("set_voice", name="shakespear")
    ids = [a("add_seed", text=t).json()["saved"]["id"] for t in ("To be", "or not", "to be")]
    assert [s["text"] for s in a("list_seeds").json()["seeds"]] == ["To be", "or not", "to be"]
    r = a("delete_seeds", ids=[ids[0], ids[2]]).json()                # no confirmation
    assert r["deleted"] == [ids[0], ids[2]] and [s["text"] for s in r["seeds"]] == ["or not"]
    b("set_voice", name="essay")
    assert b("delete_seeds", ids=[ids[1]]).json()["deleted"] == []   # chat b's voice is essay
    assert len(profiles.seeds("shakespear")) == 1
    assert a("delete_seeds", ids="../../etc").status_code == 400
    [deleted] = events.read(type="seeds_deleted", profile="shakespear")
    assert deleted["actor"] == events.HUMAN_USER


def test_clear_seeds_needs_two_clicks_and_keeps_tunes(chats, mo_home):
    win = config(chats("a"))
    win("create", name="essay")
    win("set_voice", name="essay")
    win("add_seed", text="one")
    win("add_seed", text="two")
    (mo_home / "profiles" / "essay" / "tunes" / "t1.json").write_text("{}")
    asked = win("clear_seeds", name="essay").json()
    assert asked["will_lose"]["seeds"] == 2 and profiles.summary("essay")["seeds"] == 2
    assert win("confirm_delete", name="essay", confirm=asked["confirm"]).status_code == 400  # wrong action
    code = win("clear_seeds", name="essay").json()["confirm"]
    assert win("confirm_clear_seeds", name="essay", confirm=code).json()["cleared"] == 2
    assert (profiles.summary("essay")["seeds"], profiles.summary("essay")["tunes"]) == (0, 1)


def test_deleting_a_profile_makes_its_chats_ask_again(chats):
    a, b = config(chats("a")), config(chats("b"))
    a("create", name="essay")
    a("set_voice", name="essay")
    b("set_voice", name="essay")
    code = a("delete", name="essay").json()["confirm"]
    a("confirm_delete", name="essay", confirm=code)
    assert chat_voices.voice("chat-a") is None and chat_voices.voice("chat-b") is None
    a("create", name="essay")
    assert a("state").json()["voice"] is None                          # re-creating doesn't bring it back
    assert events.read(type="profile_deleted")[0]["lost"]["chats"] == 2


def test_trace_shows_a_profiles_seeds_locally_only(chats, client):
    win = config(chats("a"))
    win("create", name="shakespear")
    win("set_voice", name="shakespear")
    win("add_seed", text="Shall I compare thee to a summer's day?")
    local = client.get("/trace/profiles/shakespear", headers={"host": "127.0.0.1:8000"}).json()
    assert local["seeds"][0]["text"] == "Shall I compare thee to a summer's day?"
    assert client.get("/trace/profiles/shakespear", headers={"host": "abc.trycloudflare.com"}).status_code == 404
    assert client.get("/trace/profiles/nope", headers={"host": "127.0.0.1:8000"}).status_code == 404
