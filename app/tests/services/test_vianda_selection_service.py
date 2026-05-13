"""
Unit tests for Vianda Selection Service.

Tests the business logic for vianda selection operations including
validation, transaction creation, and balance management.
"""

from typing import Any, cast
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.config import Status
from app.services.vianda_selection_service import (
    create_vianda_selection_with_transactions,
    update_vianda_selection,
)


class TestViandaSelectionService:
    """Test suite for Vianda Selection Service business logic."""

    def test_create_vianda_selection_with_transactions_handles_invalid_vianda_id(self, sample_current_user, mock_db):
        """Test that vianda selection creation handles invalid vianda ID format."""
        # Arrange
        invalid_payload = {"vianda_id": "invalid-uuid", "restaurant_id": str(uuid4()), "target_kitchen_day": "monday"}

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            create_vianda_selection_with_transactions(invalid_payload, sample_current_user, mock_db)

        assert exc_info.value.status_code == 400
        assert cast(dict[str, Any], exc_info.value.detail)["code"] == "database.invalid_uuid"

    def test_create_vianda_selection_with_transactions_handles_vianda_not_found(self, sample_current_user, mock_db):
        """Test that vianda selection creation handles vianda not found."""
        # Arrange
        payload = {"vianda_id": str(uuid4()), "restaurant_id": str(uuid4()), "target_kitchen_day": "monday"}

        with patch("app.services.vianda_selection_service.vianda_service") as mock_vianda_service:
            mock_vianda_service.get_by_id.return_value = None  # Vianda not found

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                create_vianda_selection_with_transactions(payload, sample_current_user, mock_db)

            assert exc_info.value.status_code == 404
            assert "Vianda not found" in str(exc_info.value.detail)

    def test_create_vianda_selection_with_transactions_handles_restaurant_not_found(self, sample_current_user, mock_db):
        """Test that vianda selection creation handles restaurant not found."""
        # Arrange
        payload = {"vianda_id": str(uuid4()), "restaurant_id": str(uuid4()), "target_kitchen_day": "monday"}

        mock_vianda = Mock()
        mock_vianda.vianda_id = uuid4()
        mock_vianda.restaurant_id = uuid4()

        with (
            patch("app.services.vianda_selection_service.vianda_service") as mock_vianda_service,
            patch("app.services.vianda_selection_service.restaurant_service") as mock_restaurant_service,
        ):
            mock_vianda_service.get_by_id.return_value = mock_vianda
            mock_restaurant_service.get_by_id.return_value = None  # Restaurant not found

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                create_vianda_selection_with_transactions(payload, sample_current_user, mock_db)

            assert exc_info.value.status_code == 404
            assert "Restaurant not found" in str(exc_info.value.detail)

    def test_create_vianda_selection_with_transactions_handles_qr_code_not_found(self, sample_current_user, mock_db):
        """Test that vianda selection creation handles QR code not found."""
        # Arrange
        payload = {"vianda_id": str(uuid4()), "restaurant_id": str(uuid4()), "target_kitchen_day": "monday"}

        mock_vianda = Mock()
        mock_vianda.vianda_id = uuid4()
        mock_vianda.restaurant_id = uuid4()

        mock_restaurant = Mock()
        mock_restaurant.restaurant_id = uuid4()
        mock_restaurant.institution_entity_id = uuid4()
        mock_restaurant.address_id = uuid4()  # Required for address lookup
        mock_restaurant.status = Status.ACTIVE  # Required for validation

        mock_entity = Mock()
        mock_entity.currency_metadata_id = uuid4()

        mock_address = Mock()
        mock_address.address_id = mock_restaurant.address_id
        mock_address.country = "USA"  # Required for kitchen day determination

        with (
            patch("app.services.vianda_selection_service.vianda_service") as mock_vianda_service,
            patch("app.services.vianda_selection_service.restaurant_service") as mock_restaurant_service,
            patch(
                "app.services.entity_service.get_currency_metadata_id_for_restaurant",
                return_value=mock_entity.currency_metadata_id,
            ),
            patch("app.services.crud_service.address_service") as mock_address_service,
            patch("app.services.vianda_selection_service.qr_code_service") as mock_qr_service,
        ):
            mock_vianda_service.get_by_id.return_value = mock_vianda
            mock_restaurant_service.get_by_id.return_value = mock_restaurant
            mock_address_service.get_by_id.return_value = mock_address
            mock_qr_service.get_by_restaurant.return_value = None  # QR code not found

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                create_vianda_selection_with_transactions(payload, sample_current_user, mock_db)

            assert exc_info.value.status_code == 404
            d = cast(dict[str, Any], exc_info.value.detail)
            assert d["code"] == "entity.not_found"
            assert d["params"]["entity"] == "QR code"

    def test_create_vianda_selection_with_transactions_handles_currency_not_found(self, sample_current_user, mock_db):
        """Test that vianda selection creation handles credit currency not found."""
        # Arrange
        payload = {"vianda_id": str(uuid4()), "restaurant_id": str(uuid4()), "target_kitchen_day": "monday"}

        mock_vianda = Mock()
        mock_vianda.vianda_id = uuid4()
        mock_vianda.restaurant_id = uuid4()

        mock_restaurant = Mock()
        mock_restaurant.restaurant_id = uuid4()
        mock_restaurant.institution_entity_id = uuid4()
        mock_restaurant.address_id = uuid4()  # Required for address lookup
        mock_restaurant.status = Status.ACTIVE  # Required for validation

        mock_entity = Mock()
        mock_entity.currency_metadata_id = uuid4()

        mock_address = Mock()
        mock_address.address_id = mock_restaurant.address_id
        mock_address.country = "USA"  # Required for kitchen day determination

        mock_qr_code = Mock()
        mock_qr_code.qr_code_id = uuid4()

        with (
            patch("app.services.vianda_selection_service.vianda_service") as mock_vianda_service,
            patch("app.services.vianda_selection_service.restaurant_service") as mock_restaurant_service,
            patch(
                "app.services.entity_service.get_currency_metadata_id_for_restaurant",
                return_value=mock_entity.currency_metadata_id,
            ),
            patch("app.services.crud_service.address_service") as mock_address_service,
            patch("app.services.vianda_selection_service.qr_code_service") as mock_qr_service,
            patch("app.services.vianda_selection_service.credit_currency_service") as mock_currency_service,
        ):
            mock_vianda_service.get_by_id.return_value = mock_vianda
            mock_restaurant_service.get_by_id.return_value = mock_restaurant
            mock_address_service.get_by_id.return_value = mock_address
            mock_qr_service.get_by_restaurant.return_value = mock_qr_code
            mock_currency_service.get_by_id.return_value = None  # Currency not found

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                create_vianda_selection_with_transactions(payload, sample_current_user, mock_db)

            assert exc_info.value.status_code == 404
            assert "Credit currency not found" in str(exc_info.value.detail)

    def test_create_vianda_selection_with_transactions_handles_creation_failure(self, sample_current_user, mock_db):
        """Test that vianda selection creation handles record creation failures."""
        # Arrange
        payload = {"vianda_id": str(uuid4()), "restaurant_id": str(uuid4()), "target_kitchen_day": "monday"}

        mock_vianda = Mock()
        mock_vianda.vianda_id = uuid4()
        mock_vianda.restaurant_id = uuid4()
        mock_vianda.credit = 5.0  # Required for credit validation

        mock_restaurant = Mock()
        mock_restaurant.restaurant_id = uuid4()
        mock_restaurant.institution_entity_id = uuid4()
        mock_restaurant.address_id = uuid4()  # Required for address lookup
        mock_restaurant.status = Status.ACTIVE  # Required for validation

        mock_entity = Mock()
        mock_entity.currency_metadata_id = uuid4()

        mock_address = Mock()
        mock_address.address_id = mock_restaurant.address_id
        mock_address.country = "USA"  # Required for kitchen day determination

        mock_qr_code = Mock()
        mock_qr_code.qr_code_id = uuid4()

        mock_currency = Mock()
        mock_currency.currency_metadata_id = uuid4()

        with (
            patch("app.services.vianda_selection_service.vianda_service") as mock_vianda_service,
            patch("app.services.vianda_selection_service.restaurant_service") as mock_restaurant_service,
            patch(
                "app.services.entity_service.get_currency_metadata_id_for_restaurant",
                return_value=mock_entity.currency_metadata_id,
            ),
            patch("app.services.crud_service.address_service") as mock_address_service,
            patch("app.services.vianda_selection_service.qr_code_service") as mock_qr_service,
            patch("app.services.vianda_selection_service.credit_currency_service") as mock_currency_service,
            patch("app.services.vianda_selection_service.vianda_selection_service") as mock_selection_service,
            patch("app.services.vianda_selection_service.determine_target_kitchen_day") as mock_determine_day,
            patch("app.services.vianda_selection_service.validate_sufficient_credits") as mock_validate_credits,
            patch("app.services.crud_service.vianda_kitchen_days_service") as mock_kitchen_days_service,
        ):
            mock_vianda_service.get_by_id.return_value = mock_vianda
            mock_restaurant_service.get_by_id.return_value = mock_restaurant
            mock_address_service.get_by_id.return_value = mock_address
            mock_qr_service.get_by_restaurant.return_value = mock_qr_code
            mock_currency_service.get_by_id.return_value = mock_currency
            mock_determine_day.return_value = "monday"
            mock_selection_service.create.return_value = None  # Creation failed
            # Mock kitchen days service (now accepts scope and include_archived)
            mock_kitchen_days_service.get_all.return_value = []

            # Mock credit validation to pass
            from app.services.credit_validation_service import CreditValidationResult

            mock_validate_credits.return_value = CreditValidationResult(
                has_sufficient_credits=True,
                current_balance=10.0,
                required_credits=5.0,
                remaining_balance_after_purchase=5.0,
                shortfall=0.0,
                can_proceed=True,
                message="Sufficient credits available",
            )

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                create_vianda_selection_with_transactions(payload, sample_current_user, mock_db)

            assert exc_info.value.status_code == 500
            # Error message might be from database or service layer
            error_detail = str(exc_info.value.detail)
            assert "Failed to create vianda selection" in error_detail or "Error executing query" in error_detail

    def test_create_vianda_selection_with_transactions_handles_exception(self, sample_current_user, mock_db):
        """Test that vianda selection creation handles exceptions gracefully."""
        # Arrange
        payload = {"vianda_id": str(uuid4()), "restaurant_id": str(uuid4()), "target_kitchen_day": "monday"}

        with patch("app.services.vianda_selection_service.vianda_service") as mock_vianda_service:
            mock_vianda_service.get_by_id.side_effect = Exception("Database error")

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                create_vianda_selection_with_transactions(payload, sample_current_user, mock_db)

            assert exc_info.value.status_code == 500
            # Error message might be from database or service layer
            error_detail = str(exc_info.value.detail)
            assert "Failed to create vianda selection" in error_detail or "Error executing query" in error_detail

    def test_create_vianda_selection_with_transactions_handles_missing_payload_key(self, sample_current_user, mock_db):
        """Test that vianda selection creation handles missing payload keys."""
        # Arrange
        payload = {
            # Missing vianda_id
            "restaurant_id": str(uuid4()),
            "target_kitchen_day": "monday",
        }

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            create_vianda_selection_with_transactions(payload, sample_current_user, mock_db)

        assert exc_info.value.status_code == 400
        assert cast(dict[str, Any], exc_info.value.detail)["code"] == "database.invalid_uuid"

    def test_create_vianda_selection_with_transactions_blocks_insufficient_credits(self, sample_current_user, mock_db):
        """Test that vianda selection is blocked when user has insufficient credits."""
        # Arrange
        payload = {"vianda_id": str(uuid4()), "restaurant_id": str(uuid4()), "target_kitchen_day": "monday"}

        mock_vianda = Mock()
        mock_vianda.vianda_id = uuid4()
        mock_vianda.restaurant_id = uuid4()
        mock_vianda.credit = 5.0  # Required credits

        mock_restaurant = Mock()
        mock_restaurant.restaurant_id = uuid4()
        mock_restaurant.institution_entity_id = uuid4()
        mock_restaurant.address_id = uuid4()  # Required for address lookup
        mock_restaurant.status = Status.ACTIVE  # Required for validation

        mock_entity = Mock()
        mock_entity.currency_metadata_id = uuid4()

        mock_address = Mock()
        mock_address.address_id = mock_restaurant.address_id
        mock_address.country = "USA"  # Required for kitchen day determination
        mock_address.country_code = "US"  # Required for holiday validation

        mock_qr_code = Mock()
        mock_qr_code.qr_code_id = uuid4()

        mock_currency = Mock()
        mock_currency.currency_metadata_id = uuid4()

        with (
            patch("app.services.vianda_selection_service.vianda_service") as mock_vianda_service,
            patch("app.services.vianda_selection_service.restaurant_service") as mock_restaurant_service,
            patch(
                "app.services.entity_service.get_currency_metadata_id_for_restaurant",
                return_value=mock_entity.currency_metadata_id,
            ),
            patch("app.services.crud_service.address_service") as mock_address_service,
            patch("app.services.vianda_selection_service.qr_code_service") as mock_qr_service,
            patch("app.services.vianda_selection_service.credit_currency_service") as mock_currency_service,
            patch("app.services.vianda_selection_service.determine_target_kitchen_day") as mock_determine_day,
            patch("app.services.vianda_selection_service.validate_sufficient_credits") as mock_validate_credits,
            patch("app.services.vianda_selection_service.get_effective_current_day") as mock_get_current_day,
            patch(
                "app.services.vianda_selection_service.validate_restaurant_status"
            ) as mock_validate_restaurant_status,
            patch("app.services.vianda_selection_service.validate_restaurant"),
            patch("app.services.vianda_selection_service.db_read") as mock_db_read,
            patch("app.services.vianda_selection_service.subscription_service") as mock_subscription_service,
            patch("app.services.crud_service.vianda_kitchen_days_service") as mock_kitchen_days_service,
        ):
            mock_vianda_service.get_by_id.return_value = mock_vianda
            mock_restaurant_service.get_by_id.return_value = mock_restaurant
            mock_address_service.get_by_id.return_value = mock_address
            mock_qr_service.get_by_restaurant.return_value = mock_qr_code
            mock_currency_service.get_by_id.return_value = mock_currency
            mock_determine_day.return_value = "monday"
            mock_get_current_day.return_value = "monday"
            mock_validate_restaurant_status.return_value = None  # No exception means validation passed

            mock_db_read.return_value = None  # No existing vianda selection for this kitchen day
            mock_subscription_service.get_by_user.return_value = None  # Skip low-balance renewal check
            # Mock kitchen days service (now accepts scope and include_archived)
            mock_kitchen_days_service.get_all.return_value = []

            # Mock credit validation to fail (insufficient credits)
            from app.services.credit_validation_service import CreditValidationResult

            mock_validate_credits.return_value = CreditValidationResult(
                has_sufficient_credits=False,
                current_balance=3.0,
                required_credits=5.0,
                remaining_balance_after_purchase=-2.0,
                shortfall=2.0,
                can_proceed=False,
                message="Insufficient credits",
            )

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                create_vianda_selection_with_transactions(payload, sample_current_user, mock_db)

            assert exc_info.value.status_code == 402  # Payment Required
            error_detail = cast(dict[str, Any], exc_info.value.detail)
            assert error_detail["error_type"] == "insufficient_credits"
            assert error_detail["current_balance"] == 3.0
            assert error_detail["required_credits"] == 5.0
            assert error_detail["shortfall"] == 2.0
            assert error_detail["retry_after_payment"] is True
            assert "payment page" in error_detail["payment_instructions"]

    def test_create_vianda_selection_with_transactions_allows_exact_credits(self, sample_current_user, mock_db):
        """Test that vianda selection is allowed when user has exactly enough credits (resulting in 0 balance)."""
        # Arrange
        payload = {"vianda_id": str(uuid4()), "restaurant_id": str(uuid4()), "target_kitchen_day": "monday"}

        mock_vianda = Mock()
        mock_vianda.vianda_id = uuid4()
        mock_vianda.restaurant_id = uuid4()
        mock_vianda.credit = 5.0  # Required credits

        mock_restaurant = Mock()
        mock_restaurant.restaurant_id = uuid4()
        mock_restaurant.institution_entity_id = uuid4()
        mock_restaurant.address_id = uuid4()  # Required for address lookup
        mock_restaurant.status = Status.ACTIVE  # Required for validation

        mock_entity = Mock()
        mock_entity.currency_metadata_id = uuid4()

        mock_address = Mock()
        mock_address.address_id = mock_restaurant.address_id
        mock_address.country = "USA"  # Required for kitchen day determination

        mock_qr_code = Mock()
        mock_qr_code.qr_code_id = uuid4()

        mock_currency = Mock()
        mock_currency.currency_metadata_id = uuid4()

        mock_selection = Mock()
        mock_selection.vianda_selection_id = uuid4()

        with (
            patch("app.services.vianda_selection_service.vianda_service") as mock_vianda_service,
            patch("app.services.vianda_selection_service.restaurant_service") as mock_restaurant_service,
            patch(
                "app.services.entity_service.get_currency_metadata_id_for_restaurant",
                return_value=mock_entity.currency_metadata_id,
            ),
            patch("app.services.crud_service.address_service") as mock_address_service,
            patch("app.services.vianda_selection_service.qr_code_service") as mock_qr_service,
            patch("app.services.vianda_selection_service.credit_currency_service") as mock_currency_service,
            patch("app.services.vianda_selection_service.vianda_selection_service") as mock_selection_service,
            patch("app.services.vianda_selection_service.determine_target_kitchen_day") as mock_determine_day,
            patch("app.services.vianda_selection_service.validate_sufficient_credits") as mock_validate_credits,
            patch("app.services.vianda_selection_service.get_effective_current_day") as mock_get_current_day,
            patch(
                "app.services.vianda_selection_service.validate_restaurant_status"
            ) as mock_validate_restaurant_status,
            patch("app.services.vianda_selection_service.validate_restaurant"),
            patch("app.services.vianda_selection_service.db_read") as mock_db_read,
            patch("app.services.vianda_selection_service.subscription_service") as mock_subscription_service,
            patch("app.services.crud_service.vianda_kitchen_days_service") as mock_kitchen_days_service,
        ):
            mock_vianda_service.get_by_id.return_value = mock_vianda
            mock_restaurant_service.get_by_id.return_value = mock_restaurant
            mock_address_service.get_by_id.return_value = mock_address
            mock_qr_service.get_by_restaurant.return_value = mock_qr_code
            mock_currency_service.get_by_id.return_value = mock_currency
            mock_determine_day.return_value = "monday"
            mock_get_current_day.return_value = "monday"
            mock_validate_restaurant_status.return_value = None  # No exception means validation passed

            mock_db_read.return_value = None  # No existing vianda selection for this kitchen day
            mock_subscription_service.get_by_user.return_value = None  # Skip low-balance renewal check
            mock_selection_service.create.return_value = mock_selection
            # Mock kitchen days service (now accepts scope and include_archived)
            mock_kitchen_days_service.get_all.return_value = []

            # Mock credit validation to pass with exact credits (resulting in 0 balance)
            from app.services.credit_validation_service import CreditValidationResult

            mock_validate_credits.return_value = CreditValidationResult(
                has_sufficient_credits=True,
                current_balance=5.0,  # Exactly enough
                required_credits=5.0,
                remaining_balance_after_purchase=0.0,  # Will result in 0 balance
                shortfall=0.0,
                can_proceed=True,
                message="Sufficient credits available",
            )

            # Act
            selection, vianda_pickup_id = create_vianda_selection_with_transactions(
                payload, sample_current_user, mock_db
            )

            # Assert
            assert selection == mock_selection
            assert vianda_pickup_id is None  # vianda_pickup created at kitchen_start via promotion cron
            mock_validate_credits.assert_called_once_with(
                sample_current_user["user_id"],
                5.0,  # vianda.credit
                mock_db,
            )
            # Client transaction and subscription balance deferred to promotion at kitchen_start

    def test_create_vianda_selection_with_transactions_rejects_duplicate_kitchen_day(
        self, sample_current_user, mock_db
    ):
        """Test that creating a second vianda selection for the same kitchen_day returns 409 Conflict."""
        # Arrange
        payload = {"vianda_id": str(uuid4()), "restaurant_id": str(uuid4()), "target_kitchen_day": "monday"}

        mock_vianda = Mock()
        mock_vianda.vianda_id = uuid4()
        mock_vianda.restaurant_id = uuid4()
        mock_vianda.credit = 5.0

        mock_restaurant = Mock()
        mock_restaurant.restaurant_id = uuid4()
        mock_restaurant.institution_entity_id = uuid4()
        mock_restaurant.address_id = uuid4()
        mock_restaurant.status = Status.ACTIVE

        mock_entity = Mock()
        mock_entity.currency_metadata_id = uuid4()

        mock_address = Mock()
        mock_address.address_id = mock_restaurant.address_id
        mock_address.country_code = None  # Avoid validate_restaurant holiday DB call
        mock_address.country = "USA"

        mock_qr_code = Mock()
        mock_qr_code.qr_code_id = uuid4()

        mock_currency = Mock()
        mock_currency.currency_metadata_id = uuid4()

        with (
            patch("app.services.vianda_selection_service.vianda_service") as mock_vianda_service,
            patch("app.services.vianda_selection_service.restaurant_service") as mock_restaurant_service,
            patch(
                "app.services.entity_service.get_currency_metadata_id_for_restaurant",
                return_value=mock_entity.currency_metadata_id,
            ),
            patch("app.services.crud_service.address_service") as mock_address_service,
            patch("app.services.vianda_selection_service.qr_code_service") as mock_qr_service,
            patch("app.services.vianda_selection_service.credit_currency_service") as mock_currency_service,
            patch("app.services.vianda_selection_service.determine_target_kitchen_day") as mock_determine_day,
            patch("app.services.vianda_selection_service.db_read") as mock_db_read,
            patch("app.services.vianda_selection_service.get_effective_current_day") as mock_get_current_day,
            patch("app.services.vianda_selection_service.validate_restaurant"),
            patch(
                "app.services.vianda_selection_service.validate_restaurant_status"
            ) as mock_validate_restaurant_status,
            patch("app.services.crud_service.vianda_kitchen_days_service") as mock_kitchen_days_service,
        ):
            mock_vianda_service.get_by_id.return_value = mock_vianda
            mock_restaurant_service.get_by_id.return_value = mock_restaurant
            mock_address_service.get_by_id.return_value = mock_address
            mock_qr_service.get_by_restaurant.return_value = mock_qr_code
            mock_currency_service.get_by_id.return_value = mock_currency
            mock_determine_day.return_value = "monday"
            mock_get_current_day.return_value = "monday"
            mock_validate_restaurant_status.return_value = None

            mock_kitchen_days_service.get_all.return_value = []

            # Simulate user already has a vianda selection for Monday (db_read returns dict with vianda_selection_id)
            existing_id = str(uuid4())
            mock_db_read.return_value = {"vianda_selection_id": existing_id}

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                create_vianda_selection_with_transactions(payload, sample_current_user, mock_db)

            assert exc_info.value.status_code == 409
            detail = cast(dict[str, Any], exc_info.value.detail)
            assert isinstance(detail, dict)
            assert detail.get("code") == "vianda_selection.duplicate_kitchen_day"
            assert detail["params"].get("kitchen_day") == "monday"
            assert detail["params"].get("existing_vianda_selection_id") == existing_id
            assert "Continue to cancel your meal and reserve this vianda" in detail.get("message", "")

    def test_create_vianda_selection_replace_existing_success(self, sample_current_user, mock_db):
        """Test that replace_existing with valid existing_vianda_selection_id cancels old and creates new."""
        existing_id = str(uuid4())
        payload = {
            "vianda_id": str(uuid4()),
            "restaurant_id": str(uuid4()),
            "target_kitchen_day": "monday",
            "replace_existing": True,
            "existing_vianda_selection_id": existing_id,
        }

        mock_vianda = Mock()
        mock_vianda.vianda_id = uuid4()
        mock_vianda.restaurant_id = uuid4()
        mock_vianda.credit = 5.0

        mock_restaurant = Mock()
        mock_restaurant.restaurant_id = uuid4()
        mock_restaurant.institution_entity_id = uuid4()
        mock_restaurant.address_id = uuid4()
        mock_restaurant.status = Status.ACTIVE

        mock_entity = Mock()
        mock_entity.currency_metadata_id = uuid4()

        mock_address = Mock()
        mock_address.address_id = mock_restaurant.address_id
        mock_address.country_code = None
        mock_address.country = "USA"

        mock_qr_code = Mock()
        mock_qr_code.qr_code_id = uuid4()

        mock_currency = Mock()
        mock_currency.currency_metadata_id = uuid4()

        mock_selection = Mock()
        mock_selection.vianda_selection_id = uuid4()

        with (
            patch("app.services.vianda_selection_service.vianda_service") as mock_vianda_service,
            patch("app.services.vianda_selection_service.restaurant_service") as mock_restaurant_service,
            patch(
                "app.services.entity_service.get_currency_metadata_id_for_restaurant",
                return_value=mock_entity.currency_metadata_id,
            ),
            patch("app.services.crud_service.address_service") as mock_address_service,
            patch("app.services.vianda_selection_service.qr_code_service") as mock_qr_service,
            patch("app.services.vianda_selection_service.credit_currency_service") as mock_currency_service,
            patch("app.services.vianda_selection_service.determine_target_kitchen_day") as mock_determine_day,
            patch("app.services.vianda_selection_service.db_read") as mock_db_read,
            patch("app.services.vianda_selection_service.cancel_vianda_selection") as mock_cancel,
            patch("app.services.vianda_selection_service.validate_sufficient_credits") as mock_validate_credits,
            patch("app.services.vianda_selection_service.subscription_service") as mock_subscription_service,
            patch("app.services.vianda_selection_service.get_effective_current_day") as mock_get_current_day,
            patch("app.services.vianda_selection_service.validate_restaurant"),
            patch(
                "app.services.vianda_selection_service.validate_restaurant_status"
            ) as mock_validate_restaurant_status,
            patch("app.services.vianda_selection_service.vianda_selection_service") as mock_selection_service,
            patch("app.services.crud_service.vianda_kitchen_days_service") as mock_kitchen_days_service,
        ):
            mock_vianda_service.get_by_id.return_value = mock_vianda
            mock_subscription_service.get_by_user.return_value = None  # No subscription = skip early renewal
            mock_restaurant_service.get_by_id.return_value = mock_restaurant
            mock_address_service.get_by_id.return_value = mock_address
            mock_qr_service.get_by_restaurant.return_value = mock_qr_code
            mock_currency_service.get_by_id.return_value = mock_currency
            mock_determine_day.return_value = "monday"
            mock_get_current_day.return_value = "monday"
            mock_validate_restaurant_status.return_value = None

            mock_selection_service.create.return_value = mock_selection
            mock_kitchen_days_service.get_all.return_value = []

            mock_db_read.return_value = {"vianda_selection_id": existing_id}

            from app.services.credit_validation_service import CreditValidationResult

            mock_validate_credits.return_value = CreditValidationResult(
                has_sufficient_credits=True,
                current_balance=10.0,
                required_credits=5.0,
                remaining_balance_after_purchase=5.0,
                shortfall=0.0,
                can_proceed=True,
                message="Sufficient credits",
            )

            cancelled = Mock()
            cancelled.vianda_selection_id = UUID(existing_id)
            cancelled.user_id = sample_current_user["user_id"]
            cancelled.is_archived = True
            mock_cancel.return_value = cancelled

            selection, vianda_pickup_id = create_vianda_selection_with_transactions(
                payload, sample_current_user, mock_db
            )

            assert selection == mock_selection
            assert vianda_pickup_id is None
            mock_cancel.assert_called_once_with(UUID(existing_id), sample_current_user, mock_db, commit=False)

    def test_create_vianda_selection_replace_existing_wrong_id_returns_409(self, sample_current_user, mock_db):
        """Test that replace_existing with non-matching existing_vianda_selection_id returns 409."""
        actual_existing_id = str(uuid4())
        wrong_id = str(uuid4())
        payload = {
            "vianda_id": str(uuid4()),
            "restaurant_id": str(uuid4()),
            "target_kitchen_day": "monday",
            "replace_existing": True,
            "existing_vianda_selection_id": wrong_id,
        }

        mock_vianda = Mock()
        mock_vianda.vianda_id = uuid4()
        mock_vianda.restaurant_id = uuid4()
        mock_vianda.credit = 5.0

        mock_restaurant = Mock()
        mock_restaurant.restaurant_id = uuid4()
        mock_restaurant.institution_entity_id = uuid4()
        mock_restaurant.address_id = uuid4()
        mock_restaurant.status = Status.ACTIVE

        mock_entity = Mock()
        mock_entity.currency_metadata_id = uuid4()

        mock_address = Mock()
        mock_address.address_id = mock_restaurant.address_id
        mock_address.country_code = None
        mock_address.country = "USA"

        mock_qr_code = Mock()
        mock_qr_code.qr_code_id = uuid4()

        mock_currency = Mock()
        mock_currency.currency_metadata_id = uuid4()

        with (
            patch("app.services.vianda_selection_service.vianda_service") as mock_vianda_service,
            patch("app.services.vianda_selection_service.restaurant_service") as mock_restaurant_service,
            patch(
                "app.services.entity_service.get_currency_metadata_id_for_restaurant",
                return_value=mock_entity.currency_metadata_id,
            ),
            patch("app.services.crud_service.address_service") as mock_address_service,
            patch("app.services.vianda_selection_service.qr_code_service") as mock_qr_service,
            patch("app.services.vianda_selection_service.credit_currency_service") as mock_currency_service,
            patch("app.services.vianda_selection_service.determine_target_kitchen_day") as mock_determine_day,
            patch("app.services.vianda_selection_service.db_read") as mock_db_read,
            patch("app.services.vianda_selection_service.get_effective_current_day") as mock_get_current_day,
            patch("app.services.vianda_selection_service.validate_restaurant"),
            patch(
                "app.services.vianda_selection_service.validate_restaurant_status"
            ) as mock_validate_restaurant_status,
            patch("app.services.crud_service.vianda_kitchen_days_service") as mock_kitchen_days_service,
        ):
            mock_vianda_service.get_by_id.return_value = mock_vianda
            mock_restaurant_service.get_by_id.return_value = mock_restaurant
            mock_address_service.get_by_id.return_value = mock_address
            mock_qr_service.get_by_restaurant.return_value = mock_qr_code
            mock_currency_service.get_by_id.return_value = mock_currency
            mock_determine_day.return_value = "monday"
            mock_get_current_day.return_value = "monday"
            mock_validate_restaurant_status.return_value = None

            mock_kitchen_days_service.get_all.return_value = []

            mock_db_read.return_value = {"vianda_selection_id": actual_existing_id}

            with pytest.raises(HTTPException) as exc_info:
                create_vianda_selection_with_transactions(payload, sample_current_user, mock_db)

            assert exc_info.value.status_code == 409
            detail = cast(dict[str, Any], exc_info.value.detail)
            assert isinstance(detail, dict)
            assert detail.get("code") == "vianda_selection.duplicate_kitchen_day"
            assert detail["params"].get("existing_vianda_selection_id") == actual_existing_id


class TestUpdateViandaSelection:
    """Tests for update_vianda_selection (PATCH) validation. Only pickup_time_range, pickup_intent, flexible_on_time are editable."""

    def test_update_rejects_vianda_id_with_400(self, sample_current_user, mock_db):
        """PATCH with vianda_id returns 400. To change vianda, user must cancel and create new."""
        payload = {"vianda_id": str(uuid4()), "pickup_time_range": "12:00-12:15"}
        with pytest.raises(HTTPException) as exc_info:
            update_vianda_selection(uuid4(), payload, sample_current_user, mock_db)
        assert exc_info.value.status_code == 400
        assert "vianda_id" in str(exc_info.value.detail)
        assert "cancel" in str(exc_info.value.detail).lower()

    def test_update_rejects_kitchen_day_with_400(self, sample_current_user, mock_db):
        """PATCH with kitchen_day returns 400."""
        payload = {"kitchen_day": "tuesday", "pickup_intent": "self"}
        with pytest.raises(HTTPException) as exc_info:
            update_vianda_selection(uuid4(), payload, sample_current_user, mock_db)
        assert exc_info.value.status_code == 400
        assert "kitchen_day" in str(exc_info.value.detail)

    def test_update_rejects_target_kitchen_day_with_400(self, sample_current_user, mock_db):
        """PATCH with target_kitchen_day returns 400."""
        payload = {"target_kitchen_day": "tuesday", "pickup_intent": "self"}
        with pytest.raises(HTTPException) as exc_info:
            update_vianda_selection(uuid4(), payload, sample_current_user, mock_db)
        assert exc_info.value.status_code == 400
        assert "target_kitchen_day" in str(exc_info.value.detail)
