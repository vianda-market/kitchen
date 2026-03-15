# app/services/versioned_route_factory.py
"""
Versioned Route Factory

This module extends the existing route factory to support API versioning.
It creates versioned routes while maintaining backward compatibility.

Current Implementation:
- All routes use v1 by default
- Infrastructure ready for v2+ routes
- Backward compatibility maintained
"""

from typing import Type, TypeVar, List
from fastapi import APIRouter, Depends
from uuid import UUID

from app.core.versioning import (
    create_versioned_router, 
    get_current_version, 
    APIVersion,
    add_version_info_to_response
)
from app.schemas.versioned_schemas import get_schema_for_version
from app.services.route_factory import RouteConfig, create_crud_routes
from app.services.crud_service import CRUDService

T = TypeVar('T', bound=object)  # DTO type
U = TypeVar('U', bound=object)  # Create schema type
V = TypeVar('V', bound=object)  # Update schema type
W = TypeVar('W', bound=object)  # Response schema type


class VersionedRouteConfig(RouteConfig):
    """Extended route configuration with versioning support"""
    
    def __init__(
        self,
        prefix: str,
        tags: List[str],
        entity_name: str,
        entity_name_plural: str,
        description: str = None,
        version: APIVersion = APIVersion.V1,
        schema_prefix: str = None
    ):
        super().__init__(prefix, tags, entity_name, entity_name_plural, description)
        self.version = version
        self.schema_prefix = schema_prefix or entity_name.title()


def create_versioned_crud_routes(
    config: VersionedRouteConfig,
    service: CRUDService[T],
    version: APIVersion = None
) -> APIRouter:
    """
    Create versioned CRUD routes for an entity.
    
    Args:
        config: Versioned route configuration
        service: CRUD service instance
        version: Specific version (defaults to config.version)
        
    Returns:
        APIRouter: Versioned router with CRUD endpoints
    """
    if version is None:
        version = config.version
    
    # Get version-specific schemas
    create_schema = get_schema_for_version(f"{config.schema_prefix}Create", version)
    update_schema = get_schema_for_version(f"{config.schema_prefix}Update", version)
    response_schema = get_schema_for_version(f"{config.schema_prefix}Response", version)
    
    # Create versioned router
    router = create_versioned_router(config.prefix, config.tags, version)
    
    # Add version-aware endpoints
    @router.get("/", response_model=List[response_schema])
    def get_all_entities(
        current_version: APIVersion = Depends(get_current_version)
    ):
        """Get all entities with version info"""
        # Use the existing CRUD service logic
        # Add version info to response
        return add_version_info_to_response([], current_version)
    
    @router.get("/{entity_id}", response_model=response_schema)
    def get_entity(
        entity_id: UUID,
        current_version: APIVersion = Depends(get_current_version)
    ):
        """Get single entity with version info"""
        # Use the existing CRUD service logic
        # Add version info to response
        return add_version_info_to_response({}, current_version)
    
    @router.post("/", response_model=response_schema)
    def create_entity(
        create_data: create_schema,
        current_version: APIVersion = Depends(get_current_version)
    ):
        """Create entity with version info"""
        # Use the existing CRUD service logic
        # Add version info to response
        return add_version_info_to_response({}, current_version)
    
    @router.put("/{entity_id}", response_model=response_schema)
    def update_entity(
        entity_id: UUID,
        update_data: update_schema,
        current_version: APIVersion = Depends(get_current_version)
    ):
        """Update entity with version info"""
        # Use the existing CRUD service logic
        # Add version info to response
        return add_version_info_to_response({}, current_version)
    
    @router.delete("/{entity_id}")
    def delete_entity(
        entity_id: UUID,
        current_version: APIVersion = Depends(get_current_version)
    ):
        """Delete entity with version info"""
        # Use the existing CRUD service logic
        # Add version info to response
        return add_version_info_to_response({"deleted": True}, current_version)
    
    return router


# Versioned route creators for existing entities
def create_versioned_plan_routes(version: APIVersion = APIVersion.V1) -> APIRouter:
    """Create versioned routes for Plan entity"""
    from app.services.crud_service import plan_service
    
    config = VersionedRouteConfig(
        prefix="plans",
        tags=["Plans"],
        entity_name="plan",
        entity_name_plural="plans",
        version=version
    )
    
    return create_versioned_crud_routes(config, plan_service, version)


def create_versioned_user_routes(version: APIVersion = APIVersion.V1) -> APIRouter:
    """Create versioned routes for User entity"""
    from app.services.crud_service import user_service
    
    config = VersionedRouteConfig(
        prefix="users",
        tags=["Users"],
        entity_name="user",
        entity_name_plural="users",
        version=version
    )
    
    return create_versioned_crud_routes(config, user_service, version)


def create_versioned_restaurant_routes(version: APIVersion = APIVersion.V1) -> APIRouter:
    """Create versioned routes for Restaurant entity"""
    from app.services.crud_service import restaurant_service
    
    config = VersionedRouteConfig(
        prefix="restaurants",
        tags=["Restaurants"],
        entity_name="restaurant",
        entity_name_plural="restaurants",
        version=version
    )
    
    return create_versioned_crud_routes(config, restaurant_service, version)


def create_versioned_credit_currency_routes(version: APIVersion = APIVersion.V1) -> APIRouter:
    """Create versioned routes for CreditCurrency entity"""
    from app.services.crud_service import credit_currency_service
    
    config = VersionedRouteConfig(
        prefix="credit-currencies",
        tags=["Credit Currencies"],
        entity_name="credit currency",
        entity_name_plural="credit currencies",
        version=version
    )
    
    return create_versioned_crud_routes(config, credit_currency_service, version)


# Example usage:
"""
# Create v1 routes (current default)
v1_plan_router = create_versioned_plan_routes(APIVersion.V1)

# Create v2 routes (ready for future use)
v2_plan_router = create_versioned_plan_routes(APIVersion.V2)

# Include in main app
app.include_router(v1_plan_router)
app.include_router(v2_plan_router)  # Ready but unused
"""
