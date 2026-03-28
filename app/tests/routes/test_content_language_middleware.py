"""X-Content-Language from Accept-Language (header-only middleware)."""

from fastapi.testclient import TestClient

from application import app


def test_root_response_includes_x_content_language():
    with TestClient(app) as client:
        r = client.get("/", headers={"Accept-Language": "es-AR"})
    assert r.headers.get("X-Content-Language") == "es"


def test_x_content_language_defaults_to_en_without_header():
    with TestClient(app) as client:
        r = client.get("/")
    assert r.headers.get("X-Content-Language") == "en"
