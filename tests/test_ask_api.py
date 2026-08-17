"""/v1/ask answers about the run and cannot be used to drive it."""

import pytest
from fastapi.testclient import TestClient

from council.api import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GUILDLESS_HOME", str(tmp_path))
    monkeypatch.setenv("COUNCIL_OUTPUT_DIR", str(tmp_path / "runs"))
    app = create_app(output_boundary=tmp_path)
    # No lifespan: starting the worker would put a live thread behind a test
    # that is only reading. The route under test never touches it.
    with TestClient(app) as made:
        yield made


def test_an_instruction_is_refused_over_http(client):
    reply = client.post("/v1/ask", json={"question": "値段を下げろ"})
    assert reply.status_code == 200
    body = reply.json()
    assert body["refused"] is True
    assert "新しいRun" in body["text"]


def test_money_questions_never_reach_a_model(client):
    body = client.post("/v1/ask", json={"question": "いくら儲かった？"}).json()
    assert body["from_model"] is False
    assert "¥" in body["text"]
    assert body["grounded_in"]


def test_an_empty_question_is_rejected_by_the_schema(client):
    assert client.post("/v1/ask", json={"question": ""}).status_code == 422


def test_the_body_accepts_nothing_but_a_question(client):
    """Any extra field would be the start of a control channel."""
    reply = client.post("/v1/ask", json={"question": "いくら？", "price_yen": 100})
    assert reply.status_code == 422


def test_asking_does_not_change_the_run(client):
    before = client.get("/v1/outcome").json()
    client.post("/v1/ask", json={"question": "なんで止まってるの？"})
    client.post("/v1/ask", json={"question": "全部やめろ"})
    after = client.get("/v1/outcome").json()
    for field in ("spark", "verified_net_outcome_yen", "status", "money", "strategy"):
        assert before[field] == after[field]
