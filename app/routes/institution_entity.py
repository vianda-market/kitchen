from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from uuid import UUID
from app.services.entity_service import (
    get_enriched_institution_entities, get_enriched_institution_entity_by_id
)
from app.services.crud_service import institution_service
from app.services.market_service import is_global_market
from app.services.error_handling import handle_business_operation
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.utils.query_params import institution_filter
from app.utils.error_messages import institution_entity_not_found
from app.schemas.consolidated_schemas import InstitutionEntityEnrichedResponseSchema
from app.security.entity_scoping import EntityScopingService, ENTITY_INSTITUTION_ENTITY
from app.security.scoping import resolve_institution_filter
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
@router.get("/enriched", response_model=List[InstitutionEntityEnrichedResponseSchema])
def list_enriched_institution_entities(
    institution_id: Optional[UUID] = institution_filter(),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all institution entities with enriched data (institution_name, address_country, address_province, address_city). Optional institution_id filters by institution (B2B Employee dropdown scoping). When institution has a local market_id (v1), only entities in that market are returned. Non-archived only."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)
    effective_institution_id = resolve_institution_filter(institution_id, scope)
    institution_market_id: Optional[UUID] = None
    if effective_institution_id is not None:
        inst = institution_service.get_by_id(effective_institution_id, db, scope=None)
        if inst and getattr(inst, "market_id", None) is not None and not is_global_market(inst.market_id):
            institution_market_id = inst.market_id

    def _get_enriched_entities():
        return get_enriched_institution_entities(
            db,
            scope=scope,
            include_archived=False,
            institution_id=effective_institution_id,
            institution_market_id=institution_market_id
        )

    return handle_business_operation(
        _get_enriched_entities,
        "enriched institution entity list retrieval"
    )

# GET /institution-entities/enriched/{entity_id} - Get a single institution entity with enriched data
@router.get("/enriched/{entity_id}", response_model=InstitutionEntityEnrichedResponseSchema)
def get_enriched_institution_entity_by_id_route(
    entity_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a single institution entity by ID with enriched data (institution_name, address_country, address_province, address_city). Non-archived only."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)

    def _get_enriched_entity():
        enriched_entity = get_enriched_institution_entity_by_id(entity_id, db, scope=scope, include_archived=False)
        if not enriched_entity:
            raise institution_entity_not_found(entity_id)
        return enriched_entity

    return handle_business_operation(
        _get_enriched_entity,
        "enriched institution entity retrieval"
    )

