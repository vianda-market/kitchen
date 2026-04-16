"""GET /api/v1/enums labeled response and language query validation."""

from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, oauth2_scheme


@pytest.fixture
def client_internal_enums():
    uid = uuid4()

    def _user():
        return {
            "user_id": uid,
            "role_type": "internal",
            "role_name": "admin",
            "institution_id": uuid4(),
        }

    def _token():
        return "test-token"

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[oauth2_scheme] = _token
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(oauth2_scheme, None)


def test_get_enums_rejects_invalid_language(client_internal_enums):
    r = client_internal_enums.get("/api/v1/enums", params={"language": "xx"})
    assert r.status_code == 422
    assert "Unsupported language" in r.json()["detail"]


def test_get_enums_spanish_street_type_label(client_internal_enums):
    r = client_internal_enums.get("/api/v1/enums", params={"language": "es"})
    assert r.status_code == 200
    data = r.json()
    st = data["street_type"]
    assert "values" in st and "labels" in st
    assert "st" in st["labels"]
    assert st["labels"]["st"] == "Calle"


def test_get_enums_unlabeled_enum_identity_map(client_internal_enums):
    """All enums now have labels. For labeled enums, labels map value→display (not identity)."""
    r = client_internal_enums.get("/api/v1/enums", params={"language": "en"})
    assert r.status_code == 200
    data = r.json()
    status = data["status"]
    assert status["values"]
    # All enum values are lowercase slugs; labels are Title Case display names
    assert "active" in status["values"]
    assert status["labels"]["active"] == "Active"
