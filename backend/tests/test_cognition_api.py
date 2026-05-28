"""Cognition extraction API tests."""

from fastapi.testclient import TestClient

from app.api.deps import get_thought_extraction_service
from app.cognitive.thought_extraction import ThoughtExtractionService
from app.main import app
from tests.test_thought_extraction import FakeLLMProvider


client = TestClient(app)


def test_extract_endpoint_returns_structured_thoughts() -> None:
    """Extract endpoint returns structured cognition output."""
    service = ThoughtExtractionService(FakeLLMProvider())
    app.dependency_overrides[get_thought_extraction_service] = lambda: service

    try:
        response = client.post(
            "/api/cognition/extract",
            json={"message": "finish memory model draft"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == "Finish the memory model draft soon"
    assert body["primary_thought"]["content"] == "Need to finish memory model draft"
    assert len(body["related_thoughts"]) == 1


def test_cognition_config_endpoint_exposes_model_settings() -> None:
    """Config endpoint exposes active LLM settings."""
    response = client.get("/api/cognition/config")

    assert response.status_code == 200
    body = response.json()
    assert body["llm_provider"] == "ollama"
    assert body["ollama_model"] == "gemma:2b"
