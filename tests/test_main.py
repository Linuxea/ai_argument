import pytest
from fastapi.testclient import TestClient


def test_get_presets_returns_debaters():
    from main import app
    client = TestClient(app)

    response = client.get("/api/presets")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["name"] == "The Skeptic"


def test_get_root_serves_html():
    from main import app
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_start_debate_validates_min_debaters():
    from main import app
    client = TestClient(app)

    response = client.post("/api/debate/start", json={
        "topic": "Test topic",
        "debater_names": ["The Skeptic"]  # Only one debater
    })

    assert response.status_code == 400
