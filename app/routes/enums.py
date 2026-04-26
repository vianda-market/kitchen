"""
Enum Routes

API endpoints for retrieving system enum values.
Provides centralized access to all valid enum values for frontend dropdowns.
"""

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse

from app.auth.dependencies import get_current_user, get_employee_or_supplier_user
from app.config.enums import DiscretionaryReason, Status
from app.config.settings import settings
from app.i18n.enum_labels import LABELED_ENUM_TYPES, labels_for_values
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import EnumsResponseSchema
from app.services.enum_service import enum_service
from app.utils.log import log_error, log_info

router = APIRouter(prefix="/enums", tags=["Enums"])


# Status variants (context-scoped subsets) share labels with the parent "status" enum.
_LABEL_SOURCE = {
    "status_user": "status",
    "status_restaurant": "status",
    "status_discretionary": "status",
    "status_plate_pickup": "status",
    "status_bill": "status",
}


def _enums_with_labels(flat: dict[str, list[str]], language: str) -> dict[str, dict]:
    """Map enum name -> {values, labels}; labeled enums use i18n maps, others use identity labels."""
    out: dict[str, dict] = {}
    for k, v in flat.items():
        if not isinstance(v, list):
            continue
        label_key = _LABEL_SOURCE.get(k, k)
        if label_key in LABELED_ENUM_TYPES:
            labels = labels_for_values(label_key, v, language)
        else:
            labels = {x: x for x in v}
        out[k] = {"values": v, "labels": labels}
    return out


@router.get("", response_model=EnumsResponseSchema)
async def get_all_enums(
    response: Response,
    language: str = Query(
        "en",
        description="Locale for enum display labels (en, es, pt). Canonical `values` are unchanged.",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Get all system enum values.

    **Authorization**: All authenticated users (Internal, Supplier, Customer, Employer)

    Returns all valid enum values used throughout the system, primarily
    for populating frontend dropdown menus and form validation.

    **Returns**: Dictionary mapping enum type names to their valid values

    **Caching**: This endpoint returns static configuration data.
    Frontend should cache for 1 hour to minimize API calls.

    **Example Response** (each key is `{ "values": [...], "labels": { code: display } }`):
    ```json
    {
        "status": { "values": ["active", "inactive"], "labels": { "active": "Active", ... } },
        "street_type": { "values": ["St", "Ave"], "labels": { "St": "Street", "Ave": "Avenue" } }
    }
    ```
    """
    if language not in settings.SUPPORTED_LOCALES:
        raise envelope_exception(
            ErrorCode.LOCALE_UNSUPPORTED, status=422, locale="en",
            lang=language, supported=", ".join(settings.SUPPORTED_LOCALES),
        )
    log_info(f"User {current_user.get('user_id')} fetching system enums (language={language})")

    try:
        enums = enum_service.get_all_enums(current_user=current_user)
        # Ensure context-scoped status keys are always in the response (user form uses status_user)
        enums["status_user"] = Status.get_by_context("user")
        enums["status_discretionary"] = Status.get_by_context("discretionary")
        enums["status_plate_pickup"] = Status.get_by_context("plate_pickup")
        enums["status_bill"] = Status.get_by_context("bill")
        # Ensure discretionary_reason is always present (discretionary request form category dropdown)
        enums["discretionary_reason"] = enums.get("discretionary_reason") or DiscretionaryReason.values()
        body = _enums_with_labels(dict(enums), language)
        log_info(f"Enums served successfully (keys: {list(body.keys())})")
        response.headers["Cache-Control"] = "public, max-age=3600"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return body
    except Exception as e:
        log_error(f"Error fetching enums: {str(e)}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en") from None


@router.get("/institution-types/assignable")
async def get_assignable_institution_types(current_user: dict = Depends(get_current_user)):
    """
    Get institution types the current user can create/assign in institution create/edit forms.

    **Authorization**: All authenticated users (response filtered by role).

    - **Super Admin**: Internal, Supplier, Customer, Employer (all four)
    - **Admin**: Supplier, Employer only (Internal and Customer restricted to Super Admin)
    - **Supplier** / **Customer**: [] (cannot create institutions)

    **Client recommendation**: Use this for the institution type dropdown in institution create/edit.
    Includes Employer (benefits-program institutions). Do not hardcode; use this enum.
    """
    try:
        result = enum_service.get_assignable_institution_types(current_user)
        return JSONResponse(
            content={"institution_type": result},
            headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"},
        )
    except Exception as e:
        log_error(f"Error fetching assignable institution types: {str(e)}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en") from None


@router.get("/roles/assignable")
async def get_assignable_roles(current_user: dict = Depends(get_employee_or_supplier_user)):
    """
    Get assignable role_type and role_name values for user create/edit forms.

    **Authorization**: Internal and Supplier only (403 for Customer).

    Returns role_type and role_name_by_role_type filtered by what the current
    user can assign. Suppliers see only Supplier role_type and Admin/Manager/Operator
    role_names. Internal users see the full set.

    **Response** (Supplier):
    {"role_type": ["supplier"], "role_name_by_role_type": {"supplier": ["admin", "manager", "operator"]}}

    **Response** (Internal): Full set per valid role combinations.
    """
    try:
        role_type_from_token = current_user.get("role_type")
        log_info(
            f"Assignable roles: user_id={current_user.get('user_id')} role_type={role_type_from_token!r} (type={type(role_type_from_token).__name__})"
        )
        result = enum_service.get_assignable_roles(current_user)
        return JSONResponse(
            content=result, headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"}
        )
    except Exception as e:
        log_error(f"Error fetching assignable roles: {str(e)}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en") from None


@router.get("/{enum_name}", response_model=list[str])
async def get_enum_by_name(enum_name: str, context: str | None = None, current_user: dict = Depends(get_current_user)):
    """
    Get values for a specific enum type.

    **Authorization**: All authenticated users (Internal, Supplier, Customer, Employer)

    **Path Parameters**:
    - `enum_name`: Name of the enum (e.g., 'status', 'role_type', 'subscription_status')

    **Query Parameters**:
    - `context`: Optional. For `enum_name=status`, restricts to a subset: `user` (Active/Inactive),
      `discretionary`, `plate_pickup`, `bill`. Use `context=user` for user edit forms.

    **Returns**: List of valid values for the requested enum

    **Caching**: Frontend should cache individual enum responses for 1 hour.

    **Example**: GET /api/v1/enums/status
    ```json
    ["active", "pending", "inactive"]
    ```
    **Example**: GET /api/v1/enums/status?context=user
    ```json
    ["active", "inactive"]
    ```

    **Error Responses**:
    - 404: Unknown enum type requested
    - 401: Not authenticated
    - 500: Server error
    """
    log_info(
        f"User {current_user.get('user_id')} fetching enum: {enum_name}" + (f" context={context}" if context else "")
    )

    try:
        enum_values = enum_service.get_enum_by_name(enum_name, current_user=current_user, context=context)

        return JSONResponse(
            content=enum_values,
            headers={
                "Cache-Control": "public, max-age=3600",  # 1 hour cache
                "X-Content-Type-Options": "nosniff",
            },
        )
    except ValueError as e:
        err_msg = str(e)
        if "cannot read role enums" in err_msg:
            raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=403, locale="en") from None
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale="en", entity=enum_name) from None
    except Exception as e:
        log_error(f"Error fetching enum {enum_name}: {str(e)}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en") from None
