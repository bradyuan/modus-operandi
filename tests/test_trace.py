from starlette.testclient import TestClient

from mo import api, trace
from mo.server import server
from mo.store import read_trace


def traced_run(monkeypatch):
    monkeypatch.setenv("MO_TRACE", "1")
    api.mo_profile(action="create", name="p")
    api.mo_write(register="essay", seed="I broke prod once.")
    api.mo_check(draft="I'm excited to leverage my skills.", register="essay")
    api.mo_check(draft="I broke prod once, and I fixed it.", register="essay")


def test_runs_show_each_draft_version_and_what_mo_sent(mo_home, monkeypatch):
    traced_run(monkeypatch)
    runs = trace.runs(read_trace())
    run = runs[-1]
    assert run["kit"]["args"]["seed"] == "I broke prod once."
    assert [v["status"] for v in run["versions"]] == ["failed_checks", "passed"]
    assert run["versions"][0]["draft"] == "I'm excited to leverage my skills."
    assert any("Empty kit" in w for w in run["warnings"])
    assert any("nothing to compare" in w for w in run["warnings"])


def test_nothing_is_traced_unless_dev_mode(mo_home):
    api.mo_write(register="essay", seed="private words")
    assert read_trace() == []


def test_trace_page_is_local_only(mo_home, monkeypatch):
    traced_run(monkeypatch)
    client = TestClient(server.streamable_http_app())
    assert client.get("/trace", headers={"host": "127.0.0.1:8000"}).status_code == 200
    assert client.get("/trace.json", headers={"host": "localhost:8000"}).json()[-1]["versions"]
    assert client.get("/trace", headers={"host": "abc.trycloudflare.com"}).status_code == 404
    assert client.get("/trace.json", headers={"host": "abc.trycloudflare.com"}).status_code == 404
