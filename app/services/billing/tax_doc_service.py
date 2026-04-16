# app/services/billing/tax_doc_service.py
"""
Tax document generation for institution bills (supplier payouts).
Stub implementation: returns a placeholder external id; country-specific
integrations (e.g. e-invoicing) can be added later.
"""

from uuid import UUID

from app.services.crud_service import institution_bill_service
from app.utils.log import log_info


def issue_tax_doc_for_bill(
    institution_bill_id: UUID,
    country_code: str,
    connection=None,
) -> str | None:
    """
    Generate (or stub) a tax document for an institution bill and store
    the external id on the bill. Returns the tax_doc_external_id, or None on failure.
    """
    # Stub: placeholder id; replace with country-specific e-invoicing when needed
    external_id = f"TAX-STUB-{str(institution_bill_id)[:8].upper()}-{country_code.upper()}"
    try:
        institution_bill_service.update(
            institution_bill_id,
            {"tax_doc_external_id": external_id},
            connection,
            commit=(connection is None),
        )
        log_info(f"Tax doc stub issued for bill {institution_bill_id}: {external_id}")
        return external_id
    except Exception as e:
        log_info(f"Tax doc stub failed for bill {institution_bill_id}: {e}")
        return None
