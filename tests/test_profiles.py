from conftest import box_call, open_box
from mo import events, profiles


def profiles_box(server, client):
    box, key, _ = open_box(server, "mo_config")
    return lambda action, **data: box_call(client, box, key, action, **data)


def test_create_list_and_names_are_normalized(server, client):
    act = profiles_box(server, client)
    assert act("list").json() == {"profiles": [], "voice": None}
    r = act("create", name="  ELI5 ")
    assert r.status_code == 200 and r.json()["created"]["name"] == "eli5"
    assert [p["name"] for p in act("list").json()["profiles"]] == ["eli5"]
    assert act("create", name="eli5").status_code == 400            # duplicate
    assert act("create", name="no spaces!").status_code == 400      # invalid name
    assert act("create", name="../etc").status_code == 400
    assert [e["profile"] for e in events.read(actor=events.HUMAN_USER)] == ["eli5"]
    assert len(events.read(type="refused")) == 3


def test_delete_needs_two_clicks_and_is_permanent(server, client, mo_home):
    act = profiles_box(server, client)
    act("create", name="journal")
    (mo_home / "profiles" / "journal" / "seeds" / "s1.json").write_text("{}")
    asked = act("delete", name="journal").json()
    assert asked["will_lose"]["seeds"] == 1 and profiles.exists("journal")  # nothing deleted yet
    assert act("confirm_delete", name="journal", confirm="guess").status_code == 400
    assert profiles.exists("journal")
    # A failed confirmation burns the code: a new Delete click is needed.
    assert act("confirm_delete", name="journal", confirm=asked["confirm"]).status_code == 400
    code = act("delete", name="journal").json()["confirm"]
    done = act("confirm_delete", name="journal", confirm=code)
    assert done.status_code == 200 and done.json()["profiles"] == []
    assert not (mo_home / "profiles" / "journal").exists()
    [deleted] = events.read(type="profile_deleted")
    assert deleted["actor"] == events.HUMAN_USER and deleted["deleted_profile"] == "journal"
    assert deleted["lost"]["seeds"] == 1


def test_confirmation_is_tied_to_the_profile_and_the_box(server, client):
    act = profiles_box(server, client)
    act("create", name="a")
    act("create", name="b")
    code = act("delete", name="a").json()["confirm"]
    assert act("confirm_delete", name="b", confirm=code).status_code == 400  # code was for "a"
    other = profiles_box(server, client)
    code = act("delete", name="a").json()["confirm"]
    assert other("confirm_delete", name="a", confirm=code).status_code == 400  # code was for another box
    assert profiles.exists("a") and profiles.exists("b")


def test_actions_belong_to_their_box_kind(server, client):
    act = profiles_box(server, client)
    assert act("pick", choice="A").status_code == 403
    assert events.read(type="refused")[0]["reason"].startswith("'pick' isn't an action")


def test_delete_purges_the_profiles_events_and_leaves_one_tombstone(server, client):
    act = profiles_box(server, client)
    act("create", name="eli5-reader")
    act("create", name="essay-writer")
    events.record(events.HUMAN_USER, "seed_added", profile="eli5-reader", text="my private words")
    code = act("delete", name="eli5-reader").json()["confirm"]
    act("confirm_delete", name="eli5-reader", confirm=code)
    assert events.read(profile="eli5-reader") == []                # its events, text included, are gone
    assert "my private words" not in str(events.read())
    [tomb] = events.read(type="profile_deleted")
    assert tomb["deleted_profile"] == "eli5-reader" and tomb["lost"]["events"] == 3
    assert events.read(profile="essay-writer")                      # other profiles untouched
    # Re-creating the name starts with a clean history: the tombstone isn't in the new profile's tab.
    act("create", name="eli5-reader")
    assert [e["type"] for e in events.read(profile="eli5-reader")] == ["profile_created"]


def test_trace_filters_by_profile(server, client):
    act = profiles_box(server, client)
    act("create", name="a")
    local = {"host": "127.0.0.1:8000"}
    by_a = client.get("/trace/events?profile=a", headers=local).json()
    assert [e["type"] for e in by_a] == ["profile_created"]
    none = client.get("/trace/events?profile=none", headers=local).json()
    assert [e["type"] for e in none] == ["tool_call"]               # opening the box belongs to no profile
    assert [p["name"] for p in client.get("/trace/profiles", headers=local).json()] == ["a"]
    assert client.get("/trace/profiles", headers={"host": "abc.trycloudflare.com"}).status_code == 404
