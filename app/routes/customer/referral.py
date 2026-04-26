# app/routes/customer/referral.py
"""
Customer Referral Routes

User-facing endpoints for viewing referral code, listing referrals, and stats.
Public endpoints for pre-auth referral code assignment (deep link lifecycle).
"""

from decimal import Decimal

import psycopg2.extensions
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.config.enums import ReferralStatus
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import (
    ReferralInfoResponseSchema,
    ReferralMyCodeResponseSchema,
    ReferralStatsResponseSchema,
)
from app.utils.db import db_read
from app.utils.log import log_info
from app.utils.rate_limit import limiter

router = APIRouter(
    prefix="/referrals",
    tags=["Referrals"],
)


# =============================================================================
# Public endpoints (no auth) — pre-auth referral code assignment
# =============================================================================


class AssignCodeRequest(BaseModel):
    referral_code: str = Field(..., max_length=20)
    device_id: str = Field(..., max_length=255)


class AssignCodeResponse(BaseModel):
    success: bool
    referral_code: str


class AssignedCodeResponse(BaseModel):
    referral_code: str


@router.post("/assign-code", response_model=AssignCodeResponse)
@limiter.limit("10/minute")
def assign_referral_code(
    request: Request,
    body: AssignCodeRequest,
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Associate a referral code with a device fingerprint (public, no auth).
    Called when a user taps a referral deep link before signing up.
    Replaces any existing assignment for the same device.
    """
    from app.services.referral_service import validate_referral_code

    referrer = validate_referral_code(body.referral_code, db)
    if not referrer:
        raise envelope_exception(ErrorCode.REFERRAL_CODE_INVALID, status=400, locale="en")

    cursor = db.cursor()
    try:
        # Replace any existing active assignment for this device
        cursor.execute(
            "DELETE FROM referral_code_assignment WHERE device_id = %s AND used = FALSE",
            (body.device_id,),
        )
        cursor.execute(
            """
            INSERT INTO referral_code_assignment (device_id, referral_code)
            VALUES (%s, %s)
            """,
            (body.device_id, body.referral_code),
        )
        db.commit()
    finally:
        cursor.close()

    log_info(f"Referral code {body.referral_code} assigned to device {body.device_id[:8]}...")
    return {"success": True, "referral_code": body.referral_code}


@router.get("/assigned-code", response_model=AssignedCodeResponse)
@limiter.limit("20/minute")
def get_assigned_code(
    request: Request,
    device_id: str = Query(..., max_length=255),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Check if a device has an active (non-expired, non-used) referral code assignment.
    Assignments expire after 48 hours.
    """
    rows = db_read(
        """
        SELECT referral_code
        FROM referral_code_assignment
        WHERE device_id = %s AND used = FALSE
          AND created_at > (CURRENT_TIMESTAMP - INTERVAL '48 hours')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (device_id,),
        connection=db,
    )
    if not rows:
        raise envelope_exception(ErrorCode.REFERRAL_ASSIGNMENT_NOT_FOUND, status=404, locale="en")
    return {"referral_code": rows[0]["referral_code"]}


# =============================================================================
# Authenticated endpoints — referral code, activity, stats
# =============================================================================


@router.get("/my-code", response_model=ReferralMyCodeResponseSchema)
def get_my_referral_code(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Return the current user's referral code."""
    user_id = current_user["user_id"]
    rows = db_read(
        "SELECT referral_code FROM user_info WHERE user_id = %s::uuid",
        (str(user_id),),
        connection=db,
    )
    if not rows or not rows[0].get("referral_code"):
        raise envelope_exception(ErrorCode.REFERRAL_CODE_NOT_FOUND, status=404, locale="en")
    return {"referral_code": rows[0]["referral_code"]}


@router.get("/my-referrals", response_model=list[ReferralInfoResponseSchema])
def get_my_referrals(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List referrals made by the current user (as referrer)."""
    user_id = current_user["user_id"]
    rows = db_read(
        """
        SELECT referral_id, referrer_user_id, referee_user_id, referral_code_used,
               market_id, referral_status, bonus_credits_awarded, bonus_plan_price,
               bonus_rate_applied, qualified_date, rewarded_date,
               is_archived, status, created_date
        FROM referral_info
        WHERE referrer_user_id = %s::uuid AND is_archived = FALSE
        ORDER BY created_date DESC
        """,
        (str(user_id),),
        connection=db,
    )
    return rows or []


@router.get("/stats", response_model=ReferralStatsResponseSchema)
def get_referral_stats(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Summary stats: total referrals, credits earned, pending count."""
    user_id = current_user["user_id"]
    rows = db_read(
        """
        SELECT
            COUNT(*) AS total_referrals,
            COALESCE(SUM(CASE WHEN referral_status = %s THEN bonus_credits_awarded ELSE 0 END), 0) AS total_credits_earned,
            COUNT(*) FILTER (WHERE referral_status IN (%s, %s)) AS pending_count
        FROM referral_info
        WHERE referrer_user_id = %s::uuid AND is_archived = FALSE
        """,
        (
            ReferralStatus.REWARDED.value,
            ReferralStatus.PENDING.value,
            ReferralStatus.QUALIFIED.value,
            str(user_id),
        ),
        connection=db,
    )
    if rows:
        return {
            "total_referrals": int(rows[0]["total_referrals"]),
            "total_credits_earned": Decimal(str(rows[0]["total_credits_earned"])),
            "pending_count": int(rows[0]["pending_count"]),
        }
    return {"total_referrals": 0, "total_credits_earned": Decimal("0"), "pending_count": 0}
