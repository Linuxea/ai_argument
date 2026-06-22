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
    """min_length=2 is enforced at the Pydantic layer (422) before any route logic.

    Runs lifespan so ``app.state.engine`` is set (otherwise we'd hit the 503
    readiness guard first and never reach the model validator).
    """
    from main import app

    with TestClient(app):
        response = app.dependency_overrides  # no-op; lifespan ran on __enter__
        client = TestClient(app)
        response = client.post(
            "/api/debate/start", json={"topic": "Test topic", "debater_names": ["正方"]}
        )

    # min_length=2 enforced at the Pydantic layer → 422.
    assert response.status_code == 422
