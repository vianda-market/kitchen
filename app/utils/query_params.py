"""
Reusable Query Parameters

This module provides common query parameters used across multiple routes
to eliminate duplication and ensure consistency.
"""

from fastapi import Query
from typing import Optional
from uuid import UUID

def include_archived_query(entity_name: str = "records") -> bool:
    """
    Standard include_archived query parameter for GET endpoints.
    
    Args:
        entity_name: The name of the entity for the description
        
    Returns:
        Query parameter for including archived records
    """
    return Query(
        False, 
        description=f"Include archived {entity_name} if true"
    )

def include_archived_optional_query(entity_name: str = "records") -> Optional[bool]:
    """
    Optional include_archived query parameter for GET endpoints.
    
    Args:
        entity_name: The name of the entity for the description
        
    Returns:
        Optional query parameter for including archived records
    """
    return Query(
        False, 
        description=f"Include archived {entity_name}"
    )

# Common filter query parameters
def institution_entity_filter() -> Optional[UUID]:
    """Filter by institution entity ID"""
    return Query(None, description="Filter by institution entity ID")

def institution_filter() -> Optional[UUID]:
    """Filter by institution ID"""
    return Query(None, description="Filter by institution ID")

def restaurant_filter() -> Optional[UUID]:
    """Filter by restaurant ID"""
    return Query(None, description="Filter by restaurant ID")

def status_filter() -> Optional[str]:
    """Filter by status"""
    return Query(None, description="Filter by status")

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
        default, 
        ge=min_val, 
        le=max_val, 
        description=f"Maximum number of results (between {min_val} and {max_val})"
    )
