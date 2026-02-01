# app/services/entity_service.py
"""
Entity-specific business logic services.

This file contains business logic functions for specific entities,
using the generic CRUD service for data operations. This separates
pure business logic from data access operations.

Benefits:
- Pure business logic functions
- Clear separation from CRUD operations
- Easy to test and maintain
- Reusable across different contexts
"""

from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
import psycopg2
from app.dto.models import UserDTO, ProductDTO, PlateDTO, InstitutionBillDTO, GeolocationDTO, EmployerDTO
from app.services.crud_service import (
    user_service, product_service, plate_service, institution_bill_service,
    address_service, employer_service, geolocation_service
)
from app.utils.log import log_info, log_warning, log_error
from app.utils.db import db_read
from fastapi import HTTPException
from app.security.institution_scope import InstitutionScope
from app.schemas.consolidated_schemas import UserEnrichedResponseSchema, InstitutionEntityEnrichedResponseSchema, AddressEnrichedResponseSchema, RestaurantEnrichedResponseSchema, QRCodeEnrichedResponseSchema, ProductEnrichedResponseSchema, PlateEnrichedResponseSchema, PlanEnrichedResponseSchema, SubscriptionEnrichedResponseSchema, PlatePickupEnrichedResponseSchema, InstitutionBillEnrichedResponseSchema, InstitutionBankAccountEnrichedResponseSchema, InstitutionPaymentAttemptEnrichedResponseSchema, RestaurantBalanceEnrichedResponseSchema, RestaurantTransactionEnrichedResponseSchema, PlateKitchenDayEnrichedResponseSchema, EmployerEnrichedResponseSchema
from app.schemas.payment_method import PaymentMethodEnrichedResponseSchema
from app.schemas.restaurant_holidays import RestaurantHolidayEnrichedResponseSchema
from app.schemas.payment_methods.fintech_link import FintechLinkEnrichedResponseSchema
from app.schemas.payment_methods.fintech_link_assignment import FintechLinkAssignmentEnrichedResponseSchema
from app.services.enriched_service import EnrichedService
from app.config import Status

# =============================================================================
# USER BUSINESS LOGIC
# =============================================================================

def get_user_by_username(
    username: str,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None
) -> Optional[UserDTO]:
    """
    Get user by username - business logic only.
    
    Args:
        username: Username to search for
        db: Database connection
        
    Returns:
        UserDTO if found, None otherwise
        
    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        return user_service.get_by_field("username", username, db, scope=scope)
    except Exception as e:
        log_error(f"Error getting user by username {username}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get user by username")

def get_user_by_email(
    email: str,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None
) -> Optional[UserDTO]:
    """
    Get user by email - business logic only.
    
    Args:
        email: Email to search for
        db: Database connection
        
    Returns:
        UserDTO if found, None otherwise
        
    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        return user_service.get_by_field("email", email, db, scope=scope)
    except Exception as e:
        log_error(f"Error getting user by email {email}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get user by email")

def create_user_with_validation(
    user_data: dict,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None
) -> UserDTO:
    """
    Create user with business validation - pure business logic.
    
    Args:
        user_data: User data dictionary
        db: Database connection
        
    Returns:
        Created UserDTO
        
    Raises:
        HTTPException: If validation fails
    """
    # Business validation
    if get_user_by_username(user_data["username"], db):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    if user_data.get("email") and get_user_by_email(user_data["email"], db):
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Create user using generic CRUD
    user = user_service.create(user_data, db, scope=scope)
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create user")
    
    return user

def get_users_by_institution(institution_id: UUID, db: psycopg2.extensions.connection) -> List[UserDTO]:
    """
    Get all users for an institution - business logic only.
    
    Args:
        institution_id: Institution ID
        db: Database connection
        
    Returns:
        List of UserDTOs
        
    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        all_users = user_service.get_all(db)
        
        # Filter by institution_id (business logic)
        institution_users = [
            user for user in all_users 
            if user.institution_id == institution_id
        ]
        
        # Sort by created_date DESC (business logic)
        institution_users.sort(key=lambda u: u.created_date, reverse=True)
        
        return institution_users
    except Exception as e:
        log_error(f"Error getting users by institution {institution_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get users for institution")

# Initialize EnrichedService instance for users
_user_enriched_service = EnrichedService(
    base_table="user_info",
    table_alias="u",
    id_column="user_id",
    schema_class=UserEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="u"  # institution_id is on the base table
)

def get_enriched_users(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[UserEnrichedResponseSchema]:
    """
    Get all users with enriched data (role_name, role_type, institution_name).
    Uses SQL JOINs to avoid N+1 queries.
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records
        
    Returns:
        List of enriched user schemas with role and institution names
    """
    return _user_enriched_service.get_enriched(
        db,
        select_fields=[
            "u.user_id",
            "u.institution_id",
            "i.name as institution_name",
            "u.role_type",
            "u.role_name",
            "u.username",
            "u.email",
            "u.first_name",
            "u.last_name",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as full_name",
            "u.cellphone",
            "u.employer_id",
            "u.is_archived",
            "u.status",
            "u.created_date",
            "u.modified_date"
        ],
        joins=[
            ("INNER", "institution_info", "i", "u.institution_id = i.institution_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

def get_enriched_user_by_id(
    user_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> Optional[UserEnrichedResponseSchema]:
    """
    Get a single user by ID with enriched data (role_name, role_type, institution_name).
    Uses SQL JOINs to avoid N+1 queries.
    
    Args:
        user_id: User ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records
        
    Returns:
        Enriched user schema with role and institution names, or None if not found
    """
    try:
        conditions = ["u.user_id = %s"]
        params: List[Any] = [str(user_id)]
        
        if not include_archived:
            conditions.append("u.is_archived = FALSE")
        
        if scope and not scope.is_global and scope.institution_id:
            conditions.append("u.institution_id = %s")
            params.append(scope.institution_id)
        
        query = f"""
            SELECT 
                u.user_id,
                u.institution_id,
                i.name as institution_name,
                u.role_type,
                u.role_name,
                u.username,
                u.email,
                u.first_name,
                u.last_name,
                TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as full_name,
                u.cellphone,
                u.employer_id,
                u.is_archived,
                u.status,
                u.created_date,
                u.modified_date
            FROM user_info u
            JOIN institution_info i ON u.institution_id = i.institution_id
            WHERE {' AND '.join(conditions)}
        """
        
        result = db_read(
            query,
            tuple(params),
            connection=db,
            fetch_one=True
        )
        
        if not result:
            return None
        
        enriched_user = UserEnrichedResponseSchema(**result)
        
        # Apply scope validation
        if scope and not scope.is_global:
            if not scope.matches(enriched_user.institution_id):
                return None
        
        return enriched_user
    except Exception as e:
        log_error(f"Error getting enriched user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get enriched user")

# =============================================================================
# INSTITUTION ENTITY BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for institution entities
_institution_entity_enriched_service = EnrichedService(
    base_table="institution_entity_info",
    table_alias="ie",
    id_column="institution_entity_id",
    schema_class=InstitutionEntityEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="ie"  # institution_id is on the base table
)

def get_enriched_institution_entities(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[InstitutionEntityEnrichedResponseSchema]:
    """
    Get all institution entities with enriched data (institution_name, address_country, address_province, address_city).
    Uses SQL JOINs to avoid N+1 queries.
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records
        
    Returns:
        List of enriched institution entity schemas with institution name and address details
    """
    return _institution_entity_enriched_service.get_enriched(
        db,
        select_fields=[
            "ie.institution_entity_id",
            "ie.institution_id",
            "i.name as institution_name",
            "ie.address_id",
            "a.country as address_country",
            "a.province as address_province",
            "a.city as address_city",
            "ie.tax_id",
            "ie.name",
            "ie.is_archived",
            "ie.status",
            "ie.created_date",
            "ie.modified_by",
            "ie.modified_date"
        ],
        joins=[
            ("INNER", "institution_info", "i", "ie.institution_id = i.institution_id"),
            ("INNER", "address_info", "a", "ie.address_id = a.address_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

def get_enriched_institution_entity_by_id(
    entity_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> Optional[InstitutionEntityEnrichedResponseSchema]:
    """
    Get a single institution entity by ID with enriched data (institution_name, address_country, address_province, address_city).
    Uses SQL JOINs to avoid N+1 queries.
    
    Args:
        entity_id: Institution entity ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records
        
    Returns:
        Enriched institution entity schema with institution name and address details, or None if not found
    """
    return _institution_entity_enriched_service.get_enriched_by_id(
        entity_id,
        db,
        select_fields=[
            "ie.institution_entity_id",
            "ie.institution_id",
            "i.name as institution_name",
            "ie.address_id",
            "a.country as address_country",
            "a.province as address_province",
            "a.city as address_city",
            "ie.tax_id",
            "ie.name",
            "ie.is_archived",
            "ie.status",
            "ie.created_date",
            "ie.modified_by",
            "ie.modified_date"
        ],
        joins=[
            ("INNER", "institution_info", "i", "ie.institution_id = i.institution_id"),
            ("INNER", "address_info", "a", "ie.address_id = a.address_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

# =============================================================================
# ADDRESS BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for addresses
_address_enriched_service = EnrichedService(
    base_table="address_info",
    table_alias="a",
    id_column="address_id",
    schema_class=AddressEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="a"  # institution_id is on the base table
)

def get_enriched_addresses(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[AddressEnrichedResponseSchema]:
    """
    Get all addresses with enriched data (institution_name, user_username, user_first_name, user_last_name).
    Uses SQL JOINs to avoid N+1 queries.
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records
        
    Returns:
        List of enriched address schemas with institution name and user details
    """
    return _address_enriched_service.get_enriched(
        db,
        select_fields=[
            "a.address_id",
            "a.institution_id",
            "i.name as institution_name",
            "a.user_id",
            "u.username as user_username",
            "u.first_name as user_first_name",
            "u.last_name as user_last_name",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as user_full_name",
            "a.address_type",
            "a.is_default",
            "a.floor",
            "a.country",
            "a.province",
            "a.city",
            "a.postal_code",
            "a.street_type",
            "a.street_name",
            "a.building_number",
            "a.apartment_unit",
            "a.timezone",
            "a.is_archived",
            "a.status",
            "a.created_date",
            "a.modified_date"
        ],
        joins=[
            ("INNER", "institution_info", "i", "a.institution_id = i.institution_id"),
            ("INNER", "user_info", "u", "a.user_id = u.user_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

def get_enriched_address_by_id(
    address_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> Optional[AddressEnrichedResponseSchema]:
    """
    Get a single address by ID with enriched data (institution_name, user_username, user_first_name, user_last_name).
    Uses SQL JOINs to avoid N+1 queries.
    
    Args:
        address_id: Address ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records
        
    Returns:
        Enriched address schema with institution name and user details, or None if not found
    """
    return _address_enriched_service.get_enriched_by_id(
        address_id,
        db,
        select_fields=[
            "a.address_id",
            "a.institution_id",
            "i.name as institution_name",
            "a.user_id",
            "u.username as user_username",
            "u.first_name as user_first_name",
            "u.last_name as user_last_name",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as user_full_name",
            "a.address_type",
            "a.is_default",
            "a.floor",
            "a.country",
            "a.province",
            "a.city",
            "a.postal_code",
            "a.street_type",
            "a.street_name",
            "a.building_number",
            "a.apartment_unit",
            "a.timezone",
            "a.is_archived",
            "a.status",
            "a.created_date",
            "a.modified_date"
        ],
        joins=[
            ("INNER", "institution_info", "i", "a.institution_id = i.institution_id"),
            ("INNER", "user_info", "u", "a.user_id = u.user_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

# =============================================================================
# RESTAURANT ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for restaurants
_restaurant_enriched_service = EnrichedService(
    base_table="restaurant_info",
    table_alias="r",
    id_column="restaurant_id",
    schema_class=RestaurantEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="r"  # institution_id is on the base table
)

def get_enriched_restaurants(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[RestaurantEnrichedResponseSchema]:
    """
    Get all restaurants with enriched data (institution name, entity name, address details).
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        List of RestaurantEnrichedResponseSchema with institution, entity, and address details
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _restaurant_enriched_service.get_enriched(
        db,
        select_fields=[
            "r.restaurant_id",
            "r.institution_id",
            "i.name as institution_name",
            "r.institution_entity_id",
            "ie.name as institution_entity_name",
            "r.address_id",
            "a.country",
            "a.province",
            "a.city",
            "a.postal_code",
            "r.credit_currency_id",
            "r.name",
            "r.cuisine",
            "r.is_archived",
            "r.status",
            "r.created_date",
            "r.modified_date"
        ],
        joins=[
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("INNER", "institution_entity_info", "ie", "r.institution_entity_id = ie.institution_entity_id"),
            ("INNER", "address_info", "a", "r.address_id = a.address_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

def get_enriched_restaurant_by_id(
    restaurant_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> Optional[RestaurantEnrichedResponseSchema]:
    """
    Get a single restaurant by ID with enriched data (institution name, entity name, address details).
    
    Args:
        restaurant_id: Restaurant ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        RestaurantEnrichedResponseSchema with institution, entity, and address details, or None if not found
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _restaurant_enriched_service.get_enriched_by_id(
        restaurant_id,
        db,
        select_fields=[
            "r.restaurant_id",
            "r.institution_id",
            "i.name as institution_name",
            "r.institution_entity_id",
            "ie.name as institution_entity_name",
            "r.address_id",
            "a.country",
            "a.province",
            "a.city",
            "a.postal_code",
            "r.credit_currency_id",
            "r.name",
            "r.cuisine",
            "r.is_archived",
            "r.status",
            "r.created_date",
            "r.modified_date"
        ],
        joins=[
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("INNER", "institution_entity_info", "ie", "r.institution_entity_id = ie.institution_entity_id"),
            ("INNER", "address_info", "a", "r.address_id = a.address_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

# =============================================================================
# QR CODE ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for QR codes
_qr_code_enriched_service = EnrichedService(
    base_table="qr_code",
    table_alias="q",
    id_column="qr_code_id",
    schema_class=QRCodeEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="r"  # institution_id is on the joined restaurant_info table
)

def get_enriched_qr_codes(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[QRCodeEnrichedResponseSchema]:
    """
    Get all QR codes with enriched data (institution name, restaurant name, address details).
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        List of QRCodeEnrichedResponseSchema with institution, restaurant, and address details
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _qr_code_enriched_service.get_enriched(
        db,
        select_fields=[
            "q.qr_code_id",
            "q.restaurant_id",
            "r.name as restaurant_name",
            "r.institution_id",
            "i.name as institution_name",
            "a.country",
            "a.province",
            "a.city",
            "a.postal_code",
            "TRIM(CONCAT_WS(' ', a.street_type, a.street_name, a.building_number)) as street_address",
            "q.qr_code_payload",
            "q.qr_code_image_url",
            "q.image_storage_path",
            "q.qr_code_checksum",
            "CASE WHEN q.qr_code_image_url IS NOT NULL AND q.qr_code_image_url != '' THEN TRUE ELSE FALSE END as has_image",
            "q.is_archived",
            "q.status",
            "q.created_date",
            "q.modified_date"
        ],
        joins=[
            ("INNER", "restaurant_info", "r", "q.restaurant_id = r.restaurant_id"),
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("INNER", "address_info", "a", "r.address_id = a.address_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

def get_enriched_qr_code_by_id(
    qr_code_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> Optional[QRCodeEnrichedResponseSchema]:
    """
    Get a single QR code by ID with enriched data (institution name, restaurant name, address details).
    
    Args:
        qr_code_id: QR code ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        QRCodeEnrichedResponseSchema with institution, restaurant, and address details, or None if not found
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _qr_code_enriched_service.get_enriched_by_id(
        qr_code_id,
        db,
        select_fields=[
            "q.qr_code_id",
            "q.restaurant_id",
            "r.name as restaurant_name",
            "r.institution_id",
            "i.name as institution_name",
            "a.country",
            "a.province",
            "a.city",
            "a.postal_code",
            "TRIM(CONCAT_WS(' ', a.street_type, a.street_name, a.building_number)) as street_address",
            "q.qr_code_payload",
            "q.qr_code_image_url",
            "q.image_storage_path",
            "q.qr_code_checksum",
            "CASE WHEN q.qr_code_image_url IS NOT NULL AND q.qr_code_image_url != '' THEN TRUE ELSE FALSE END as has_image",
            "q.is_archived",
            "q.status",
            "q.created_date",
            "q.modified_date"
        ],
        joins=[
            ("INNER", "restaurant_info", "r", "q.restaurant_id = r.restaurant_id"),
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("INNER", "address_info", "a", "r.address_id = a.address_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

# =============================================================================
# PRODUCT ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for products
_product_enriched_service = EnrichedService(
    base_table="product_info",
    table_alias="p",
    id_column="product_id",
    schema_class=ProductEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="p"  # institution_id is on the base table
)

def get_enriched_products(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[ProductEnrichedResponseSchema]:
    """
    Get all products with enriched data (institution name).
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        List of ProductEnrichedResponseSchema with institution name
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _product_enriched_service.get_enriched(
        db,
        select_fields=[
            "p.product_id",
            "p.institution_id",
            "i.name as institution_name",
            "p.name",
            "p.ingredients",
            "p.dietary",
            "p.image_url",
            "p.image_storage_path",
            "p.image_checksum",
            "CASE WHEN p.image_storage_path != 'static/placeholders/product_default.png' THEN TRUE ELSE FALSE END as has_image",
            "p.is_archived",
            "p.status",
            "p.created_date",
            "p.modified_date"
        ],
        joins=[
            ("INNER", "institution_info", "i", "p.institution_id = i.institution_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

def get_enriched_product_by_id(
    product_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> Optional[ProductEnrichedResponseSchema]:
    """
    Get a single product by ID with enriched data (institution name).
    
    Args:
        product_id: Product ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        ProductEnrichedResponseSchema with institution name, or None if not found
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _product_enriched_service.get_enriched_by_id(
        product_id,
        db,
        select_fields=[
            "p.product_id",
            "p.institution_id",
            "i.name as institution_name",
            "p.name",
            "p.ingredients",
            "p.dietary",
            "p.image_url",
            "p.image_storage_path",
            "p.image_checksum",
            "CASE WHEN p.image_storage_path != 'static/placeholders/product_default.png' THEN TRUE ELSE FALSE END as has_image",
            "p.is_archived",
            "p.status",
            "p.created_date",
            "p.modified_date"
        ],
        joins=[
            ("INNER", "institution_info", "i", "p.institution_id = i.institution_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

# =============================================================================
# PLATE ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for plates
_plate_enriched_service = EnrichedService(
    base_table="plate_info",
    table_alias="p",
    id_column="plate_id",
    schema_class=PlateEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="r"  # institution_id is on the joined restaurant_info table
)

def get_enriched_plates(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[PlateEnrichedResponseSchema]:
    """
    Get all plates with enriched data (institution, restaurant, product, address details).
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        List of PlateEnrichedResponseSchema with enriched data
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _plate_enriched_service.get_enriched(
        db,
        select_fields=[
            "p.plate_id",
            "p.product_id",
            "p.restaurant_id",
            "i.name as institution_name",
            "r.name as restaurant_name",
            "r.cuisine",
            "a.country",
            "a.province",
            "a.city",
            "pr.name as product_name",
            "pr.dietary",
            "pr.image_url as product_image_url",
            "pr.image_storage_path as product_image_storage_path",
            "CASE WHEN pr.image_storage_path != 'static/placeholders/product_default.png' THEN TRUE ELSE FALSE END as has_image",
            "p.price",
            "p.credit",
            "p.savings",
            "p.no_show_discount",
            "p.delivery_time_minutes",
            "p.is_archived",
            "p.status",
            "p.created_date",
            "p.modified_date"
        ],
        joins=[
            ("INNER", "product_info", "pr", "p.product_id = pr.product_id"),
            ("INNER", "restaurant_info", "r", "p.restaurant_id = r.restaurant_id"),
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("INNER", "address_info", "a", "r.address_id = a.address_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

def get_enriched_plate_by_id(
    plate_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> Optional[PlateEnrichedResponseSchema]:
    """
    Get a single plate by ID with enriched data (institution, restaurant, product, address details).
    
    Args:
        plate_id: Plate ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        PlateEnrichedResponseSchema with enriched data, or None if not found
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _plate_enriched_service.get_enriched_by_id(
        plate_id,
        db,
        select_fields=[
            "p.plate_id",
            "p.product_id",
            "p.restaurant_id",
            "i.name as institution_name",
            "r.name as restaurant_name",
            "r.cuisine",
            "a.country",
            "a.province",
            "a.city",
            "pr.name as product_name",
            "pr.dietary",
            "pr.image_url as product_image_url",
            "pr.image_storage_path as product_image_storage_path",
            "CASE WHEN pr.image_storage_path != 'static/placeholders/product_default.png' THEN TRUE ELSE FALSE END as has_image",
            "p.price",
            "p.credit",
            "p.savings",
            "p.no_show_discount",
            "p.delivery_time_minutes",
            "p.is_archived",
            "p.status",
            "p.created_date",
            "p.modified_date"
        ],
        joins=[
            ("INNER", "product_info", "pr", "p.product_id = pr.product_id"),
            ("INNER", "restaurant_info", "r", "p.restaurant_id = r.restaurant_id"),
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("INNER", "address_info", "a", "r.address_id = a.address_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

# =============================================================================
# PLAN ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for plans
# Note: Plans don't have institution scoping, so we pass None for institution_column
_plan_enriched_service = EnrichedService(
    base_table="plan_info",
    table_alias="pl",
    id_column="plan_id",
    schema_class=PlanEnrichedResponseSchema,
    institution_column=None,  # Plans don't have institution scoping
    institution_table_alias=None
)

def get_enriched_plans(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[PlanEnrichedResponseSchema]:
    """
    Get all plans with enriched data (currency name and code).
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering (not used for plans, but kept for consistency)
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        List of PlanEnrichedResponseSchema with currency name and code
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _plan_enriched_service.get_enriched(
        db,
        select_fields=[
            "pl.plan_id",
            "pl.credit_currency_id",
            "cc.currency_name",
            "cc.currency_code",
            "pl.name",
            "pl.credit",
            "pl.price",
            "pl.rollover",
            "pl.rollover_cap",
            "pl.is_archived",
            "pl.status",
            "pl.created_date",
            "pl.modified_date"
        ],
        joins=[
            ("INNER", "credit_currency_info", "cc", "pl.credit_currency_id = cc.credit_currency_id")
        ],
        scope=None,  # Plans don't have institution scoping
        include_archived=include_archived
    )

def get_enriched_plan_by_id(
    plan_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> Optional[PlanEnrichedResponseSchema]:
    """
    Get a single plan by ID with enriched data (currency name and code).
    
    Args:
        plan_id: Plan ID
        db: Database connection
        scope: Optional institution scope for filtering (not used for plans, but kept for consistency)
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        PlanEnrichedResponseSchema with currency name and code, or None if not found
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _plan_enriched_service.get_enriched_by_id(
        plan_id,
        db,
        select_fields=[
            "pl.plan_id",
            "pl.credit_currency_id",
            "cc.currency_name",
            "cc.currency_code",
            "pl.name",
            "pl.credit",
            "pl.price",
            "pl.rollover",
            "pl.rollover_cap",
            "pl.is_archived",
            "pl.status",
            "pl.created_date",
            "pl.modified_date"
        ],
        joins=[
            ("INNER", "credit_currency_info", "cc", "pl.credit_currency_id = cc.credit_currency_id")
        ],
        scope=None,  # Plans don't have institution scoping
        include_archived=include_archived
    )

# =============================================================================
# FINTECH LINK ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for fintech links
# Note: Fintech links don't have institution scoping, so we pass None for institution_column
_fintech_link_enriched_service = EnrichedService(
    base_table="fintech_link_info",
    table_alias="fl",
    id_column="fintech_link_id",
    schema_class=FintechLinkEnrichedResponseSchema,
    institution_column=None,  # Fintech links don't have institution scoping
    institution_table_alias=None
)

def get_enriched_fintech_links(
    db: psycopg2.extensions.connection,
    *,
    include_archived: bool = False
) -> List[FintechLinkEnrichedResponseSchema]:
    """
    Get all fintech links with enriched data (plan name, price, credit, status, currency code).
    
    Args:
        db: Database connection
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        List of FintechLinkEnrichedResponseSchema with enriched data
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _fintech_link_enriched_service.get_enriched(
        db,
        select_fields=[
            "fl.fintech_link_id",
            "fl.plan_id",
            "pl.name as plan_name",
            "pl.price",
            "pl.credit",
            "pl.status as plan_status",
            "cc.currency_code",
            "fl.provider",
            "fl.fintech_link",
            "fl.is_archived",
            "fl.status",
            "fl.created_date",
            "fl.modified_date"
        ],
        joins=[
            ("INNER", "plan_info", "pl", "fl.plan_id = pl.plan_id"),
            ("INNER", "credit_currency_info", "cc", "pl.credit_currency_id = cc.credit_currency_id")
        ],
        scope=None,  # Fintech links don't have institution scoping
        include_archived=include_archived
    )

def get_enriched_fintech_link_by_id(
    fintech_link_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    include_archived: bool = False
) -> Optional[FintechLinkEnrichedResponseSchema]:
    """
    Get a single fintech link by ID with enriched data (plan name, price, credit, status, currency code).
    
    Args:
        fintech_link_id: Fintech link ID
        db: Database connection
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        FintechLinkEnrichedResponseSchema with enriched data, or None if not found
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _fintech_link_enriched_service.get_enriched_by_id(
        fintech_link_id,
        db,
        select_fields=[
            "fl.fintech_link_id",
            "fl.plan_id",
            "pl.name as plan_name",
            "pl.price",
            "pl.credit",
            "pl.status as plan_status",
            "cc.currency_code",
            "fl.provider",
            "fl.fintech_link",
            "fl.is_archived",
            "fl.status",
            "fl.created_date",
            "fl.modified_date"
        ],
        joins=[
            ("INNER", "plan_info", "pl", "fl.plan_id = pl.plan_id"),
            ("INNER", "credit_currency_info", "cc", "pl.credit_currency_id = cc.credit_currency_id")
        ],
        scope=None,  # Fintech links don't have institution scoping
        include_archived=include_archived
    )

# =============================================================================
# PRODUCT BUSINESS LOGIC
# =============================================================================

def get_products_by_institution(institution_id: UUID, db: psycopg2.extensions.connection) -> List[ProductDTO]:
    """
    Get all products for an institution - business logic only.
    
    Args:
        institution_id: Institution ID
        db: Database connection
        
    Returns:
        List of ProductDTOs
        
    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        all_products = product_service.get_all(db)
        
        # Filter by institution_id (business logic)
        institution_products = [
            product for product in all_products 
            if product.institution_id == institution_id
        ]
        
        # Sort by name (business logic)
        institution_products.sort(key=lambda p: p.name)
        
        return institution_products
    except Exception as e:
        log_error(f"Error getting products by institution {institution_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get products for institution")

def search_products_by_name(search_term: str, institution_id: UUID, db: psycopg2.extensions.connection) -> List[ProductDTO]:
    """
    Search products by name - business logic only.
    
    Args:
        search_term: Term to search for
        institution_id: Institution ID
        db: Database connection
        
    Returns:
        List of matching ProductDTOs
        
    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        all_products = product_service.get_all(db)
        
        # Filter by institution_id and name search (business logic)
        search_term_lower = search_term.lower()
        matching_products = [
            product for product in all_products 
            if product.institution_id == institution_id and search_term_lower in product.name.lower()
        ]
        
        # Sort by name (business logic)
        matching_products.sort(key=lambda p: p.name)
        
        return matching_products
    except Exception as e:
        log_error(f"Error searching products by name {search_term}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search products")

# =============================================================================
# PLATE BUSINESS LOGIC
# =============================================================================

def get_plates_by_restaurant(restaurant_id: UUID, db: psycopg2.extensions.connection) -> List[PlateDTO]:
    """
    Get all plates for a restaurant - business logic only.
    
    Args:
        restaurant_id: Restaurant ID
        db: Database connection
        
    Returns:
        List of PlateDTOs
        
    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        all_plates = plate_service.get_all(db)
        
        # Filter by restaurant_id (business logic)
        restaurant_plates = [
            plate for plate in all_plates 
            if plate.restaurant_id == restaurant_id
        ]
        
        # Sort by price (business logic)
        restaurant_plates.sort(key=lambda p: p.price)
        
        return restaurant_plates
    except Exception as e:
        log_error(f"Error getting plates by restaurant {restaurant_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get plates for restaurant")

def get_plates_by_product(product_id: UUID, db: psycopg2.extensions.connection) -> List[PlateDTO]:
    """
    Get all plates for a product - business logic only.
    
    Args:
        product_id: Product ID
        db: Database connection
        
    Returns:
        List of PlateDTOs
        
    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        all_plates = plate_service.get_all(db)
        
        # Filter by product_id (business logic)
        product_plates = [
            plate for plate in all_plates 
            if plate.product_id == product_id
        ]
        
        # Sort by price (business logic)
        product_plates.sort(key=lambda p: p.price)
        
        return product_plates
    except Exception as e:
        log_error(f"Error getting plates by product {product_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get plates for product")

# =============================================================================
# BILLING BUSINESS LOGIC
# =============================================================================

def get_pending_bills_by_institution(institution_id: UUID, db: psycopg2.extensions.connection) -> List[InstitutionBillDTO]:
    """
    Get all pending bills for an institution - business logic only.
    
    Args:
        institution_id: Institution Entity ID (actually institution_entity_id)
        db: Database connection
        
    Returns:
        List of pending InstitutionBillDTOs
        
    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        all_bills = institution_bill_service.get_all(db)
        
        # Filter by institution_entity_id and pending status (business logic)
        # Note: Despite the parameter name, this filters by institution_entity_id
        pending_bills = [
            bill for bill in all_bills 
            if bill.institution_entity_id == institution_id and bill.status == Status.PENDING
        ]
        
        # Sort by created_date DESC (business logic)
        pending_bills.sort(key=lambda b: b.created_date, reverse=True)
        
        return pending_bills
    except Exception as e:
        log_error(f"Error getting pending bills by institution {institution_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get pending bills for institution")

def get_bills_by_status(institution_id: UUID, status: str, db: psycopg2.extensions.connection) -> List[InstitutionBillDTO]:
    """
    Get bills by status for an institution - business logic only.
    
    Args:
        institution_id: Institution ID
        status: Bill status to filter by
        db: Database connection
        
    Returns:
        List of InstitutionBillDTOs
        
    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        all_bills = institution_bill_service.get_all(db)
        
        # Filter by institution_id and status (business logic)
        filtered_bills = [
            bill for bill in all_bills 
            if bill.institution_entity_id == institution_id and bill.status == status
        ]
        
        # Sort by created_date DESC (business logic)
        filtered_bills.sort(key=lambda b: b.created_date, reverse=True)
        
        return filtered_bills
    except Exception as e:
        log_error(f"Error getting bills by status {status} for institution {institution_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get bills for institution")

# =============================================================================
# EMPLOYER BUSINESS LOGIC
# =============================================================================

def create_employer_with_address(
    employer_data: dict, 
    address_data: dict, 
    user_id: UUID, 
    db: psycopg2.extensions.connection,
    *,
    assign_to_user: bool = False
) -> EmployerDTO:
    """
    Create employer with address - business logic with atomic transaction.
    
    All operations (address creation, employer creation, address update, user assignment)
    are performed atomically - either all succeed or all are rolled back.
    
    Args:
        employer_data: Employer data dictionary
        address_data: Address data dictionary
        user_id: ID of user creating the employer
        db: Database connection
        assign_to_user: If True, automatically assign employer to user after creation.
                        Only applies to Customers. Must be set by the route handler based on role_type.
        
    Returns:
        Created EmployerDTO
        
    Raises:
        HTTPException: If creation fails (triggers rollback of all operations)
    """
    try:
        # All operations use commit=False for atomic transaction
        # Create address using business service (sets timezone, handles geocoding)
        from app.services.address_service import address_business_service
        
        # Convert user_id to current_user dict format expected by business service
        current_user_dict = {"user_id": user_id}
        
        # Note: address_data["modified_by"] will be set by business service
        address = address_business_service.create_address_with_geocoding(
            address_data,
            current_user_dict,
            db,
            scope=None,
            commit=False
        )
        if not address:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to create address")
        
        # Create employer with address reference
        employer_data["address_id"] = address.address_id
        employer_data["modified_by"] = user_id
        employer = employer_service.create(employer_data, db, commit=False)
        if not employer:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to create employer")
        
        # Update address to link it to the employer (set employer_id)
        # This creates the bidirectional relationship: employer -> address and address -> employer
        address_update_data = {
            "employer_id": employer.employer_id,
            "modified_by": user_id
        }
        updated_address = address_service.update(address.address_id, address_update_data, db, commit=False)
        if not updated_address:
            db.rollback()
            log_error(f"Failed to link address {address.address_id} to employer {employer.employer_id}")
            raise HTTPException(
                status_code=500,
                detail="Failed to link address to employer"
            )
        
        # Assign employer to user if requested (atomic within same transaction)
        if assign_to_user:
            user_update_data = {
                "employer_id": employer.employer_id,
                "modified_by": user_id
            }
            updated_user = user_service.update(user_id, user_update_data, db, scope=None, commit=False)
            if not updated_user:
                db.rollback()
                raise HTTPException(
                    status_code=500,
                    detail="Failed to assign employer to user"
                )
            log_info(f"Assigned employer {employer.employer_id} to user {user_id}")
        
        # Commit all operations atomically
        db.commit()
        log_info(f"Successfully created employer {employer.employer_id} with address {address.address_id} (atomic transaction)")
        
        return employer
    except HTTPException:
        # HTTPException already handled rollback, just re-raise
        raise
    except Exception as e:
        # Rollback on any unexpected error
        db.rollback()
        log_error(f"Error creating employer with address: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create employer: {e}")

def get_employers_by_name(name: str, db: psycopg2.extensions.connection) -> List[EmployerDTO]:
    """
    Search employers by name - business logic only.
    
    Args:
        name: Name to search for
        db: Database connection
        
    Returns:
        List of matching EmployerDTOs
        
    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        all_employers = employer_service.get_all(db)
        
        # Filter by name (case-insensitive search - business logic)
        name_lower = name.lower()
        matching_employers = [
            employer for employer in all_employers 
            if name_lower in employer.name.lower()
        ]
        
        # Sort by name (business logic)
        matching_employers.sort(key=lambda e: e.name)
        
        return matching_employers
    except Exception as e:
        log_error(f"Error searching employers by name {name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search employers")

# Initialize EnrichedService instance for employers
_employer_enriched_service = EnrichedService(
    base_table="employer_info",
    table_alias="e",
    id_column="employer_id",
    schema_class=EmployerEnrichedResponseSchema,
    institution_column=None,  # Employers don't have institution_id
    institution_table_alias=None
)

def get_enriched_employers(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[EmployerEnrichedResponseSchema]:
    """
    Get all employers with enriched address data.
    Uses SQL JOINs to avoid N+1 queries.
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering (not used for employers)
        include_archived: Whether to include archived records
        
    Returns:
        List of enriched employer schemas with address details
    """
    return _employer_enriched_service.get_enriched(
        db,
        select_fields=[
            "e.employer_id",
            "e.name",
            "e.address_id",
            "a.country as address_country",
            "a.province as address_province",
            "a.city as address_city",
            "a.postal_code as address_postal_code",
            "a.street_type as address_street_type",
            "a.street_name as address_street_name",
            "a.building_number as address_building_number",
            "a.floor as address_floor",
            "a.apartment_unit as address_apartment_unit",
            "e.is_archived",
            "e.status",
            "e.created_date",
            "e.modified_date"
        ],
        joins=[
            ("LEFT", "address_info", "a", "e.address_id = a.address_id")
        ],
        scope=None,  # Employers don't have institution scope
        include_archived=include_archived
    )

def get_enriched_employer_by_id(
    employer_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> Optional[EmployerEnrichedResponseSchema]:
    """
    Get a single employer by ID with enriched address data.
    Uses SQL JOINs to avoid N+1 queries.
    
    Args:
        employer_id: Employer ID
        db: Database connection
        scope: Optional institution scope for filtering (not used for employers)
        include_archived: Whether to include archived records
        
    Returns:
        Enriched employer schema with address details, or None if not found
    """
    return _employer_enriched_service.get_enriched_by_id(
        employer_id,
        db,
        select_fields=[
            "e.employer_id",
            "e.name",
            "e.address_id",
            "a.country as address_country",
            "a.province as address_province",
            "a.city as address_city",
            "a.postal_code as address_postal_code",
            "a.street_name as address_street_name",
            "a.building_number as address_building_number",
            "e.is_archived",
            "e.status",
            "e.created_date",
            "e.modified_by",
            "e.modified_date"
        ],
        joins=[
            ("LEFT", "address_info", "a", "e.address_id = a.address_id")
        ],
        scope=None,  # Employers don't have institution scope
        include_archived=include_archived
    )

# =============================================================================
# GEOLOCATION BUSINESS LOGIC
# =============================================================================

def get_geolocation_by_address_id(address_id: UUID, db: psycopg2.extensions.connection) -> Optional[GeolocationDTO]:
    """
    Get geolocation by address ID - business logic only.
    
    Args:
        address_id: Address ID to search for
        db: Database connection
        
    Returns:
        GeolocationDTO if found, None otherwise
        
    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        # Use service layer instead of direct db_read
        return geolocation_service.get_by_field("address_id", address_id, db)
    except Exception as e:
        log_error(f"Error getting geolocation by address ID {address_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get geolocation by address ID")

# =============================================================================
# SUBSCRIPTION BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for subscriptions
# Note: institution_id is on the joined user_info table
_subscription_enriched_service = EnrichedService(
    base_table="subscription_info",
    table_alias="s",
    id_column="subscription_id",
    schema_class=SubscriptionEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="u"  # institution_id is on the joined user_info table
)

def get_enriched_subscriptions(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False,
    user_id: Optional[UUID] = None
) -> List[SubscriptionEnrichedResponseSchema]:
    """
    Get all subscriptions with enriched data (user information and plan information).
    Includes: user_full_name, user_username, user_email, user_status, user_cellphone,
    plan_name, plan_credit, plan_price, plan_rollover, plan_rollover_cap, plan_status.
    Uses SQL JOINs to avoid N+1 queries.
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering (not typically used for subscriptions)
        include_archived: Whether to include archived records
        user_id: Optional user_id to filter subscriptions by user
        
    Returns:
        List of enriched subscription schemas with user information
    """
    additional_conditions = []
    if user_id:
        additional_conditions.append(("s.user_id = %s::uuid", str(user_id)))
    
    return _subscription_enriched_service.get_enriched(
        db,
        select_fields=[
            "s.subscription_id",
            "s.user_id",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as user_full_name",
            "u.username as user_username",
            "u.email as user_email",
            "u.status as user_status",
            "u.cellphone as user_cellphone",
            "s.plan_id",
            "p.name as plan_name",
            "p.credit as plan_credit",
            "p.price as plan_price",
            "p.rollover as plan_rollover",
            "p.rollover_cap as plan_rollover_cap",
            "p.status as plan_status",
            "s.renewal_date",
            "s.balance",
            "s.is_archived",
            "s.status",
            "s.created_date",
            "s.modified_by",
            "s.modified_date"
        ],
        joins=[
            ("INNER", "user_info", "u", "s.user_id = u.user_id"),
            ("INNER", "plan_info", "p", "s.plan_id = p.plan_id")
        ],
        scope=scope,
        include_archived=include_archived,
        additional_conditions=additional_conditions if additional_conditions else None
    )

def get_enriched_subscription_by_id(
    subscription_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> Optional[SubscriptionEnrichedResponseSchema]:
    """
    Get a single subscription by ID with enriched data (user information and plan information).
    Includes: user_full_name, user_username, user_email, user_status, user_cellphone,
    plan_name, plan_credit, plan_price, plan_rollover, plan_rollover_cap, plan_status.
    Uses SQL JOINs to avoid N+1 queries.
    
    Args:
        subscription_id: Subscription ID
        db: Database connection
        scope: Optional institution scope for filtering (not typically used for subscriptions)
        include_archived: Whether to include archived records
        
    Returns:
        Enriched subscription schema with user information, or None if not found
    """
    return _subscription_enriched_service.get_enriched_by_id(
        subscription_id,
        db,
        select_fields=[
            "s.subscription_id",
            "s.user_id",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as user_full_name",
            "u.username as user_username",
            "u.email as user_email",
            "u.status as user_status",
            "u.cellphone as user_cellphone",
            "s.plan_id",
            "p.name as plan_name",
            "p.credit as plan_credit",
            "p.price as plan_price",
            "p.rollover as plan_rollover",
            "p.rollover_cap as plan_rollover_cap",
            "p.status as plan_status",
            "s.renewal_date",
            "s.balance",
            "s.is_archived",
            "s.status",
            "s.created_date",
            "s.modified_by",
            "s.modified_date"
        ],
        joins=[
            ("INNER", "user_info", "u", "s.user_id = u.user_id"),
            ("INNER", "plan_info", "p", "s.plan_id = p.plan_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

# =============================================================================
# INSTITUTION BILL ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for institution bills
_bill_enriched_service = EnrichedService(
    base_table="institution_bill_info",
    table_alias="ibi",
    id_column="institution_bill_id",
    schema_class=InstitutionBillEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="r"  # institution_id is on the joined restaurant_info table
)

def get_enriched_institution_bills(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[InstitutionBillEnrichedResponseSchema]:
    """
    Get all institution bills with enriched data (institution name, entity name, restaurant name).
    Returns an array of enriched institution bill records.
    
    Scoping rules:
    - If scope is global (Employee): Returns all institution bills
    - If scope is institution-scoped (Supplier): Returns bills for restaurants in their institution
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering (for Employees/Suppliers)
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        List of InstitutionBillEnrichedResponseSchema with institution, entity, restaurant, and currency information
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _bill_enriched_service.get_enriched(
        db,
        select_fields=[
            "ibi.institution_bill_id",
            "ibi.institution_id",
            "COALESCE(i.name, '') as institution_name",
            "ibi.institution_entity_id",
            "COALESCE(ie.name, '') as institution_entity_name",
            "ibi.restaurant_id",
            "COALESCE(r.name, '') as restaurant_name",
            "ibi.credit_currency_id",
            "ibi.payment_id",
            "ibi.transaction_count",
            "ibi.amount",
            "ibi.currency_code",
            "ibi.balance_event_id",
            "ibi.period_start",
            "ibi.period_end",
            "ibi.is_archived",
            "ibi.status",
            "ibi.resolution",
            "ibi.created_date",
            "ibi.modified_by",
            "ibi.modified_date"
        ],
        joins=[
            ("LEFT", "institution_info", "i", "ibi.institution_id = i.institution_id"),
            ("LEFT", "institution_entity_info", "ie", "ibi.institution_entity_id = ie.institution_entity_id"),
            ("LEFT", "restaurant_info", "r", "ibi.restaurant_id = r.restaurant_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

# =============================================================================
# INSTITUTION BANK ACCOUNT ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for institution bank accounts
_bank_account_enriched_service = EnrichedService(
    base_table="institution_bank_account",
    table_alias="iba",
    id_column="bank_account_id",
    schema_class=InstitutionBankAccountEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="ie"  # institution_id is on the joined institution_entity_info table
)

def get_enriched_institution_bank_accounts(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[InstitutionBankAccountEnrichedResponseSchema]:
    """
    Get all institution bank accounts with enriched data (institution name, entity name, country).
    Returns an array of enriched institution bank account records.
    
    Scoping rules:
    - If scope is global (Employee): Returns all institution bank accounts
    - If scope is institution-scoped (Supplier): Returns bank accounts for entities in their institution
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering (for Employees/Suppliers)
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        List of InstitutionBankAccountEnrichedResponseSchema with institution, entity, and address information
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _bank_account_enriched_service.get_enriched(
        db,
        select_fields=[
            "iba.bank_account_id",
            "iba.institution_entity_id",
            "ie.institution_id",
            "COALESCE(i.name, '') as institution_name",
            "COALESCE(ie.name, '') as institution_entity_name",
            "iba.address_id",
            "COALESCE(a.country, '') as country",
            "iba.account_holder_name",
            "iba.bank_name",
            "iba.account_type",
            "iba.routing_number",
            "iba.account_number",
            "iba.is_archived",
            "iba.status",
            "iba.created_date",
            "iba.modified_by"
        ],
        joins=[
            ("INNER", "institution_entity_info", "ie", "iba.institution_entity_id = ie.institution_entity_id"),
            ("LEFT", "institution_info", "i", "ie.institution_id = i.institution_id"),
            ("LEFT", "address_info", "a", "iba.address_id = a.address_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

# =============================================================================
# INSTITUTION PAYMENT ATTEMPT ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for institution payment attempts
_payment_attempt_enriched_service = EnrichedService(
    base_table="institution_payment_attempt",
    table_alias="ipa",
    id_column="payment_id",
    schema_class=InstitutionPaymentAttemptEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="ie"  # institution_id is on the joined institution_entity_info table
)

def get_enriched_institution_payment_attempts(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[InstitutionPaymentAttemptEnrichedResponseSchema]:
    """
    Get all institution payment attempts with enriched data (institution name, entity name, bank name, country, period start, period end).
    Returns an array of enriched institution payment attempt records.
    
    Scoping rules:
    - If scope is global (Employee): Returns all institution payment attempts
    - If scope is institution-scoped (Supplier): Returns payment attempts for entities in their institution
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering (for Employees/Suppliers)
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        List of InstitutionPaymentAttemptEnrichedResponseSchema with institution, entity, bank account, and bill information
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _payment_attempt_enriched_service.get_enriched(
        db,
        select_fields=[
            "ipa.payment_id",
            "ipa.institution_entity_id",
            "COALESCE(i.name, '') as institution_name",
            "COALESCE(ie.name, '') as institution_entity_name",
            "ipa.bank_account_id",
            "COALESCE(iba.bank_name, '') as bank_name",
            "COALESCE(a.country, '') as country",
            "ipa.institution_bill_id",
            "ibi.period_start",
            "ibi.period_end",
            "ipa.credit_currency_id",
            "ipa.amount",
            "ipa.currency_code",
            "ipa.transaction_result",
            "ipa.external_transaction_id",
            "ipa.is_archived",
            "ipa.status",
            "ipa.created_date",
            "ipa.resolution_date"
        ],
        joins=[
            ("INNER", "institution_entity_info", "ie", "ipa.institution_entity_id = ie.institution_entity_id"),
            ("LEFT", "institution_info", "i", "ie.institution_id = i.institution_id"),
            ("INNER", "institution_bank_account", "iba", "ipa.bank_account_id = iba.bank_account_id"),
            ("LEFT", "address_info", "a", "iba.address_id = a.address_id"),
            ("LEFT", "institution_bill_info", "ibi", "ipa.institution_bill_id = ibi.institution_bill_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

def get_enriched_institution_payment_attempt_by_id(
    db: psycopg2.extensions.connection,
    payment_id: UUID,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> Optional[InstitutionPaymentAttemptEnrichedResponseSchema]:
    """
    Get a single institution payment attempt by ID with enriched data (institution name, entity name, bank name, country, period start, period end).
    
    Scoping rules:
    - If scope is global (Employee): Returns any payment attempt
    - If scope is institution-scoped (Supplier): Returns payment attempt only if entity belongs to their institution
    
    Args:
        db: Database connection
        payment_id: Payment attempt ID
        scope: Optional institution scope for filtering (for Employees/Suppliers)
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        InstitutionPaymentAttemptEnrichedResponseSchema with institution, entity, bank account, and bill information, or None if not found
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _payment_attempt_enriched_service.get_enriched_by_id(
        db,
        payment_id,
        select_fields=[
            "ipa.payment_id",
            "ipa.institution_entity_id",
            "COALESCE(i.name, '') as institution_name",
            "COALESCE(ie.name, '') as institution_entity_name",
            "ipa.bank_account_id",
            "COALESCE(iba.bank_name, '') as bank_name",
            "COALESCE(a.country, '') as country",
            "ipa.institution_bill_id",
            "ibi.period_start",
            "ibi.period_end",
            "ipa.credit_currency_id",
            "ipa.amount",
            "ipa.currency_code",
            "ipa.transaction_result",
            "ipa.external_transaction_id",
            "ipa.is_archived",
            "ipa.status",
            "ipa.created_date",
            "ipa.resolution_date"
        ],
        joins=[
            ("INNER", "institution_entity_info", "ie", "ipa.institution_entity_id = ie.institution_entity_id"),
            ("LEFT", "institution_info", "i", "ie.institution_id = i.institution_id"),
            ("INNER", "institution_bank_account", "iba", "ipa.bank_account_id = iba.bank_account_id"),
            ("LEFT", "address_info", "a", "iba.address_id = a.address_id"),
            ("LEFT", "institution_bill_info", "ibi", "ipa.institution_bill_id = ibi.institution_bill_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

# =============================================================================
# RESTAURANT BALANCE ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for restaurant balances
_restaurant_balance_enriched_service = EnrichedService(
    base_table="restaurant_balance_info",
    table_alias="rb",
    id_column="restaurant_id",
    schema_class=RestaurantBalanceEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="r"  # institution_id is on the joined restaurant_info table
)

def get_enriched_restaurant_balances(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[RestaurantBalanceEnrichedResponseSchema]:
    """
    Get all restaurant balances with enriched data (institution name, entity name, restaurant name, country).
    Returns an array of enriched restaurant balance records.
    
    **Note: This is a read-only endpoint. Restaurant balances are automatically managed by the backend
    through transactions and billing operations. They cannot be created or modified via API.**
    
    Scoping rules:
    - If scope is global (Employee): Returns all restaurant balances
    - If scope is institution-scoped (Supplier): Returns balances for restaurants in their institution
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering (for Employees/Suppliers)
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        List of RestaurantBalanceEnrichedResponseSchema with institution, entity, restaurant, and address information
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _restaurant_balance_enriched_service.get_enriched(
        db,
        select_fields=[
            "rb.restaurant_id",
            "r.institution_id",
            "COALESCE(i.name, '') as institution_name",
            "r.institution_entity_id",
            "COALESCE(ie.name, '') as institution_entity_name",
            "COALESCE(r.name, '') as restaurant_name",
            "COALESCE(a.country, '') as country",
            "rb.credit_currency_id",
            "rb.transaction_count",
            "rb.balance",
            "rb.currency_code",
            "rb.is_archived",
            "rb.status",
            "rb.created_date",
            "rb.modified_by",
            "rb.modified_date"
        ],
        joins=[
            ("INNER", "restaurant_info", "r", "rb.restaurant_id = r.restaurant_id"),
            ("LEFT", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("LEFT", "institution_entity_info", "ie", "r.institution_entity_id = ie.institution_entity_id"),
            ("LEFT", "address_info", "a", "r.address_id = a.address_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

def get_enriched_restaurant_balance_by_id(
    db: psycopg2.extensions.connection,
    restaurant_id: UUID,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> Optional[RestaurantBalanceEnrichedResponseSchema]:
    """
    Get a single restaurant balance by restaurant ID with enriched data (institution name, entity name, restaurant name, country).
    
    **Note: This is a read-only endpoint. Restaurant balances are automatically managed by the backend
    through transactions and billing operations. They cannot be created or modified via API.**
    
    Scoping rules:
    - If scope is global (Employee): Returns any restaurant balance
    - If scope is institution-scoped (Supplier): Returns balance only if restaurant belongs to their institution
    
    Args:
        db: Database connection
        restaurant_id: Restaurant ID (primary key of restaurant_balance_info)
        scope: Optional institution scope for filtering (for Employees/Suppliers)
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        RestaurantBalanceEnrichedResponseSchema with institution, entity, restaurant, and address information, or None if not found
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _restaurant_balance_enriched_service.get_enriched_by_id(
        db,
        restaurant_id,
        select_fields=[
            "rb.restaurant_id",
            "r.institution_id",
            "COALESCE(i.name, '') as institution_name",
            "r.institution_entity_id",
            "COALESCE(ie.name, '') as institution_entity_name",
            "COALESCE(r.name, '') as restaurant_name",
            "COALESCE(a.country, '') as country",
            "rb.credit_currency_id",
            "rb.transaction_count",
            "rb.balance",
            "rb.currency_code",
            "rb.is_archived",
            "rb.status",
            "rb.created_date",
            "rb.modified_by",
            "rb.modified_date"
        ],
        joins=[
            ("INNER", "restaurant_info", "r", "rb.restaurant_id = r.restaurant_id"),
            ("LEFT", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("LEFT", "institution_entity_info", "ie", "r.institution_entity_id = ie.institution_entity_id"),
            ("LEFT", "address_info", "a", "r.address_id = a.address_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

# =============================================================================
# RESTAURANT TRANSACTION ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for restaurant transactions
_restaurant_transaction_enriched_service = EnrichedService(
    base_table="restaurant_transaction",
    table_alias="rt",
    id_column="transaction_id",
    schema_class=RestaurantTransactionEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="r"  # institution_id is on the joined restaurant_info table
)

def get_enriched_restaurant_transactions(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[RestaurantTransactionEnrichedResponseSchema]:
    """
    Get all restaurant transactions with enriched data (institution name, entity name, restaurant name, plate name, currency code, country).
    Returns an array of enriched restaurant transaction records.
    
    **Note: This is a read-only endpoint. Restaurant transactions are automatically managed by the backend
    through plate selection, QR code scanning, and billing operations. They cannot be created or modified via API.**
    
    Scoping rules:
    - If scope is global (Employee): Returns all restaurant transactions
    - If scope is institution-scoped (Supplier): Returns transactions for restaurants in their institution
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering (for Employees/Suppliers)
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        List of RestaurantTransactionEnrichedResponseSchema with institution, entity, restaurant, plate, and address information
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _restaurant_transaction_enriched_service.get_enriched(
        db,
        select_fields=[
            "rt.transaction_id",
            "rt.restaurant_id",
            "r.institution_id",
            "COALESCE(i.name, '') as institution_name",
            "r.institution_entity_id",
            "COALESCE(ie.name, '') as institution_entity_name",
            "COALESCE(r.name, '') as restaurant_name",
            "rt.plate_selection_id",
            "COALESCE(pr.name, '') as plate_name",
            "rt.discretionary_id",
            "rt.credit_currency_id",
            "rt.currency_code",
            "COALESCE(a.country, '') as country",
            "rt.was_collected",
            "rt.ordered_timestamp",
            "rt.collected_timestamp",
            "rt.arrival_time",
            "rt.completion_time",
            "rt.expected_completion_time",
            "rt.transaction_type",
            "rt.credit",
            "rt.no_show_discount",
            "rt.final_amount",
            "rt.is_archived",
            "rt.status",
            "rt.created_date",
            "rt.modified_by",
            "rt.modified_date"
        ],
        joins=[
            ("INNER", "restaurant_info", "r", "rt.restaurant_id = r.restaurant_id"),
            ("LEFT", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("LEFT", "institution_entity_info", "ie", "r.institution_entity_id = ie.institution_entity_id"),
            ("LEFT", "address_info", "a", "r.address_id = a.address_id"),
            ("LEFT", "plate_selection", "ps", "rt.plate_selection_id = ps.plate_selection_id"),
            ("LEFT", "plate_info", "pi", "ps.plate_id = pi.plate_id"),
            ("LEFT", "product_info", "pr", "pi.product_id = pr.product_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

def get_enriched_restaurant_transaction_by_id(
    db: psycopg2.extensions.connection,
    transaction_id: UUID,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> Optional[RestaurantTransactionEnrichedResponseSchema]:
    """
    Get a single restaurant transaction by ID with enriched data (institution name, entity name, restaurant name, plate name, currency code, country).
    
    **Note: This is a read-only endpoint. Restaurant transactions are automatically managed by the backend
    through plate selection, QR code scanning, and billing operations. They cannot be created or modified via API.**
    
    Scoping rules:
    - If scope is global (Employee): Returns any restaurant transaction
    - If scope is institution-scoped (Supplier): Returns transaction only if restaurant belongs to their institution
    
    Args:
        db: Database connection
        transaction_id: Transaction ID
        scope: Optional institution scope for filtering (for Employees/Suppliers)
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        RestaurantTransactionEnrichedResponseSchema with institution, entity, restaurant, plate, and address information, or None if not found
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _restaurant_transaction_enriched_service.get_enriched_by_id(
        db,
        transaction_id,
        select_fields=[
            "rt.transaction_id",
            "rt.restaurant_id",
            "r.institution_id",
            "COALESCE(i.name, '') as institution_name",
            "r.institution_entity_id",
            "COALESCE(ie.name, '') as institution_entity_name",
            "COALESCE(r.name, '') as restaurant_name",
            "rt.plate_selection_id",
            "COALESCE(pr.name, '') as plate_name",
            "rt.discretionary_id",
            "rt.credit_currency_id",
            "rt.currency_code",
            "COALESCE(a.country, '') as country",
            "rt.was_collected",
            "rt.ordered_timestamp",
            "rt.collected_timestamp",
            "rt.arrival_time",
            "rt.completion_time",
            "rt.expected_completion_time",
            "rt.transaction_type",
            "rt.credit",
            "rt.no_show_discount",
            "rt.final_amount",
            "rt.is_archived",
            "rt.status",
            "rt.created_date",
            "rt.modified_by",
            "rt.modified_date"
        ],
        joins=[
            ("INNER", "restaurant_info", "r", "rt.restaurant_id = r.restaurant_id"),
            ("LEFT", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("LEFT", "institution_entity_info", "ie", "r.institution_entity_id = ie.institution_entity_id"),
            ("LEFT", "address_info", "a", "r.address_id = a.address_id"),
            ("LEFT", "plate_selection", "ps", "rt.plate_selection_id = ps.plate_selection_id"),
            ("LEFT", "plate_info", "pi", "ps.plate_id = pi.plate_id"),
            ("LEFT", "product_info", "pr", "pi.product_id = pr.product_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

# =============================================================================
# PLATE PICKUP ENRICHED BUSINESS LOGIC
# =============================================================================

def get_enriched_plate_pickups(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    user_id: Optional[UUID] = None,
    include_archived: bool = False
) -> List[PlatePickupEnrichedResponseSchema]:
    """
    Get all plate pickups with enriched data (restaurant name, address details, product name, credit).
    Returns an array of enriched plate pickup records.
    
    Scoping rules:
    - If scope is global (Employee): Returns all plate pickups
    - If scope is institution-scoped (Supplier): Returns plate pickups for restaurants in their institution
    - If user_id is provided (Customer): Returns only plate pickups for that specific user
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering (for Employees/Suppliers)
        user_id: Optional user ID for user-level filtering (for Customers)
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        List of PlatePickupEnrichedResponseSchema with restaurant, address, product, and credit information
        
    Raises:
        HTTPException: For system errors or database failures
    """
    try:
        conditions = []
        params: List[Any] = []
        
        # Apply user-level filtering (for Customers)
        if user_id is not None:
            user_id_str = str(user_id) if isinstance(user_id, UUID) else user_id
            conditions.append("ppl.user_id = %s::uuid")
            params.append(user_id_str)
        
        # Apply institution scoping (for Suppliers - filter by restaurant's institution)
        if scope and not scope.is_global and scope.institution_id:
            conditions.append("r.institution_id = %s::uuid")
            params.append(str(scope.institution_id))
        
        # Filter by archived status
        if not include_archived:
            conditions.append("ppl.is_archived = FALSE")
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        query = f"""
            SELECT 
                ppl.plate_pickup_id,
                ppl.plate_selection_id,
                ppl.user_id,
                ppl.restaurant_id,
                COALESCE(r.name, '') as restaurant_name,
                COALESCE(a.country, '') as country,
                COALESCE(a.province, '') as province,
                COALESCE(a.city, '') as city,
                COALESCE(a.postal_code, '') as postal_code,
                ppl.plate_id,
                ppl.product_id,
                COALESCE(prod.name, '') as product_name,
                COALESCE(p.credit, 0) as credit,
                ppl.qr_code_id,
                ppl.qr_code_payload,
                ppl.is_archived,
                ppl.status,
                COALESCE(ppl.was_collected, FALSE) as was_collected,
                ppl.arrival_time,
                ppl.completion_time,
                ppl.expected_completion_time,
                ppl.confirmation_code,
                ppl.created_date,
                ppl.modified_by,
                ppl.modified_date
            FROM plate_pickup_live ppl
            LEFT JOIN restaurant_info r ON ppl.restaurant_id = r.restaurant_id
            LEFT JOIN address_info a ON r.address_id = a.address_id
            LEFT JOIN product_info prod ON ppl.product_id = prod.product_id
            LEFT JOIN plate_info p ON ppl.plate_id = p.plate_id
            {where_clause}
            ORDER BY ppl.created_date DESC
        """
        
        # Convert all params to strings to avoid UUID issues
        safe_params = tuple(str(p) if isinstance(p, UUID) else p for p in params)
        
        results = db_read(
            query,
            safe_params,
            connection=db,
            fetch_one=False
        )
        
        if not results:
            return []
        
        enriched_pickups = []
        for row in results:
            try:
                # Convert UUID objects and other types to Pydantic-compatible formats
                row_dict = {}
                for key, value in row.items():
                    if value is None:
                        row_dict[key] = value
                    elif isinstance(value, UUID):
                        row_dict[key] = str(value)
                    elif isinstance(value, datetime):
                        # Keep datetime objects as-is (Pydantic handles them)
                        row_dict[key] = value
                    else:
                        row_dict[key] = value
                enriched_pickups.append(PlatePickupEnrichedResponseSchema(**row_dict))
            except Exception as schema_error:
                log_error(f"Error parsing plate pickup row for user {user_id}: {schema_error}. Row data: {row}")
                # Skip invalid rows instead of failing completely
                continue
        
        return enriched_pickups
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        # Safely convert exception to string, handling UUID objects and other types
        try:
            error_msg = str(e)
        except Exception as str_error:
            try:
                error_msg = repr(e)
            except Exception:
                error_msg = f"Error converting exception to string: {type(e).__name__}"
        log_error(f"Error getting enriched plate pickups for user {user_id}: {error_msg}\nFull traceback:\n{error_trace}")
        raise HTTPException(status_code=500, detail=f"Failed to get enriched plate pickups: {error_msg}")

# =============================================================================
# PLATE KITCHEN DAYS ENRICHED BUSINESS LOGIC
# =============================================================================

# Initialize EnrichedService instance for plate kitchen days
# Institution scoping is via: plate_kitchen_days -> plate_info -> restaurant_info -> institution_id
_plate_kitchen_day_enriched_service = EnrichedService(
    base_table="plate_kitchen_days",
    table_alias="pkd",
    id_column="plate_kitchen_day_id",
    schema_class=PlateKitchenDayEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="r"  # institution_id is on the joined restaurant_info table
)

def get_enriched_plate_kitchen_days(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[PlateKitchenDayEnrichedResponseSchema]:
    """
    Get all plate kitchen days with enriched data (institution name, restaurant name, plate name, dietary).
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        List of PlateKitchenDayEnrichedResponseSchema with enriched data
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _plate_kitchen_day_enriched_service.get_enriched(
        db,
        select_fields=[
            "pkd.plate_kitchen_day_id",
            "pkd.plate_id",
            "pkd.kitchen_day",
            "pkd.status",
            "COALESCE(i.name, '') as institution_name",
            "COALESCE(r.name, '') as restaurant_name",
            "COALESCE(pr.name, '') as plate_name",  # Product name is the "plate name"
            "pr.dietary",
            "pkd.is_archived",
            "pkd.created_date",
            "pkd.modified_by",
            "pkd.modified_date"
        ],
        joins=[
            ("INNER", "plate_info", "p", "pkd.plate_id = p.plate_id"),
            ("INNER", "restaurant_info", "r", "p.restaurant_id = r.restaurant_id"),
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("INNER", "product_info", "pr", "p.product_id = pr.product_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

def get_enriched_plate_kitchen_day_by_id(
    kitchen_day_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> Optional[PlateKitchenDayEnrichedResponseSchema]:
    """
    Get a single plate kitchen day by ID with enriched data (institution name, restaurant name, plate name, dietary).
    
    Args:
        kitchen_day_id: Plate kitchen day ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        PlateKitchenDayEnrichedResponseSchema with enriched data, or None if not found
        
    Raises:
        HTTPException: For system errors or database failures
    """
    return _plate_kitchen_day_enriched_service.get_enriched_by_id(
        kitchen_day_id,
        db,
        select_fields=[
            "pkd.plate_kitchen_day_id",
            "pkd.plate_id",
            "pkd.kitchen_day",
            "pkd.status",
            "COALESCE(i.name, '') as institution_name",
            "COALESCE(r.name, '') as restaurant_name",
            "COALESCE(pr.name, '') as plate_name",  # Product name is the "plate name"
            "pr.dietary",
            "pkd.is_archived",
            "pkd.created_date",
            "pkd.modified_by",
            "pkd.modified_date"
        ],
        joins=[
            ("INNER", "plate_info", "p", "pkd.plate_id = p.plate_id"),
            ("INNER", "restaurant_info", "r", "p.restaurant_id = r.restaurant_id"),
            ("INNER", "institution_info", "i", "r.institution_id = i.institution_id"),
            ("INNER", "product_info", "pr", "p.product_id = pr.product_id")
        ],
        scope=scope,
        include_archived=include_archived
    )


# RESTAURANT HOLIDAYS ENRICHED BUSINESS LOGIC
def get_enriched_restaurant_holidays(
    restaurant_id: Optional[UUID] = None,
    db: psycopg2.extensions.connection = None,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[RestaurantHolidayEnrichedResponseSchema]:
    """
    Get enriched restaurant holidays that includes both restaurant-specific holidays
    and applicable national holidays.
    
    This endpoint allows restaurant people (Suppliers) to see national holidays
    that apply to their restaurants without direct access to the employee-only
    national holidays API.
    
    Args:
        restaurant_id: Optional restaurant ID to filter by (if None, returns holidays for all accessible restaurants)
        db: Database connection
        scope: Optional institution scope for filtering (Suppliers see their restaurants, Employees see all)
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        List of RestaurantHolidayEnrichedResponseSchema with both restaurant and national holidays
        
    Raises:
        HTTPException: For system errors or database failures
    """
    from app.services.crud_service import restaurant_service, address_service
    from app.services.market_detection import MarketDetectionService
    
    try:
        enriched_holidays = []
        
        # Step 1: Get restaurant holidays
        # Build query for restaurant holidays with scoping
        restaurant_conditions = []
        restaurant_params = []
        
        if not include_archived:
            restaurant_conditions.append("rh.is_archived = FALSE")
        
        if restaurant_id:
            restaurant_conditions.append("rh.restaurant_id = %s")
            restaurant_params.append(str(restaurant_id))
        
        # Add institution scoping if needed
        if scope and not scope.is_global:
            restaurant_conditions.append("r.institution_id = %s")
            restaurant_params.append(str(scope.institution_id))
        
        restaurant_where = " WHERE " + " AND ".join(restaurant_conditions) if restaurant_conditions else ""
        
        restaurant_query = f"""
            SELECT 
                rh.holiday_id,
                rh.restaurant_id,
                r.name as restaurant_name,
                i.name as institution_name,
                rh.country,
                rh.holiday_date,
                rh.holiday_name,
                rh.is_recurring,
                rh.recurring_month_day,
                rh.status,
                rh.is_archived,
                rh.created_date,
                rh.modified_by,
                rh.modified_date
            FROM restaurant_holidays rh
            INNER JOIN restaurant_info r ON rh.restaurant_id = r.restaurant_id
            INNER JOIN institution_info i ON r.institution_id = i.institution_id
            {restaurant_where}
            ORDER BY rh.holiday_date DESC
        """
        
        restaurant_holidays = db_read(
            restaurant_query,
            tuple(restaurant_params) if restaurant_params else None,
            connection=db
        )
        
        # Convert restaurant holidays to enriched schema
        for row in restaurant_holidays or []:
            enriched_holidays.append(RestaurantHolidayEnrichedResponseSchema(
                holiday_type="restaurant",
                holiday_id=UUID(row.get("holiday_id")),
                restaurant_id=UUID(row.get("restaurant_id")),
                restaurant_name=row.get("restaurant_name"),
                institution_name=row.get("institution_name"),
                country=row.get("country"),
                holiday_date=row.get("holiday_date"),
                holiday_name=row.get("holiday_name"),
                is_recurring=row.get("is_recurring", False),
                recurring_month_day=row.get("recurring_month_day"),
                status=row.get("status", Status.ACTIVE.value),  # Use actual status from database
                is_archived=row.get("is_archived", False),
                created_date=row.get("created_date"),
                modified_by=UUID(row.get("modified_by")) if row.get("modified_by") else None,
                modified_date=row.get("modified_date"),
                country_code=None,
                is_editable=True  # Restaurant holidays are editable by suppliers
            ))
        
        # Step 2: Get national holidays for restaurants the user has access to
        # First, get list of restaurants and their country codes
        restaurant_conditions_national = []
        restaurant_params_national = []
        
        if restaurant_id:
            restaurant_conditions_national.append("r.restaurant_id = %s")
            restaurant_params_national.append(str(restaurant_id))
        
        # Add institution scoping if needed
        if scope and not scope.is_global:
            restaurant_conditions_national.append("r.institution_id = %s")
            restaurant_params_national.append(str(scope.institution_id))
        
        restaurant_where_national = " WHERE " + " AND ".join(restaurant_conditions_national) if restaurant_conditions_national else ""
        
        # Get restaurants with their addresses to determine country codes
        restaurants_query = f"""
            SELECT DISTINCT
                r.restaurant_id,
                a.country
            FROM restaurant_info r
            INNER JOIN address_info a ON r.address_id = a.address_id
            {restaurant_where_national}
        """
        
        restaurants = db_read(
            restaurants_query,
            tuple(restaurant_params_national) if restaurant_params_national else None,
            connection=db
        )
        
        # Collect unique country codes
        country_codes = set()
        for restaurant_row in restaurants or []:
            country_name = restaurant_row.get("country")
            if country_name:
                country_code = MarketDetectionService._country_name_to_code(country_name)
                if country_code:
                    country_codes.add(country_code)
        
        # Get national holidays for these country codes
        if country_codes:
            national_conditions = ["nh.is_archived = FALSE"]
            national_params = []
            
            # Build IN clause for country codes
            placeholders = ",".join(["%s"] * len(country_codes))
            national_conditions.append(f"nh.country_code IN ({placeholders})")
            national_params.extend(list(country_codes))
            
            national_where = " WHERE " + " AND ".join(national_conditions)
            
            national_query = f"""
                SELECT 
                    nh.country_code,
                    nh.holiday_name,
                    nh.holiday_date,
                    nh.is_recurring,
                    nh.status
                FROM national_holidays nh
                {national_where}
                ORDER BY nh.holiday_date DESC
            """
            
            national_holidays = db_read(
                national_query,
                tuple(national_params),
                connection=db
            )
            
            # Convert national holidays to enriched schema
            for row in national_holidays or []:
                enriched_holidays.append(RestaurantHolidayEnrichedResponseSchema(
                    holiday_type="national",
                    country_code=row.get("country_code"),
                    holiday_name=row.get("holiday_name"),
                    holiday_date=row.get("holiday_date"),
                    is_recurring=row.get("is_recurring", False),
                    holiday_id=None,
                    restaurant_id=None,
                    restaurant_name=None,  # National holidays are not tied to a specific restaurant
                    institution_name=None,  # National holidays are not tied to a specific institution
                    country=None,
                    recurring_month_day=None,
                    status=row.get("status", Status.ACTIVE.value),  # Use actual status from database
                    is_archived=False,  # National holidays shown are always non-archived (we filter archived ones)
                    created_date=None,
                    modified_by=None,
                    modified_date=None,
                    is_editable=False  # National holidays are NOT editable by suppliers
                ))
        
        # Sort all holidays by date (most recent first)
        enriched_holidays.sort(key=lambda x: x.holiday_date, reverse=True)
        
        return enriched_holidays
        
    except Exception as e:
        log_error(f"Error getting enriched restaurant holidays: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve enriched restaurant holidays: {str(e)}")


def get_enriched_restaurant_holidays_by_restaurant(
    restaurant_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[RestaurantHolidayEnrichedResponseSchema]:
    """
    Get enriched restaurant holidays for a specific restaurant.
    
    Convenience wrapper around get_enriched_restaurant_holidays with restaurant_id filter.
    
    Args:
        restaurant_id: Restaurant ID
        db: Database connection
        scope: Optional institution scope for filtering
        include_archived: Whether to include archived records (default: False)
        
    Returns:
        List of RestaurantHolidayEnrichedResponseSchema for the specified restaurant
    """
    return get_enriched_restaurant_holidays(
        restaurant_id=restaurant_id,
        db=db,
        scope=scope,
        include_archived=include_archived
    )


# =============================================================================
# PAYMENT METHOD ENRICHED SERVICES
# =============================================================================

# Initialize EnrichedService instance for payment methods
_payment_method_enriched_service = EnrichedService(
    base_table="payment_method",
    table_alias="pm",
    id_column="payment_method_id",
    schema_class=PaymentMethodEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="u"  # institution_id is on the joined user_info table
)

def get_enriched_payment_methods(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False,
    user_id: Optional[UUID] = None
) -> List[PaymentMethodEnrichedResponseSchema]:
    """
    Get all payment methods with enriched data (user information).
    Includes: user_full_name, user_username, user_email, user_cellphone.
    Uses SQL JOINs to avoid N+1 queries.
    
    Args:
        db: Database connection
        scope: Optional institution scope for filtering (not typically used for payment methods)
        include_archived: Whether to include archived records
        user_id: Optional user_id to filter payment methods by user
        
    Returns:
        List of enriched payment method schemas with user information
    """
    additional_conditions = []
    if user_id:
        additional_conditions.append(("pm.user_id = %s::uuid", str(user_id)))
    
    return _payment_method_enriched_service.get_enriched(
        db,
        select_fields=[
            "pm.payment_method_id",
            "pm.user_id",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as full_name",
            "u.username",
            "u.email",
            "u.cellphone",
            "pm.method_type",
            "pm.method_type_id",
            "pm.is_archived",
            "pm.status",
            "pm.is_default",
            "pm.created_date",
            "pm.modified_by",
            "pm.modified_date"
        ],
        joins=[
            ("INNER", "user_info", "u", "pm.user_id = u.user_id")
        ],
        scope=scope,
        include_archived=include_archived,
        additional_conditions=additional_conditions if additional_conditions else None
    )

def get_enriched_payment_method_by_id(
    payment_method_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> Optional[PaymentMethodEnrichedResponseSchema]:
    """
    Get a single payment method by ID with enriched data (user information).
    Includes: user_full_name, user_username, user_email, user_cellphone.
    Uses SQL JOINs to avoid N+1 queries.
    
    Args:
        payment_method_id: Payment method ID
        db: Database connection
        scope: Optional institution scope for filtering (not typically used for payment methods)
        include_archived: Whether to include archived records
        
    Returns:
        Enriched payment method schema with user information, or None if not found
    """
    return _payment_method_enriched_service.get_enriched_by_id(
        payment_method_id,
        db,
        select_fields=[
            "pm.payment_method_id",
            "pm.user_id",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as full_name",
            "u.username",
            "u.email",
            "u.cellphone",
            "pm.method_type",
            "pm.method_type_id",
            "pm.is_archived",
            "pm.status",
            "pm.is_default",
            "pm.created_date",
            "pm.modified_by",
            "pm.modified_date"
        ],
        joins=[
            ("INNER", "user_info", "u", "pm.user_id = u.user_id")
        ],
        scope=scope,
        include_archived=include_archived
    )

# =============================================================================
# FINTECH LINK ASSIGNMENT ENRICHED SERVICES
# =============================================================================

# Initialize EnrichedService instance for fintech link assignments
_fintech_link_assignment_enriched_service = EnrichedService(
    base_table="fintech_link_assignment",
    table_alias="fla",
    id_column="fintech_link_assignment_id",
    schema_class=FintechLinkAssignmentEnrichedResponseSchema,
    institution_column=None,  # Scoping is done through payment_method -> user_id
    institution_table_alias=None
)

def get_enriched_fintech_link_assignments(
    db: psycopg2.extensions.connection,
    *,
    user_id: Optional[UUID] = None,
    include_archived: bool = False
) -> List[FintechLinkAssignmentEnrichedResponseSchema]:
    """
    Get all fintech link assignments with enriched data.
    Includes: provider (from fintech_link_info), plan_name, credit, price (from plan_info),
    and user information (full_name, username, email, cellphone from user_info via payment_method).
    Uses SQL JOINs to avoid N+1 queries.
    
    Scoping:
    - Employees: See all assignments
    - Customers: See only their own assignments (via payment_method.user_id)
    
    Args:
        db: Database connection
        user_id: Optional user_id to filter assignments by user (for customer self-scope)
        include_archived: Whether to include archived records
        
    Returns:
        List of enriched fintech link assignment schemas
    """
    additional_conditions = []
    if user_id:
        # Filter by user through payment_method
        additional_conditions.append(("pm.user_id = %s::uuid", str(user_id)))
    
    return _fintech_link_assignment_enriched_service.get_enriched(
        db,
        select_fields=[
            "fla.fintech_link_assignment_id",
            "fla.payment_method_id",
            "fla.fintech_link_id",
            "fl.provider",
            "pl.name as plan_name",
            "pl.credit",
            "pl.price",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as full_name",
            "u.username",
            "u.email",
            "u.cellphone",
            "fla.is_archived",
            "fla.status",
            "fla.created_date"
        ],
        joins=[
            ("INNER", "fintech_link_info", "fl", "fla.fintech_link_id = fl.fintech_link_id"),
            ("INNER", "plan_info", "pl", "fl.plan_id = pl.plan_id"),
            ("INNER", "payment_method", "pm", "fla.payment_method_id = pm.payment_method_id"),
            ("INNER", "user_info", "u", "pm.user_id = u.user_id")
        ],
        scope=None,  # Scoping handled via user_id filter
        include_archived=include_archived,
        additional_conditions=additional_conditions if additional_conditions else None
    )


def get_enriched_fintech_link_assignment_by_id(
    fintech_link_assignment_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    user_id: Optional[UUID] = None,
    include_archived: bool = False
) -> Optional[FintechLinkAssignmentEnrichedResponseSchema]:
    """
    Get a single fintech link assignment by ID with enriched data.
    Includes: provider (from fintech_link_info), plan_name, credit, price (from plan_info),
    and user information (full_name, username, email, cellphone from user_info via payment_method).
    Uses SQL JOINs to avoid N+1 queries.
    
    Scoping:
    - Employees: Can access any assignment
    - Customers: Can only access their own assignments (via payment_method.user_id)
    
    Args:
        fintech_link_assignment_id: Fintech link assignment ID
        db: Database connection
        user_id: Optional user_id to verify ownership (for customer self-scope)
        include_archived: Whether to include archived records
        
    Returns:
        Enriched fintech link assignment schema, or None if not found
    """
    additional_conditions = []
    if user_id:
        # Filter by user through payment_method
        additional_conditions.append(("pm.user_id = %s::uuid", str(user_id)))
    
    return _fintech_link_assignment_enriched_service.get_enriched_by_id(
        fintech_link_assignment_id,
        db,
        select_fields=[
            "fla.fintech_link_assignment_id",
            "fla.payment_method_id",
            "fla.fintech_link_id",
            "fl.provider",
            "pl.name as plan_name",
            "pl.credit",
            "pl.price",
            "TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as full_name",
            "u.username",
            "u.email",
            "u.cellphone",
            "fla.is_archived",
            "fla.status",
            "fla.created_date"
        ],
        joins=[
            ("INNER", "fintech_link_info", "fl", "fla.fintech_link_id = fl.fintech_link_id"),
            ("INNER", "plan_info", "pl", "fl.plan_id = pl.plan_id"),
            ("INNER", "payment_method", "pm", "fla.payment_method_id = pm.payment_method_id"),
            ("INNER", "user_info", "u", "pm.user_id = u.user_id")
        ],
        scope=None,  # Scoping handled via user_id filter
        include_archived=include_archived,
        additional_conditions=additional_conditions if additional_conditions else None
    )
