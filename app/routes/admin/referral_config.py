# app/routes/admin/referral_config.py
"""
Admin Referral Configuration Routes

Routes for internal administrators to manage referral program configuration per market
and trigger the referral cron job.
"""

from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends

from app.auth.dependencies import get_employee_user, get_resolved_locale
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import (
    ReferralConfigEnrichedResponseSchema,
    ReferralConfigResponseSchema,
    ReferralConfigUpdateSchema,
)
from app.services.crud_service import referral_config_service
from app.utils.db import db_read
from app.utils.log import log_info

router = APIRouter(
    prefix="/admin/referral-config",
    tags=["Admin Referral Config"],
)


@router.get("", response_model=list[ReferralConfigResponseSchema])
def list_referral_configs(
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List all referral configurations (one per market)."""
    configs = referral_config_service.get_all(db, include_archived=False)
    return configs


@router.get("/enriched", response_model=list[ReferralConfigEnrichedResponseSchema])
def list_referral_configs_enriched(
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List all referral configurations with market name and country code."""
    rows = db_read(
        """
        SELECT rc.referral_config_id, rc.market_id,
               gc.name AS market_name, m.country_code,
               rc.is_enabled, rc.referrer_bonus_rate, rc.referrer_bonus_cap,
               rc.referrer_monthly_cap, rc.min_plan_price_to_qualify,
               rc.cooldown_days, rc.held_reward_expiry_hours, rc.pending_expiry_days,
               rc.is_archived, rc.status, rc.created_date, rc.modified_date
        FROM referral_config rc
        JOIN market_info m ON rc.market_id = m.market_id
        LEFT JOIN external.geonames_country gc ON gc.iso_alpha2 = m.country_code
        WHERE rc.is_archived = FALSE
        ORDER BY gc.name
        """,
        connection=db,
    )
    return rows or []


@router.get("/{market_id}", response_model=ReferralConfigResponseSchema)
def get_referral_config_by_market(
    market_id: UUID,
    current_user: dict = Depends(get_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get referral configuration for a specific market."""
    rows = db_read(
        "SELECT * FROM referral_config WHERE market_id = %s AND is_archived = FALSE",
        (str(market_id),),
        connection=db,
    )
    if not rows:
        raise envelope_exception(ErrorCode.REFERRAL_CONFIG_NOT_FOUND, status=404, locale=locale)
    return rows[0]


@router.put("/{market_id}", response_model=ReferralConfigResponseSchema)
def update_referral_config(
    market_id: UUID,
    update: ReferralConfigUpdateSchema,
    current_user: dict = Depends(get_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Update referral configuration for a market."""
    rows = db_read(
        "SELECT referral_config_id FROM referral_config WHERE market_id = %s AND is_archived = FALSE",
        (str(market_id),),
        connection=db,
    )
    if not rows:
        raise envelope_exception(ErrorCode.REFERRAL_CONFIG_NOT_FOUND, status=404, locale=locale)

    config_id = UUID(str(rows[0]["referral_config_id"]))
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    update_data["modified_by"] = current_user["user_id"]

    log_info(f"Admin {current_user['user_id']} updating referral config for market {market_id}")
    updated = referral_config_service.update(config_id, update_data, db)
    if not updated:
        raise envelope_exception(ErrorCode.ENTITY_UPDATE_FAILED, status=500, locale=locale, entity="Referral config")
    return updated


@router.post("/run-cron", status_code=200)
def run_referral_cron_endpoint(
    current_user: dict = Depends(get_employee_user),
):
    """Run the referral cron job. Internal only."""
    from app.services.cron.referral_cron import run_referral_cron

    result = run_referral_cron()
    return result
