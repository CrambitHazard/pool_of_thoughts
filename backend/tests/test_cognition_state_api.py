"""Cognition runtime API tests."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_cognition_state_endpoint() -> None:
    """State endpoint returns workspace, backlog, and activity fields."""
    response = client.get("/api/cognition/state")

    assert response.status_code == 200
    body = response.json()
    assert "working_memory" in body
    assert "backlog" in body
    assert "activity" in body
    assert body["working_capacity"] == 7


def test_demo_seed_populates_workspace() -> None:
    """Demo endpoint seeds thoughts without LLM calls."""
    response = client.post("/api/cognition/demo")

    assert response.status_code == 200
    body = response.json()
    assert len(body["working_memory"]) >= 1
    assert len(body["activity"]) >= 1


def test_cognition_tick_updates_state() -> None:
    """Tick endpoint runs the cognitive loop."""
    client.post("/api/cognition/demo")
    response = client.post("/api/cognition/tick")

    assert response.status_code == 200
    assert response.json()["tick_count"] >= 1
