"""
Unit tests for Error Handling Service.

Tests the centralized error handling functions including
service call handling, database operations, and business operations.
"""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.error_handling import (
    handle_business_operation,
    handle_create,
    handle_database_operation,
    handle_delete,
    handle_get_all,
    handle_get_by_id,
    handle_service_call,
    handle_update,
)


class TestErrorHandlingService:
    """Test suite for Error Handling Service functions."""

    def test_handle_service_call_returns_result_on_success(self, mock_db):
        """Test that handle_service_call returns result when service succeeds."""

        # Arrange
        def mock_service():
            return "success_result"

        # Act
        result = handle_service_call(mock_service, "Error message")

        # Assert
        assert result == "success_result"

    def test_handle_service_call_raises_http_exception_on_error(self, mock_db):
        """Test that handle_service_call raises HTTPException when service fails."""

        # Arrange
        def mock_service():
            raise Exception("Service error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            handle_service_call(mock_service, "Error message")

        assert exc_info.value.status_code == 500
        detail = exc_info.value.detail
        if isinstance(detail, dict):
            assert detail.get("code") == "server.internal_error"
        else:
            assert "Error message" in str(detail)

    def test_handle_service_call_raises_http_exception_when_requested(self, mock_db):
        """Test that handle_service_call raises HTTPException when http_status provided."""

        # Arrange
        def mock_service():
            raise Exception("Service error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            handle_service_call(mock_service, "Error message", http_status=400)

        assert exc_info.value.status_code == 400
        detail = exc_info.value.detail
        if isinstance(detail, dict):
            assert detail.get("code") == "server.internal_error"
        else:
            assert "Error message" in str(detail)

    def test_handle_service_call_passes_arguments_correctly(self, mock_db):
        """Test that handle_service_call passes arguments to service function."""

        # Arrange
        def mock_service(arg1, arg2, kwarg1=None):
            return f"{arg1}_{arg2}_{kwarg1}"

        # Act
        result = handle_service_call(mock_service, "Error message", None, "value1", "value2", kwarg1="kwvalue")

        # Assert
        assert result == "value1_value2_kwvalue"

    def test_handle_database_operation_returns_result_on_success(self, mock_db):
        """Test that handle_database_operation returns result when operation succeeds."""

        # Arrange
        def mock_db_operation():
            return "db_result"

        # Act
        result = handle_database_operation(mock_db_operation, "DB error")

        # Assert
        assert result == "db_result"

    def test_handle_database_operation_raises_http_exception_on_error(self, mock_db):
        """Test that handle_database_operation raises HTTPException when operation fails."""

        # Arrange
        def mock_db_operation():
            raise Exception("Database error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            handle_database_operation(mock_db_operation, "DB error")

        assert exc_info.value.status_code == 500
        detail = exc_info.value.detail
        if isinstance(detail, dict):
            assert detail.get("code") == "server.internal_error"
        else:
            assert "Error DB error" in str(detail)

    def test_handle_business_operation_returns_result_on_success(self, mock_db):
        """Test that handle_business_operation returns result when operation succeeds."""

        # Arrange
        def mock_business_operation():
            return "business_result"

        # Act
        result = handle_business_operation(mock_business_operation, "Business error")

        # Assert
        assert result == "business_result"

    def test_handle_business_operation_raises_http_exception_on_error(self, mock_db):
        """Test that handle_business_operation raises HTTPException when operation fails."""

        # Arrange
        def mock_business_operation():
            raise Exception("Business error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            handle_business_operation(mock_business_operation, "Business error")

        assert exc_info.value.status_code == 500
        detail = exc_info.value.detail
        if isinstance(detail, dict):
            assert detail.get("code") == "server.internal_error"
        else:
            assert "Error in Business error" in str(detail)

    def test_handle_get_by_id_returns_result_on_success(self, mock_db):
        """Test that handle_get_by_id returns result when get operation succeeds."""
        # Arrange
        entity_id = uuid4()
        mock_entity = Mock()

        def mock_get_func(id, db):
            return mock_entity

        # Act
        result = handle_get_by_id(mock_get_func, entity_id, mock_db, "Entity not found")

        # Assert
        assert result == mock_entity

    def test_handle_get_by_id_raises_http_exception_when_not_found(self, mock_db):
        """Test that handle_get_by_id raises HTTPException when entity not found."""
        # Arrange
        entity_id = uuid4()

        def mock_get_func(id, db):
            return None

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            handle_get_by_id(mock_get_func, entity_id, mock_db, "Entity not found")

        assert exc_info.value.status_code == 404
        detail = exc_info.value.detail
        if isinstance(detail, dict):
            assert detail.get("code") == "entity.not_found"
        else:
            assert "Entity Not Found not found" in str(detail)

    def test_handle_get_all_returns_result_on_success(self, mock_db):
        """Test that handle_get_all returns result when get all operation succeeds."""
        # Arrange
        mock_entities = [Mock(), Mock(), Mock()]

        def mock_get_all_func(db):
            return mock_entities

        # Act
        result = handle_get_all(mock_get_all_func, mock_db, "Failed to get entities")

        # Assert
        assert result == mock_entities

    def test_handle_get_all_raises_http_exception_on_error(self, mock_db):
        """Test that handle_get_all raises HTTPException when operation fails."""

        # Arrange
        def mock_get_all_func(db):
            raise Exception("Database error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            handle_get_all(mock_get_all_func, mock_db, "Failed to get entities")

        assert exc_info.value.status_code == 500
        detail = exc_info.value.detail
        if isinstance(detail, dict):
            assert detail.get("code") == "server.internal_error"
        else:
            assert "Error retrieving Failed to get entities" in str(detail)

    def test_handle_create_returns_result_on_success(self, mock_db):
        """Test that handle_create returns result when create operation succeeds."""
        # Arrange
        mock_entity = Mock()
        create_data = {"name": "Test Entity"}

        def mock_create_func(data, db):
            return mock_entity

        # Act
        result = handle_create(mock_create_func, create_data, mock_db, "Failed to create entity")

        # Assert
        assert result == mock_entity

    def test_handle_create_raises_http_exception_on_error(self, mock_db):
        """Test that handle_create raises HTTPException when create operation fails."""
        # Arrange
        create_data = {"name": "Test Entity"}

        def mock_create_func(data, db):
            raise Exception("Create error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            handle_create(mock_create_func, create_data, mock_db, "Failed to create entity")

        assert exc_info.value.status_code == 500
        detail = exc_info.value.detail
        if isinstance(detail, dict):
            assert detail.get("code") == "server.internal_error"
        else:
            assert "Failed to create entity" in str(detail)

    def test_handle_update_returns_result_on_success(self, mock_db):
        """Test that handle_update returns result when update operation succeeds."""
        # Arrange
        entity_id = uuid4()
        update_data = {"name": "Updated Entity"}
        mock_updated_entity = Mock()

        def mock_update_func(id, data, db):
            return mock_updated_entity

        # Act
        result = handle_update(mock_update_func, entity_id, update_data, mock_db, "Failed to update entity")

        # Assert
        assert result == mock_updated_entity

    def test_handle_update_raises_http_exception_on_error(self, mock_db):
        """Test that handle_update raises HTTPException when update operation fails."""
        # Arrange
        entity_id = uuid4()
        update_data = {"name": "Updated Entity"}

        def mock_update_func(id, data, db):
            raise Exception("Update error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            handle_update(mock_update_func, entity_id, update_data, mock_db, "Failed to update entity")

        assert exc_info.value.status_code == 500
        detail = exc_info.value.detail
        if isinstance(detail, dict):
            assert detail.get("code") == "server.internal_error"
        else:
            assert "Failed to update entity" in str(detail)

    def test_handle_delete_returns_success_on_success(self, mock_db):
        """Test that handle_delete returns success when delete operation succeeds."""
        # Arrange
        entity_id = uuid4()

        def mock_delete_func(id, db):
            return True

        # Act
        result = handle_delete(mock_delete_func, entity_id, mock_db, "Failed to delete entity")

        # Assert
        assert result is True

    def test_handle_delete_raises_http_exception_on_error(self, mock_db):
        """Test that handle_delete raises HTTPException when delete operation fails."""
        # Arrange
        entity_id = uuid4()

        def mock_delete_func(id, db):
            raise Exception("Delete error")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            handle_delete(mock_delete_func, entity_id, mock_db, "Failed to delete entity")

        assert exc_info.value.status_code == 500
        detail = exc_info.value.detail
        if isinstance(detail, dict):
            assert detail.get("code") == "server.internal_error"
        else:
            assert "Failed to delete entity" in str(detail)

    def test_handle_service_call_logs_errors(self, mock_db):
        """Test that handle_service_call logs errors when they occur."""

        # Arrange
        def mock_service():
            raise Exception("Service error")

        with patch("app.services.error_handling.log_error") as mock_log_error:
            # Act & Assert
            with pytest.raises(HTTPException):
                handle_service_call(mock_service, "Error message")

            # Assert
            mock_log_error.assert_called_once()

    def test_handle_database_operation_logs_errors(self, mock_db):
        """Test that handle_database_operation logs errors when they occur."""

        # Arrange
        def mock_db_operation():
            raise Exception("Database error")

        with patch("app.services.error_handling.log_error") as mock_log_error:
            # Act & Assert
            with pytest.raises(HTTPException):
                handle_database_operation(mock_db_operation, "DB error")

            # Assert
            mock_log_error.assert_called_once()

    def test_handle_business_operation_logs_errors(self, mock_db):
        """Test that handle_business_operation logs errors when they occur."""

        # Arrange
        def mock_business_operation():
            raise Exception("Business error")

        with patch("app.services.error_handling.log_error") as mock_log_error:
            # Act & Assert
            with pytest.raises(HTTPException):
                handle_business_operation(mock_business_operation, "Business error")

            # Assert
            mock_log_error.assert_called_once()
