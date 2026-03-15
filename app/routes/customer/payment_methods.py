"""
Customer payment method management (B2C).

Mock endpoints for UI development. Phase 2: persists mock data to DB (stripe_customer_id,
payment_method, external_payment_method). DELETE and PUT default perform real DB updates.
See docs/roadmap/STRIPE_CUSTOMER_INTEGRATION_ROADMAP.md.
"""
import uuid as uuid_module
from uuid import UUID
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Body
import psycopg2.extensions

from app.auth.dependencies import get_client_user
from app.dependencies.database import get_db
from app.config.settings import settings
from app.config import Status
from app.utils.db import db_read, db_insert, db_update
from app.schemas.customer_payment_method import (
    CustomerPaymentMethodListResponseSchema,
    CustomerPaymentMethodItemSchema,
    SetupSessionRequestSchema,
    SetupSessionResponseSchema,
)

router = APIRouter(prefix="/payment-methods", tags=["Customer Payment Methods"])

MOCK_SETUP_URL = "https://mock-stripe-setup.example"


def _get_payment_provider() -> str:
    return (getattr(settings, "PAYMENT_PROVIDER", None) or "mock").strip().lower()


def _ensure_stripe_customer_for_mock(
    user_id: UUID,
    db: psycopg2.extensions.connection,
) -> str:
    """Ensure user has stripe_customer_id; create mock value if missing. Returns the id."""
    rows = db_read(
        "SELECT stripe_customer_id FROM user_info WHERE user_id = %s::uuid",
        (str(user_id),),
        connection=db,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="User not found.")
    existing = rows[0].get("stripe_customer_id")
    if existing:
        return existing
    mock_cus_id = f"cus_mock_{str(user_id).replace('-', '')[:24]}"
    now = datetime.now(timezone.utc)
    db_update(
        "user_info",
        {
            "stripe_customer_id": mock_cus_id,
            "modified_by": str(user_id),
            "modified_date": now,
        },
        {"user_id": str(user_id)},
        connection=db,
    )
    return mock_cus_id


def _list_from_db(user_id: UUID, db: psycopg2.extensions.connection) -> List[CustomerPaymentMethodItemSchema]:
    """Fetch payment methods from DB for user (Stripe provider only)."""
    rows = db_read(
        """
        SELECT pm.payment_method_id, pm.is_default, epm.external_id, epm.last4, epm.brand
        FROM payment_method pm
        JOIN external_payment_method epm ON epm.payment_method_id = pm.payment_method_id
        WHERE pm.user_id = %s::uuid
          AND pm.is_archived = FALSE
          AND epm.provider = 'stripe'
        ORDER BY pm.is_default DESC, pm.created_date ASC
        """,
        (str(user_id),),
        connection=db,
    )
    return [
        CustomerPaymentMethodItemSchema(
            payment_method_id=row["payment_method_id"],
            last4=row.get("last4"),
            brand=row.get("brand"),
            is_default=row.get("is_default", False),
            external_id=row.get("external_id"),
        )
        for row in rows
    ]


def _get_payment_method_owner(payment_method_id: UUID, db: psycopg2.extensions.connection) -> Optional[UUID]:
    """Return user_id if payment method exists and is not archived, else None."""
    rows = db_read(
        """
        SELECT user_id FROM payment_method
        WHERE payment_method_id = %s::uuid AND is_archived = FALSE
        """,
        (str(payment_method_id),),
        connection=db,
    )
    if not rows:
        return None
    return UUID(str(rows[0]["user_id"]))


@router.get("", response_model=CustomerPaymentMethodListResponseSchema)
def list_customer_payment_methods(
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    List saved payment methods for the current customer.
    Returns DB rows (Phase 2: real data from payment_method + external_payment_method).
    Customer only.
    """
    user_id = UUID(str(current_user["user_id"]))
    items = _list_from_db(user_id, db)
    return CustomerPaymentMethodListResponseSchema(payment_methods=items)


@router.post("/setup-session", response_model=SetupSessionResponseSchema)
def create_setup_session(
    body: Optional[SetupSessionRequestSchema] = Body(None),
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Create Stripe Checkout setup session URL for adding/updating payment method.
    Mock: ensures stripe_customer_id on user, returns fixed URL. Live: creates Stripe Session.
    Customer only.
    """
    user_id = UUID(str(current_user["user_id"]))
    if _get_payment_provider() == "mock":
        _ensure_stripe_customer_for_mock(user_id, db)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    return SetupSessionResponseSchema(
        setup_url=MOCK_SETUP_URL,
        expires_at=expires_at,
    )


@router.post("/mock-add", response_model=CustomerPaymentMethodItemSchema)
def mock_add_payment_method(
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    [Mock only] Simulate adding a payment method after returning from Stripe setup.
    Creates payment_method + external_payment_method in DB. Only when PAYMENT_PROVIDER=mock.
    Use for E2E testing and local dev to persist mock data.
    Customer only.
    """
    if _get_payment_provider() != "mock":
        raise HTTPException(
            status_code=400,
            detail="mock-add is only available when PAYMENT_PROVIDER=mock.",
        )
    user_id = UUID(str(current_user["user_id"]))
    stripe_customer_id = _ensure_stripe_customer_for_mock(user_id, db)
    external_id = f"pm_mock_{uuid_module.uuid4().hex[:24]}"
    pm_data = {
        "user_id": str(user_id),
        "method_type": "Stripe",
        "is_archived": False,
        "status": Status.ACTIVE,
        "is_default": False,
        "modified_by": str(user_id),
    }
    existing_count = db_read(
        """
        SELECT COUNT(*) AS cnt FROM payment_method pm
        JOIN external_payment_method epm ON epm.payment_method_id = pm.payment_method_id
        WHERE pm.user_id = %s::uuid AND pm.is_archived = FALSE AND epm.provider = 'stripe'
        """,
        (str(user_id),),
        connection=db,
    )[0]["cnt"]
    pm_data["is_default"] = existing_count == 0

    pm_id = db_insert("payment_method", pm_data, connection=db, commit=False)
    epm_data = {
        "payment_method_id": str(pm_id),
        "provider": "stripe",
        "external_id": external_id,
        "last4": "4242",
        "brand": "visa",
        "provider_customer_id": stripe_customer_id,
    }
    db_insert("external_payment_method", epm_data, connection=db, commit=True)

    return CustomerPaymentMethodItemSchema(
        payment_method_id=UUID(str(pm_id)),
        last4="4242",
        brand="visa",
        is_default=pm_data["is_default"],
        external_id=external_id,
    )


@router.delete("/{payment_method_id}")
def delete_customer_payment_method(
    payment_method_id: UUID,
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Remove a payment method (archive). Verifies ownership.
    Live: also calls stripe.PaymentMethod.detach(). Customer only.
    """
    user_id = UUID(str(current_user["user_id"]))
    owner = _get_payment_method_owner(payment_method_id, db)
    if owner is None:
        raise HTTPException(status_code=404, detail="Payment method not found.")
    if owner != user_id:
        raise HTTPException(status_code=403, detail="You cannot remove this payment method.")

    db_update(
        "payment_method",
        {"is_archived": True, "modified_by": str(user_id)},
        {"payment_method_id": str(payment_method_id)},
        connection=db,
    )
    return {"detail": "Payment method removed."}


@router.put("/{payment_method_id}/default")
def set_default_payment_method(
    payment_method_id: UUID,
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Set payment method as default. Verifies ownership. Clears default on others.
    Live: also updates Stripe Customer invoice_settings. Customer only.
    """
    user_id = UUID(str(current_user["user_id"]))
    owner = _get_payment_method_owner(payment_method_id, db)
    if owner is None:
        raise HTTPException(status_code=404, detail="Payment method not found.")
    if owner != user_id:
        raise HTTPException(status_code=403, detail="You cannot update this payment method.")

    db_update(
        "payment_method",
        {"is_default": False, "modified_by": str(user_id)},
        {"user_id": str(user_id)},
        connection=db,
    )
    db_update(
        "payment_method",
        {"is_default": True, "modified_by": str(user_id)},
        {"payment_method_id": str(payment_method_id)},
        connection=db,
    )
    return {"detail": "Default payment method updated."}
