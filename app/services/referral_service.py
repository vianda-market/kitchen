# app/services/referral_service.py
"""
Referral domain service.

Core business logic for the referral system: code validation, referral creation,
reward calculation, credit issuance, and lifecycle management (held rewards, expiration).
"""

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import psycopg2.extensions

from app.config.enums import ReferralStatus, Status
from app.utils.db import db_read
from app.utils.log import log_info


def validate_referral_code(code: str, db: psycopg2.extensions.connection) -> dict | None:
    """Look up a user by referral_code. Returns user row dict or None."""
    if not code or not code.strip():
        return None
    rows = db_read(
        "SELECT user_id, referral_code, market_id FROM user_info WHERE referral_code = %s AND is_archived = FALSE",
        (code.strip(),),
        connection=db,
    )
    return rows[0] if rows else None


def create_referral_on_signup(
    referrer_user_id: UUID,
    referee_user_id: UUID,
    referral_code_used: str,
    market_id: UUID,
    modified_by: UUID,
    db: psycopg2.extensions.connection,
) -> None:
    """Insert a referral_info row with status=pending after a referred user completes signup."""
    from app.services.crud_service import referral_info_service

    referral_data = {
        "referrer_user_id": referrer_user_id,
        "referee_user_id": referee_user_id,
        "referral_code_used": referral_code_used,
        "market_id": market_id,
        "referral_status": ReferralStatus.PENDING.value,
        "status": Status.ACTIVE,
        "modified_by": modified_by,
    }
    referral_info_service.create(referral_data, db)
    log_info(f"Referral created: referrer={referrer_user_id}, referee={referee_user_id}, code={referral_code_used}")


def process_referral_reward(
    referee_user_id: UUID,
    db: psycopg2.extensions.connection,
) -> None:
    """
    Check if referee was referred, and if so attempt to issue the referral reward.

    Called after the referee's first subscription payment is confirmed.
    If the referrer has an active subscription, credits are issued immediately.
    If not, the reward is held for up to held_reward_expiry_hours.
    """
    # Find pending referral for this referee
    rows = db_read(
        """
        SELECT referral_id, referrer_user_id, market_id
        FROM referral_info
        WHERE referee_user_id = %s AND referral_status = %s AND is_archived = FALSE
        """,
        (str(referee_user_id), ReferralStatus.PENDING.value),
        connection=db,
    )
    if not rows:
        return  # Not referred or already processed

    referral = rows[0]
    referral_id = UUID(str(referral["referral_id"]))
    referrer_user_id = UUID(str(referral["referrer_user_id"]))
    market_id = UUID(str(referral["market_id"]))

    # Load referral config for this market
    config = _get_referral_config(market_id, db)
    if not config or not config["is_enabled"]:
        _update_referral_status(referral_id, ReferralStatus.EXPIRED, db, expired_date=datetime.now(UTC))
        log_info(f"Referral {referral_id} expired: program not enabled for market {market_id}")
        return

    # Get referee's plan price
    plan_price = _get_referee_plan_price(referee_user_id, db)
    if plan_price is None or plan_price < config["min_plan_price_to_qualify"]:
        _update_referral_status(referral_id, ReferralStatus.EXPIRED, db, expired_date=datetime.now(UTC))
        log_info(
            f"Referral {referral_id} expired: plan price {plan_price} below minimum {config['min_plan_price_to_qualify']}"
        )
        return

    # Mark as qualified
    now = datetime.now(UTC)
    bonus_rate = config["referrer_bonus_rate"]
    bonus_credits = _compute_bonus_credits(plan_price, bonus_rate, config.get("referrer_bonus_cap"), market_id, db)

    # Check monthly cap
    if config.get("referrer_monthly_cap") is not None:
        rewarded_this_month = _count_rewards_this_month(referrer_user_id, db)
        if rewarded_this_month >= config["referrer_monthly_cap"]:
            _update_referral_status(referral_id, ReferralStatus.EXPIRED, db, expired_date=now)
            log_info(f"Referral {referral_id} expired: referrer {referrer_user_id} hit monthly cap")
            return

    # Check if referrer has active subscription
    referrer_subscription = _get_active_subscription(referrer_user_id, db)

    if referrer_subscription:
        # Issue credits immediately
        _issue_reward(
            referral_id,
            referrer_user_id,
            referrer_subscription["subscription_id"],
            bonus_credits,
            plan_price,
            bonus_rate,
            db,
        )
        log_info(f"Referral {referral_id} rewarded: {bonus_credits} credits to referrer {referrer_user_id}")
    else:
        # Hold reward — referrer doesn't have active subscription
        held_until = now + timedelta(hours=config["held_reward_expiry_hours"])
        cursor = db.cursor()
        try:
            cursor.execute(
                """
                UPDATE referral_info
                SET referral_status = %s, qualified_date = %s,
                    bonus_credits_awarded = %s, bonus_plan_price = %s, bonus_rate_applied = %s,
                    reward_held_until = %s, modified_date = CURRENT_TIMESTAMP
                WHERE referral_id = %s::uuid
                """,
                (
                    ReferralStatus.QUALIFIED.value,
                    now,
                    float(bonus_credits),
                    float(plan_price),
                    bonus_rate,
                    held_until,
                    str(referral_id),
                ),
            )
            db.commit()
        finally:
            cursor.close()
        log_info(f"Referral {referral_id} qualified but held until {held_until} (referrer has no active subscription)")


def retry_held_rewards(db: psycopg2.extensions.connection) -> int:
    """Retry held rewards. Called by cron. Returns count of referrals processed."""
    now = datetime.now(UTC)
    rows = db_read(
        """
        SELECT referral_id, referrer_user_id, bonus_credits_awarded, bonus_plan_price,
               bonus_rate_applied, reward_held_until, market_id
        FROM referral_info
        WHERE referral_status = %s AND reward_held_until IS NOT NULL AND is_archived = FALSE
        """,
        (ReferralStatus.QUALIFIED.value,),
        connection=db,
    )
    if not rows:
        return 0

    processed = 0
    for row in rows:
        referral_id = UUID(str(row["referral_id"]))
        referrer_user_id = UUID(str(row["referrer_user_id"]))
        held_until = row["reward_held_until"]

        # Ensure timezone-aware comparison
        if held_until and held_until.tzinfo is None:
            held_until = held_until.replace(tzinfo=UTC)

        if held_until and held_until < now:
            # Expired — referrer never activated
            _update_referral_status(referral_id, ReferralStatus.EXPIRED, db, expired_date=now)
            log_info(f"Held referral {referral_id} expired (referrer {referrer_user_id} never activated)")
            processed += 1
            continue

        # Check if referrer now has active subscription
        referrer_subscription = _get_active_subscription(referrer_user_id, db)
        if referrer_subscription:
            bonus_credits = Decimal(str(row["bonus_credits_awarded"])) if row["bonus_credits_awarded"] else Decimal("0")
            plan_price = Decimal(str(row["bonus_plan_price"])) if row["bonus_plan_price"] else Decimal("0")
            bonus_rate = row["bonus_rate_applied"] or 0
            _issue_reward(
                referral_id,
                referrer_user_id,
                referrer_subscription["subscription_id"],
                bonus_credits,
                plan_price,
                bonus_rate,
                db,
            )
            log_info(f"Held referral {referral_id} now rewarded: {bonus_credits} credits to {referrer_user_id}")
            processed += 1

    return processed


def expire_stale_pending_referrals(db: psycopg2.extensions.connection) -> int:
    """Expire pending referrals older than their market's pending_expiry_days. Returns count expired."""
    rows = db_read(
        """
        SELECT ri.referral_id, ri.market_id, ri.created_date,
               rc.pending_expiry_days
        FROM referral_info ri
        JOIN referral_config rc ON ri.market_id = rc.market_id AND rc.is_archived = FALSE
        WHERE ri.referral_status = %s AND ri.is_archived = FALSE
        """,
        (ReferralStatus.PENDING.value,),
        connection=db,
    )
    if not rows:
        return 0

    now = datetime.now(UTC)
    expired_count = 0
    for row in rows:
        created = row["created_date"]
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        expiry_days = row["pending_expiry_days"] or 90
        if created and (now - created).days >= expiry_days:
            referral_id = UUID(str(row["referral_id"]))
            _update_referral_status(referral_id, ReferralStatus.EXPIRED, db, expired_date=now)
            expired_count += 1

    return expired_count


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_referral_config(market_id: UUID, db: psycopg2.extensions.connection) -> dict | None:
    """Load active referral config for a market."""
    rows = db_read(
        "SELECT * FROM referral_config WHERE market_id = %s AND is_archived = FALSE",
        (str(market_id),),
        connection=db,
    )
    return rows[0] if rows else None


def _get_referee_plan_price(referee_user_id: UUID, db: psycopg2.extensions.connection) -> Decimal | None:
    """Get the plan price for the referee's subscription."""
    rows = db_read(
        """
        SELECT p.price
        FROM subscription_info s
        JOIN plan_info p ON s.plan_id = p.plan_id
        WHERE s.user_id = %s AND s.is_archived = FALSE
        ORDER BY s.created_date DESC
        LIMIT 1
        """,
        (str(referee_user_id),),
        connection=db,
    )
    if not rows or rows[0]["price"] is None:
        return None
    return Decimal(str(rows[0]["price"]))


def _compute_bonus_credits(
    plan_price: Decimal,
    bonus_rate: int,
    bonus_cap: Decimal | None,
    market_id: UUID,
    db: psycopg2.extensions.connection,
) -> Decimal:
    """Compute bonus credits: floor(plan_price * rate / 100 / credit_value), capped."""
    raw_bonus = plan_price * Decimal(str(bonus_rate)) / Decimal("100")
    if bonus_cap is not None:
        bonus_cap = Decimal(str(bonus_cap))
        raw_bonus = min(raw_bonus, bonus_cap)

    # Convert currency amount to credits using market's credit currency
    rows = db_read(
        """
        SELECT cc.credit_value_local_currency
        FROM market_info m
        JOIN currency_metadata cc ON m.currency_metadata_id = cc.currency_metadata_id
        WHERE m.market_id = %s
        """,
        (str(market_id),),
        connection=db,
    )
    if rows and rows[0]["credit_value_local_currency"]:
        credit_value = Decimal(str(rows[0]["credit_value_local_currency"]))
        if credit_value > 0:
            return Decimal(str(math.floor(raw_bonus / credit_value)))

    # Fallback: treat raw_bonus as credits directly
    return Decimal(str(math.floor(raw_bonus)))


def _get_active_subscription(user_id: UUID, db: psycopg2.extensions.connection) -> dict | None:
    """Return the active subscription for a user, or None."""
    rows = db_read(
        """
        SELECT subscription_id, balance
        FROM subscription_info
        WHERE user_id = %s AND subscription_status = 'active' AND is_archived = FALSE
        LIMIT 1
        """,
        (str(user_id),),
        connection=db,
    )
    return rows[0] if rows else None


def _count_rewards_this_month(referrer_user_id: UUID, db: psycopg2.extensions.connection) -> int:
    """Count how many referral rewards were issued to this referrer in the current calendar month."""
    rows = db_read(
        """
        SELECT COUNT(*) as cnt
        FROM referral_info
        WHERE referrer_user_id = %s
          AND referral_status = %s
          AND rewarded_date >= date_trunc('month', CURRENT_TIMESTAMP)
          AND is_archived = FALSE
        """,
        (str(referrer_user_id), ReferralStatus.REWARDED.value),
        connection=db,
    )
    return int(rows[0]["cnt"]) if rows else 0


def _issue_reward(
    referral_id: UUID,
    referrer_user_id: UUID,
    subscription_id: UUID,
    bonus_credits: Decimal,
    plan_price: Decimal,
    bonus_rate: int,
    db: psycopg2.extensions.connection,
) -> None:
    """Issue referral credits: create client_transaction, update balance, mark rewarded."""
    from app.services.crud_service import client_transaction_service, update_balance

    if bonus_credits <= 0:
        _update_referral_status(referral_id, ReferralStatus.EXPIRED, db, expired_date=datetime.now(UTC))
        return

    # System user for modified_by
    system_user_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    # Create client transaction
    transaction_data = {
        "user_id": referrer_user_id,
        "source": "referral_program",
        "referral_id": referral_id,
        "credit": float(bonus_credits),
        "status": Status.ACTIVE,
        "modified_by": system_user_id,
    }
    transaction = client_transaction_service.create(transaction_data, db)

    # Update subscription balance
    update_balance(UUID(str(subscription_id)), float(bonus_credits), db, commit=False)

    # Mark referral as rewarded
    now = datetime.now(UTC)
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            UPDATE referral_info
            SET referral_status = %s, qualified_date = COALESCE(qualified_date, %s),
                rewarded_date = %s, bonus_credits_awarded = %s,
                bonus_plan_price = %s, bonus_rate_applied = %s,
                transaction_id = %s::uuid, reward_held_until = NULL,
                modified_date = CURRENT_TIMESTAMP
            WHERE referral_id = %s::uuid
            """,
            (
                ReferralStatus.REWARDED.value,
                now,
                now,
                float(bonus_credits),
                float(plan_price),
                bonus_rate,
                str(transaction.transaction_id),
                str(referral_id),
            ),
        )
        db.commit()
    finally:
        cursor.close()


def _update_referral_status(
    referral_id: UUID,
    new_status: ReferralStatus,
    db: psycopg2.extensions.connection,
    *,
    expired_date: datetime | None = None,
) -> None:
    """Update referral_info status with optional expired_date."""
    cursor = db.cursor()
    try:
        if expired_date:
            cursor.execute(
                """
                UPDATE referral_info
                SET referral_status = %s, expired_date = %s, modified_date = CURRENT_TIMESTAMP
                WHERE referral_id = %s::uuid
                """,
                (new_status.value, expired_date, str(referral_id)),
            )
        else:
            cursor.execute(
                """
                UPDATE referral_info
                SET referral_status = %s, modified_date = CURRENT_TIMESTAMP
                WHERE referral_id = %s::uuid
                """,
                (new_status.value, str(referral_id)),
            )
        db.commit()
    finally:
        cursor.close()
