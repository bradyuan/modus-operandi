import json

import anyio
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mo.server import server
from mo.store import Profile, active_profile


def call(tool, args):
    return anyio.run(server.call_tool, tool, args)


def ok(args, tool="mo_profile"):
    result = call(tool, args)
    assert not result.is_error, result.content
    return result.structured_content


def fails(args, tool="mo_profile"):
    with pytest.raises(ToolError) as exc:
        call(tool, args)
    # The message must reach the host, not just "Error executing tool".
    assert ":" in str(exc.value)
    return str(exc.value)


def test_create_use_and_list(mo_home):
    assert ok({"action": "list"})["profiles"] == []
    ok({"action": "create", "name": "job-apps"})
    assert active_profile() == "job-apps"
    ok({"action": "create", "name": "journal"})
    ok({"action": "use", "name": "job-apps"})
    listed = ok({"action": "list"})
    assert listed == {"profiles": ["job-apps", "journal"], "active": "job-apps", "profile": "job-apps"}


def test_create_rejects_duplicates_and_use_rejects_unknown(mo_home):
    ok({"action": "create", "name": "a"})
    fails({"action": "create", "name": "a"})
    fails({"action": "use", "name": "missing"})


def test_add_sample_saves_immediately(mo_home):
    ok({"action": "create", "name": "job-apps"})
    saved = ok({"action": "add_sample", "register": "essay", "text": "I broke prod once. I fixed it."})
    samples = Profile("job-apps").exemplars("essay")
    assert [e.name for e in samples] == [saved["saved"]]
    assert samples[0].source == "user-provided"
    assert samples[0].text == "I broke prod once. I fixed it."


def test_add_sample_rejects_recent_mo_drafts(mo_home):
    ok({"action": "create", "name": "p"})
    draft = ("At my last job I rebuilt the alerting pipeline so that pages reached the right engineer within "
             "a minute, which cut our overnight incidents in half over one quarter.")
    ok({"register": "cover_letter", "draft": draft}, tool="mo_check")
    message = fails({"action": "add_sample", "register": "cover_letter", "text": draft})
    assert "looks AI-written" in message
    # Lightly wrapping the draft doesn't get around it either.
    fails({"action": "add_sample", "register": "cover_letter", "text": "Here's my letter. " + draft})
    # The user's own, different writing is fine.
    ok({"action": "add_sample", "register": "cover_letter",
        "text": "Honestly the reason I want this job is that I like fixing things at 2am more than I should."})
    assert len(Profile("p").exemplars("cover_letter")) == 1


def test_draft_fingerprints_store_no_text(mo_home):
    ok({"register": "essay", "draft": "Completely unique sentence about pelicans and spreadsheets today."},
       tool="mo_check")
    assert "pelicans" not in (mo_home / "recent_drafts.json").read_text()


def test_show_and_remove_sample(mo_home):
    ok({"action": "create", "name": "p"})
    saved = ok({"action": "add_sample", "register": "essay", "text": "Short. Plain.", "sample": "My Essay"})["saved"]
    shown = ok({"action": "show"})
    assert shown["samples"] == {"essay": [{"sample": "my-essay", "words": 2, "source": "user-provided"}]}
    ok({"action": "remove_sample", "register": "essay", "sample": saved})
    assert ok({"action": "show"})["samples"] == {}
    fails({"action": "remove_sample", "register": "essay", "sample": saved})


def test_write_uses_active_profile_and_nudges_for_seed(mo_home):
    ok({"action": "create", "name": "journal"})
    kit = ok({"register": "article"}, tool="mo_write")
    assert kit["profile"] == "journal"
    assert any("verbatim as `seed`" in n for n in kit["notes"])


def test_tool_calls_and_failures_are_logged_without_text(mo_home):
    ok({"action": "create", "name": "p"})
    ok({"register": "essay", "draft": "I'm excited to leverage this."}, tool="mo_check")
    fails({"action": "use", "name": "missing"})
    lines = [json.loads(l) for l in (mo_home / "logs" / "calls.jsonl").read_text().splitlines()]
    assert [l["tool"] for l in lines] == ["mo_profile", "mo_check", "mo_profile"]
    assert lines[1]["status"] == "failed_checks"
    assert "missing" in lines[2]["error"]
    assert "excited" not in json.dumps(lines)


def test_profile_names_are_case_insensitive(mo_home):
    assert ok({"action": "create", "name": "ELI5-reader"})["profile"] == "eli5-reader"
    assert ok({"action": "use", "name": "Eli5-Reader"})["profile"] == "eli5-reader"


def test_stated_rules_reach_the_right_kit(mo_home):
    ok({"action": "create", "name": "reader"})
    ok({"action": "add_rule", "text": "Open with a real puzzle, not fluff.", "task": "reading"})
    ok({"action": "add_rule", "text": "Short sentences."})  # both
    read = ok({"source": "CAP theorem"}, tool="mo_read")
    assert [r["rule"] for r in read["rules"]] == ["Open with a real puzzle, not fluff.", "Short sentences."]
    assert all(r["strength"] == "always" for r in read["rules"])
    write = ok({"register": "essay"}, tool="mo_write")
    assert [r["rule"] for r in write["rules"]] == ["Short sentences."]
    assert ok({"action": "add_rule", "text": "short sentences."})["reinforced"] == "Short sentences."
    ok({"action": "remove_rule", "text": "Short sentences."})
    assert [r["rule"] for r in ok({"action": "show"})["rules"]] == ["Open with a real puzzle, not fluff."]
    fails({"action": "remove_rule", "text": "Short sentences."})
