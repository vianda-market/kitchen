"""POST /api/v1/auth/reset-password returns access_token after success."""

from unittest.mock import patch
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from application import app
from app.config.settings import settings
from app.dto.models import UserDTO
from app.config import RoleType, RoleName, Status
from datetime import datetime, timezone


@pytest.fixture
def reset_user_dto():
    uid = uuid4()
    return UserDTO(
        user_id=uid,
        institution_id=uuid4(),
        role_type=RoleType.CUSTOMER,
        role_name=RoleName.COMENSAL,
        username="u1",
        hashed_password="h",
        market_id=uuid4(),
        locale="es",
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.now(timezone.utc),
        modified_by=uid,
        modified_date=datetime.now(timezone.utc),
    )


def test_reset_password_response_includes_jwt_with_locale(reset_user_dto):
    with patch("app.routes.user_public.password_recovery_service") as svc:
        svc.reset_password.return_value = {
            "success": True,
            "message": "Password reset successful. You can now log in with your new password.",
            "user": reset_user_dto,
        }
        with TestClient(app) as client:
            r = client.post(
                "/api/v1/auth/reset-password",
                json={"code": "123456", "new_password": "NewSecurePass123!"},
            )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body.get("access_token")
    assert body.get("token_type") == "bearer"
    payload = jwt.decode(
        body["access_token"],
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    assert payload.get("locale") == "es"
    assert payload.get("sub") == str(reset_user_dto.user_id)
