import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user
from app.dependencies.database import get_db
from app.schemas.onboarding import OnboardingStatusResponseSchema
from app.services.onboarding_service import get_customer_onboarding_status
from app.utils.rate_limit import limiter

router = APIRouter(
    prefix="/users",
    tags=["User Onboarding"],
)


@router.get(
    "/me/onboarding-status",
    response_model=OnboardingStatusResponseSchema,
)
@limiter.limit("30/minute")
def get_my_onboarding_status(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Customer onboarding status (user-level). Returns checklist with has_verified_email and has_active_subscription."""
    if current_user.get("role_type") != "customer":
        raise HTTPException(status_code=404, detail="Onboarding status is only available for Customer users")

    user_id = current_user["user_id"]
    result = get_customer_onboarding_status(user_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")

    # Customers never see "stalled" — show as in_progress
    if result["onboarding_status"] == "stalled":
        result["onboarding_status"] = "in_progress"

    return result
