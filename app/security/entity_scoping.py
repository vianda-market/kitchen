"""
Centralized Entity Scoping Service

This module provides a unified scoping determination system for all entities.
It ensures that base and enriched endpoints share the same scoping rules,
and provides a single source of truth for entity-specific scoping logic.

Usage:
    from app.security.entity_scoping import EntityScopingService
    
    scope = EntityScopingService.get_scope_for_entity("plate_kitchen_days", current_user)
    # Use scope for both base and enriched endpoints
"""

from typing import Optional
from fastapi import HTTPException, status

from app.security.scoping import InstitutionScope, get_institution_scope


# Entity Type Constants
ENTITY_PLATE_KITCHEN_DAYS = "plate_kitchen_days"
ENTITY_RESTAURANT_BALANCE = "restaurant_balance"
ENTITY_RESTAURANT_TRANSACTION = "restaurant_transaction"
ENTITY_PLATE_PICKUP_LIVE = "plate_pickup_live"
ENTITY_QR_CODE = "qr_code"
ENTITY_RESTAURANT = "restaurant"
ENTITY_PLATE = "plate"
ENTITY_PRODUCT = "product"
ENTITY_INSTITUTION_ENTITY = "institution_entity"
ENTITY_INSTITUTION_BILL = "institution_bill"
ENTITY_USER = "user"
ENTITY_ADDRESS = "address"
ENTITY_SUBSCRIPTION = "subscription"
ENTITY_RESTAURANT_HOLIDAY = "restaurant_holiday"


class EntityScopingService:
    """
    Centralized scoping determination for all entities.
    
    This service provides a single source of truth for entity-specific scoping rules,
    ensuring consistency between base and enriched endpoints.
    """
    
    # Registry of entity-specific scoping rules
    _SCOPING_RULES = {
        ENTITY_PLATE_KITCHEN_DAYS: "_scope_plate_kitchen_days",
        ENTITY_RESTAURANT_BALANCE: "_scope_restaurant_balance",
        ENTITY_RESTAURANT_TRANSACTION: "_scope_restaurant_transaction",
        ENTITY_PLATE_PICKUP_LIVE: "_scope_plate_pickup_live",
        ENTITY_QR_CODE: "_scope_qr_code",
        ENTITY_RESTAURANT: "_scope_restaurant",
        ENTITY_PLATE: "_scope_plate",
        ENTITY_PRODUCT: "_scope_product",
        ENTITY_INSTITUTION_ENTITY: "_scope_institution_entity",
        ENTITY_INSTITUTION_BILL: "_scope_institution_bill",
        ENTITY_USER: "_scope_user",
        ENTITY_ADDRESS: "_scope_address",
        ENTITY_SUBSCRIPTION: "_scope_subscription",
        ENTITY_RESTAURANT_HOLIDAY: "_scope_restaurant_holiday",
    }
    
    @staticmethod
    def get_scope_for_entity(
        entity_type: str,
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Get institution scope for a specific entity type.
        
        This method determines the appropriate scoping based on:
        - Entity type (each entity may have specific rules)
        - User role type (Internal, Supplier, Customer, Employer)
        - Special cases (e.g., Customer blocking)
        
        Args:
            entity_type: Entity identifier (use constants from this module)
            current_user: Current authenticated user dictionary
            **kwargs: Additional context (e.g., for user-level scoping)
            
        Returns:
            InstitutionScope or None (for global access)
            
        Raises:
            HTTPException: If access is forbidden (e.g., Customer trying to access restricted entity)
            
        Example:
            scope = EntityScopingService.get_scope_for_entity(
                EntityScopingService.ENTITY_PLATE_KITCHEN_DAYS,
                current_user
            )
        """
        rule_method_name = EntityScopingService._SCOPING_RULES.get(entity_type)
        
        if rule_method_name:
            # Use entity-specific scoping rule
            rule_method = getattr(EntityScopingService, rule_method_name, None)
            if rule_method:
                return rule_method(current_user, **kwargs)
        
        # Default: standard institution scoping
        return EntityScopingService._scope_default(current_user, **kwargs)
    
    @staticmethod
    def _scope_plate_kitchen_days(
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Scoping rules for plate_kitchen_days.
        
        Rules:
        - Customers: Blocked (403 Forbidden)
        - Internal Admin/Super Admin: Global access (None)
        - Internal Management: Institution-scoped
        - Internal Operator: Blocked (should not reach here - blocked in route)
        - Suppliers, Employer: Institution-scoped
        """
        role_type = current_user.get("role_type")
        role_name = current_user.get("role_name")
        
        # Block Customers
        if role_type == "Customer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Customers cannot access plate kitchen days"
            )
        
        # Employer: institution-scoped (like Supplier)
        if role_type == "Employer":
            return get_institution_scope(current_user)
        
        # Internal: check role_name for access level
        if role_type == "Internal":
            if role_name in ["Admin", "Super Admin"]:
                return None  # Global access
            elif role_name == "Manager":
                return get_institution_scope(current_user)  # Institution scope
            elif role_name == "Operator":
                # Internal Operators should be blocked in route layer
                # If they reach here, return None and let route handle 403
                return None
            else:
                # Unknown role_name - default to no access
                return None
        
        # Suppliers: institution-scoped
        if role_type == "Supplier":
            return get_institution_scope(current_user)
        
        # Default: no access
        return None
    
    @staticmethod
    def _scope_restaurant_balance(
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Scoping rules for restaurant_balance.
        
        Rules:
        - Internal Admin/Super Admin: Global access (None)
        - Internal Management: Institution-scoped
        - Internal Operator: Institution-scoped (limited access)
        - Suppliers, Employer: Institution-scoped
        - Customers: Standard institution scoping (typically not used, but allowed)
        """
        # get_institution_scope handles role_name logic automatically
        return get_institution_scope(current_user)
    
    @staticmethod
    def _scope_restaurant_transaction(
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Scoping rules for restaurant_transaction.
        
        Rules:
        - Internal Admin/Super Admin: Global access (None)
        - Internal Management: Institution-scoped
        - Internal Operator: Institution-scoped (limited access)
        - Suppliers, Employer: Institution-scoped
        - Customers: Standard institution scoping (typically not used, but allowed)
        """
        # get_institution_scope handles role_name logic automatically
        return get_institution_scope(current_user)
    
    @staticmethod
    def _scope_plate_pickup_live(
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Scoping rules for plate_pickup_live.
        
        Rules:
        - Internal Admin/Super Admin: Global access (None)
        - Internal Management: Institution-scoped
        - Internal Operator: Institution-scoped (limited access)
        - Suppliers, Employer: Institution-scoped
        - Customers: Standard institution scoping (user-level filtering handled in service)
        
        Note: Customer user-level filtering is handled in the service layer,
        not in the scope itself. The scope is still returned for consistency.
        """
        # get_institution_scope handles role_name logic automatically
        return get_institution_scope(current_user)
    
    @staticmethod
    def _scope_qr_code(
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Scoping rules for qr_code.
        
        Rules:
        - Internal Admin/Super Admin: Global access (None)
        - Internal Management: Institution-scoped
        - Internal Operator: Institution-scoped (limited access)
        - Suppliers, Employer: Institution-scoped
        - Customers: Standard institution scoping (typically not used, but allowed)
        """
        # get_institution_scope handles role_name logic automatically
        return get_institution_scope(current_user)
    
    @staticmethod
    def _scope_restaurant(
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Scoping rules for restaurant.
        
        Rules:
        - Internal Admin/Super Admin: Global access (None)
        - Internal Management: Institution-scoped
        - Internal Operator: Institution-scoped (limited access)
        - Suppliers: Institution-scoped
        - Customers: Standard institution scoping (typically not used, but allowed)
        """
        # get_institution_scope handles role_name logic automatically
        return get_institution_scope(current_user)
    
    @staticmethod
    def _scope_plate(
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Scoping rules for plate.
        
        Rules:
        - Internal Admin/Super Admin: Global access (None)
        - Internal Management: Institution-scoped
        - Internal Operator: Institution-scoped (limited access)
        - Suppliers, Employer: Institution-scoped
        - Customers: No scoping (can view all plates)
        """
        role_type = current_user.get("role_type")
        
        # Customers: no scoping (can view all plates)
        if role_type == "Customer":
            return None
        
        # Internal, Suppliers, Employer: standard institution scoping
        # get_institution_scope handles role_name logic automatically
        return get_institution_scope(current_user)
    
    @staticmethod
    def _scope_product(
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Scoping rules for product.
        
        Rules:
        - Internal Admin/Super Admin: Global access (None)
        - Internal Management: Institution-scoped
        - Internal Operator: Institution-scoped (limited access)
        - Suppliers, Employer: Institution-scoped
        - Customers: Standard institution scoping (typically not used, but allowed)
        """
        # get_institution_scope handles role_name logic automatically
        return get_institution_scope(current_user)
    
    @staticmethod
    def _scope_institution_entity(
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Scoping rules for institution_entity.
        
        Rules:
        - Internal Admin/Super Admin: Global access (None)
        - Internal Management: Institution-scoped
        - Internal Operator: Institution-scoped (limited access)
        - Suppliers, Employer: Institution-scoped
        - Customers: Standard institution scoping (typically not used, but allowed)
        """
        # get_institution_scope handles role_name logic automatically
        return get_institution_scope(current_user)
    
    @staticmethod
    def _scope_institution_bill(
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Scoping rules for institution_bill.
        
        Rules:
        - Internal Admin/Super Admin: Global access (None)
        - Internal Management: Institution-scoped
        - Internal Operator: Institution-scoped (limited access)
        - Suppliers, Employer: Institution-scoped
        - Customers: Standard institution scoping (typically not used, but allowed)
        """
        # get_institution_scope handles role_name logic automatically
        return get_institution_scope(current_user)
    
    @staticmethod
    def _scope_user(
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Scoping rules for user.
        
        Rules:
        - Internal Admin/Super Admin: Global access (None)
        - Internal Management: Institution-scoped
        - Internal Operator: Blocked from managing others (use /me endpoints)
        - Suppliers, Employer: Institution-scoped
        - Customers: Standard institution scoping (user-level filtering handled in route)
        
        Note: Customer user-level filtering is handled in the route layer,
        not in the scope itself. Internal Operator blocking is handled in route layer.
        The scope is still returned for consistency.
        """
        role_type = current_user.get("role_type")
        role_name = current_user.get("role_name")
        
        if role_type == "Employer":
            return get_institution_scope(current_user)  # Institution-scoped like Supplier
        
        if role_type == "Internal":
            if role_name in ["Admin", "Super Admin"]:
                return None  # Global access
            elif role_name == "Manager":
                return get_institution_scope(current_user)  # Institution scope
            elif role_name == "Operator":
                # Internal Operators cannot manage other users
                # They should use /me endpoints for self-updates
                # For admin operations (managing others), return None and let route handle 403
                return None  # Will be blocked in route if trying to manage others
            else:
                # Unknown role_name - default to institution scope
                return get_institution_scope(current_user)
        
        # Suppliers and Customers: standard institution scoping
        # get_institution_scope handles role_name logic automatically
        return get_institution_scope(current_user)
    
    @staticmethod
    def _scope_address(
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Scoping rules for address.
        
        Rules:
        - Internal Admin/Super Admin: Global access (None)
        - Internal Management: Institution-scoped
        - Internal Operator: Institution-scoped (limited access, self-updates via /me)
        - Suppliers, Employer: Institution-scoped
        - Customers: Standard institution scoping (user-level filtering handled in route)
        
        Note: Customer user-level filtering is handled in the route layer,
        not in the scope itself. The scope is still returned for consistency.
        """
        # get_institution_scope handles role_name logic automatically
        return get_institution_scope(current_user)
    
    @staticmethod
    def _scope_subscription(
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Scoping rules for subscription.
        
        Rules:
        - Internal Admin/Super Admin: Global access (None)
        - Internal Management: Institution-scoped
        - Internal Operator: Institution-scoped (limited access)
        - Suppliers, Employer: Blocked (should not reach here - blocked in route)
        - Customers: User-level filtering (handled in route, not here)
        
        Note: This method is primarily for base CRUD routes. Enriched endpoints
        handle access control directly in the route layer.
        """
        role_type = current_user.get("role_type")
        role_name = current_user.get("role_name")
        
        if role_type == "Employer":
            return get_institution_scope(current_user)  # Institution-scoped like Supplier
        
        if role_type == "Internal":
            if role_name in ["Admin", "Super Admin"]:
                return None  # Global access
            elif role_name == "Manager":
                return get_institution_scope(current_user)  # Institution scope
            elif role_name == "Operator":
                # Internal Operators should be blocked in route layer
                # If they reach here, return None and let route handle 403
                return None
            else:
                # Unknown role_name - default to institution scope
                return get_institution_scope(current_user)
        elif role_type == "Supplier":
            # Suppliers should be blocked, but if they reach here, return None
            # (actual blocking happens in route layer)
            return None
        else:  # Customer
            # Customer access is handled via user_id filtering in route layer
            return None
    
    @staticmethod
    def _scope_restaurant_holiday(
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Scoping rules for restaurant_holiday.
        
        Rules:
        - Internal Admin/Super Admin: Global access (None)
        - Internal Management: Institution-scoped
        - Internal Operator: Institution-scoped (limited access)
        - Suppliers: Institution-scoped (via restaurant)
        - Customers: Blocked (403 Forbidden)
        """
        role_type = current_user.get("role_type")
        
        # Block Customers
        if role_type == "Customer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Customers cannot access restaurant holidays"
            )
        
        # Internal, Suppliers, Employer: standard institution scoping
        # get_institution_scope handles role_name logic automatically
        return get_institution_scope(current_user)
    
    @staticmethod
    def _scope_default(
        current_user: dict,
        **kwargs
    ) -> Optional[InstitutionScope]:
        """
        Default scoping rule for entities without specific rules.
        
        Rules:
        - Internal Admin/Super Admin: Global access (None)
        - Internal Management: Institution-scoped
        - Internal Operator: Institution-scoped (limited access)
        - Suppliers: Institution-scoped
        - Customers: Standard institution scoping
        """
        # get_institution_scope handles role_name logic automatically
        return get_institution_scope(current_user)

