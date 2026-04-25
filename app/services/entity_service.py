# app/services/entity_service.py
"""
Entity-specific business logic services.

This file contains business logic functions for specific entities,
using the generic CRUD service for data operations. This separates
pure business logic from data access operations.

Benefits:
- Pure business logic functions
- Clear separation from CRUD operations
- Easy to test and maintain
- Reusable across different contexts
"""

from datetime import datetime
from typing import Any, cast
from uuid import UUID

import psycopg2
from fastapi import HTTPException

from app.config import Status
from app.dto.models import GeolocationDTO, InstitutionBillDTO, PlateDTO, ProductDTO, UserDTO
from app.schemas.consolidated_schemas import (
    AddressEnrichedResponseSchema,
    CreditCurrencyEnrichedResponseSchema,
    DiscretionaryEnrichedResponseSchema,
    InstitutionBillEnrichedResponseSchema,
    InstitutionEntityEnrichedResponseSchema,
    MarketResponseSchema,
    PlanEnrichedResponseSchema,
    PlateEnrichedResponseSchema,
    PlateKitchenDayEnrichedResponseSchema,
    PlatePickupEnrichedResponseSchema,
    ProductEnrichedResponseSchema,
    QRCodeEnrichedResponseSchema,
    QRCodePrintContextSchema,
    RestaurantBalanceEnrichedResponseSchema,
    RestaurantEnrichedResponseSchema,
    RestaurantTransactionEnrichedResponseSchema,
    SubscriptionEnrichedResponseSchema,
    SupplierInvoiceEnrichedResponseSchema,
    UserEnrichedResponseSchema,
)
from app.schemas.payment_method import PaymentMethodEnrichedResponseSchema
from app.schemas.restaurant_holidays import RestaurantHolidayEnrichedResponseSchema
from app.security.institution_scope import InstitutionScope
from app.services.crud_service import (
    geolocation_service,
    institution_bill_service,
    plate_service,
    product_service,
    user_service,
)
from app.services.enriched_service import EnrichedService
from app.services.subscription_action_service import reconcile_hold_subscriptions
from app.utils.address_formatting import format_address_display, format_street_display
from app.utils.db import db_read
from app.utils.log import log_error
from app.utils.phone import format_mobile_for_display
from app.utils.portion_size import bucket_portion_size

# =============================================================================
# USER BUSINESS LOGIC
# =============================================================================


def get_assigned_market_ids(
    user_id: UUID, db: psycopg2.extensions.connection, *, fallback_primary: UUID | None = None
) -> list[UUID]:
    """v2: Return list of market_id for user from user_market_assignment (primary first). If table missing (v1 DB), return [fallback_primary]."""
    try:
        rows = db_read(
            """
            SELECT market_id FROM user_market_assignment
            WHERE user_id = %s
            ORDER BY is_primary DESC, created_at ASC
            """,
            (str(user_id),),
            connection=db,
        )
    except Exception as e:
        if "user_market_assignment" in str(e) and "does not exist" in str(e):
            if fallback_primary is not None:
                return [fallback_primary]
            return []
        raise
    if rows:
        return [UUID(str(r["market_id"])) for r in rows]
    if fallback_primary is not None:
        return [fallback_primary]
    # Fallback: user may have market_id in user_info but no row in user_market_assignment (e.g. customer created before we populated assignments)
    try:
        user_rows = db_read(
            "SELECT market_id FROM user_info WHERE user_id = %s AND market_id IS NOT NULL",
            (str(user_id),),
            connection=db,
        )
        if user_rows and user_rows[0].get("market_id"):
            return [UUID(str(user_rows[0]["market_id"]))]
    except Exception:
        pass
    return []


def get_assigned_market_ids_bulk(
    user_ids: list[UUID], db: psycopg2.extensions.connection, *, primary_by_user: dict[UUID, UUID] | None = None
) -> dict[UUID, list[UUID]]:
    """v2: Return map user_id -> list of market_id for many users. If table missing (v1 DB), use primary_by_user fallback."""
    if not user_ids:
        return {}
    ids_str = ",".join("%s" for _ in user_ids)
    try:
        rows = db_read(
            f"""
            SELECT user_id, market_id FROM user_market_assignment
            WHERE user_id IN ({ids_str})
            ORDER BY is_primary DESC, created_at ASC
            """,
            tuple(str(uid) for uid in user_ids),
            connection=db,
        )
    except Exception as e:
        if "user_market_assignment" in str(e) and "does not exist" in str(e):
            out = {}
            for uid in user_ids:
                out[uid] = [primary_by_user[uid]] if primary_by_user and uid in primary_by_user else []
            return out
        raise
    out: dict[UUID, list[UUID]] = {uid: [] for uid in user_ids}
    for r in rows:
        uid = UUID(str(r["user_id"]))
        mid = UUID(str(r["market_id"]))
        if uid in out:
            out[uid].append(mid)
    for uid in user_ids:
        if not out[uid] and primary_by_user and uid in primary_by_user:
            out[uid] = [primary_by_user[uid]]
    return out


def set_user_market_assignments(
    user_id: UUID,
    market_ids: list[UUID],
    db: psycopg2.extensions.connection,
) -> None:
    """
    v2: Replace user_market_assignment rows for user with the given list.
    First market is primary; user_info.market_id is set to the first.
    Validates that all market_ids exist and are not archived.
    """
    if not market_ids:
        raise HTTPException(
            status_code=400,
            detail="market_ids must contain at least one market when provided.",
        )
    # Validate all markets exist and are not archived
    ids_str = ",".join("%s" for _ in market_ids)
    rows = db_read(
        f"""
        SELECT market_id FROM market_info
        WHERE market_id IN ({ids_str}) AND is_archived = FALSE
        """,
        tuple(str(m) for m in market_ids),
        connection=db,
    )
    found = {UUID(str(r["market_id"])) for r in rows}
    missing = [m for m in market_ids if m not in found]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid or archived market_id(s): {missing}",
        )
    # Validate that requested markets are assigned to the user's institution
    # Skip for Internal (global access) and Customer (Vianda Customers institution is Global, users get local markets)
    user_inst_row = db_read(
        "SELECT u.institution_id, i.institution_type "
        "FROM user_info u "
        "JOIN institution_info i ON u.institution_id = i.institution_id "
        "WHERE u.user_id = %s",
        (str(user_id),),
        connection=db,
        fetch_one=True,
    )
    if user_inst_row:
        inst_type = str(user_inst_row["institution_type"]).lower()
        if inst_type not in ("internal", "customer"):
            institution_id = user_inst_row["institution_id"]
            inst_markets = db_read(
                "SELECT market_id FROM core.institution_market WHERE institution_id = %s",
                (str(institution_id),),
                connection=db,
            )
            inst_market_set = {str(r["market_id"]) for r in (inst_markets or [])}
            for mid in market_ids:
                if str(mid) not in inst_market_set:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Market {mid} is not assigned to the user's institution",
                    )
    cur = db.cursor()
    try:
        cur.execute(
            "DELETE FROM user_market_assignment WHERE user_id = %s",
            (str(user_id),),
        )
        for i, mid in enumerate(market_ids):
            cur.execute(
                """
                INSERT INTO user_market_assignment (user_id, market_id, is_primary)
                VALUES (%s, %s, %s)
                """,
                (str(user_id), str(mid), i == 0),
            )
        cur.execute(
            "UPDATE user_info SET market_id = %s WHERE user_id = %s",
            (str(market_ids[0]), str(user_id)),
        )
        db.commit()
    except Exception as e:
        db.rollback()
        err_msg = str(e)
        if "user_market_assignment" in err_msg and "does not exist" in err_msg:
            raise HTTPException(
                status_code=503,
                detail="market_ids (multi-market) is not available: run schema migration to create user_market_assignment table.",
            ) from None
        log_error(f"set_user_market_assignments failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to update market assignments") from None
    finally:
        cur.close()


# =============================================================================
# INSTITUTION MARKET HELPERS
# =============================================================================


def get_institution_market_ids(
    institution_id: UUID,
    db: psycopg2.extensions.connection,
) -> list[UUID]:
    """Return list of market_ids for an institution from core.institution_market (primary first)."""
    rows = db_read(
        "SELECT market_id FROM core.institution_market WHERE institution_id = %s ORDER BY is_primary DESC",
        (str(institution_id),),
        connection=db,
    )
    return [r["market_id"] for r in (rows or [])]


def get_institution_market_ids_bulk(
    institution_ids: list[UUID],
    db: psycopg2.extensions.connection,
) -> dict[str, list[UUID]]:
    """Bulk fetch institution -> market_ids map to avoid N+1 queries on list endpoints."""
    if not institution_ids:
        return {}
    placeholders = ",".join(["%s"] * len(institution_ids))
    rows = db_read(
        f"SELECT institution_id, market_id FROM core.institution_market "
        f"WHERE institution_id IN ({placeholders}) ORDER BY is_primary DESC",
        tuple(str(iid) for iid in institution_ids),
        connection=db,
    )
    result: dict[str, list[UUID]] = {}
    for r in rows or []:
        key = str(r["institution_id"])
        result.setdefault(key, []).append(r["market_id"])
    return result


def attach_institution_market_ids(institution, db: psycopg2.extensions.connection) -> dict:
    """Convert a single institution DTO to a dict with market_ids attached."""
    d = institution.dict() if hasattr(institution, "dict") else dict(institution)
    d["market_ids"] = get_institution_market_ids(institution.institution_id, db)
    return d


def attach_institution_market_ids_bulk(institutions: list, db: psycopg2.extensions.connection) -> list[dict]:
    """Convert a list of institution DTOs to dicts with market_ids attached (bulk, no N+1)."""
    if not institutions:
        return []
    ids = [inst.institution_id for inst in institutions]
    bulk = get_institution_market_ids_bulk(ids, db)
    result = []
    for inst in institutions:
        d = inst.dict() if hasattr(inst, "dict") else dict(inst)
        d["market_ids"] = bulk.get(str(inst.institution_id), [])
        result.append(d)
    return result


def get_user_by_username(
    username: str, db: psycopg2.extensions.connection, *, scope: InstitutionScope | None = None
) -> UserDTO | None:
    """
    Get user by username - business logic only.

    Args:
        username: Username to search for
        db: Database connection

    Returns:
        UserDTO if found, None otherwise

    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        username_normalized = (username or "").strip().lower()
        return user_service.get_by_field("username", username_normalized, db, scope=scope)
    except Exception as e:
        log_error(f"Error getting user by username {username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user by username") from None


def get_user_by_email(
    email: str, db: psycopg2.extensions.connection, *, scope: InstitutionScope | None = None
) -> UserDTO | None:
    """
    Get user by email - business logic only.

    Args:
        email: Email to search for
        db: Database connection

    Returns:
        UserDTO if found, None otherwise

    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        email_normalized = (email or "").strip().lower()
        return user_service.get_by_field("email", email_normalized, db, scope=scope)
    except Exception as e:
        log_error(f"Error getting user by email {email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user by email") from None


def create_user_with_validation(
    user_data: dict, db: psycopg2.extensions.connection, *, scope: InstitutionScope | None = None
) -> UserDTO:
    """
    Create user with business validation - pure business logic.

    Args:
        user_data: User data dictionary
        db: Database connection

    Returns:
        Created UserDTO

    Raises:
        HTTPException: If validation fails
    """
    # Normalize username and email to lowercase (safety net for any caller)
    user_data["username"] = (user_data.get("username") or "").strip().lower()
    if user_data.get("email"):
        user_data["email"] = user_data["email"].strip().lower()

    # Business validation
    if get_user_by_username(user_data["username"], db):
        raise HTTPException(status_code=400, detail="Username already exists")

    if user_data.get("email") and get_user_by_email(user_data["email"], db):
        raise HTTPException(status_code=400, detail="Email already exists")

    # Create user using generic CRUD
    user = user_service.create(user_data, db, scope=scope)
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create user")

    return user


def get_users_by_institution(institution_id: UUID, db: psycopg2.extensions.connection) -> list[UserDTO]:
    """
    Get all users for an institution - business logic only.

    Args:
        institution_id: Institution ID
        db: Database connection

    Returns:
        List of UserDTOs

    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        all_users = user_service.get_all(db)

        # Filter by institution_id (business logic)
        institution_users = [user for user in all_users if user.institution_id == institution_id]

        # Sort by user_id DESC (newest first; UUID7 is time-ordered)
        institution_users.sort(key=lambda u: u.user_id, reverse=True)

        return institution_users
    except Exception as e:
        log_error(f"Error getting users by institution {institution_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get users for institution") from None


# Initialize EnrichedService instance for users
_user_enriched_service = EnrichedService(
    base_table="user_info",
    table_alias="u",
    id_column="user_id",
    schema_class=UserEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="u",  # institution_id is on the base table
)


def get_enriched_users(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    page: int | None = None,
    page_size: int | None = None,
) -> list[UserEnrichedResponseSchema]:
    """
    Get all users with enriched data (role_name, role_type, institution_name).
    Uses SQL JOINs to avoid N+1 queries.

    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records

    Returns:
        List of enriched user schemas with role and institution names
    """
    users = _user_enriched_service.get_enriched(
        db,
        select_fields=[
            "u.user_id",
            "u.institution_id",
            "i.name as institution_name",
            "u.role_type",
            "u.role_name",
            "u.username",
            "u.email",
            "u.first_name",
            "u.last_name",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as full_name",
            "u.mobile_number",
            "u.mobile_number_verified",
            "u.mobile_number_verified_at",
            "u.email_verified",
            "u.email_verified_at",
            "u.employer_entity_id",
            "u.employer_address_id",
            "emp_entity.name as employer_entity_name",
            "u.workplace_group_id",
            "wg.name as workplace_group_name",
            "u.market_id",
            "gc_country.name as market_name",
            "u.city_metadata_id",
            "COALESCE(cm.display_name_override, gc_city.name) as city_name",
            "u.locale",
            "u.is_archived",
            "u.status",
            "u.created_date",
            "u.modified_date",
        ],
        joins=[
            ("INNER", "core.institution_info", "i", "u.institution_id = i.institution_id"),
            ("INNER", "core.market_info", "m", "u.market_id = m.market_id"),
            (
                "LEFT",
                "ops.institution_entity_info",
                "emp_entity",
                "u.employer_entity_id = emp_entity.institution_entity_id",
            ),
            ("LEFT", "core.workplace_group", "wg", "u.workplace_group_id = wg.workplace_group_id"),
            ("LEFT", "core.city_metadata", "cm", "u.city_metadata_id = cm.city_metadata_id"),
            ("LEFT", "external.geonames_city", "gc_city", "gc_city.geonames_id = cm.geonames_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
        page=page,
        page_size=page_size,
    )
    # v2: attach market_ids for each user (bulk fetch)
    if not users:
        return users
    user_ids = [u.user_id for u in users]
    primary_by_user = {u.user_id: u.market_id for u in users}
    bulk = get_assigned_market_ids_bulk(user_ids, db, primary_by_user=primary_by_user)
    result = []
    for u in users:
        d = u.dict()
        d.pop("market_ids", None)  # avoid duplicate keyword when building schema
        d["market_ids"] = bulk.get(u.user_id, [u.market_id])
        d["mobile_number_display"] = format_mobile_for_display(d.get("mobile_number"))
        result.append(UserEnrichedResponseSchema(**d))
    return result


def get_enriched_user_by_id(
    user_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> UserEnrichedResponseSchema | None:
    """
    Get a single user by ID with enriched data (role_name, role_type, institution_name).
    Uses SQL JOINs to avoid N+1 queries.

    Args:
        user_id: User ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records

    Returns:
        Enriched user schema with role and institution names, or None if not found
    """
    try:
        conditions = ["u.user_id = %s"]
        params: list[Any] = [str(user_id)]

        if not include_archived:
            conditions.append("u.is_archived = FALSE")

        if scope and not scope.is_global and scope.institution_id:
            conditions.append("u.institution_id = %s")
            params.append(scope.institution_id)

        query = f"""
            SELECT
                u.user_id,
                u.institution_id,
                i.name as institution_name,
                u.role_type,
                u.role_name,
                u.username,
                u.email,
                u.first_name,
                u.last_name,
                TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as full_name,
                u.mobile_number,
                u.mobile_number_verified,
                u.mobile_number_verified_at,
                u.email_verified,
                u.email_verified_at,
                u.employer_entity_id,
                u.employer_address_id,
                emp_entity.name as employer_entity_name,
                u.workplace_group_id,
                wg.name as workplace_group_name,
                u.market_id,
                gc_country.name as market_name,
                u.city_metadata_id,
                COALESCE(cm.display_name_override, gc_city.name) as city_name,
                u.locale,
                u.is_archived,
                u.status,
                u.created_date,
                u.modified_date
            FROM core.user_info u
            JOIN core.institution_info i ON u.institution_id = i.institution_id
            JOIN core.market_info m ON u.market_id = m.market_id
            LEFT JOIN external.geonames_country gc_country ON gc_country.iso_alpha2 = m.country_code
            LEFT JOIN ops.institution_entity_info emp_entity ON u.employer_entity_id = emp_entity.institution_entity_id
            LEFT JOIN core.workplace_group wg ON u.workplace_group_id = wg.workplace_group_id
            LEFT JOIN core.city_metadata cm ON u.city_metadata_id = cm.city_metadata_id
            LEFT JOIN external.geonames_city gc_city ON gc_city.geonames_id = cm.geonames_id
            WHERE {" AND ".join(conditions)}
        """

        result = db_read(query, tuple(params), connection=db, fetch_one=True)

        if not result:
            return None

        # v2: add market_ids from user_market_assignment (primary first)
        result = dict(result)
        result["market_ids"] = get_assigned_market_ids(user_id, db, fallback_primary=result.get("market_id"))
        result["mobile_number_display"] = format_mobile_for_display(result.get("mobile_number"))
        enriched_user = UserEnrichedResponseSchema(**result)

        # Apply scope validation
        if scope and not scope.is_global:
            if not scope.matches(enriched_user.institution_id):
                return None

        return enriched_user
    except Exception as e:
        log_error(f"Error getting enriched user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get enriched user") from None


def search_users(
    q: str,
    search_by: str,
    db: psycopg2.extensions.connection,
    *,
    limit: int = 20,
    offset: int = 0,
    role_type: str | None = None,
    scope: InstitutionScope | None = None,
    institution_id: UUID | None = None,
    market_id: UUID | None = None,
) -> tuple[list[dict], int]:
    """
    Search users by name, username, or email with optional role_type filter and pagination.
    Used by discretionary recipient picker and other search-by-select UIs.

    Args:
        q: Search string (substring match, case-insensitive).
        search_by: One of 'name', 'username', 'email'.
        db: Database connection.
        limit: Max results per page.
        offset: Number of items to skip.
        role_type: Optional role_type filter (e.g. 'Customer').
        scope: Optional institution scope (filters by institution_id when not global).
        institution_id: Optional institution ID to restrict results (e.g. from discretionary form).
        market_id: Optional market ID to restrict results to users in that market.

    Returns:
        (list of dicts with user_id, full_name, username, email; total count)
    """
    if search_by not in ("name", "username", "email"):
        raise HTTPException(status_code=400, detail="search_by must be one of: name, username, email")

    q_stripped = (q or "").strip()
    if not q_stripped:
        return [], 0
    search_term = f"%{q_stripped}%"
    conditions = ["u.is_archived = FALSE"]
    params: list[Any] = []

    if search_by == "name":
        conditions.append("TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) ILIKE %s")
        params.append(search_term)
    elif search_by == "username":
        conditions.append("u.username ILIKE %s")
        params.append(search_term)
    else:  # email
        conditions.append("u.email ILIKE %s")
        params.append(search_term)

    if role_type:
        conditions.append("u.role_type::text = %s")
        params.append(role_type)

    if institution_id is not None:
        conditions.append("u.institution_id = %s")
        params.append(str(institution_id))
    elif scope and not scope.is_global and scope.institution_id:
        conditions.append("u.institution_id = %s")
        params.append(str(scope.institution_id))

    if market_id is not None:
        conditions.append("u.market_id = %s")
        params.append(str(market_id))

    where_sql = " AND ".join(conditions)

    count_query = f"""
        SELECT COUNT(*) AS total
        FROM user_info u
        WHERE {where_sql}
    """
    count_result = db_read(count_query, tuple(params), connection=db, fetch_one=True)
    total = int(count_result["total"]) if count_result else 0

    data_query = f"""
        SELECT
            u.user_id,
            TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) AS full_name,
            u.username,
            u.email
        FROM user_info u
        WHERE {where_sql}
        ORDER BY u.username
        LIMIT %s OFFSET %s
    """
    data_params = params + [limit, offset]
    rows = db_read(data_query, tuple(data_params), connection=db, fetch_one=False) or []

    return [dict(r) for r in rows], total


# =============================================================================
# INSTITUTION ENTITY BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for institution entities
_institution_entity_enriched_service = EnrichedService(
    base_table="institution_entity_info",
    table_alias="ie",
    id_column="institution_entity_id",
    schema_class=InstitutionEntityEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="ie",  # institution_id is on the base table
)


def get_enriched_institution_entities(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    institution_id: UUID | None = None,
    institution_market_id: UUID | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[InstitutionEntityEnrichedResponseSchema]:
    """
    Get all institution entities with enriched data (institution, address, and market information).
    Uses SQL JOINs to avoid N+1 queries.

    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records
        institution_id: Optional institution ID to filter results (B2B Internal dropdown scoping)
        institution_market_id: Optional market ID when institution is local (v1 bloat control:
            only entities whose address is in this market are returned)

    Returns:
        List of enriched institution entity schemas with institution, address, and market details
    """
    additional_conditions: list[tuple[str, list]] = []
    if institution_id is not None:
        additional_conditions.append(
            (
                f"{_institution_entity_enriched_service.institution_table_alias}.{_institution_entity_enriched_service.institution_column} = %s",
                [institution_id],
            )
        )
    if institution_market_id is not None:
        additional_conditions.append(
            (
                "a.country_code = (SELECT country_code FROM market_info WHERE market_id = %s AND is_archived = FALSE LIMIT 1)",
                [institution_market_id],
            )
        )
    return _institution_entity_enriched_service.get_enriched(
        db,
        select_fields=[
            "ie.institution_entity_id",
            "ie.institution_id",
            "i.name as institution_name",
            "i.institution_type",
            "ie.currency_metadata_id",
            "m.market_id",
            "gc_country.name as market_name",
            "m.country_code",
            "ie.address_id",
            "gc_country.name as address_country_name",
            "a.country_code as address_country_code",
            "a.province as address_province",
            "a.city as address_city",
            "ie.tax_id",
            "ie.name",
            "ie.payout_provider_account_id",
            "ie.payout_aggregator",
            "ie.payout_onboarding_status",
            "ie.email_domain",
            "ie.is_archived",
            "ie.status",
            "ie.created_date",
            "ie.modified_by",
            "ie.modified_date",
        ],
        joins=[
            ("INNER", "institution_info", "i", "ie.institution_id = i.institution_id"),
            ("INNER", "address_info", "a", "ie.address_id = a.address_id"),
            ("LEFT", "market_info", "m", "a.country_code = m.country_code"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
        additional_conditions=additional_conditions if additional_conditions else None,
        page=page,
        page_size=page_size,
    )


def get_enriched_institution_entity_by_id(
    entity_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> InstitutionEntityEnrichedResponseSchema | None:
    """
    Get a single institution entity by ID with enriched data (institution, address, and market information).
    Uses SQL JOINs to avoid N+1 queries.

    Args:
        entity_id: Institution entity ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records

    Returns:
        Enriched institution entity schema with institution, address, and market details, or None if not found
    """
    return _institution_entity_enriched_service.get_enriched_by_id(
        entity_id,
        db,
        select_fields=[
            "ie.institution_entity_id",
            "ie.institution_id",
            "i.name as institution_name",
            "i.institution_type",
            "ie.currency_metadata_id",
            "m.market_id",
            "gc_country.name as market_name",
            "m.country_code",
            "ie.address_id",
            "gc_country.name as address_country_name",
            "a.country_code as address_country_code",
            "a.province as address_province",
            "a.city as address_city",
            "ie.tax_id",
            "ie.name",
            "ie.payout_provider_account_id",
            "ie.payout_aggregator",
            "ie.payout_onboarding_status",
            "ie.email_domain",
            "ie.is_archived",
            "ie.status",
            "ie.created_date",
            "ie.modified_by",
            "ie.modified_date",
        ],
        joins=[
            ("INNER", "institution_info", "i", "ie.institution_id = i.institution_id"),
            ("INNER", "address_info", "a", "ie.address_id = a.address_id"),
            ("LEFT", "market_info", "m", "a.country_code = m.country_code"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
    )


def get_institution_entity_by_payout_account_id(
    payout_provider_account_id: str,
    db: psycopg2.extensions.connection,
) -> dict | None:
    """Look up institution_entity by payout_provider_account_id. Used by Connect webhook handlers."""
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT institution_entity_id, institution_id, name, payout_provider_account_id
                FROM ops.institution_entity_info
                WHERE payout_provider_account_id = %s AND is_archived = FALSE
                """,
                (payout_provider_account_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row, strict=False))
    except Exception as e:
        log_error(f"Error looking up entity by payout account id {payout_provider_account_id}: {e}")
        return None


# =============================================================================
# ADDRESS BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for addresses
_address_enriched_service = EnrichedService(
    base_table="address_info",
    table_alias="a",
    id_column="address_id",
    schema_class=AddressEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="a",  # institution_id is on the base table
)


def get_enriched_addresses(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    institution_id: UUID | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[AddressEnrichedResponseSchema]:
    """
    Get all addresses with enriched data (institution_name, user_username, user_first_name, user_last_name).
    Uses SQL JOINs to avoid N+1 queries.

    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records
        institution_id: Optional institution ID to filter results (B2B Internal dropdown scoping)

    Returns:
        List of enriched address schemas with institution name and user details
    """
    additional_conditions: list[tuple[str, list]] = []
    if institution_id is not None:
        additional_conditions.append(("a.institution_id = %s", [institution_id]))
    addresses = _address_enriched_service.get_enriched(
        db,
        select_fields=[
            "a.address_id",
            "a.institution_id",
            "i.name as institution_name",
            "a.user_id",
            "u.username as user_username",
            "u.first_name as user_first_name",
            "u.last_name as user_last_name",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as user_full_name",
            # a.employer_id REMOVED
            "a.address_type",
            "FALSE as is_default",
            "NULL::varchar as floor",
            "NULL::varchar as apartment_unit",
            "gc_country.name as country_name",
            "a.country_code",
            "a.province",
            "a.city",
            "a.postal_code",
            "a.street_type",
            "a.street_name",
            "a.building_number",
            "a.timezone",
            "a.is_archived",
            "a.status",
            "a.created_date",
            "a.modified_date",
            "g.latitude",
            "g.longitude",
            "COALESCE(TRIM(CONCAT_WS(' · ', a.street_name, a.city, a.postal_code)), '') as formatted_address",
        ],
        joins=[
            ("INNER", "institution_info", "i", "a.institution_id = i.institution_id"),
            ("LEFT", "user_info", "u", "a.user_id = u.user_id"),
            ("LEFT", "market_info", "m", "a.country_code = m.country_code"),
            ("LEFT", "geolocation_info", "g", "g.address_id = a.address_id AND g.is_archived = FALSE"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
        additional_conditions=additional_conditions if additional_conditions else None,
        page=page,
        page_size=page_size,
    )
    for addr in addresses:
        addr.formatted_address = format_address_display(
            addr.country_code or "",
            addr.street_type,
            addr.street_name,
            addr.building_number,
            addr.city,
            addr.postal_code,
        )
    return addresses


def get_enriched_address_by_id(
    address_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> AddressEnrichedResponseSchema | None:
    """
    Get a single address by ID with enriched data (institution_name, user_username, user_first_name, user_last_name).
    Uses SQL JOINs to avoid N+1 queries.

    Args:
        address_id: Address ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records

    Returns:
        Enriched address schema with institution name and user details, or None if not found
    """
    addr = _address_enriched_service.get_enriched_by_id(
        address_id,
        db,
        select_fields=[
            "a.address_id",
            "a.institution_id",
            "i.name as institution_name",
            "a.user_id",
            "u.username as user_username",
            "u.first_name as user_first_name",
            "u.last_name as user_last_name",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as user_full_name",
            # a.employer_id REMOVED
            "a.address_type",
            "FALSE as is_default",
            "NULL::varchar as floor",
            "NULL::varchar as apartment_unit",
            "gc_country.name as country_name",
            "a.country_code",
            "a.province",
            "a.city",
            "a.postal_code",
            "a.street_type",
            "a.street_name",
            "a.building_number",
            "a.timezone",
            "a.is_archived",
            "a.status",
            "a.created_date",
            "a.modified_date",
            "g.latitude",
            "g.longitude",
            "COALESCE(TRIM(CONCAT_WS(' · ', a.street_name, a.city, a.postal_code)), '') as formatted_address",
        ],
        joins=[
            ("INNER", "institution_info", "i", "a.institution_id = i.institution_id"),
            ("LEFT", "user_info", "u", "a.user_id = u.user_id"),
            ("LEFT", "market_info", "m", "a.country_code = m.country_code"),
            ("LEFT", "geolocation_info", "g", "g.address_id = a.address_id AND g.is_archived = FALSE"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
    )
    if addr:
        addr.formatted_address = format_address_display(
            addr.country_code or "",
            addr.street_type,
            addr.street_name,
            addr.building_number,
            addr.city,
            addr.postal_code,
        )
    return addr


def get_enriched_addresses_for_customer(
    user_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    include_archived: bool = False,
) -> list[AddressEnrichedResponseSchema]:
    """
    Get enriched addresses for a Customer. Same logic as get_addresses_for_customer:
    - Home/billing: addresses created by the user
    - Employer: only the address assigned as employer_address_id (from user_info)
    """
    from app.services.address_service import get_addresses_for_customer

    addresses = get_addresses_for_customer(user_id, db, include_archived=include_archived)
    result: list[AddressEnrichedResponseSchema] = []
    for addr in addresses:
        enriched = get_enriched_address_by_id(addr.address_id, db, scope=None, include_archived=include_archived)
        if enriched:
            result.append(enriched)
    return result


def get_enriched_addresses_search(
    db: psycopg2.extensions.connection,
    *,
    institution_id: UUID | None = None,
    q: str | None = None,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    limit: int = 50,
    page: int | None = None,
    page_size: int | None = None,
) -> list[AddressEnrichedResponseSchema]:
    """
    Search addresses with enriched data, optionally restricted by institution and text query.
    For B2B restaurant address picker: filter by institution_id and optionally search by q
    (matches street_name, city, postal_code, province, formatted_address).
    """
    additional_conditions: list[tuple[str, list]] = []
    effective_scope = scope
    if institution_id is not None:
        additional_conditions.append(("a.institution_id = %s", [institution_id]))
        if scope is None or scope.is_global:
            effective_scope = InstitutionScope(institution_id=institution_id, is_global=False)
    if effective_scope is None and institution_id is not None:
        effective_scope = InstitutionScope(institution_id=institution_id, is_global=False)
    addresses = _address_enriched_service.get_enriched(
        db,
        select_fields=[
            "a.address_id",
            "a.institution_id",
            "i.name as institution_name",
            "a.user_id",
            "u.username as user_username",
            "u.first_name as user_first_name",
            "u.last_name as user_last_name",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as user_full_name",
            # a.employer_id REMOVED
            "a.address_type",
            "FALSE as is_default",
            "NULL::varchar as floor",
            "NULL::varchar as apartment_unit",
            "gc_country.name as country_name",
            "a.country_code",
            "a.province",
            "a.city",
            "a.postal_code",
            "a.street_type",
            "a.street_name",
            "a.building_number",
            "a.timezone",
            "a.is_archived",
            "a.status",
            "a.created_date",
            "a.modified_date",
            "g.latitude",
            "g.longitude",
            "COALESCE(TRIM(CONCAT_WS(' · ', a.street_name, a.city, a.postal_code)), '') as formatted_address",
        ],
        joins=[
            ("INNER", "institution_info", "i", "a.institution_id = i.institution_id"),
            ("LEFT", "user_info", "u", "a.user_id = u.user_id"),
            ("LEFT", "market_info", "m", "a.country_code = m.country_code"),
            ("LEFT", "geolocation_info", "g", "g.address_id = a.address_id AND g.is_archived = FALSE"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=effective_scope,
        include_archived=include_archived,
        additional_conditions=additional_conditions if additional_conditions else None,
        page=page,
        page_size=page_size,
    )
    for addr in addresses:
        addr.formatted_address = format_address_display(
            addr.country_code or "",
            addr.street_type,
            addr.street_name,
            addr.building_number,
            addr.city,
            addr.postal_code,
        )
    # Text filter by q (street_name, city, postal_code, province, formatted_address)
    if q and q.strip():
        q_lower = q.strip().lower()
        addresses = [
            addr
            for addr in addresses
            if q_lower in (addr.street_name or "").lower()
            or q_lower in (addr.city or "").lower()
            or q_lower in (addr.postal_code or "").lower()
            or q_lower in (addr.province or "").lower()
            or q_lower in (addr.formatted_address or "").lower()
        ]
    if limit > 0 and len(addresses) > limit:
        return addresses[:limit]
    return addresses


# =============================================================================
# RESTAURANT ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for restaurants
_restaurant_enriched_service = EnrichedService(
    base_table="restaurant_info",
    table_alias="r",
    id_column="restaurant_id",
    schema_class=RestaurantEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="r",  # institution_id is on the base table
)


def get_enriched_restaurants(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    institution_id: UUID | None = None,
    institution_market_id: UUID | None = None,
    additional_conditions: list[tuple[str, list]] | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[RestaurantEnrichedResponseSchema]:
    """
    Get all restaurants with enriched data (institution name, entity name, address details).

    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)
        institution_id: Optional institution ID to filter results (B2B Internal dropdown scoping)
        institution_market_id: Optional market ID when institution is local (v1 bloat control:
            only restaurants whose address is in this market are returned; pass when
            institution has a non-Global market_id)
        additional_conditions: Optional extra (condition, param_list) tuples from the filter
            registry (e.g. city, market_id, kitchen_day, cuisine, search). Merged with the
            institution_id / institution_market_id conditions built internally.

    Returns:
        List of RestaurantEnrichedResponseSchema with institution, entity, and address details

    Raises:
        HTTPException: For system errors or database failures
    """
    merged_conditions: list[tuple[str, list]] = list(additional_conditions or [])
    if institution_id is not None:
        merged_conditions.append(("r.institution_id = %s", [institution_id]))
    if institution_market_id is not None:
        # Restrict to restaurants in this market (address.country_code = market.country_code)
        merged_conditions.append(
            (
                "a.country_code = (SELECT country_code FROM market_info WHERE market_id = %s AND is_archived = FALSE LIMIT 1)",
                [institution_market_id],
            )
        )
    return _restaurant_enriched_service.get_enriched(
        db,
        select_fields=[
            "r.restaurant_id",
            "r.institution_id",
            "i.name as institution_name",
            "r.institution_entity_id",
            "ie.name as institution_entity_name",
            "r.address_id",
            "gc_country.name as country_name",
            "a.country_code",
            "a.province",
            "a.city",
            "a.postal_code",
            "ie.currency_metadata_id",
            "cc.credit_value_local_currency as market_credit_value_local_currency",
            "r.name",
            "r.cuisine_id",
            "cu.cuisine_name",
            "cu.cuisine_name_i18n",
            "r.tagline",
            "r.tagline_i18n",
            "r.is_featured",
            "r.cover_image_url",
            "r.average_rating",
            "r.review_count",
            "r.verified_badge",
            "r.spotlight_label",
            "r.spotlight_label_i18n",
            "r.member_perks",
            "r.member_perks_i18n",
            "r.is_archived",
            "r.status",
            "r.created_date",
            "r.modified_date",
            # PostGIS: serialise geometry point as GeoJSON. The ::jsonb cast causes
            # psycopg2 to return a parsed Python dict ({"type":"Point","coordinates":[lng,lat]}).
            # ::jsonb (not ::json) is required because this query uses SELECT DISTINCT, and
            # PostgreSQL's json type has no equality operator — jsonb does.
            # GeoJSON coordinate order is [longitude, latitude] — the reverse of conversational
            # "lat/lng" ordering. NULL when location is not yet geocoded.
            "ST_AsGeoJSON(r.location)::jsonb as location",
        ],
        joins=[
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("INNER", "institution_entity_info", "ie", "r.institution_entity_id = ie.institution_entity_id"),
            ("INNER", "currency_metadata", "cc", "ie.currency_metadata_id = cc.currency_metadata_id"),
            ("INNER", "address_info", "a", "r.address_id = a.address_id"),
            ("LEFT", "market_info", "m", "a.country_code = m.country_code"),
            ("LEFT", "cuisine", "cu", "r.cuisine_id = cu.cuisine_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
            # Filter-only joins for kitchen_day. plate_info → plate_kitchen_days is 1:N per
            # restaurant, so rows are deduplicated via distinct=True below. These joins surface
            # pkd.kitchen_day for WHERE filtering without adding it to the SELECT shape.
            ("LEFT", "ops.plate_info", "pi", "pi.restaurant_id = r.restaurant_id AND pi.is_archived = FALSE"),
            ("LEFT", "ops.plate_kitchen_days", "pkd", "pkd.plate_id = pi.plate_id AND pkd.is_archived = FALSE"),
        ],
        scope=scope,
        include_archived=include_archived,
        additional_conditions=merged_conditions if merged_conditions else None,
        page=page,
        page_size=page_size,
        distinct=True,
    )


def get_enriched_restaurant_by_id(
    restaurant_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> RestaurantEnrichedResponseSchema | None:
    """
    Get a single restaurant by ID with enriched data (institution name, entity name, address details).

    Args:
        restaurant_id: Restaurant ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)

    Returns:
        RestaurantEnrichedResponseSchema with institution, entity, and address details, or None if not found

    Raises:
        HTTPException: For system errors or database failures
    """
    return _restaurant_enriched_service.get_enriched_by_id(
        restaurant_id,
        db,
        select_fields=[
            "r.restaurant_id",
            "r.institution_id",
            "i.name as institution_name",
            "r.institution_entity_id",
            "ie.name as institution_entity_name",
            "r.address_id",
            "gc_country.name as country_name",
            "a.country_code",
            "a.province",
            "a.city",
            "a.postal_code",
            "ie.currency_metadata_id",
            "cc.credit_value_local_currency as market_credit_value_local_currency",
            "r.name",
            "r.cuisine_id",
            "cu.cuisine_name",
            "cu.cuisine_name_i18n",
            "r.tagline",
            "r.tagline_i18n",
            "r.is_featured",
            "r.cover_image_url",
            "r.average_rating",
            "r.review_count",
            "r.verified_badge",
            "r.spotlight_label",
            "r.spotlight_label_i18n",
            "r.member_perks",
            "r.member_perks_i18n",
            "r.is_archived",
            "r.status",
            "r.created_date",
            "r.modified_date",
            # PostGIS: serialise geometry point as GeoJSON. The ::jsonb cast causes
            # psycopg2 to return a parsed Python dict ({"type":"Point","coordinates":[lng,lat]}).
            # ::jsonb (not ::json) is required because this query uses SELECT DISTINCT, and
            # PostgreSQL's json type has no equality operator — jsonb does.
            # GeoJSON coordinate order is [longitude, latitude] — the reverse of conversational
            # "lat/lng" ordering. NULL when location is not yet geocoded.
            "ST_AsGeoJSON(r.location)::jsonb as location",
        ],
        joins=[
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("INNER", "institution_entity_info", "ie", "r.institution_entity_id = ie.institution_entity_id"),
            ("INNER", "currency_metadata", "cc", "ie.currency_metadata_id = cc.currency_metadata_id"),
            ("INNER", "address_info", "a", "r.address_id = a.address_id"),
            ("LEFT", "market_info", "m", "a.country_code = m.country_code"),
            ("LEFT", "cuisine", "cu", "r.cuisine_id = cu.cuisine_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
    )


def get_currency_metadata_id_for_restaurant(restaurant, db: psycopg2.extensions.connection) -> UUID:
    """
    Get currency_metadata_id for a restaurant. The credit currency comes from the
    institution_entity, not the restaurant table directly.

    Args:
        restaurant: Restaurant DTO or dict with institution_entity_id or restaurant_id
        db: Database connection

    Returns:
        UUID of the currency_metadata_id for the restaurant's institution_entity

    Raises:
        ValueError: If no currency_metadata_id found for the restaurant
    """
    institution_entity_id = getattr(restaurant, "institution_entity_id", None) or (
        restaurant.get("institution_entity_id") if isinstance(restaurant, dict) else None
    )
    if institution_entity_id:
        rows = db_read(
            "SELECT currency_metadata_id FROM institution_entity_info WHERE institution_entity_id = %s",
            (str(institution_entity_id),),
            connection=db,
        )
    else:
        restaurant_id = getattr(restaurant, "restaurant_id", None) or (
            restaurant.get("restaurant_id") if isinstance(restaurant, dict) else None
        )
        if not restaurant_id:
            raise ValueError("Restaurant must have institution_entity_id or restaurant_id")
        rows = db_read(
            """
            SELECT ie.currency_metadata_id FROM institution_entity_info ie
            INNER JOIN restaurant_info r ON r.institution_entity_id = ie.institution_entity_id
            WHERE r.restaurant_id = %s
            """,
            (str(restaurant_id),),
            connection=db,
        )
    if not rows:
        raise ValueError("Could not find currency_metadata_id for restaurant")
    return UUID(str(rows[0]["currency_metadata_id"]))


def derive_currency_metadata_id_for_address(address_id: UUID, db: psycopg2.extensions.connection) -> UUID:
    """
    Derive currency_metadata_id from an address. The credit currency comes from the
    market associated with the address's country_code (address.country_code -> market_info).

    Args:
        address_id: Address ID
        db: Database connection

    Returns:
        UUID of the currency_metadata_id for the address's market

    Raises:
        ValueError: If address not found or no market/credit_currency for the address's country
    """
    rows = db_read(
        """
        SELECT m.currency_metadata_id
        FROM address_info a
        INNER JOIN market_info m ON a.country_code = m.country_code AND m.is_archived = FALSE
        WHERE a.address_id = %s
        """,
        (str(address_id),),
        connection=db,
    )
    if not rows:
        raise ValueError(f"Could not derive currency_metadata_id for address {address_id}")
    return UUID(str(rows[0]["currency_metadata_id"]))


def search_restaurants(
    q: str,
    search_by: str,
    db: psycopg2.extensions.connection,
    *,
    limit: int = 20,
    offset: int = 0,
    scope: InstitutionScope | None = None,
    institution_id: UUID | None = None,
    market_id: UUID | None = None,
) -> tuple[list[dict], int]:
    """
    Search restaurants by name with pagination.
    Used by discretionary recipient picker and other search-by-select UIs.

    Args:
        q: Search string (substring match, case-insensitive).
        search_by: Must be 'name' (only supported field per contract).
        db: Database connection.
        limit: Max results per page.
        offset: Number of items to skip.
        scope: Optional institution scope (filters by institution_id when not global).
        institution_id: Optional institution ID to restrict results (e.g. from discretionary form).
        market_id: Optional market ID to restrict results to restaurants in that market.

    Returns:
        (list of dicts with restaurant_id, name; total count)
    """
    if search_by not in ("name",):
        raise HTTPException(status_code=400, detail="search_by must be: name")

    q_stripped = (q or "").strip()
    if not q_stripped:
        return [], 0
    search_term = f"%{q_stripped}%"

    conditions = ["r.is_archived = FALSE"]
    params: list[Any] = []

    conditions.append("r.name ILIKE %s")
    params.append(search_term)

    if institution_id is not None:
        conditions.append("r.institution_id = %s")
        params.append(str(institution_id))
    elif scope and not scope.is_global and scope.institution_id:
        conditions.append("r.institution_id = %s")
        params.append(str(scope.institution_id))

    if market_id is not None:
        conditions.append(
            "ie.currency_metadata_id = (SELECT currency_metadata_id FROM market_info WHERE market_id = %s AND is_archived = FALSE LIMIT 1)"
        )
        params.append(str(market_id))

    where_sql = " AND ".join(conditions)
    ie_join = (
        " INNER JOIN institution_entity_info ie ON r.institution_entity_id = ie.institution_entity_id"
        if market_id is not None
        else ""
    )

    count_query = f"""
        SELECT COUNT(*) AS total
        FROM restaurant_info r{ie_join}
        WHERE {where_sql}
    """
    count_result = db_read(count_query, tuple(params), connection=db, fetch_one=True)
    total = int(count_result["total"]) if count_result else 0

    data_query = f"""
        SELECT r.restaurant_id, r.name
        FROM restaurant_info r{ie_join}
        WHERE {where_sql}
        ORDER BY r.name
        LIMIT %s OFFSET %s
    """
    data_params = params + [limit, offset]
    rows = db_read(data_query, tuple(data_params), connection=db, fetch_one=False) or []

    return [dict(r) for r in rows], total


# =============================================================================
# QR CODE ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for QR codes
_qr_code_enriched_service = EnrichedService(
    base_table="qr_code",
    table_alias="q",
    id_column="qr_code_id",
    schema_class=QRCodeEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="r",  # institution_id is on the joined restaurant_info table
)

_qr_code_print_enriched_service = EnrichedService(
    base_table="qr_code",
    table_alias="q",
    id_column="qr_code_id",
    schema_class=QRCodePrintContextSchema,
    institution_column="institution_id",
    institution_table_alias="r",
)


def get_enriched_qr_codes(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    page: int | None = None,
    page_size: int | None = None,
) -> list[QRCodeEnrichedResponseSchema]:
    """
    Get all QR codes with enriched data (institution name, restaurant name, address details).

    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)

    Returns:
        List of QRCodeEnrichedResponseSchema with institution, restaurant, and address details

    Raises:
        HTTPException: For system errors or database failures
    """
    from app.utils.gcs import resolve_qr_code_image_url

    return _qr_code_enriched_service.get_enriched(
        db,
        row_transform=resolve_qr_code_image_url,
        select_fields=[
            "q.qr_code_id",
            "q.restaurant_id",
            "r.name as restaurant_name",
            "r.institution_id",
            "i.name as institution_name",
            "gc_country.name as country_name",
            "a.country_code",
            "a.province",
            "a.city",
            "a.postal_code",
            "TRIM(CONCAT_WS(' ', a.street_type, a.street_name, a.building_number)) as street_address",
            "q.qr_code_payload",
            "q.qr_code_image_url",
            "q.image_storage_path",
            "q.qr_code_checksum",
            "CASE WHEN q.qr_code_image_url IS NOT NULL AND q.qr_code_image_url != '' THEN TRUE ELSE FALSE END as has_image",
            "q.is_archived",
            "q.status",
            "q.created_date",
            "q.modified_date",
        ],
        joins=[
            ("INNER", "restaurant_info", "r", "q.restaurant_id = r.restaurant_id"),
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("INNER", "address_info", "a", "r.address_id = a.address_id"),
            ("LEFT", "market_info", "m", "a.country_code = m.country_code"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
        page=page,
        page_size=page_size,
    )


def get_enriched_qr_code_by_id(
    qr_code_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> QRCodeEnrichedResponseSchema | None:
    """
    Get a single QR code by ID with enriched data (institution name, restaurant name, address details).

    Args:
        qr_code_id: QR code ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)

    Returns:
        QRCodeEnrichedResponseSchema with institution, restaurant, and address details, or None if not found

    Raises:
        HTTPException: For system errors or database failures
    """
    from app.utils.gcs import resolve_qr_code_image_url

    return _qr_code_enriched_service.get_enriched_by_id(
        qr_code_id,
        db,
        row_transform=resolve_qr_code_image_url,
        select_fields=[
            "q.qr_code_id",
            "q.restaurant_id",
            "r.name as restaurant_name",
            "r.institution_id",
            "i.name as institution_name",
            "gc_country.name as country_name",
            "a.country_code",
            "a.province",
            "a.city",
            "a.postal_code",
            "TRIM(CONCAT_WS(' ', a.street_type, a.street_name, a.building_number)) as street_address",
            "q.qr_code_payload",
            "q.qr_code_image_url",
            "q.image_storage_path",
            "q.qr_code_checksum",
            "CASE WHEN q.qr_code_image_url IS NOT NULL AND q.qr_code_image_url != '' THEN TRUE ELSE FALSE END as has_image",
            "q.is_archived",
            "q.status",
            "q.created_date",
            "q.modified_date",
        ],
        joins=[
            ("INNER", "restaurant_info", "r", "q.restaurant_id = r.restaurant_id"),
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("INNER", "address_info", "a", "r.address_id = a.address_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = a.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
    )


def get_qr_code_print_context_by_id(
    qr_code_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> QRCodePrintContextSchema | None:
    """QR row with raw address parts for market-aware print formatting. No signed URL transform."""
    return _qr_code_print_enriched_service.get_enriched_by_id(
        qr_code_id,
        db,
        select_fields=[
            "q.qr_code_id",
            "q.restaurant_id",
            "r.name as restaurant_name",
            "a.country_code",
            "a.street_type",
            "a.street_name",
            "a.building_number",
            "a.city",
            "a.province",
            "a.postal_code",
            "gc_country.name as country_name",
            "q.image_storage_path",
        ],
        joins=[
            ("INNER", "restaurant_info", "r", "q.restaurant_id = r.restaurant_id"),
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("INNER", "address_info", "a", "r.address_id = a.address_id"),
            ("LEFT", "market_info", "m", "a.country_code = m.country_code"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
    )


# =============================================================================
# PRODUCT ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for products
_product_enriched_service = EnrichedService(
    base_table="product_info",
    table_alias="p",
    id_column="product_id",
    schema_class=ProductEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="p",  # institution_id is on the base table
)


def get_enriched_products(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    page: int | None = None,
    page_size: int | None = None,
) -> list[ProductEnrichedResponseSchema]:
    """
    Get all products with enriched data (institution name).

    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)

    Returns:
        List of ProductEnrichedResponseSchema with institution name

    Raises:
        HTTPException: For system errors or database failures
    """
    from app.utils.gcs import resolve_product_image_urls

    return _product_enriched_service.get_enriched(
        db,
        row_transform=resolve_product_image_urls,
        select_fields=[
            "p.product_id",
            "p.institution_id",
            "i.name as institution_name",
            "p.name",
            "p.name_i18n",
            "p.ingredients",
            "p.ingredients_i18n",
            "p.description",
            "p.description_i18n",
            "p.dietary",
            "p.image_url",
            "p.image_storage_path",
            "p.image_thumbnail_url",
            "p.image_thumbnail_storage_path",
            "p.image_checksum",
            "CASE WHEN p.image_storage_path NOT IN ('static/placeholders/product_default.png', 'placeholder/product_default.png') THEN TRUE ELSE FALSE END as has_image",
            "p.is_archived",
            "p.status",
            "p.created_date",
            "p.modified_date",
        ],
        joins=[("INNER", "institution_info", "i", "p.institution_id = i.institution_id")],
        scope=scope,
        include_archived=include_archived,
        page=page,
        page_size=page_size,
    )


def get_enriched_product_by_id(
    product_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> ProductEnrichedResponseSchema | None:
    """
    Get a single product by ID with enriched data (institution name).

    Args:
        product_id: Product ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)

    Returns:
        ProductEnrichedResponseSchema with institution name, or None if not found

    Raises:
        HTTPException: For system errors or database failures
    """
    from app.utils.gcs import resolve_product_image_urls

    return _product_enriched_service.get_enriched_by_id(
        product_id,
        db,
        row_transform=resolve_product_image_urls,
        select_fields=[
            "p.product_id",
            "p.institution_id",
            "i.name as institution_name",
            "p.name",
            "p.name_i18n",
            "p.ingredients",
            "p.ingredients_i18n",
            "p.description",
            "p.description_i18n",
            "p.dietary",
            "p.image_url",
            "p.image_storage_path",
            "p.image_thumbnail_url",
            "p.image_thumbnail_storage_path",
            "p.image_checksum",
            "CASE WHEN p.image_storage_path NOT IN ('static/placeholders/product_default.png', 'placeholder/product_default.png') THEN TRUE ELSE FALSE END as has_image",
            "p.is_archived",
            "p.status",
            "p.created_date",
            "p.modified_date",
        ],
        joins=[("INNER", "institution_info", "i", "p.institution_id = i.institution_id")],
        scope=scope,
        include_archived=include_archived,
    )


# =============================================================================
# PLATE ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for plates
_plate_enriched_service = EnrichedService(
    base_table="plate_info",
    table_alias="p",
    id_column="plate_id",
    schema_class=PlateEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="r",  # institution_id is on the joined restaurant_info table
)


def get_enriched_plates(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    additional_conditions: list[tuple[str, list]] | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[PlateEnrichedResponseSchema]:
    """
    Get all plates with enriched data (institution, restaurant, product, address details).

    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)
        additional_conditions: Optional extra (condition, param_list) tuples from the filter
            registry (e.g. status, market_id, restaurant_id, plate_date_from, plate_date_to).

    Returns:
        List of PlateEnrichedResponseSchema with enriched data

    Raises:
        HTTPException: For system errors or database failures
    """
    from app.utils.gcs import resolve_product_image_urls

    plates = _plate_enriched_service.get_enriched(
        db,
        row_transform=resolve_product_image_urls,
        select_fields=[
            "p.plate_id",
            "p.product_id",
            "p.restaurant_id",
            "i.name as institution_name",
            "r.name as restaurant_name",
            "cu.cuisine_name",
            "cu.cuisine_name_i18n",
            "r.pickup_instructions",
            "gc_country.name as country_name",
            "a.country_code",
            "a.province",
            "a.city",
            "a.street_type",
            "a.street_name",
            "a.building_number",
            "g.latitude",
            "g.longitude",
            "pr.name as product_name",
            "pr.name_i18n as product_name_i18n",
            "pr.dietary",
            "pr.ingredients",
            "pr.ingredients_i18n",
            "pr.description",
            "pr.description_i18n",
            "pr.image_url as product_image_url",
            "pr.image_storage_path as product_image_storage_path",
            "CASE WHEN pr.image_storage_path NOT IN ('static/placeholders/product_default.png', 'placeholder/product_default.png') THEN TRUE ELSE FALSE END as has_image",
            "p.price",
            "p.credit",
            "p.expected_payout_local_currency",
            "st.no_show_discount",
            "p.delivery_time_minutes",
            "p.is_archived",
            "p.status",
            "p.created_date",
            "p.modified_date",
            "(SELECT ROUND(AVG(prv.stars_rating)::numeric, 1) FROM plate_review_info prv WHERE prv.plate_id = p.plate_id AND prv.is_archived = FALSE) as average_stars",
            "(SELECT ROUND(AVG(prv.portion_size_rating)::numeric, 1) FROM plate_review_info prv WHERE prv.plate_id = p.plate_id AND prv.is_archived = FALSE) as average_portion_size",
            "(SELECT COALESCE(COUNT(*)::int, 0) FROM plate_review_info prv WHERE prv.plate_id = p.plate_id AND prv.is_archived = FALSE) as review_count",
        ],
        joins=[
            ("INNER", "product_info", "pr", "p.product_id = pr.product_id"),
            ("INNER", "restaurant_info", "r", "p.restaurant_id = r.restaurant_id"),
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("LEFT", "supplier_terms", "st", "i.institution_id = st.institution_id"),
            ("INNER", "address_info", "a", "r.address_id = a.address_id"),
            ("LEFT", "geolocation_info", "g", "a.address_id = g.address_id AND g.is_archived = FALSE"),
            ("LEFT", "market_info", "m", "a.country_code = m.country_code"),
            ("LEFT", "cuisine", "cu", "r.cuisine_id = cu.cuisine_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
        additional_conditions=additional_conditions,
        page=page,
        page_size=page_size,
    )
    for plate in plates:
        plate.address_display = format_street_display(
            plate.country_code or "",
            plate.street_type,
            plate.street_name,
            plate.building_number,
        )
        # Apply minimum review threshold (5) and portion_size bucketing
        rc = plate.review_count or 0
        if rc < 5:
            plate.average_stars = None
            plate.average_portion_size = None
            plate.portion_size = "insufficient_reviews"
        else:
            plate.portion_size = bucket_portion_size(plate.average_portion_size, rc)
    return plates


def get_enriched_plate_by_id(
    plate_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    kitchen_day: str | None = None,
    employer_entity_id: UUID | None = None,
    employer_address_id: UUID | None = None,
    user_id: UUID | None = None,
) -> PlateEnrichedResponseSchema | None:
    """
    Get a single plate by ID with enriched data (institution, restaurant, product, address details).

    Optionally accepts kitchen_day, employer_entity_id, employer_address_id, user_id for future
    has_coworker_offer / has_coworker_request support; currently accepted but not used.

    Args:
        plate_id: Plate ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)
        kitchen_day: Optional; for future coworker flags (has_coworker_offer, has_coworker_request)
        employer_entity_id: Optional; for future coworker flags
        employer_address_id: Optional; for future coworker flags
        user_id: Optional; for future coworker flags

    Returns:
        PlateEnrichedResponseSchema with enriched data, or None if not found

    Raises:
        HTTPException: For system errors or database failures
    """
    from app.utils.gcs import resolve_product_image_urls

    plate = _plate_enriched_service.get_enriched_by_id(
        plate_id,
        db,
        row_transform=resolve_product_image_urls,
        select_fields=[
            "p.plate_id",
            "p.product_id",
            "p.restaurant_id",
            "i.name as institution_name",
            "r.name as restaurant_name",
            "cu.cuisine_name",
            "cu.cuisine_name_i18n",
            "r.pickup_instructions",
            "gc_country.name as country_name",
            "a.country_code",
            "a.province",
            "a.city",
            "a.street_type",
            "a.street_name",
            "a.building_number",
            "g.latitude",
            "g.longitude",
            "pr.name as product_name",
            "pr.name_i18n as product_name_i18n",
            "pr.dietary",
            "pr.ingredients",
            "pr.ingredients_i18n",
            "pr.description",
            "pr.description_i18n",
            "pr.image_url as product_image_url",
            "pr.image_storage_path as product_image_storage_path",
            "CASE WHEN pr.image_storage_path NOT IN ('static/placeholders/product_default.png', 'placeholder/product_default.png') THEN TRUE ELSE FALSE END as has_image",
            "p.price",
            "p.credit",
            "p.expected_payout_local_currency",
            "st.no_show_discount",
            "p.delivery_time_minutes",
            "p.is_archived",
            "p.status",
            "p.created_date",
            "p.modified_date",
            "(SELECT ROUND(AVG(prv.stars_rating)::numeric, 1) FROM plate_review_info prv WHERE prv.plate_id = p.plate_id AND prv.is_archived = FALSE) as average_stars",
            "(SELECT ROUND(AVG(prv.portion_size_rating)::numeric, 1) FROM plate_review_info prv WHERE prv.plate_id = p.plate_id AND prv.is_archived = FALSE) as average_portion_size",
            "(SELECT COALESCE(COUNT(*)::int, 0) FROM plate_review_info prv WHERE prv.plate_id = p.plate_id AND prv.is_archived = FALSE) as review_count",
        ],
        joins=[
            ("INNER", "product_info", "pr", "p.product_id = pr.product_id"),
            ("INNER", "restaurant_info", "r", "p.restaurant_id = r.restaurant_id"),
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("LEFT", "supplier_terms", "st", "i.institution_id = st.institution_id"),
            ("INNER", "address_info", "a", "r.address_id = a.address_id"),
            ("LEFT", "geolocation_info", "g", "a.address_id = g.address_id AND g.is_archived = FALSE"),
            ("LEFT", "market_info", "m", "a.country_code = m.country_code"),
            ("LEFT", "cuisine", "cu", "r.cuisine_id = cu.cuisine_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
    )
    if plate:
        plate.address_display = format_street_display(
            plate.country_code or "",
            plate.street_type,
            plate.street_name,
            plate.building_number,
        )
        # Apply minimum review threshold (5) and portion_size bucketing
        rc = plate.review_count or 0
        if rc < 5:
            plate.average_stars = None
            plate.average_portion_size = None
            plate.portion_size = "insufficient_reviews"
        else:
            plate.portion_size = bucket_portion_size(plate.average_portion_size, rc)
    return plate


# =============================================================================
# MARKET ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for markets
# Note: Markets don't have institution scoping, so we pass None for institution_column
_market_enriched_service = EnrichedService(
    base_table="market_info",
    table_alias="m",
    id_column="market_id",
    schema_class=MarketResponseSchema,
    institution_column=None,  # Markets don't have institution scoping
    institution_table_alias=None,
)


def _enrich_market_row_with_tax_id(row: dict) -> dict:
    """Inject tax_id config fields (label, regex, example) based on country_code."""
    from app.config.tax_id_config import get_tax_id_config

    cfg = get_tax_id_config(row.get("country_code", ""))
    row["tax_id_label"] = cfg["label"] if cfg else None
    row["tax_id_mask"] = cfg["mask"] if cfg else None
    row["tax_id_regex"] = cfg["regex"] if cfg else None
    row["tax_id_example"] = cfg["example"] if cfg else None
    return row


def get_enriched_markets(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    page: int | None = None,
    page_size: int | None = None,
) -> list[MarketResponseSchema]:
    """
    Get all markets with enriched data (currency name and code).

    Args:
        db: Database connection
        scope: Optional institution scope for filtering (not used for markets, but kept for consistency)
        include_archived: Whether to include archived records (default: False)

    Returns:
        List of MarketResponseSchema with currency name and code

    Raises:
        HTTPException: For system errors or database failures
    """
    return _market_enriched_service.get_enriched(
        db,
        select_fields=[
            "m.market_id",
            "gc_country.name as country_name",
            "m.country_code",
            "m.currency_metadata_id",
            "ic.name as currency_name",
            "c.currency_code",
            "c.credit_value_local_currency",
            "c.currency_conversion_usd",
            "m.language",
            "m.phone_dial_code",
            "m.phone_local_digits",
            "m.is_archived",
            "m.status",
            "m.created_date",
            "m.modified_date",
        ],
        joins=[
            ("LEFT", "currency_metadata", "c", "m.currency_metadata_id = c.currency_metadata_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
            ("LEFT", "external.iso4217_currency", "ic", "ic.code = c.currency_code"),
        ],
        scope=None,  # Markets don't have institution scoping
        include_archived=include_archived,
        order_by="gc_country.name ASC",
        page=page,
        page_size=page_size,
        row_transform=_enrich_market_row_with_tax_id,
    )


def get_enriched_market_by_id(
    market_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> MarketResponseSchema | None:
    """
    Get a single market by ID with enriched data (currency name and code).

    Args:
        market_id: Market ID
        db: Database connection
        scope: Optional institution scope for filtering (not used for markets, but kept for consistency)
        include_archived: Whether to include archived records (default: False)

    Returns:
        MarketResponseSchema with currency name and code, or None if not found

    Raises:
        HTTPException: For system errors or database failures
    """
    return _market_enriched_service.get_enriched_by_id(
        market_id,
        db,
        select_fields=[
            "m.market_id",
            "gc_country.name as country_name",
            "m.country_code",
            "m.currency_metadata_id",
            "ic.name as currency_name",
            "c.currency_code",
            "c.credit_value_local_currency",
            "c.currency_conversion_usd",
            "m.language",
            "m.phone_dial_code",
            "m.phone_local_digits",
            "m.is_archived",
            "m.status",
            "m.created_date",
            "m.modified_date",
        ],
        joins=[
            ("LEFT", "currency_metadata", "c", "m.currency_metadata_id = c.currency_metadata_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
            ("LEFT", "external.iso4217_currency", "ic", "ic.code = c.currency_code"),
        ],
        scope=None,  # Markets don't have institution scoping
        include_archived=include_archived,
        row_transform=_enrich_market_row_with_tax_id,
    )


# =============================================================================
# PLAN ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for plans
# Note: Plans don't have institution scoping, so we pass None for institution_column
_plan_enriched_service = EnrichedService(
    base_table="plan_info",
    table_alias="pl",
    id_column="plan_id",
    schema_class=PlanEnrichedResponseSchema,
    institution_column=None,  # Plans don't have institution scoping
    institution_table_alias=None,
)


def get_enriched_plans(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    additional_conditions: list[tuple] | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[PlanEnrichedResponseSchema]:
    """
    Get all plans with enriched data (currency name, code, and market info).

    Args:
        db: Database connection
        scope: Optional institution scope for filtering (not used for plans, but kept for consistency)
        include_archived: Whether to include archived records (default: False)
        additional_conditions: Optional list of (condition, param) for WHERE clause (e.g. market_id, status, currency_code)

    Returns:
        List of PlanEnrichedResponseSchema with currency and market data

    Raises:
        HTTPException: For system errors or database failures
    """
    return _plan_enriched_service.get_enriched(
        db,
        select_fields=[
            "pl.plan_id",
            "pl.market_id",
            "gc_country.name as market_name",
            "m.country_code",
            "ic.name as currency_name",
            "cc.currency_code",
            "pl.name",
            "pl.name_i18n",
            "pl.marketing_description",
            "pl.marketing_description_i18n",
            "pl.features",
            "pl.features_i18n",
            "pl.cta_label",
            "pl.cta_label_i18n",
            "pl.credit",
            "pl.price",
            "pl.credit_cost_local_currency",
            "pl.credit_cost_usd",
            "pl.rollover",
            "pl.rollover_cap",
            "pl.is_archived",
            "pl.status",
            "pl.created_date",
            "pl.modified_date",
        ],
        joins=[
            ("INNER", "market_info", "m", "pl.market_id = m.market_id"),
            ("INNER", "currency_metadata", "cc", "m.currency_metadata_id = cc.currency_metadata_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
            ("LEFT", "external.iso4217_currency", "ic", "ic.code = cc.currency_code"),
        ],
        scope=None,  # Plans don't have institution scoping
        include_archived=include_archived,
        additional_conditions=additional_conditions,
        page=page,
        page_size=page_size,
    )


def get_enriched_plan_by_id(
    plan_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> PlanEnrichedResponseSchema | None:
    """
    Get a single plan by ID with enriched data (currency name, code, and market info).

    Args:
        plan_id: Plan ID
        db: Database connection
        scope: Optional institution scope for filtering (not used for plans, but kept for consistency)
        include_archived: Whether to include archived records (default: False)

    Returns:
        PlanEnrichedResponseSchema with currency and market data, or None if not found

    Raises:
        HTTPException: For system errors or database failures
    """
    return _plan_enriched_service.get_enriched_by_id(
        plan_id,
        db,
        select_fields=[
            "pl.plan_id",
            "pl.market_id",
            "gc_country.name as market_name",
            "m.country_code",
            "ic.name as currency_name",
            "cc.currency_code",
            "pl.name",
            "pl.name_i18n",
            "pl.marketing_description",
            "pl.marketing_description_i18n",
            "pl.features",
            "pl.features_i18n",
            "pl.cta_label",
            "pl.cta_label_i18n",
            "pl.credit",
            "pl.price",
            "pl.credit_cost_local_currency",
            "pl.credit_cost_usd",
            "pl.rollover",
            "pl.rollover_cap",
            "pl.is_archived",
            "pl.status",
            "pl.created_date",
            "pl.modified_date",
        ],
        joins=[
            ("INNER", "market_info", "m", "pl.market_id = m.market_id"),
            ("INNER", "currency_metadata", "cc", "m.currency_metadata_id = cc.currency_metadata_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
            ("LEFT", "external.iso4217_currency", "ic", "ic.code = cc.currency_code"),
        ],
        scope=None,  # Plans don't have institution scoping
        include_archived=include_archived,
    )


# =============================================================================
# CREDIT CURRENCY ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for credit currencies
# Note: Credit currencies don't have institution scoping, so we pass None for institution_column
_credit_currency_enriched_service = EnrichedService(
    base_table="currency_metadata",
    table_alias="cc",
    id_column="currency_metadata_id",
    schema_class=CreditCurrencyEnrichedResponseSchema,
    institution_column=None,  # Credit currencies don't have institution scoping
    institution_table_alias=None,
)

_CREDIT_CURRENCY_SELECT = [
    "cc.currency_metadata_id",
    "ic.name as currency_name",
    "cc.currency_code",
    "cc.credit_value_local_currency",
    "cc.currency_conversion_usd",
    "cc.is_archived",
    "cc.status",
    "cc.created_date",
    "cc.modified_date",
]

_CREDIT_CURRENCY_JOINS = [
    ("LEFT", "market_info", "m", "cc.currency_metadata_id = m.currency_metadata_id"),
    ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
    ("LEFT", "external.iso4217_currency", "ic", "ic.code = cc.currency_code"),
]

_CREDIT_CURRENCY_MARKETS_AGG = {
    "alias": "markets",
    "fields": {
        "market_id": "m.market_id",
        "market_name": "gc_country.name",
        "country_code": "m.country_code",
    },
    "filter": "m.market_id IS NOT NULL",
    "order_by": "gc_country.name",
}


def get_enriched_credit_currencies(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    page: int | None = None,
    page_size: int | None = None,
) -> list[CreditCurrencyEnrichedResponseSchema]:
    """
    Get all credit currencies with enriched data. One row per currency;
    markets that use the currency are aggregated into a nested array.
    """
    return _credit_currency_enriched_service.get_distinct_enriched(
        db,
        select_fields=_CREDIT_CURRENCY_SELECT,
        aggregate_fields=[_CREDIT_CURRENCY_MARKETS_AGG],
        joins=_CREDIT_CURRENCY_JOINS,
        scope=None,
        include_archived=include_archived,
        page=page,
        page_size=page_size,
    )


def get_enriched_credit_currency_by_id(
    currency_metadata_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> CreditCurrencyEnrichedResponseSchema | None:
    """
    Get a single credit currency by ID with enriched data. Markets aggregated into nested array.
    """
    results = _credit_currency_enriched_service.get_distinct_enriched(
        db,
        select_fields=_CREDIT_CURRENCY_SELECT,
        aggregate_fields=[_CREDIT_CURRENCY_MARKETS_AGG],
        joins=_CREDIT_CURRENCY_JOINS,
        additional_conditions=[("cc.currency_metadata_id = %s", [str(currency_metadata_id)])],
        scope=None,
        include_archived=include_archived,
    )
    return results[0] if results else None


# =============================================================================
# DISCRETIONARY ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for discretionary requests
# Note: Discretionary requests have institution scoping through user or restaurant
_discretionary_enriched_service = EnrichedService(
    base_table="discretionary_info",
    table_alias="d",
    id_column="discretionary_id",
    schema_class=DiscretionaryEnrichedResponseSchema,
    institution_column="i.institution_id",  # Via user or restaurant
    institution_table_alias="i",
)


def get_enriched_discretionary_requests(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    page: int | None = None,
    page_size: int | None = None,
) -> list[DiscretionaryEnrichedResponseSchema]:
    """
    Get all discretionary requests with enriched data (user, restaurant, institution, and market information).

    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)

    Returns:
        List of DiscretionaryEnrichedResponseSchema with full context

    Raises:
        HTTPException: For system errors or database failures
    """
    return _discretionary_enriched_service.get_enriched(
        db,
        select_fields=[
            "d.discretionary_id",
            "d.user_id",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as user_full_name",
            "u.username as user_username",
            "d.restaurant_id",
            "r.name as restaurant_name",
            "COALESCE(u.institution_id, ie.institution_id) as institution_id",
            "i.name as institution_name",
            "ie.currency_metadata_id",
            "ic.name as currency_name",
            "cc.currency_code",
            "m.market_id",
            "gc_country.name as market_name",
            "m.country_code",
            "d.approval_id",
            "d.category",
            "d.reason",
            "d.amount",
            "d.comment",
            "d.is_archived",
            "d.status",
            "d.created_date",
            "d.modified_date",
            "(SELECT dh.changed_by FROM discretionary_history dh WHERE dh.discretionary_id = d.discretionary_id AND dh.operation = 'create' ORDER BY dh.changed_at ASC LIMIT 1) as created_by",
            "(SELECT TRIM(COALESCE(CONCAT_WS(' ', u2.first_name, u2.last_name), '')) FROM discretionary_history dh JOIN user_info u2 ON u2.user_id = dh.changed_by WHERE dh.discretionary_id = d.discretionary_id AND dh.operation = 'create' ORDER BY dh.changed_at ASC LIMIT 1) as created_by_name",
        ],
        joins=[
            ("LEFT", "user_info", "u", "d.user_id = u.user_id"),
            ("LEFT", "restaurant_info", "r", "d.restaurant_id = r.restaurant_id"),
            ("LEFT", "institution_entity_info", "ie", "r.institution_entity_id = ie.institution_entity_id"),
            ("INNER", "institution_info", "i", "COALESCE(u.institution_id, ie.institution_id) = i.institution_id"),
            ("LEFT", "currency_metadata", "cc", "ie.currency_metadata_id = cc.currency_metadata_id"),
            ("LEFT", "market_info", "m", "cc.currency_metadata_id = m.currency_metadata_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
            ("LEFT", "external.iso4217_currency", "ic", "ic.code = cc.currency_code"),
        ],
        scope=scope,
        include_archived=include_archived,
        page=page,
        page_size=page_size,
    )


def get_enriched_discretionary_request_by_id(
    discretionary_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> DiscretionaryEnrichedResponseSchema | None:
    """
    Get a single discretionary request by ID with enriched data.

    Args:
        discretionary_id: Discretionary Request ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)

    Returns:
        DiscretionaryEnrichedResponseSchema with full context, or None if not found

    Raises:
        HTTPException: For system errors or database failures
    """
    return _discretionary_enriched_service.get_enriched_by_id(
        discretionary_id,
        db,
        select_fields=[
            "d.discretionary_id",
            "d.user_id",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as user_full_name",
            "u.username as user_username",
            "d.restaurant_id",
            "r.name as restaurant_name",
            "COALESCE(u.institution_id, ie.institution_id) as institution_id",
            "i.name as institution_name",
            "ie.currency_metadata_id",
            "ic.name as currency_name",
            "cc.currency_code",
            "m.market_id",
            "gc_country.name as market_name",
            "m.country_code",
            "d.approval_id",
            "d.category",
            "d.reason",
            "d.amount",
            "d.comment",
            "d.is_archived",
            "d.status",
            "d.created_date",
            "d.modified_date",
            "(SELECT dh.changed_by FROM discretionary_history dh WHERE dh.discretionary_id = d.discretionary_id AND dh.operation = 'create' ORDER BY dh.changed_at ASC LIMIT 1) as created_by",
            "(SELECT TRIM(COALESCE(CONCAT_WS(' ', u2.first_name, u2.last_name), '')) FROM discretionary_history dh JOIN user_info u2 ON u2.user_id = dh.changed_by WHERE dh.discretionary_id = d.discretionary_id AND dh.operation = 'create' ORDER BY dh.changed_at ASC LIMIT 1) as created_by_name",
        ],
        joins=[
            ("LEFT", "user_info", "u", "d.user_id = u.user_id"),
            ("LEFT", "restaurant_info", "r", "d.restaurant_id = r.restaurant_id"),
            ("LEFT", "institution_entity_info", "ie", "r.institution_entity_id = ie.institution_entity_id"),
            ("INNER", "institution_info", "i", "COALESCE(u.institution_id, ie.institution_id) = i.institution_id"),
            ("LEFT", "currency_metadata", "cc", "ie.currency_metadata_id = cc.currency_metadata_id"),
            ("LEFT", "market_info", "m", "cc.currency_metadata_id = m.currency_metadata_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
            ("LEFT", "external.iso4217_currency", "ic", "ic.code = cc.currency_code"),
        ],
        scope=scope,
        include_archived=include_archived,
    )


# =============================================================================
# PRODUCT BUSINESS LOGIC
# =============================================================================


def get_products_by_institution(institution_id: UUID, db: psycopg2.extensions.connection) -> list[ProductDTO]:
    """
    Get all products for an institution - business logic only.

    Args:
        institution_id: Institution ID
        db: Database connection

    Returns:
        List of ProductDTOs

    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        all_products = product_service.get_all(db)

        # Filter by institution_id (business logic)
        institution_products = [product for product in all_products if product.institution_id == institution_id]

        # Sort by name (business logic)
        institution_products.sort(key=lambda p: p.name)

        return institution_products
    except Exception as e:
        log_error(f"Error getting products by institution {institution_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get products for institution") from None


def search_products_by_name(
    search_term: str, institution_id: UUID, db: psycopg2.extensions.connection
) -> list[ProductDTO]:
    """
    Search products by name - business logic only.

    Args:
        search_term: Term to search for
        institution_id: Institution ID
        db: Database connection

    Returns:
        List of matching ProductDTOs

    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        all_products = product_service.get_all(db)

        # Filter by institution_id and name search (business logic)
        search_term_lower = search_term.lower()
        matching_products = [
            product
            for product in all_products
            if product.institution_id == institution_id and search_term_lower in product.name.lower()
        ]

        # Sort by name (business logic)
        matching_products.sort(key=lambda p: p.name)

        return matching_products
    except Exception as e:
        log_error(f"Error searching products by name {search_term}: {e}")
        raise HTTPException(status_code=500, detail="Failed to search products") from None


# =============================================================================
# PLATE BUSINESS LOGIC
# =============================================================================


def get_plates_by_restaurant(restaurant_id: UUID, db: psycopg2.extensions.connection) -> list[PlateDTO]:
    """
    Get all plates for a restaurant - business logic only.

    Args:
        restaurant_id: Restaurant ID
        db: Database connection

    Returns:
        List of PlateDTOs

    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        all_plates = plate_service.get_all(db)

        # Filter by restaurant_id (business logic)
        restaurant_plates = [plate for plate in all_plates if plate.restaurant_id == restaurant_id]

        # Sort by price (business logic)
        restaurant_plates.sort(key=lambda p: p.price)

        return restaurant_plates
    except Exception as e:
        log_error(f"Error getting plates by restaurant {restaurant_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get plates for restaurant") from None


def get_plates_by_product(product_id: UUID, db: psycopg2.extensions.connection) -> list[PlateDTO]:
    """
    Get all plates for a product - business logic only.

    Args:
        product_id: Product ID
        db: Database connection

    Returns:
        List of PlateDTOs

    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        all_plates = plate_service.get_all(db)

        # Filter by product_id (business logic)
        product_plates = [plate for plate in all_plates if plate.product_id == product_id]

        # Sort by price (business logic)
        product_plates.sort(key=lambda p: p.price)

        return product_plates
    except Exception as e:
        log_error(f"Error getting plates by product {product_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get plates for product") from None


# =============================================================================
# BILLING BUSINESS LOGIC
# =============================================================================


def get_pending_bills_by_institution(
    institution_id: UUID, db: psycopg2.extensions.connection
) -> list[InstitutionBillDTO]:
    """
    Get all pending bills for an institution - business logic only.

    Args:
        institution_id: Institution Entity ID (actually institution_entity_id)
        db: Database connection

    Returns:
        List of pending InstitutionBillDTOs

    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        all_bills = institution_bill_service.get_all(db)

        # Filter by institution_entity_id and pending status (business logic)
        # Note: Despite the parameter name, this filters by institution_entity_id
        pending_bills = [
            bill for bill in all_bills if bill.institution_entity_id == institution_id and bill.status == Status.PENDING
        ]

        # Sort by institution_bill_id DESC (newest first; UUID7 is time-ordered)
        pending_bills.sort(key=lambda b: b.institution_bill_id, reverse=True)

        return pending_bills
    except Exception as e:
        log_error(f"Error getting pending bills by institution {institution_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pending bills for institution") from None


def get_bills_by_status(
    institution_id: UUID, status: str, db: psycopg2.extensions.connection
) -> list[InstitutionBillDTO]:
    """
    Get bills by status for an institution - business logic only.

    Args:
        institution_id: Institution ID
        status: Bill status to filter by
        db: Database connection

    Returns:
        List of InstitutionBillDTOs

    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        all_bills = institution_bill_service.get_all(db)

        # Filter by institution_id and status (business logic)
        filtered_bills = [
            bill for bill in all_bills if bill.institution_entity_id == institution_id and bill.status == status
        ]

        # Sort by institution_bill_id DESC (newest first; UUID7 is time-ordered)
        filtered_bills.sort(key=lambda b: b.institution_bill_id, reverse=True)

        return filtered_bills
    except Exception as e:
        log_error(f"Error getting bills by status {status} for institution {institution_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get bills for institution") from None


# =============================================================================
# EMPLOYER BUSINESS LOGIC — REMOVED
# employer identity is now institution_info (type=employer) + institution_entity_info.
# Removed: create_employer_with_address(), get_employers_by_name(),
#          get_enriched_employers(), get_enriched_employer_by_id(), _employer_enriched_service
# See docs/plans/MULTINATIONAL_INSTITUTIONS.md
# =============================================================================

# =============================================================================
# GEOLOCATION BUSINESS LOGIC
# =============================================================================


def get_geolocation_by_address_id(address_id: UUID, db: psycopg2.extensions.connection) -> GeolocationDTO | None:
    """
    Get geolocation by address ID - business logic only.

    Args:
        address_id: Address ID to search for
        db: Database connection

    Returns:
        GeolocationDTO if found, None otherwise

    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        return geolocation_service.get_by_field("address_id", address_id, db)
    except Exception as e:
        log_error(f"Error getting geolocation by address ID {address_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get geolocation by address ID") from None


# =============================================================================
# SUBSCRIPTION BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for subscriptions
# Note: institution_id is on the joined user_info table
_subscription_enriched_service = EnrichedService(
    base_table="subscription_info",
    table_alias="s",
    id_column="subscription_id",
    schema_class=SubscriptionEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="u",  # institution_id is on the joined user_info table
)


def get_enriched_subscriptions(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    user_id: UUID | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[SubscriptionEnrichedResponseSchema]:
    """
    Get all subscriptions with enriched data (user, plan, and market information).
    Includes: user_full_name, user_username, user_email, user_status, user_mobile_number,
    plan_name, plan_credit, plan_price, plan_rollover, plan_rollover_cap, plan_status,
    market_id, market_name, country_code.
    Uses SQL JOINs to avoid N+1 queries.

    Args:
        db: Database connection
        scope: Optional institution scope for filtering (not typically used for subscriptions)
        include_archived: Whether to include archived records
        user_id: Optional user_id to filter subscriptions by user

    Returns:
        List of enriched subscription schemas with user, plan, and market information
    """
    reconcile_hold_subscriptions(db)
    additional_conditions = []
    if user_id:
        additional_conditions.append(("s.user_id = %s::uuid", [str(user_id)]))

    return _subscription_enriched_service.get_enriched(
        db,
        select_fields=[
            "s.subscription_id",
            "s.user_id",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as user_full_name",
            "u.username as user_username",
            "u.email as user_email",
            "u.status as user_status",
            "u.mobile_number as user_mobile_number",
            "s.plan_id",
            "p.name as plan_name",
            "p.credit as plan_credit",
            "p.price as plan_price",
            "p.rollover as plan_rollover",
            "p.rollover_cap as plan_rollover_cap",
            "p.status as plan_status",
            "p.market_id",
            "gc_country.name as market_name",
            "m.country_code",
            "s.renewal_date",
            "s.balance",
            "s.is_archived",
            "s.status",
            "s.subscription_status",
            "s.hold_start_date",
            "s.hold_end_date",
            "s.early_renewal_threshold",
            "s.created_date",
            "s.modified_by",
            "s.modified_date",
        ],
        joins=[
            ("INNER", "user_info", "u", "s.user_id = u.user_id"),
            ("INNER", "plan_info", "p", "s.plan_id = p.plan_id"),
            ("INNER", "market_info", "m", "p.market_id = m.market_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
        additional_conditions=additional_conditions if additional_conditions else None,
        page=page,
        page_size=page_size,
    )


def get_enriched_subscription_by_id(
    subscription_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> SubscriptionEnrichedResponseSchema | None:
    """
    Get a single subscription by ID with enriched data (user, plan, and market information).
    Includes: user_full_name, user_username, user_email, user_status, user_mobile_number,
    plan_name, plan_credit, plan_price, plan_rollover, plan_rollover_cap, plan_status,
    market_id, market_name, country_code.
    Uses SQL JOINs to avoid N+1 queries.

    Args:
        subscription_id: Subscription ID
        db: Database connection
        scope: Optional institution scope for filtering (not typically used for subscriptions)
        include_archived: Whether to include archived records

    Returns:
        Enriched subscription schema with user, plan, and market information, or None if not found
    """
    reconcile_hold_subscriptions(db)
    return _subscription_enriched_service.get_enriched_by_id(
        subscription_id,
        db,
        select_fields=[
            "s.subscription_id",
            "s.user_id",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as user_full_name",
            "u.username as user_username",
            "u.email as user_email",
            "u.status as user_status",
            "u.mobile_number as user_mobile_number",
            "s.plan_id",
            "p.name as plan_name",
            "p.credit as plan_credit",
            "p.price as plan_price",
            "p.rollover as plan_rollover",
            "p.rollover_cap as plan_rollover_cap",
            "p.status as plan_status",
            "p.market_id",
            "gc_country.name as market_name",
            "m.country_code",
            "s.renewal_date",
            "s.balance",
            "s.is_archived",
            "s.status",
            "s.subscription_status",
            "s.hold_start_date",
            "s.hold_end_date",
            "s.early_renewal_threshold",
            "s.created_date",
            "s.modified_by",
            "s.modified_date",
        ],
        joins=[
            ("INNER", "user_info", "u", "s.user_id = u.user_id"),
            ("INNER", "plan_info", "p", "s.plan_id = p.plan_id"),
            ("INNER", "market_info", "m", "p.market_id = m.market_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
    )


# =============================================================================
# INSTITUTION BILL ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for institution bills
_bill_enriched_service = EnrichedService(
    base_table="institution_bill_info",
    table_alias="ibi",
    id_column="institution_bill_id",
    schema_class=InstitutionBillEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="ibi",  # institution_id is on the base table
)


def get_enriched_institution_bills(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    page: int | None = None,
    page_size: int | None = None,
) -> list[InstitutionBillEnrichedResponseSchema]:
    """
    Get all institution bills with enriched data (institution, entity, restaurant, and market information).
    Returns an array of enriched institution bill records.

    Scoping rules:
    - If scope is global (Internal): Returns all institution bills
    - If scope is institution-scoped (Supplier): Returns bills for restaurants in their institution

    Args:
        db: Database connection
        scope: Optional institution scope for filtering (for Internal/Suppliers)
        include_archived: Whether to include archived records (default: False)

    Returns:
        List of InstitutionBillEnrichedResponseSchema with institution, entity, restaurant, currency, and market information

    Raises:
        HTTPException: For system errors or database failures
    """
    return _bill_enriched_service.get_enriched(
        db,
        select_fields=[
            "ibi.institution_bill_id",
            "ibi.institution_id",
            "COALESCE(i.name, '') as institution_name",
            "ibi.institution_entity_id",
            "COALESCE(ie.name, '') as institution_entity_name",
            "ibi.currency_metadata_id",
            "m.market_id",
            "gc_country.name as market_name",
            "m.country_code",
            "ibi.transaction_count",
            "ibi.amount",
            "ibi.currency_code",
            "ibi.period_start",
            "ibi.period_end",
            "ibi.is_archived",
            "ibi.status",
            "ibi.resolution",
            "ibi.created_date",
            "ibi.modified_by",
            "ibi.modified_date",
        ],
        joins=[
            ("LEFT", "institution_info", "i", "ibi.institution_id = i.institution_id"),
            ("LEFT", "institution_entity_info", "ie", "ibi.institution_entity_id = ie.institution_entity_id"),
            ("INNER", "market_info", "m", "ibi.currency_metadata_id = m.currency_metadata_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
        page=page,
        page_size=page_size,
    )


# =============================================================================
# BILL PAYOUT ENRICHED BUSINESS LOGIC
# =============================================================================


def get_enriched_bill_payouts(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> list:
    """
    Get all bill payouts with enriched data (institution, entity, billing period).
    Entity-level view — no restaurant breakdown (bills aggregate across restaurants).

    Scoping:
    - Internal: all payouts
    - Supplier: payouts for bills belonging to their institution

    Uses hand-written SQL because institution_bill_payout has no is_archived column;
    the bill's is_archived is used for filtering instead.
    """
    conditions = ["ibi.is_archived = FALSE"] if not include_archived else []
    params = []
    if scope and not scope.is_global and scope.institution_id:
        conditions.append("ibi.institution_id = %s::uuid")
        params.append(str(scope.institution_id))

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT
            bp.bill_payout_id,
            bp.institution_bill_id,
            ibi.institution_id,
            COALESCE(i.name, '') AS institution_name,
            ibi.institution_entity_id,
            COALESCE(ie.name, '') AS institution_entity_name,
            bp.provider,
            bp.provider_transfer_id,
            bp.amount,
            bp.currency_code,
            ibi.period_start AS billing_period_start,
            ibi.period_end AS billing_period_end,
            bp.status,
            bp.created_at,
            bp.completed_at
        FROM billing.institution_bill_payout bp
        INNER JOIN billing.institution_bill_info ibi
            ON bp.institution_bill_id = ibi.institution_bill_id
        LEFT JOIN core.institution_info i
            ON ibi.institution_id = i.institution_id
        LEFT JOIN ops.institution_entity_info ie
            ON ibi.institution_entity_id = ie.institution_entity_id
        {where}
        ORDER BY bp.created_at DESC
    """
    rows = db_read(query, tuple(params) if params else None, connection=db)
    return rows if rows else []


# =============================================================================
# SUPPLIER INVOICE ENRICHED BUSINESS LOGIC
# =============================================================================

_supplier_invoice_enriched_service = EnrichedService(
    base_table="supplier_invoice",
    table_alias="si",
    id_column="supplier_invoice_id",
    schema_class=SupplierInvoiceEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="ie",
)


def get_enriched_supplier_invoices(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    institution_entity_id: UUID | None = None,
    status_filter: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[SupplierInvoiceEnrichedResponseSchema]:
    """
    Get supplier invoices with enriched data (entity name, institution name, created-by name).
    Uses SQL JOINs to avoid N+1 queries.
    """
    additional_conditions: list[tuple[str, list]] = []
    if institution_entity_id is not None:
        additional_conditions.append(("si.institution_entity_id = %s", [institution_entity_id]))
    if status_filter is not None:
        additional_conditions.append(("si.status = %s::supplier_invoice_status_enum", [status_filter]))

    return _supplier_invoice_enriched_service.get_enriched(
        db,
        select_fields=[
            "si.supplier_invoice_id",
            "si.institution_entity_id",
            "COALESCE(ie.name, '') as institution_entity_name",
            "COALESCE(i.name, '') as institution_name",
            "si.country_code",
            "si.invoice_type",
            "si.external_invoice_number",
            "si.issued_date",
            "si.amount",
            "si.currency_code",
            "si.tax_amount",
            "si.tax_rate",
            "si.document_storage_path",
            "si.document_format",
            "si.status",
            "si.rejection_reason",
            "si.reviewed_by",
            "si.reviewed_at",
            "COALESCE(u.first_name || ' ' || u.last_name, '') as created_by_name",
            "si.is_archived",
            "si.created_date",
            "si.created_by",
            "si.modified_by",
            "si.modified_date",
        ],
        joins=[
            ("INNER", "institution_entity_info", "ie", "si.institution_entity_id = ie.institution_entity_id"),
            ("LEFT", "institution_info", "i", "ie.institution_id = i.institution_id"),
            ("LEFT", "user_info", "u", "si.created_by = u.user_id"),
        ],
        scope=scope,
        include_archived=include_archived,
        additional_conditions=additional_conditions if additional_conditions else None,
        page=page,
        page_size=page_size,
    )


# =============================================================================
# RESTAURANT BALANCE ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for restaurant balances
_restaurant_balance_enriched_service = EnrichedService(
    base_table="restaurant_balance_info",
    table_alias="rb",
    id_column="restaurant_id",
    schema_class=RestaurantBalanceEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="r",  # institution_id is on the joined restaurant_info table
)


def get_enriched_restaurant_balances(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    page: int | None = None,
    page_size: int | None = None,
) -> list[RestaurantBalanceEnrichedResponseSchema]:
    """
    Get all restaurant balances with enriched data (institution name, entity name, restaurant name, country).
    Returns an array of enriched restaurant balance records.

    **Note: This is a read-only endpoint. Restaurant balances are automatically managed by the backend
    through transactions and billing operations. They cannot be created or modified via API.**

    Scoping rules:
    - If scope is global (Internal): Returns all restaurant balances
    - If scope is institution-scoped (Supplier): Returns balances for restaurants in their institution

    Args:
        db: Database connection
        scope: Optional institution scope for filtering (for Internal/Suppliers)
        include_archived: Whether to include archived records (default: False)

    Returns:
        List of RestaurantBalanceEnrichedResponseSchema with institution, entity, restaurant, and address information

    Raises:
        HTTPException: For system errors or database failures
    """
    return _restaurant_balance_enriched_service.get_enriched(
        db,
        select_fields=[
            "rb.restaurant_id",
            "r.institution_id",
            "COALESCE(i.name, '') as institution_name",
            "r.institution_entity_id",
            "COALESCE(ie.name, '') as institution_entity_name",
            "COALESCE(r.name, '') as restaurant_name",
            "gc_country.name as country_name",
            "a.country_code",
            "rb.currency_metadata_id",
            "rb.transaction_count",
            "rb.balance",
            "rb.currency_code",
            "rb.is_archived",
            "rb.status",
            "rb.created_date",
            "rb.modified_by",
            "rb.modified_date",
        ],
        joins=[
            ("INNER", "restaurant_info", "r", "rb.restaurant_id = r.restaurant_id"),
            ("LEFT", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("LEFT", "institution_entity_info", "ie", "r.institution_entity_id = ie.institution_entity_id"),
            ("LEFT", "address_info", "a", "r.address_id = a.address_id"),
            ("LEFT", "market_info", "m", "a.country_code = m.country_code"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
        page=page,
        page_size=page_size,
    )


def get_enriched_restaurant_balance_by_id(
    db: psycopg2.extensions.connection,
    restaurant_id: UUID,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> RestaurantBalanceEnrichedResponseSchema | None:
    """
    Get a single restaurant balance by restaurant ID with enriched data (institution name, entity name, restaurant name, country).

    **Note: This is a read-only endpoint. Restaurant balances are automatically managed by the backend
    through transactions and billing operations. They cannot be created or modified via API.**

    Scoping rules:
    - If scope is global (Internal): Returns any restaurant balance
    - If scope is institution-scoped (Supplier): Returns balance only if restaurant belongs to their institution

    Args:
        db: Database connection
        restaurant_id: Restaurant ID (primary key of restaurant_balance_info)
        scope: Optional institution scope for filtering (for Internal/Suppliers)
        include_archived: Whether to include archived records (default: False)

    Returns:
        RestaurantBalanceEnrichedResponseSchema with institution, entity, restaurant, and address information, or None if not found

    Raises:
        HTTPException: For system errors or database failures
    """
    return _restaurant_balance_enriched_service.get_enriched_by_id(
        db,
        restaurant_id,
        select_fields=[
            "rb.restaurant_id",
            "r.institution_id",
            "COALESCE(i.name, '') as institution_name",
            "r.institution_entity_id",
            "COALESCE(ie.name, '') as institution_entity_name",
            "COALESCE(r.name, '') as restaurant_name",
            "gc_country.name as country_name",
            "a.country_code",
            "rb.currency_metadata_id",
            "rb.transaction_count",
            "rb.balance",
            "rb.currency_code",
            "rb.is_archived",
            "rb.status",
            "rb.created_date",
            "rb.modified_by",
            "rb.modified_date",
        ],
        joins=[
            ("INNER", "restaurant_info", "r", "rb.restaurant_id = r.restaurant_id"),
            ("LEFT", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("LEFT", "institution_entity_info", "ie", "r.institution_entity_id = ie.institution_entity_id"),
            ("LEFT", "address_info", "a", "r.address_id = a.address_id"),
            ("LEFT", "market_info", "m", "a.country_code = m.country_code"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
    )


# =============================================================================
# RESTAURANT TRANSACTION ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for restaurant transactions
_restaurant_transaction_enriched_service = EnrichedService(
    base_table="restaurant_transaction",
    table_alias="rt",
    id_column="transaction_id",
    schema_class=RestaurantTransactionEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="r",  # institution_id is on the joined restaurant_info table
)


def get_enriched_restaurant_transactions(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    page: int | None = None,
    page_size: int | None = None,
) -> list[RestaurantTransactionEnrichedResponseSchema]:
    """
    Get all restaurant transactions with enriched data (institution name, entity name, restaurant name, plate name, currency code, country).
    Returns an array of enriched restaurant transaction records.

    **Note: This is a read-only endpoint. Restaurant transactions are automatically managed by the backend
    through plate selection, QR code scanning, and billing operations. They cannot be created or modified via API.**

    Scoping rules:
    - If scope is global (Internal): Returns all restaurant transactions
    - If scope is institution-scoped (Supplier): Returns transactions for restaurants in their institution

    Args:
        db: Database connection
        scope: Optional institution scope for filtering (for Internal/Suppliers)
        include_archived: Whether to include archived records (default: False)

    Returns:
        List of RestaurantTransactionEnrichedResponseSchema with institution, entity, restaurant, plate, and address information

    Raises:
        HTTPException: For system errors or database failures
    """
    return _restaurant_transaction_enriched_service.get_enriched(
        db,
        select_fields=[
            "rt.transaction_id",
            "rt.restaurant_id",
            "r.institution_id",
            "COALESCE(i.name, '') as institution_name",
            "r.institution_entity_id",
            "COALESCE(ie.name, '') as institution_entity_name",
            "COALESCE(r.name, '') as restaurant_name",
            "rt.plate_selection_id",
            "COALESCE(pr.name, '') as plate_name",
            "rt.discretionary_id",
            "rt.currency_metadata_id",
            "rt.currency_code",
            "gc_country.name as country_name",
            "a.country_code",
            "rt.was_collected",
            "rt.ordered_timestamp",
            "rt.collected_timestamp",
            "rt.arrival_time",
            "rt.completion_time",
            "rt.expected_completion_time",
            "rt.transaction_type",
            "rt.credit",
            "rt.no_show_discount",
            "rt.final_amount",
            "rt.is_archived",
            "rt.status",
            "rt.created_date",
            "rt.modified_by",
            "rt.modified_date",
        ],
        joins=[
            ("INNER", "restaurant_info", "r", "rt.restaurant_id = r.restaurant_id"),
            ("LEFT", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("LEFT", "institution_entity_info", "ie", "r.institution_entity_id = ie.institution_entity_id"),
            ("LEFT", "address_info", "a", "r.address_id = a.address_id"),
            ("LEFT", "market_info", "m", "a.country_code = m.country_code"),
            ("LEFT", "plate_selection_info", "ps", "rt.plate_selection_id = ps.plate_selection_id"),
            ("LEFT", "plate_info", "pi", "ps.plate_id = pi.plate_id"),
            ("LEFT", "product_info", "pr", "pi.product_id = pr.product_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
        page=page,
        page_size=page_size,
    )


def get_enriched_restaurant_transaction_by_id(
    db: psycopg2.extensions.connection,
    transaction_id: UUID,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> RestaurantTransactionEnrichedResponseSchema | None:
    """
    Get a single restaurant transaction by ID with enriched data (institution name, entity name, restaurant name, plate name, currency code, country).

    **Note: This is a read-only endpoint. Restaurant transactions are automatically managed by the backend
    through plate selection, QR code scanning, and billing operations. They cannot be created or modified via API.**

    Scoping rules:
    - If scope is global (Internal): Returns any restaurant transaction
    - If scope is institution-scoped (Supplier): Returns transaction only if restaurant belongs to their institution

    Args:
        db: Database connection
        transaction_id: Transaction ID
        scope: Optional institution scope for filtering (for Internal/Suppliers)
        include_archived: Whether to include archived records (default: False)

    Returns:
        RestaurantTransactionEnrichedResponseSchema with institution, entity, restaurant, plate, and address information, or None if not found

    Raises:
        HTTPException: For system errors or database failures
    """
    return _restaurant_transaction_enriched_service.get_enriched_by_id(
        db,
        transaction_id,
        select_fields=[
            "rt.transaction_id",
            "rt.restaurant_id",
            "r.institution_id",
            "COALESCE(i.name, '') as institution_name",
            "r.institution_entity_id",
            "COALESCE(ie.name, '') as institution_entity_name",
            "COALESCE(r.name, '') as restaurant_name",
            "rt.plate_selection_id",
            "COALESCE(pr.name, '') as plate_name",
            "rt.discretionary_id",
            "rt.currency_metadata_id",
            "rt.currency_code",
            "gc_country.name as country_name",
            "a.country_code",
            "rt.was_collected",
            "rt.ordered_timestamp",
            "rt.collected_timestamp",
            "rt.arrival_time",
            "rt.completion_time",
            "rt.expected_completion_time",
            "rt.transaction_type",
            "rt.credit",
            "rt.no_show_discount",
            "rt.final_amount",
            "rt.is_archived",
            "rt.status",
            "rt.created_date",
            "rt.modified_by",
            "rt.modified_date",
        ],
        joins=[
            ("INNER", "restaurant_info", "r", "rt.restaurant_id = r.restaurant_id"),
            ("LEFT", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("LEFT", "institution_entity_info", "ie", "r.institution_entity_id = ie.institution_entity_id"),
            ("LEFT", "address_info", "a", "r.address_id = a.address_id"),
            ("LEFT", "market_info", "m", "a.country_code = m.country_code"),
            ("LEFT", "plate_selection_info", "ps", "rt.plate_selection_id = ps.plate_selection_id"),
            ("LEFT", "plate_info", "pi", "ps.plate_id = pi.plate_id"),
            ("LEFT", "product_info", "pr", "pi.product_id = pr.product_id"),
            ("LEFT", "external.geonames_country", "gc_country", "gc_country.iso_alpha2 = m.country_code"),
        ],
        scope=scope,
        include_archived=include_archived,
    )


# =============================================================================
# PLATE PICKUP ENRICHED BUSINESS LOGIC
# =============================================================================


def get_enriched_plate_pickups(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    user_id: UUID | None = None,
    include_archived: bool = False,
    completed_only: bool = False,
    additional_conditions: list[tuple[str, list]] | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[PlatePickupEnrichedResponseSchema]:
    """
    Get all plate pickups with enriched data (restaurant name, address details, product name, credit).
    Returns an array of enriched plate pickup records.

    Scoping rules:
    - If scope is global (Internal): Returns all plate pickups
    - If scope is institution-scoped (Supplier): Returns plate pickups for restaurants in their institution
    - If user_id is provided (Customer): Returns only plate pickups for that specific user

    Args:
        db: Database connection
        scope: Optional institution scope for filtering (for Internal/Suppliers)
        user_id: Optional user ID for user-level filtering (for Customers)
        include_archived: Whether to include archived records (default: False)
        additional_conditions: Optional extra (condition, param_list) tuples from the filter
            registry (e.g. status, market_id, window_from, window_to).

    Returns:
        List of PlatePickupEnrichedResponseSchema with restaurant, address, product, and credit information

    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        conditions = []
        params: list[Any] = []

        # Apply user-level filtering (for Customers)
        if user_id is not None:
            user_id_str = str(user_id) if isinstance(user_id, UUID) else user_id
            conditions.append("ppl.user_id = %s::uuid")
            params.append(user_id_str)

        # Apply institution scoping (for Suppliers - filter by restaurant's institution)
        if scope and not scope.is_global and scope.institution_id:
            conditions.append("r.institution_id = %s::uuid")
            params.append(str(scope.institution_id))

        # Filter by archived status
        if not include_archived:
            conditions.append("ppl.is_archived = FALSE")

        # For Customers: filter to completed pickups only (order history page)
        if completed_only and user_id is not None:
            conditions.append("ppl.was_collected = TRUE")

        # Apply registry-based filter conditions (e.g. status, market_id, window_from, window_to)
        if additional_conditions:
            for condition, param_list in additional_conditions:
                conditions.append(condition)
                if param_list is not None:
                    params.extend(param_list)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        joins_fragment = """
            FROM plate_pickup_live ppl
            LEFT JOIN restaurant_info r ON ppl.restaurant_id = r.restaurant_id
            LEFT JOIN address_info a ON r.address_id = a.address_id
            LEFT JOIN market_info m ON a.country_code = m.country_code
            LEFT JOIN external.geonames_country gc_country ON gc_country.iso_alpha2 = m.country_code
            LEFT JOIN product_info prod ON ppl.product_id = prod.product_id
            LEFT JOIN plate_info p ON ppl.plate_id = p.plate_id"""

        # Convert all params to strings to avoid UUID issues
        safe_params = tuple(str(p) if isinstance(p, UUID) else p for p in params)

        # Count query for X-Total-Count header support.
        count_query = f"SELECT COUNT(*) AS total {joins_fragment} {where_clause}"
        count_row = db_read(count_query, safe_params, connection=db, fetch_one=True)
        total_count: int = count_row["total"] if count_row else 0

        paginate = page is not None and page_size is not None
        limit_clause = ""
        offset_clause = ""
        if paginate:
            assert page is not None and page_size is not None  # narrowed by `paginate` guard above
            clamped_page_size = max(1, min(page_size, 100))
            clamped_offset = (page - 1) * clamped_page_size
            limit_clause = f" LIMIT {clamped_page_size}"
            offset_clause = f" OFFSET {clamped_offset}"

        query = f"""
            SELECT
                ppl.plate_pickup_id,
                ppl.plate_selection_id,
                ppl.user_id,
                ppl.restaurant_id,
                COALESCE(r.name, '') as restaurant_name,
                gc_country.name as country_name,
                a.country_code,
                a.street_type,
                a.street_name,
                a.building_number,
                COALESCE(a.province, '') as province,
                COALESCE(a.city, '') as city,
                COALESCE(a.postal_code, '') as postal_code,
                ppl.plate_id,
                ppl.product_id,
                COALESCE(prod.name, '') as product_name,
                COALESCE(p.credit, 0) as credit,
                ppl.qr_code_id,
                ppl.qr_code_payload,
                ppl.is_archived,
                ppl.status,
                COALESCE(ppl.was_collected, FALSE) as was_collected,
                ppl.arrival_time,
                ppl.completion_time,
                ppl.expected_completion_time,
                ppl.confirmation_code,
                ppl.created_date,
                ppl.modified_by,
                ppl.modified_date
            {joins_fragment}
            {where_clause}
            ORDER BY ppl.plate_pickup_id DESC{limit_clause}{offset_clause}
        """

        results = db_read(query, safe_params, connection=db, fetch_one=False)

        if not results:
            from app.utils.pagination import PaginatedList  # noqa: PLC0415

            return PaginatedList([], total_count=total_count) if paginate else []

        enriched_pickups = []
        for row in results:
            try:
                # Convert UUID objects and other types to Pydantic-compatible formats
                row_dict = {}
                for key, value in row.items():
                    if value is None:
                        row_dict[key] = value
                    elif isinstance(value, UUID):
                        row_dict[key] = str(value)
                    elif isinstance(value, datetime):
                        # Keep datetime objects as-is (Pydantic handles them)
                        row_dict[key] = value
                    else:
                        row_dict[key] = value
                row_dict["country"] = row.get("country_name", "")
                row_dict["address_display"] = format_street_display(
                    row.get("country_code") or "",
                    row.get("street_type"),
                    row.get("street_name"),
                    row.get("building_number"),
                )
                enriched_pickups.append(PlatePickupEnrichedResponseSchema(**row_dict))
            except Exception as schema_error:
                log_error(f"Error parsing plate pickup row for user {user_id}: {schema_error}. Row data: {row}")
                # Skip invalid rows instead of failing completely
                continue

        from app.utils.pagination import PaginatedList  # noqa: PLC0415

        return PaginatedList(enriched_pickups, total_count=total_count) if paginate else enriched_pickups
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        error_trace = traceback.format_exc()
        # Safely convert exception to string, handling UUID objects and other types
        try:
            error_msg = str(e)
        except Exception:
            try:
                error_msg = repr(e)
            except Exception:
                error_msg = f"Error converting exception to string: {type(e).__name__}"
        log_error(
            f"Error getting enriched plate pickups for user {user_id}: {error_msg}\nFull traceback:\n{error_trace}"
        )
        raise HTTPException(status_code=500, detail=f"Failed to get enriched plate pickups: {error_msg}") from None


# =============================================================================
# PLATE KITCHEN DAYS ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for plate kitchen days
# Institution scoping is via: plate_kitchen_days -> plate_info -> restaurant_info -> institution_id
_plate_kitchen_day_enriched_service = EnrichedService(
    base_table="plate_kitchen_days",
    table_alias="pkd",
    id_column="plate_kitchen_day_id",
    schema_class=PlateKitchenDayEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="r",  # institution_id is on the joined restaurant_info table
)


def get_enriched_plate_kitchen_days(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    institution_id: UUID | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[PlateKitchenDayEnrichedResponseSchema]:
    """
    Get all plate kitchen days with enriched data (institution name, restaurant name, plate name, dietary).

    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)
        institution_id: Optional institution ID to filter results (B2B Internal dropdown scoping; filters via restaurant)

    Returns:
        List of PlateKitchenDayEnrichedResponseSchema with enriched data

    Raises:
        HTTPException: For system errors or database failures
    """
    additional_conditions: list[tuple[str, list]] = []
    if institution_id is not None:
        additional_conditions.append(("r.institution_id = %s", [institution_id]))
    return _plate_kitchen_day_enriched_service.get_enriched(
        db,
        select_fields=[
            "pkd.plate_kitchen_day_id",
            "pkd.plate_id",
            "pkd.kitchen_day",
            "pkd.status",
            "COALESCE(i.name, '') as institution_name",
            "COALESCE(r.name, '') as restaurant_name",
            "COALESCE(pr.name, '') as plate_name",  # Product name is the "plate name"
            "pr.dietary",
            "pkd.is_archived",
            "pkd.created_date",
            "pkd.modified_by",
            "pkd.modified_date",
        ],
        joins=[
            ("INNER", "plate_info", "p", "pkd.plate_id = p.plate_id"),
            ("INNER", "restaurant_info", "r", "p.restaurant_id = r.restaurant_id"),
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("INNER", "product_info", "pr", "p.product_id = pr.product_id"),
        ],
        scope=scope,
        include_archived=include_archived,
        additional_conditions=additional_conditions if additional_conditions else None,
        page=page,
        page_size=page_size,
    )


def get_enriched_plate_kitchen_day_by_id(
    kitchen_day_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> PlateKitchenDayEnrichedResponseSchema | None:
    """
    Get a single plate kitchen day by ID with enriched data (institution name, restaurant name, plate name, dietary).

    Args:
        kitchen_day_id: Plate kitchen day ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)

    Returns:
        PlateKitchenDayEnrichedResponseSchema with enriched data, or None if not found

    Raises:
        HTTPException: For system errors or database failures
    """
    return _plate_kitchen_day_enriched_service.get_enriched_by_id(
        kitchen_day_id,
        db,
        select_fields=[
            "pkd.plate_kitchen_day_id",
            "pkd.plate_id",
            "pkd.kitchen_day",
            "pkd.status",
            "COALESCE(i.name, '') as institution_name",
            "COALESCE(r.name, '') as restaurant_name",
            "COALESCE(pr.name, '') as plate_name",  # Product name is the "plate name"
            "pr.dietary",
            "pkd.is_archived",
            "pkd.created_date",
            "pkd.modified_by",
            "pkd.modified_date",
        ],
        joins=[
            ("INNER", "plate_info", "p", "pkd.plate_id = p.plate_id"),
            ("INNER", "restaurant_info", "r", "p.restaurant_id = r.restaurant_id"),
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("INNER", "product_info", "pr", "p.product_id = pr.product_id"),
        ],
        scope=scope,
        include_archived=include_archived,
    )


# RESTAURANT HOLIDAYS ENRICHED BUSINESS LOGIC
def get_enriched_restaurant_holidays(
    restaurant_id: UUID | None = None,
    db: psycopg2.extensions.connection = None,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> list[RestaurantHolidayEnrichedResponseSchema]:
    """
    Get enriched restaurant holidays that includes both restaurant-specific holidays
    and applicable national holidays.

    This endpoint allows restaurant people (Suppliers) to see national holidays
    that apply to their restaurants without direct access to the employee-only
    national holidays API.

    Args:
        restaurant_id: Optional restaurant ID to filter by (if None, returns holidays for all accessible restaurants)
        db: Database connection
        scope: Optional institution scope for filtering (Suppliers see their restaurants, Internal see all)
        include_archived: Whether to include archived records (default: False)

    Returns:
        List of RestaurantHolidayEnrichedResponseSchema with both restaurant and national holidays

    Raises:
        HTTPException: For system errors or database failures
    """

    try:
        enriched_holidays = []

        # Step 1: Get restaurant holidays
        # Build query for restaurant holidays with scoping
        restaurant_conditions = []
        restaurant_params = []

        if not include_archived:
            restaurant_conditions.append("rh.is_archived = FALSE")

        if restaurant_id:
            restaurant_conditions.append("rh.restaurant_id = %s")
            restaurant_params.append(str(restaurant_id))

        # Add institution scoping if needed
        if scope and not scope.is_global:
            restaurant_conditions.append("r.institution_id = %s")
            restaurant_params.append(str(scope.institution_id))

        restaurant_where = " WHERE " + " AND ".join(restaurant_conditions) if restaurant_conditions else ""

        restaurant_query = f"""
            SELECT
                rh.holiday_id,
                rh.restaurant_id,
                r.name as restaurant_name,
                i.name as institution_name,
                rh.country_code,
                rh.holiday_date,
                rh.holiday_name,
                rh.is_recurring,
                rh.recurring_month,
                rh.recurring_day,
                rh.source,
                rh.status,
                rh.is_archived,
                rh.created_date,
                rh.modified_by,
                rh.modified_date
            FROM restaurant_holidays rh
            INNER JOIN restaurant_info r ON rh.restaurant_id = r.restaurant_id
            INNER JOIN institution_info i ON r.institution_id = i.institution_id
            {restaurant_where}
            ORDER BY rh.holiday_date DESC
        """

        restaurant_holidays = db_read(
            restaurant_query, tuple(restaurant_params) if restaurant_params else None, connection=db
        )

        # Convert restaurant holidays to enriched schema
        for row in restaurant_holidays or []:
            enriched_holidays.append(
                RestaurantHolidayEnrichedResponseSchema(
                    holiday_type="restaurant",
                    holiday_id=UUID(row.get("holiday_id")),
                    restaurant_id=UUID(row.get("restaurant_id")),
                    restaurant_name=row.get("restaurant_name"),
                    institution_name=row.get("institution_name"),
                    country_code=row.get("country_code"),
                    holiday_date=row.get("holiday_date"),
                    holiday_name=row.get("holiday_name"),
                    is_recurring=row.get("is_recurring", False),
                    recurring_month=row.get("recurring_month"),
                    recurring_day=row.get("recurring_day"),
                    source=row.get("source"),
                    status=row.get("status", Status.ACTIVE.value),
                    is_archived=row.get("is_archived", False),
                    created_date=row.get("created_date"),
                    modified_by=UUID(row.get("modified_by")) if row.get("modified_by") else None,
                    modified_date=row.get("modified_date"),
                    is_editable=True,
                )
            )

        # Step 2: Get national holidays for restaurants the user has access to
        # First, get list of restaurants and their country codes
        restaurant_conditions_national = []
        restaurant_params_national = []

        if restaurant_id:
            restaurant_conditions_national.append("r.restaurant_id = %s")
            restaurant_params_national.append(str(restaurant_id))

        # Add institution scoping if needed
        if scope and not scope.is_global:
            restaurant_conditions_national.append("r.institution_id = %s")
            restaurant_params_national.append(str(scope.institution_id))

        restaurant_where_national = (
            " WHERE " + " AND ".join(restaurant_conditions_national) if restaurant_conditions_national else ""
        )

        # Get restaurants with their addresses to determine country codes
        restaurants_query = f"""
            SELECT DISTINCT
                r.restaurant_id,
                a.country_code
            FROM restaurant_info r
            INNER JOIN address_info a ON r.address_id = a.address_id
            {restaurant_where_national}
        """

        restaurants = db_read(
            restaurants_query, tuple(restaurant_params_national) if restaurant_params_national else None, connection=db
        )

        # Collect unique country codes
        country_codes = set()
        for restaurant_row in restaurants or []:
            country_code = restaurant_row.get("country_code")
            if country_code:
                country_codes.add(country_code)

        # Get national holidays for these country codes
        if country_codes:
            national_conditions = ["nh.is_archived = FALSE"]
            national_params = []

            # Build IN clause for country codes
            placeholders = ",".join(["%s"] * len(country_codes))
            national_conditions.append(f"nh.country_code IN ({placeholders})")
            national_params.extend(list(country_codes))

            national_where = " WHERE " + " AND ".join(national_conditions)

            national_query = f"""
                SELECT
                    nh.country_code,
                    nh.holiday_name,
                    nh.holiday_date,
                    nh.is_recurring,
                    nh.recurring_month,
                    nh.recurring_day,
                    nh.source,
                    nh.status
                FROM national_holidays nh
                {national_where}
                ORDER BY nh.holiday_date DESC
            """

            national_holidays = db_read(national_query, tuple(national_params), connection=db)

            # Convert national holidays to enriched schema
            for row in national_holidays or []:
                enriched_holidays.append(
                    RestaurantHolidayEnrichedResponseSchema(
                        holiday_type="national",
                        country_code=row.get("country_code"),
                        holiday_name=row.get("holiday_name"),
                        holiday_date=row.get("holiday_date"),
                        is_recurring=row.get("is_recurring", False),
                        recurring_month=row.get("recurring_month"),
                        recurring_day=row.get("recurring_day"),
                        source=row.get("source"),
                        holiday_id=None,
                        restaurant_id=None,
                        restaurant_name=None,
                        institution_name=None,
                        status=row.get("status", Status.ACTIVE.value),
                        is_archived=False,
                        created_date=None,
                        modified_by=None,
                        modified_date=None,
                        is_editable=False,
                    )
                )

        # Sort all holidays by date (most recent first)
        enriched_holidays.sort(key=lambda x: x.holiday_date, reverse=True)

        return enriched_holidays

    except Exception as e:
        log_error(f"Error getting enriched restaurant holidays: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve enriched restaurant holidays: {str(e)}"
        ) from None


def get_enriched_restaurant_holidays_by_restaurant(
    restaurant_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> list[RestaurantHolidayEnrichedResponseSchema]:
    """
    Get enriched restaurant holidays for a specific restaurant.

    Convenience wrapper around get_enriched_restaurant_holidays with restaurant_id filter.

    Args:
        restaurant_id: Restaurant ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)

    Returns:
        List of RestaurantHolidayEnrichedResponseSchema for the specified restaurant
    """
    return get_enriched_restaurant_holidays(
        restaurant_id=restaurant_id, db=db, scope=scope, include_archived=include_archived
    )


# =============================================================================
# PAYMENT METHOD ENRICHED SERVICES
# =============================================================================

# Initialize EnrichedService instance for payment methods
_payment_method_enriched_service = EnrichedService(
    base_table="payment_method",
    table_alias="pm",
    id_column="payment_method_id",
    schema_class=PaymentMethodEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="u",  # institution_id is on the joined user_info table
)


def get_enriched_payment_methods(
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
    user_id: UUID | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[PaymentMethodEnrichedResponseSchema]:
    """
    Get all payment methods with enriched data (user information).
    Includes: user_full_name, user_username, user_email, user_mobile_number.
    Uses SQL JOINs to avoid N+1 queries.

    Args:
        db: Database connection
        scope: Optional institution scope for filtering (not typically used for payment methods)
        include_archived: Whether to include archived records
        user_id: Optional user_id to filter payment methods by user

    Returns:
        List of enriched payment method schemas with user information
    """
    additional_conditions = []
    if user_id:
        additional_conditions.append(("pm.user_id = %s::uuid", [str(user_id)]))

    return _payment_method_enriched_service.get_enriched(
        db,
        select_fields=[
            "pm.payment_method_id",
            "pm.user_id",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as full_name",
            "u.username",
            "u.email",
            "u.mobile_number",
            "pm.method_type",
            "pm.method_type_id",
            "pm.address_id",
            "pm.is_archived",
            "pm.status",
            "pm.is_default",
            "pm.created_date",
            "pm.modified_by",
            "pm.modified_date",
            "epm.provider",
            "epm.last4",
            "epm.brand",
        ],
        joins=[
            ("INNER", "user_info", "u", "pm.user_id = u.user_id"),
            ("LEFT", "external_payment_method", "epm", "pm.payment_method_id = epm.payment_method_id"),
        ],
        scope=scope,
        include_archived=include_archived,
        additional_conditions=additional_conditions if additional_conditions else None,
        page=page,
        page_size=page_size,
    )


def get_enriched_payment_method_by_id(
    payment_method_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: InstitutionScope | None = None,
    include_archived: bool = False,
) -> PaymentMethodEnrichedResponseSchema | None:
    """
    Get a single payment method by ID with enriched data (user information).
    Includes: user_full_name, user_username, user_email, user_mobile_number.
    Uses SQL JOINs to avoid N+1 queries.

    Args:
        payment_method_id: Payment method ID
        db: Database connection
        scope: Optional institution scope for filtering (not typically used for payment methods)
        include_archived: Whether to include archived records

    Returns:
        Enriched payment method schema with user information, or None if not found
    """
    return _payment_method_enriched_service.get_enriched_by_id(
        payment_method_id,
        db,
        select_fields=[
            "pm.payment_method_id",
            "pm.user_id",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as full_name",
            "u.username",
            "u.email",
            "u.mobile_number",
            "pm.method_type",
            "pm.method_type_id",
            "pm.address_id",
            "pm.is_archived",
            "pm.status",
            "pm.is_default",
            "pm.created_date",
            "pm.modified_by",
            "pm.modified_date",
            "epm.provider",
            "epm.last4",
            "epm.brand",
        ],
        joins=[
            ("INNER", "user_info", "u", "pm.user_id = u.user_id"),
            ("LEFT", "external_payment_method", "epm", "pm.payment_method_id = epm.payment_method_id"),
        ],
        scope=scope,
        include_archived=include_archived,
    )


# ---------------------------------------------------------------------------
# Archive guardrails
# ---------------------------------------------------------------------------


def validate_entity_can_be_archived(entity_id: UUID, db: psycopg2.extensions.connection) -> None:
    """Raise HTTPException if entity has active dependencies that prevent archival.

    Checks (in order):
    1. Active plate pickups via entity's restaurants
    2. Active restaurants
    """
    from fastapi import HTTPException

    active_pickups = db_read(
        """
        SELECT COUNT(*) as cnt
        FROM customer.plate_pickup_live pp
        JOIN ops.restaurant_info r ON pp.restaurant_id = r.restaurant_id
        WHERE r.institution_entity_id = %s
          AND pp.is_archived = FALSE
          AND pp.status IN ('pending', 'active')
        """,
        (str(entity_id),),
        connection=db,
        fetch_one=True,
    )
    if active_pickups and active_pickups["cnt"] > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot archive entity: {active_pickups['cnt']} active plate pickup(s) exist. Complete or cancel them first.",
        )

    active_restaurants = db_read(
        """
        SELECT r.name FROM ops.restaurant_info r
        WHERE r.institution_entity_id = %s AND r.is_archived = FALSE
        """,
        (str(entity_id),),
        connection=db,
    )
    if active_restaurants:
        names = [r["name"] for r in active_restaurants]
        raise HTTPException(
            status_code=409,
            detail=f"Cannot archive entity: {len(names)} active restaurant(s) must be archived first: {', '.join(names)}",
        )


def validate_restaurant_can_be_archived(restaurant_id: UUID, db: psycopg2.extensions.connection) -> None:
    """Raise HTTPException if restaurant has active plate pickups that prevent archival."""
    from fastapi import HTTPException

    active_pickups: dict[str, Any] | None = cast(
        dict[str, Any] | None,
        db_read(
            """
        SELECT COUNT(*) as cnt
        FROM customer.plate_pickup_live pp
        WHERE pp.restaurant_id = %s
          AND pp.is_archived = FALSE
          AND pp.status IN ('pending', 'active')
        """,
            (str(restaurant_id),),
            connection=db,
            fetch_one=True,
        ),
    )
    if active_pickups and active_pickups["cnt"] > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot archive restaurant: {active_pickups['cnt']} active plate pickup(s) exist. Complete or cancel them first.",
        )
