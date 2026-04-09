"""PUT /users/me locale validation."""

from uuid import uuid4

from fastapi.testclient import TestClient

from application import app
from app.auth.dependencies import get_current_user, oauth2_scheme


def test_put_me_invalid_locale_returns_422():
    def _user():
        return {
            "user_id": uuid4(),
            "role_type": "internal",
            "role_name": "admin",
            "institution_id": uuid4(),
        }

    def _token():
        return "test-token"

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[oauth2_scheme] = _token
    try:
        with TestClient(app) as client:
            r = client.put("/api/v1/users/me", json={"locale": "xx"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(oauth2_scheme, None)

    assert r.status_code == 422
