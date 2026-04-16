"""
Backward compatibility module for InstitutionScope.

This module re-exports InstitutionScope and get_institution_scope from the
centralized scoping module to maintain backward compatibility with existing imports.
"""

# Re-export from centralized scoping module
from app.security.scoping import InstitutionScope, UserScope, get_institution_scope, get_user_scope

__all__ = ["InstitutionScope", "get_institution_scope", "UserScope", "get_user_scope"]
