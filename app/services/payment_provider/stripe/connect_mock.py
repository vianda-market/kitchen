# app/services/payment_provider/stripe/connect_mock.py
"""
Mock Stripe Connect implementation. Same signatures as connect_gateway.py; no HTTP calls.
Used when SUPPLIER_PAYOUT_PROVIDER=mock (default for dev/test environments).
"""
import uuid
from typing import Optional
from uuid import UUID

import psycopg2.extensions

from app.utils.log import log_info


def create_connected_account(entity_id: UUID, name: str, email: Optional[str] = None) -> str:
    """Return a fake acct_mock_… ID; no Stripe call made."""
    mock_id = f"acct_mock_{uuid.uuid4().hex[:16]}"
    log_info(f"[MOCK] Created Connect account {mock_id} for entity {entity_id}")
    return mock_id


def create_account_link(
    payout_provider_account_id: str,
    refresh_url: str,
    return_url: str,
) -> dict:
    """Return a fake onboarding link; no Stripe call made."""
    log_info(f"[MOCK] Created onboarding link for {payout_provider_account_id}")
    return {
        "url": f"https://connect.stripe.com/mock/onboarding/{payout_provider_account_id}",
        "expires_at": 9999999999,
    }


def get_account_status(payout_provider_account_id: str) -> dict:
    """Return fully-enabled mock status; no Stripe call made."""
    return {
        "charges_enabled": True,
        "payouts_enabled": True,
        "details_submitted": True,
    }


def create_account_session(payout_provider_account_id: str) -> str:
    """Return a fake client_secret; no Stripe call made."""
    mock_secret = f"cs_mock_{uuid.uuid4().hex}"
    log_info(f"[MOCK] Created AccountSession for {payout_provider_account_id}")
    return mock_secret


def create_transfer(
    payout_provider_account_id: str,
    amount_minor: int,
    currency: str,
    institution_bill_id: UUID,
    institution_entity_id: UUID,
    idempotency_key: str,
) -> str:
    """Return a fake tr_mock_… transfer ID; no Stripe call made."""
    mock_id = f"tr_mock_{uuid.uuid4().hex[:16]}"
    log_info(
        f"[MOCK] Transfer {mock_id} → {payout_provider_account_id} "
        f"amount={amount_minor} {currency} bill={institution_bill_id}"
    )
    return mock_id


def execute_supplier_payout(
    institution_bill_id: UUID,
    entity_id: UUID,
    current_user_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict:
    """
    Mock payout execution. Validates bill and entity the same way as the live gateway,
    but uses fake transfer IDs. No real Stripe calls.
    """
    from fastapi import HTTPException
    from app.services.crud_service import institution_bill_service, institution_entity_service

    bill = institution_bill_service.get_by_id(str(institution_bill_id), db)
    if not bill:
        raise HTTPException(status_code=404, detail="Institution bill not found")
    if bill.get("resolution") != "Pending":
        raise HTTPException(
            status_code=400,
            detail=f"Bill resolution is '{bill.get('resolution')}'; only Pending bills can be paid out",
        )

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

    entity = institution_entity_service.get_by_id(str(entity_id), db)
    if not entity:
        raise HTTPException(status_code=404, detail="Institution entity not found")
    connect_id = entity.get("payout_provider_account_id")
    if not connect_id:
        raise HTTPException(
            status_code=400,
            detail="Entity has no payout provider account. Complete onboarding first.",
        )

    amount = bill.get("amount") or 0
    currency_code = bill.get("currency_code") or "usd"
    idempotency_key = f"bill_{institution_bill_id}_stripe"
    transfer_id = create_transfer(
        payout_provider_account_id=connect_id,
        amount_minor=int(amount),
        currency=currency_code,
        institution_bill_id=institution_bill_id,
        institution_entity_id=entity_id,
        idempotency_key=idempotency_key,
    )

    payout_id = None
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO billing.institution_bill_payout
                (institution_bill_id, provider, provider_transfer_id, amount, currency_code,
                 status, idempotency_key, modified_by)
            VALUES (%s, 'stripe', %s, %s, %s, 'Pending', %s, %s)
            RETURNING bill_payout_id
            """,
            (str(institution_bill_id), transfer_id, amount, currency_code, idempotency_key, str(current_user_id)),
        )
        payout_id = cur.fetchone()[0]
    db.commit()

    log_info(
        f"[MOCK] Payout initiated: institution_entity_id={entity_id} "
        f"institution_bill_id={institution_bill_id} bill_payout_id={payout_id} "
        f"amount={amount} currency={currency_code} provider=mock "
        f"provider_transfer_id={transfer_id}"
    )

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
