import pytest
from fastapi.testclient import TestClient

from mo.actions import create_app
from mo.server import _secret


@pytest.fixture
def client(mo_home):
    return TestClient(create_app("https://example.trycloudflare.com"))


@pytest.fixture
def auth(mo_home):
    return {"Authorization": f"Bearer {_secret()}"}


def test_requires_the_secret(client):
    assert client.post("/mo_profile", json={"action": "list"}).status_code in (401, 403)
    assert client.post("/mo_profile", json={"action": "list"}, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_tools_work_over_http(client, auth):
    assert client.post("/mo_profile", json={"action": "create", "name": "job-apps"}, headers=auth).json()["active"]
    kit = client.post("/mo_write", json={"register": "cover_letter", "seed": "I broke prod once."}, headers=auth)
    assert kit.status_code == 200 and kit.json()["seed_source"] == "user"
    checked = client.post("/mo_check", json={"register": "essay", "draft": "I'm excited to leverage this."}, headers=auth)
    assert checked.json()["status"] == "failed_checks"


def test_errors_reach_the_gpt_as_messages(client, auth):
    response = client.post("/mo_profile", json={"action": "use", "name": "missing"}, headers=auth)
    assert response.status_code == 400 and "No profile named" in response.json()["detail"]
    assert client.post("/mo_write", json={"register": "poem"}, headers=auth).status_code == 422


def test_openapi_schema_for_gpt_actions(client):
    schema = client.get("/openapi.json").json()
    assert schema["servers"] == [{"url": "https://example.trycloudflare.com"}]
    ops = {op["operationId"] for path in schema["paths"].values() for op in path.values()}
    assert ops == {"mo_write", "mo_check", "mo_tune", "mo_record", "mo_profile"}
    descriptions = [op["description"] for path in schema["paths"].values() for op in path.values()]
    assert all(len(d) <= 300 for d in descriptions)          # GPT Actions limit


def test_full_guidance_goes_in_the_gpt_instructions():
    from mo import api

    guide = api.host_guide()
    assert "BEFORE drafting" in guide and "mo_tune" in guide and len(guide) < 8000
