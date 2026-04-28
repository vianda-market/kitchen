from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Body, Depends, Response

from app.auth.dependencies import get_current_user, get_employee_user, oauth2_scheme
from app.config.settings import settings
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import (
    InstitutionBillPayoutResponseSchema,
    InstitutionEntityEnrichedResponseSchema,
    InstitutionEntityResponseSchema,
    InstitutionEntityUpsertByKeySchema,
    MarketPayoutAggregatorResponseSchema,
)
from app.security.entity_scoping import ENTITY_INSTITUTION_ENTITY, EntityScopingService
from app.security.scoping import resolve_institution_filter
from app.services.crud_service import (
    find_institution_entity_by_canonical_key,
    institution_entity_service,
)
from app.services.entity_service import get_enriched_institution_entities, get_enriched_institution_entity_by_id
from app.services.error_handling import handle_business_operation
from app.services.market_service import is_global_market
from app.utils.error_messages import institution_entity_not_found
from app.utils.pagination import PaginationParams, get_pagination_params, set_pagination_headers
from app.utils.query_params import institution_filter

router = APIRouter(prefix="/institution-entities", tags=["Institution Entities"], dependencies=[Depends(oauth2_scheme)])

# =============================================================================
# UPSERT BY CANONICAL KEY (seed/fixture endpoint)
# =============================================================================
# PUT /institution-entities/by-key — idempotent upsert (seed/fixture endpoint).
# MUST be registered before PUT /{entity_id} so the static segment "by-key"
# wins over the UUID path parameter (FastAPI evaluates in registration order).
# This router is included in application.py BEFORE the CRUD router that owns
# the generic PUT /{entity_id}, so ordering is guaranteed.


@router.put("/by-key", response_model=InstitutionEntityResponseSchema, status_code=200)
def upsert_institution_entity_by_key(
    upsert_data: InstitutionEntityUpsertByKeySchema,
    current_user: dict = Depends(get_employee_user),  # Internal-only
    db: psycopg2.extensions.connection = Depends(get_db),
) -> InstitutionEntityResponseSchema:
    """Idempotent upsert an institution entity by canonical_key.

    INTERNAL SEED/FIXTURE ENDPOINT — never use for supplier self-registration or
    ad-hoc entity creation (use POST /institution-entities instead).

    If an entity with this canonical_key already exists it is updated in-place;
    otherwise a new entity is inserted.  On INSERT the ``currency_metadata_id``
    is derived automatically from the address country code (same policy as
    POST /institution-entities) — do not include it in the request body.

    Immutable fields on UPDATE: ``institution_id`` is locked after insert and
    ignored on the update path (entities cannot move between institutions after
    creation).

    Auth: Internal only (get_employee_user dependency).  Returns 403 for
    Customer/Supplier roles.

    Returns HTTP 200 on both insert and update (unlike POST which returns 201).
    """
    from app.services.entity_service import derive_currency_metadata_id_for_address
    from app.utils.log import log_info

    def _upsert() -> InstitutionEntityResponseSchema:
        key = upsert_data.canonical_key
        existing = find_institution_entity_by_canonical_key(key, db)
        payload = upsert_data.model_dump()
        payload["modified_by"] = current_user["user_id"]

        if existing is not None:
            # UPDATE path — strip fields that must not change after creation.
            # institution_id is immutable; canonical_key is not in the update dict.
            update_payload = {k: v for k, v in payload.items() if k != "canonical_key"}
            update_payload.pop("institution_id", None)
            # Re-derive currency_metadata_id in case address changed.
            if "address_id" in update_payload:
                update_payload["currency_metadata_id"] = derive_currency_metadata_id_for_address(
                    update_payload["address_id"], db
                )

            result = institution_entity_service.update(existing.institution_entity_id, update_payload, db)
            if result is None:
                raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en")
            log_info(f"Upsert updated institution entity {existing.institution_entity_id} with canonical_key '{key}'")
            return InstitutionEntityResponseSchema.model_validate(result)

        # INSERT path — derive currency_metadata_id from address country (mirrors POST /institution-entities).
        payload["currency_metadata_id"] = derive_currency_metadata_id_for_address(payload["address_id"], db)

        # Validate that the entity's address country maps to a market assigned to the institution
        from app.utils.db import db_read as _db_read

        market_check = _db_read(
            "SELECT a.country_code FROM core.institution_market im "
            "JOIN core.market_info m ON im.market_id = m.market_id "
            "JOIN core.address_info a ON a.country_code = m.country_code "
            "WHERE im.institution_id = %s AND a.address_id = %s",
            (str(payload["institution_id"]), str(payload["address_id"])),
            connection=db,
            fetch_one=True,
        )
        if not market_check:
            raise envelope_exception(ErrorCode.INSTITUTION_ENTITY_MARKET_MISMATCH, status=400, locale="en")

        institution = institution_entity_service.create(payload, db, scope=None)
        if not institution:
            raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en")
        log_info(f"Upsert inserted institution entity {institution.institution_entity_id} with canonical_key '{key}'")
        return InstitutionEntityResponseSchema.model_validate(institution)

    return handle_business_operation(_upsert, "institution entity upsert by canonical key")


# =============================================================================
# ENRICHED INSTITUTION ENTITY ENDPOINTS (with institution_name, address details)
# =============================================================================


# GET /institution-entities/enriched/ - List all institution entities with enriched data
@router.get("/enriched", response_model=list[InstitutionEntityEnrichedResponseSchema])
def list_enriched_institution_entities(
    response: Response,
    institution_id: UUID | None = institution_filter(),
    pagination: PaginationParams | None = Depends(get_pagination_params),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List all institution entities with enriched data (institution_name, address_country, address_province, address_city). Optional institution_id filters by institution (B2B Internal dropdown scoping). When institution has a local market_id (v1), only entities in that market are returned. Non-archived only."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)
    effective_institution_id = resolve_institution_filter(institution_id, scope)
    institution_market_id: UUID | None = None
    if effective_institution_id is not None:
        from app.services.entity_service import get_institution_market_ids

        inst_markets = get_institution_market_ids(effective_institution_id, db)
        if inst_markets and len(inst_markets) == 1 and not is_global_market(inst_markets[0]):
            institution_market_id = inst_markets[0]

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

    result = handle_business_operation(_get_enriched_entities, "enriched institution entity list retrieval")
    set_pagination_headers(response, result)
    return result


# GET /institution-entities/enriched/{entity_id} - Get a single institution entity with enriched data
@router.get("/enriched/{entity_id}", response_model=InstitutionEntityEnrichedResponseSchema)
def get_enriched_institution_entity_by_id_route(
    entity_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get a single institution entity by ID with enriched data (institution_name, address_country, address_province, address_city). Non-archived only."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_ENTITY, current_user)

    def _get_enriched_entity():
        enriched_entity = get_enriched_institution_entity_by_id(entity_id, db, scope=scope, include_archived=False)
        if not enriched_entity:
            raise institution_entity_not_found(entity_id)
        return enriched_entity

    return handle_business_operation(_get_enriched_entity, "enriched institution entity retrieval")


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
            "SELECT market_id FROM core.institution_market WHERE institution_id = %s ORDER BY is_primary DESC LIMIT 1",
            (str(institution_id),),
        )
        row = cur.fetchone()
    if not row:
        raise envelope_exception(ErrorCode.INSTITUTION_ENTITY_NO_MARKETS, status=404, locale="en")
    market_id = row[0]

    from psycopg2.extras import RealDictCursor

    with db.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT market_id, aggregator, is_active, require_invoice,
                      max_unmatched_bill_days, kitchen_open_time, kitchen_close_time,
                      notes, is_archived, status,
                      created_date, modified_by, modified_date
               FROM billing.market_payout_aggregator
               WHERE market_id = %s AND is_archived = FALSE""",
            (str(market_id),),
        )
        agg_row = cur.fetchone()
    if not agg_row:
        raise envelope_exception(ErrorCode.INSTITUTION_ENTITY_NO_PAYOUT_AGGREGATOR, status=404, locale="en")

    # Convert time objects to HH:MM strings for schema serialization
    row = dict(agg_row)
    for tf in ("kitchen_open_time", "kitchen_close_time"):
        v = row.get(tf)
        if v is not None and hasattr(v, "strftime"):
            row[tf] = v.strftime("%H:%M")
    return MarketPayoutAggregatorResponseSchema(**row)


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
        raise envelope_exception(ErrorCode.INSTITUTION_ENTITY_PAYOUT_SETUP_REQUIRED, status=400, locale="en")

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
        raise envelope_exception(ErrorCode.INSTITUTION_ENTITY_PAYOUT_SETUP_REQUIRED, status=400, locale="en")

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
    Bill must have resolution='pending' and no active payout already in progress.
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


@router.get("/{entity_id}/stripe-connect/payouts", response_model=list[InstitutionBillPayoutResponseSchema])
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
    return [InstitutionBillPayoutResponseSchema(**dict(zip(cols, row, strict=False))) for row in rows]
