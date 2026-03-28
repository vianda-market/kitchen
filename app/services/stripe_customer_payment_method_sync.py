# app/services/stripe_customer_payment_method_sync.py
"""Stripe webhook helpers: persist customer payment methods from payment_method.* events."""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

import psycopg2.extensions

from app.utils.db import db_read
from app.utils.log import log_info, log_warning


def resolve_user_id_for_stripe_customer(
    stripe_customer_id: str,
    db: psycopg2.extensions.connection,
) -> Optional[UUID]:
    row = db_read(
        """
        SELECT u.user_id FROM user_payment_provider upp
        JOIN user_info u ON u.user_id = upp.user_id
        WHERE upp.provider = 'stripe'
          AND upp.provider_customer_id = %s
          AND upp.is_archived = FALSE
          AND u.is_archived = FALSE
        LIMIT 1
        """,
        (stripe_customer_id,),
        connection=db,
        fetch_one=True,
    )
    return UUID(str(row["user_id"])) if row else None


def stripe_pm_attached_insert_if_new(
    *,
    user_id: UUID,
    stripe_customer_id: str,
    external_pm_id: str,
    last4: Optional[str],
    brand: Optional[str],
    db: psycopg2.extensions.connection,
) -> None:
    """
    Idempotent: skip if external_payment_method (stripe, external_id) exists.
    Otherwise insert payment_method + external_payment_method in one transaction.
    Rolls back orphan payment_method if EPM insert hits ON CONFLICT DO NOTHING.
    """
    existing = db_read(
        """
        SELECT 1 AS ok FROM external_payment_method epm
        WHERE epm.provider = 'stripe' AND epm.external_id = %s
        LIMIT 1
        """,
        (external_pm_id,),
        connection=db,
        fetch_one=True,
    )
    if existing:
        return

    cur = db.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*)::int FROM payment_method pm
            WHERE pm.user_id = %s::uuid
              AND pm.method_type = 'Stripe'
              AND pm.is_archived = FALSE
            """,
            (str(user_id),),
        )
        count_before = cur.fetchone()[0]
        is_default = count_before == 0

        cur.execute(
            """
            INSERT INTO payment_method (
                user_id, method_type, is_archived, status, is_default,
                modified_by, modified_date
            ) VALUES (
                %s::uuid, 'Stripe', FALSE, 'Active'::status_enum, %s,
                %s::uuid, CURRENT_TIMESTAMP
            )
            RETURNING payment_method_id
            """,
            (str(user_id), is_default, str(user_id)),
        )
        pm_row = cur.fetchone()
        if not pm_row:
            db.rollback()
            return
        pm_id = pm_row[0]

        cur.execute(
            """
            INSERT INTO external_payment_method (
                payment_method_id, provider, external_id, last4, brand, provider_customer_id,
                created_at, updated_at
            ) VALUES (
                %s::uuid, 'stripe', %s, %s, %s, %s,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT (provider, external_id) DO NOTHING
            """,
            (str(pm_id), external_pm_id, last4, brand, stripe_customer_id),
        )
        if cur.rowcount == 0:
            db.rollback()
            log_info(
                f"stripe PM attach: ON CONFLICT epm {external_pm_id}, rolled back orphan payment_method"
            )
            return
        db.commit()
        log_info(f"stripe PM attach: user={user_id} pm={external_pm_id}")
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def handle_payment_method_attached(
    payment_method_obj: Any,
    db: psycopg2.extensions.connection,
) -> None:
    customer_id = getattr(payment_method_obj, "customer", None)
    pm_id = getattr(payment_method_obj, "id", None)
    if not customer_id or not pm_id:
        log_warning("payment_method.attached missing customer or id; skipping DB")
        return

    user_id = resolve_user_id_for_stripe_customer(str(customer_id), db)
    if not user_id:
        log_warning(
            f"payment_method.attached: no user for stripe_customer_id={customer_id}; skip insert"
        )
        return

    card = getattr(payment_method_obj, "card", None)
    last4 = getattr(card, "last4", None) if card else None
    brand = getattr(card, "brand", None) if card else None

    try:
        stripe_pm_attached_insert_if_new(
            user_id=user_id,
            stripe_customer_id=str(customer_id),
            external_pm_id=str(pm_id),
            last4=last4,
            brand=brand,
            db=db,
        )
    except Exception as e:
        db.rollback()
        log_warning(f"payment_method.attached DB error (Stripe gets 200): {e}")


def handle_payment_method_detached(
    payment_method_obj: Any,
    db: psycopg2.extensions.connection,
) -> None:
    pm_id = getattr(payment_method_obj, "id", None)
    if not pm_id:
        log_warning("payment_method.detached missing id; skipping")
        return
    cur = db.cursor()
    try:
        cur.execute(
            """
            UPDATE payment_method pm
            SET is_archived = TRUE,
                modified_by = pm.user_id,
                modified_date = CURRENT_TIMESTAMP
            FROM external_payment_method epm
            WHERE epm.payment_method_id = pm.payment_method_id
              AND epm.provider = 'stripe'
              AND epm.external_id = %s
              AND pm.is_archived = FALSE
            RETURNING pm.payment_method_id
            """,
            (str(pm_id),),
        )
        if not cur.fetchone():
            db.rollback()
            log_info(f"payment_method.detached: no local row for {pm_id}; ok")
        else:
            db.commit()
            log_info(f"payment_method.detached: archived {pm_id}")
    except Exception as e:
        db.rollback()
        log_warning(f"payment_method.detached DB error (Stripe gets 200): {e}")
    finally:
        cur.close()
