from fastapi import APIRouter, HTTPException, Depends, Body, Response
from typing import Optional, List
from uuid import UUID
from app.services.entity_service import (
    get_enriched_institution_entities, get_enriched_institution_entity_by_id
)
from app.services.crud_service import institution_service, institution_entity_service
from app.services.market_service import is_global_market
from app.services.error_handling import handle_business_operation
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.utils.query_params import institution_filter
from app.utils.error_messages import institution_entity_not_found
from app.schemas.consolidated_schemas import (
    InstitutionEntityEnrichedResponseSchema,
    InstitutionBillPayoutResponseSchema,
    MarketPayoutAggregatorResponseSchema,
)
from app.security.entity_scoping import EntityScopingService, ENTITY_INSTITUTION_ENTITY
from app.security.scoping import resolve_institution_filter
from app.utils.pagination import PaginationParams, get_pagination_params, set_pagination_headers
from app.config.settings import settings
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
    response: Response,
    institution_id: Optional[UUID] = institution_filter(),
    pagination: Optional[PaginationParams] = Depends(get_pagination_params),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all institution entities with enriched data (institution_name, address_country, address_province, address_city). Optional institution_id filters by institution (B2B Internal dropdown scoping). When institution has a local market_id (v1), only entities in that market are returned. Non-archived only."""
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
            institution_market_id=institution_market_id,
            page=pagination.page if pagination else None,
            page_size=pagination.page_size if pagination else None,
        )

    result = handle_business_operation(
        _get_enriched_entities,
        "enriched institution entity list retrieval"
    )
    set_pagination_headers(response, result)
    return result

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


# =============================================================================
# STRIPE CONNECT ONBOARDING ENDPOINTS
# =============================================================================

def _get_connect_gateway():
    """Return the appropriate Connect gateway (live or mock) based on SUPPLIER_PAYOUT_PROVIDER."""
    if (settings.SUPPLIER_PAYOUT_PROVIDER or "mock").lower() == "stripe":
        from app.services.payment_provider.stripe import connect_gateway
        return connect_gateway
    from app.services.payment_provider.stripe import connect_mock
    return connect_mock


@router.get("/{entity_id}/payout-aggregator", response_model=MarketPayoutAggregatorResponseSchema)
def get_payout_aggregator(
    entity_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Return the payout aggregator configured for the entity's market.
    Frontend uses this to determine which onboarding UI to show:
    - aggregator='stripe' + is_active=true → render Stripe embedded onboarding
    - is_active=false → show 'coming soon' message
    Auth: Supplier Admin (own entity) or Internal.
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)
    entity = institution_entity_service.get_by_id(str(entity_id), db, scope=scope)
    if not entity:
        raise institution_entity_not_found(entity_id)

    institution_id = entity.institution_id
    with db.cursor() as cur:
        cur.execute(
            "SELECT market_id FROM core.institution_info WHERE institution_id = %s",
            (str(institution_id),),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Institution not found for entity")
    market_id = row[0]

    with db.cursor() as cur:
        cur.execute(
            "SELECT market_id, aggregator, is_active, require_invoice, max_unmatched_bill_days FROM billing.market_payout_aggregator WHERE market_id = %s",
            (str(market_id),),
        )
        agg_row = cur.fetchone()
    if not agg_row:
        raise HTTPException(status_code=404, detail="No payout aggregator configured for this market")

    return MarketPayoutAggregatorResponseSchema(
        market_id=agg_row[0],
        aggregator=agg_row[1],
        is_active=agg_row[2],
        require_invoice=agg_row[3],
        max_unmatched_bill_days=agg_row[4],
    )


@router.post("/{entity_id}/stripe-connect/account-session")
def create_stripe_connect_account_session(
    entity_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Create (or reuse) a Stripe Connect Express account for the entity, then create an
    AccountSession for embedded onboarding (Connect.js).
    Returns { client_secret, payout_provider_account_id }.
    client_secret expires in minutes — always regenerate, never cache.
    Auth: Supplier Admin (own entity) or Internal.
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)
    entity = institution_entity_service.get_by_id(str(entity_id), db, scope=scope)
    if not entity:
        raise institution_entity_not_found(entity_id)

    gw = _get_connect_gateway()

    connect_id = entity.payout_provider_account_id
    if not connect_id:
        connect_id = gw.create_connected_account(
            entity_id=entity_id,
            name=entity.name or "",
        )
        institution_entity_service.update(
            str(entity_id),
            {
                "payout_provider_account_id": connect_id,
                "payout_aggregator": "stripe",
                "modified_by": str(current_user["user_id"]),
            },
            db,
        )

    client_secret = gw.create_account_session(connect_id)

    return {
        "client_secret": client_secret,
        "payout_provider_account_id": connect_id,
    }


@router.post("/{entity_id}/stripe-connect/onboarding")
def initiate_stripe_connect_onboarding(
    entity_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Create a Stripe Connect Express account for a supplier entity (redirect-based flow).
    Idempotent: if payout_provider_account_id is already set, returns it without creating a new account.
    Auth: Supplier Admin (own entity) or Internal. Entity must belong to a Supplier institution.
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)
    entity = institution_entity_service.get_by_id(str(entity_id), db, scope=scope)
    if not entity:
        raise institution_entity_not_found(entity_id)

    existing_account_id = entity.payout_provider_account_id
    if existing_account_id:
        return {
            "institution_entity_id": str(entity_id),
            "payout_provider_account_id": existing_account_id,
        }

    gw = _get_connect_gateway()
    account_id = gw.create_connected_account(
        entity_id=entity_id,
        name=entity.name or "",
    )

    institution_entity_service.update(
        str(entity_id),
        {
            "payout_provider_account_id": account_id,
            "payout_aggregator": "stripe",
            "modified_by": str(current_user["user_id"]),
        },
        db,
    )

    return {
        "institution_entity_id": str(entity_id),
        "payout_provider_account_id": account_id,
    }


@router.get("/{entity_id}/stripe-connect/onboarding-link")
def get_stripe_connect_onboarding_link(
    entity_id: UUID,
    refresh_url: str,
    return_url: str,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Generate a Stripe Express onboarding link for the supplier entity.
    Requires payout_provider_account_id to be set (call POST /stripe-connect/onboarding first).
    Links expire in ~10 minutes; always regenerate on each onboarding attempt.
    Auth: Supplier Admin (own entity) or Internal.
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)
    entity = institution_entity_service.get_by_id(str(entity_id), db, scope=scope)
    if not entity:
        raise institution_entity_not_found(entity_id)

    connect_id = entity.payout_provider_account_id
    if not connect_id:
        raise HTTPException(
            status_code=400,
            detail="Entity has no payout provider account. Call POST /stripe-connect/onboarding first.",
        )

    gw = _get_connect_gateway()
    return gw.create_account_link(
        payout_provider_account_id=connect_id,
        refresh_url=refresh_url,
        return_url=return_url,
    )


@router.get("/{entity_id}/stripe-connect/status")
def get_stripe_connect_status(
    entity_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Retrieve Stripe Connect account status for the entity: charges_enabled, payouts_enabled, details_submitted.
    Auth: Supplier Admin (own entity) or Internal.
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)
    entity = institution_entity_service.get_by_id(str(entity_id), db, scope=scope)
    if not entity:
        raise institution_entity_not_found(entity_id)

    connect_id = entity.payout_provider_account_id
    if not connect_id:
        raise HTTPException(
            status_code=400,
            detail="Entity has no payout provider account. Call POST /stripe-connect/onboarding first.",
        )

    gw = _get_connect_gateway()
    return gw.get_account_status(connect_id)


@router.post("/{entity_id}/stripe-connect/payout", response_model=InstitutionBillPayoutResponseSchema)
def execute_stripe_connect_payout(
    entity_id: UUID,
    institution_bill_id: UUID = Body(..., embed=True),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Initiate a Stripe payout for an institution bill to the supplier entity's connected account.
    Bill must have resolution='Pending' and no active payout already in progress.
    Auth: Internal only (admins approve payouts; suppliers do not self-trigger).
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)
    entity = institution_entity_service.get_by_id(str(entity_id), db, scope=scope)
    if not entity:
        raise institution_entity_not_found(entity_id)

    gw = _get_connect_gateway()
    payout_row = gw.execute_supplier_payout(
        institution_bill_id=institution_bill_id,
        entity_id=entity_id,
        current_user_id=UUID(str(current_user["user_id"])),
        db=db,
    )
    return InstitutionBillPayoutResponseSchema(**payout_row)


@router.get("/{entity_id}/stripe-connect/payouts", response_model=List[InstitutionBillPayoutResponseSchema])
def list_entity_payouts(
    entity_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    List all payout attempts for an entity's bills, newest first.
    Auth: Internal only (admin visibility into payout history).
    """
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)
    entity = institution_entity_service.get_by_id(str(entity_id), db, scope=scope)
    if not entity:
        raise institution_entity_not_found(entity_id)

    with db.cursor() as cur:
        cur.execute(
            """
            SELECT bp.bill_payout_id, bp.institution_bill_id, bp.provider,
                   bp.provider_transfer_id, bp.amount, bp.currency_code,
                   bp.status, bp.created_at, bp.completed_at
            FROM billing.institution_bill_payout bp
            JOIN billing.institution_bill_info bi
                ON bp.institution_bill_id = bi.institution_bill_id
            WHERE bi.institution_entity_id = %s
            ORDER BY bp.created_at DESC
            """,
            (str(entity_id),),
        )
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
    return [InstitutionBillPayoutResponseSchema(**dict(zip(cols, row))) for row in rows]
