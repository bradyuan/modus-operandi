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


def rules(profile="default"):
    return {r["rule"]: (r["hits"], r["misses"]) for r in Profile(profile).rules()}


def test_draft_pick_finishes_and_stores_the_result_in_code(mo_home):
    plan = start(mode="draft", target="I am writing to apply for the role.")
    assert plan["status"] == "show_variations"
    assert set(plan["variations"]) == {"A", "B", "C"}
    done = answer(plan["session"], "picked", chosen="B", note="host-written text that must not be stored")
    assert done["status"] == "done" and "variation B" in done["next"]
    picked = f"{plan['axis']}: {plan['variations']['B']}"
    assert done["stored"] == {"rule": picked, "picked": 1, "passed_over": 0}
    # Worded from MO's own labels; the picked option gains a hit, the others a miss.
    assert rules() == {f"{plan['axis']}: {plan['variations'][k]}": (k == "B", k != "B") for k in "ABC"}
    [case] = cases()
    assert case["type"] == "tune_result" and case["data"]["chosen"] == "B"
    assert "must not be stored" not in str(case)


def test_none_fit_stays_on_target_and_changes_dimension(mo_home):
    plan = start(mode="draft", target="Opening sentence")
    again = answer(plan["session"], "none_fit")
    assert again["status"] == "regenerate"
    assert again["target"] == "Opening sentence"          # same part, not the next one
    assert again["axis"] != plan["axis"]                  # a different dimension
    assert any("already rejected" in s for s in again["steps"])
    assert cases() == [] and rules() == {}               # mid-run: nothing stored


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
    assert cases() == [] and rules() == {}


def test_abandoned_run_stores_nothing(mo_home):
    old = start(mode="draft", target="x")
    answer(old["session"], "none_fit")
    new = start(mode="draft", target="y")
    assert new["abandoned"] == [old["session"]]
    assert cases() == [] and rules() == {}
    with pytest.raises(ToolError):
        anyio.run(server.call_tool, "mo_tune", {"action": "answer", "session": old["session"],
                                                "outcome": "picked", "chosen": "A"})


def test_repeated_picks_strengthen_the_rule_the_kit_sends(mo_home):
    for n in range(3):
        plan = start(mode="draft", task="reading", target="x")
        answer(plan["session"], "picked", chosen="C")
    kit = anyio.run(server.call_tool, "mo_read", {"source": "TCP"}).structured_content
    top = kit["rules"][0]
    assert top["rule"] == f"{plan['axis']}: {plan['variations']['C']}"
    assert top["strength"] == "always"                    # 3 picks, 0 misses -> weight 0.8
    assert len(kit["rules"]) == 1                         # passed-over options never reach the kit


def test_diagnostic_pick_and_skip_advance_but_none_fit_does_not(mo_home):
    plan = start(mode="diagnostic", task="reading", source="https://example.com/paper")
    assert plan["round"] == 1
    stuck = answer(plan["session"], "none_fit")
    assert stuck["round"] == 1                            # bottleneck stays until addressed
    picked = answer(plan["session"], "picked", chosen="A")
    assert picked["round"] == 2
    skipped = answer(plan["session"], "skipped")
    assert skipped["round"] == 3
    assert [c["data"]["chosen"] for c in cases()] == ["A"]


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
