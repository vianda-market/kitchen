"""
Credit Validation Service - Business Logic for Credit Balance Validation

This service handles credit validation for vianda selections, ensuring users
cannot go into negative credits while allowing orders that result in zero balance.
"""

from uuid import UUID

import psycopg2.extensions
from fastapi import HTTPException
from pydantic import BaseModel

from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.services.crud_service import subscription_service
from app.utils.log import log_error, log_info, log_warning


class CreditValidationResult(BaseModel):
    """Result of credit validation check"""

    has_sufficient_credits: bool
    current_balance: float
    required_credits: float
    remaining_balance_after_purchase: float
    shortfall: float = 0.0
    can_proceed: bool = True
    message: str = ""


class InsufficientCreditsResponse(BaseModel):
    """User-friendly response for insufficient credits scenario"""

    error_type: str = "insufficient_credits"
    message: str
    current_balance: float
    required_credits: float
    shortfall: float
    payment_instructions: str
    retry_after_payment: bool = True


def validate_sufficient_credits(
    user_id: UUID, required_credits: float, db: psycopg2.extensions.connection
) -> CreditValidationResult:
    """
    Validate if user has sufficient credits for vianda selection.

    Business Rules:
    - Allow orders when user has exactly enough credits (resulting in 0 balance)
    - Block orders when credits would go negative
    - Return detailed validation result for decision making

    Args:
        user_id: User ID to check credits for
        required_credits: Credits required for the vianda selection
        db: Database connection

    Returns:
        CreditValidationResult with validation details

    Raises:
        HTTPException: If user or subscription not found
    """
    try:
        # Get user's current subscription balance
        subscription = subscription_service.get_by_user(user_id, db)
        if not subscription:
            log_error(f"Subscription not found for user {user_id}")
            raise envelope_exception(ErrorCode.SUBSCRIPTION_NOT_FOUND, status=404, locale="en")

        from decimal import Decimal

        current_decimal = Decimal(str(subscription.balance))
        required_decimal = Decimal(str(required_credits))
        remaining_decimal = current_decimal - required_decimal
        remaining_balance = float(remaining_decimal)
        current_balance = float(current_decimal)
        required_credits_float = float(required_decimal)

        has_sufficient_credits = remaining_decimal >= 0
        shortfall_decimal = max(Decimal("0"), required_decimal - current_decimal)
        shortfall = float(shortfall_decimal)

        if has_sufficient_credits:
            message = f"Sufficient credits available. Current: {current_balance}, Required: {required_credits_float}, Remaining: {remaining_balance}"
            log_info(f"Credit validation passed for user {user_id}: {message}")
        else:
            message = f"Insufficient credits. Current: {current_balance}, Required: {required_credits_float}, Shortfall: {shortfall}"
            log_warning(f"Credit validation failed for user {user_id}: {message}")

        return CreditValidationResult(
            has_sufficient_credits=has_sufficient_credits,
            current_balance=current_balance,
            required_credits=required_credits_float,
            remaining_balance_after_purchase=remaining_balance,
            shortfall=shortfall,
            can_proceed=has_sufficient_credits,
            message=message,
        )

    except HTTPException:
        # Re-raise HTTPExceptions (these are intentional)
        raise
    except Exception as e:
        log_error(f"Error validating credits for user {user_id}: {e}")
        raise envelope_exception(ErrorCode.CREDIT_VALIDATION_FAILED, status=500, locale="en") from None


def handle_insufficient_credits(
    user_id: UUID, required_credits: float, current_balance: float
) -> InsufficientCreditsResponse:
    """
    Handle insufficient credits scenario with user-friendly response.

    Args:
        user_id: User ID (for logging)
        required_credits: Credits required for the vianda
        current_balance: User's current balance

    Returns:
        InsufficientCreditsResponse with payment instructions
    """
    shortfall = required_credits - current_balance

    # Generate user-friendly message
    if current_balance == 0:
        message = f"You have no credits remaining. This vianda costs {required_credits} credits."
    else:
        message = f"You have {current_balance} credits, but this vianda costs {required_credits} credits. You need {shortfall} more credits."

    # Payment instructions (supports both current and future payment methods)
    payment_instructions = _get_payment_instructions(shortfall)

    log_info(f"Generated insufficient credits response for user {user_id}: {message}")

    return InsufficientCreditsResponse(
        message=message,
        current_balance=current_balance,
        required_credits=required_credits,
        shortfall=shortfall,
        payment_instructions=payment_instructions,
        retry_after_payment=True,
    )


def _get_payment_instructions(shortfall: float) -> str:
    """
    Get user-friendly payment instructions based on available payment methods.

    Currently supports QR code payments, but designed to support future methods.
    """
    return (
        f"To add {shortfall} credits to your account:\n"
        f"1. Visit the payment page and scan the QR code\n"
        f"2. Complete your payment\n"
        f"3. Return here to retry your vianda selection\n"
        f"Your order will be available immediately after payment."
    )


def get_user_balance(user_id: UUID, db: psycopg2.extensions.connection) -> float | None:
    """
    Get user's current credit balance.

    Args:
        user_id: User ID to check
        db: Database connection

    Returns:
        Current balance as float, or None if not found
    """
    try:
        subscription = subscription_service.get_by_user(user_id, db)
        return float(subscription.balance) if subscription else None
    except Exception as e:
        log_error(f"Error getting balance for user {user_id}: {e}")
        return None
