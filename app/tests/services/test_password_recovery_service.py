"""
Unit tests for Password Recovery Service.

Tests password reset flow including status transition to Active.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.password_recovery_service import password_recovery_service


class TestPasswordRecoveryService:
    """Test suite for PasswordRecoveryService."""

    @patch('app.services.password_recovery_service.hash_password')
    def test_reset_password_sets_user_status_to_active(self, mock_hash_password):
        """Test that reset_password sets user status to Active after successful password reset."""
        mock_hash_password.return_value = "hashed_new_password"
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = mock_cursor
        mock_cm.__exit__.return_value = False
        mock_db.cursor.return_value = mock_cm

        with patch.object(
            password_recovery_service,
            'validate_reset_code',
            return_value={
                'user_id': '11111111-1111-1111-1111-111111111111',
                'credential_recovery_id': '22222222-2222-2222-2222-222222222222',
            }
        ):
            result = password_recovery_service.reset_password(
                code="123456",
                new_password="NewSecurePass123!",
                db=mock_db
            )

        assert result["success"] is True
        assert "Password reset successful" in result["message"]

        # Verify UPDATE user_info was called with status = 'Active'
        execute_calls = mock_cursor.execute.call_args_list
        user_update_calls = [
            c for c in execute_calls
            if c.args and "user_info" in c.args[0] and "hashed_password" in c.args[0]
        ]
        assert len(user_update_calls) >= 1, "Expected UPDATE user_info to be called"
        update_sql = user_update_calls[0].args[0]
        assert "status" in update_sql and "Active" in update_sql
