"""
Tests for kitchen start promotion service and cron.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4, UUID

from app.services.plate_selection_promotion_service import promote_plate_selection_to_live


class TestPromotePlateSelectionToLive:
    """Tests for promote_plate_selection_to_live."""

    def test_promote_returns_none_when_selection_not_found(self, mock_db):
        """When plate selection is not found or archived, returns None."""
        plate_selection_id = uuid4()
        with patch('app.services.plate_selection_promotion_service.plate_selection_service') as mock_svc:
            mock_svc.get_by_id_non_archived.return_value = None
            result = promote_plate_selection_to_live(
                plate_selection_id, uuid4(), mock_db, commit=False
            )
        assert result is None

    def test_promote_returns_existing_plate_pickup_id_when_already_promoted(self, mock_db):
        """When selection already has plate_pickup_live, returns existing id (idempotent)."""
        plate_selection_id = uuid4()
        existing_pickup_id = uuid4()
        mock_selection = Mock()
        mock_selection.plate_selection_id = plate_selection_id
        mock_selection.plate_id = uuid4()
        mock_selection.restaurant_id = uuid4()
        mock_selection.user_id = uuid4()

        with patch('app.services.plate_selection_promotion_service.plate_selection_service') as mock_sel_svc, \
             patch('app.services.plate_selection_promotion_service.db_read') as mock_db_read:
            mock_sel_svc.get_by_id_non_archived.return_value = mock_selection
            mock_db_read.return_value = {"plate_pickup_id": str(existing_pickup_id)}

            result = promote_plate_selection_to_live(
                plate_selection_id, uuid4(), mock_db, commit=False
            )
        assert result == existing_pickup_id

    def test_promote_returns_none_when_insufficient_credits(self, mock_db):
        """When user has insufficient credits at promotion time, skip and return None."""
        plate_selection_id = uuid4()
        mock_selection = Mock()
        mock_selection.plate_selection_id = plate_selection_id
        mock_selection.plate_id = uuid4()
        mock_selection.restaurant_id = uuid4()
        mock_selection.user_id = uuid4()

        mock_plate = Mock()
        mock_plate.plate_id = mock_selection.plate_id
        mock_plate.credit = 10.0
        mock_plate.restaurant_id = mock_selection.restaurant_id
        mock_plate.product_id = uuid4()

        mock_restaurant = Mock()
        mock_restaurant.restaurant_id = mock_selection.restaurant_id
        mock_restaurant.institution_id = uuid4()

        mock_institution = Mock()

        mock_supplier_terms = Mock()
        mock_supplier_terms.no_show_discount = 0

        currency_metadata_id = uuid4()
        with patch('app.services.plate_selection_promotion_service.plate_selection_service') as mock_sel_svc, \
             patch('app.services.plate_selection_promotion_service.db_read') as mock_db_read, \
             patch('app.services.plate_selection_promotion_service.plate_service') as mock_plate_svc, \
             patch('app.services.plate_selection_promotion_service.restaurant_service') as mock_rest_svc, \
             patch('app.services.plate_selection_promotion_service.institution_service') as mock_inst_svc, \
             patch('app.services.plate_selection_promotion_service.supplier_terms_service') as mock_st_svc, \
             patch('app.services.plate_selection_promotion_service.qr_code_service') as mock_qr_svc, \
             patch('app.services.plate_selection_promotion_service.credit_currency_service') as mock_cc_svc, \
             patch('app.services.plate_selection_promotion_service.get_currency_metadata_id_for_restaurant', return_value=currency_metadata_id), \
             patch('app.services.plate_selection_promotion_service.validate_sufficient_credits') as mock_validate:
            mock_sel_svc.get_by_id_non_archived.return_value = mock_selection
            mock_db_read.return_value = None  # Not yet promoted
            mock_plate_svc.get_by_id.return_value = mock_plate
            mock_rest_svc.get_by_id.return_value = mock_restaurant
            mock_inst_svc.get_by_id.return_value = mock_institution
            mock_st_svc.get_by_field.return_value = mock_supplier_terms
            mock_qr_svc.get_by_restaurant.return_value = Mock(qr_code_id=uuid4(), qr_code_payload="test")
            mock_cc_svc.get_by_id.return_value = Mock(currency_metadata_id=uuid4(), currency_code="USD")

            from app.services.credit_validation_service import CreditValidationResult
            mock_validate.return_value = CreditValidationResult(
                has_sufficient_credits=False,
                current_balance=5.0,
                required_credits=10.0,
                remaining_balance_after_purchase=-5.0,
                shortfall=5.0,
                can_proceed=False,
                message="Insufficient credits",
            )

            result = promote_plate_selection_to_live(
                plate_selection_id, uuid4(), mock_db, commit=False
            )
        assert result is None
