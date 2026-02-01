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

from typing import Type, TypeVar, Generic, Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status, Query, Depends, UploadFile, File, Form
from pydantic import BaseModel
from uuid import UUID
import psycopg2.extensions

from app.auth.dependencies import get_current_user, get_employee_user, get_client_user, get_client_or_employee_user, oauth2_scheme
from app.dependencies.database import get_db
from app.services.error_handling import handle_get_by_id, handle_get_all, handle_create, handle_update, handle_delete
from app.security.institution_scope import get_institution_scope
from app.security.entity_scoping import EntityScopingService, ENTITY_PRODUCT

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
        entity_type: Optional[str] = None
    ):
        self.prefix = prefix
        self.tags = tags
        self.entity_name = entity_name
        self.entity_name_plural = entity_name_plural
        self.description = description or f"{entity_name.title()} management endpoints"
        self.institution_scoped = institution_scoped
        self.entity_type = entity_type  # Entity type for EntityScopingService


def create_crud_routes(
    config: RouteConfig,
    service: CRUDService[T],
    create_schema: Type[U],
    update_schema: Type[V],
    response_schema: Type[W],
    additional_routes: Optional[List] = None,
    requires_user_context: bool = False,
    allows_modification: bool = True
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
        
    Returns:
        APIRouter with all CRUD endpoints
    """
    
    router = APIRouter(
        prefix=config.prefix,
        tags=config.tags,
        dependencies=[Depends(oauth2_scheme)]
    )
    
    # GET /{entity_id}
    @router.get("/{entity_id}", response_model=response_schema)
    def get_entity(
        entity_id: UUID,
        include_archived: bool = Query(False, description=f"Include archived {config.entity_name_plural} if true"),
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get a single entity by ID with optional archived records"""
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
            include_archived,
            extra_kwargs={"scope": scope} if config.institution_scoped else None
        )
    
    # GET /
    @router.get("/", response_model=List[response_schema])
    def get_all_entities(
        include_archived: bool = Query(False, description=f"Include archived {config.entity_name_plural} if true"),
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get all entities with optional archived records"""
        if config.institution_scoped:
            if config.entity_type:
                scope = EntityScopingService.get_scope_for_entity(config.entity_type, current_user)
            else:
                scope = get_institution_scope(current_user)  # Fallback for backward compatibility
        else:
            scope = None

        def service_callable(connection: psycopg2.extensions.connection):
            return service.get_all(connection, scope=scope)

        return handle_get_all(service_callable, db, config.entity_name_plural, include_archived)
    
    # GET (without trailing slash) - alias
    @router.get("", response_model=List[response_schema])
    def get_all_entities_no_trailing_slash(
        include_archived: bool = Query(False, description=f"Include archived {config.entity_name_plural} if true"),
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Alias for get_all_entities endpoint without trailing slash"""
        return get_all_entities(include_archived, current_user, db)
    
    # POST /
    @router.post("/", response_model=response_schema, status_code=status.HTTP_201_CREATED)
    def create_entity(
        create_data: create_schema,
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Create a new entity"""
        data = create_data.dict()
        # Set modified_by from the current user's id
        data["modified_by"] = current_user["user_id"]
        
        # Set user_id if this entity requires user context
        if requires_user_context:
            data["user_id"] = current_user["user_id"]

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
    
    # POST (without trailing slash) - alias
    @router.post("", response_model=response_schema, status_code=status.HTTP_201_CREATED)
    def create_entity_no_trailing_slash(
        create_data: create_schema,
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Alias for create_entity endpoint without trailing slash"""
        return create_entity(create_data, current_user, db)
    
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
            data = update_data.dict(exclude_unset=True)
            if "modified_by" not in data:
                data["modified_by"] = current_user["user_id"]
            if config.institution_scoped:
                if config.entity_type:
                    scope = EntityScopingService.get_scope_for_entity(config.entity_type, current_user)
                else:
                    scope = get_institution_scope(current_user)  # Fallback for backward compatibility
            else:
                scope = None

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
            data = update_data.dict(exclude_unset=True)
            if "modified_by" not in data:
                data["modified_by"] = current_user["user_id"]
            if config.institution_scoped:
                if config.entity_type:
                    scope = EntityScopingService.get_scope_for_entity(config.entity_type, current_user)
                else:
                    scope = get_institution_scope(current_user)  # Fallback for backward compatibility
            else:
                scope = None

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
    from app.utils.query_params import include_archived_optional_query, include_archived_query
    from app.utils.error_messages import entity_not_found
    from app.utils.log import log_error
    from typing import List, Optional
    
    config = RouteConfig(
        prefix="/products",
        tags=["Products"],
        entity_name="product",
        entity_name_plural="products",
        institution_scoped=True
    )

    router = create_crud_routes(
        config=config,
        service=product_service,
        create_schema=ProductCreateSchema,
        update_schema=ProductUpdateSchema,
        response_schema=ProductResponseSchema
    )

    product_image_service = ProductImageService()

    # Override the POST / endpoint to add image validation (Phase 1)
    @router.post("/", response_model=ProductResponseSchema, status_code=status.HTTP_201_CREATED)
    def create_product_with_image_validation(
        create_data: ProductCreateSchema,
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Create a new product with image validation"""
        from app.services.error_handling import handle_create
        from app.utils.error_messages import entity_not_found
        
        data = create_data.dict()
        data["modified_by"] = current_user["user_id"]
        scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)

        # Phase 1: Validate and ensure image exists
        image_storage_path = data.get("image_storage_path")
        image_url = data.get("image_url")
        image_checksum = data.get("image_checksum")
        
        validated_path, validated_url, validated_checksum = product_image_service.validate_product_image_at_creation(
            image_storage_path=image_storage_path,
            image_url=image_url,
            image_checksum=image_checksum
        )
        
        # Update data with validated image values
        data["image_storage_path"] = validated_path
        data["image_url"] = validated_url
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
        storage_path, url_path, checksum = product_image_service.save_image(
            product_id,
            image_bytes=contents,
            content_type=file.content_type or "",
            expected_checksum=client_checksum,
        )

        update_data = {
            "image_url": url_path,
            "image_storage_path": storage_path,
            "image_checksum": checksum,
            "modified_by": current_user["user_id"],
        }

        updated_product = product_service.update(product_id, update_data, db, scope=scope)
        if not updated_product:
            # Clean up newly saved file to avoid orphans
            product_image_service.delete_image(storage_path)
            raise HTTPException(status_code=500, detail="Failed to update product image")

        # Delete old image if it differs from the new one and is not the placeholder
        if (
            product.image_storage_path != storage_path
            and not product_image_service.is_placeholder(product.image_storage_path)
        ):
            product_image_service.delete_image(product.image_storage_path)

        return updated_product

    # =============================================================================
    # ENRICHED PRODUCT ENDPOINTS (with institution_name)
    # =============================================================================

    @router.get("/enriched/", response_model=List[ProductEnrichedResponseSchema])
    def list_enriched_products(
        include_archived: Optional[bool] = include_archived_optional_query("products"),
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """List all products with enriched data (institution_name)"""
        try:
            scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)
            enriched_products = get_enriched_products(
                db,
                scope=scope,
                include_archived=include_archived or False
            )
            return enriched_products
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error getting enriched products: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve enriched products")

    @router.get("/enriched/{product_id}", response_model=ProductEnrichedResponseSchema)
    def get_enriched_product_by_id_route(
        product_id: UUID,
        include_archived: bool = include_archived_query("products"),
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get a single product by ID with enriched data (institution_name)"""
        try:
            scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)
            enriched_product = get_enriched_product_by_id(
                product_id,
                db,
                scope=scope,
                include_archived=include_archived
            )
            if not enriched_product:
                raise entity_not_found("Product", product_id)
            return enriched_product
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error getting enriched product {product_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve enriched product")

    return router


def create_plan_routes() -> APIRouter:
    """Create routes for Plan entity with Employee-only access for modifications, Client/Employee access for viewing"""
    from app.services.crud_service import plan_service
    from app.schemas.consolidated_schemas import PlanCreateSchema, PlanUpdateSchema, PlanResponseSchema, PlanEnrichedResponseSchema
    from app.services.entity_service import get_enriched_plans, get_enriched_plan_by_id
    from app.utils.query_params import include_archived_optional_query, include_archived_query
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
    @router.get("/", response_model=List[PlanResponseSchema])
    def get_all_plans(
        include_archived: bool = Query(False, description="Include archived plans if true"),
        current_user: dict = Depends(get_client_or_employee_user),  # Clients and Employees can view
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get all plans - Available to Clients and Employees only"""
        scope = None  # Plans are not institution-scoped
        def service_callable(connection: psycopg2.extensions.connection):
            return plan_service.get_all(connection, scope=scope)
        return handle_get_all(service_callable, db, "plans", include_archived)
    
    @router.get("/{plan_id}", response_model=PlanResponseSchema)
    def get_plan(
        plan_id: UUID,
        include_archived: bool = Query(False, description="Include archived plans if true"),
        current_user: dict = Depends(get_client_or_employee_user),  # Clients and Employees can view
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get a single plan by ID - Available to Clients and Employees only"""
        scope = None  # Plans are not institution-scoped
        return handle_get_by_id(
            plan_service.get_by_id,
            plan_id,
            db,
            "plan",
            include_archived,
            extra_kwargs={"scope": scope} if config.institution_scoped else None
        )
    
    # Override POST/PUT/DELETE endpoints to be Employee-only
    @router.post("/", response_model=PlanResponseSchema, status_code=status.HTTP_201_CREATED)
    def create_plan(
        create_data: PlanCreateSchema,
        current_user: dict = Depends(get_employee_user),  # Employee-only
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Create a new plan - Employee-only"""
        data = create_data.dict()
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
        data = update_data.dict(exclude_unset=True)
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
    
    @router.get("/enriched/", response_model=List[PlanEnrichedResponseSchema])
    def list_enriched_plans(
        include_archived: Optional[bool] = include_archived_optional_query("plans"),
        current_user: dict = Depends(get_client_or_employee_user),  # Clients and Employees can view
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """List all plans with enriched data (currency_name and currency_code) - Available to Clients and Employees only"""
        try:
            enriched_plans = get_enriched_plans(
                db,
                include_archived=include_archived or False
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
        include_archived: bool = include_archived_query("plans"),
        current_user: dict = Depends(get_client_or_employee_user),  # Clients and Employees can view
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get a single plan by ID with enriched data (currency_name and currency_code) - Available to Clients and Employees only"""
        try:
            enriched_plan = get_enriched_plan_by_id(
                plan_id,
                db,
                include_archived=include_archived
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
        tags=["credit-currencies"],
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
    @router.get("/", response_model=List[CreditCurrencyResponseSchema])
    def get_all_credit_currencies(
        include_archived: bool = Query(False, description="Include archived credit currencies if true"),
        current_user: dict = Depends(get_employee_user),  # Employee-only
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get all credit currencies - Employee-only"""
        scope = None  # Credit currencies are not institution-scoped
        def service_callable(connection: psycopg2.extensions.connection):
            return credit_currency_service.get_all(connection, scope=scope)
        return handle_get_all(service_callable, db, "credit currencies", include_archived)
    
    @router.get("/{currency_id}", response_model=CreditCurrencyResponseSchema)
    def get_credit_currency(
        currency_id: UUID,
        include_archived: bool = Query(False, description="Include archived credit currencies if true"),
        current_user: dict = Depends(get_employee_user),  # Employee-only
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get a single credit currency by ID - Employee-only"""
        scope = None  # Credit currencies are not institution-scoped
        return handle_get_by_id(
            credit_currency_service.get_by_id,
            currency_id,
            db,
            "credit currency",
            include_archived,
            extra_kwargs={"scope": scope} if config.institution_scoped else None
        )
    
    @router.post("/", response_model=CreditCurrencyResponseSchema, status_code=status.HTTP_201_CREATED)
    def create_credit_currency(
        create_data: CreditCurrencyCreateSchema,
        current_user: dict = Depends(get_employee_user),  # Employee-only
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Create a new credit currency - Employee-only"""
        data = create_data.dict()
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
        data = update_data.dict(exclude_unset=True)
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
    from app.schemas.subscription import SubscriptionCreateSchema, SubscriptionUpdateSchema, SubscriptionResponseSchema
    from app.schemas.consolidated_schemas import SubscriptionEnrichedResponseSchema
    from app.services.entity_service import get_enriched_subscriptions, get_enriched_subscription_by_id
    from app.services.error_handling import handle_business_operation, handle_get_by_id
    from app.utils.query_params import include_archived_optional_query
    from typing import List
    
    config = RouteConfig(
        prefix="/subscriptions",
        tags=["Subscriptions"],
        entity_name="subscription",
        entity_name_plural="subscriptions"
    )
    
    router = create_crud_routes(
        config=config,
        service=subscription_service,
        create_schema=SubscriptionCreateSchema,
        update_schema=SubscriptionUpdateSchema,
        response_schema=SubscriptionResponseSchema,
        requires_user_context=True  # Subscriptions require user_id from current_user
    )
    
    # Override base GET routes to add Supplier blocking and Customer self-scoping
    from app.services.error_handling import handle_business_operation
    from app.security.entity_scoping import EntityScopingService, ENTITY_SUBSCRIPTION
    from app.utils.query_params import include_archived_optional_query as include_archived_query
    
    # Override GET /subscriptions/ - List all subscriptions
    @router.get("/", response_model=List[SubscriptionResponseSchema])
    def list_subscriptions_override(
        include_archived: Optional[bool] = include_archived_query("subscriptions"),
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """
        List all subscriptions.
        
        Access Control:
        - Employees: Can see all subscriptions (global access)
        - Customers: Can only see their own subscription (self-scoped)
        - Suppliers: Blocked (403 Forbidden)
        """
        role_type = current_user.get("role_type")
        
        # Block Suppliers
        if role_type == "Supplier":
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Suppliers cannot access subscription data"
            )
        
        # For Customers: self-scope (only their own subscription)
        # For Employees: global access
        if role_type == "Customer":
            user_id = current_user.get("user_id")
            if not user_id:
                raise HTTPException(status_code=401, detail="User ID not found in token")
            
            def _get_subscriptions():
                return subscription_service.get_all(
                    db,
                    scope=None,  # No institution scoping for customers
                    include_archived=include_archived or False,
                    additional_conditions=[("user_id = %s::uuid", str(user_id))]
                )
        else:  # Employee
            def _get_subscriptions():
                return subscription_service.get_all(
                    db,
                    scope=None,  # Global access for employees
                    include_archived=include_archived or False
                )
        
        return handle_business_operation(
            _get_subscriptions,
            "subscription list retrieval"
        )
    
    # Override GET /subscriptions/{subscription_id} - Get single subscription
    @router.get("/{subscription_id}", response_model=SubscriptionResponseSchema)
    def get_subscription_override(
        subscription_id: UUID,
        include_archived: Optional[bool] = include_archived_query("subscriptions"),
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """
        Get a single subscription by ID.
        
        Access Control:
        - Employees: Can see any subscription (global access)
        - Customers: Can only see their own subscription (self-scoped, 404 if not theirs)
        - Suppliers: Blocked (403 Forbidden)
        """
        role_type = current_user.get("role_type")
        
        # Block Suppliers
        if role_type == "Supplier":
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Suppliers cannot access subscription data"
            )
        
        # For Customers: verify the subscription belongs to them
        # For Employees: global access
        if role_type == "Customer":
            user_id = current_user.get("user_id")
            if not user_id:
                raise HTTPException(status_code=401, detail="User ID not found in token")
            
            def _get_subscription():
                subscription = subscription_service.get_by_id(
                    subscription_id,
                    db,
                    scope=None,  # No institution scoping for customers
                    include_archived=include_archived
                )
                if not subscription:
                    raise HTTPException(status_code=404, detail="Subscription not found")
                
                # Verify the subscription belongs to the customer
                if subscription.user_id != user_id:
                    raise HTTPException(
                        status_code=404,
                        detail="Subscription not found"  # Don't reveal existence of other subscriptions
                    )
                
                return subscription
        else:  # Employee
            def _get_subscription():
                subscription = subscription_service.get_by_id(
                    subscription_id,
                    db,
                    scope=None,  # Global access for employees
                    include_archived=include_archived
                )
                if not subscription:
                    raise HTTPException(status_code=404, detail="Subscription not found")
                return subscription
        
        return handle_business_operation(
            _get_subscription,
            "subscription retrieval"
        )
    
    # ENRICHED SUBSCRIPTION ENDPOINTS (with user and plan information)
    # GET /subscriptions/enriched/ - List all subscriptions with enriched data
    @router.get("/enriched/", response_model=List[SubscriptionEnrichedResponseSchema])
    def list_enriched_subscriptions(
        include_archived: Optional[bool] = include_archived_optional_query("subscriptions"),
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """
        List all subscriptions with enriched data.
        
        Access Control:
        - Employees: Can see all subscriptions (global access)
        - Customers: Can only see their own subscription (self-scoped)
        - Suppliers: Blocked (403 Forbidden)
        
        Includes: user information (full_name, username, email, status, cellphone) 
        and plan information (name, credit, price, rollover, rollover_cap, status).
        """
        role_type = current_user.get("role_type")
        
        # Block Suppliers
        if role_type == "Supplier":
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Suppliers cannot access subscription data"
            )
        
        # For Customers: self-scope (only their own subscription)
        # For Employees: global access (scope=None)
        if role_type == "Customer":
            user_id = current_user.get("user_id")
            if not user_id:
                raise HTTPException(status_code=401, detail="User ID not found in token")
            
            def _get_enriched_subscriptions():
                return get_enriched_subscriptions(
                    db,
                    scope=None,  # No institution scoping for customers (user-level filtering)
                    include_archived=include_archived or False,
                    user_id=user_id  # Filter by customer's own user_id
                )
        else:  # Employee
            def _get_enriched_subscriptions():
                return get_enriched_subscriptions(
                    db,
                    scope=None,  # Global access for employees
                    include_archived=include_archived or False
                )
        
        return handle_business_operation(
            _get_enriched_subscriptions,
            "enriched subscription list retrieval"
        )
    
    # GET /subscriptions/enriched/{subscription_id} - Get a single subscription with enriched data
    @router.get("/enriched/{subscription_id}", response_model=SubscriptionEnrichedResponseSchema)
    def get_enriched_subscription_by_id_route(
        subscription_id: UUID,
        include_archived: Optional[bool] = include_archived_optional_query("subscriptions"),
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """
        Get a single subscription by ID with enriched data.
        
        Access Control:
        - Employees: Can see any subscription (global access)
        - Customers: Can only see their own subscription (self-scoped, 404 if not theirs)
        - Suppliers: Blocked (403 Forbidden)
        
        Includes: user information (full_name, username, email, status, cellphone) 
        and plan information (name, credit, price, rollover, rollover_cap, status).
        """
        role_type = current_user.get("role_type")
        
        # Block Suppliers
        if role_type == "Supplier":
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Suppliers cannot access subscription data"
            )
        
        # For Customers: verify the subscription belongs to them
        # For Employees: global access
        if role_type == "Customer":
            user_id = current_user.get("user_id")
            if not user_id:
                raise HTTPException(status_code=401, detail="User ID not found in token")
            
            def _get_enriched_subscription():
                # First, get the subscription to verify ownership
                enriched_subscription = get_enriched_subscription_by_id(
                    subscription_id,
                    db,
                    scope=None,  # No institution scoping for customers
                    include_archived=include_archived
                )
                if not enriched_subscription:
                    raise HTTPException(status_code=404, detail="Subscription not found")
                
                # Verify the subscription belongs to the customer
                if enriched_subscription.user_id != user_id:
                    raise HTTPException(
                        status_code=404,
                        detail="Subscription not found"  # Don't reveal existence of other subscriptions
                    )
                
                return enriched_subscription
        else:  # Employee
            def _get_enriched_subscription():
                enriched_subscription = get_enriched_subscription_by_id(
                    subscription_id,
                    db,
                    scope=None,  # Global access for employees
                    include_archived=include_archived
                )
                if not enriched_subscription:
                    raise HTTPException(status_code=404, detail="Subscription not found")
                return enriched_subscription
        
        return handle_business_operation(
            _get_enriched_subscription,
            "enriched subscription retrieval"
        )
    
    return router


def create_institution_routes() -> APIRouter:
    """Create routes for Institution entity with POST restricted to Employees only"""
    from app.services.crud_service import institution_service
    from app.schemas.consolidated_schemas import InstitutionCreateSchema, InstitutionUpdateSchema, InstitutionResponseSchema
    from app.auth.dependencies import get_employee_user
    from app.services.error_handling import handle_create
    
    config = RouteConfig(
        prefix="/institutions",
        tags=["Institutions"],
        entity_name="institution",
        entity_name_plural="institutions"
    )
    
    router = create_crud_routes(
        config=config,
        service=institution_service,
        create_schema=InstitutionCreateSchema,
        update_schema=InstitutionUpdateSchema,
        response_schema=InstitutionResponseSchema
    )
    
    # Override POST endpoint to restrict creation to Employees only
    from fastapi import status
    
    @router.post("/", response_model=InstitutionResponseSchema, status_code=status.HTTP_201_CREATED)
    def create_institution(
        create_data: InstitutionCreateSchema,
        current_user: dict = Depends(get_employee_user),  # Employee-only
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Create a new institution - Employee-only"""
        data = create_data.dict()
        data["modified_by"] = current_user["user_id"]
        scope = None  # Institutions are not institution-scoped
        
        def create_callable(payload: dict, connection: psycopg2.extensions.connection):
            return institution_service.create(payload, connection, scope=scope)
        
        return handle_create(create_callable, data, db, "institution")
    
    return router


def create_payment_method_routes() -> APIRouter:
    """Create routes for PaymentMethod entity with enriched endpoints"""
    from app.services.crud_service import payment_method_service
    from app.schemas.payment_method import PaymentMethodCreateSchema, PaymentMethodUpdateSchema, PaymentMethodResponseSchema, PaymentMethodEnrichedResponseSchema
    from app.services.entity_service import get_enriched_payment_methods, get_enriched_payment_method_by_id
    from app.services.error_handling import handle_business_operation
    from app.utils.query_params import include_archived_optional_query
    from app.auth.dependencies import get_employee_or_customer_user
    from app.security.scoping import EmployeeCustomerAccessControl
    from typing import List
    from fastapi import HTTPException
    
    config = RouteConfig(
        prefix="/payment-methods",
        tags=["Payment Methods"],
        entity_name="payment method",
        entity_name_plural="payment methods"
    )
    
    router = create_crud_routes(
        config=config,
        service=payment_method_service,
        create_schema=PaymentMethodCreateSchema,
        update_schema=PaymentMethodUpdateSchema,
        response_schema=PaymentMethodResponseSchema,
        requires_user_context=True  # Payment methods require user_id from current_user
    )
    
    # Override POST endpoint to set is_default=True if this is the user's first payment method
    @router.post("/", response_model=PaymentMethodResponseSchema, status_code=status.HTTP_201_CREATED)
    def create_payment_method(
        create_data: PaymentMethodCreateSchema,
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Create a new payment method with optional address creation - sets is_default=True if this is the user's first payment method"""
        from app.services.error_handling import handle_business_operation
        from app.services.payment_method_service import create_payment_method_with_address
        from app.utils.log import log_info
        from app.utils.db import db_read
        
        def _create_payment_method():
            data = create_data.dict()
            
            # Extract address_id and address_data from request
            address_id = data.pop("address_id", None)
            address_data = data.pop("address_data", None)
            
            # Check if user has any existing non-archived payment methods
            query = """
                SELECT COUNT(*) as count
                FROM payment_method
                WHERE user_id = %s::uuid
                  AND is_archived = FALSE
            """
            result = db_read(query, (str(current_user["user_id"]),), connection=db, fetch_one=True)
            existing_count = result["count"] if result else 0
            
            # If no existing payment methods, set is_default=True
            # Otherwise, respect the value from the request (defaults to False from schema)
            if existing_count == 0:
                data["is_default"] = True
                log_info(f"Setting is_default=True for first payment method for user {current_user['user_id']}")
            else:
                # User already has payment methods, use the value from request (defaults to False)
                # Explicit True values from the request are preserved
                log_info(f"User {current_user['user_id']} already has {existing_count} payment method(s), is_default={data.get('is_default', False)}")
            
            # Use atomic service method for payment method + address creation
            return create_payment_method_with_address(
                payment_method_data=data,
                address_id=address_id,
                address_data=address_data,
                current_user=current_user,
                db=db,
                scope=None  # Payment methods are user-scoped, not institution-scoped
            )
        
        return handle_business_operation(
            _create_payment_method,
            "payment method creation",
            "Payment method created successfully"
        )
    
    # POST (without trailing slash) - alias
    @router.post("", response_model=PaymentMethodResponseSchema, status_code=status.HTTP_201_CREATED)
    def create_payment_method_no_trailing_slash(
        create_data: PaymentMethodCreateSchema,
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Alias for create_payment_method endpoint without trailing slash"""
        return create_payment_method(create_data, current_user, db)
    
    # ENRICHED PAYMENT METHOD ENDPOINTS (with user information)
    # GET /payment-methods/enriched/ - List all payment methods with enriched data
    @router.get("/enriched/", response_model=List[PaymentMethodEnrichedResponseSchema])
    def list_enriched_payment_methods(
        include_archived: Optional[bool] = include_archived_optional_query("payment_methods"),
        current_user: dict = Depends(get_employee_or_customer_user),  # Blocks Suppliers
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """
        List all payment methods with enriched data.
        
        Access Control:
        - Employees: Can see all payment methods (global access)
        - Customers: Can only see their own payment methods (self-scoped)
        - Suppliers: Blocked (403 Forbidden)
        
        Includes: user information (full_name, username, email, cellphone).
        """
        # Get user_id filter (None for Employees, UUID for Customers)
        user_id, error = EmployeeCustomerAccessControl.enforce_access(current_user)
        if error:
            raise HTTPException(**error)
        
        def _get_enriched_payment_methods():
            return get_enriched_payment_methods(
                db,
                scope=None,  # No institution scoping for this pattern
                include_archived=include_archived or False,
                user_id=user_id  # None for Employees, UUID for Customers
            )
        
        return handle_business_operation(
            _get_enriched_payment_methods,
            "enriched payment method list retrieval"
        )
    
    # GET /payment-methods/enriched/{payment_method_id} - Get a single payment method with enriched data
    @router.get("/enriched/{payment_method_id}", response_model=PaymentMethodEnrichedResponseSchema)
    def get_enriched_payment_method_by_id_route(
        payment_method_id: UUID,
        include_archived: Optional[bool] = include_archived_optional_query("payment_methods"),
        current_user: dict = Depends(get_employee_or_customer_user),  # Blocks Suppliers
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """
        Get a single payment method by ID with enriched data.
        
        Access Control:
        - Employees: Can see any payment method (global access)
        - Customers: Can only see their own payment methods (self-scoped, 404 if not theirs)
        - Suppliers: Blocked (403 Forbidden)
        
        Includes: user information (full_name, username, email, cellphone).
        """
        def _get_enriched_payment_method():
            enriched_payment_method = get_enriched_payment_method_by_id(
                payment_method_id,
                db,
                scope=None,  # No institution scoping for this pattern
                include_archived=include_archived
            )
            if not enriched_payment_method:
                raise HTTPException(status_code=404, detail="Payment method not found")
            
            # Verify ownership for Customers
            error = EmployeeCustomerAccessControl.verify_ownership(
                enriched_payment_method.user_id,
                current_user
            )
            if error:
                raise HTTPException(**error)
            
            return enriched_payment_method
        
        return handle_business_operation(
            _get_enriched_payment_method,
            "enriched payment method retrieval"
        )
    
    return router


def create_plate_routes() -> APIRouter:
    """Create routes for Plate entity"""
    from app.services.crud_service import plate_service
    from app.schemas.consolidated_schemas import PlateCreateSchema, PlateUpdateSchema, PlateResponseSchema, PlateEnrichedResponseSchema
    from app.services.entity_service import get_enriched_plates, get_enriched_plate_by_id
    from app.utils.query_params import include_archived_optional_query, include_archived_query
    from app.utils.error_messages import entity_not_found
    from app.utils.log import log_error
    from typing import List, Optional
    
    config = RouteConfig(
        prefix="/plates",
        tags=["Plates"],
        entity_name="plate",
        entity_name_plural="plates",
        institution_scoped=True
    )
    
    router = create_crud_routes(
        config=config,
        service=plate_service,
        create_schema=PlateCreateSchema,
        update_schema=PlateUpdateSchema,
        response_schema=PlateResponseSchema
    )
    
    # Override GET endpoints to allow Customers to view plates
    from app.auth.dependencies import get_client_or_employee_user
    from app.services.error_handling import handle_get_by_id, handle_get_all
    from fastapi import Query
    
    @router.get("/", response_model=List[PlateResponseSchema])
    def get_all_plates(
        include_archived: bool = Query(False, description="Include archived plates if true"),
        current_user: dict = Depends(get_client_or_employee_user),  # Customers and Employees can view
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get all plates - Available to Customers and Employees (no scoping for Customers)"""
        # Customers can see all plates (no scoping), Suppliers/Employees use institution scoping
        if current_user.get("role_type") == "Customer":
            scope = None  # No scoping for Customers
        else:
            from app.security.entity_scoping import EntityScopingService, ENTITY_PLATE
            scope = EntityScopingService.get_scope_for_entity(ENTITY_PLATE, current_user)
        
        def service_callable(connection: psycopg2.extensions.connection):
            return plate_service.get_all(connection, scope=scope)
        
        return handle_get_all(service_callable, db, "plates", include_archived)
    
    @router.get("/{plate_id}", response_model=PlateResponseSchema)
    def get_plate(
        plate_id: UUID,
        include_archived: bool = Query(False, description="Include archived plates if true"),
        current_user: dict = Depends(get_client_or_employee_user),  # Customers and Employees can view
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get a single plate by ID - Available to Customers and Employees"""
        # Customers can see all plates (no scoping), Suppliers/Employees use institution scoping
        if current_user.get("role_type") == "Customer":
            scope = None  # No scoping for Customers
        else:
            from app.security.entity_scoping import EntityScopingService, ENTITY_PLATE
            scope = EntityScopingService.get_scope_for_entity(ENTITY_PLATE, current_user)
        
        return handle_get_by_id(
            plate_service.get_by_id,
            plate_id,
            db,
            "plate",
            include_archived,
            extra_kwargs={"scope": scope} if scope else None
        )

    # =============================================================================
    # ENRICHED PLATE ENDPOINTS (with institution, restaurant, product, address details)
    # =============================================================================
    
    @router.get("/enriched/", response_model=List[PlateEnrichedResponseSchema])
    def list_enriched_plates(
        include_archived: Optional[bool] = include_archived_optional_query("plates"),
        current_user: dict = Depends(get_client_or_employee_user),  # Customers and Employees can view
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """List all plates with enriched data - Available to Customers and Employees"""
        try:
            # Customers can see all plates (no scoping), Suppliers/Employees use institution scoping
            if current_user.get("role_type") == "Customer":
                scope = None  # No scoping for Customers
            else:
                scope = get_institution_scope(current_user)
            
            enriched_plates = get_enriched_plates(
                db,
                scope=scope,
                include_archived=include_archived or False
            )
            return enriched_plates
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error getting enriched plates: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve enriched plates")

    @router.get("/enriched/{plate_id}", response_model=PlateEnrichedResponseSchema)
    def get_enriched_plate_by_id_route(
        plate_id: UUID,
        include_archived: bool = include_archived_query("plates"),
        current_user: dict = Depends(get_client_or_employee_user),  # Customers and Employees can view
        db: psycopg2.extensions.connection = Depends(get_db)
    ):
        """Get a single plate by ID with enriched data - Available to Customers and Employees"""
        try:
            # Customers can see all plates (no scoping), Suppliers/Employees use institution scoping
            if current_user.get("role_type") == "Customer":
                scope = None  # No scoping for Customers
            else:
                scope = get_institution_scope(current_user)
            
            enriched_plate = get_enriched_plate_by_id(
                plate_id,
                db,
                scope=scope,
                include_archived=include_archived
            )
            if not enriched_plate:
                raise entity_not_found("Plate", plate_id)
            return enriched_plate
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error getting enriched plate {plate_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve enriched plate")

    return router


def create_geolocation_routes() -> APIRouter:
    """Create routes for Geolocation entity"""
    from app.services.crud_service import geolocation_service
    from app.schemas.geolocation import GeolocationCreateSchema, GeolocationUpdateSchema, GeolocationResponseSchema
    
    config = RouteConfig(
        prefix="/geolocations",
        tags=["geolocations"],
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
    """Create routes for InstitutionEntity entity"""
    from app.services.crud_service import institution_entity_service
    from app.schemas.consolidated_schemas import InstitutionEntityCreateSchema, InstitutionEntityUpdateSchema, InstitutionEntityResponseSchema
    
    config = RouteConfig(
        prefix="/institution-entities",
        tags=["Institution Entities"],
        entity_name="institution entity",
        entity_name_plural="institution entities",
        institution_scoped=True
    )
    
    return create_crud_routes(
        config=config,
        service=institution_entity_service,
        create_schema=InstitutionEntityCreateSchema,
        update_schema=InstitutionEntityUpdateSchema,
        response_schema=InstitutionEntityResponseSchema
    )


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

def create_institution_payment_attempt_routes() -> APIRouter:
    """Create routes for InstitutionPaymentAttempt entity (status updates allowed)"""
    from app.services.crud_service import institution_payment_attempt_service
    from app.schemas.payment_methods.institution_payment_attempt import (
        InstitutionPaymentAttemptCreateSchema,
        InstitutionPaymentAttemptUpdateSchema,
        InstitutionPaymentAttemptResponseSchema
    )
    
    config = RouteConfig(
        prefix="/institution-payment-attempts",
        tags=["Institution Payment Attempts"],
        entity_name="institution payment attempt",
        entity_name_plural="institution payment attempts"
    )
    
    return create_crud_routes(
        config=config,
        service=institution_payment_attempt_service,
        create_schema=InstitutionPaymentAttemptCreateSchema,
        update_schema=InstitutionPaymentAttemptUpdateSchema,  # Allows status updates
        response_schema=InstitutionPaymentAttemptResponseSchema,
        requires_user_context=False,  # Admin/system entity
        allows_modification=True  # ← KEY: Allows status updates only
    )


def create_client_payment_attempt_routes() -> APIRouter:
    """Create routes for ClientPaymentAttempt entity (status updates allowed)"""
    from app.services.crud_service import client_payment_attempt_service
    from app.schemas.payment_methods.client_payment_attempt import (
        ClientPaymentAttemptCreateSchema,
        ClientPaymentAttemptUpdateSchema,
        ClientPaymentAttemptResponseSchema
    )
    
    config = RouteConfig(
        prefix="/client-payment-attempts",
        tags=["Client Payment Attempts"],
        entity_name="client payment attempt",
        entity_name_plural="client payment attempts"
    )
    
    return create_crud_routes(
        config=config,
        service=client_payment_attempt_service,
        create_schema=ClientPaymentAttemptCreateSchema,
        update_schema=ClientPaymentAttemptUpdateSchema,  # Allows status and resolution_date updates
        response_schema=ClientPaymentAttemptResponseSchema,
        requires_user_context=False,  # No direct user_id column - linked via payment_method_id
        allows_modification=True  # ← KEY: Allows status updates only
    )


def create_institution_bank_account_routes() -> APIRouter:
    """Create routes for InstitutionBankAccount entity (immutable - no modification allowed)"""
    from app.services.crud_service import institution_bank_account_service
    from app.schemas.institution_bank_account import (
        InstitutionBankAccountCreateSchema, 
        InstitutionBankAccountResponseSchema
    )
    
    config = RouteConfig(
        prefix="/institution-bank-accounts",
        tags=["Institution Bank Accounts"],
        entity_name="institution bank account",
        entity_name_plural="institution bank accounts"
    )
    
    return create_crud_routes(
        config=config,
        service=institution_bank_account_service,
        create_schema=InstitutionBankAccountCreateSchema,
        update_schema=InstitutionBankAccountCreateSchema,  # Not used for immutable entities
        response_schema=InstitutionBankAccountResponseSchema,
        requires_user_context=False,  # Admin/system entity
        allows_modification=False  # ← KEY: Immutable entity - no PUT/update routes
    )

