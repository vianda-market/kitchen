from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from uuid import UUID
from app.services.entity_service import (
    get_enriched_institution_entities, get_enriched_institution_entity_by_id
)
from app.services.error_handling import handle_business_operation
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.utils.query_params import include_archived_query, include_archived_optional_query
from app.utils.error_messages import institution_entity_not_found
from app.schemas.consolidated_schemas import InstitutionEntityEnrichedResponseSchema
from app.security.entity_scoping import EntityScopingService, ENTITY_INSTITUTION_ENTITY
import psycopg2.extensions

router = APIRouter(
    prefix="/institution-entities",
    tags=["Institution Entities"],
    dependencies=[Depends(oauth2_scheme)]
)

# =============================================================================
# ENRICHED INSTITUTION ENTITY ENDPOINTS (with institution_name, address details)
# =============================================================================

# GET /institution-entities/enriched/ - List all institution entities with enriched data
@router.get("/enriched/", response_model=List[InstitutionEntityEnrichedResponseSchema])
def list_enriched_institution_entities(
    include_archived: Optional[bool] = include_archived_optional_query("institution entities"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all institution entities with enriched data (institution_name, address_country, address_province, address_city)"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)

    def _get_enriched_entities():
        return get_enriched_institution_entities(db, scope=scope, include_archived=include_archived or False)

    return handle_business_operation(
        _get_enriched_entities,
        "enriched institution entity list retrieval"
    )

# GET /institution-entities/enriched/{entity_id} - Get a single institution entity with enriched data
@router.get("/enriched/{entity_id}", response_model=InstitutionEntityEnrichedResponseSchema)
def get_enriched_institution_entity_by_id_route(
    entity_id: UUID,
    include_archived: bool = include_archived_query("institution entities"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a single institution entity by ID with enriched data (institution_name, address_country, address_province, address_city)"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)

    def _get_enriched_entity():
        enriched_entity = get_enriched_institution_entity_by_id(entity_id, db, scope=scope, include_archived=include_archived)
        if not enriched_entity:
            raise institution_entity_not_found(entity_id)
        return enriched_entity

    return handle_business_operation(
        _get_enriched_entity,
        "enriched institution entity retrieval"
    )

