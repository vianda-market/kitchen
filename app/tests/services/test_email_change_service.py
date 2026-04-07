"""Unit tests for email_change_service."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.config import Status, RoleType, RoleName
from app.dto.models import UserDTO
from app.services.email_change_service import email_change_service


@pytest.fixture
def sample_user():
    uid = uuid4()
    return UserDTO(
        user_id=uid,
        institution_id=uuid4(),
        role_type=RoleType.CUSTOMER,
        role_name=RoleName.COMENSAL,
        username="u1",
        hashed_password="h",
        first_name="A",
        last_name="B",
        email="old@example.com",
        mobile_number=None,
        mobile_number_verified=False,
        mobile_number_verified_at=None,
        email_verified=True,
        email_verified_at=datetime.now(timezone.utc),
        employer_id=None,
        employer_address_id=None,
        market_id=uuid4(),
        city_id=uuid4(),
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.now(timezone.utc),
        modified_by=uid,
        modified_date=datetime.now(timezone.utc),
    )


class TestEmailChangeService:
    def test_request_email_change_same_email_raises_400(self, sample_user):
        mock_db = MagicMock()
        with patch(
            "app.services.email_change_service.user_service.get_by_id",
            return_value=sample_user,
        ):
            with pytest.raises(HTTPException) as exc:
                email_change_service.request_email_change(
                    sample_user.user_id, "old@example.com", mock_db
                )
            assert exc.value.status_code == 400

    def test_request_email_change_duplicate_user_email_raises_409(self, sample_user):
        mock_db = MagicMock()
        other = MagicMock()
        other.user_id = uuid4()
        with patch(
            "app.services.email_change_service.user_service.get_by_id",
            return_value=sample_user,
        ), patch(
            "app.services.email_change_service.get_user_by_email",
            return_value=other,
        ):
            with pytest.raises(HTTPException) as exc:
                email_change_service.request_email_change(
                    sample_user.user_id, "taken@example.com", mock_db
                )
            assert exc.value.status_code == 409

    @patch("app.services.email_change_service.email_service.send_email_change_verification_email")
    @patch("app.services.email_change_service.get_user_by_email", return_value=None)
    @patch("app.services.email_change_service.user_service.get_by_id")
    def test_request_email_change_commits_after_send(
        self, mock_get_by_id, mock_get_by_email_unused, mock_send, sample_user
    ):
        mock_get_by_id.return_value = sample_user
        mock_send.return_value = True
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_db.cursor.return_value = mock_cursor

        email_change_service.request_email_change(
            sample_user.user_id, "new@example.com", mock_db
        )

        mock_send.assert_called_once()
        assert mock_cursor.execute.call_count >= 2
        mock_db.commit.assert_called()

    def test_verify_email_change_empty_code_raises_400(self):
        mock_db = MagicMock()
        with pytest.raises(HTTPException) as exc:
            email_change_service.verify_email_change(uuid4(), "   ", mock_db)
        assert exc.value.status_code == 400

    def test_verify_email_change_invalid_code_raises_400(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_db.cursor.return_value = mock_cursor

        with pytest.raises(HTTPException) as exc:
            email_change_service.verify_email_change(uuid4(), "999999", mock_db)
        assert exc.value.status_code == 400
        assert "Invalid" in str(exc.value.detail) or "expired" in str(exc.value.detail).lower()
