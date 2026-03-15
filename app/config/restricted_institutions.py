# app/config/restricted_institutions.py
"""
Centralized validation for Vianda Customers and Vianda Enterprises institutions.

These two institutions must not be assigned to certain entities (e.g. products,
institution entities, restaurants). Use get_restricted_institution_ids() and
validate_institution_assignable() so all such checks share one rule and message.
"""
from typing import Optional
from uuid import UUID
from fastapi import HTTPException

from app.config.settings import get_vianda_customers_institution_id, get_vianda_enterprises_institution_id


# Tables where institution_id must NOT be Vianda Customers or Vianda Enterprises
RESTRICTED_INSTITUTION_TABLES = frozenset({
    "product_info",
    "institution_entity_info",
    "restaurant_info",
})


# Human-readable context for error messages (table_name -> context)
TABLE_CONTEXT_FOR_MESSAGE = {
    "product_info": "product",
    "institution_entity_info": "institution entity",
    "restaurant_info": "restaurant",
}


def get_restricted_institution_ids() -> tuple:
    """Return (Vianda Customers id, Vianda Enterprises id). Do not assign these to products, entities, or restaurants."""
    return (get_vianda_customers_institution_id(), get_vianda_enterprises_institution_id())


def validate_institution_assignable(institution_id: Optional[UUID], context: str = "record") -> None:
    """
    Raise HTTP 400 if institution_id is Vianda Customers or Vianda Enterprises.

    Use when assigning institution_id to products, institution entities, or restaurants.
    Does nothing if institution_id is None.

    Raises:
        HTTPException: 400 with a consistent message if institution is restricted.
    """
    if institution_id is None:
        return
    uid = institution_id if isinstance(institution_id, UUID) else UUID(str(institution_id))
    restricted = get_restricted_institution_ids()
    if uid in restricted:
        raise HTTPException(
            status_code=400,
            detail=f"Vianda Customers and Vianda Enterprises cannot be assigned to a {context}. Use a Supplier institution.",
        )
