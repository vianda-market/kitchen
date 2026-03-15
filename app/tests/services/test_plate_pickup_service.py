"""
Simplified unit tests for Plate Pickup Service.

Tests the core business logic with focused, isolated tests.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import UUID, uuid4
from datetime import datetime
from fastapi import HTTPException

from app.services.plate_pickup_service import PlatePickupService, plate_pickup_service
from app.config import Status


class TestPlatePickupServiceSimple:
    """Simplified test suite for PlatePickupService business logic."""

    def test_scan_qr_code_validates_pickup_record_ownership(self, sample_current_user, mock_db):
        """Test that QR code scan validates pickup record belongs to current user."""
        # Arrange
        pickup_id = uuid4()
        qr_code_id = uuid4()
        wrong_user_id = uuid4()
        
        # Mock pickup record with different user
        mock_pickup = Mock()
        mock_pickup.user_id = wrong_user_id
        mock_pickup.status = Status.PENDING
        
        with patch('app.services.plate_pickup_service.plate_pickup_live_service') as mock_service:
            mock_service.get_by_id.return_value = mock_pickup
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                plate_pickup_service.scan_qr_code(pickup_id, qr_code_id, sample_current_user, mock_db)
            
            assert exc_info.value.status_code == 403
            assert "Not authorized" in str(exc_info.value.detail)

    def test_scan_qr_code_validates_pickup_record_not_found(self, sample_current_user, mock_db):
        """Test that QR code scan handles pickup record not found."""
        # Arrange
        pickup_id = uuid4()
        qr_code_id = uuid4()
        
        with patch('app.services.plate_pickup_service.plate_pickup_live_service') as mock_service:
            mock_service.get_by_id.return_value = None
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                plate_pickup_service.scan_qr_code(pickup_id, qr_code_id, sample_current_user, mock_db)
            
            assert exc_info.value.status_code == 404
            assert "Pickup record with ID" in str(exc_info.value.detail)

    def test_scan_qr_code_validates_qr_code_not_found(self, sample_current_user, mock_db):
        """Test that QR code scan handles QR code not found."""
        # Arrange
        pickup_id = uuid4()
        qr_code_payload = "restaurant_id:12345678-1234-1234-1234-1234567890ab"  # QR code payload string
        
        # Mock valid pickup record
        mock_pickup = Mock()
        mock_pickup.user_id = sample_current_user["user_id"]
        mock_pickup.status = Status.PENDING
        
        with patch('app.services.plate_pickup_service.plate_pickup_live_service') as mock_pickup_service, \
             patch.object(plate_pickup_service, '_validate_qr_code_by_payload') as mock_validate_qr:
            
            mock_pickup_service.get_by_id.return_value = mock_pickup
            # QR code validation raises exception when not found
            from fastapi import HTTPException
            mock_validate_qr.side_effect = HTTPException(status_code=400, detail="This QR code is not recognized")
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                plate_pickup_service.scan_qr_code(pickup_id, qr_code_payload, sample_current_user, mock_db)
            
            assert exc_info.value.status_code == 400
            assert "This QR code is not recognized" in str(exc_info.value.detail)

    def test_complete_order_validates_pickup_record_not_found(self, sample_current_user, mock_db):
        """Test that order completion handles pickup record not found."""
        # Arrange
        pickup_id = uuid4()
        
        with patch('app.services.plate_pickup_service.plate_pickup_live_service') as mock_service:
            mock_service.get_by_id.return_value = None
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                plate_pickup_service.complete_order(pickup_id, sample_current_user, mock_db)
            
            assert exc_info.value.status_code == 404
            assert "Pickup record with ID" in str(exc_info.value.detail)

    def test_complete_order_validates_user_authorization(self, sample_current_user, mock_db):
        """Test that order completion validates user authorization."""
        # Arrange
        pickup_id = uuid4()
        wrong_user_id = uuid4()
        
        # Mock pickup record with different user
        mock_pickup = Mock()
        mock_pickup.user_id = wrong_user_id
        mock_pickup.status = Status.ARRIVED
        
        with patch('app.services.plate_pickup_service.plate_pickup_live_service') as mock_service:
            mock_service.get_by_id.return_value = mock_pickup
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                plate_pickup_service.complete_order(pickup_id, sample_current_user, mock_db)
            
            assert exc_info.value.status_code == 403
            assert "Not authorized" in str(exc_info.value.detail)

    def test_complete_order_validates_status(self, sample_current_user, mock_db):
        """Test that order completion validates pickup record status."""
        # Arrange
        pickup_id = uuid4()
        
        # Mock pickup record with wrong status
        mock_pickup = Mock()
        mock_pickup.user_id = sample_current_user["user_id"]
        mock_pickup.status = Status.COMPLETED  # Wrong status for completion
        
        with patch('app.services.plate_pickup_service.plate_pickup_live_service') as mock_service:
            mock_service.get_by_id.return_value = mock_pickup
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                plate_pickup_service.complete_order(pickup_id, sample_current_user, mock_db)
            
            assert exc_info.value.status_code == 400
            # Error message should mention the status
            assert "status" in str(exc_info.value.detail).lower() or "complete" in str(exc_info.value.detail).lower()

    def test_delete_pickup_record_validates_not_found(self, sample_current_user, mock_db):
        """Test that pickup record deletion handles not found case."""
        # Arrange
        pickup_id = uuid4()
        
        with patch('app.services.plate_pickup_service.plate_pickup_live_service') as mock_service:
            mock_service.get_by_id.return_value = None
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                plate_pickup_service.delete_pickup_record(pickup_id, sample_current_user, mock_db)
            
            assert exc_info.value.status_code == 404
            assert "Pickup record with ID" in str(exc_info.value.detail)

    def test_delete_pickup_record_validates_user_authorization(self, sample_current_user, mock_db):
        """Test that pickup record deletion validates user authorization."""
        # Arrange
        pickup_id = uuid4()
        wrong_user_id = uuid4()
        
        # Mock pickup record with different user
        mock_pickup = Mock()
        mock_pickup.user_id = wrong_user_id
        mock_pickup.status = Status.PENDING
        
        with patch('app.services.plate_pickup_service.plate_pickup_live_service') as mock_service:
            mock_service.get_by_id.return_value = mock_pickup
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                plate_pickup_service.delete_pickup_record(pickup_id, sample_current_user, mock_db)
            
            assert exc_info.value.status_code == 403
            assert "Not authorized" in str(exc_info.value.detail)

    def test_delete_pickup_record_validates_status(self, sample_current_user, mock_db):
        """Test that pickup record deletion validates status is Pending."""
        # Arrange
        pickup_id = uuid4()
        
        # Mock pickup record with wrong status
        mock_pickup = Mock()
        mock_pickup.user_id = sample_current_user["user_id"]
        mock_pickup.status = Status.ARRIVED  # Wrong status for deletion
        
        with patch('app.services.plate_pickup_service.plate_pickup_live_service') as mock_service:
            mock_service.get_by_id.return_value = mock_pickup
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                plate_pickup_service.delete_pickup_record(pickup_id, sample_current_user, mock_db)
            
            assert exc_info.value.status_code == 400
            # Error message should mention the status
            assert "status" in str(exc_info.value.detail).lower() or "arrived" in str(exc_info.value.detail).lower()

    def test_delete_pickup_record_performs_soft_delete(self, sample_current_user, mock_db):
        """Test that pickup record deletion performs soft delete operation."""
        # Arrange
        pickup_id = uuid4()
        
        # Mock valid pickup record
        mock_pickup = Mock()
        mock_pickup.user_id = sample_current_user["user_id"]
        mock_pickup.status = Status.PENDING  # Valid status for deletion
        
        with patch('app.services.plate_pickup_service.plate_pickup_live_service') as mock_service:
            mock_service.get_by_id.return_value = mock_pickup
            mock_service.soft_delete.return_value = 1  # Successfully deleted
            
            # Act
            result = plate_pickup_service.delete_pickup_record(pickup_id, sample_current_user, mock_db)
            
            # Assert
            assert result["detail"] == "Plate pickup record deleted successfully"
            mock_service.soft_delete.assert_called_once_with(pickup_id, sample_current_user["user_id"], mock_db)

    def test_validate_qr_code_handles_not_found(self, mock_db):
        """Test that QR code validation handles not found case."""
        # Arrange
        qr_code_id = uuid4()
        
        with patch('app.services.plate_pickup_service.qr_code_service') as mock_service:
            mock_service.get_by_id.return_value = None
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                plate_pickup_service._validate_qr_code(qr_code_id, mock_db)
            
            assert exc_info.value.status_code == 400
            assert "This QR code is not recognized" in str(exc_info.value.detail)

    def test_get_plate_delivery_info_handles_plate_selection_not_found(self, mock_db):
        """Test that plate delivery info retrieval handles plate selection not found."""
        # Arrange
        mock_pickup = Mock()
        mock_pickup.plate_selection_id = uuid4()
        
        with patch('app.services.plate_pickup_service.plate_selection_service') as mock_service:
            mock_service.get_by_id.return_value = None
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                plate_pickup_service._get_plate_delivery_info(mock_pickup, mock_db)
            
            assert exc_info.value.status_code == 404
            assert "Plate selection not found" in str(exc_info.value.detail)

    def test_get_plate_delivery_info_handles_plate_not_found(self, mock_db):
        """Test that plate delivery info retrieval handles plate not found."""
        # Arrange
        mock_pickup = Mock()
        mock_pickup.plate_selection_id = uuid4()
        mock_plate_selection = Mock()
        mock_plate_selection.plate_id = uuid4()
        
        with patch('app.services.plate_pickup_service.plate_selection_service') as mock_plate_selection_service, \
             patch('app.services.plate_pickup_service.plate_service') as mock_plate_service:
            
            mock_plate_selection_service.get_by_id.return_value = mock_plate_selection
            mock_plate_service.get_by_id.return_value = None
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                plate_pickup_service._get_plate_delivery_info(mock_pickup, mock_db)
            
            assert exc_info.value.status_code == 404
            assert "Plate not found" in str(exc_info.value.detail)
