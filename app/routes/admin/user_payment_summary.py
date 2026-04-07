"""
Employee-facing user payment summary (Internal role only).

Read-only endpoint returning a per-customer view of Stripe payment method status.
Used by Internal employees to review which customers have payment methods registered.

Access: Internal role only (get_employee_user). Suppliers, Customers, and Employers
receive 403.
"""
from typing import List

import psycopg2.extensions
from fastapi import APIRouter, Depends

from app.auth.dependencies import get_employee_user
from app.dependencies.database import get_db
from app.schemas.payment_method import UserPaymentSummarySchema
from app.utils.db import db_read

router = APIRouter(prefix="/user-payment-summary", tags=["User Payment Summary"])

_SUMMARY_QUERY = """
SELECT
    u.user_id,
    u.username,
    u.email,
    TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) AS full_name,
    u.status,
    CASE WHEN upp.user_payment_provider_id IS NOT NULL
         THEN TRUE ELSE FALSE END                           AS has_stripe_provider,
    upp.created_date                                        AS provider_connected_date,
    COUNT(pm.payment_method_id)
        FILTER (WHERE pm.is_archived = FALSE)::int          AS payment_method_count,
    MAX(CASE WHEN pm.is_default = TRUE AND pm.is_archived = FALSE
             THEN epm.last4 END)                            AS default_last4,
    MAX(CASE WHEN pm.is_default = TRUE AND pm.is_archived = FALSE
             THEN epm.brand END)                            AS default_brand
FROM user_info u
LEFT JOIN user_payment_provider upp
       ON upp.user_id = u.user_id
      AND upp.provider = 'stripe'
      AND upp.is_archived = FALSE
LEFT JOIN payment_method pm
       ON pm.user_id = u.user_id
      AND pm.method_type = 'Stripe'
LEFT JOIN external_payment_method epm
       ON epm.payment_method_id = pm.payment_method_id
WHERE u.role_type = 'Customer'
  AND u.is_archived = FALSE
GROUP BY
    u.user_id,
    u.username,
    u.email,
    u.first_name,
    u.last_name,
    u.status,
    upp.user_payment_provider_id,
    upp.created_date
ORDER BY u.created_date DESC
"""


@router.get("", response_model=List[UserPaymentSummarySchema])
def list_user_payment_summary(
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> List[UserPaymentSummarySchema]:
    """
    List all non-archived customers with their Stripe payment method status.

    Returns one row per customer regardless of whether they have a payment method.
    Customers with no saved cards appear with has_stripe_provider=false and
    payment_method_count=0.

    Authorization: Internal role only.
    """
    rows = db_read(_SUMMARY_QUERY, None, connection=db)
    return [UserPaymentSummarySchema(**row) for row in rows]
