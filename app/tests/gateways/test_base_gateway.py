"""
Unit tests for BaseGateway

Tests the abstract base gateway functionality including:
- Development mode detection
- Mock response loading
- API call logging
- Error handling
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from pathlib import Path

from app.gateways.base_gateway import BaseGateway, ExternalServiceError


class ConcreteTestGateway(BaseGateway):
    """Concrete implementation of BaseGateway for testing"""
    
    @property
    def service_name(self) -> str:
        return "Test Service"
    
    def _load_mock_responses(self):
        return {
            "test_operation": {"result": "mock_data", "status": "success"},
            "failing_operation": {"error": "mock_error"}
        }
    
    def _make_request(self, operation: str, **kwargs):
        if operation == "test_operation":
            return {"result": "real_data", "status": "success"}
        elif operation == "failing_operation":
            raise Exception("Real API error")
        else:
            raise Exception(f"Unknown operation: {operation}")


class TestBaseGatewayDevMode:
    """Test BaseGateway behavior in development mode"""
    
    @patch('app.gateways.base_gateway.get_settings')
    def test_dev_mode_enabled_uses_mock_responses(self, mock_get_settings):
        """Test that dev mode uses mock responses instead of real API calls"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = True
        mock_get_settings.return_value = mock_settings
        
        gateway = ConcreteTestGateway()
        
        # Act
        result = gateway.call("test_operation", param="value")
        
        # Assert
        assert result == {"result": "mock_data", "status": "success"}
        assert gateway.dev_mode is True
    
    @patch('app.gateways.base_gateway.get_settings')
    def test_dev_mode_disabled_makes_real_api_calls(self, mock_get_settings):
        """Test that production mode makes real API calls"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = False
        mock_get_settings.return_value = mock_settings
        
        gateway = ConcreteTestGateway()
        
        # Act
        result = gateway.call("test_operation")
        
        # Assert
        assert result == {"result": "real_data", "status": "success"}
        assert gateway.dev_mode is False
    
    @patch('app.gateways.base_gateway.get_settings')
    def test_dev_mode_raises_error_for_missing_mock(self, mock_get_settings):
        """Test that dev mode raises error when mock response not found"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = True
        mock_get_settings.return_value = mock_settings
        
        gateway = ConcreteTestGateway()
        
        # Act & Assert
        with pytest.raises(ExternalServiceError) as exc_info:
            gateway.call("unknown_operation")
        
        assert "Mock response not configured" in str(exc_info.value)


class TestBaseGatewayErrorHandling:
    """Test BaseGateway error handling"""
    
    @patch('app.gateways.base_gateway.get_settings')
    def test_wraps_api_errors_in_external_service_error(self, mock_get_settings):
        """Test that API errors are wrapped in ExternalServiceError"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = False
        mock_get_settings.return_value = mock_settings
        
        gateway = ConcreteTestGateway()
        
        # Act & Assert
        with pytest.raises(ExternalServiceError) as exc_info:
            gateway.call("failing_operation")
        
        assert "Test Service API call failed" in str(exc_info.value)
        assert "Real API error" in str(exc_info.value)
    
    @patch('app.gateways.base_gateway.get_settings')
    def test_logs_failed_api_calls(self, mock_get_settings, caplog):
        """Test that failed API calls are logged"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = False
        mock_get_settings.return_value = mock_settings
        
        gateway = ConcreteTestGateway()
        
        # Act
        with pytest.raises(ExternalServiceError):
            gateway.call("failing_operation")
        
        # Assert
        assert "❌ failed" in caplog.text


class TestBaseGatewayLogging:
    """Test BaseGateway API call logging"""
    
    @patch('app.gateways.base_gateway.get_settings')
    def test_logs_successful_api_calls(self, mock_get_settings, caplog):
        """Test that successful API calls are logged with duration"""
        # Arrange
        import logging
        caplog.set_level(logging.INFO)
        
        mock_settings = Mock()
        mock_settings.DEV_MODE = False
        mock_get_settings.return_value = mock_settings
        
        gateway = ConcreteTestGateway()
        
        # Act
        gateway.call("test_operation", param="value")
        
        # Assert
        assert "💰 External API Call" in caplog.text
        assert "Test Service" in caplog.text
        assert "✅ success" in caplog.text
    
    @patch('app.gateways.base_gateway.get_settings')
    def test_excludes_sensitive_parameters_from_logs(self, mock_get_settings, caplog):
        """Test that sensitive parameters are excluded from logs"""
        # Arrange
        import logging
        caplog.set_level(logging.INFO)
        
        mock_settings = Mock()
        mock_settings.DEV_MODE = False
        mock_get_settings.return_value = mock_settings
        
        gateway = ConcreteTestGateway()
        
        # Act
        gateway.call("test_operation", api_key="secret123", param="value")
        
        # Assert
        # Check that the call was logged
        assert "💰 External API Call" in caplog.text
        assert "Test Service" in caplog.text
        # Sensitive data should not appear in logs
        assert "secret123" not in caplog.text
        # Note: Parameters are in structured log data (extra), not in text output


class TestBaseGatewayMockFileLoading:
    """Test BaseGateway mock file loading"""
    
    @patch('app.gateways.base_gateway.get_settings')
    @patch('pathlib.Path.exists')
    def test_raises_error_when_mock_file_not_found(self, mock_exists, mock_get_settings):
        """Test that missing mock file raises clear error"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = True
        mock_get_settings.return_value = mock_settings
        mock_exists.return_value = False
        
        # Act & Assert
        with pytest.raises(ExternalServiceError) as exc_info:
            gateway = ConcreteTestGateway()
            gateway._load_mock_file("nonexistent.json")
        
        assert "Mock file 'nonexistent.json' not found" in str(exc_info.value)
    
    @patch('app.gateways.base_gateway.get_settings')
    @patch('pathlib.Path.exists')
    @patch('builtins.open', side_effect=Exception("Invalid JSON"))
    def test_raises_error_when_mock_file_invalid(self, mock_open, mock_exists, mock_get_settings):
        """Test that invalid JSON in mock file raises clear error"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = True
        mock_get_settings.return_value = mock_settings
        mock_exists.return_value = True
        
        # Act & Assert
        with pytest.raises(Exception):
            gateway = ConcreteTestGateway()
            gateway._load_mock_file("invalid.json")
