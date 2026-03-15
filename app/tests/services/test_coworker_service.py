"""
Unit tests for Coworker Service.

Tests eligibility logic and ineligibility_reason for the "Offer to pick up" flow.
"""

import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4, UUID

from app.services.coworker_service import get_coworkers_with_eligibility


class TestCoworkerServiceIneligibilityReason:
    """Tests for ineligibility_reason in get_coworkers_with_eligibility."""

    def _make_ps_row(self, kitchen_day="Monday", restaurant_id=None, pickup_time_range="12:00-12:15", employer_id=None, employer_address_id=None):
        return {
            "kitchen_day": kitchen_day,
            "restaurant_id": str(restaurant_id or uuid4()),
            "pickup_time_range": pickup_time_range,
            "employer_id": str(employer_id or uuid4()),
            "employer_address_id": str(employer_address_id) if employer_address_id else None,
        }

    def _make_owner_check(self, user_id):
        return {"user_id": user_id}

    def _make_coworker(self, user_id=None, first_name="Maria", last_name="Garcia"):
        return {
            "user_id": user_id or uuid4(),
            "first_name": first_name,
            "last_name": last_name,
        }

    def test_eligible_coworker_returns_ineligibility_reason_null(self, mock_db):
        """Eligible coworker (no existing plate_selection) has ineligibility_reason null."""
        current_user_id = uuid4()
        plate_selection_id = uuid4()
        coworker_id = uuid4()
        restaurant_id = uuid4()

        ps_row = self._make_ps_row(
            restaurant_id=restaurant_id,
            employer_id=uuid4(),
            employer_address_id=uuid4(),
        )
        owner_check = self._make_owner_check(current_user_id)
        coworkers = [self._make_coworker(user_id=coworker_id)]
        # No existing plate_selection for coworker -> eligible
        existing = None

        call_count = [0]

        def db_read_side_effect(sql, params, *, connection=None, fetch_one=False):
            call_count[0] += 1
            if fetch_one:
                if "plate_selection_info ps" in sql and "JOIN user_info" in sql:
                    return ps_row
                if "user_id FROM plate_selection_info" in sql and "plate_selection_id" in sql:
                    return owner_check
                if "user_id = %s AND kitchen_day = %s" in sql:
                    return existing
            else:
                return coworkers
            return None

        with patch("app.services.coworker_service.db_read", side_effect=db_read_side_effect):
            result = get_coworkers_with_eligibility(plate_selection_id, current_user_id, mock_db)

        assert len(result) == 1
        assert result[0]["eligible"] is True
        assert result[0]["ineligibility_reason"] is None

    def test_different_restaurant_returns_already_ordered_different_restaurant(self, mock_db):
        """Ineligible coworker (different restaurant) has ineligibility_reason already_ordered_different_restaurant."""
        current_user_id = uuid4()
        plate_selection_id = uuid4()
        coworker_id = uuid4()
        restaurant_a = uuid4()
        restaurant_b = uuid4()

        ps_row = self._make_ps_row(restaurant_id=restaurant_a)
        owner_check = self._make_owner_check(current_user_id)
        coworkers = [self._make_coworker(user_id=coworker_id)]
        existing = {"restaurant_id": restaurant_b, "pickup_time_range": "12:00-12:15"}  # same time, different restaurant

        def db_read_side_effect(sql, params, *, connection=None, fetch_one=False):
            if fetch_one:
                if "plate_selection_info ps" in sql and "JOIN user_info" in sql:
                    return ps_row
                if "user_id FROM plate_selection_info" in sql and "plate_selection_id" in sql:
                    return owner_check
                if "user_id = %s AND kitchen_day = %s" in sql:
                    return {"restaurant_id": restaurant_b, "pickup_time_range": "12:00-12:15"}
            else:
                return coworkers
            return None

        with patch("app.services.coworker_service.db_read", side_effect=db_read_side_effect):
            result = get_coworkers_with_eligibility(plate_selection_id, current_user_id, mock_db)

        assert len(result) == 1
        assert result[0]["eligible"] is False
        assert result[0]["ineligibility_reason"] == "already_ordered_different_restaurant"

    def test_different_pickup_time_returns_already_ordered_different_pickup_time(self, mock_db):
        """Ineligible coworker (same restaurant, different time) has ineligibility_reason already_ordered_different_pickup_time."""
        current_user_id = uuid4()
        plate_selection_id = uuid4()
        coworker_id = uuid4()
        restaurant_id = uuid4()

        ps_row = self._make_ps_row(restaurant_id=restaurant_id, pickup_time_range="12:00-12:15")
        owner_check = self._make_owner_check(current_user_id)
        coworkers = [self._make_coworker(user_id=coworker_id)]
        existing = {"restaurant_id": restaurant_id, "pickup_time_range": "12:15-12:30"}  # same restaurant, different time

        def db_read_side_effect(sql, params, *, connection=None, fetch_one=False):
            if fetch_one:
                if "plate_selection_info ps" in sql and "JOIN user_info" in sql:
                    return ps_row
                if "user_id FROM plate_selection_info" in sql and "plate_selection_id" in sql:
                    return owner_check
                if "user_id = %s AND kitchen_day = %s" in sql:
                    return existing
            else:
                return coworkers
            return None

        with patch("app.services.coworker_service.db_read", side_effect=db_read_side_effect):
            result = get_coworkers_with_eligibility(plate_selection_id, current_user_id, mock_db)

        assert len(result) == 1
        assert result[0]["eligible"] is False
        assert result[0]["ineligibility_reason"] == "already_ordered_different_pickup_time"

    def test_different_restaurant_and_time_returns_already_ordered_different_restaurant(self, mock_db):
        """Ineligible coworker (different restaurant and time) returns already_ordered_different_restaurant as primary."""
        current_user_id = uuid4()
        plate_selection_id = uuid4()
        coworker_id = uuid4()
        restaurant_a = uuid4()
        restaurant_b = uuid4()

        ps_row = self._make_ps_row(restaurant_id=restaurant_a, pickup_time_range="12:00-12:15")
        owner_check = self._make_owner_check(current_user_id)
        coworkers = [self._make_coworker(user_id=coworker_id)]
        existing = {"restaurant_id": restaurant_b, "pickup_time_range": "12:15-12:30"}

        def db_read_side_effect(sql, params, *, connection=None, fetch_one=False):
            if fetch_one:
                if "plate_selection_info ps" in sql and "JOIN user_info" in sql:
                    return ps_row
                if "user_id FROM plate_selection_info" in sql and "plate_selection_id" in sql:
                    return owner_check
                if "user_id = %s AND kitchen_day = %s" in sql:
                    return existing
            else:
                return coworkers
            return None

        with patch("app.services.coworker_service.db_read", side_effect=db_read_side_effect):
            result = get_coworkers_with_eligibility(plate_selection_id, current_user_id, mock_db)

        assert len(result) == 1
        assert result[0]["eligible"] is False
        assert result[0]["ineligibility_reason"] == "already_ordered_different_restaurant"

    def test_coworkers_with_can_participate_false_excluded_from_list(self, mock_db):
        """Coworkers with can_participate_in_plate_pickups=false are excluded from the list."""
        current_user_id = uuid4()
        plate_selection_id = uuid4()
        employer_id = uuid4()
        employer_address_id = uuid4()

        ps_row = self._make_ps_row(
            employer_id=employer_id,
            employer_address_id=employer_address_id,
        )
        owner_check = self._make_owner_check(current_user_id)
        # Coworker query returns empty because JOIN with user_messaging_preferences filters out opted-out users
        coworkers = []

        def db_read_side_effect(sql, params, *, connection=None, fetch_one=False):
            if fetch_one:
                if "plate_selection_info ps" in sql and "JOIN user_info" in sql:
                    return ps_row
                if "user_id FROM plate_selection_info" in sql and "plate_selection_id" in sql:
                    return owner_check
                if "user_id = %s AND kitchen_day = %s" in sql:
                    return None
            else:
                return coworkers
            return None

        with patch("app.services.coworker_service.db_read", side_effect=db_read_side_effect):
            result = get_coworkers_with_eligibility(plate_selection_id, current_user_id, mock_db)

        assert len(result) == 0
