"""
Unit tests for Messaging Preferences Service.

Tests get/update for preference toggles and cascade when can_participate_in_vianda_pickups is set to false.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.messaging_preferences_service import (
    get_messaging_preferences,
    update_messaging_preferences,
)


class TestMessagingPreferencesService:
    """Tests for messaging preferences get and update with new fields and cascade."""

    @patch("app.services.messaging_preferences_service.db_read")
    @patch("app.services.messaging_preferences_service.db_insert")
    def test_get_returns_default_row_with_new_fields_when_missing(self, mock_insert, mock_read):
        """When no row exists, default row includes coworkers_can_see_my_orders and can_participate_in_vianda_pickups."""
        user_id = uuid4()
        mock_read.side_effect = [
            None,  # First read: no row
            {
                "user_id": user_id,
                "notify_coworker_pickup_alert": True,
                "notify_vianda_readiness_alert": True,
                "notify_promotions_push": True,
                "notify_promotions_email": True,
                "coworkers_can_see_my_orders": True,
                "can_participate_in_vianda_pickups": True,
                "created_date": datetime.now(UTC),
                "modified_date": datetime.now(UTC),
            },
        ]
        mock_db = MagicMock()

        result = get_messaging_preferences(user_id, mock_db)

        assert result.coworkers_can_see_my_orders is True
        assert result.can_participate_in_vianda_pickups is True
        insert_call = mock_insert.call_args
        assert "coworkers_can_see_my_orders" in insert_call[0][1]
        assert "can_participate_in_vianda_pickups" in insert_call[0][1]
        assert insert_call[0][1]["coworkers_can_see_my_orders"] is True
        assert insert_call[0][1]["can_participate_in_vianda_pickups"] is True

    @patch("app.services.messaging_preferences_service.get_messaging_preferences")
    @patch("app.services.messaging_preferences_service.db_update")
    def test_update_can_participate_false_cascades_to_coworkers_and_notify(self, mock_update, mock_get):
        """When can_participate_in_vianda_pickups is set to False, cascade sets coworkers_can_see_my_orders and notify_coworker_pickup_alert to False."""
        user_id = uuid4()
        mock_get.return_value = MagicMock(
            coworkers_can_see_my_orders=True,
            can_participate_in_vianda_pickups=False,
            notify_coworker_pickup_alert=False,
        )
        mock_db = MagicMock()

        update_messaging_preferences(
            user_id,
            {"can_participate_in_vianda_pickups": False},
            mock_db,
        )

        call_kwargs = mock_update.call_args[0][1]
        assert call_kwargs["can_participate_in_vianda_pickups"] is False
        assert call_kwargs["coworkers_can_see_my_orders"] is False
        assert call_kwargs["notify_coworker_pickup_alert"] is False

    @patch("app.services.messaging_preferences_service.get_messaging_preferences")
    @patch("app.services.messaging_preferences_service.db_update")
    def test_update_new_fields_preserves_marketing_prefs_on_cascade(self, mock_update, mock_get):
        """Cascade when can_participate_in_vianda_pickups=False does not change marketing or vianda_ready prefs."""
        user_id = uuid4()
        mock_get.return_value = MagicMock(
            notify_promotions_push=True,
            notify_promotions_email=True,
            notify_vianda_readiness_alert=True,
            coworkers_can_see_my_orders=False,
            can_participate_in_vianda_pickups=False,
            notify_coworker_pickup_alert=False,
        )
        mock_db = MagicMock()

        update_messaging_preferences(
            user_id,
            {"can_participate_in_vianda_pickups": False},
            mock_db,
        )

        call_kwargs = mock_update.call_args[0][1]
        # Cascade fields
        assert "coworkers_can_see_my_orders" in call_kwargs
        assert "notify_coworker_pickup_alert" in call_kwargs
        # Marketing and vianda_ready not in update (not sent, not cascaded)
        assert "notify_promotions_push" not in call_kwargs
        assert "notify_promotions_email" not in call_kwargs
        assert "notify_vianda_readiness_alert" not in call_kwargs
