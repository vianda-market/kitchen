# app/services/route_factory.py
"""
Generic Route Factory for CRUD Operations

This module provides a factory pattern to automatically generate standard CRUD routes
for any entity, eliminating the need for repetitive route files and reducing code duplication.

The factory creates:
- GET /{entity_id} - Get single entity
- GET / - Get all entities  
- POST / - Create entity
- PUT /{entity_id} - Update entity
- DELETE /{entity_id} - Delete entity

Benefits:
- Eliminates 90% of boilerplate CRUD route code
- Consistent API patterns across all entities
- Centralized route logic for easier maintenance
- Automatic error handling and logging
"""

from typing import Type, TypeVar, Generic, Any, Dict, List, Optional, Callable
from fastapi import APIRouter, HTTPException, status, Query, Depends, UploadFile, File, Form
from pydantic import BaseModel
from uuid import UUID
import psycopg2.extensions

from app.auth.dependencies import get_current_user, get_employee_user, get_client_user, get_client_or_employee_user, oauth2_scheme
from app.dependencies.database import get_db
from app.services.error_handling import handle_get_by_id, handle_get_all, handle_create, handle_update, handle_delete
from app.security.institution_scope import get_institution_scope
from app.security.entity_scoping import (
    EntityScopingService,
    ENTITY_PRODUCT,
    ENTITY_PLATE,
    ENTITY_INSTITUTION_ENTITY,
)

T = TypeVar('T', bound=BaseModel)  # DTO type
U = TypeVar('U', bound=BaseModel)  # Create schema type
V = TypeVar('V', bound=BaseModel)  # Update schema type
W = TypeVar('W', bound=BaseModel)  # Response schema type


class CRUDService(Generic[T]):
    """Generic CRUD service interface"""
    
    def get_by_id(self, entity_id: UUID, db: psycopg2.extensions.connection) -> Optional[T]:
        raise NotImplementedError
    
    def get_by_id_non_archived(self, entity_id: UUID, db: psycopg2.extensions.connection) -> Optional[T]:
        raise NotImplementedError
    
    def get_all(self, db: psycopg2.extensions.connection) -> List[T]:
        raise NotImplementedError
    
    def get_all_non_archived(self, db: psycopg2.extensions.connection) -> List[T]:
        raise NotImplementedError
    
    def create(self, data: Dict[str, Any], db: psycopg2.extensions.connection) -> Optional[T]:
        raise NotImplementedError
    
    def update(self, entity_id: UUID, data: Dict[str, Any], db: psycopg2.extensions.connection) -> Optional[T]:
        raise NotImplementedError
    
    def soft_delete(self, entity_id: UUID, db: psycopg2.extensions.connection) -> bool:
        raise NotImplementedError


class RouteConfig:
    """Configuration for route generation"""
    
    def __init__(
        self,
        prefix: str,
        tags: List[str],
        entity_name: str,
        entity_name_plural: str,
        description: Optional[str] = None,
        institution_scoped: bool = False,
        entity_type: Optional[str] = None,
        immutable_update_fields: Optional[List[str]] = None,
    ):
        self.prefix = prefix
        self.tags = tags
        self.entity_name = entity_name
        self.entity_name_plural = entity_name_plural
        self.description = description or f"{entity_name.title()} management endpoints"
        self.institution_scoped = institution_scoped
        self.entity_type = entity_type  # Entity type for EntityScopingService
        self.immutable_update_fields = immutable_update_fields or []


def create_crud_routes(
    config: RouteConfig,
    service: CRUDService[T],
    create_schema: Type[U],
    update_schema: Type[V],
    response_schema: Type[W],
    additional_routes: Optional[List] = None,
    requires_user_context: bool = False,
    allows_modification: bool = True,
    before_create: Optional[Callable[[dict, psycopg2.extensions.connection], dict]] = None,
    before_update: Optional[Callable[[dict, psycopg2.extensions.connection, UUID], dict]] = None,
    custom_routes_first: Optional[Callable[[APIRouter], None]] = None,
) -> APIRouter:
    """
    Create a complete set of CRUD routes for an entity.
    
    Args:
        config: Route configuration (prefix, tags, entity names)
        service: CRUD service instance
        create_schema: Pydantic schema for entity creation
        update_schema: Pydantic schema for entity updates
        response_schema: Pydantic schema for responses
        additional_routes: Optional list of additional custom routes
        custom_routes_first: Optional callback to add custom routes before generic ones.
            Custom routes take precedence when path+method overlap (FastAPI first-match wins).
        
    Returns:
        APIRouter with all CRUD endpoints
    """
    
    router = APIRouter(
        prefix=config.prefix,
        tags=config.tags,
        dependencies=[Depends(oauth2_scheme)]
    )
    
    # Register custom routes FIRST — they take precedence when path+method match
    if custom_routes_first:
        custom_routes_first(router)
    
    # GET /{entity_id}
    @router.get("/{entity_id}", response_model=response_schema)
    def get_entity(
        entity_id: UUID,
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get a single entity by ID (non-archived only)"""
        if config.institution_scoped:
            if config.entity_type:
                scope = EntityScopingService.get_scope_for_entity(config.entity_type, current_user)
            else:
                scope = get_institution_scope(current_user)  # Fallback for backward compatibility
        else:
            scope = None
        return handle_get_by_id(
            service.get_by_id,
            entity_id,
            db,
            config.entity_name,
            extra_kwargs={"scope": scope} if config.institution_scoped else None
        )
    
    # GET (collection root - no trailing slash per REST convention)
    @router.get("", response_model=List[response_schema])
    def get_all_entities(
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get all entities (non-archived only)"""
        if config.institution_scoped:
            if config.entity_type:
                scope = EntityScopingService.get_scope_for_entity(config.entity_type, current_user)
            else:
                scope = get_institution_scope(current_user)  # Fallback for backward compatibility
        else:
            scope = None

        def service_callable(connection: psycopg2.extensions.connection):
            return service.get_all(connection, scope=scope, include_archived=False)

        return handle_get_all(service_callable, db, config.entity_name_plural)
    
    # POST (collection root - no trailing slash per REST convention)
    @router.post("", response_model=response_schema, status_code=status.HTTP_201_CREATED)
    def create_entity(
        create_data: create_schema,
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Create a new entity"""
        data = create_data.model_dump()
        # Set modified_by from the current user's id
        data["modified_by"] = current_user["user_id"]
        
        # Set user_id if this entity requires user context
        if requires_user_context:
            data["user_id"] = current_user["user_id"]

        if before_create:
            data = before_create(data, db)

        if config.institution_scoped:
            if config.entity_type:
                scope = EntityScopingService.get_scope_for_entity(config.entity_type, current_user)
            else:
                scope = get_institution_scope(current_user)  # Fallback for backward compatibility
        else:
            scope = None

        def create_callable(payload: dict, connection: psycopg2.extensions.connection):
            return service.create(payload, connection, scope=scope)

        return handle_create(create_callable, data, db, config.entity_name)
    
    # PUT /{entity_id} - Only include if entity allows modification
    if allows_modification:
        @router.put("/{entity_id}", response_model=response_schema)
        def update_entity(
            entity_id: UUID,
            update_data: update_schema,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Update an existing entity"""
            data = update_data.model_dump(exclude_unset=True)
            if "modified_by" not in data:
                data["modified_by"] = current_user["user_id"]
            if before_update:
                data = before_update(data, db, entity_id)
            if config.institution_scoped:
                if config.entity_type:
                    scope = EntityScopingService.get_scope_for_entity(config.entity_type, current_user)
                else:
                    scope = get_institution_scope(current_user)  # Fallback for backward compatibility
            else:
                scope = None

            # Enforce immutable update fields (e.g. institution_id)
            if getattr(config, "immutable_update_fields", None):
                existing = service.get_by_id(entity_id, db, scope=scope)
                if not existing:
                    raise HTTPException(status_code=404, detail=f"{config.entity_name.title()} not found")
                for field in config.immutable_update_fields:
                    if field in data:
                        existing_val = getattr(existing, field, None)
                        if str(data[field]) != str(existing_val):
                            raise HTTPException(
                                status_code=400,
                                detail=f"{field} is immutable after creation.",
                            )
                        data.pop(field, None)

            def update_callable(
                target_id: UUID,
                payload: dict,
                connection: psycopg2.extensions.connection
            ):
                return service.update(target_id, payload, connection, scope=scope)

            return handle_update(update_callable, entity_id, data, db, config.entity_name)
        
        @router.patch("/{entity_id}", response_model=response_schema)
        def partial_update_entity(
            entity_id: UUID,
            update_data: update_schema,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Partially update an existing entity"""
            data = update_data.model_dump(exclude_unset=True)
            if "modified_by" not in data:
                data["modified_by"] = current_user["user_id"]
            if before_update:
                data = before_update(data, db, entity_id)
            if config.institution_scoped:
                if config.entity_type:
                    scope = EntityScopingService.get_scope_for_entity(config.entity_type, current_user)
                else:
                    scope = get_institution_scope(current_user)  # Fallback for backward compatibility
            else:
                scope = None

            # Enforce immutable update fields (e.g. institution_id)
            if getattr(config, "immutable_update_fields", None):
                existing = service.get_by_id(entity_id, db, scope=scope)
                if not existing:
                    raise HTTPException(status_code=404, detail=f"{config.entity_name.title()} not found")
                for field in config.immutable_update_fields:
                    if field in data:
                        existing_val = getattr(existing, field, None)
                        if str(data[field]) != str(existing_val):
                            raise HTTPException(
                                status_code=400,
                                detail=f"{field} is immutable after creation.",
                            )
                        data.pop(field, None)

            def partial_update_callable(
                target_id: UUID,
                payload: dict,
                connection: psycopg2.extensions.connection
            ):
                return service.update(target_id, payload, connection, scope=scope)

            return handle_update(partial_update_callable, entity_id, data, db, config.entity_name)
    
    # DELETE /{entity_id}
    @router.delete("/{entity_id}", response_model=dict)
    def delete_entity(
        entity_id: UUID,
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Delete an entity (soft delete)"""
        if config.institution_scoped:
            if config.entity_type:
                scope = EntityScopingService.get_scope_for_entity(config.entity_type, current_user)
            else:
                scope = get_institution_scope(current_user)  # Fallback for backward compatibility
        else:
            scope = None

        def delete_callable(target_id: UUID, connection: psycopg2.extensions.connection):
            return service.soft_delete(target_id, current_user["user_id"], connection, scope=scope)

        handle_delete(delete_callable, entity_id, db, config.entity_name)
        return {"detail": f"{config.entity_name.title()} deleted successfully"}
    
    # Add any additional custom routes
    if additional_routes:
        for route in additional_routes:
            # Additional routes would be added here
            # This allows for custom endpoints beyond standard CRUD
            pass
    
    return router


# =============================================================================
# ROUTE FACTORY INSTANCES FOR COMMON ENTITIES
# =============================================================================

# create_role_routes removed - role_info table deprecated, roles stored directly on user_info as enums


def create_product_routes() -> APIRouter:
    """Create routes for Product entity"""
    from app.services.crud_service import product_service
    from app.schemas.consolidated_schemas import ProductCreateSchema, ProductUpdateSchema, ProductResponseSchema, ProductEnrichedResponseSchema
    from app.services.product_image_service import ProductImageService
    from app.services.entity_service import get_enriched_products, get_enriched_product_by_id
    from app.services.error_handling import handle_create
    from app.utils.error_messages import entity_not_found
    from app.utils.log import log_error
    from typing import List, Optional
    
    config = RouteConfig(
        prefix="/products",
        tags=["Products"],
        entity_name="product",
        entity_name_plural="products",
        institution_scoped=True,
        entity_type=ENTITY_PRODUCT,
    )
    product_image_service = ProductImageService()

    def _product_custom_routes(router: APIRouter) -> None:
        @router.post("", response_model=ProductResponseSchema, status_code=status.HTTP_201_CREATED)
        def create_product_with_image_validation(
            create_data: ProductCreateSchema,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Create a new product with image validation"""
            data = create_data.model_dump()
            data["modified_by"] = current_user["user_id"]
            scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)
            image_storage_path = data.get("image_storage_path")
            image_url = data.get("image_url")
            image_checksum = data.get("image_checksum")
            validated_path, validated_url, validated_checksum = product_image_service.validate_product_image_at_creation(
                image_storage_path=image_storage_path,
                image_url=image_url,
                image_checksum=image_checksum
            )
            data["image_storage_path"] = validated_path
            data["image_url"] = validated_url
            data["image_thumbnail_storage_path"] = validated_path
            data["image_thumbnail_url"] = validated_url
            data["image_checksum"] = validated_checksum
            def create_callable(payload: dict, connection: psycopg2.extensions.connection):
                return product_service.create(payload, connection, scope=scope)
            return handle_create(create_callable, data, db, "product")

        @router.post("/{product_id}/image", response_model=ProductResponseSchema)
        async def upload_product_image(
            product_id: UUID,
            file: UploadFile = File(...),
            client_checksum: str = Form(...),
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Upload or replace a product image."""
            scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)
            product = product_service.get_by_id(product_id, db, scope=scope)
            if not product or product.is_archived:
                raise entity_not_found("Product", product_id)
            contents = await file.read()
            storage_path, url_path, thumb_storage_path, thumb_url_path, checksum = product_image_service.save_image(
                product_id,
                image_bytes=contents,
                content_type=file.content_type or "",
                expected_checksum=client_checksum,
            )
            update_data = {
                "image_url": url_path,
                "image_storage_path": storage_path,
                "image_thumbnail_url": thumb_url_path,
                "image_thumbnail_storage_path": thumb_storage_path,
                "image_checksum": checksum,
                "modified_by": current_user["user_id"],
            }
            updated_product = product_service.update(product_id, update_data, db, scope=scope)
            if not updated_product:
                product_image_service.delete_image(storage_path, thumb_storage_path)
                raise HTTPException(status_code=500, detail="Failed to update product image")
            if (
                product.image_storage_path != storage_path
                and not product_image_service.is_placeholder(product.image_storage_path)
            ):
                old_thumb = getattr(product, "image_thumbnail_storage_path", None)
                product_image_service.delete_image(product.image_storage_path, old_thumb)
            return updated_product

        @router.get("/enriched", response_model=List[ProductEnrichedResponseSchema])
        def list_enriched_products(
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """List all products with enriched data (institution_name). Non-archived only."""
            try:
                scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)
                return get_enriched_products(db, scope=scope, include_archived=False)
            except HTTPException:
                raise
            except Exception as e:
                log_error(f"Error getting enriched products: {e}")
                raise HTTPException(status_code=500, detail="Failed to retrieve enriched products")

        @router.get("/enriched/{product_id}", response_model=ProductEnrichedResponseSchema)
        def get_enriched_product_by_id_route(
            product_id: UUID,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Get a single product by ID with enriched data (institution_name). Non-archived only."""
            try:
                scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)
                enriched_product = get_enriched_product_by_id(product_id, db, scope=scope, include_archived=False)
                if not enriched_product:
                    raise entity_not_found("Product", product_id)
                return enriched_product
            except HTTPException:
                raise
            except Exception as e:
                log_error(f"Error getting enriched product {product_id}: {e}")
                raise HTTPException(status_code=500, detail="Failed to retrieve enriched product")

    router = create_crud_routes(
        config=config,
        service=product_service,
        create_schema=ProductCreateSchema,
        update_schema=ProductUpdateSchema,
        response_schema=ProductResponseSchema,
        custom_routes_first=_product_custom_routes
    )
    return router


def create_plan_routes() -> APIRouter:
    """Create routes for Plan entity with Employee-only access for modifications, Client/Employee access for viewing"""
    from app.services.crud_service import plan_service
    from app.services.market_service import reject_global_market_for_entity, GLOBAL_MARKET_ID
    from app.schemas.consolidated_schemas import PlanCreateSchema, PlanUpdateSchema, PlanResponseSchema, PlanEnrichedResponseSchema
    from app.services.entity_service import get_enriched_plans, get_enriched_plan_by_id
    from app.utils.query_params import (
        market_filter,
        status_filter,
        currency_code_filter,
    )
    from app.utils.filter_builder import build_filter_conditions
    from app.utils.error_messages import entity_not_found
    from app.utils.log import log_error
    from typing import List, Optional
    
    config = RouteConfig(
        prefix="/plans",
        tags=["Plans"],
        entity_name="plan",
        entity_name_plural="plans"
    )
    
    # Create router without generic routes to avoid route conflicts
    router = APIRouter(
        prefix=config.prefix,
        tags=config.tags,
        dependencies=[Depends(oauth2_scheme)]
    )
    
    # Define GET endpoints first with proper access control (Clients and Employees only, not Suppliers)
    @router.get("", response_model=List[PlanResponseSchema])
    def get_all_plans(
        current_user: dict = Depends(get_client_or_employee_user),  # Clients and Employees can view
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get all plans - Available to Clients and Employees only. Excludes plans for Global Marketplace. Non-archived only."""
        scope = None  # Plans are not institution-scoped
        def service_callable(connection: psycopg2.extensions.connection):
            plans = plan_service.get_all(connection, scope=scope, include_archived=False)
            return [p for p in plans if p.market_id != GLOBAL_MARKET_ID]
        return handle_get_all(service_callable, db, "plans")
    
    @router.get("/{plan_id}", response_model=PlanResponseSchema)
    def get_plan(
        plan_id: UUID,
        current_user: dict = Depends(get_client_or_employee_user),  # Clients and Employees can view
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get a single plan by ID - Available to Clients and Employees only. Non-archived only."""
        scope = None  # Plans are not institution-scoped
        return handle_get_by_id(
            plan_service.get_by_id,
            plan_id,
            db,
            "plan",
            extra_kwargs={"scope": scope} if config.institution_scoped else None
        )
    
    # Override POST/PUT/DELETE endpoints to be Employee-only
    @router.post("", response_model=PlanResponseSchema, status_code=status.HTTP_201_CREATED)
    def create_plan(
        create_data: PlanCreateSchema,
        current_user: dict = Depends(get_employee_user),  # Employee-only
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Create a new plan - Employee-only"""
        data = create_data.model_dump()
        if "market_id" in data and data["market_id"] is not None:
            reject_global_market_for_entity(data["market_id"], "plan")
        data["rollover"] = True
        data["rollover_cap"] = None
        data["modified_by"] = current_user["user_id"]
        scope = None  # Plans are not institution-scoped
        def create_callable(payload: dict, connection: psycopg2.extensions.connection):
            return plan_service.create(payload, connection, scope=scope)
        return handle_create(create_callable, data, db, "plan")
    
    @router.put("/{plan_id}", response_model=PlanResponseSchema)
    def update_plan(
        plan_id: UUID,
        update_data: PlanUpdateSchema,
        current_user: dict = Depends(get_employee_user),  # Employee-only
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Update an existing plan - Employee-only"""
        data = update_data.model_dump(exclude_unset=True)
        data.pop("rollover", None)
        data.pop("rollover_cap", None)
        if "market_id" in data and data["market_id"] is not None:
            reject_global_market_for_entity(data["market_id"], "plan")
        if "modified_by" not in data:
            data["modified_by"] = current_user["user_id"]
        scope = None  # Plans are not institution-scoped
        def update_callable(target_id: UUID, payload: dict, connection: psycopg2.extensions.connection):
            return plan_service.update(target_id, payload, connection, scope=scope)
        return handle_update(update_callable, plan_id, data, db, "plan")
    
    @router.delete("/{plan_id}", response_model=dict)
    def delete_plan(
        plan_id: UUID,
        current_user: dict = Depends(get_employee_user),  # Employee-only
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Delete a plan (soft delete) - Employee-only"""
        scope = None  # Plans are not institution-scoped
        def delete_callable(target_id: UUID, connection: psycopg2.extensions.connection):
            return plan_service.soft_delete(target_id, current_user["user_id"], connection, scope=scope)
        handle_delete(delete_callable, plan_id, db, "plan")
        return {"detail": "Plan deleted successfully"}

    # =============================================================================
    # ENRICHED PLAN ENDPOINTS (with currency_name and currency_code)
    # =============================================================================
    
    @router.get("/enriched", response_model=List[PlanEnrichedResponseSchema])
    def list_enriched_plans(
        market_id: Optional[UUID] = market_filter(),
        status: Optional[str] = status_filter(),
        currency_code: Optional[str] = currency_code_filter(),
        current_user: dict = Depends(get_client_or_employee_user),  # Clients and Employees can view
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """List all plans with enriched data (currency_name and currency_code). Optional filters: market_id, status, currency_code. Excludes plans for Global Marketplace. Non-archived only."""
        try:
            filters = {"market_id": market_id, "status": status, "currency_code": currency_code}
            additional_conditions = list(build_filter_conditions("plans", filters) or [])
            additional_conditions.append(("pl.market_id != %s::uuid", str(GLOBAL_MARKET_ID)))
            enriched_plans = get_enriched_plans(
                db,
                include_archived=False,
                additional_conditions=additional_conditions
            )
            return enriched_plans
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error getting enriched plans: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve enriched plans")

    @router.get("/enriched/{plan_id}", response_model=PlanEnrichedResponseSchema)
    def get_enriched_plan_by_id_route(
        plan_id: UUID,
        current_user: dict = Depends(get_client_or_employee_user),  # Clients and Employees can view
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get a single plan by ID with enriched data (currency_name and currency_code) - Available to Clients and Employees only. Non-archived only."""
        try:
            enriched_plan = get_enriched_plan_by_id(
                plan_id,
                db,
                include_archived=False
            )
            if not enriched_plan:
                raise entity_not_found("Plan", plan_id)
            return enriched_plan
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error getting enriched plan {plan_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve enriched plan")

    return router


def create_restaurant_routes() -> APIRouter:
    """Create custom routes for Restaurant entity with automatic balance creation"""
    from app.routes.restaurant import router as restaurant_router
    return restaurant_router


def create_credit_currency_routes() -> APIRouter:
    """Create routes for CreditCurrency entity with Employee-only access"""
    from app.services.crud_service import credit_currency_service
    from app.schemas.consolidated_schemas import CreditCurrencyCreateSchema, CreditCurrencyUpdateSchema, CreditCurrencyResponseSchema
    from typing import List
    
    config = RouteConfig(
        prefix="/credit-currencies",
        tags=["Credit Currencies"],
        entity_name="credit currency",
        entity_name_plural="credit currencies"
    )
    
    # Create router without generic routes to avoid route conflicts
    router = APIRouter(
        prefix=config.prefix,
        tags=config.tags,
        dependencies=[Depends(oauth2_scheme)]
    )
    
    # Define all endpoints with Employee-only access (Suppliers use credit_currency data via plates, but can't access API directly)
    @router.get("", response_model=List[CreditCurrencyResponseSchema])
    def get_all_credit_currencies(
        current_user: dict = Depends(get_employee_user),  # Employee-only
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get all credit currencies - Employee-only. Non-archived only."""
        scope = None  # Credit currencies are not institution-scoped
        def service_callable(connection: psycopg2.extensions.connection):
            return credit_currency_service.get_all(connection, scope=scope, include_archived=False)
        return handle_get_all(service_callable, db, "credit currencies")
    
    @router.get("/{currency_id}", response_model=CreditCurrencyResponseSchema)
    def get_credit_currency(
        currency_id: UUID,
        current_user: dict = Depends(get_employee_user),  # Employee-only
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get a single credit currency by ID - Employee-only. Non-archived only."""
        scope = None  # Credit currencies are not institution-scoped
        return handle_get_by_id(
            credit_currency_service.get_by_id,
            currency_id,
            db,
            "credit currency",
            extra_kwargs={"scope": scope} if config.institution_scoped else None
        )
    
    @router.post("", response_model=CreditCurrencyResponseSchema, status_code=status.HTTP_201_CREATED)
    def create_credit_currency(
        create_data: CreditCurrencyCreateSchema,
        current_user: dict = Depends(get_employee_user),  # Employee-only
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Create a new credit currency - Employee-only. Backend assigns currency_code from supported list."""
        from app.config.supported_currencies import get_currency_code_by_name

        data = create_data.model_dump()
        # Resolve currency_code from currency_name; do not accept client-supplied currency_code
        currency_name = data.get("currency_name") or ""
        currency_code = get_currency_code_by_name(currency_name)
        if not currency_code:
            raise HTTPException(
                status_code=400,
                detail="Currency name not supported. Use GET /api/v1/currencies/ for the list.",
            )
        data["currency_code"] = currency_code
        data["modified_by"] = current_user["user_id"]
        scope = None  # Credit currencies are not institution-scoped
        def create_callable(payload: dict, connection: psycopg2.extensions.connection):
            return credit_currency_service.create(payload, connection, scope=scope)
        return handle_create(create_callable, data, db, "credit currency")
    
    @router.put("/{currency_id}", response_model=CreditCurrencyResponseSchema)
    def update_credit_currency(
        currency_id: UUID,
        update_data: CreditCurrencyUpdateSchema,
        current_user: dict = Depends(get_employee_user),  # Employee-only
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Update an existing credit currency - Employee-only"""
        data = update_data.model_dump(exclude_unset=True)
        if "modified_by" not in data:
            data["modified_by"] = current_user["user_id"]
        scope = None  # Credit currencies are not institution-scoped
        def update_callable(target_id: UUID, payload: dict, connection: psycopg2.extensions.connection):
            return credit_currency_service.update(target_id, payload, connection, scope=scope)
        return handle_update(update_callable, currency_id, data, db, "credit currency")
    
    @router.delete("/{currency_id}", response_model=dict)
    def delete_credit_currency(
        currency_id: UUID,
        current_user: dict = Depends(get_employee_user),  # Employee-only
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Delete a credit currency (soft delete) - Employee-only"""
        scope = None  # Credit currencies are not institution-scoped
        def delete_callable(target_id: UUID, connection: psycopg2.extensions.connection):
            return credit_currency_service.soft_delete(target_id, current_user["user_id"], connection, scope=scope)
        handle_delete(delete_callable, currency_id, db, "credit currency")
        return {"detail": "Credit currency deleted successfully"}
    
    return router


def create_qr_code_routes() -> APIRouter:
    """Create routes for QRCode entity"""
    from app.services.crud_service import qr_code_service
    from app.schemas.consolidated_schemas import QRCodeCreateSchema, QRCodeUpdateSchema, QRCodeResponseSchema
    
    config = RouteConfig(
        prefix="/qr-codes",
        tags=["QR Codes"],
        entity_name="QR code",
        entity_name_plural="QR codes"
    )
    
    return create_crud_routes(
        config=config,
        service=qr_code_service,
        create_schema=QRCodeCreateSchema,
        update_schema=QRCodeUpdateSchema,
        response_schema=QRCodeResponseSchema
    )


def create_subscription_routes() -> APIRouter:
    """Create routes for Subscription entity with enriched endpoints"""
    from app.services.crud_service import subscription_service
    from app.schemas.subscription import SubscriptionCreateSchema, SubscriptionUpdateSchema, SubscriptionResponseSchema, SubscriptionHoldRequestSchema
    from app.schemas.consolidated_schemas import SubscriptionEnrichedResponseSchema
    from app.services.entity_service import get_enriched_subscriptions, get_enriched_subscription_by_id
    from app.services.error_handling import handle_business_operation
    from app.services.subscription_action_service import put_subscription_on_hold, resume_subscription
    from typing import List
    
    config = RouteConfig(
        prefix="/subscriptions",
        tags=["Subscriptions"],
        entity_name="subscription",
        entity_name_plural="subscriptions"
    )
    
    def _subscription_custom_routes(router: APIRouter) -> None:
        @router.get("", response_model=List[SubscriptionResponseSchema])
        def list_subscriptions_override(
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """List subscriptions. Employees: global. Customers: own. Suppliers: 403. Non-archived only."""
            role_type = current_user.get("role_type")
            if role_type == "Supplier":
                raise HTTPException(status_code=403, detail="Forbidden: Suppliers cannot access subscription data")
            if role_type == "Customer":
                user_id = current_user.get("user_id")
                if not user_id:
                    raise HTTPException(status_code=401, detail="User ID not found in token")
                def _get_subscriptions():
                    return subscription_service.get_all(db, scope=None, include_archived=False, additional_conditions=[("user_id = %s::uuid", str(user_id))])
            else:
                def _get_subscriptions():
                    return subscription_service.get_all(db, scope=None, include_archived=False)
            return handle_business_operation(_get_subscriptions, "subscription list retrieval")

        @router.get("/{subscription_id}", response_model=SubscriptionResponseSchema)
        def get_subscription_override(
            subscription_id: UUID,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Get a single subscription by ID. Employees: global. Customers: own only. Suppliers: 403."""
            role_type = current_user.get("role_type")
            if role_type == "Supplier":
                raise HTTPException(status_code=403, detail="Forbidden: Suppliers cannot access subscription data")
            if role_type == "Customer":
                user_id = current_user.get("user_id")
                if not user_id:
                    raise HTTPException(status_code=401, detail="User ID not found in token")
                def _get_subscription():
                    subscription = subscription_service.get_by_id(subscription_id, db, scope=None)
                    if not subscription:
                        raise HTTPException(status_code=404, detail="Subscription not found")
                    if subscription.user_id != user_id:
                        raise HTTPException(status_code=404, detail="Subscription not found")
                    return subscription
            else:
                def _get_subscription():
                    subscription = subscription_service.get_by_id(subscription_id, db, scope=None)
                    if not subscription:
                        raise HTTPException(status_code=404, detail="Subscription not found")
                    return subscription
            return handle_business_operation(_get_subscription, "subscription retrieval")

        @router.post("/{subscription_id}/hold", response_model=SubscriptionResponseSchema)
        def hold_subscription_route(
            subscription_id: UUID,
            body: SubscriptionHoldRequestSchema,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Put a subscription on hold. Only the owning customer. Hold duration max 3 months."""
            if current_user.get("role_type") != "Customer":
                raise HTTPException(status_code=403, detail="Forbidden: Only customers can put their subscription on hold.")
            user_id = current_user.get("user_id")
            if not user_id:
                raise HTTPException(status_code=401, detail="User ID not found in token")
            return put_subscription_on_hold(subscription_id, user_id, body.hold_start_date, body.hold_end_date, db)

        @router.post("/{subscription_id}/resume", response_model=SubscriptionResponseSchema)
        def resume_subscription_route(
            subscription_id: UUID,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Resume a subscription from hold. Only the owning customer."""
            if current_user.get("role_type") != "Customer":
                raise HTTPException(status_code=403, detail="Forbidden: Only customers can resume their own subscription.")
            user_id = current_user.get("user_id")
            if not user_id:
                raise HTTPException(status_code=401, detail="User ID not found in token")
            return resume_subscription(subscription_id, user_id, db)

        @router.get("/enriched", response_model=List[SubscriptionEnrichedResponseSchema])
        def list_enriched_subscriptions(
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """List subscriptions with enriched data. Employees: global. Customers: own. Suppliers: 403. Non-archived only."""
            role_type = current_user.get("role_type")
            if role_type == "Supplier":
                raise HTTPException(status_code=403, detail="Forbidden: Suppliers cannot access subscription data")
            if role_type == "Customer":
                user_id = current_user.get("user_id")
                if not user_id:
                    raise HTTPException(status_code=401, detail="User ID not found in token")
                def _get_enriched_subscriptions():
                    return get_enriched_subscriptions(db, scope=None, include_archived=False, user_id=user_id)
            else:
                def _get_enriched_subscriptions():
                    return get_enriched_subscriptions(db, scope=None, include_archived=False)
            return handle_business_operation(_get_enriched_subscriptions, "enriched subscription list retrieval")

        @router.get("/enriched/{subscription_id}", response_model=SubscriptionEnrichedResponseSchema)
        def get_enriched_subscription_by_id_route(
            subscription_id: UUID,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Get subscription by ID with enriched data. Employees: global. Customers: own. Suppliers: 403. Non-archived only."""
            role_type = current_user.get("role_type")
            if role_type == "Supplier":
                raise HTTPException(status_code=403, detail="Forbidden: Suppliers cannot access subscription data")
            if role_type == "Customer":
                user_id = current_user.get("user_id")
                if not user_id:
                    raise HTTPException(status_code=401, detail="User ID not found in token")
                def _get_enriched_subscription():
                    sub = get_enriched_subscription_by_id(subscription_id, db, scope=None, include_archived=False)
                    if not sub:
                        raise HTTPException(status_code=404, detail="Subscription not found")
                    if sub.user_id != user_id:
                        raise HTTPException(status_code=404, detail="Subscription not found")
                    return sub
            else:
                def _get_enriched_subscription():
                    sub = get_enriched_subscription_by_id(subscription_id, db, scope=None, include_archived=False)
                    if not sub:
                        raise HTTPException(status_code=404, detail="Subscription not found")
                    return sub
            return handle_business_operation(_get_enriched_subscription, "enriched subscription retrieval")

    router = create_crud_routes(
        config=config,
        service=subscription_service,
        create_schema=SubscriptionCreateSchema,
        update_schema=SubscriptionUpdateSchema,
        response_schema=SubscriptionResponseSchema,
        requires_user_context=True,
        custom_routes_first=_subscription_custom_routes
    )
    return router


def create_institution_routes() -> APIRouter:
    """Create routes for Institution entity with POST/PUT/DELETE restricted to Employee Admin and Super Admin only.
    GET endpoints scoped: Suppliers, Customers, and Employee Management see only their institution."""
    from app.services.crud_service import institution_service
    from app.schemas.consolidated_schemas import InstitutionCreateSchema, InstitutionUpdateSchema, InstitutionResponseSchema
    from app.auth.dependencies import get_admin_user
    from app.services.error_handling import handle_create, handle_get_all, handle_get_by_id, handle_update, handle_delete
    from app.security.field_policies import ensure_can_edit_institution_no_show_discount
    
    config = RouteConfig(
        prefix="/institutions",
        tags=["Institutions"],
        entity_name="institution",
        entity_name_plural="institutions",
        institution_scoped=True  # Suppliers/Customers/Employee Management: own institution only
    )
    
    def _institution_scope(current_user: dict):
        role_type = current_user.get("role_type")
        role_name = current_user.get("role_name")
        if role_type == "Employee" and role_name in ("Admin", "Super Admin"):
            return None  # Global access
        return get_institution_scope(current_user)
    
    def _institution_custom_routes(router: APIRouter) -> None:
        """Custom institution routes — registered first so they take precedence over generic CRUD."""
        @router.get("", response_model=List[InstitutionResponseSchema])
        def get_all_institutions(
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """List institutions. Suppliers, Customers, Employee Management: own institution only. Admin/Super Admin: all. Non-archived only."""
            scope = _institution_scope(current_user)
            def service_callable(connection: psycopg2.extensions.connection):
                return institution_service.get_all(connection, scope=scope, include_archived=False)
            return handle_get_all(service_callable, db, "institutions")
        
        @router.get("/{entity_id}", response_model=InstitutionResponseSchema)
        def get_institution(
            entity_id: UUID,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Get institution by ID. Suppliers, Customers, Employee Management: own institution only. Admin/Super Admin: any. Non-archived only."""
            scope = _institution_scope(current_user)
            return handle_get_by_id(
                institution_service.get_by_id,
                entity_id,
                db,
                "institution",
                extra_kwargs={"scope": scope} if scope else None
            )
        
        @router.put("/{entity_id}", response_model=InstitutionResponseSchema)
        def update_institution(
            entity_id: UUID,
            update_data: InstitutionUpdateSchema,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Update institution. Admin/Super Admin: full update. Manager/Global Manager: no_show_discount only."""
            scope = _institution_scope(current_user)
            data = update_data.model_dump(exclude_unset=True)
            if "modified_by" not in data:
                data["modified_by"] = current_user["user_id"]

            payload_keys = set(data.keys()) - {"modified_by"}
            has_non_no_show = payload_keys - {"no_show_discount"}
            has_no_show = "no_show_discount" in payload_keys

            if has_non_no_show:
                if current_user.get("role_type") != "Employee" or current_user.get("role_name") not in ("Admin", "Super Admin"):
                    raise HTTPException(status_code=403, detail="Only Admin or Super Admin can edit institution name, type, or market.")
            if has_no_show:
                ensure_can_edit_institution_no_show_discount(current_user)

            existing = institution_service.get_by_id(entity_id, db, scope=scope)
            inst_type = getattr(existing, "institution_type", None) if existing else None
            inst_type_str = (inst_type.value if hasattr(inst_type, "value") else str(inst_type)) if inst_type else ""
            # Effective type after update: new value if provided, else existing
            new_type = data.get("institution_type")
            effective_type_str = (
                (new_type.value if hasattr(new_type, "value") else str(new_type)) if new_type is not None else inst_type_str
            )
            if effective_type_str in ("Employee", "Customer") and current_user.get("role_name") != "Super Admin":
                raise HTTPException(
                    status_code=403,
                    detail="Only Super Admin can set institution_type to Employee or Customer.",
                )
            if inst_type_str == "Supplier":
                data.pop("market_id", None)
            # Only Supplier institutions carry no_show_discount; clear for non-Supplier
            if effective_type_str != "Supplier":
                data["no_show_discount"] = None
            def update_callable(target_id: UUID, payload: dict, connection: psycopg2.extensions.connection):
                return institution_service.update(target_id, payload, connection, scope=scope)

            return handle_update(update_callable, entity_id, data, db, "institution")
        
        @router.delete("/{entity_id}", response_model=dict)
        def delete_institution(
            entity_id: UUID,
            current_user: dict = Depends(get_admin_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Delete institution (soft delete) - Employee Admin and Super Admin only."""
            scope = _institution_scope(current_user)
            def delete_callable(target_id: UUID, connection: psycopg2.extensions.connection):
                return institution_service.soft_delete(target_id, current_user["user_id"], connection, scope=scope)
            handle_delete(delete_callable, entity_id, db, "institution")
            return {"detail": "Institution deleted successfully"}
        
        @router.post("", response_model=InstitutionResponseSchema, status_code=status.HTTP_201_CREATED)
        def create_institution(
            create_data: InstitutionCreateSchema,
            current_user: dict = Depends(get_admin_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Create a new institution - Employee Admin and Super Admin only"""
            data = create_data.model_dump(exclude_none=True)
            # Only Supplier institutions carry no_show_discount
            inst_type = data.get("institution_type")
            inst_str = inst_type.value if hasattr(inst_type, "value") else str(inst_type) if inst_type else "Supplier"
            if inst_str != "Supplier":
                data.pop("no_show_discount", None)
            if inst_str in ("Employee", "Customer") and current_user.get("role_name") != "Super Admin":
                raise HTTPException(
                    status_code=403,
                    detail="Only Super Admin can create Employee or Customer-type institutions.",
                )
            data["modified_by"] = current_user["user_id"]
            scope = None
            def create_callable(payload: dict, connection: psycopg2.extensions.connection):
                return institution_service.create(payload, connection, scope=scope)
            return handle_create(create_callable, data, db, "institution")
    
    router = create_crud_routes(
        config=config,
        service=institution_service,
        create_schema=InstitutionCreateSchema,
        update_schema=InstitutionUpdateSchema,
        response_schema=InstitutionResponseSchema,
        custom_routes_first=_institution_custom_routes
    )
    return router


def create_payment_method_routes() -> APIRouter:
    """Create routes for PaymentMethod entity with enriched endpoints"""
    from app.services.crud_service import payment_method_service
    from app.schemas.payment_method import PaymentMethodCreateSchema, PaymentMethodUpdateSchema, PaymentMethodResponseSchema, PaymentMethodEnrichedResponseSchema
    from app.services.entity_service import get_enriched_payment_methods as fetch_enriched_payment_methods, get_enriched_payment_method_by_id
    from app.services.error_handling import handle_business_operation
    from app.auth.dependencies import get_employee_or_customer_user
    from app.security.scoping import EmployeeCustomerAccessControl
    from typing import List
    
    config = RouteConfig(
        prefix="/payment-methods",
        tags=["Payment Methods"],
        entity_name="payment method",
        entity_name_plural="payment methods"
    )
    
    def _payment_method_custom_routes(router: APIRouter) -> None:
        from app.services.payment_method_service import create_payment_method_with_address
        from app.utils.log import log_info
        from app.utils.db import db_read
        
        @router.post("", response_model=PaymentMethodResponseSchema, status_code=status.HTTP_201_CREATED)
        def create_payment_method(
            create_data: PaymentMethodCreateSchema,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Create payment method - sets is_default=True if user's first."""
            def _create_payment_method():
                data = create_data.model_dump()
                address_id = data.pop("address_id", None)
                address_data = data.pop("address_data", None)
                if address_data:
                    from app.security.field_policies import ensure_supplier_can_create_edit_addresses
                    ensure_supplier_can_create_edit_addresses(current_user)
                query = "SELECT COUNT(*) as count FROM payment_method WHERE user_id = %s::uuid AND is_archived = FALSE"
                result = db_read(query, (str(current_user["user_id"]),), connection=db, fetch_one=True)
                existing_count = result["count"] if result else 0
                if existing_count == 0:
                    data["is_default"] = True
                    log_info(f"Setting is_default=True for first payment method for user {current_user['user_id']}")
                else:
                    log_info(f"User {current_user['user_id']} already has {existing_count} payment method(s), is_default={data.get('is_default', False)}")
                return create_payment_method_with_address(
                    payment_method_data=data,
                    address_id=address_id,
                    address_data=address_data,
                    current_user=current_user,
                    db=db,
                    scope=None
                )
            return handle_business_operation(_create_payment_method, "payment method creation", "Payment method created successfully")

        @router.get("/enriched", response_model=List[PaymentMethodEnrichedResponseSchema])
        def list_enriched_payment_methods(
            current_user: dict = Depends(get_employee_or_customer_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """List payment methods with enriched data. Employees: global. Customers: own. Suppliers: 403. Non-archived only."""
            user_id, error = EmployeeCustomerAccessControl.enforce_access(current_user)
            if error:
                raise HTTPException(**error)
            def _get():
                return fetch_enriched_payment_methods(db, scope=None, include_archived=False, user_id=user_id)
            return handle_business_operation(_get, "enriched payment method list retrieval")

        @router.get("/enriched/{payment_method_id}", response_model=PaymentMethodEnrichedResponseSchema)
        def get_enriched_payment_method_by_id_route(
            payment_method_id: UUID,
            current_user: dict = Depends(get_employee_or_customer_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Get payment method by ID with enriched data. Non-archived only."""
            def _get():
                pm = get_enriched_payment_method_by_id(payment_method_id, db, scope=None, include_archived=False)
                if not pm:
                    raise HTTPException(status_code=404, detail="Payment method not found")
                error = EmployeeCustomerAccessControl.verify_ownership(pm.user_id, current_user)
                if error:
                    raise HTTPException(**error)
                return pm
            return handle_business_operation(_get, "enriched payment method retrieval")

    router = create_crud_routes(
        config=config,
        service=payment_method_service,
        create_schema=PaymentMethodCreateSchema,
        update_schema=PaymentMethodUpdateSchema,
        response_schema=PaymentMethodResponseSchema,
        requires_user_context=True,
        custom_routes_first=_payment_method_custom_routes
    )
    return router


def create_plate_routes() -> APIRouter:
    """Create routes for Plate entity"""
    from app.services.crud_service import plate_service
    from app.schemas.consolidated_schemas import PlateCreateSchema, PlateUpdateSchema, PlateResponseSchema, PlateEnrichedResponseSchema
    from app.services.entity_service import get_enriched_plates, get_enriched_plate_by_id
    from app.services.error_handling import handle_get_by_id, handle_get_all
    from app.utils.error_messages import entity_not_found
    from app.utils.log import log_error
    from typing import List, Optional
    
    config = RouteConfig(
        prefix="/plates",
        tags=["Plates"],
        entity_name="plate",
        entity_name_plural="plates",
        institution_scoped=True,
        entity_type=ENTITY_PLATE,
    )
    
    def _plate_custom_routes(router: APIRouter) -> None:
        @router.get("", response_model=List[PlateResponseSchema])
        def get_all_plates(
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Get all plates - Customers: all. Employees/Suppliers: institution-scoped. Non-archived only."""
            if current_user.get("role_type") == "Customer":
                scope = None
            else:
                scope = EntityScopingService.get_scope_for_entity(ENTITY_PLATE, current_user)
            def service_callable(connection: psycopg2.extensions.connection):
                return plate_service.get_all(connection, scope=scope, include_archived=False)
            return handle_get_all(service_callable, db, "plates")

        @router.get("/{plate_id}", response_model=PlateResponseSchema)
        def get_plate(
            plate_id: UUID,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Get plate by ID - Customers: any. Employees/Suppliers: institution-scoped. Non-archived only."""
            if current_user.get("role_type") == "Customer":
                scope = None
            else:
                scope = EntityScopingService.get_scope_for_entity(ENTITY_PLATE, current_user)
            return handle_get_by_id(
                plate_service.get_by_id,
                plate_id,
                db,
                "plate",
                extra_kwargs={"scope": scope} if scope else None
            )

        @router.get("/enriched", response_model=List[PlateEnrichedResponseSchema])
        def list_enriched_plates(
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """List plates with enriched data - Customers: all. Employees/Suppliers: institution-scoped. Non-archived only."""
            try:
                if current_user.get("role_type") == "Customer":
                    scope = None
                else:
                    scope = EntityScopingService.get_scope_for_entity(ENTITY_PLATE, current_user)
                return get_enriched_plates(db, scope=scope, include_archived=False)
            except HTTPException:
                raise
            except Exception as e:
                log_error(f"Error getting enriched plates: {e}")
                raise HTTPException(status_code=500, detail="Failed to retrieve enriched plates")

        @router.get("/enriched/{plate_id}", response_model=PlateEnrichedResponseSchema)
        def get_enriched_plate_by_id_route(
            plate_id: UUID,
            kitchen_day: Optional[str] = Query(None, description="When provided with user having employer, includes has_coworker_offer, has_coworker_request"),
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Get plate by ID with enriched data. Non-archived only."""
            try:
                if current_user.get("role_type") == "Customer":
                    scope = None
                else:
                    scope = EntityScopingService.get_scope_for_entity(ENTITY_PLATE, current_user)
                employer_id = None
                employer_address_id = None
                user_id = None
                if kitchen_day and current_user.get("user_id"):
                    from app.utils.db import db_read
                    uid_raw = current_user["user_id"]
                    try:
                        user_id = uid_raw if isinstance(uid_raw, UUID) else UUID(uid_raw)
                    except (ValueError, TypeError):
                        user_id = None
                    user_row = db_read("SELECT employer_id, employer_address_id FROM user_info WHERE user_id = %s", (str(uid_raw),), connection=db, fetch_one=True)
                    if user_row and user_row.get("employer_id"):
                        employer_id = user_row["employer_id"]
                        employer_address_id = user_row.get("employer_address_id")
                enriched_plate = get_enriched_plate_by_id(plate_id, db, scope=scope, include_archived=False, kitchen_day=kitchen_day, employer_id=employer_id, employer_address_id=employer_address_id, user_id=user_id)
                if not enriched_plate:
                    raise entity_not_found("Plate", plate_id)
                return enriched_plate
            except HTTPException:
                raise
            except Exception as e:
                log_error(f"Error getting enriched plate {plate_id}: {e}")
                raise HTTPException(status_code=500, detail="Failed to retrieve enriched plate")

    router = create_crud_routes(
        config=config,
        service=plate_service,
        create_schema=PlateCreateSchema,
        update_schema=PlateUpdateSchema,
        response_schema=PlateResponseSchema,
        custom_routes_first=_plate_custom_routes
    )
    return router


def create_geolocation_routes() -> APIRouter:
    """Create routes for Geolocation entity"""
    from app.services.crud_service import geolocation_service
    from app.schemas.geolocation import GeolocationCreateSchema, GeolocationUpdateSchema, GeolocationResponseSchema
    
    config = RouteConfig(
        prefix="/geolocations",
        tags=["Geolocations"],
        entity_name="geolocation",
        entity_name_plural="geolocations"
    )
    
    return create_crud_routes(
        config=config,
        service=geolocation_service,
        create_schema=GeolocationCreateSchema,
        update_schema=GeolocationUpdateSchema,
        response_schema=GeolocationResponseSchema
    )


def create_institution_entity_routes() -> APIRouter:
    """Create routes for InstitutionEntity entity. Supplier Admin and Employee Admin/Super Admin can access (GET, POST, PUT, DELETE).
    credit_currency_id is derived from address.country_code -> market (Option A); client does not send it."""
    from app.services.crud_service import institution_entity_service
    from app.schemas.consolidated_schemas import InstitutionEntityCreateSchema, InstitutionEntityUpdateSchema, InstitutionEntityResponseSchema
    from app.auth.dependencies import require_supplier_admin_or_employee_admin
    from app.services.entity_service import derive_credit_currency_id_for_address

    def _before_create(data: dict, connection: psycopg2.extensions.connection) -> dict:
        data["credit_currency_id"] = derive_credit_currency_id_for_address(data["address_id"], connection)
        return data

    def _before_update(data: dict, connection: psycopg2.extensions.connection, entity_id: UUID) -> dict:
        if "address_id" in data:
            data["credit_currency_id"] = derive_credit_currency_id_for_address(data["address_id"], connection)
        return data

    config = RouteConfig(
        prefix="/institution-entities",
        tags=["Institution Entities"],
        entity_name="institution entity",
        entity_name_plural="institution entities",
        institution_scoped=True,
        entity_type=ENTITY_INSTITUTION_ENTITY,
        immutable_update_fields=["institution_id"],
    )

    router = create_crud_routes(
        config=config,
        service=institution_entity_service,
        create_schema=InstitutionEntityCreateSchema,
        update_schema=InstitutionEntityUpdateSchema,
        response_schema=InstitutionEntityResponseSchema,
        before_create=_before_create,
        before_update=_before_update,
    )
    router.dependencies.append(Depends(require_supplier_admin_or_employee_admin))
    return router


# =============================================================================
# USER-DEPENDENT ROUTE FACTORY FUNCTIONS
# =============================================================================

# Note: create_payment_method_routes() is defined above with enriched endpoints


def create_plate_selection_routes() -> APIRouter:
    """Create routes for PlateSelection entity (user-dependent)"""
    from app.services.crud_service import plate_selection_service
    from app.schemas.consolidated_schemas import PlateSelectionCreateSchema, PlateSelectionResponseSchema
    
    config = RouteConfig(
        prefix="/plate-selections",
        tags=["Plate Selections"],
        entity_name="plate selection",
        entity_name_plural="plate selections"
    )
    
    return create_crud_routes(
        config=config,
        service=plate_selection_service,
        create_schema=PlateSelectionCreateSchema,
        update_schema=PlateSelectionCreateSchema,  # Using same schema for update
        response_schema=PlateSelectionResponseSchema,
        requires_user_context=True  # ← KEY: This entity requires user_id
    )


# =============================================================================
# IMMUTABLE ENTITY ROUTE FACTORY FUNCTIONS
# =============================================================================
# institution_payment_attempt and client_payment_attempt routes removed (payment attempts deprecated)

