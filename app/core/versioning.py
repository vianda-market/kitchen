# app/core/versioning.py
"""
API Versioning Infrastructure

This module provides a flexible versioning system for the Kitchen API.
It supports multiple versioning strategies while maintaining backward compatibility.

Versioning Strategies:
1. URL Path Versioning: /api/v1/plans/
2. Header Versioning: Accept: application/vnd.kitchen.v1+json
3. Query Parameter Versioning: /api/plans/?version=1

Current Implementation:
- All APIs default to v1
- Infrastructure ready for v2+ when needed
- Backward compatibility maintained
"""

from enum import Enum

from fastapi import HTTPException, Request
from fastapi.routing import APIRouter


class APIVersion(str, Enum):
    """Supported API versions"""

    V1 = "v1"
    V2 = "v2"
    # Add more versions as needed


class VersioningStrategy(str, Enum):
    """Supported versioning strategies"""

    URL_PATH = "url_path"
    HEADER = "header"
    QUERY_PARAM = "query_param"


class VersionConfig:
    """Configuration for API versioning"""

    def __init__(
        self,
        default_version: APIVersion = APIVersion.V1,
        supported_versions: list[APIVersion] = None,
        strategy: VersioningStrategy = VersioningStrategy.URL_PATH,
        deprecated_versions: list[APIVersion] = None,
    ):
        self.default_version = default_version
        self.supported_versions = supported_versions or [APIVersion.V1]
        self.strategy = strategy
        self.deprecated_versions = deprecated_versions or []

    def is_version_supported(self, version: APIVersion) -> bool:
        """Check if a version is supported"""
        return version in self.supported_versions

    def is_version_deprecated(self, version: APIVersion) -> bool:
        """Check if a version is deprecated"""
        return version in self.deprecated_versions


# Global versioning configuration
VERSION_CONFIG = VersionConfig(
    default_version=APIVersion.V1,
    supported_versions=[APIVersion.V1],  # Only v1 supported initially
    strategy=VersioningStrategy.URL_PATH,
    deprecated_versions=[],
)


def get_version_from_request(request: Request) -> APIVersion:
    """
    Extract API version from request using configured strategy

    Args:
        request: FastAPI request object

    Returns:
        APIVersion: The requested API version

    Raises:
        HTTPException: If version is invalid or unsupported
    """
    version = None

    if VERSION_CONFIG.strategy == VersioningStrategy.URL_PATH:
        # Extract version from URL path: /api/v1/plans/ -> v1
        path_parts = request.url.path.split("/")
        for part in path_parts:
            if part.startswith("v") and part[1:].isdigit():
                try:
                    version = APIVersion(part)
                    break
                except ValueError:
                    continue

    elif VERSION_CONFIG.strategy == VersioningStrategy.HEADER:
        # Extract version from Accept header
        accept_header = request.headers.get("accept", "")
        if "vnd.kitchen.v" in accept_header:
            # Parse: application/vnd.kitchen.v1+json
            version_str = accept_header.split("vnd.kitchen.v")[1].split("+")[0]
            try:
                version = APIVersion(f"v{version_str}")
            except ValueError:
                pass

    elif VERSION_CONFIG.strategy == VersioningStrategy.QUERY_PARAM:
        # Extract version from query parameter
        version_param = request.query_params.get("version", request.query_params.get("v"))
        if version_param:
            try:
                version = APIVersion(f"v{version_param}")
            except ValueError:
                pass

    # Default to configured default version
    if version is None:
        version = VERSION_CONFIG.default_version

    # Validate version
    if not VERSION_CONFIG.is_version_supported(version):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported API version: {version}. Supported versions: {VERSION_CONFIG.supported_versions}",
        )

    # Check if version is deprecated
    if VERSION_CONFIG.is_version_deprecated(version):
        # Log deprecation warning but don't block request
        # In production, you might want to add deprecation headers
        pass

    return version


def create_versioned_router(prefix: str, tags: list[str], version: APIVersion = None) -> APIRouter:
    """
    Create a versioned router with appropriate prefix

    Args:
        prefix: Base prefix for the router (e.g., "plans")
        tags: OpenAPI tags for the router
        version: Specific version (defaults to V1 for backward compatibility)

    Returns:
        APIRouter: Configured router with version prefix
    """
    if version is None:
        version = APIVersion.V1

    # Create versioned prefix
    # Standard convention: /api/v1/... (prefix comes before version)
    if prefix:
        versioned_prefix = f"/{prefix}/{version.value}"
    else:
        versioned_prefix = f"/{version.value}"

    router = APIRouter(
        prefix=versioned_prefix,
        tags=tags,
    )

    return router


def add_version_info_to_response(data: dict, version: APIVersion) -> dict:
    """
    Add version information to API response

    Args:
        data: Response data
        version: API version used

    Returns:
        dict: Response data with version info
    """
    if isinstance(data, dict):
        data["_api_version"] = version.value
        data["_version_info"] = {
            "version": version.value,
            "is_deprecated": VERSION_CONFIG.is_version_deprecated(version),
        }

    return data


# Dependency for getting current API version
def get_current_version(request: Request) -> APIVersion:
    """FastAPI dependency to get current API version from request"""
    return get_version_from_request(request)


# Version-specific schema imports
def get_schema_for_version(schema_class, version: APIVersion):
    """
    Get the appropriate schema class for a given API version

    Args:
        schema_class: Base schema class
        version: API version

    Returns:
        Schema class for the specified version
    """
    # For now, all versions use the same schemas
    # In the future, you can implement version-specific schemas here
    return schema_class


# Example usage in route files:
"""
from app.core.versioning import create_versioned_router, get_current_version, APIVersion

# Create versioned router
router = create_versioned_router("plans", ["Plans"], APIVersion.V1)

@router.get("")
def get_plans(version: APIVersion = Depends(get_current_version)):
    # Handle version-specific logic
    pass
"""
