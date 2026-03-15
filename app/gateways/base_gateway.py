"""
Base Gateway for External Service Calls

Provides common functionality for all external API gateways:
- Development mode support (mock responses)
- Centralized logging for cost tracking
- Error handling and retries
- Request/response validation
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class ExternalServiceError(Exception):
    """Raised when an external service call fails"""
    pass


class BaseGateway(ABC):
    """
    Base class for all external service gateways.
    
    Subclasses must implement:
    - service_name: str property
    - _load_mock_responses(): Load mock data for dev mode
    - _make_request(): Make the actual API call
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.dev_mode = self.settings.DEV_MODE
        self._mock_data: Optional[Dict[str, Any]] = None
        
        if self.dev_mode:
            logger.warning(f"🚧 {self.service_name} Gateway running in DEV_MODE - using mock responses")
            self._mock_data = self._load_mock_responses()
    
    @property
    @abstractmethod
    def service_name(self) -> str:
        """Human-readable name of the external service"""
        pass
    
    @abstractmethod
    def _load_mock_responses(self) -> Dict[str, Any]:
        """
        Load mock responses from JSON file for development mode.
        
        Returns:
            Dictionary of mock responses keyed by operation name
        """
        pass
    
    @abstractmethod
    def _make_request(self, operation: str, **kwargs) -> Any:
        """
        Make the actual API request to the external service.
        
        Args:
            operation: Name of the operation (e.g., 'geocode', 'reverse_geocode')
            **kwargs: Operation-specific parameters
            
        Returns:
            Raw response from the API
            
        Raises:
            ExternalServiceError: If the request fails
        """
        pass
    
    def call(self, operation: str, **kwargs) -> Any:
        """
        Main entry point for making external service calls.
        
        In DEV_MODE: Returns mock response
        In PROD_MODE: Makes real API call and logs for cost tracking
        
        Args:
            operation: Name of the operation to perform
            **kwargs: Operation-specific parameters
            
        Returns:
            Response data (mock or real)
            
        Raises:
            ExternalServiceError: If the request fails
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            if self.dev_mode:
                return self._get_mock_response(operation, **kwargs)
            else:
                response = self._make_request(operation, **kwargs)
                self._log_api_call(operation, start_time, success=True, **kwargs)
                return response
                
        except Exception as e:
            self._log_api_call(operation, start_time, success=False, error=str(e), **kwargs)
            raise ExternalServiceError(
                f"{self.service_name} API call failed for operation '{operation}': {str(e)}"
            ) from e
    
    def _get_mock_response(self, operation: str, **kwargs) -> Any:
        """
        Retrieve mock response for the given operation.
        
        Args:
            operation: Name of the operation
            **kwargs: Parameters (used for logging only)
            
        Returns:
            Mock response data
            
        Raises:
            ExternalServiceError: If mock data not found
        """
        if not self._mock_data or operation not in self._mock_data:
            logger.error(
                f"❌ Mock response not found for {self.service_name}.{operation}. "
                f"Available operations: {list(self._mock_data.keys()) if self._mock_data else 'none'}"
            )
            raise ExternalServiceError(
                f"Mock response not configured for operation '{operation}'"
            )
        
        logger.info(f"🎭 Returning mock response for {self.service_name}.{operation}")
        return self._mock_data[operation]
    
    def _log_api_call(
        self,
        operation: str,
        start_time: datetime,
        success: bool,
        error: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Log external API call for cost tracking and monitoring.
        
        Args:
            operation: Name of the operation performed
            start_time: When the call started
            success: Whether the call succeeded
            error: Error message if call failed
            **kwargs: Additional context (parameters, etc.)
        """
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        log_data = {
            "service": self.service_name,
            "operation": operation,
            "success": success,
            "duration_ms": round(duration_ms, 2),
            "timestamp": start_time.isoformat(),
        }
        
        if error:
            log_data["error"] = error
        
        # Include parameters for debugging (exclude sensitive data)
        safe_params = {k: v for k, v in kwargs.items() if k not in ['api_key', 'token', 'secret']}
        if safe_params:
            log_data["parameters"] = safe_params
        
        log_message = (
            f"💰 External API Call: {self.service_name}.{operation} "
            f"({'✅ success' if success else '❌ failed'}) "
            f"in {duration_ms:.2f}ms"
        )
        
        if success:
            logger.info(log_message, extra=log_data)
        else:
            logger.error(log_message, extra=log_data)
    
    def _load_mock_file(self, filename: str) -> Dict[str, Any]:
        """
        Helper to load mock data from JSON file.
        
        Args:
            filename: Name of the JSON file in app/mocks/
            
        Returns:
            Parsed JSON data
            
        Raises:
            ExternalServiceError: If file not found or invalid
        """
        mock_path = Path(__file__).parent.parent / "mocks" / filename
        
        if not mock_path.exists():
            logger.error(f"❌ Mock file not found: {mock_path}")
            raise ExternalServiceError(
                f"Mock file '{filename}' not found. Create it in app/mocks/"
            )
        
        try:
            with open(mock_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in mock file {filename}: {e}")
            raise ExternalServiceError(
                f"Invalid JSON in mock file '{filename}': {str(e)}"
            ) from e
