import pytest
from fastapi.testclient import TestClient


def test_get_presets_returns_debaters():
    from main import app

    client = TestClient(app)

    response = client.get("/api/presets")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    # Preset names are in Chinese (see presets.yaml)
    assert data[0]["name"] == "正方"
    assert data[1]["name"] == "反方"
    assert data[2]["name"] == "分析家"


def test_get_root_serves_html():
    from main import app

    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_start_debate_validates_min_debaters():
    from main import app

    client = TestClient(app)

    response = client.post(
        "/api/debate/start", json={"topic": "Test topic", "debater_names": ["正方"]}
    )

    assert response.status_code == 400
