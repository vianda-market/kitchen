"""
Customer payment provider management (B2C).

Endpoints for listing and disconnecting payment provider accounts (e.g. Stripe).
A payment provider account (user_payment_provider) is the link between a user and
a provider's customer object. It is created automatically during the setup-session
flow and can be archived (disconnected) here.

Note: Archiving a provider does NOT delete the Stripe Customer object via the Stripe
API — Stripe Customer deletion is irreversible and out of scope. The record is only
archived locally, along with all associated payment methods.
"""

from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_client_user
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.payment_method import UserPaymentProviderResponseSchema
from app.utils.db import db_read
from app.utils.log import log_info, log_warning

router = APIRouter(prefix="/payment-providers", tags=["Customer Payment Providers"])


def _get_providers_for_user(
    user_id: UUID,
    db: psycopg2.extensions.connection,
) -> list[UserPaymentProviderResponseSchema]:
    rows = db_read(
        """
        SELECT
            upp.user_payment_provider_id,
            upp.provider,
            upp.created_date,
            COUNT(pm.payment_method_id) FILTER (
                WHERE pm.is_archived = FALSE
            )::int AS payment_method_count
        FROM user_payment_provider upp
        LEFT JOIN payment_method pm
            ON pm.user_id = upp.user_id
            AND pm.method_type = 'Stripe'
        WHERE upp.user_id = %s::uuid
          AND upp.is_archived = FALSE
        GROUP BY upp.user_payment_provider_id, upp.provider, upp.created_date
        ORDER BY upp.created_date ASC
        """,
        (str(user_id),),
        connection=db,
    )
    return [UserPaymentProviderResponseSchema(**row) for row in rows]


def _archive_provider(
    user_payment_provider_id: UUID,
    user_id: UUID,
    db: psycopg2.extensions.connection,
) -> None:
    """Archive the provider record and all associated payment methods for this user."""
    cur = db.cursor()
    try:
        cur.execute(
            """
            UPDATE user_payment_provider
            SET is_archived = TRUE,
                status = 'inactive'::status_enum,
                modified_by = %s::uuid,
                modified_date = CURRENT_TIMESTAMP
            WHERE user_payment_provider_id = %s::uuid
              AND user_id = %s::uuid
              AND is_archived = FALSE
            RETURNING provider
            """,
            (str(user_id), str(user_payment_provider_id), str(user_id)),
        )
        row = cur.fetchone()
        if not row:
            db.rollback()
            raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale="en", entity="Payment provider")
        provider = row[0]

        # Archive all active payment methods for this user+provider
        cur.execute(
            """
            UPDATE payment_method
            SET is_archived = TRUE,
                modified_by = %s::uuid,
                modified_date = CURRENT_TIMESTAMP
            WHERE user_id = %s::uuid
              AND method_type = 'Stripe'
              AND is_archived = FALSE
            """,
            (str(user_id), str(user_id)),
        )
        archived_pm_count = cur.rowcount
        db.commit()
        log_info(
            f"provider disconnect: user={user_id} provider={provider} archived {archived_pm_count} payment method(s)"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log_warning(f"provider disconnect error: user={user_id} err={e}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en") from None
    finally:
        cur.close()


@router.get("", response_model=list[UserPaymentProviderResponseSchema])
def list_payment_providers(
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> list[UserPaymentProviderResponseSchema]:
    """List connected payment provider accounts for the current user."""
    user_id = UUID(str(current_user["user_id"]))
    return _get_providers_for_user(user_id, db)


@router.delete(
    "/{user_payment_provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def disconnect_payment_provider(
    user_payment_provider_id: UUID,
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> None:
    """
    Disconnect (archive) a payment provider account and all associated payment methods.

    Does NOT delete the Stripe Customer object in Stripe — only archives the local record.
    """
    user_id = UUID(str(current_user["user_id"]))
    _archive_provider(user_payment_provider_id, user_id, db)
