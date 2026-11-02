import json
import time

import pytest

from mo import events, profiles, runs

INITIAL = "Sleep matters because the brain clears waste and stores memories while you rest."
REWRITTEN = "Sleep, that knits the ravelled sleeve of care, doth clear the brain and keep its memories."


def voiced(chat, name="shakespear", seeds=()):
    """Create a profile, make it this chat's voice, and seed it (all as the HUMAN USER)."""
    win = chat.box("mo_config")
    win("create", name=name)
    win("set_voice", name=name)
    for s in seeds:
        win("add_seed", text=s)
    return win


def start(chat, request="explain why sleep matters"):
    """`@MO` + request: returns the run id, what MO told ChatGPT, and the Output window it opened."""
    result = chat.call("mo_output", initial=INITIAL, request=request)
    assert not result.get("isError"), result["content"]
    from conftest import box_call
    box, key = result["structuredContent"]["box"], result["_meta"]["mo/key"]
    window = lambda action, **data: box_call(chat.client, box, key, action, **data)  # noqa: E731
    return result["structuredContent"]["run"], result["content"][0]["text"], window


def test_mo_output_opens_the_window_itself(chats):
    a = chats("a")
    voiced(a, seeds=["To be, or not to be."])
    run_id, reply, window = start(a)
    assert "MO pass 1 of 1." in reply                                  # ChatGPT gets pass 1 …
    shown = window("result").json()                                     # … and the window already shows
    assert (shown["best"], shown["voice_loaded"], shown["done"]) == (INITIAL, 0, False)   # the best so far


def test_first_output_in_a_chat_asks_for_its_voice_then_continues(chats):
    a = chats("a")
    a.box("mo_config")("create", name="shakespear")
    run_id, reply, window = start(a)
    assert "no MO voice yet" in reply and "Stop now and wait" in reply
    assert window("result").json()["profile"] is None                  # the window shows the picker
    assert "waiting" in a.error("mo_output_continue", run=run_id)
    assert "waiting" in a.error("mo_output_pass", run=run_id, pass_number=1, version="x")
    chosen = window("choose_voice", name="shakespear").json()
    assert chosen["continue"] == run_id and chosen["voice"] == "shakespear"
    assert "no seeds" in a.text("mo_output_continue", run=run_id)     # shakespear has no seeds yet
    assert events.read(type="output_continued")[0]["chat"] == "chat-a"
    shown = window("result").json()
    assert (shown["done"], shown["seeds"], shown["voice_loaded"], shown["best"]) == (True, False, 100, INITIAL)
    [voice_set] = events.read(type="voice_set")
    assert voice_set["actor"] == events.HUMAN_USER and voice_set["chat"] == "chat-a"


def test_a_full_run_updates_the_window_as_passes_arrive(chats):
    a = chats("a")
    voiced(a, seeds=["To be, or not to be.", "What's in a name?"])
    run_id, reply, window = start(a)
    assert "reads like the EXAMPLES" in reply and INITIAL in reply and "What's in a name?" in reply
    assert "This is pass 1" in a.error("mo_output_pass", run=run_id, pass_number=2, version="x")
    assert "identical" in a.error("mo_output_pass", run=run_id, pass_number=1, version=INITIAL)
    assert "either" in a.error("mo_output_pass", run=run_id, pass_number=1, version="x", no_change_reason="y")
    done = a.text("mo_output_pass", run=run_id, pass_number=1, version=REWRITTEN)
    assert "the MO window above shows the result" in done and "Don't repeat the text" in done
    shown = window("result").json()
    assert (shown["best"], shown["done"], shown["voice_loaded"], shown["profile"]) == (REWRITTEN, True, 100, "shakespear")
    assert 0 < shown["changed"] <= 100
    assert "ravelled" not in json.dumps(events.read()) and "brain clears" not in json.dumps(events.read())


def test_voice_loaded_counts_seed_words_passed_through(chats):
    a = chats("a")
    voiced(a, seeds=["a " * 2000, "b " * 2000, "c " * 500])         # batches: [a] 2000, [b, c] 2500
    run_id, _, window = start(a)
    assert window("result").json()["voice_loaded"] == 0
    a.text("mo_output_pass", run=run_id, pass_number=1, version="first rewrite")
    shown = window("result").json()
    assert (shown["best"], shown["voice_loaded"], shown["done"]) == ("first rewrite", 44, False)  # 2000 / 4500


def test_a_stalled_run_offers_continue_and_never_retries_itself(chats, monkeypatch):
    a = chats("a")
    voiced(a, seeds=["a " * 2000, "b " * 2000])
    run_id, _, window = start(a)
    assert window("result").json()["stalled"] is False
    clock = [time.time() + runs.STALL_SECONDS + 1]
    monkeypatch.setattr(runs.time, "time", lambda: clock[0])
    assert window("result").json()["stalled"] is True                 # 90 s with nothing from ChatGPT
    assert window("continue_clicked").json()["continue"] == run_id      # the human user's click …
    assert window("result").json()["stalled"] is False                  # … restarts the clock
    assert events.read(type="continue_clicked")[0]["actor"] == events.HUMAN_USER
    assert "MO pass 1 of 2." in a.text("mo_output_continue", run=run_id)   # ChatGPT picks it back up (read-only)


def test_a_run_belongs_to_its_chat(chats):
    a, b = chats("a"), chats("b")
    voiced(a, seeds=["Short."])
    run_id, _, _ = start(a)
    assert "another chat" in b.error("mo_output_pass", run=run_id, pass_number=1, version="hijack")
    assert "another chat" in b.error("mo_output_continue", run=run_id)
    assert runs.find(run_id)["passes"] == []


def test_no_change_is_declared_with_a_reason(chats):
    a = chats("a")
    voiced(a, seeds=["Short. Plain."])
    run_id, _, window = start(a)
    a.text("mo_output_pass", run=run_id, pass_number=1, no_change_reason="Already short and plain.")
    [entry] = runs.find(run_id)["passes"]
    assert entry["no_change"] == "Already short and plain." and entry["changed"] == 0
    assert window("result").json()["voice_loaded"] == 100


def test_changing_the_voice_offers_a_rerun_that_the_same_window_follows(chats):
    a = chats("a")
    voiced(a, seeds=["To be, or not to be."])
    voiced(a, name="essay", seeds=["Plain words."])
    a.box("mo_config")("set_voice", name="shakespear")
    run_id, _, window = start(a)
    a.text("mo_output_pass", run=run_id, pass_number=1, version=REWRITTEN)
    assert window("set_voice", name="essay").json()["voice"] == "essay"
    assert window("result").json()["profile"] == "shakespear"            # the result keeps its label
    new_id = window("rerun").json()["continue"]
    assert (runs.find(new_id)["initial"], runs.find(new_id)["profile"]) == (INITIAL, "essay")
    assert "Plain words." in a.text("mo_output_continue", run=new_id)
    assert window("result", run=new_id).json()["run"] == new_id          # this window follows its rerun …
    other_id, _, _ = start(a)
    assert window("result", run=other_id).json()["run"] == run_id        # … but not other runs
    assert events.read(type="rerun")[0]["from_run"] == run_id


def test_runs_that_never_get_a_voice_expire_after_a_day(chats, monkeypatch):
    a = chats("a")
    a.box("mo_config")("create", name="essay")
    waiting_id, _, _ = start(a)
    later = time.time() + runs.WAITING_EXPIRES + 1
    monkeypatch.setattr(runs.time, "time", lambda: later)
    start(a)                                                            # the next output sweeps
    with pytest.raises(ValueError):
        runs.find(waiting_id)
    assert events.read(type="run_expired")[0]["run"] == waiting_id


def test_batches_and_changed_are_deterministic():
    seeds = [{"id": "1", "words": 2500}, {"id": "2", "words": 400}, {"id": "3", "words": 200}, {"id": "4", "words": 5000}]
    assert runs.batches(seeds) == [["1", "2"], ["3"], ["4"]]
    assert runs.batches([]) == []
    assert runs.changed("a b c d", "a b c d") == 0
    assert runs.changed("a b c d", "a x c d") == 25


def test_the_trace_keeps_exactly_what_mo_sent_each_pass(chats, client):
    a = chats("a")
    win = voiced(a, seeds=["To be, or not to be."])
    run_id, reply, _ = start(a)
    a.text("mo_output_pass", run=run_id, pass_number=1, version=REWRITTEN)
    win("delete_seeds", ids=[win("list_seeds").json()["seeds"][0]["id"]])   # deleting a seed later…
    [run] = client.get("/trace/profiles/shakespear", headers={"host": "127.0.0.1:8000"}).json()["runs"]
    assert run["sent"]["1"] == reply                                        # …doesn't rewrite history


def test_deleting_a_profile_deletes_its_runs(chats):
    a = chats("a")
    win = voiced(a)
    run_id, _, _ = start(a)
    code = win("delete", name="shakespear").json()["confirm"]
    win("confirm_delete", name="shakespear", confirm=code)
    with pytest.raises(ValueError):
        runs.find(run_id)
    assert not profiles.exists("shakespear")
