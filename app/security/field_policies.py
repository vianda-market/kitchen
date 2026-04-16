"""
Field-level access policies for shared APIs (Addresses, Users, Institution Entities).

These enforce which values are allowed per role_type when creating/updating
resources that multiple roles can access. Route-level access is handled by
auth dependencies (get_employee_user, etc.); this module handles payload rules
and Supplier role restrictions (e.g. Admin-only vs Manager read-only).
"""

from typing import Any

from fastapi import HTTPException, status

# Supplier may only use these address types (no customer-facing types on main address API)
SUPPLIER_ALLOWED_ADDRESS_TYPES = {"restaurant", "entity_billing", "entity_address"}

# Customer may only use these address types (if we enforce; currently optional)
CUSTOMER_ALLOWED_ADDRESS_TYPES = {"customer_home", "customer_billing", "customer_employer"}

# Customer address types are allowed for institutions with institution_type = Customer or Employer
CUSTOMER_INSTITUTION_ADDRESS_TYPES = {"customer_home", "customer_billing", "customer_employer"}
# Entity/restaurant address types are for Supplier or Internal institutions only (not Customer/Employer)
ENTITY_INSTITUTION_ADDRESS_TYPES = {"restaurant", "entity_billing", "entity_address"}

# Supplier may create/update users with these role_types only (Supplier only, not Internal or Customer)
SUPPLIER_ALLOWED_USER_ROLE_TYPES = {"supplier"}

# B2B POST /users: Customers cannot be created here; they must self-register via POST /customers/signup/request and /verify.
# Internal creates Internal, Supplier, Employer; Supplier creates Supplier only.
B2B_CREATABLE_ROLE_TYPES = {"internal", "supplier", "employer"}

# Supplier may assign these role_names only (excludes Super Admin, Comensal)
SUPPLIER_ALLOWED_ROLE_NAMES = {"admin", "manager", "operator"}

# Supplier roles that can create/edit/delete addresses (Admin and Manager)
SUPPLIER_ADDRESS_MUTATION_ROLES = {"admin", "manager"}

# Supplier roles that can create/edit users (Admin and Manager)
SUPPLIER_USER_MUTATION_ROLES = {"admin", "manager"}

# Supplier roles that can access CRUD management routes (Admin and Manager). Operator is kiosk-only.
SUPPLIER_MANAGEMENT_ROLES = {"admin", "manager"}

# Institution bank accounts and institution entities: only Supplier Admin can access (GET, POST, PUT, DELETE)
SUPPLIER_ADMIN_ONLY_ROLES = {"admin"}

# Supplier terms: only Internal Manager, Global Manager, Admin, or Super Admin can edit
SUPPLIER_TERMS_EDIT_ROLES = {"manager", "global_manager", "admin", "super_admin"}


def ensure_can_edit_supplier_terms(current_user: dict) -> None:
    """Raise 403 if user cannot edit supplier terms."""
    role_type = (current_user.get("role_type") or "").strip()
    role_name = (current_user.get("role_name") or "").strip()
    if role_type != "internal":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Internal users with Manager, Global Manager, Admin, or Super Admin role can edit supplier terms.",
        )
    if role_name not in SUPPLIER_TERMS_EDIT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Manager, Global Manager, Admin, or Super Admin can edit supplier terms.",
        )


def ensure_address_type_allowed(
    address_type_list: list,
    current_user: dict,
    *,
    employer_context: bool = False,
) -> None:
    """
    Raise 403 if the current user's role_type is not allowed to submit the given address_type list.

    - Supplier: only Restaurant, Entity Billing, Entity Address; when employer_context=True,
      Customer Employer is also allowed (for employer addresses).
    - Customer: only Customer Home, Customer Billing, Customer Employer (Comensal cannot create Restaurant or entity addresses).
    - Internal: no restriction.
    """
    if not address_type_list:
        return
    role_type = (current_user.get("role_type") or "").strip()
    if role_type == "internal":
        return
    if role_type == "supplier":
        allowed = set(SUPPLIER_ALLOWED_ADDRESS_TYPES)
        if employer_context:
            allowed = allowed | {"customer_employer"}
        types_set = {t if isinstance(t, str) else getattr(t, "value", str(t)) for t in address_type_list}
        disallowed = types_set - allowed
        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Suppliers may only use address types: Restaurant, Entity Billing, Entity Address. "
                    f"Disallowed: {', '.join(sorted(disallowed))}."
                ),
            )
        return
    if role_type == "customer":
        allowed = set(CUSTOMER_ALLOWED_ADDRESS_TYPES)
        types_set = {t if isinstance(t, str) else getattr(t, "value", str(t)) for t in address_type_list}
        disallowed = types_set - allowed
        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Customers may only use address types: Customer Home, Customer Billing, Customer Employer. "
                    f"Disallowed: {', '.join(sorted(disallowed))}."
                ),
            )
        return


def ensure_address_type_matches_institution_type(
    address_type_list: list,
    institution_type: str,
) -> None:
    """
    Raise 400 if address types are used with the wrong institution type.

    - Customer Home, Customer Billing, Customer Employer: only allowed when institution_type is 'Customer' or 'Employer'
      (e.g. Vianda Customers or Employer institutions). Not allowed for Supplier or Internal institutions.
    - Restaurant, Entity Billing, Entity Address: only allowed when institution_type is 'Supplier' or 'Internal'.
      Not allowed for Customer or Employer institutions.
    """
    if not address_type_list or not institution_type:
        return
    inst_type = (
        institution_type
        if isinstance(institution_type, str)
        else getattr(institution_type, "value", str(institution_type))
    ).strip()
    types_set = {t if isinstance(t, str) else getattr(t, "value", str(t)) for t in address_type_list}
    has_customer_types = bool(types_set & CUSTOMER_INSTITUTION_ADDRESS_TYPES)
    has_entity_types = bool(types_set & ENTITY_INSTITUTION_ADDRESS_TYPES)
    if has_customer_types and inst_type not in ("customer", "employer"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Address types Customer Home, Customer Billing, and Customer Employer are only allowed "
                "for Customer or Employer institutions. This institution is not a Customer/Employer institution."
            ),
        )
    if has_entity_types and inst_type in ("customer", "employer"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Address types Restaurant, Entity Billing, and Entity Address are not allowed "
                "for Customer or Employer institutions. Use a Supplier or Internal institution for those address types."
            ),
        )


def ensure_user_role_type_allowed(
    role_type: str,
    current_user: dict,
    action: str = "create",
) -> None:
    """
    Raise 403 if the current user is not allowed to create/update a user with the given role_type.

    - Supplier: may only set role_type to Supplier (cannot create/assign Internal or Customer).
    - Internal: may set any role_type (Internal, Supplier, Employer).
    - Customer: cannot create users (enforced at route level).
    """
    if not role_type:
        return
    role_type_str = role_type if isinstance(role_type, str) else getattr(role_type, "value", str(role_type))
    actor_role = (current_user.get("role_type") or "").strip()
    if actor_role == "internal":
        return
    if actor_role == "supplier":
        allowed = set(SUPPLIER_ALLOWED_USER_ROLE_TYPES)
        if role_type_str not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Suppliers cannot create or update users to Internal or Customer. "
                    "Allowed role types: Supplier only."
                ),
            )


def ensure_user_role_name_allowed(
    role_type: str,
    role_name: str,
    current_user: dict,
    action: str = "create",
) -> None:
    """
    Raise 403 if the current user is not allowed to create/update a user with the given role_name.

    - Supplier: may only set role_name to Admin, Manager, or Operator (cannot assign Super Admin).
    - Internal: may set any role_name (further restricted by ensure_can_assign_role_name).
    - Customer: cannot create users (enforced at route level).
    """
    if not role_name:
        return
    role_name_str = role_name if isinstance(role_name, str) else getattr(role_name, "value", str(role_name))
    actor_role = (current_user.get("role_type") or "").strip()
    if actor_role == "internal":
        return
    if actor_role == "supplier":
        if role_name_str not in SUPPLIER_ALLOWED_ROLE_NAMES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Suppliers cannot assign Super Admin or Comensal. "
                    f"Allowed role names: {', '.join(sorted(SUPPLIER_ALLOWED_ROLE_NAMES))}."
                ),
            )


def ensure_operator_cannot_create_users(current_user: dict) -> None:
    """
    Raise 403 if the current user is an Operator who cannot create users.

    - Internal Operator: Cannot create users (403).
    - Supplier Operator: Cannot create users (403; also blocked by ensure_supplier_can_create_edit_users).
    - All other roles: No restriction.
    """
    (current_user.get("role_type") or "").strip()
    role_name = (current_user.get("role_name") or "").strip()
    if role_name == "operator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Operator does not have permission to create or edit other users. "
                "Only Admin and Manager can manage user accounts."
            ),
        )


def ensure_can_assign_role_name(
    actor_role_type: Any,
    actor_role_name: Any,
    target_role_type: Any,
    target_role_name: Any,
) -> None:
    """
    Raise 403 if the actor cannot assign the given role_name to a user.

    Rules (for Internal and Supplier users):
    1. Super Admin: Only Super Admin (Internal) can assign Super Admin.
    2. Admin: Only Admin or Super Admin can assign Admin.
    3. Manager: Only Admin, Super Admin, or Manager can assign Manager.
    4. Operator: Only Admin, Super Admin, or Manager can assign Operator.

    Customer role_names (Comensal only) and Employer role_names (Admin, Manager, Comensal) are validated
    by ensure_user_role_name_allowed; only Internal can create Customer and Employer users.
    """

    def _str(v: Any) -> str:
        if v is None:
            return ""
        if hasattr(v, "value"):
            return str(v.value).strip()
        return str(v).strip()

    target_str = _str(target_role_name)
    actor_rt = _str(actor_role_type)
    actor_rn = _str(actor_role_name)
    target_rt = _str(target_role_type)

    # Customer (Comensal only) and Employer (Admin, Manager, Comensal): only Internal creates these; no further restriction here
    if target_rt == "customer" or target_rt == "employer" or target_str == "comensal":
        return

    if target_str == "super_admin":
        if not (actor_rt == "internal" and actor_rn == "super_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Super Admin can assign another user as Super Admin.",
            )
        return

    if target_str == "admin":
        if actor_rn not in ("admin", "super_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admin (or Super Admin) can assign another user as Admin.",
            )
        return

    # v2: Global Manager — only Super Admin, Admin, or Global Manager can assign; Global Manager can assign Global Manager only
    if target_str == "global_manager":
        if actor_rn not in ("admin", "super_admin", "global_manager"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admin, Super Admin, or Global Manager can assign Global Manager. Managers and Operators cannot.",
            )
        return
    if actor_rn == "global_manager":
        # Global Manager can only assign Global Manager (cannot create/assign Admin, Manager, Operator)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Global Manager can only create or assign Global Manager users.",
        )

    if target_str in ("manager", "operator"):
        if actor_rn not in ("admin", "super_admin", "manager"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admin, Super Admin, or Manager can assign Manager or Operator role.",
            )


def ensure_can_edit_user(
    actor_role_type: Any,
    actor_role_name: Any,
    target_role_type: Any,
    target_role_name: Any,
) -> None:
    """
    Raise 403 if the actor cannot edit the target user (prevents editing users above your level).

    Hierarchy: Super Admin > Admin > Manager > Operator

    - Manager cannot edit Admin or Super Admin (prevents downgrading Admin to Manager).
    - Admin cannot edit Super Admin (prevents downgrading Super Admin).
    - Operator cannot edit anyone (enforced elsewhere).
    """

    def _str(v: Any) -> str:
        if v is None:
            return ""
        if hasattr(v, "value"):
            return str(v.value).strip()
        return str(v).strip()

    actor_rt = _str(actor_role_type)
    actor_rn = _str(actor_role_name)
    target_rt = _str(target_role_type)
    target_rn = _str(target_role_name)

    # Only apply to Internal, Supplier, and Employer targets (hierarchy applies to these role types)
    if target_rt not in ("internal", "supplier", "employer"):
        return

    # Target Super Admin: only Super Admin can edit (Internal only)
    if target_rn == "super_admin":
        if not (actor_rt == "internal" and actor_rn == "super_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Super Admin can edit a Super Admin user.",
            )
        return

    # Target Admin: only Admin or Super Admin can edit (Manager cannot)
    if target_rn == "admin":
        if actor_rn not in ("admin", "super_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admin or Super Admin can edit an Admin user.",
            )
        return

    # v2: Target Global Manager — only Super Admin, Admin, or Global Manager can edit
    if target_rn == "global_manager":
        if actor_rn not in ("admin", "super_admin", "global_manager"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admin, Super Admin, or Global Manager can edit a Global Manager user.",
            )
        return
    # Actor is Global Manager: can only edit Global Manager (cannot edit Admin, Manager, Operator)
    if actor_rn == "global_manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Global Manager can only edit Global Manager users.",
        )

    # Target Manager, Operator: Admin, Super Admin, or Manager can edit
    if target_rn in ("manager", "operator"):
        if actor_rn not in ("admin", "super_admin", "manager"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admin, Super Admin, or Manager can edit Manager or Operator users.",
            )


def ensure_customer_cannot_edit_employer_address(
    existing_address: Any,
    current_user: dict,
) -> None:
    """
    Raise 403 if the current user is a Customer and the address is linked to an employer.

    Comensals who created an employer address must not be able to edit/delete it via
    PUT/DELETE, since that would affect other Comensals who use that address.
    employer_id is the source of truth (no need to inspect address_type).
    """
    role_type = (current_user.get("role_type") or "").strip()
    if role_type != "customer":
        return
    if existing_address and getattr(existing_address, "employer_id", None) is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customers cannot edit or delete employer addresses. Employer addresses are shared and managed by the employer.",
        )


def ensure_supplier_can_create_edit_addresses(current_user: dict) -> None:
    """
    Raise 403 if the current user is a Supplier who cannot create or edit addresses.

    - Supplier Admin, Supplier Manager: Can create/edit/delete addresses (full management).
    - Supplier Operator: Cannot create/edit/delete addresses (403); read-only.
    - Internal and Customers: No restriction (handled by other logic).
    """
    role_type = (current_user.get("role_type") or "").strip()
    if role_type != "supplier":
        return
    role_name = (current_user.get("role_name") or "").strip()
    if role_name not in SUPPLIER_ADDRESS_MUTATION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only Supplier Admin and Manager can create or edit addresses. "
                "Supplier Operator has read-only access to addresses."
            ),
        )


def ensure_supplier_can_create_edit_users(current_user: dict) -> None:
    """
    Raise 403 if the current user is a Supplier who cannot create or edit users.

    - Supplier Admin, Supplier Manager: Can create/edit users.
    - Supplier Operator: Cannot create/edit users (403).
    - All Supplier roles: Can GET users within institution scope (handled elsewhere).
    - Employees and Customers: No restriction (Customers cannot create users, enforced at route level).
    """
    role_type = (current_user.get("role_type") or "").strip()
    if role_type != "supplier":
        return
    role_name = (current_user.get("role_name") or "").strip()
    if role_name not in SUPPLIER_USER_MUTATION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only Supplier Admin and Manager can create or edit users. "
                "Supplier Operator has read-only access to users within their institution."
            ),
        )


def ensure_supplier_admin_or_manager(current_user: dict) -> None:
    """
    Block Supplier Operators from management/CRUD endpoints. Internal passes through.

    - Supplier Admin, Supplier Manager: Allowed (full CRUD management access).
    - Supplier Operator: Blocked (kiosk-only: daily orders, verify code, hand out, mark complete, view feedback).
    - Internal, Customer, Employer: No restriction from this check (handled by other guards).
    """
    role_type = (current_user.get("role_type") or "").strip()
    if role_type != "supplier":
        return
    role_name = (current_user.get("role_name") or "").strip()
    if role_name not in SUPPLIER_MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Supplier Operators can only access kiosk and field operations. "
                "Use Admin or Manager role for this action."
            ),
        )


def ensure_supplier_admin_only(current_user: dict) -> None:
    """
    Raise 403 if the current user is not a Supplier Admin.
    Used where only Supplier Admin is allowed (e.g. other flows).
    """
    role_type = (current_user.get("role_type") or "").strip()
    role_name = (current_user.get("role_name") or "").strip()
    if role_type != "supplier" or role_name not in SUPPLIER_ADMIN_ONLY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=("Only Supplier Admin can access this resource."),
        )


def ensure_supplier_can_reset_user_password(current_user: dict) -> None:
    """
    Raise 403 if the current user is a Supplier who cannot reset another user's password.

    - Supplier Admin, Supplier Manager: Can reset passwords for users in their institution scope.
    - Supplier Operator: Cannot reset other users' passwords (403), even within scope.
    - Internal and Customers: No restriction (Customers/Operators only for self, enforced in route).
    """
    role_type = (current_user.get("role_type") or "").strip()
    if role_type != "supplier":
        return
    role_name = (current_user.get("role_name") or "").strip()
    if role_name not in SUPPLIER_USER_MUTATION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only Supplier Admin and Manager can reset user passwords. "
                "Supplier Operator cannot reset other users' passwords."
            ),
        )


def _normalize_uuid(value) -> str:
    """Normalize UUID or str to string for comparison."""
    if value is None:
        return ""
    if hasattr(value, "hex"):
        return str(value).lower()
    return str(value).strip().lower()


def ensure_institution_type_matches_role_type(
    role_type: Any,
    institution_type: Any,
    *,
    context: str = "create",
) -> None:
    """
    Raise 400 if the institution's institution_type does not match the user's role_type.
    When creating a user: Internal users must be in an Internal institution,
    Customer users in a Customer or Employer institution, Supplier users in a Supplier institution,
    Employer users in an Employer institution.

    - institution_type and role_type must be compatible (data-driven, not hardcoded names).
    - Customer users may be in institution_type Customer (e.g. Vianda Customers) or Employer.
    - Call this after resolving institution_id to its institution_type (e.g. from DB).
    """
    if institution_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Institution type could not be resolved. The institution_id may be invalid.",
        )
    role_str = role_type.value if hasattr(role_type, "value") else str(role_type)
    inst_str = institution_type.value if hasattr(institution_type, "value") else str(institution_type)
    # Customer users may be in Customer or Employer institutions; others must match exactly
    if role_str == "customer" and inst_str in ("customer", "employer"):
        return
    if role_str == "employer" and inst_str == "employer":
        return
    if role_str != inst_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Institution type ({inst_str}) does not match user role type ({role_str}). "
                "Internal users must be in an Internal institution, Customer users in a Customer or Employer institution, "
                "Supplier users in a Supplier institution, Employer users in an Employer institution."
            ),
        )


def ensure_supplier_user_institution_only(
    institution_id: Any,
    current_user: dict,
    *,
    action: str = "create",
) -> None:
    """
    Raise 403 if the current user is a Supplier and the given institution_id
    is not their own institution. Suppliers may only create users for their own institution.

    - Supplier: institution_id must equal current_user's institution_id.
    - Internal: No restriction.
    - Customer: Cannot create users (enforced at route level).
    """
    role_type = (current_user.get("role_type") or "").strip()
    if role_type != "supplier":
        return
    if not institution_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="institution_id is required when creating a user.",
        )
    current_institution = current_user.get("institution_id")
    if not current_institution:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Suppliers can only add users to their own institution. Your account has no institution.",
        )
    if _normalize_uuid(institution_id) != _normalize_uuid(current_institution):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Suppliers can only add users to their own institution. The institution_id must match your institution.",
        )


def ensure_employer_not_for_supplier_employee(
    role_type: Any,
    employer_id: Any,
    *,
    context: str = "create",
) -> None:
    """
    Raise 400 if employer_id is set for a user with role_type Supplier, Internal, or Employer.
    Supplier, Internal, and Employer users do not have an employer_id; only Customer (Comensal) can.

    - Supplier, Internal, Employer: employer_id must be null/omitted.
    - Customer: employer_id is allowed.
    """
    if employer_id is None:
        return
    role_str = role_type.value if hasattr(role_type, "value") else str(role_type)
    if role_str in ("supplier", "internal", "employer"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employer is not applicable to Supplier, Internal, or Employer users. Only Customer (Comensal) users can have an employer.",
        )
