from fastapi.testclient import TestClient

import app as service


client = TestClient(service.app)


def test_health_is_public():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_playground_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "small_LLM" in response.text


def test_models_requires_configured_api_key(monkeypatch):
    monkeypatch.setattr(service, "API_KEYS", {"test-secret"})
    assert client.get("/v1/models").status_code == 401
    response = client.get("/v1/models", headers={"Authorization": "Bearer test-secret"})
    assert response.status_code == 200


def test_developer_api_returns_clear_setup_error(monkeypatch):
    monkeypatch.setattr(service, "API_KEYS", {"test-secret"})
    monkeypatch.setattr(service, "HF_TOKEN", "")
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-secret"},
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert response.status_code == 503
    assert "HF_TOKEN" in response.json()["detail"]


def test_streaming_is_rejected_explicitly(monkeypatch):
    monkeypatch.setattr(service, "API_KEYS", {"test-secret"})
    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test-secret"},
        json={"messages": [{"role": "user", "content": "Hello"}], "stream": True},
    )
    assert response.status_code == 400
