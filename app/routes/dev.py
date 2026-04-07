# app/routes/dev.py
"""
Dev-only endpoints for integration testing. All routes guarded by DEV_MODE.
Never enable DEV_MODE in production.
"""
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, HTTPException, Depends, Body

from app.auth.dependencies import get_current_user, oauth2_scheme
from app.config.settings import settings
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import InstitutionBillPayoutResponseSchema

router = APIRouter(
    prefix="/dev",
    tags=["Dev"],
    dependencies=[Depends(oauth2_scheme)],
)


def _require_dev_mode() -> None:
    if not settings.DEV_MODE:
        raise HTTPException(status_code=403, detail="This endpoint is only available in DEV_MODE")


def _get_connect_gateway():
    if (settings.SUPPLIER_PAYOUT_PROVIDER or "mock").lower() == "stripe":
        from app.services.payment_provider.stripe import connect_gateway
        return connect_gateway
    from app.services.payment_provider.stripe import connect_mock
    return connect_mock


@router.post("/trigger-test-payout", response_model=InstitutionBillPayoutResponseSchema)
def trigger_test_payout(
    institution_bill_id: UUID = Body(..., embed=True),
    entity_id: UUID = Body(..., embed=True),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Trigger a test payout for e2e integration testing in sandbox.
    Guarded by DEV_MODE — returns 403 in production.
    """
    _require_dev_mode()
    gw = _get_connect_gateway()
    payout_row = gw.execute_supplier_payout(
        institution_bill_id=institution_bill_id,
        entity_id=entity_id,
        current_user_id=UUID(str(current_user["user_id"])),
        db=db,
    )
    return InstitutionBillPayoutResponseSchema(**payout_row)
