import anyio
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mo import tune
from mo.server import server
from mo.store import Profile


def tune_call(args):
    result = anyio.run(server.call_tool, "mo_tune", args)
    assert not result.is_error, result.content
    return result.structured_content


def start(**kw):
    return tune_call({"action": "start", **kw})


def answer(session, outcome, **kw):
    return tune_call({"action": "answer", "session": session, "outcome": outcome, **kw})


def cases(profile="default"):
    return Profile(profile).cases()


def test_draft_pick_finishes_and_records(mo_home):
    plan = start(mode="draft", target="I am writing to apply for the role.")
    assert plan["status"] == "show_variations"
    assert set(plan["variations"]) == {"A", "B", "C"}
    done = answer(plan["session"], "picked", chosen="B")
    assert done["status"] == "done" and "variation B" in done["next"]
    [case] = cases()
    assert case["data"]["outcome"] == "picked" and case["data"]["chosen"] == "B"
    assert case["data"]["passed_over"] == ["A", "C"]


def test_none_fit_stays_on_target_and_changes_dimension(mo_home):
    plan = start(mode="draft", target="Opening sentence")
    again = answer(plan["session"], "none_fit")
    assert again["status"] == "regenerate"
    assert again["target"] == "Opening sentence"          # same part, not the next one
    assert again["axis"] != plan["axis"]                  # a different dimension
    assert any("already rejected" in s for s in again["steps"])
    assert cases()[0]["data"]["outcome"] == "none_fit"


def test_asks_whats_off_after_two_misses_then_uses_the_note(mo_home):
    plan = start(mode="draft", target="Opening sentence")
    first = answer(plan["session"], "none_fit")
    assert "ask_user" not in first
    second = answer(plan["session"], "none_fit")
    assert second["ask_user"] == tune.WHATS_OFF
    third = answer(plan["session"], "none_fit", note="the claim is backwards")
    assert "ask_user" not in third
    assert any("the claim is backwards" in s for s in third["steps"])


def test_skip_records_no_preference(mo_home):
    plan = start(mode="draft", target="x")
    done = answer(plan["session"], "skipped")
    assert done["status"] == "done"
    assert cases() == []


def test_diagnostic_pick_and_skip_advance_but_none_fit_does_not(mo_home):
    plan = start(mode="diagnostic", task="reading", source="https://example.com/paper")
    assert plan["round"] == 1
    stuck = answer(plan["session"], "none_fit")
    assert stuck["round"] == 1                            # bottleneck stays until addressed
    picked = answer(plan["session"], "picked", chosen="A")
    assert picked["round"] == 2
    skipped = answer(plan["session"], "skipped")
    assert skipped["round"] == 3
    assert [c["data"]["outcome"] for c in cases()] == ["none_fit", "picked"]


def test_diagnostic_finishes_after_last_round(mo_home):
    plan = start(mode="diagnostic")
    for _ in range(tune.MAX_DIAGNOSTIC_ROUNDS - 1):
        plan = answer(plan["session"], "picked", chosen="A")
    done = answer(plan["session"], "picked", chosen="C")
    assert done["status"] == "done"
    with pytest.raises(ToolError):
        anyio.run(server.call_tool, "mo_tune", {"action": "answer", "session": plan["session"], "outcome": "skipped"})


def test_picked_requires_a_choice_and_sessions_are_validated(mo_home):
    plan = start(mode="draft")
    for args in ({"outcome": "picked"}, {}):
        with pytest.raises(ToolError):
            anyio.run(server.call_tool, "mo_tune", {"action": "answer", "session": plan["session"], **args})
    with pytest.raises(ToolError):
        anyio.run(server.call_tool, "mo_tune", {"action": "answer", "session": "../../etc", "outcome": "skipped"})
