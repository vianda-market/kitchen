# app/routes/billing/payout.py
"""
Enriched payout endpoints. Entity-level view — bills aggregate across restaurants,
so payouts are scoped to institution/entity, not restaurant.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Response
import psycopg2.extensions

from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import BillPayoutEnrichedResponseSchema
from app.security.entity_scoping import EntityScopingService, ENTITY_INSTITUTION_BILL
from app.services.entity_service import get_enriched_bill_payouts
from app.services.error_handling import handle_business_operation
from app.utils.pagination import PaginationParams, get_pagination_params, set_pagination_headers

router = APIRouter(
    prefix="/payouts",
    tags=["Payouts"],
    dependencies=[Depends(oauth2_scheme)],
)


@router.get("/enriched", response_model=List[BillPayoutEnrichedResponseSchema])
def get_enriched_payouts(
    response: Response,
    pagination: Optional[PaginationParams] = Depends(get_pagination_params),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Get all bill payouts with enriched institution, entity, and billing period context.
    Sorted by created_at descending (newest first).

    Scoping:
    - Internal: all payouts across all institutions
    - Supplier: payouts for bills belonging to their institution
    """
    def _get():
        scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_BILL, current_user)
        return get_enriched_bill_payouts(
            db, scope=scope,
            page=pagination.page if pagination else None,
            page_size=pagination.page_size if pagination else None,
        )

    result = handle_business_operation(_get, "enriched bill payouts retrieval")
    set_pagination_headers(response, result)
    return result
