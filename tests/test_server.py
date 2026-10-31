import anyio
import pytest

from mo.server import server
from mo.store import Profile


def call(name, args):
    return anyio.run(server.call_tool, name, args)


def test_tools_are_listed():
    names = {t.name for t in anyio.run(server.list_tools)}
    assert names == {"mo_write", "mo_check", "mo_record", "mo_profile"}


def test_write_check_record_round_trip(mo_home):
    kit = call("mo_write", {"register": "cover_letter", "seed": "I broke prod once."})
    assert not kit.is_error
    assert kit.structured_content["seed_source"] == "user"

    checked = call("mo_check", {"register": "cover_letter", "draft": "I'm excited to leverage synergy."})
    assert checked.structured_content["status"] == "failed_checks"

    recorded = call("mo_record", {"kind": "variations", "register": "cover_letter",
                                  "data": {"chosen": "b", "rejected": "a", "passed_over": ["c"]}})
    assert recorded.structured_content["recorded"].startswith("c")
    assert Profile("default").cases()[0]["data"]["chosen"] == "b"


def test_bad_profile_name_is_rejected(mo_home):
    with pytest.raises(ValueError):
        Profile("../etc")
