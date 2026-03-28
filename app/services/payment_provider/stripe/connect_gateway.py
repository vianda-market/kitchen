# app/services/payment_provider/stripe/connect_gateway.py
"""
Stripe Connect outbound: account creation, onboarding links, transfers, and payout execution.

Only active when SUPPLIER_PAYOUT_PROVIDER=stripe. Uses the same STRIPE_SECRET_KEY as inbound.
All functions raise HTTPException on Stripe API errors so routes get clean 4xx/5xx responses.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import psycopg2.extensions
import stripe

from app.config.settings import settings
from app.config.enums import BillPayoutStatus
from app.utils.log import log_info, log_error


def _ensure_connect_configured() -> None:
    """Set Stripe API key from settings. Called before any Stripe Connect API call."""
    key = (settings.STRIPE_SECRET_KEY or "").strip()
    if not key:
        raise ValueError(
            "STRIPE_SECRET_KEY is required when SUPPLIER_PAYOUT_PROVIDER=stripe. "
            "Add it to .env (use sk_test_... for sandbox)."
        )
    stripe.api_key = key


def create_connected_account(entity_id: UUID, name: str, email: Optional[str] = None) -> str:
    """
    Create a Stripe Express connected account for a supplier entity.
    Returns stripe_connect_account_id (acct_…). Idempotent by metadata lookup is not done here —
    callers must check entity.stripe_connect_account_id before calling.
    """
    _ensure_connect_configured()
    params = {
        "type": "express",
        "metadata": {"institution_entity_id": str(entity_id)},
    }
    if name:
        params["business_profile"] = {"name": name}
    if email:
        params["email"] = email
    account = stripe.Account.create(**params)
    log_info(f"Created Stripe Connect account {account.id} for entity {entity_id}")
    return account.id


def create_account_link(
    stripe_connect_account_id: str,
    refresh_url: str,
    return_url: str,
) -> dict:
    """
    Generate an Account Link URL for the supplier to complete Stripe Express onboarding.
    Returns {"url": str, "expires_at": int (Unix timestamp)}.
    Links expire in ~10 minutes; always regenerate on each onboarding attempt.
    """
    _ensure_connect_configured()
    link = stripe.AccountLink.create(
        account=stripe_connect_account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )
    log_info(f"Created onboarding link for {stripe_connect_account_id}")
    return {"url": link.url, "expires_at": link.expires_at}


def get_account_status(stripe_connect_account_id: str) -> dict:
    """
    Retrieve charges_enabled, payouts_enabled, and details_submitted from Stripe.
    Returns {"charges_enabled": bool, "payouts_enabled": bool, "details_submitted": bool}.
    """
    _ensure_connect_configured()
    account = stripe.Account.retrieve(stripe_connect_account_id)
    return {
        "charges_enabled": account.charges_enabled,
        "payouts_enabled": account.payouts_enabled,
        "details_submitted": account.details_submitted,
    }


def create_transfer(
    stripe_connect_account_id: str,
    amount_minor: int,
    currency: str,
    institution_bill_id: UUID,
    institution_entity_id: UUID,
    idempotency_key: str,
) -> str:
    """
    Create a Stripe Transfer to a connected account. Returns transfer ID (tr_…).
    amount_minor is in the smallest currency unit (e.g. cents for USD).
    Uses idempotency_key to prevent double-transfers on retries.
    """
    _ensure_connect_configured()
    transfer = stripe.Transfer.create(
        amount=amount_minor,
        currency=(currency or "usd").lower(),
        destination=stripe_connect_account_id,
        metadata={
            "institution_bill_id": str(institution_bill_id),
            "institution_entity_id": str(institution_entity_id),
        },
        idempotency_key=idempotency_key,
    )
    log_info(f"Created Stripe Transfer {transfer.id} → {stripe_connect_account_id} for bill {institution_bill_id}")
    return transfer.id


def execute_supplier_payout(
    institution_bill_id: UUID,
    entity_id: UUID,
    current_user_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict:
    """
    Initiate a Stripe payout for an institution bill.

    Write-first pattern: INSERT payout row as Pending before calling Stripe so
    the row exists if the process crashes after the transfer is created.

    Steps:
    1. Load and validate bill (Pending resolution, no active payout in progress)
    2. Load entity; verify stripe_connect_account_id is set and payouts_enabled
    3. INSERT payout row (Pending) with idempotency_key
    4. Call Stripe create_transfer
    5. UPDATE payout row with provider_transfer_id
    6. Return payout row dict
    """
    from fastapi import HTTPException
    from app.services.crud_service import institution_bill_service, institution_entity_service
    from app.utils.db import db_read

    # 1. Load bill
    bill = institution_bill_service.get_by_id(str(institution_bill_id), db)
    if not bill:
        raise HTTPException(status_code=404, detail="Institution bill not found")
    if bill.get("resolution") != "Pending":
        raise HTTPException(
            status_code=400,
            detail=f"Bill resolution is '{bill.get('resolution')}'; only Pending bills can be paid out",
        )

    # Check for an existing non-Failed payout (idempotency guard)
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT bill_payout_id, status FROM billing.institution_bill_payout
            WHERE institution_bill_id = %s AND status != 'Failed'
            ORDER BY created_at DESC LIMIT 1
            """,
            (str(institution_bill_id),),
        )
        existing = cur.fetchone()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"A payout for this bill already exists with status '{existing[1]}'",
        )

    # 2. Load entity
    entity = institution_entity_service.get_by_id(str(entity_id), db)
    if not entity:
        raise HTTPException(status_code=404, detail="Institution entity not found")
    connect_id = entity.get("stripe_connect_account_id")
    if not connect_id:
        raise HTTPException(
            status_code=400,
            detail="Entity has no Stripe Connect account. Complete onboarding first.",
        )

    # Verify payouts_enabled via live Stripe check
    status_info = get_account_status(connect_id)
    if not status_info.get("payouts_enabled"):
        raise HTTPException(
            status_code=400,
            detail="Stripe Connect account is not yet enabled for payouts. Supplier must complete onboarding.",
        )

    # 3. Compute amount and idempotency_key; INSERT payout row as Pending
    amount = bill.get("amount") or 0
    currency_code = bill.get("currency_code") or "usd"
    # Stripe amounts are in minor units; assume stored amount is already in minor units (integer cents)
    amount_minor = int(amount)
    idempotency_key = f"bill_{institution_bill_id}_stripe"

    payout_id = None
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO billing.institution_bill_payout
                    (institution_bill_id, provider, amount, currency_code, status, idempotency_key, modified_by)
                VALUES (%s, 'stripe', %s, %s, 'Pending', %s, %s)
                RETURNING bill_payout_id
                """,
                (str(institution_bill_id), amount, currency_code, idempotency_key, str(current_user_id)),
            )
            payout_id = cur.fetchone()[0]
        db.commit()

        # 4. Call Stripe
        transfer_id = create_transfer(
            stripe_connect_account_id=connect_id,
            amount_minor=amount_minor,
            currency=currency_code,
            institution_bill_id=institution_bill_id,
            institution_entity_id=entity_id,
            idempotency_key=idempotency_key,
        )

        # 5. UPDATE payout row with transfer ID
        with db.cursor() as cur:
            cur.execute(
                """
                UPDATE billing.institution_bill_payout
                SET provider_transfer_id = %s
                WHERE bill_payout_id = %s
                """,
                (transfer_id, str(payout_id)),
            )
        db.commit()

    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Payout execution failed for bill {institution_bill_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Stripe payout failed: {str(e)}")

    # 6. Return payout row
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT bill_payout_id, institution_bill_id, provider, provider_transfer_id,
                   amount, currency_code, status, created_at, completed_at
            FROM billing.institution_bill_payout
            WHERE bill_payout_id = %s
            """,
            (str(payout_id),),
        )
        row = cur.fetchone()
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))
