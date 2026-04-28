"""
Onboarding status service — computes supplier/employer onboarding checklist,
completion percentage, next step, and aggregated admin summary.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg2.extensions

from app.utils.db import db_read
from app.utils.log import log_warning

# =========================================================================
# Supplier checklist
# =========================================================================

SUPPLIER_CHECKLIST_ORDER = [
    "has_active_address",
    "has_active_entity_with_payouts",
    "has_active_restaurant",
    "has_active_product",
    "has_active_plate",
    "has_active_kitchen_day",
    "has_active_qr_code",
]

SUPPLIER_NEXT_STEP_LABELS = {
    "has_active_address": "address",
    "has_active_entity_with_payouts": "entity_payout_setup",
    "has_active_restaurant": "restaurant",
    "has_active_product": "product",
    "has_active_plate": "plate",
    "has_active_kitchen_day": "kitchen_day",
    "has_active_qr_code": "qr_code",
}

_SUPPLIER_CHECKLIST_SQL = """
SELECT
    i.created_date,
    EXISTS(
        SELECT 1 FROM core.address_info
        WHERE institution_id = %(iid)s AND status = 'active' AND NOT is_archived
    ) AS has_active_address,
    EXISTS(
        SELECT 1 FROM ops.institution_entity_info
        WHERE institution_id = %(iid)s AND status = 'active' AND NOT is_archived
              AND payout_onboarding_status = 'complete'
    ) AS has_active_entity_with_payouts,
    EXISTS(
        SELECT 1 FROM ops.restaurant_info
        WHERE institution_id = %(iid)s AND status IN ('pending', 'active') AND NOT is_archived
    ) AS has_active_restaurant,
    EXISTS(
        SELECT 1 FROM ops.product_info
        WHERE institution_id = %(iid)s AND status = 'active' AND NOT is_archived
    ) AS has_active_product,
    EXISTS(
        SELECT 1 FROM ops.plate_info p
        JOIN ops.restaurant_info r ON p.restaurant_id = r.restaurant_id
        WHERE r.institution_id = %(iid)s AND p.status = 'active' AND NOT p.is_archived
    ) AS has_active_plate,
    EXISTS(
        SELECT 1 FROM ops.plate_kitchen_days pkd
        JOIN ops.plate_info p ON pkd.plate_id = p.plate_id
        JOIN ops.restaurant_info r ON p.restaurant_id = r.restaurant_id
        WHERE r.institution_id = %(iid)s AND pkd.status = 'active' AND NOT pkd.is_archived
    ) AS has_active_kitchen_day,
    EXISTS(
        SELECT 1 FROM ops.qr_code q
        JOIN ops.restaurant_info r ON q.restaurant_id = r.restaurant_id
        WHERE r.institution_id = %(iid)s AND q.status = 'active' AND NOT q.is_archived
    ) AS has_active_qr_code,
    GREATEST(
        (SELECT MAX(modified_date) FROM core.address_info WHERE institution_id = %(iid)s AND NOT is_archived),
        (SELECT MAX(modified_date) FROM ops.institution_entity_info WHERE institution_id = %(iid)s AND NOT is_archived),
        (SELECT MAX(modified_date) FROM ops.restaurant_info WHERE institution_id = %(iid)s AND NOT is_archived),
        (SELECT MAX(modified_date) FROM ops.product_info WHERE institution_id = %(iid)s AND NOT is_archived),
        (SELECT MAX(p.modified_date) FROM ops.plate_info p JOIN ops.restaurant_info r ON p.restaurant_id = r.restaurant_id WHERE r.institution_id = %(iid)s AND NOT p.is_archived),
        (SELECT MAX(pkd.modified_date) FROM ops.plate_kitchen_days pkd JOIN ops.plate_info p ON pkd.plate_id = p.plate_id JOIN ops.restaurant_info r ON p.restaurant_id = r.restaurant_id WHERE r.institution_id = %(iid)s AND NOT pkd.is_archived),
        (SELECT MAX(q.modified_date) FROM ops.qr_code q JOIN ops.restaurant_info r ON q.restaurant_id = r.restaurant_id WHERE r.institution_id = %(iid)s AND NOT q.is_archived)
    ) AS last_activity_date
FROM core.institution_info i
WHERE i.institution_id = %(iid)s
"""

# =========================================================================
# Employer checklist
# =========================================================================

EMPLOYER_CHECKLIST_ORDER = [
    "has_benefits_program",
    "has_email_domain",
    "has_enrolled_employee",
    "has_active_subscription",
]

EMPLOYER_NEXT_STEP_LABELS = {
    "has_benefits_program": "benefits_program",
    "has_email_domain": "email_domain",
    "has_enrolled_employee": "enroll_employee",
    "has_active_subscription": "employee_subscription",
}

_EMPLOYER_CHECKLIST_SQL = """
SELECT
    i.created_date,
    EXISTS(
        SELECT 1 FROM core.employer_benefits_program
        WHERE institution_id = %(iid)s AND status = 'active' AND NOT is_archived
    ) AS has_benefits_program,
    EXISTS(
        SELECT 1 FROM ops.institution_entity_info
        WHERE institution_id = %(iid)s AND email_domain IS NOT NULL AND is_archived = FALSE
    ) AS has_email_domain,
    EXISTS(
        SELECT 1 FROM core.user_info
        WHERE institution_id = %(iid)s AND role_type = 'customer'
              AND status = 'active' AND NOT is_archived
    ) AS has_enrolled_employee,
    EXISTS(
        SELECT 1 FROM customer.subscription_info s
        JOIN core.user_info u ON s.user_id = u.user_id
        WHERE u.institution_id = %(iid)s
              AND s.subscription_status = 'active' AND NOT s.is_archived
    ) AS has_active_subscription,
    GREATEST(
        (SELECT MAX(modified_date) FROM core.employer_benefits_program WHERE institution_id = %(iid)s AND NOT is_archived),
        (SELECT MAX(modified_date) FROM ops.institution_entity_info WHERE institution_id = %(iid)s AND NOT is_archived),
        (SELECT MAX(modified_date) FROM core.user_info WHERE institution_id = %(iid)s AND role_type = 'customer' AND NOT is_archived),
        (SELECT MAX(modified_date) FROM customer.subscription_info s JOIN core.user_info u ON s.user_id = u.user_id WHERE u.institution_id = %(iid)s AND NOT s.is_archived)
    ) AS last_activity_date
FROM core.institution_info i
WHERE i.institution_id = %(iid)s
"""

# =========================================================================
# Customer checklist (user-level, not institution-level)
# =========================================================================

CUSTOMER_CHECKLIST_ORDER = [
    "has_verified_email",
    "has_active_subscription",
]

CUSTOMER_NEXT_STEP_LABELS = {
    "has_verified_email": "verify_email",
    "has_active_subscription": "subscribe",
}

_CUSTOMER_CHECKLIST_SQL = """
SELECT
    u.created_date,
    u.email_verified AS has_verified_email,
    EXISTS(
        SELECT 1 FROM customer.subscription_info
        WHERE user_id = %(uid)s AND subscription_status = 'active' AND NOT is_archived
    ) AS has_active_subscription,
    GREATEST(
        u.modified_date,
        (SELECT MAX(modified_date) FROM customer.subscription_info WHERE user_id = %(uid)s AND NOT is_archived)
    ) AS last_activity_date
FROM core.user_info u
WHERE u.user_id = %(uid)s
"""

# =========================================================================
# Dispatch helpers
# =========================================================================

_CHECKLIST_CONFIG = {
    "supplier": (_SUPPLIER_CHECKLIST_SQL, SUPPLIER_CHECKLIST_ORDER, SUPPLIER_NEXT_STEP_LABELS),
    "employer": (_EMPLOYER_CHECKLIST_SQL, EMPLOYER_CHECKLIST_ORDER, EMPLOYER_NEXT_STEP_LABELS),
}

# Keep backward-compat aliases used by stall detection cron
NEXT_STEP_LABELS = SUPPLIER_NEXT_STEP_LABELS

STALL_THRESHOLD_DAYS = 7


def _derive_status(checklist_bools: list[bool], days_since_last_activity: int | None) -> str:
    if all(checklist_bools):
        return "complete"
    if not any(checklist_bools):
        return "not_started"
    if days_since_last_activity is not None and days_since_last_activity >= STALL_THRESHOLD_DAYS:
        return "stalled"
    return "in_progress"


def _find_next_step(checklist: dict[str, bool], order: list[str], labels: dict[str, str]) -> str | None:
    for key in order:
        if not checklist.get(key, False):
            return labels[key]
    return None


def _compute_days_since(ref_date: datetime | None) -> int | None:
    if ref_date is None:
        return None
    now = datetime.now(UTC)
    if ref_date.tzinfo is None:
        ref_date = ref_date.replace(tzinfo=UTC)
    return (now - ref_date).days


def _run_checklist(institution_id: UUID, institution_type: str, db) -> dict[str, Any] | None:
    """Run the appropriate checklist query and return parsed result dict, or None."""
    config = _CHECKLIST_CONFIG.get(institution_type)
    if not config:
        return None

    sql, order, labels = config
    iid = str(institution_id)
    row = db_read(sql, {"iid": iid}, connection=db, fetch_one=True)
    if not row:
        return None

    checklist = {key: row[key] for key in order}
    checklist_bools = [checklist[k] for k in order]
    created_date = row["created_date"]
    last_activity_date = row["last_activity_date"]
    days_since_creation = _compute_days_since(created_date) or 0
    days_since_last_activity = _compute_days_since(last_activity_date)
    completion_percentage = round(sum(checklist_bools) / len(order) * 100)

    return {
        "institution_id": institution_id,
        "institution_type": institution_type,
        "onboarding_status": _derive_status(checklist_bools, days_since_last_activity),
        "completion_percentage": completion_percentage,
        "next_step": _find_next_step(checklist, order, labels),
        "days_since_creation": days_since_creation,
        "days_since_last_activity": days_since_last_activity,
        "last_activity_date": last_activity_date,
        "checklist": checklist,
    }


# =========================================================================
# Public API
# =========================================================================


def get_onboarding_status(
    institution_id: UUID,
    institution_type: str,
    db: psycopg2.extensions.connection,
) -> dict[str, Any] | None:
    """Compute full onboarding status for a single institution (Supplier or Employer)."""
    result = _run_checklist(institution_id, institution_type, db)
    if not result:
        log_warning(f"Onboarding status: institution {institution_id} not found or unsupported type {institution_type}")
    return result


def get_onboarding_status_claim(
    institution_id: UUID,
    db: psycopg2.extensions.connection,
) -> str:
    """Lightweight status for JWT claim. Returns not_started, in_progress, or complete (never stalled)."""
    # Look up institution_type
    row = db_read(
        "SELECT institution_type FROM core.institution_info WHERE institution_id = %s",
        (str(institution_id),),
        connection=db,
        fetch_one=True,
    )
    if not row:
        return "not_started"

    institution_type = row["institution_type"]
    config = _CHECKLIST_CONFIG.get(institution_type)
    if not config:
        return "not_started"

    sql, order, _ = config
    checklist_row = db_read(sql, {"iid": str(institution_id)}, connection=db, fetch_one=True)
    if not checklist_row:
        return "not_started"

    bools = [checklist_row[key] for key in order]
    if all(bools):
        return "complete"
    if not any(bools):
        return "not_started"
    return "in_progress"


def get_customer_onboarding_status(
    user_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict[str, Any] | None:
    """Compute onboarding status for a Customer user (user-level, not institution-level)."""
    uid = str(user_id)
    row = db_read(_CUSTOMER_CHECKLIST_SQL, {"uid": uid}, connection=db, fetch_one=True)
    if not row:
        return None

    checklist = {key: row[key] for key in CUSTOMER_CHECKLIST_ORDER}
    checklist_bools = [checklist[k] for k in CUSTOMER_CHECKLIST_ORDER]
    created_date = row["created_date"]
    last_activity_date = row["last_activity_date"]
    days_since_creation = _compute_days_since(created_date) or 0
    days_since_last_activity = _compute_days_since(last_activity_date)
    completion_percentage = round(sum(checklist_bools) / len(CUSTOMER_CHECKLIST_ORDER) * 100)

    return {
        "institution_id": None,
        "institution_type": "customer",
        "onboarding_status": _derive_status(checklist_bools, days_since_last_activity),
        "completion_percentage": completion_percentage,
        "next_step": _find_next_step(checklist, CUSTOMER_CHECKLIST_ORDER, CUSTOMER_NEXT_STEP_LABELS),
        "days_since_creation": days_since_creation,
        "days_since_last_activity": days_since_last_activity,
        "last_activity_date": last_activity_date,
        "checklist": checklist,
    }


def get_customer_onboarding_claim(
    user_id: UUID,
    db: psycopg2.extensions.connection,
) -> str:
    """Lightweight customer onboarding status for JWT claim."""
    uid = str(user_id)
    row = db_read(_CUSTOMER_CHECKLIST_SQL, {"uid": uid}, connection=db, fetch_one=True)
    if not row:
        return "not_started"

    bools = [row[key] for key in CUSTOMER_CHECKLIST_ORDER]
    if all(bools):
        return "complete"
    if not any(bools):
        return "not_started"
    return "in_progress"


_SUMMARY_SQL_TEMPLATE = """
SELECT
    i.institution_id,
    i.name AS institution_name,
    i.created_date,
    m.name AS market_name,
    {checklist_columns}
    {last_activity_subquery}
FROM core.institution_info i
LEFT JOIN core.institution_market im ON i.institution_id = im.institution_id AND im.is_primary = TRUE
LEFT JOIN core.market_info m ON im.market_id = m.market_id
WHERE i.institution_type = %(inst_type)s
  AND i.status = 'active'
  AND NOT i.is_archived
"""

_SUPPLIER_SUMMARY_CHECKLIST = """
    EXISTS(SELECT 1 FROM core.address_info WHERE institution_id = i.institution_id AND status = 'active' AND NOT is_archived) AS has_active_address,
    EXISTS(SELECT 1 FROM ops.institution_entity_info WHERE institution_id = i.institution_id AND status = 'active' AND NOT is_archived AND payout_onboarding_status = 'complete') AS has_active_entity_with_payouts,
    EXISTS(SELECT 1 FROM ops.restaurant_info WHERE institution_id = i.institution_id AND status IN ('pending', 'active') AND NOT is_archived) AS has_active_restaurant,
    EXISTS(SELECT 1 FROM ops.product_info WHERE institution_id = i.institution_id AND status = 'active' AND NOT is_archived) AS has_active_product,
    EXISTS(SELECT 1 FROM ops.plate_info p JOIN ops.restaurant_info r ON p.restaurant_id = r.restaurant_id WHERE r.institution_id = i.institution_id AND p.status = 'active' AND NOT p.is_archived) AS has_active_plate,
    EXISTS(SELECT 1 FROM ops.plate_kitchen_days pkd JOIN ops.plate_info p ON pkd.plate_id = p.plate_id JOIN ops.restaurant_info r ON p.restaurant_id = r.restaurant_id WHERE r.institution_id = i.institution_id AND pkd.status = 'active' AND NOT pkd.is_archived) AS has_active_kitchen_day,
    EXISTS(SELECT 1 FROM ops.qr_code q JOIN ops.restaurant_info r ON q.restaurant_id = r.restaurant_id WHERE r.institution_id = i.institution_id AND q.status = 'active' AND NOT q.is_archived) AS has_active_qr_code,"""

_SUPPLIER_SUMMARY_ACTIVITY = """
    GREATEST(
        (SELECT MAX(modified_date) FROM core.address_info WHERE institution_id = i.institution_id AND NOT is_archived),
        (SELECT MAX(modified_date) FROM ops.institution_entity_info WHERE institution_id = i.institution_id AND NOT is_archived),
        (SELECT MAX(modified_date) FROM ops.restaurant_info WHERE institution_id = i.institution_id AND NOT is_archived),
        (SELECT MAX(modified_date) FROM ops.product_info WHERE institution_id = i.institution_id AND NOT is_archived),
        (SELECT MAX(p.modified_date) FROM ops.plate_info p JOIN ops.restaurant_info r ON p.restaurant_id = r.restaurant_id WHERE r.institution_id = i.institution_id AND NOT p.is_archived),
        (SELECT MAX(pkd.modified_date) FROM ops.plate_kitchen_days pkd JOIN ops.plate_info p ON pkd.plate_id = p.plate_id JOIN ops.restaurant_info r ON p.restaurant_id = r.restaurant_id WHERE r.institution_id = i.institution_id AND NOT pkd.is_archived),
        (SELECT MAX(q.modified_date) FROM ops.qr_code q JOIN ops.restaurant_info r ON q.restaurant_id = r.restaurant_id WHERE r.institution_id = i.institution_id AND NOT q.is_archived)
    ) AS last_activity_date"""

_EMPLOYER_SUMMARY_CHECKLIST = """
    EXISTS(SELECT 1 FROM core.employer_benefits_program WHERE institution_id = i.institution_id AND status = 'active' AND NOT is_archived) AS has_benefits_program,
    EXISTS(SELECT 1 FROM ops.institution_entity_info WHERE institution_id = i.institution_id AND email_domain IS NOT NULL AND NOT is_archived) AS has_email_domain,
    EXISTS(SELECT 1 FROM core.user_info WHERE institution_id = i.institution_id AND role_type = 'customer' AND status = 'active' AND NOT is_archived) AS has_enrolled_employee,
    EXISTS(SELECT 1 FROM customer.subscription_info s JOIN core.user_info u ON s.user_id = u.user_id WHERE u.institution_id = i.institution_id AND s.subscription_status = 'active' AND NOT s.is_archived) AS has_active_subscription,"""

_EMPLOYER_SUMMARY_ACTIVITY = """
    GREATEST(
        (SELECT MAX(modified_date) FROM core.employer_benefits_program WHERE institution_id = i.institution_id AND NOT is_archived),
        (SELECT MAX(modified_date) FROM ops.institution_entity_info WHERE institution_id = i.institution_id AND NOT is_archived),
        (SELECT MAX(modified_date) FROM core.user_info WHERE institution_id = i.institution_id AND role_type = 'customer' AND NOT is_archived),
        (SELECT MAX(modified_date) FROM customer.subscription_info s JOIN core.user_info u ON s.user_id = u.user_id WHERE u.institution_id = i.institution_id AND NOT s.is_archived)
    ) AS last_activity_date"""

_SUMMARY_CONFIG = {
    "supplier": (
        _SUPPLIER_SUMMARY_CHECKLIST,
        _SUPPLIER_SUMMARY_ACTIVITY,
        SUPPLIER_CHECKLIST_ORDER,
        SUPPLIER_NEXT_STEP_LABELS,
    ),
    "employer": (
        _EMPLOYER_SUMMARY_CHECKLIST,
        _EMPLOYER_SUMMARY_ACTIVITY,
        EMPLOYER_CHECKLIST_ORDER,
        EMPLOYER_NEXT_STEP_LABELS,
    ),
}


def get_onboarding_summary(
    db: psycopg2.extensions.connection,
    institution_type: str = "supplier",
    market_id: UUID | None = None,
    onboarding_status_filter: str | None = None,
    stalled_days: int | None = None,
) -> dict[str, Any]:
    """Aggregated onboarding funnel for Internal admin view."""
    config = _SUMMARY_CONFIG.get(institution_type)
    if not config:
        return {"counts": {}, "stalled_institutions": []}

    checklist_cols, activity_sub, order, labels = config
    query = _SUMMARY_SQL_TEMPLATE.format(
        checklist_columns=checklist_cols,
        last_activity_subquery=activity_sub,
    )
    params: dict[str, Any] = {"inst_type": institution_type}

    if market_id:
        query += " AND im.market_id = %(market_id)s"
        params["market_id"] = str(market_id)

    rows = db_read(query, params, connection=db)

    counts = {"not_started": 0, "in_progress": 0, "stalled": 0, "complete": 0}
    stalled_institutions = []

    for row in rows:
        checklist_bools = [row[key] for key in order]
        checklist = {key: row[key] for key in order}

        last_activity_date = row["last_activity_date"]
        days_since_last_activity = _compute_days_since(last_activity_date)
        days_since_creation = _compute_days_since(row["created_date"]) or 0

        inst_status = _derive_status(checklist_bools, days_since_last_activity)
        counts[inst_status] = counts.get(inst_status, 0) + 1

        missing = [labels[k] for k in order if not checklist[k]]

        if inst_status == "stalled":
            effective_stalled_days = stalled_days or STALL_THRESHOLD_DAYS
            if days_since_last_activity is not None and days_since_last_activity >= effective_stalled_days:
                stalled_institutions.append(
                    {
                        "institution_id": row["institution_id"],
                        "institution_name": row["institution_name"],
                        "market_name": row.get("market_name"),
                        "onboarding_status": inst_status,
                        "completion_percentage": round(sum(checklist_bools) / len(order) * 100),
                        "days_since_creation": days_since_creation,
                        "days_since_last_activity": days_since_last_activity,
                        "missing_steps": missing,
                        "created_date": row["created_date"],
                    }
                )

    return {
        "total": sum(counts.values()),
        "counts": counts,
        "stalled_institutions": stalled_institutions,
    }


# =========================================================================
# Regression detection — called after resource archive/deactivation
# =========================================================================

# Tables whose archival can regress onboarding, mapped to how to find institution_id
_ONBOARDING_TABLES = {
    # Supplier tables
    "address_info": "SELECT institution_id FROM core.address_info WHERE address_id = %s",
    "institution_entity_info": "SELECT institution_id FROM ops.institution_entity_info WHERE institution_entity_id = %s",
    "restaurant_info": "SELECT institution_id FROM ops.restaurant_info WHERE restaurant_id = %s",
    "product_info": "SELECT institution_id FROM ops.product_info WHERE product_id = %s",
    "plate_info": "SELECT r.institution_id FROM ops.plate_info p JOIN ops.restaurant_info r ON p.restaurant_id = r.restaurant_id WHERE p.plate_id = %s",
    "plate_kitchen_days": "SELECT r.institution_id FROM ops.plate_kitchen_days pkd JOIN ops.plate_info p ON pkd.plate_id = p.plate_id JOIN ops.restaurant_info r ON p.restaurant_id = r.restaurant_id WHERE pkd.plate_kitchen_day_id = %s",
    "qr_code": "SELECT r.institution_id FROM ops.qr_code q JOIN ops.restaurant_info r ON q.restaurant_id = r.restaurant_id WHERE q.qr_code_id = %s",
    # Employer tables
    "employer_benefits_program": "SELECT institution_id FROM core.employer_benefits_program WHERE program_id = %s",
}


def check_onboarding_regression(
    table_name: str,
    record_id: UUID,
    db: psycopg2.extensions.connection,
) -> None:
    """
    After a resource is archived/deactivated, check if the owning
    institution's onboarding regressed from complete. Logs the event if so.

    Safe to call for any table — silently returns for non-onboarding tables.
    """
    lookup_sql = _ONBOARDING_TABLES.get(table_name)
    if not lookup_sql:
        return

    try:
        row = db_read(lookup_sql, (str(record_id),), connection=db, fetch_one=True)
        if not row:
            return

        institution_id = row["institution_id"]

        # Only check Supplier/Employer institutions
        inst_row = db_read(
            "SELECT institution_type FROM core.institution_info WHERE institution_id = %s AND institution_type IN ('supplier', 'employer')",
            (str(institution_id),),
            connection=db,
            fetch_one=True,
        )
        if not inst_row:
            return

        status = get_onboarding_status_claim(institution_id, db)
        if status != "complete":
            log_warning(
                f"Onboarding regression: institution {institution_id} ({inst_row['institution_type']}) "
                f"is now '{status}' after {table_name} record {record_id} was archived/deactivated"
            )
    except Exception as e:
        # Never let regression detection break the calling operation.
        # IMPORTANT: if the failure was a DB error, the psycopg2 connection is now in
        # "current transaction is aborted" state — any subsequent query on the same
        # request (or on a subsequent request if the connection is pool-reused) will
        # 500. Roll back to clear the aborted state so the caller can proceed.
        log_warning(f"Onboarding regression check failed for {table_name}/{record_id}: {e}")
        try:
            db.rollback()
        except Exception as rollback_err:
            log_warning(f"Failed to rollback after regression check failure: {rollback_err}")
