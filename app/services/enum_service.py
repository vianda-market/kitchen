"""
Enum Service

Service for retrieving all system enum values.
Provides a centralized way to access all enum values used throughout the system,
primarily for frontend dropdown population.
"""

from typing import Any

from app.config.enums import (
    AddressType,
    BillPayoutStatus,
    BillResolution,
    DiscretionaryReason,
    DiscretionaryStatus,
    FavoriteEntityType,
    KitchenDay,
    PaymentMethodType,
    PickupType,
    PortionSizeDisplay,
    RoleName,
    RoleType,
    Status,
    StreetType,
    SubscriptionStatus,
    TransactionType,
)
from app.config.enums.dietary_flags import DietaryFlag
from app.security.field_policies import (
    SUPPLIER_ALLOWED_ROLE_NAMES,
    SUPPLIER_ALLOWED_USER_ROLE_TYPES,
)


class EnumService:
    """
    Service for retrieving all system enum values.

    This service provides a centralized way to access all enum values
    used throughout the system, primarily for frontend dropdown population.
    """

    @staticmethod
    def get_all_enums(current_user: dict | None = None) -> dict[str, list[str]]:
        """
        Get all enum values as a dictionary.

        When current_user is a Customer, role_type and role_name are omitted
        (Customers cannot read roles).

        Args:
            current_user: Optional authenticated user dict; when role_type=Customer,
                role_type and role_name are excluded from the response.

        Returns:
            Dictionary mapping enum type names to their valid values.
        """
        enums = {
            "status": Status.get_by_context("general"),
            "status_user": Status.get_by_context("user"),
            "status_restaurant": Status.get_by_context("restaurant"),
            "status_discretionary": DiscretionaryStatus.values(),
            "status_vianda_pickup": Status.get_by_context("vianda_pickup"),
            "status_bill": Status.get_by_context("bill"),
            "address_type": AddressType.values(),
            "role_type": [rt.value for rt in RoleType],  # User role_type: Internal, Supplier, Customer, Employer
            "institution_type": RoleType.values(),  # Institution type: includes Employer (benefits-program institutions)
            "role_name": RoleName.values(),
            "subscription_status": SubscriptionStatus.values(),
            "method_type": PaymentMethodType.values(),
            "transaction_type": TransactionType.values(),
            "street_type": StreetType.values(),
            "kitchen_day": KitchenDay.values(),
            "pickup_type": PickupType.values(),
            "discretionary_reason": DiscretionaryReason.values(),
            "bill_resolution": BillResolution.values(),
            "bill_payout_status": BillPayoutStatus.values(),
            "favorite_entity_type": FavoriteEntityType.values(),
            "portion_size_display": PortionSizeDisplay.values(),
            "dietary_flag": DietaryFlag.values(),
        }
        if current_user and (current_user.get("role_type") or "").strip().lower() == "customer":
            enums.pop("role_type", None)
            enums.pop("institution_type", None)
            enums.pop("role_name", None)
        else:
            assignable = EnumService.get_assignable_institution_types(current_user or {})
            enums["institution_type_assignable"] = assignable
        return enums

    @staticmethod
    def get_enum_by_name(
        enum_name: str,
        current_user: dict | None = None,
        context: str | None = None,
    ) -> list[str]:
        """
        Get values for a specific enum type, optionally scoped by context (for status).

        When current_user is a Customer and enum_name is role_type or role_name,
        raises ValueError (Customers cannot read roles).

        For enum_name 'status', context restricts to a subset (e.g. 'user' -> Active/Inactive).
        Use context='user' for user edit forms so only Active/Inactive are returned.

        Args:
            enum_name: Name of the enum type (e.g., 'status', 'role_type')
            current_user: Optional authenticated user; Customers get error for role enums
            context: Optional context for status enum (e.g. 'user', 'discretionary', 'vianda_pickup', 'bill')

        Returns:
            List of valid values for the enum

        Raises:
            ValueError: If enum_name is not recognized or Customer requests role_type/role_name
        """
        if current_user and (current_user.get("role_type") or "").strip().lower() == "customer":
            if enum_name in ("role_type", "role_name", "institution_type"):
                raise ValueError("Customers cannot read role or institution type enums")
        all_enums = EnumService.get_all_enums(current_user)
        if enum_name == "status" and context:
            if context == "discretionary":
                return DiscretionaryStatus.values()
            values = Status.get_by_context(context)
            if values:
                return values
            # unknown context: fall back to general
            return Status.get_by_context("general")
        if enum_name not in all_enums:
            raise ValueError(f"Unknown enum type: {enum_name}")
        return all_enums[enum_name]

    @staticmethod
    def get_assignable_roles(current_user: dict) -> dict[str, Any]:
        """
        Get assignable role_type and role_name values based on the current user.

        - Internal: Full set per RoleName.get_valid_for_role_type()
        - Supplier: role_type Supplier only; role_name Admin, Manager, Operator
        - Customer: Should not reach (route blocks with 403)

        Returns:
            Dict with keys: role_type (list), role_name_by_role_type (dict mapping
            role_type -> list of role_name values)
        """
        # role_type from JWT is always a string; ensure we have one for consistent comparison
        raw = str(current_user.get("role_type") or "").strip()
        # Normalize to canonical role: JWT may have different casing; compare case-insensitively
        raw_lower = raw.lower()
        if raw_lower == "internal":
            actor_role = "internal"
        elif raw_lower == "supplier":
            actor_role = "supplier"
        elif raw_lower == "customer":
            actor_role = "customer"
        elif raw_lower == "employer":
            actor_role = "employer"
        else:
            actor_role = (
                raw_lower
                if raw_lower in ("internal", "supplier", "customer", "employer")
                else (raw.lower() if raw else "")
            )

        if actor_role == "internal":
            # User role_type: internal, supplier, customer, employer (all four)
            role_types = [rt.value for rt in RoleType]
            role_name_by_role_type = {rt.value: RoleName.get_valid_for_role_type(rt) for rt in RoleType}
            return {
                "role_type": role_types,
                "role_name_by_role_type": role_name_by_role_type,
            }
        if actor_role == "supplier":
            role_types = list(SUPPLIER_ALLOWED_USER_ROLE_TYPES)
            role_name_by_role_type = {}
            for rt_str in role_types:
                rt = RoleType(rt_str)
                valid_names = RoleName.get_valid_for_role_type(rt)
                role_name_by_role_type[rt_str] = [n for n in valid_names if n in SUPPLIER_ALLOWED_ROLE_NAMES]
            return {
                "role_type": role_types,
                "role_name_by_role_type": role_name_by_role_type,
            }
        return {"role_type": [], "role_name_by_role_type": {}}

    @staticmethod
    def get_assignable_institution_types(current_user: dict) -> list[str]:
        """
        Get institution types the current user can create/assign when creating or editing institutions.

        - Super Admin: Internal, Supplier, Customer, Employer (all four)
        - Admin: Supplier, Employer only (Internal and Customer restricted to Super Admin)
        - Supplier: [] (Suppliers do not create institutions)
        - Customer: [] (Customers do not create institutions)

        Use this for the institution create/edit form dropdown.
        """
        role_type = str(current_user.get("role_type") or "").strip()
        role_name = str(current_user.get("role_name") or "").strip()

        if role_type.lower() != "internal":
            return []

        if role_name.lower() == "super_admin":
            return RoleType.values()

        if role_name.lower() == "admin":
            return [rt.value for rt in RoleType if rt not in (RoleType.INTERNAL, RoleType.CUSTOMER)]

        return []


# Singleton instance
enum_service = EnumService()
