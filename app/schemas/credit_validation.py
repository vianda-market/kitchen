"""
Credit Validation Schemas

Pydantic schemas for credit validation responses and error handling.
"""

from pydantic import BaseModel, ConfigDict, Field


class InsufficientCreditsResponseSchema(BaseModel):
    """User-friendly response schema for insufficient credits scenario"""

    error_type: str = Field(default="insufficient_credits", description="Type of error")
    message: str = Field(..., description="User-friendly error message")
    current_balance: float = Field(..., ge=0, description="User's current credit balance")
    required_credits: float = Field(..., gt=0, description="Credits required for the vianda")
    shortfall: float = Field(..., ge=0, description="Additional credits needed")
    payment_instructions: str = Field(..., description="Instructions for adding credits")
    retry_after_payment: bool = Field(default=True, description="Whether user can retry after payment")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_type": "insufficient_credits",
                "message": "You have 2.0 credits, but this vianda costs 5.0 credits. You need 3.0 more credits.",
                "current_balance": 2.0,
                "required_credits": 5.0,
                "shortfall": 3.0,
                "payment_instructions": "To add 3.0 credits to your account:\n1. Visit the payment page and scan the QR code\n2. Complete your payment\n3. Return here to retry your vianda selection\nYour order will be available immediately after payment.",
                "retry_after_payment": True,
            }
        }
    )


class CreditValidationResultSchema(BaseModel):
    """Schema for credit validation result (internal use)"""

    has_sufficient_credits: bool = Field(..., description="Whether user has sufficient credits")
    current_balance: float = Field(..., ge=0, description="User's current balance")
    required_credits: float = Field(..., gt=0, description="Credits required")
    remaining_balance_after_purchase: float = Field(..., description="Balance after purchase")
    shortfall: float = Field(default=0.0, ge=0, description="Credits shortfall if insufficient")
    can_proceed: bool = Field(default=True, description="Whether the operation can proceed")
    message: str = Field(default="", description="Validation message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "has_sufficient_credits": True,
                "current_balance": 10.0,
                "required_credits": 5.0,
                "remaining_balance_after_purchase": 5.0,
                "shortfall": 0.0,
                "can_proceed": True,
                "message": "Sufficient credits available. Current: 10.0, Required: 5.0, Remaining: 5.0",
            }
        }
    )
