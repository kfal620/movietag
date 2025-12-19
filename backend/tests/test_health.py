from fastapi.testclient import TestClient

from app.main import create_application


def test_health_endpoint_returns_ok():
    app = create_application()
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "version" in payload
    assert "environment" in payload


def test_root_endpoint_includes_docs_link():
    app = create_application()
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"].startswith("Framegrab Tagger")
    assert payload["docs_url"].endswith("/docs")
