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

from collections.abc import Callable
from datetime import UTC
from typing import Any, Generic, TypeVar
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel

from app.auth.dependencies import (
    get_client_or_employee_user,
    get_current_user,
    get_employee_user,
    get_resolved_locale,
    oauth2_scheme,
)
from app.config.settings import settings
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.security.entity_scoping import (
    ENTITY_INSTITUTION_ENTITY,
    ENTITY_PLATE,
    ENTITY_PRODUCT,
    EntityScopingService,
)
from app.security.institution_scope import get_institution_scope
from app.services.error_handling import handle_create, handle_delete, handle_get_all, handle_get_by_id, handle_update
from app.utils.pagination import PaginationParams, get_pagination_params, set_pagination_headers

T = TypeVar("T", bound=BaseModel)  # DTO type
U = TypeVar("U", bound=BaseModel)  # Create schema type
V = TypeVar("V", bound=BaseModel)  # Update schema type
W = TypeVar("W", bound=BaseModel)  # Response schema type


class CRUDService(Generic[T]):
    """Generic CRUD service interface"""

    def get_by_id(self, entity_id: UUID, db: psycopg2.extensions.connection) -> T | None:
        raise NotImplementedError

    def get_by_id_non_archived(self, entity_id: UUID, db: psycopg2.extensions.connection) -> T | None:
        raise NotImplementedError

    def get_all(self, db: psycopg2.extensions.connection) -> list[T]:
        raise NotImplementedError

    def get_all_non_archived(self, db: psycopg2.extensions.connection) -> list[T]:
        raise NotImplementedError

    def create(self, data: dict[str, Any], db: psycopg2.extensions.connection) -> T | None:
        raise NotImplementedError

    def update(self, entity_id: UUID, data: dict[str, Any], db: psycopg2.extensions.connection) -> T | None:
        raise NotImplementedError

    def soft_delete(self, entity_id: UUID, db: psycopg2.extensions.connection) -> bool:
        raise NotImplementedError


class RouteConfig:
    """Configuration for route generation"""

    def __init__(
        self,
        prefix: str,
        tags: list[str],
        entity_name: str,
        entity_name_plural: str,
        description: str | None = None,
        institution_scoped: bool = False,
        entity_type: str | None = None,
        immutable_update_fields: list[str] | None = None,
        paginatable: bool = False,
        pre_archive_validator: Callable | None = None,
    ):
        self.prefix = prefix
        self.tags = tags
        self.entity_name = entity_name
        self.entity_name_plural = entity_name_plural
        self.description = description or f"{entity_name.title()} management endpoints"
        self.institution_scoped = institution_scoped
        self.entity_type = entity_type  # Entity type for EntityScopingService
        self.immutable_update_fields = immutable_update_fields or []
        self.paginatable = paginatable
        self.pre_archive_validator = pre_archive_validator


def create_crud_routes(
    config: RouteConfig,
    service: CRUDService[T],
    create_schema: type[U],
    update_schema: type[V],
    response_schema: type[W],
    additional_routes: list | None = None,
    requires_user_context: bool = False,
    allows_modification: bool = True,
    before_create: Callable[[dict, psycopg2.extensions.connection], dict] | None = None,
    before_update: Callable[[dict, psycopg2.extensions.connection, UUID], dict] | None = None,
    custom_routes_first: Callable[[APIRouter], None] | None = None,
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

    router = APIRouter(prefix=config.prefix, tags=config.tags, dependencies=[Depends(oauth2_scheme)])

    # Register custom routes FIRST — they take precedence when path+method match
    if custom_routes_first:
        custom_routes_first(router)

    from app.security.field_policies import ensure_supplier_admin_or_manager

    # GET /{entity_id}
    @router.get("/{entity_id}", response_model=response_schema)
    def get_entity(
        entity_id: UUID,
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """Get a single entity by ID (non-archived only)"""
        ensure_supplier_admin_or_manager(current_user)
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
            extra_kwargs={"scope": scope} if config.institution_scoped else None,
        )

    # GET (collection root - no trailing slash per REST convention)
    if config.paginatable:

        @router.get("", response_model=list[response_schema])
        def get_all_entities(
            response: Response,
            pagination: PaginationParams | None = Depends(get_pagination_params),
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Get all entities (non-archived only). Supports optional pagination via page/page_size query params."""
            ensure_supplier_admin_or_manager(current_user)
            if config.institution_scoped:
                if config.entity_type:
                    scope = EntityScopingService.get_scope_for_entity(config.entity_type, current_user)
                else:
                    scope = get_institution_scope(current_user)
            else:
                scope = None

            def service_callable(connection: psycopg2.extensions.connection):
                return service.get_all(
                    connection,
                    scope=scope,
                    include_archived=False,
                    page=pagination.page if pagination else None,
                    page_size=pagination.page_size if pagination else None,
                )

            result = handle_get_all(service_callable, db, config.entity_name_plural)
            set_pagination_headers(response, result)
            return result
    else:

        @router.get("", response_model=list[response_schema])
        def get_all_entities(
            current_user: dict = Depends(get_current_user), db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Get all entities (non-archived only)"""
            ensure_supplier_admin_or_manager(current_user)
            if config.institution_scoped:
                if config.entity_type:
                    scope = EntityScopingService.get_scope_for_entity(config.entity_type, current_user)
                else:
                    scope = get_institution_scope(current_user)
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
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """Create a new entity"""
        ensure_supplier_admin_or_manager(current_user)
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
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Update an existing entity"""
            ensure_supplier_admin_or_manager(current_user)
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
                    raise envelope_exception(
                        ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity=config.entity_name.title()
                    )
                for field in config.immutable_update_fields:
                    if field in data:
                        existing_val = getattr(existing, field, None)
                        if str(data[field]) != str(existing_val):
                            raise envelope_exception(
                                ErrorCode.ENTITY_FIELD_IMMUTABLE, status=400, locale=locale, field=field
                            )
                        data.pop(field, None)

            def update_callable(target_id: UUID, payload: dict, connection: psycopg2.extensions.connection):
                return service.update(target_id, payload, connection, scope=scope)

            return handle_update(update_callable, entity_id, data, db, config.entity_name)

        @router.patch("/{entity_id}", response_model=response_schema)
        def partial_update_entity(
            entity_id: UUID,
            update_data: update_schema,
            current_user: dict = Depends(get_current_user),
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
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
                    raise envelope_exception(
                        ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity=config.entity_name.title()
                    )
                for field in config.immutable_update_fields:
                    if field in data:
                        existing_val = getattr(existing, field, None)
                        if str(data[field]) != str(existing_val):
                            raise envelope_exception(
                                ErrorCode.ENTITY_FIELD_IMMUTABLE, status=400, locale=locale, field=field
                            )
                        data.pop(field, None)

            def partial_update_callable(target_id: UUID, payload: dict, connection: psycopg2.extensions.connection):
                return service.update(target_id, payload, connection, scope=scope)

            return handle_update(partial_update_callable, entity_id, data, db, config.entity_name)

    # DELETE /{entity_id}
    @router.delete("/{entity_id}", response_model=dict)
    def delete_entity(
        entity_id: UUID,
        current_user: dict = Depends(get_current_user),
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """Delete an entity (soft delete)"""
        ensure_supplier_admin_or_manager(current_user)
        if config.institution_scoped:
            if config.entity_type:
                scope = EntityScopingService.get_scope_for_entity(config.entity_type, current_user)
            else:
                scope = get_institution_scope(current_user)  # Fallback for backward compatibility
        else:
            scope = None

        if config.pre_archive_validator:
            config.pre_archive_validator(entity_id, db)

        def delete_callable(target_id: UUID, connection: psycopg2.extensions.connection):
            return service.soft_delete(target_id, current_user["user_id"], connection, scope=scope)

        handle_delete(delete_callable, entity_id, db, config.entity_name)
        return {"detail": f"{config.entity_name.title()} deleted successfully"}

    # Add any additional custom routes
    if additional_routes:
        for _route in additional_routes:
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

    from app.schemas.consolidated_schemas import (
        ProductCreateSchema,
        ProductEnrichedResponseSchema,
        ProductIngredientResponseSchema,
        ProductIngredientsSetSchema,
        ProductResponseSchema,
        ProductUpdateSchema,
    )
    from app.security.field_policies import ensure_supplier_admin_or_manager
    from app.services.crud_service import product_service
    from app.services.entity_service import get_enriched_product_by_id, get_enriched_products
    from app.services.product_image_service import ProductImageService
    from app.utils.error_messages import entity_not_found
    from app.utils.log import log_error

    config = RouteConfig(
        prefix="/products",
        tags=["Products"],
        entity_name="product",
        entity_name_plural="products",
        institution_scoped=True,
        entity_type=ENTITY_PRODUCT,
        paginatable=True,
    )
    product_image_service = ProductImageService()

    def _product_custom_routes(router: APIRouter) -> None:
        # Static path segments must be registered before /{product_id} or "enriched" is parsed as a UUID.
        @router.get("/enriched", response_model=list[ProductEnrichedResponseSchema])
        def list_enriched_products(
            current_user: dict = Depends(get_current_user), db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """List all products with enriched data (institution_name). Non-archived only."""
            try:
                scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)
                return get_enriched_products(db, scope=scope, include_archived=False)
            except HTTPException:
                raise
            except Exception as e:
                log_error(f"Error getting enriched products: {e}")
                raise HTTPException(status_code=500, detail="Failed to retrieve enriched products") from None

        @router.get("/enriched/{product_id}", response_model=ProductEnrichedResponseSchema)
        def get_enriched_product_by_id_route(
            product_id: UUID,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db),
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
                raise HTTPException(status_code=500, detail="Failed to retrieve enriched product") from None

        @router.get("/{product_id}/ingredients", response_model=list[ProductIngredientResponseSchema])
        def get_product_ingredients_route(
            product_id: UUID,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Get ordered ingredient list for a product."""
            from app.services.ingredient_service import get_product_ingredients

            market_id = (
                str(current_user["subscription_market_id"]) if current_user.get("subscription_market_id") else None
            )
            return get_product_ingredients(product_id, market_id, db)

        @router.post(
            "/{product_id}/ingredients",
            response_model=list[ProductIngredientResponseSchema],
            status_code=status.HTTP_200_OK,
        )
        def set_product_ingredients_route(
            product_id: UUID,
            body: ProductIngredientsSetSchema,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Full-replace ingredient list for a product. Accepts {ingredient_ids: [UUID, ...]}."""
            from app.services.ingredient_service import set_product_ingredients

            scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)
            product = product_service.get_by_id(product_id, db, scope=scope)
            if not product or product.is_archived:
                raise entity_not_found("Product", product_id)
            market_id = (
                str(current_user["subscription_market_id"]) if current_user.get("subscription_market_id") else None
            )
            return set_product_ingredients(product_id, body.ingredient_ids, current_user["user_id"], market_id, db)

        @router.get("/{product_id}", response_model=ProductResponseSchema)
        def get_product_with_resolved_urls(
            product_id: UUID,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Get a single product by ID with resolved image URLs (signed URLs when GCS)."""
            scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)
            product = product_service.get_by_id(product_id, db, scope=scope)
            if not product or product.is_archived:
                raise entity_not_found("Product", product_id)
            data = product.model_dump(mode="json")
            from app.utils.gcs import resolve_product_image_urls

            data = resolve_product_image_urls(data)
            return ProductResponseSchema(**data)

        @router.post("", response_model=ProductResponseSchema, status_code=status.HTTP_201_CREATED)
        def create_product_with_image_validation(
            create_data: ProductCreateSchema,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Create a new product with image validation.
            Supports composite creation: embed ingredient_ids for atomic product + ingredients."""
            from app.services.ingredient_service import set_product_ingredients

            data = create_data.model_dump()
            ingredient_ids = data.pop("ingredient_ids", None)
            data["modified_by"] = current_user["user_id"]
            scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)
            validated = product_image_service.validate_product_image_at_creation(
                image_storage_path=data.get("image_storage_path"),
                image_url=data.get("image_url"),
                image_checksum=data.get("image_checksum"),
            )
            data["image_storage_path"] = validated["storage_path"]
            data["image_url"] = validated["image_url"]
            data["image_thumbnail_storage_path"] = validated["thumbnail_storage_path"]
            data["image_thumbnail_url"] = validated["thumbnail_url"]
            data["image_checksum"] = validated["checksum"]
            has_ingredients = ingredient_ids is not None and len(ingredient_ids) > 0

            try:
                product = product_service.create(data, db, scope=scope, commit=not has_ingredients)
                if not product:
                    raise HTTPException(status_code=500, detail="Failed to create product")

                if has_ingredients:
                    market_id = (
                        str(current_user["subscription_market_id"])
                        if current_user.get("subscription_market_id")
                        else None
                    )
                    set_product_ingredients(
                        product.product_id,
                        ingredient_ids,
                        current_user["user_id"],
                        market_id,
                        db,
                        commit=False,
                    )
                    db.commit()

                from app.utils.gcs import resolve_product_image_urls

                return ProductResponseSchema(**resolve_product_image_urls(product.model_dump(mode="json")))
            except HTTPException:
                raise
            except Exception as e:
                db.rollback()
                log_error(f"Error creating product: {e}")
                raise HTTPException(status_code=500, detail="Error creating product") from None

        @router.put("/{product_id}", response_model=ProductResponseSchema)
        def update_product_with_ingredients(
            product_id: UUID,
            update_data: ProductUpdateSchema,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Update a product. If ingredient_ids is provided, full-replaces ingredient set atomically."""
            from app.services.ingredient_service import set_product_ingredients

            ensure_supplier_admin_or_manager(current_user)
            data = update_data.model_dump(exclude_unset=True)
            ingredient_ids = data.pop("ingredient_ids", None)
            data["modified_by"] = current_user["user_id"]
            scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)
            has_ingredients = ingredient_ids is not None

            try:
                product = product_service.update(product_id, data, db, scope=scope, commit=not has_ingredients)
                if not product:
                    raise HTTPException(status_code=500, detail="Failed to update product")

                if has_ingredients:
                    market_id = (
                        str(current_user["subscription_market_id"])
                        if current_user.get("subscription_market_id")
                        else None
                    )
                    if len(ingredient_ids) > 0:
                        set_product_ingredients(
                            product_id,
                            ingredient_ids,
                            current_user["user_id"],
                            market_id,
                            db,
                            commit=False,
                        )
                    else:
                        # Empty list = remove all ingredients
                        cursor = db.cursor()
                        cursor.execute(
                            "DELETE FROM ops.product_ingredient WHERE product_id = %s",
                            (str(product_id),),
                        )
                    db.commit()

                from app.utils.gcs import resolve_product_image_urls

                return ProductResponseSchema(**resolve_product_image_urls(product.model_dump(mode="json")))
            except HTTPException:
                raise
            except Exception as e:
                db.rollback()
                log_error(f"Error updating product {product_id}: {e}")
                raise HTTPException(status_code=500, detail="Error updating product") from None

        @router.post("/{product_id}/image", response_model=ProductResponseSchema)
        async def upload_product_image(
            product_id: UUID,
            file: UploadFile = File(...),
            client_checksum: str = Form(...),
            checksum_algorithm: str = Form(default="sha256"),
            current_user: dict = Depends(get_current_user),
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Upload or replace a product image."""
            from app.utils.checksum import verify_checksum

            scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)
            product = product_service.get_by_id(product_id, db, scope=scope)
            if not product or product.is_archived:
                raise entity_not_found("Product", product_id, locale=locale)
            contents = await file.read()
            if len(contents) > settings.MAX_PRODUCT_IMAGE_BYTES:
                raise envelope_exception(ErrorCode.PRODUCT_IMAGE_TOO_LARGE, status=400, locale=locale)
            verify_checksum(contents, client_checksum, checksum_algorithm)
            storage_path, url_path, thumb_storage_path, thumb_url_path, checksum = product_image_service.save_image(
                product_id,
                product.institution_id,
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
            if product.image_storage_path != storage_path and not product_image_service.is_placeholder(
                product.image_storage_path
            ):
                old_thumb = getattr(product, "image_thumbnail_storage_path", None)
                product_image_service.delete_image(product.image_storage_path, old_thumb)
            return updated_product

        @router.delete("/{product_id}/image", response_model=ProductResponseSchema)
        def delete_product_image(
            product_id: UUID,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Delete product image and revert to placeholder. Idempotent: returns 200 if already placeholder."""
            scope = EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)
            product = product_service.get_by_id(product_id, db, scope=scope)
            if not product or product.is_archived:
                raise entity_not_found("Product", product_id)
            if product_image_service.is_placeholder(product.image_storage_path):
                data = product.model_dump(mode="json")
                from app.utils.gcs import resolve_product_image_urls

                data = resolve_product_image_urls(data)
                return ProductResponseSchema(**data)
            product_image_service.delete_image(
                product.image_storage_path,
                getattr(product, "image_thumbnail_storage_path", None),
            )
            meta = product_image_service.placeholder_metadata()
            update_data = {
                "image_storage_path": meta["storage_path"],
                "image_thumbnail_storage_path": meta["thumbnail_storage_path"],
                "image_url": meta["image_url"],
                "image_thumbnail_url": meta["thumbnail_url"],
                "image_checksum": meta["checksum"],
                "modified_by": current_user["user_id"],
            }
            updated_product = product_service.update(product_id, update_data, db, scope=scope)
            if not updated_product:
                raise HTTPException(status_code=500, detail="Failed to revert product to placeholder")
            data = updated_product.model_dump(mode="json")
            from app.utils.gcs import resolve_product_image_urls

            data = resolve_product_image_urls(data)
            return ProductResponseSchema(**data)

    router = create_crud_routes(
        config=config,
        service=product_service,
        create_schema=ProductCreateSchema,
        update_schema=ProductUpdateSchema,
        response_schema=ProductResponseSchema,
        custom_routes_first=_product_custom_routes,
    )
    return router


def create_plan_routes() -> APIRouter:
    """Create routes for Plan entity with Internal-only access for modifications, Client/Internal access for viewing"""

    from app.schemas.consolidated_schemas import (
        PlanCreateSchema,
        PlanEnrichedResponseSchema,
        PlanResponseSchema,
        PlanUpdateSchema,
    )
    from app.services.crud_service import plan_service
    from app.services.entity_service import get_enriched_plan_by_id, get_enriched_plans
    from app.services.market_service import GLOBAL_MARKET_ID, reject_global_market_for_entity
    from app.utils.error_messages import entity_not_found
    from app.utils.filter_builder import build_filter_conditions
    from app.utils.log import log_error
    from app.utils.query_params import (
        currency_code_filter,
        market_filter,
        status_filter,
    )

    config = RouteConfig(
        prefix="/plans",
        tags=["Plans"],
        entity_name="plan",
        entity_name_plural="plans",
        paginatable=True,
    )

    # Create router without generic routes to avoid route conflicts
    router = APIRouter(prefix=config.prefix, tags=config.tags, dependencies=[Depends(oauth2_scheme)])

    # Define GET endpoints first with proper access control (Clients and Internal only, not Suppliers)
    @router.get("", response_model=list[PlanResponseSchema])
    def get_all_plans(
        current_user: dict = Depends(get_client_or_employee_user),  # Clients and Internal can view
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """Get all plans - Available to Clients and Internal only. Excludes plans for Global Marketplace. Non-archived only."""
        scope = None  # Plans are not institution-scoped

        def service_callable(connection: psycopg2.extensions.connection):
            plans = plan_service.get_all(connection, scope=scope, include_archived=False)
            return [p for p in plans if p.market_id != GLOBAL_MARKET_ID]

        return handle_get_all(service_callable, db, "plans")

    # Enriched routes MUST be before /{plan_id} so /enriched is not parsed as plan_id
    @router.get("/enriched", response_model=list[PlanEnrichedResponseSchema])
    def list_enriched_plans(  # noqa: PLR0913
        response: Response,
        market_id: UUID | None = market_filter(),
        status: str | None = status_filter(),
        currency_code: str | None = currency_code_filter(),
        price_from: float | None = Query(None, description="Filter plans with price >= this value"),
        price_to: float | None = Query(None, description="Filter plans with price <= this value"),
        credit_from: int | None = Query(None, description="Filter plans with credit >= this value"),
        credit_to: int | None = Query(None, description="Filter plans with credit <= this value"),
        country_code: list[str] | None = Query(None, description="Filter by country code(s) (multi-select)"),
        rollover: bool | None = Query(None, description="Filter by rollover flag"),
        pagination: PaginationParams | None = Depends(get_pagination_params),
        current_user: dict = Depends(get_client_or_employee_user),
        locale: str = Depends(get_resolved_locale),
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """List all plans with enriched data (currency_name and currency_code). Optional filters: market_id, status, currency_code, price_from/to, credit_from/to, country_code, rollover. Excludes plans for Global Marketplace. Non-archived only."""
        try:
            from app.i18n.locale_names import resolve_i18n_field, resolve_i18n_list_field

            filters = {
                "market_id": market_id,
                "status": status,
                "currency_code": currency_code,
                "price_from": price_from,
                "price_to": price_to,
                "credit_from": credit_from,
                "credit_to": credit_to,
                "country_code": country_code,
                "rollover": rollover,
            }
            try:
                additional_conditions = list(build_filter_conditions("plans", filters) or [])
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from None
            additional_conditions.append(("pl.market_id != %s::uuid", [str(GLOBAL_MARKET_ID)]))
            enriched_plans = get_enriched_plans(
                db,
                include_archived=False,
                additional_conditions=additional_conditions,
                page=pagination.page if pagination else None,
                page_size=pagination.page_size if pagination else None,
            )
            if locale != "en":
                for p in enriched_plans:
                    resolve_i18n_field(p, "name", locale)
                    resolve_i18n_field(p, "marketing_description", locale)
                    resolve_i18n_list_field(p, "features", locale)
                    resolve_i18n_field(p, "cta_label", locale)
            set_pagination_headers(response, enriched_plans)
            return enriched_plans
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error getting enriched plans: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve enriched plans") from None

    @router.get("/enriched/{plan_id}", response_model=PlanEnrichedResponseSchema)
    def get_enriched_plan_by_id_route(
        plan_id: UUID,
        current_user: dict = Depends(get_client_or_employee_user),
        locale: str = Depends(get_resolved_locale),
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """Get a single plan by ID with enriched data (currency_name and currency_code) - Available to Clients and Internal only. Non-archived only."""
        try:
            from app.i18n.locale_names import resolve_i18n_field, resolve_i18n_list_field

            enriched_plan = get_enriched_plan_by_id(plan_id, db, include_archived=False)
            if not enriched_plan:
                raise entity_not_found("Plan", plan_id, locale=locale)
            if locale != "en":
                resolve_i18n_field(enriched_plan, "name", locale)
                resolve_i18n_field(enriched_plan, "marketing_description", locale)
                resolve_i18n_list_field(enriched_plan, "features", locale)
                resolve_i18n_field(enriched_plan, "cta_label", locale)
            return enriched_plan
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error getting enriched plan {plan_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve enriched plan") from None

    @router.get("/{plan_id}", response_model=PlanResponseSchema)
    def get_plan(
        plan_id: UUID,
        current_user: dict = Depends(get_client_or_employee_user),  # Clients and Internal can view
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """Get a single plan by ID - Available to Clients and Internal only. Non-archived only."""
        scope = None  # Plans are not institution-scoped
        return handle_get_by_id(
            plan_service.get_by_id,
            plan_id,
            db,
            "plan",
            extra_kwargs={"scope": scope} if config.institution_scoped else None,
        )

    # Override POST/PUT/DELETE endpoints to be Internal-only
    @router.post("", response_model=PlanResponseSchema, status_code=status.HTTP_201_CREATED)
    def create_plan(
        create_data: PlanCreateSchema,
        current_user: dict = Depends(get_employee_user),  # Internal-only
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """Create a new plan - Internal-only"""
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
        current_user: dict = Depends(get_employee_user),  # Internal-only
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """Update an existing plan - Internal-only"""
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
        current_user: dict = Depends(get_employee_user),  # Internal-only
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """Delete a plan (soft delete) - Internal-only"""
        scope = None  # Plans are not institution-scoped

        def delete_callable(target_id: UUID, connection: psycopg2.extensions.connection):
            return plan_service.soft_delete(target_id, current_user["user_id"], connection, scope=scope)

        handle_delete(delete_callable, plan_id, db, "plan")
        return {"detail": "Plan deleted successfully"}

    return router


def create_restaurant_routes() -> APIRouter:
    """Create custom routes for Restaurant entity with automatic balance creation"""
    from app.routes.restaurant import router as restaurant_router

    return restaurant_router


def create_credit_currency_routes() -> APIRouter:
    """Create routes for CreditCurrency entity with Internal-only access"""

    from app.schemas.consolidated_schemas import (
        CreditCurrencyCreateSchema,
        CreditCurrencyEnrichedResponseSchema,
        CreditCurrencyResponseSchema,
        CreditCurrencyUpdateSchema,
    )
    from app.services.crud_service import credit_currency_service

    config = RouteConfig(
        prefix="/credit-currencies",
        tags=["Credit Currencies"],
        entity_name="credit currency",
        entity_name_plural="credit currencies",
        paginatable=True,
    )

    # Create router without generic routes to avoid route conflicts
    router = APIRouter(prefix=config.prefix, tags=config.tags, dependencies=[Depends(oauth2_scheme)])

    # Define all endpoints with Internal-only access (Suppliers use credit_currency data via plates, but can't access API directly)
    @router.get("", response_model=list[CreditCurrencyResponseSchema])
    def get_all_credit_currencies(
        current_user: dict = Depends(get_employee_user),  # Internal-only
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """Get all credit currencies - Internal-only. Non-archived only."""
        scope = None  # Credit currencies are not institution-scoped

        def service_callable(connection: psycopg2.extensions.connection):
            return credit_currency_service.get_all(connection, scope=scope, include_archived=False)

        return handle_get_all(service_callable, db, "credit currencies")

    # Enriched routes MUST be before /{currency_id} so /enriched is not parsed as currency_id
    @router.get("/enriched", response_model=list[CreditCurrencyEnrichedResponseSchema])
    def get_all_credit_currencies_enriched(
        current_user: dict = Depends(get_employee_user),
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """Get all credit currencies with enriched data (market name, country code). Internal-only. Non-archived only."""
        from app.services.entity_service import get_enriched_credit_currencies

        return get_enriched_credit_currencies(db, include_archived=False)

    @router.get("/enriched/{currency_id}", response_model=CreditCurrencyEnrichedResponseSchema)
    def get_credit_currency_enriched(
        currency_id: UUID,
        current_user: dict = Depends(get_employee_user),
        locale: str = Depends(get_resolved_locale),
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """Get a single credit currency by ID with enriched data. Internal-only. Non-archived only."""
        from app.services.entity_service import get_enriched_credit_currency_by_id

        result = get_enriched_credit_currency_by_id(currency_id, db, include_archived=False)
        if not result:
            raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Credit currency")
        return result

    @router.get("/{currency_id}", response_model=CreditCurrencyResponseSchema)
    def get_credit_currency(
        currency_id: UUID,
        current_user: dict = Depends(get_employee_user),  # Internal-only
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """Get a single credit currency by ID - Internal-only. Non-archived only."""
        scope = None  # Credit currencies are not institution-scoped
        return handle_get_by_id(
            credit_currency_service.get_by_id,
            currency_id,
            db,
            "credit currency",
            extra_kwargs={"scope": scope} if config.institution_scoped else None,
        )

    @router.post("", response_model=CreditCurrencyResponseSchema, status_code=status.HTTP_201_CREATED)
    def create_credit_currency(
        create_data: CreditCurrencyCreateSchema,
        current_user: dict = Depends(get_employee_user),  # Internal-only
        locale: str = Depends(get_resolved_locale),
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """Create a new credit currency - Internal-only. Backend assigns currency_code from supported list and fetches currency_conversion_usd from open.er-api.com."""
        from app.config.supported_currencies import get_currency_code_by_name
        from app.services.cron.currency_refresh import fetch_usd_rate_for_currency

        data = create_data.model_dump()
        data.pop("currency_conversion_usd", None)  # Backend fetches; do not accept client value
        # Resolve currency_code from currency_name; do not accept client-supplied currency_code
        currency_name = data.get("currency_name") or ""
        currency_code = get_currency_code_by_name(currency_name)
        if not currency_code:
            raise envelope_exception(ErrorCode.CREDIT_CURRENCY_NAME_NOT_SUPPORTED, status=400, locale=locale)
        data["currency_code"] = currency_code
        rate, _ = fetch_usd_rate_for_currency(currency_code)
        if rate is None:
            raise envelope_exception(
                ErrorCode.CREDIT_CURRENCY_RATE_UNAVAILABLE, status=400, locale=locale, currency_code=currency_code
            )
        data["currency_conversion_usd"] = rate
        data["modified_by"] = current_user["user_id"]
        scope = None  # Credit currencies are not institution-scoped

        def create_callable(payload: dict, connection: psycopg2.extensions.connection):
            return credit_currency_service.create(payload, connection, scope=scope)

        return handle_create(create_callable, data, db, "credit currency")

    @router.put("/{currency_id}", response_model=CreditCurrencyResponseSchema)
    def update_credit_currency(
        currency_id: UUID,
        update_data: CreditCurrencyUpdateSchema,
        current_user: dict = Depends(get_employee_user),  # Internal-only
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """Update an existing credit currency - Internal-only"""
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
        current_user: dict = Depends(get_employee_user),  # Internal-only
        db: psycopg2.extensions.connection = Depends(get_db),
    ):
        """Delete a credit currency (soft delete) - Internal-only"""
        scope = None  # Credit currencies are not institution-scoped

        def delete_callable(target_id: UUID, connection: psycopg2.extensions.connection):
            return credit_currency_service.soft_delete(target_id, current_user["user_id"], connection, scope=scope)

        handle_delete(delete_callable, currency_id, db, "credit currency")
        return {"detail": "Credit currency deleted successfully"}

    return router


def create_qr_code_routes() -> APIRouter:
    """Create routes for QRCode entity"""
    from app.schemas.consolidated_schemas import QRCodeCreateSchema, QRCodeResponseSchema, QRCodeUpdateSchema
    from app.services.crud_service import qr_code_service

    config = RouteConfig(
        prefix="/qr-codes",
        tags=["QR Codes"],
        entity_name="QR code",
        entity_name_plural="QR codes",
        paginatable=True,
    )

    return create_crud_routes(
        config=config,
        service=qr_code_service,
        create_schema=QRCodeCreateSchema,
        update_schema=QRCodeUpdateSchema,
        response_schema=QRCodeResponseSchema,
    )


def create_subscription_routes() -> APIRouter:
    """Create routes for Subscription entity with enriched endpoints"""

    from app.schemas.consolidated_schemas import SubscriptionEnrichedResponseSchema
    from app.schemas.subscription import (
        RenewalPreferencesSchema,
        SubscriptionCreateSchema,
        SubscriptionHoldRequestSchema,
        SubscriptionResponseSchema,
        SubscriptionUpdateSchema,
    )
    from app.services.crud_service import subscription_service
    from app.services.entity_service import get_enriched_subscription_by_id, get_enriched_subscriptions
    from app.services.error_handling import handle_business_operation
    from app.services.subscription_action_service import put_subscription_on_hold, resume_subscription

    config = RouteConfig(
        prefix="/subscriptions",
        tags=["Subscriptions"],
        entity_name="subscription",
        entity_name_plural="subscriptions",
        paginatable=True,
    )

    def _subscription_custom_routes(router: APIRouter) -> None:
        # Enriched routes MUST be before /{subscription_id} so /enriched is not parsed as subscription_id
        @router.get("/enriched", response_model=list[SubscriptionEnrichedResponseSchema])
        def list_enriched_subscriptions(
            current_user: dict = Depends(get_current_user),
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """List subscriptions with enriched data. Internal: global. Customers: own. Suppliers: 403. Non-archived only."""
            role_type = current_user.get("role_type")
            if role_type == "supplier":
                raise envelope_exception(ErrorCode.SECURITY_FORBIDDEN, status=403, locale=locale)
            if role_type == "customer":
                user_id = current_user.get("user_id")
                if not user_id:
                    raise envelope_exception(ErrorCode.SECURITY_TOKEN_USER_ID_MISSING, status=401, locale=locale)

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
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Get subscription by ID with enriched data. Internal: global. Customers: own. Suppliers: 403. Non-archived only."""
            role_type = current_user.get("role_type")
            if role_type == "supplier":
                raise envelope_exception(ErrorCode.SECURITY_FORBIDDEN, status=403, locale=locale)
            if role_type == "customer":
                user_id = current_user.get("user_id")
                if not user_id:
                    raise envelope_exception(ErrorCode.SECURITY_TOKEN_USER_ID_MISSING, status=401, locale=locale)

                def _get_enriched_subscription():
                    sub = get_enriched_subscription_by_id(subscription_id, db, scope=None, include_archived=False)
                    if not sub:
                        raise envelope_exception(
                            ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Subscription"
                        )
                    if sub.user_id != user_id:
                        raise envelope_exception(
                            ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Subscription"
                        )
                    return sub
            else:

                def _get_enriched_subscription():
                    sub = get_enriched_subscription_by_id(subscription_id, db, scope=None, include_archived=False)
                    if not sub:
                        raise envelope_exception(
                            ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Subscription"
                        )
                    return sub

            return handle_business_operation(_get_enriched_subscription, "enriched subscription retrieval")

        @router.patch("/me/renewal-preferences", response_model=SubscriptionResponseSchema)
        def update_my_renewal_preferences(
            body: RenewalPreferencesSchema,
            current_user: dict = Depends(get_current_user),
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Update early renewal threshold for the current user's active subscription.
            Send an integer (>= 1) to set the threshold, or null to disable early renewal (period-end only)."""
            if current_user.get("role_type") != "customer":
                raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=403, locale=locale)
            user_id = current_user.get("user_id")
            if not user_id:
                raise envelope_exception(ErrorCode.SECURITY_TOKEN_USER_ID_MISSING, status=401, locale=locale)
            subscription = subscription_service.get_by_user(user_id, db)
            if not subscription:
                raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Subscription")
            update_data = {
                "early_renewal_threshold": body.early_renewal_threshold,
                "modified_by": user_id,
            }
            updated = subscription_service.update(subscription.subscription_id, update_data, db, scope=None)
            if not updated:
                raise HTTPException(status_code=500, detail="Failed to update renewal preferences")
            return updated

        @router.get("/benefit-plans")
        def get_benefit_plans(
            current_user: dict = Depends(get_current_user),
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Get available plans with employer benefit breakdown for benefit employees.
            Returns plans in the user's market with employer/employee split.
            Non-benefit users get 404."""
            from app.services.crud_service import institution_service
            from app.services.crud_service import plan_service as _plan_service
            from app.services.employer.billing_service import compute_employee_benefit
            from app.services.employer.program_service import resolve_effective_program
            from app.utils.db import db_read

            user_id = current_user.get("user_id")
            if not user_id:
                raise envelope_exception(ErrorCode.SECURITY_TOKEN_USER_ID_MISSING, status=401, locale=locale)

            institution_id = current_user.get("institution_id")
            if not institution_id:
                raise envelope_exception(ErrorCode.EMPLOYER_BENEFIT_PROGRAM_NOT_FOUND, status=404, locale=locale)

            inst = institution_service.get_by_id(institution_id, db, scope=None)
            if not inst:
                raise envelope_exception(ErrorCode.EMPLOYER_BENEFIT_PROGRAM_NOT_FOUND, status=404, locale=locale)
            inst_type = getattr(inst, "institution_type", None)
            inst_type_str = inst_type.value if hasattr(inst_type, "value") else str(inst_type)
            if inst_type_str != "employer":
                raise envelope_exception(ErrorCode.EMPLOYER_BENEFIT_PROGRAM_NOT_FOUND, status=404, locale=locale)

            # Get user's market and employer_entity_id
            user_row = db_read(
                "SELECT market_id, employer_entity_id FROM user_info WHERE user_id = %s::uuid",
                (str(user_id),),
                connection=db,
                fetch_one=True,
            )
            if not user_row or not user_row.get("market_id"):
                raise envelope_exception(ErrorCode.USER_MARKET_NOT_ASSIGNED, status=400, locale=locale)

            employer_entity_id = user_row.get("employer_entity_id")
            program = resolve_effective_program(institution_id, employer_entity_id, db)
            if not program or not program.is_active:
                raise envelope_exception(ErrorCode.EMPLOYER_BENEFIT_PROGRAM_NOT_FOUND, status=404, locale=locale)

            # Get plans in market
            plans = _plan_service.get_all_by_field(
                "market_id",
                user_row["market_id"],
                db,
                scope=None,
            )

            # Compute monthly cap usage
            already_used = 0.0
            benefit_cap = float(program.benefit_cap) if program.benefit_cap is not None else None
            if benefit_cap is not None and program.benefit_cap_period == "monthly":
                from datetime import datetime

                now = datetime.now(UTC)
                month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                usage = db_read(
                    "SELECT COALESCE(SUM(ebl.employee_benefit), 0) as total FROM employer_bill_line ebl JOIN employer_bill eb ON ebl.employer_bill_id = eb.employer_bill_id WHERE ebl.user_id = %s::uuid AND ebl.renewal_date >= %s",
                    (str(user_id), month_start),
                    connection=db,
                    fetch_one=True,
                )
                already_used = float(usage["total"]) if usage else 0.0

            remaining_cap = (benefit_cap - already_used) if benefit_cap is not None else None

            result = []
            for plan in plans:
                plan_price = float(getattr(plan, "price", 0))
                emp_benefit, emp_share = compute_employee_benefit(
                    plan_price,
                    program.benefit_rate,
                    benefit_cap,
                    program.benefit_cap_period,
                    already_used,
                )
                result.append(
                    {
                        "plan_id": plan.plan_id,
                        "plan_name": getattr(plan, "name", ""),
                        "plan_price": plan_price,
                        "plan_credit": int(getattr(plan, "credit", 0)),
                        "employer_covers": emp_benefit,
                        "employee_pays": emp_share,
                        "benefit_rate": program.benefit_rate,
                        "benefit_cap": program.benefit_cap,
                        "benefit_cap_period": program.benefit_cap_period,
                        "remaining_monthly_cap": round(remaining_cap, 2) if remaining_cap is not None else None,
                    }
                )
            return result

        @router.get("", response_model=list[SubscriptionResponseSchema])
        def list_subscriptions_override(
            current_user: dict = Depends(get_current_user),
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """List subscriptions. Internal: global. Customers: own. Suppliers: 403. Non-archived only."""
            role_type = current_user.get("role_type")
            if role_type == "supplier":
                raise envelope_exception(ErrorCode.SECURITY_FORBIDDEN, status=403, locale=locale)
            if role_type == "customer":
                user_id = current_user.get("user_id")
                if not user_id:
                    raise envelope_exception(ErrorCode.SECURITY_TOKEN_USER_ID_MISSING, status=401, locale=locale)

                def _get_subscriptions():
                    return subscription_service.get_all_by_field("user_id", user_id, db, scope=None)
            else:

                def _get_subscriptions():
                    return subscription_service.get_all(db, scope=None, include_archived=False)

            return handle_business_operation(_get_subscriptions, "subscription list retrieval")

        @router.get("/{subscription_id}", response_model=SubscriptionResponseSchema)
        def get_subscription_override(
            subscription_id: UUID,
            current_user: dict = Depends(get_current_user),
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Get a single subscription by ID. Internal: global. Customers: own only. Suppliers: 403."""
            role_type = current_user.get("role_type")
            if role_type == "supplier":
                raise envelope_exception(ErrorCode.SECURITY_FORBIDDEN, status=403, locale=locale)
            if role_type == "customer":
                user_id = current_user.get("user_id")
                if not user_id:
                    raise envelope_exception(ErrorCode.SECURITY_TOKEN_USER_ID_MISSING, status=401, locale=locale)

                def _get_subscription():
                    subscription = subscription_service.get_by_id(subscription_id, db, scope=None)
                    if not subscription:
                        raise envelope_exception(
                            ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Subscription"
                        )
                    if subscription.user_id != user_id:
                        raise envelope_exception(
                            ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Subscription"
                        )
                    return subscription
            else:

                def _get_subscription():
                    subscription = subscription_service.get_by_id(subscription_id, db, scope=None)
                    if not subscription:
                        raise envelope_exception(
                            ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Subscription"
                        )
                    return subscription

            return handle_business_operation(_get_subscription, "subscription retrieval")

        @router.post("/{subscription_id}/hold", response_model=SubscriptionResponseSchema)
        def hold_subscription_route(
            subscription_id: UUID,
            body: SubscriptionHoldRequestSchema,
            current_user: dict = Depends(get_current_user),
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Put a subscription on hold. Only the owning customer. Hold duration max 3 months."""
            if current_user.get("role_type") != "customer":
                raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=403, locale=locale)
            user_id = current_user.get("user_id")
            if not user_id:
                raise envelope_exception(ErrorCode.SECURITY_TOKEN_USER_ID_MISSING, status=401, locale=locale)
            return put_subscription_on_hold(subscription_id, user_id, body.hold_start_date, body.hold_end_date, db)

        @router.post("/{subscription_id}/resume", response_model=SubscriptionResponseSchema)
        def resume_subscription_route(
            subscription_id: UUID,
            current_user: dict = Depends(get_current_user),
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Resume a subscription from hold. Only the owning customer."""
            if current_user.get("role_type") != "customer":
                raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=403, locale=locale)
            user_id = current_user.get("user_id")
            if not user_id:
                raise envelope_exception(ErrorCode.SECURITY_TOKEN_USER_ID_MISSING, status=401, locale=locale)
            return resume_subscription(subscription_id, user_id, db)

    router = create_crud_routes(
        config=config,
        service=subscription_service,
        create_schema=SubscriptionCreateSchema,
        update_schema=SubscriptionUpdateSchema,
        response_schema=SubscriptionResponseSchema,
        requires_user_context=True,
        custom_routes_first=_subscription_custom_routes,
    )
    return router


def create_institution_routes() -> APIRouter:
    """Create routes for Institution entity with POST/PUT/DELETE restricted to Internal Admin and Super Admin only.
    GET endpoints scoped: Suppliers, Customers, and Internal Management see only their institution."""
    from app.auth.dependencies import get_admin_user
    from app.schemas.consolidated_schemas import (
        InstitutionCreateSchema,
        InstitutionResponseSchema,
        InstitutionUpdateSchema,
    )
    from app.services.crud_service import institution_service, supplier_terms_service
    from app.services.entity_service import (
        attach_institution_market_ids,
        attach_institution_market_ids_bulk,
    )
    from app.services.error_handling import (
        handle_delete,
        handle_get_all,
        handle_get_by_id,
        handle_update,
    )
    from app.utils.log import log_error, log_info

    config = RouteConfig(
        prefix="/institutions",
        tags=["Institutions"],
        entity_name="institution",
        entity_name_plural="institutions",
        institution_scoped=True,  # Suppliers/Customers/Internal Management: own institution only
        paginatable=True,
    )

    def _institution_scope(current_user: dict):
        role_type = current_user.get("role_type")
        role_name = current_user.get("role_name")
        if role_type == "internal" and role_name in ("admin", "super_admin"):
            return None  # Global access
        return get_institution_scope(current_user)

    def _institution_custom_routes(router: APIRouter) -> None:
        """Custom institution routes — registered first so they take precedence over generic CRUD."""

        @router.get("", response_model=list[InstitutionResponseSchema])
        def get_all_institutions(
            current_user: dict = Depends(get_current_user), db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """List institutions. Suppliers, Customers, Internal Management: own institution only. Admin/Super Admin: all. Non-archived only."""
            scope = _institution_scope(current_user)

            def service_callable(connection: psycopg2.extensions.connection):
                return institution_service.get_all(connection, scope=scope, include_archived=False)

            institutions = handle_get_all(service_callable, db, "institutions")
            if not institutions:
                return institutions
            enriched = attach_institution_market_ids_bulk(institutions, db)
            return [InstitutionResponseSchema(**d) for d in enriched]

        @router.get("/{entity_id}", response_model=InstitutionResponseSchema)
        def get_institution(
            entity_id: UUID,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Get institution by ID. Suppliers, Customers, Internal Management: own institution only. Admin/Super Admin: any. Non-archived only."""
            scope = _institution_scope(current_user)
            institution = handle_get_by_id(
                institution_service.get_by_id,
                entity_id,
                db,
                "institution",
                extra_kwargs={"scope": scope} if scope else None,
            )
            if institution is None:
                return institution
            return InstitutionResponseSchema(**attach_institution_market_ids(institution, db))

        @router.put("/{entity_id}", response_model=InstitutionResponseSchema)
        def update_institution(
            entity_id: UUID,
            update_data: InstitutionUpdateSchema,
            current_user: dict = Depends(get_current_user),
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Update institution. Admin/Super Admin only."""
            scope = _institution_scope(current_user)
            data = update_data.model_dump(exclude_unset=True)
            if "modified_by" not in data:
                data["modified_by"] = current_user["user_id"]

            if current_user.get("role_type") != "internal" or current_user.get("role_name") not in (
                "admin",
                "super_admin",
            ):
                raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=403, locale=locale)

            existing = institution_service.get_by_id(entity_id, db, scope=scope)
            inst_type = getattr(existing, "institution_type", None) if existing else None
            inst_type_str = (inst_type.value if hasattr(inst_type, "value") else str(inst_type)) if inst_type else ""
            # Effective type after update: new value if provided, else existing
            new_type = data.get("institution_type")
            effective_type_str = (
                (new_type.value if hasattr(new_type, "value") else str(new_type))
                if new_type is not None
                else inst_type_str
            )
            if effective_type_str in ("internal", "customer") and current_user.get("role_name") != "super_admin":
                raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=403, locale=locale)
            # Extract market_ids for junction table handling
            market_ids = data.pop("market_ids", None)
            data.pop("market_id", None)

            if market_ids is not None:
                # Update institution_market junction: delete old rows, insert new ones
                def update_callable(target_id: UUID, payload: dict, connection: psycopg2.extensions.connection):
                    result = institution_service.update(target_id, payload, connection, scope=scope, commit=False)
                    cursor = connection.cursor()
                    cursor.execute(
                        "DELETE FROM core.institution_market WHERE institution_id = %s",
                        (str(target_id),),
                    )
                    for idx, mid in enumerate(market_ids):
                        cursor.execute(
                            "INSERT INTO core.institution_market (institution_id, market_id, is_primary) VALUES (%s, %s, %s)",
                            (str(target_id), str(mid), idx == 0),
                        )
                    connection.commit()
                    return result
            else:

                def update_callable(target_id: UUID, payload: dict, connection: psycopg2.extensions.connection):
                    return institution_service.update(target_id, payload, connection, scope=scope)

            updated = handle_update(update_callable, entity_id, data, db, "institution")
            if updated is None:
                return updated
            return InstitutionResponseSchema(**attach_institution_market_ids(updated, db))

        @router.delete("/{entity_id}", response_model=dict)
        def delete_institution(
            entity_id: UUID,
            current_user: dict = Depends(get_admin_user),
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Delete institution (soft delete) - Internal Admin and Super Admin only.
            System institutions (Vianda Enterprises, Vianda Customers) cannot be archived."""
            from app.config.restricted_institutions import get_restricted_institution_ids

            uid = entity_id if isinstance(entity_id, UUID) else UUID(str(entity_id))
            if uid in get_restricted_institution_ids():
                raise envelope_exception(ErrorCode.INSTITUTION_SYSTEM_PROTECTED, status=400, locale=locale)
            scope = _institution_scope(current_user)

            def delete_callable(target_id: UUID, connection: psycopg2.extensions.connection):
                return institution_service.soft_delete(target_id, current_user["user_id"], connection, scope=scope)

            handle_delete(delete_callable, entity_id, db, "institution")
            return {"detail": "Institution deleted successfully"}

        @router.post("", response_model=InstitutionResponseSchema, status_code=status.HTTP_201_CREATED)
        def create_institution(
            create_data: InstitutionCreateSchema,
            current_user: dict = Depends(get_admin_user),
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Create a new institution - Internal Admin and Super Admin only.
            Supports composite creation: embed supplier_terms for atomic institution + terms creation."""
            data = create_data.model_dump(exclude_none=True)
            supplier_terms_data = data.pop("supplier_terms", None)
            market_ids = data.pop("market_ids", [])
            data.pop("market_id", None)
            inst_type = data.get("institution_type")
            inst_str = inst_type.value if hasattr(inst_type, "value") else str(inst_type) if inst_type else "supplier"
            if inst_str in ("internal", "customer") and current_user.get("role_name") != "super_admin":
                raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=403, locale=locale)
            if supplier_terms_data is not None and inst_str != "supplier":
                raise envelope_exception(ErrorCode.INSTITUTION_SUPPLIER_TERMS_INVALID, status=422, locale=locale)
            # Treat empty supplier_terms (all defaults) as absent
            if supplier_terms_data is not None and all(
                v is None or v == field.default
                for v, field in zip(
                    supplier_terms_data.values(),
                    create_data.supplier_terms.__class__.model_fields.values(),
                    strict=False,
                )
            ):
                supplier_terms_data = None

            data["modified_by"] = current_user["user_id"]
            is_supplier = inst_str == "supplier"

            try:
                # Always defer commit — junction rows and optional supplier_terms are part of the same transaction
                institution = institution_service.create(data, db, scope=None, commit=False)
                if not institution:
                    raise HTTPException(status_code=500, detail="Failed to create institution")

                # Insert institution_market junction rows
                if market_ids:
                    cursor = db.cursor()
                    for idx, mid in enumerate(market_ids):
                        cursor.execute(
                            "INSERT INTO core.institution_market (institution_id, market_id, is_primary) VALUES (%s, %s, %s)",
                            (str(institution.institution_id), str(mid), idx == 0),
                        )

                if is_supplier:
                    terms_payload = {
                        **(supplier_terms_data or {}),
                        "institution_id": str(institution.institution_id),
                        "modified_by": current_user["user_id"],
                    }
                    terms = supplier_terms_service.create(terms_payload, db, commit=False)
                    if not terms:
                        db.rollback()
                        raise HTTPException(status_code=500, detail="Failed to create supplier terms")
                    log_info(f"Created institution {institution.institution_id} with supplier terms")

                db.commit()

                return InstitutionResponseSchema(**attach_institution_market_ids(institution, db))
            except HTTPException:
                raise
            except Exception as e:
                db.rollback()
                log_error(f"Error creating institution: {e}")
                raise HTTPException(status_code=500, detail="Error creating institution") from None

    router = create_crud_routes(
        config=config,
        service=institution_service,
        create_schema=InstitutionCreateSchema,
        update_schema=InstitutionUpdateSchema,
        response_schema=InstitutionResponseSchema,
        custom_routes_first=_institution_custom_routes,
    )
    return router


def create_payment_method_routes() -> APIRouter:
    """Create routes for PaymentMethod entity with enriched endpoints"""

    from app.auth.dependencies import get_employee_or_customer_user
    from app.schemas.payment_method import (
        PaymentMethodCreateSchema,
        PaymentMethodEnrichedResponseSchema,
        PaymentMethodResponseSchema,
        PaymentMethodUpdateSchema,
    )
    from app.security.scoping import EmployeeCustomerAccessControl
    from app.services.crud_service import payment_method_service
    from app.services.entity_service import get_enriched_payment_method_by_id
    from app.services.entity_service import get_enriched_payment_methods as fetch_enriched_payment_methods
    from app.services.error_handling import handle_business_operation

    config = RouteConfig(
        prefix="/payment-methods",
        tags=["Payment Methods"],
        entity_name="payment method",
        entity_name_plural="payment methods",
        paginatable=True,
    )

    def _payment_method_custom_routes(router: APIRouter) -> None:
        from app.services.payment_method_service import create_payment_method_with_address
        from app.utils.db import db_read
        from app.utils.log import log_info

        @router.post("", response_model=PaymentMethodResponseSchema, status_code=status.HTTP_201_CREATED)
        def create_payment_method(
            create_data: PaymentMethodCreateSchema,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db),
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
                    log_info(
                        f"User {current_user['user_id']} already has {existing_count} payment method(s), is_default={data.get('is_default', False)}"
                    )
                return create_payment_method_with_address(
                    payment_method_data=data,
                    address_id=address_id,
                    address_data=address_data,
                    current_user=current_user,
                    db=db,
                    scope=None,
                )

            return handle_business_operation(
                _create_payment_method, "payment method creation", "Payment method created successfully"
            )

        @router.get("/enriched", response_model=list[PaymentMethodEnrichedResponseSchema])
        def list_enriched_payment_methods(
            current_user: dict = Depends(get_employee_or_customer_user),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """List payment methods with enriched data. Internal: global. Customers: own. Suppliers: 403. Non-archived only."""
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
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Get payment method by ID with enriched data. Non-archived only."""

            def _get():
                pm = get_enriched_payment_method_by_id(payment_method_id, db, scope=None, include_archived=False)
                if not pm:
                    raise envelope_exception(
                        ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Payment method"
                    )
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
        custom_routes_first=_payment_method_custom_routes,
    )
    return router


def create_plate_routes() -> APIRouter:
    """Create routes for Plate entity"""

    from app.schemas.consolidated_schemas import (
        PlateCreateSchema,
        PlateEnrichedResponseSchema,
        PlateResponseSchema,
        PlateUpdateSchema,
    )
    from app.services.crud_service import plate_service
    from app.services.entity_service import get_enriched_plate_by_id, get_enriched_plates
    from app.services.error_handling import handle_get_all, handle_get_by_id
    from app.utils.error_messages import entity_not_found
    from app.utils.filter_builder import build_filter_conditions
    from app.utils.log import log_error

    config = RouteConfig(
        prefix="/plates",
        tags=["Plates"],
        entity_name="plate",
        entity_name_plural="plates",
        institution_scoped=True,
        entity_type=ENTITY_PLATE,
        paginatable=True,
    )

    def _plate_custom_routes(router: APIRouter) -> None:
        @router.get("", response_model=list[PlateResponseSchema])
        def get_all_plates(
            current_user: dict = Depends(get_current_user), db: psycopg2.extensions.connection = Depends(get_db)
        ):
            """Get all plates - Customers: all. Internal/Suppliers: institution-scoped. Non-archived only."""
            if current_user.get("role_type") == "customer":
                scope = None
            else:
                scope = EntityScopingService.get_scope_for_entity(ENTITY_PLATE, current_user)

            def service_callable(connection: psycopg2.extensions.connection):
                return plate_service.get_all(connection, scope=scope, include_archived=False)

            return handle_get_all(service_callable, db, "plates")

        # Enriched routes MUST be before /{plate_id} so /enriched is not parsed as plate_id
        @router.get("/enriched", response_model=list[PlateEnrichedResponseSchema])
        def list_enriched_plates(  # noqa: PLR0913
            response: Response,
            status: str | None = Query(None, description="Filter by plate status (e.g. active, inactive)"),
            market_id: UUID | None = Query(None, description="Filter by market ID"),
            restaurant_id: UUID | None = Query(None, description="Filter by restaurant ID"),
            plate_date_from: str | None = Query(
                None, description="Filter plates created on or after this date (YYYY-MM-DD)"
            ),
            plate_date_to: str | None = Query(
                None, description="Filter plates created on or before this date (YYYY-MM-DD)"
            ),
            cuisine_id: list[UUID] | None = Query(None, description="Filter by cuisine ID(s) (multi-select)"),
            dietary: list[str] | None = Query(
                None, description="Filter by dietary flag(s) (multi-select, e.g. vegan, vegetarian)"
            ),
            price_from: int | None = Query(None, description="Filter plates with price >= this value"),
            price_to: int | None = Query(None, description="Filter plates with price <= this value"),
            credit_from: int | None = Query(None, description="Filter plates with credit >= this value"),
            credit_to: int | None = Query(None, description="Filter plates with credit <= this value"),
            pagination: PaginationParams | None = Depends(get_pagination_params),
            current_user: dict = Depends(get_current_user),
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """List plates with enriched data. Optional filters: status, market_id, restaurant_id, plate_date_from/to, cuisine_id, dietary, price_from/to, credit_from/to. Customers: all. Internal/Suppliers: institution-scoped. Non-archived only."""
            try:
                from app.i18n.locale_names import resolve_cuisine_name

                if current_user.get("role_type") == "customer":
                    scope = None
                else:
                    scope = EntityScopingService.get_scope_for_entity(ENTITY_PLATE, current_user)
                try:
                    filter_conditions = list(
                        build_filter_conditions(
                            "plates",
                            {
                                "status": status,
                                "market_id": market_id,
                                "restaurant_id": restaurant_id,
                                "plate_date_from": plate_date_from,
                                "plate_date_to": plate_date_to,
                                "cuisine_id": [str(c) for c in cuisine_id] if cuisine_id else None,
                                "price_from": price_from,
                                "price_to": price_to,
                                "credit_from": credit_from,
                                "credit_to": credit_to,
                            },
                        )
                        or []
                    )
                    # dietary uses array-overlap SQL because dietary is TEXT[] in PostgreSQL.
                    # filter_builder "in" op emits col = ANY(%s) which checks if the whole array
                    # equals one value -- NOT element containment. Use && (array overlap) instead.
                    if dietary:
                        filter_conditions.append(("pr.dietary && %s::text[]", [dietary]))
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from None
                plates = get_enriched_plates(
                    db,
                    scope=scope,
                    include_archived=False,
                    additional_conditions=filter_conditions,
                    page=pagination.page if pagination else None,
                    page_size=pagination.page_size if pagination else None,
                )
                if locale != "en":
                    from app.i18n.locale_names import resolve_i18n_field, resolve_i18n_field_aliased

                    for p in plates:
                        resolve_cuisine_name(p, locale)
                        resolve_i18n_field_aliased(p, "product_name", "product_name_i18n", locale)
                        resolve_i18n_field(p, "ingredients", locale)
                        resolve_i18n_field(p, "description", locale)
                set_pagination_headers(response, plates)
                return plates
            except HTTPException:
                raise
            except Exception as e:
                log_error(f"Error getting enriched plates: {e}")
                raise HTTPException(status_code=500, detail="Failed to retrieve enriched plates") from None

        @router.get("/enriched/{plate_id}", response_model=PlateEnrichedResponseSchema)
        def get_enriched_plate_by_id_route(
            plate_id: UUID,
            kitchen_day: str | None = Query(
                None,
                description="When provided with user having employer, includes has_coworker_offer, has_coworker_request",
            ),
            current_user: dict = Depends(get_current_user),
            locale: str = Depends(get_resolved_locale),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Get plate by ID with enriched data. Non-archived only."""
            try:
                if current_user.get("role_type") == "customer":
                    scope = None
                else:
                    scope = EntityScopingService.get_scope_for_entity(ENTITY_PLATE, current_user)
                employer_entity_id = None
                employer_address_id = None
                user_id = None
                if kitchen_day and current_user.get("user_id"):
                    from app.utils.db import db_read

                    uid_raw = current_user["user_id"]
                    try:
                        user_id = uid_raw if isinstance(uid_raw, UUID) else UUID(uid_raw)
                    except (ValueError, TypeError):
                        user_id = None
                    user_row = db_read(
                        "SELECT employer_entity_id, employer_address_id FROM user_info WHERE user_id = %s",
                        (str(uid_raw),),
                        connection=db,
                        fetch_one=True,
                    )
                    if user_row and user_row.get("employer_entity_id"):
                        employer_entity_id = user_row["employer_entity_id"]
                        employer_address_id = user_row.get("employer_address_id")
                enriched_plate = get_enriched_plate_by_id(
                    plate_id,
                    db,
                    scope=scope,
                    include_archived=False,
                    kitchen_day=kitchen_day,
                    employer_entity_id=employer_entity_id,
                    employer_address_id=employer_address_id,
                    user_id=user_id,
                )
                if not enriched_plate:
                    raise entity_not_found("Plate", plate_id, locale=locale)
                if locale != "en":
                    from app.i18n.locale_names import (
                        resolve_cuisine_name,
                        resolve_i18n_field,
                        resolve_i18n_field_aliased,
                    )

                    resolve_cuisine_name(enriched_plate, locale)
                    resolve_i18n_field_aliased(enriched_plate, "product_name", "product_name_i18n", locale)
                    resolve_i18n_field(enriched_plate, "ingredients", locale)
                    resolve_i18n_field(enriched_plate, "description", locale)
                return enriched_plate
            except HTTPException:
                raise
            except Exception as e:
                log_error(f"Error getting enriched plate {plate_id}: {e}")
                raise HTTPException(status_code=500, detail="Failed to retrieve enriched plate") from None

        @router.get("/{plate_id}", response_model=PlateResponseSchema)
        def get_plate(
            plate_id: UUID,
            current_user: dict = Depends(get_current_user),
            db: psycopg2.extensions.connection = Depends(get_db),
        ):
            """Get plate by ID - Customers: any. Internal/Suppliers: institution-scoped. Non-archived only."""
            if current_user.get("role_type") == "customer":
                scope = None
            else:
                scope = EntityScopingService.get_scope_for_entity(ENTITY_PLATE, current_user)
            return handle_get_by_id(
                plate_service.get_by_id, plate_id, db, "plate", extra_kwargs={"scope": scope} if scope else None
            )

    router = create_crud_routes(
        config=config,
        service=plate_service,
        create_schema=PlateCreateSchema,
        update_schema=PlateUpdateSchema,
        response_schema=PlateResponseSchema,
        custom_routes_first=_plate_custom_routes,
    )
    return router


def create_geolocation_routes() -> APIRouter:
    """Create routes for Geolocation entity"""
    from app.schemas.geolocation import GeolocationCreateSchema, GeolocationResponseSchema, GeolocationUpdateSchema
    from app.services.crud_service import geolocation_service

    config = RouteConfig(
        prefix="/geolocations",
        tags=["Geolocations"],
        entity_name="geolocation",
        entity_name_plural="geolocations",
        paginatable=True,
    )

    return create_crud_routes(
        config=config,
        service=geolocation_service,
        create_schema=GeolocationCreateSchema,
        update_schema=GeolocationUpdateSchema,
        response_schema=GeolocationResponseSchema,
    )


def create_institution_entity_routes() -> APIRouter:
    """Create routes for InstitutionEntity entity. Supplier Admin and Internal Admin/Super Admin can access (GET, POST, PUT, DELETE).
    currency_metadata_id is derived from address.country_code -> market (Option A); client does not send it.
    Note: Enriched endpoints (/enriched, /enriched/{entity_id}) are in app/routes/institution_entity.py,
    registered before this router so /enriched matches before /{entity_id}."""
    from app.auth.dependencies import require_supplier_admin_or_employee_admin
    from app.schemas.consolidated_schemas import (
        InstitutionEntityCreateSchema,
        InstitutionEntityResponseSchema,
        InstitutionEntityUpdateSchema,
    )
    from app.services.crud_service import institution_entity_service
    from app.services.entity_service import derive_currency_metadata_id_for_address

    def _before_create(data: dict, connection: psycopg2.extensions.connection) -> dict:
        from app.config.tax_id_config import validate_tax_id_for_country
        from app.utils.db import db_read as _db_read

        data["currency_metadata_id"] = derive_currency_metadata_id_for_address(data["address_id"], connection)
        # Validate that the entity's address country maps to a market assigned to the institution
        market_check = _db_read(
            "SELECT a.country_code FROM core.institution_market im "
            "JOIN core.market_info m ON im.market_id = m.market_id "
            "JOIN core.address_info a ON a.country_code = m.country_code "
            "WHERE im.institution_id = %s AND a.address_id = %s",
            (str(data["institution_id"]), str(data["address_id"])),
            connection=connection,
            fetch_one=True,
        )
        if not market_check:
            raise envelope_exception(ErrorCode.INSTITUTION_ENTITY_MARKET_MISMATCH, status=400, locale="en")
        # Validate tax_id format for the entity's country
        if data.get("tax_id"):
            validate_tax_id_for_country(data["tax_id"], market_check["country_code"])
        return data

    def _before_update(data: dict, connection: psycopg2.extensions.connection, entity_id: UUID) -> dict:
        from app.config.tax_id_config import validate_tax_id_for_country
        from app.utils.db import db_read as _db_read

        if "address_id" in data:
            data["currency_metadata_id"] = derive_currency_metadata_id_for_address(data["address_id"], connection)
        # Validate tax_id format if being updated
        if data.get("tax_id"):
            addr_row = _db_read(
                "SELECT a.country_code FROM ops.institution_entity_info ie "
                "JOIN core.address_info a ON a.address_id = COALESCE(%s, ie.address_id) "
                "WHERE ie.institution_entity_id = %s",
                (data.get("address_id") and str(data["address_id"]), str(entity_id)),
                connection=connection,
                fetch_one=True,
            )
            if addr_row:
                validate_tax_id_for_country(data["tax_id"], addr_row["country_code"])
        return data

    from app.services.entity_service import validate_entity_can_be_archived

    config = RouteConfig(
        prefix="/institution-entities",
        tags=["Institution Entities"],
        entity_name="institution entity",
        entity_name_plural="institution entities",
        institution_scoped=True,
        entity_type=ENTITY_INSTITUTION_ENTITY,
        immutable_update_fields=["institution_id"],
        paginatable=True,
        pre_archive_validator=validate_entity_can_be_archived,
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
    from app.schemas.consolidated_schemas import PlateSelectionCreateSchema, PlateSelectionResponseSchema
    from app.services.crud_service import plate_selection_service

    config = RouteConfig(
        prefix="/plate-selections",
        tags=["Plate Selections"],
        entity_name="plate selection",
        entity_name_plural="plate selections",
        paginatable=True,
    )

    return create_crud_routes(
        config=config,
        service=plate_selection_service,
        create_schema=PlateSelectionCreateSchema,
        update_schema=PlateSelectionCreateSchema,  # Using same schema for update
        response_schema=PlateSelectionResponseSchema,
        requires_user_context=True,  # ← KEY: This entity requires user_id
    )


# =============================================================================
# IMMUTABLE ENTITY ROUTE FACTORY FUNCTIONS
# =============================================================================
# institution_payment_attempt and client_payment_attempt routes removed (payment attempts deprecated)
