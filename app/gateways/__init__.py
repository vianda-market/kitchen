"""
External Service Gateways

This module provides a unified interface for interacting with external APIs.
All external service calls should go through these gateways to enable:
- Centralized logging for cost tracking
- Development mode with mock responses
- Consistent error handling
- Rate limiting and retry logic
"""

from app.gateways.base_gateway import BaseGateway
from app.gateways.google_maps_gateway import GoogleMapsGateway

__all__ = [
    "BaseGateway",
    "GoogleMapsGateway",
]
