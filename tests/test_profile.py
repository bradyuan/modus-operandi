import json

import anyio
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mo.server import server
from mo.store import Profile, active_profile, mo_home


def call(args):
    return anyio.run(server.call_tool, "mo_profile", args)


def ok(args):
    result = call(args)
    assert not result.is_error, result.content
    return result.structured_content


def fails(args):
    with pytest.raises(ToolError) as exc:
        call(args)
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


def test_add_sample_needs_confirmation(mo_home):
    ok({"action": "create", "name": "job-apps"})
    pending = ok({"action": "add_sample", "register": "cover_letter", "text": "I broke prod once. I fixed it."})
    assert pending["status"] == "needs_confirmation"
    assert "your own writing" in pending["ask_user"]
    # Nothing is saved until the user confirms.
    assert Profile("job-apps").exemplars("cover_letter") == []

    saved = ok({"action": "confirm", "code": pending["code"]})
    samples = Profile("job-apps").exemplars("cover_letter")
    assert [e.name for e in samples] == [saved["saved"]]
    assert samples[0].source == "user-provided"
    assert samples[0].text == "I broke prod once. I fixed it."

    # A code works once.
    fails({"action": "confirm", "code": pending["code"]})


def test_show_and_remove_sample(mo_home):
    ok({"action": "create", "name": "p"})
    code = ok({"action": "add_sample", "register": "essay", "text": "Short. Plain.", "sample": "My Essay"})["code"]
    saved = ok({"action": "confirm", "code": code})["saved"]
    shown = ok({"action": "show"})
    assert shown["samples"] == {"essay": [{"sample": "my-essay", "words": 2, "source": "user-provided"}]}
    ok({"action": "remove_sample", "register": "essay", "sample": saved})
    assert ok({"action": "show"})["samples"] == {}
    fails({"action": "remove_sample", "register": "essay", "sample": saved})


def test_write_uses_active_profile(mo_home):
    ok({"action": "create", "name": "journal"})
    kit = anyio.run(server.call_tool, "mo_write", {"register": "article"}).structured_content
    assert kit["profile"] == "journal"


def test_diagnostic_rounds_vary_one_axis(mo_home):
    first = ok({"action": "diagnostic", "kind": "reading", "source": "https://example.com/paper"})
    second = ok({"action": "diagnostic", "kind": "reading", "round": 2})
    assert set(first["variations"]) == {"A", "B", "C"}
    assert first["axis"] != second["axis"]
    assert any("mo_record" in step for step in first["steps"])


def test_tool_calls_are_logged_without_text(mo_home):
    ok({"action": "create", "name": "p"})
    anyio.run(server.call_tool, "mo_check", {"register": "essay", "draft": "I'm excited to leverage this."})
    lines = [json.loads(l) for l in (mo_home / "logs" / "calls.jsonl").read_text().splitlines()]
    assert [l["tool"] for l in lines] == ["mo_profile", "mo_check"]
    assert lines[1]["status"] == "failed_checks"
    assert "excited" not in json.dumps(lines)
