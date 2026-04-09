"""
JWT payload helpers — single place for access-token claims so login, B2C verify, and password reset stay in sync.
"""

from typing import Any, Dict
from uuid import UUID

import psycopg2.extensions

from app.dto.models import UserDTO


def build_token_data(user: UserDTO) -> Dict[str, Any]:
    """Core JWT claims for Kitchen user tokens (sub, roles, institution, locale)."""
    role_type = user.role_type.value if hasattr(user.role_type, "value") else str(user.role_type)
    role_name = user.role_name.value if hasattr(user.role_name, "value") else str(user.role_name)
    loc = getattr(user, "locale", None) or "en"
    return {
        "sub": str(user.user_id),
        "role_type": role_type or "Unknown",
        "role_name": role_name or "Unknown",
        "institution_id": str(user.institution_id),
        "locale": loc,
    }


def merge_subscription_token_claims(
    token_data: Dict[str, Any],
    user_id: UUID,
    db: psycopg2.extensions.connection,
) -> None:
    """
    Add credit_cost_local_currency and subscription_market_id when user has an active subscription.
    Mutates token_data in place.
    """
    from app.services.crud_service import plan_service, subscription_service

    try:
        subscription = subscription_service.get_by_user(user_id, db)
        if subscription:
            plan = plan_service.get_by_id(subscription.plan_id, db)
            if plan:
                token_data["credit_cost_local_currency"] = float(plan.credit_cost_local_currency)
                token_data["subscription_market_id"] = str(subscription.market_id)
    except Exception:
        pass


def merge_onboarding_token_claims(
    token_data: Dict[str, Any],
    db: psycopg2.extensions.connection,
) -> None:
    """
    Add onboarding_status claim for Supplier/Employer/Customer users.
    Values: not_started, in_progress, complete (never stalled — that's internal-only).
    Mutates token_data in place.
    """
    role_type = token_data.get("role_type")
    if role_type == "internal":
        return

    try:
        if role_type in ("supplier", "employer"):
            from app.services.onboarding_service import get_onboarding_status_claim
            institution_id = UUID(token_data["institution_id"])
            token_data["onboarding_status"] = get_onboarding_status_claim(institution_id, db)
        elif role_type == "customer":
            from app.services.onboarding_service import get_customer_onboarding_claim
            user_id = UUID(token_data["sub"])
            token_data["onboarding_status"] = get_customer_onboarding_claim(user_id, db)
    except Exception:
        pass
