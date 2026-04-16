"""
Reusable Query Parameters

This module provides common query parameters used across multiple routes
to eliminate duplication and ensure consistency.
"""

from uuid import UUID

from fastapi import Query


# Common filter query parameters
def institution_entity_filter() -> UUID | None:
    """Filter by institution entity ID"""
    return Query(None, description="Filter by institution entity ID")


def institution_filter() -> UUID | None:
    """Filter by institution ID"""
    return Query(None, description="Filter by institution ID")


def restaurant_filter() -> UUID | None:
    """Filter by restaurant ID"""
    return Query(None, description="Filter by restaurant ID")


def status_filter() -> str | None:
    """Filter by status"""
    return Query(None, description="Filter by status")


def market_filter() -> UUID | None:
    """Filter by market ID"""
    return Query(None, description="Filter by market ID")


def currency_code_filter() -> str | None:
    """Filter by currency code (e.g. ARS, USD)"""
    return Query(None, description="Filter by currency code (e.g. ARS, USD)")


def limit_query(default: int = 10, min_val: int = 1, max_val: int = 100) -> int:
    """
    Standard limit query parameter for pagination.

    Args:
        default: Default limit value
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Query parameter for limiting results
    """
    return Query(
        default, ge=min_val, le=max_val, description=f"Maximum number of results (between {min_val} and {max_val})"
    )
