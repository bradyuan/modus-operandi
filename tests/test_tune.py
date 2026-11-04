import json
import time

import pytest

from conftest import box_call
from mo import events, profiles, runs, tunes

SOURCE = ("Sleep lends its strength to learning. It bids remembrance hold. It steadies the passions. "
          "Within its quiet hours, the flesh repairs its fabric. The body's watch against disease is kept.")


def window_of(chat, result):
    box, key = result["structuredContent"]["box"], result["_meta"]["mo/key"]
    return lambda action, **data: box_call(chat.client, box, key, action, **data)


def variants(chat, **round_):
    """ChatGPT writes a round's A/B/C; MO draws them in a new window, the one the user acts in next."""
    return window_of(chat, chat.call("mo_tune_variants", **round_))


def finished_output(chat, seeds=("To be, or not to be.",)):
    """A chat with a voice and one finished output; returns the Output window."""
    win = chat.box("mo_config")
    win("create", name="shakespear")
    win("set_voice", name="shakespear")
    for s in seeds:
        win("add_seed", text=s)
    result = chat.call("mo_output", initial="Sleep matters.", request="why sleep matters")
    run_id = result["structuredContent"]["run"]
    chat.text("mo_output_pass", run=run_id, pass_number=1, version=SOURCE)
    return window_of(chat, result), run_id


def test_tune_from_an_output_click_by_click(chats):
    a = chats("a")
    out, run_id = finished_output(a)
    state = out("start_tune").json()                                       # "Not satisfied? Tune voice profile"
    tune_id = state["tune"]
    assert (state["status"], state["source"]) == ("part", SOURCE)
    # Begin Tuning on the clicked sentences (3 and 4), with an optional note for ChatGPT.
    assert out("tune_select", first=3, last=4, note="I don't like the word fabric").json()["work"] == tune_id
    assert out("tune_state").json()["target"] == ("Within its quiet hours, the flesh repairs its fabric. "
                                                  "The body's watch against disease is kept.")
    vary = a.text("mo_tune_work", tune=tune_id)                          # ChatGPT's only job: variants
    assert "round 1" in vary and "I don't like the word fabric" in vary and "To be, or not to be." in vary
    assert "must differ" in a.error("mo_tune_variants", tune=tune_id, round_number=1, a="x", b="x", c="y")
    out = variants(a, tune=tune_id, round_number=1, a="A1", b="B1", c="C1")
    assert out("tune_done").status_code == 400                           # nothing picked yet
    # Click C → round 2 varies C (with an optional note).
    out("tune_choose", pick="C", comment="less stiff", final=False)
    vary2 = a.text("mo_tune_work", tune=tune_id)
    assert "round 2" in vary2 and "C1" in vary2 and "less stiff" in vary2
    out = variants(a, tune=tune_id, round_number=2, a="C1a", b="C1b", c="C1c")
    out("tune_choose", pick="B", final=False)                            # click B → round 3 varies B …
    out = variants(a, tune=tune_id, round_number=3, a="x1", b="x2", c="x3")
    sealed = out("tune_done").json()                                     # … Done keeps the last pick (C1b)
    assert sealed["status"] == "sealed" and sealed["final"] == "C1b"
    assert sealed["tuned"] == SOURCE.replace("Within its quiet hours, the flesh repairs its fabric. "
                                             "The body's watch against disease is kept.", "C1b")
    [stored] = tunes.sealed_for("shakespear")
    assert [r.get("pick") for r in stored["rounds"]] == ["C", "B", None] and stored["rounds"][1]["from"] == "C1"
    assert tunes.rejected(stored) == ["A1", "B1", "C1a", "C1c"]          # the unanswered round 3 isn't "rejected"
    assert "fabric" not in json.dumps(events.read()) and "stiff" not in json.dumps(events.read())
    [seal] = events.read(type="tune_sealed")
    assert seal["actor"] == events.HUMAN_USER and seal["rounds"] == 2      # round 3 was on screen, unanswered


def test_begin_tuning_without_clicks_lets_mo_choose_and_none_needs_no_note(chats):
    a = chats("a")
    out, _ = finished_output(a)
    tune_id = out("start_tune").json()["tune"]
    out("tune_choose_for_me")
    state = out("tune_state").json()
    assert state["target"] == "Sleep lends its strength to learning. It bids remembrance hold. It steadies the passions."
    assert (state["status"], state["how"]) == ("vary", "chosen by MO")
    out = variants(a, tune=tune_id, round_number=1, a="A1", b="B1", c="C1")
    assert out("tune_choose", pick=None, comment="", final=False).status_code == 200   # None of these, no note


def test_reopening_resumes_the_unfinished_tune_or_starts_over(chats):
    a = chats("a")
    out, _ = finished_output(a)
    tune_id = out("start_tune").json()["tune"]
    out("tune_choose_for_me")
    resumed = out("start_tune").json()                                    # the button again: no duplicate
    assert resumed["resumed"] is True and resumed["tune"] == tune_id
    again = a.call("mo_tune")                                             # @MO tune resumes it too
    assert again["structuredContent"]["tune"] == tune_id
    fresh = window_of(a, again)("tune_start_over").json()              # in the newest window
    assert fresh["tune"] != tune_id and fresh["status"] == "part"
    with pytest.raises(ValueError):
        tunes.find(tune_id)                                               # the unfinished one stored nothing
    assert [e["type"] for e in events.read(tune=tune_id)][-1] == "tune_discarded"


def test_mo_tune_uses_the_chats_last_output_or_asks_to_paste(chats):
    a, b = chats("a"), chats("b")
    finished_output(a)
    result = a.call("mo_tune")
    tune = tunes.find(result["structuredContent"]["tune"])
    assert tune["source"]["text"] == SOURCE and tune["profile"] == "shakespear"
    assert events.read(type="tune_started")[0]["actor"] == events.MO     # MO's fixed rule: the last output
    # A chat with no output: paste text (needs the chat's voice first).
    fresh = b.call("mo_tune")
    assert fresh["structuredContent"]["tune"] is None
    paste = window_of(b, fresh)
    assert paste("tune_paste", text="My own draft.").status_code == 400  # no voice for chat b yet
    paste("set_voice", name="shakespear")
    assert paste("tune_paste", text="My own draft.").json()["source"] == "My own draft."


def test_a_tune_belongs_to_its_chat(chats):
    a, b = chats("a"), chats("b")
    out, _ = finished_output(a)
    tune_id = out("start_tune").json()["tune"]
    out("tune_choose_for_me")
    assert "another chat" in b.error("mo_tune_variants", tune=tune_id, round_number=1, a="x", b="y", c="z")


def test_output_hands_out_tunes_after_seeds_in_batches_of_1_3_10_30(chats):
    a = chats("a")
    out, _ = finished_output(a)
    tune_id = out("start_tune").json()["tune"]
    out("tune_choose_for_me", note="less stiff")
    out = variants(a, tune=tune_id, round_number=1, a="A1", b="B1", c="C1")
    out("tune_choose", pick="A", final=False)
    out("tune_done")
    result = a.call("mo_output", initial="Dreams matter.", request="why dreams matter")
    run_id = result["structuredContent"]["run"]
    run = runs.find(run_id)
    assert run["batch_kinds"] == ["seeds", "tunes"] and run["batches"][1] == [tune_id]
    first = result["content"][0]["text"]
    assert "MO pass 1 of 2." in first and "EXAMPLES" in first
    second = a.text("mo_output_pass", run=run_id, pass_number=1, version="Dreams do matter.")
    assert "MO pass 2 of 2: tuned parts." in second
    assert "TUNED:\n<<<\nA1\n>>>" in second and "less stiff" in second and "REJECTED: <<<\nB1" in second
    assert 0 < window_of(a, result)("result").json()["voice_loaded"] < 100


def test_tune_batch_sizes_follow_the_rule_of_threes():
    ids = [str(i) for i in range(50)]
    assert [len(b) for b in runs.tune_batches(ids)] == [1, 3, 10, 30, 6]
    assert [len(b) for b in runs.tune_batches([str(i) for i in range(150)])] == [1, 3, 10, 30, 100, 6]


def test_tunes_tab_lists_and_deletes_without_confirmation(chats):
    a = chats("a")
    out, _ = finished_output(a)
    tune_id = out("start_tune").json()["tune"]
    out("tune_choose_for_me")
    out = variants(a, tune=tune_id, round_number=1, a="A1", b="B1", c="C1")
    out("tune_choose", pick="A", final=True)
    cfg = a.box("mo_config")
    assert [t["id"] for t in cfg("list_tunes").json()["tunes"]] == [tune_id]
    assert cfg("delete_tunes", ids=[tune_id]).json()["tunes"] == []
    assert events.read(type="tunes_deleted")[0]["actor"] == events.HUMAN_USER


def test_unconfirmed_tunes_store_nothing_and_expire(chats, monkeypatch):
    a = chats("a")
    out, _ = finished_output(a)
    tune_id = out("start_tune").json()["tune"]
    assert profiles.summary("shakespear")["tunes"] == 0                  # open tunes aren't part of the voice
    later = time.time() + tunes.OPEN_EXPIRES + 1
    monkeypatch.setattr(tunes.time, "time", lambda: later)
    a.call("mo_tune")
    with pytest.raises(ValueError):
        tunes.find(tune_id)
    assert events.read(type="tune_expired")[0]["tune"] == tune_id


def test_opening_takes_the_first_three_sentences_exactly():
    assert "".join(tunes.sentences("One. Two! Three? Four.")) == "One. Two! Three? Four."
    assert tunes.opening("One. Two! Three? Four.") == "One. Two! Three?"
    assert tunes.opening("Just one sentence") == "Just one sentence"
    assert tunes.opening('He said "hi." Then left. Done. More.') == 'He said "hi." Then left. Done.'


def test_each_round_draws_a_new_window_that_takes_over(chats):
    a = chats("a")
    out, _ = finished_output(a)
    tune_id = out("start_tune").json()["tune"]
    first_window = out("tune_state").json()["window"]
    out("tune_choose_for_me")
    result = a.call("mo_tune_variants", tune=tune_id, round_number=1, a="A1", b="B1", c="C1")
    assert not result.get("isError") and result["structuredContent"]["tune"] == tune_id
    snap = result["_meta"]["mo/snapshot"]                                # drawn instantly from this …
    assert snap["status"] == "choose" and snap["rounds"][0]["variants"]["B"] == "B1"
    assert snap["window"] == result["structuredContent"]["box"]           # … and it knows it's the live one
    assert "snapshot" not in str(result["content"])                      # the model just gets a short note
    new_window = result["structuredContent"]["box"]
    state = out("tune_state").json()
    assert state["window"] == new_window != first_window                 # the old window folds up
    newer = window_of(a, result)
    newer("tune_choose", pick="B", final=False)                          # the new window carries on
    assert tunes.find(tune_id)["rounds"][0]["pick"] == "B"


def test_only_the_chats_newest_window_is_interactive(chats):
    a = chats("a")
    out, _ = finished_output(a)
    newer = a.box("mo_config")                                           # a newer window in the same chat
    r = out("start_tune")
    assert r.status_code == 409 and "newer MO window" in r.json()["error"]
    assert out("result").json()["stale"] is True                         # reading still works, flagged stale
    assert newer("list").json()["stale"] is False
    other = chats("b").box("mo_config")                                  # another chat's windows don't count
    assert other("list").json()["stale"] is False


def test_retry_is_offered_after_20_s_if_chatgpt_never_picked_up(chats, monkeypatch):
    a = chats("a")
    out, _ = finished_output(a)
    tune_id = out("start_tune").json()["tune"]
    out("tune_choose_for_me")                                            # the window asks ChatGPT for A/B/C
    assert out("tune_state").json()["stalled"] is False
    clock = [time.time() + tunes.PICKUP_SECONDS + 1]
    monkeypatch.setattr(tunes.time, "time", lambda: clock[0])
    state = out("tune_state").json()
    assert state["stalled"] is True and state["picked_up"] is False      # → "ChatGPT didn't pick this up" + Retry
    a.text("mo_tune_work", tune=tune_id)                                 # ChatGPT picks it up
    state = out("tune_state").json()
    assert state["picked_up"] is True and state["stalled"] is False      # now the 90 s clock applies
    clock[0] += 5
    out("tune_continue")                                                 # Retry: the user's click, waits again
    assert out("tune_state").json()["picked_up"] is False


def test_the_window_reports_whether_its_message_reached_chatgpt(chats):
    a = chats("a")
    out, _ = finished_output(a)
    out("followup", ok=True, what="Begin tuning")
    out("followup", ok=False, what="Picked B", error="sendFollowUpMessage is not available")
    sent, failed = events.read(type="followup_sent"), events.read(type="followup_failed")
    assert sent[0]["what"] == "Begin tuning" and failed[0]["error"].startswith("sendFollowUpMessage")
    assert sent[0]["actor"] == events.MO and sent[0]["reported_by"] == "window"
