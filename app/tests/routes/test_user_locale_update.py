"""PUT /users/me locale validation."""

from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, oauth2_scheme

# Needs live Postgres (TestClient triggers DB pool init via unmocked code paths).
# Excluded from unit test job by -m "not database"; runs in acceptance (Newman).
pytestmark = pytest.mark.database


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
