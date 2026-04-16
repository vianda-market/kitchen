from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.schemas.consolidated_schemas import (
    PhoneValidateRequestSchema,
    PhoneValidateResponseSchema,
)
from app.utils.phone import (
    _normalize_mobile_or_raise_value_error,
    format_mobile_for_display,
)

router = APIRouter(prefix="/phone", tags=["Phone"])


@router.post("/validate", response_model=PhoneValidateResponseSchema)
def validate_phone_number(
    payload: PhoneValidateRequestSchema,
    _current_user: dict = Depends(get_current_user),
) -> PhoneValidateResponseSchema:
    """
    Pre-validate a phone number without storing it.
    Always returns 200; the `valid` field indicates whether the number is valid.
    """
    try:
        e164 = _normalize_mobile_or_raise_value_error(payload.mobile_number, payload.country_code)
    except ValueError as exc:
        return PhoneValidateResponseSchema(valid=False, error=str(exc))

    if e164 is None:
        return PhoneValidateResponseSchema(valid=False, error="Phone number is required.")

    return PhoneValidateResponseSchema(
        valid=True,
        e164=e164,
        display=format_mobile_for_display(e164),
    )
