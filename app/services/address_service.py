"""
Address Business Logic Service

This service contains all business logic related to address operations,
including geocoding integration, timezone calculation, and address validation.

Address type is derived from linkages only (restaurant, institution entity,
employer, payment method). The API does not accept address_type
from clients; it is computed server-side and returned for display.
"""

from datetime import datetime, timezone
from uuid import UUID
from typing import Dict, Any, Optional, List
from fastapi import HTTPException
import psycopg2.extensions

from app.dto.models import AddressDTO, GeolocationDTO
from app.services.crud_service import address_service, geolocation_service
from app.utils.db import db_read, db_insert, db_update
from app.security.institution_scope import InstitutionScope
from app.utils.log import log_info, log_warning
from app.services.geolocation_service import call_geocode_api
from app.config import Status
from app.config.enums.address_types import AddressType


def derive_address_type_from_linkages(
    address_id: UUID,
    db: psycopg2.extensions.connection,
) -> List[str]:
    """
    Derive address_type from connected objects (restaurant, institution entity,
    employer, payment method). Address type is never taken from
    client input; it reflects actual linkages.
    """
    types: List[str] = []
    aid = str(address_id)

    # Restaurant
    r = db_read(
        "SELECT 1 FROM restaurant_info WHERE address_id = %s AND NOT is_archived",
        (aid,),
        connection=db,
        fetch_one=True,
    )
    if r:
        types.append(AddressType.RESTAURANT.value)

    # Entity Address (institution entity) - also used for Entity Billing (settlement pipeline uses entity address for country)
    ie = db_read(
        "SELECT 1 FROM institution_entity_info WHERE address_id = %s AND NOT is_archived",
        (aid,),
        connection=db,
        fetch_one=True,
    )
    if ie:
        types.append(AddressType.ENTITY_ADDRESS.value)
        types.append(AddressType.ENTITY_BILLING.value)

    # Customer Employer: address is employer's primary address (employer_info.address_id) or address has employer_id set
    emp_primary = db_read(
        "SELECT 1 FROM employer_info WHERE address_id = %s AND NOT is_archived",
        (aid,),
        connection=db,
        fetch_one=True,
    )
    addr_employer = db_read(
        "SELECT employer_id FROM address_info WHERE address_id = %s AND employer_id IS NOT NULL",
        (aid,),
        connection=db,
        fetch_one=True,
    )
    is_employer_linked = bool(emp_primary or addr_employer)
    if is_employer_linked:
        types.append(AddressType.CUSTOMER_EMPLOYER.value)

    # Customer Billing (payment method)
    pm = db_read(
        "SELECT 1 FROM payment_method WHERE address_id = %s AND NOT is_archived",
        (aid,),
        connection=db,
        fetch_one=True,
    )
    if pm:
        types.append(AddressType.CUSTOMER_BILLING.value)

    # Customer Home: address belongs to Customer institution and is NOT linked to employer or payment method
    # Must exclude both employer primary (employer_info) and employer-linked (address_info.employer_id)
    if not is_employer_linked and not pm:
        inst = db_read(
            """
            SELECT i.institution_type
            FROM address_info a
            JOIN institution_info i ON a.institution_id = i.institution_id
            WHERE a.address_id = %s
            """,
            (aid,),
            connection=db,
            fetch_one=True,
        )
        if inst:
            it = inst.get("institution_type")
            if it in ("Customer", "customer") or (hasattr(it, "value") and getattr(it, "value", None) == "Customer"):
                types.append(AddressType.CUSTOMER_HOME.value)

    return sorted(set(types))


def _upsert_address_subpremise(
    address_id: UUID,
    user_id: UUID,
    modified_by: UUID,
    db: psycopg2.extensions.connection,
    *,
    floor: Optional[str] = None,
    apartment_unit: Optional[str] = None,
    is_default: bool = False,
    commit: bool = True,
) -> None:
    """
    Upsert address_subpremise for (address_id, user_id). At most one is_default=True per user.
    """
    aid, uid, mby = str(address_id), str(user_id), str(modified_by)
    if is_default:
        db_update(
            "address_subpremise",
            {"is_default": False, "modified_by": mby},
            {"user_id": uid},
            connection=db,
            commit=False,
        )
    existing = db_read(
        "SELECT subpremise_id FROM address_subpremise WHERE address_id = %s AND user_id = %s",
        (aid, uid),
        connection=db,
        fetch_one=True,
    )
    if existing:
        db_update(
            "address_subpremise",
            {
                "floor": floor,
                "apartment_unit": apartment_unit,
                "is_default": is_default,
                "modified_by": mby,
                "modified_date": datetime.now(timezone.utc),
            },
            {"address_id": aid, "user_id": uid},
            connection=db,
            commit=commit,
        )
    else:
        db_insert(
            "address_subpremise",
            {
                "address_id": address_id,
                "user_id": user_id,
                "floor": floor,
                "apartment_unit": apartment_unit,
                "is_default": is_default,
                "created_by": modified_by,
                "modified_by": modified_by,
            },
            connection=db,
            commit=commit,
        )


def get_addresses_for_customer(
    user_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    include_archived: bool = False,
) -> List[AddressDTO]:
    """
    Get addresses visible to a Customer for GET /addresses and GET /addresses/enriched.

    - Home and billing: address.user_id = user_id OR subpremise (address_id, user_id) exists
    - Employer: only the address assigned as employer_address_id (from user_info)
    - Enriches with floor, apartment_unit, is_default from address_subpremise
    """
    from app.services.crud_service import user_service

    user = user_service.get_by_id(user_id, db, scope=None)
    if not user:
        return []

    employer_id = getattr(user, "employer_id", None)
    employer_address_id = getattr(user, "employer_address_id", None)
    uid = str(user_id)

    # Single query: addresses where (a.user_id = uid OR sp exists) OR a is assigned employer address
    # LEFT JOIN subpremise for this user to get floor, unit, is_default
    params: List[Any] = [uid, uid]
    employer_clause = ""
    if employer_address_id and employer_id:
        employer_clause = " OR (a.address_id = %s::uuid AND a.employer_id = %s::uuid)"
        params.extend([str(employer_address_id), str(employer_id)])

    archived = "" if include_archived else " AND a.is_archived = FALSE"
    q = f"""
        SELECT a.*, COALESCE(m.country_name, '') AS country_name,
               sp.floor, sp.apartment_unit, sp.is_default
        FROM address_info a
        LEFT JOIN market_info m ON a.country_code = m.country_code
        LEFT JOIN address_subpremise sp ON sp.address_id = a.address_id AND sp.user_id = %s
        WHERE (a.user_id = %s OR sp.user_id IS NOT NULL{employer_clause}){archived}
    """
    rows = db_read(q, tuple(params), connection=db)
    if not rows:
        return []

    result: List[AddressDTO] = []
    for r in rows:
        # For employer address filter: only include if it's the assigned one
        if r.get("employer_id") and employer_address_id:
            if str(r.get("address_id")) != str(employer_address_id):
                continue
            if employer_id and str(r.get("employer_id")) != str(employer_id):
                continue
        elif r.get("employer_id") and not employer_address_id:
            continue  # employer address but user has none assigned
        d = {**r, "floor": r.get("floor"), "apartment_unit": r.get("apartment_unit"), "is_default": r.get("is_default") or False}
        result.append(AddressDTO(**d))

    return result


def update_address_type_from_linkages(
    address_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    commit: bool = True,
) -> List[str]:
    """
    Recompute address_type from linkages and persist to address_info.
    Returns the new address_type list.
    """
    derived = derive_address_type_from_linkages(address_id, db)
    db_update(
        "address_info",
        {"address_type": derived},
        {"address_id": address_id},
        connection=db,
        commit=commit,
    )
    return derived


class AddressBusinessService:
    """Service for handling address business logic"""
    
    def __init__(self):
        pass
    
    def create_address_with_geocoding(
        self, 
        address_data: Dict[str, Any], 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection,
        scope: Optional[InstitutionScope] = None,
        commit: bool = True
    ) -> AddressDTO:
        """
        Create a new address with automatic geocoding for restaurants, customer home, and customer employer addresses.
        
        Geocoding failures are non-blocking - addresses are created successfully
        even if geocoding fails (e.g., when geocoding API is unavailable).
        
        Args:
            address_data: Address data dictionary
            current_user: Current user information
            db: Database connection
            scope: Optional institution scope for access control
            commit: Whether to commit immediately after insert (default: True).
                    Set to False for atomic multi-operation transactions.
            
        Returns:
            Created address DTO
            
        Raises:
            HTTPException: For validation errors (not for geocoding failures)
        """
        # Set modified_by field
        address_data["modified_by"] = current_user["user_id"]

        # address_type is never taken from client; derived from linkages only
        address_data.pop("address_type", None)
        address_data["address_type"] = []

        # place_id path: fetch Place Details, map to address, validate geography, create with geolocation
        place_id_raw = (address_data.get("place_id") or "").strip()
        if place_id_raw:
            address_data, geoloc_from_place = self._resolve_address_from_place_id(
                place_id_raw, address_data, current_user
            )
        else:
            # Structured (manual) create is internal/testing only. Production must use place_id.
            from app.config.settings import get_settings
            if not getattr(get_settings(), "DEV_MODE", False):
                raise HTTPException(
                    status_code=403,
                    detail="Address creation via manual entry is only available in development. Use the address search (place_id) for production.",
                )
            geoloc_from_place = None

        # floor, apartment_unit, is_default go to address_subpremise (not address_info); extract before create
        subpremise_floor = address_data.pop("floor", None)
        subpremise_unit = address_data.pop("apartment_unit", None)
        subpremise_is_default = address_data.pop("is_default", False)

        # Resolve country to alpha-2 only (DB and API standard); accept country_code (normalized by schema) or country (name)
        from app.services.market_service import market_service
        from app.gateways.google_places_gateway import country_name_to_alpha2
        from app.utils.country import normalize_country_code
        country_code = address_data.get("country_code")
        if not country_code and address_data.get("country"):
            raw = (address_data.get("country") or "").strip()
            address_data.pop("country", None)
            alpha2 = country_name_to_alpha2(raw) if len(raw) != 2 or not raw.isalpha() else raw
            if not alpha2 and len(raw) == 2 and raw.isalpha():
                alpha2 = raw
            if alpha2:
                country_code = normalize_country_code(alpha2)
                address_data["country_code"] = country_code
        if country_code:
            # Already normalized by schema when from body, or by normalize_country_code when from country name
            address_data["country_code"] = country_code
            address_data.pop("country_name", None)  # not stored on address; resolved via market_info on read
            market = market_service.get_by_country_code(country_code)
            if not market:
                raise HTTPException(status_code=400, detail=f"Invalid country_code: {country_code}. Market not found.")
            if market.get("country_code") == "GL":
                raise HTTPException(
                    status_code=400,
                    detail="Addresses cannot be registered to Global Marketplace. Please select a specific country (e.g. Argentina, Peru, Chile).",
                )
            country_name_for_log = market["country_name"]
        else:
            raise HTTPException(
                status_code=400,
                detail="country_code or country (country name) is required. If sending country name, use a supported value (e.g. Argentina, Peru, Chile)."
            )

        # Validate address data (required fields, country-province-city combination)
        self.validate_address_data(address_data)
        
        # Automatically set timezone based on country_code (alpha-2) and province
        from app.services.geolocation_service import get_timezone_from_address
        province = address_data.get("province", "")
        timezone = get_timezone_from_address(country_code, province, db)
        address_data["timezone"] = timezone
        log_info(f"Set timezone '{timezone}' for address in {province}, {country_name_for_log} ({country_code})")

        # Create the address first (even for restaurants), so we get an address_id
        # NOTE: address_service.create() should ONLY be called from this business service.
        # All external callers should use address_business_service.create_address_with_geocoding() instead.
        new_addr = address_service.create(address_data, db, scope=scope, commit=commit)

        # Create address_subpremise when user_id is set (Comensal home/other; floor, unit, is_default)
        user_id = address_data.get("user_id") or getattr(new_addr, "user_id", None)
        if user_id:
            _upsert_address_subpremise(
                new_addr.address_id,
                UUID(str(user_id)) if isinstance(user_id, str) else user_id,
                current_user["user_id"],
                db,
                floor=subpremise_floor,
                apartment_unit=subpremise_unit,
                is_default=subpremise_is_default,
                commit=commit,
            )

        # Refresh address_type from linkages (new address has none, so remains [])
        derived_types = update_address_type_from_linkages(new_addr.address_id, db, commit=commit)
        # Re-fetch so response has correct address_type and subpremise (floor, unit, is_default)
        if user_id:
            new_addr = self._get_address_with_subpremise(
                new_addr.address_id, user_id, db, scope=scope
            ) or address_service.get_by_id(new_addr.address_id, db, scope=scope) or new_addr
        else:
            new_addr = address_service.get_by_id(new_addr.address_id, db, scope=scope) or new_addr

        # Handle geocoding: when we have Place Details (place_id path), store immediately.
        # Otherwise geocode for restaurant/customer employer/customer home from derived types.
        address_types = derived_types
        if geoloc_from_place:
            self._create_geolocation_from_place_details(new_addr, geoloc_from_place, current_user, db, commit=commit)
        elif isinstance(address_types, list):
            should_geocode = (
                "Restaurant" in address_types or
                "Customer Employer" in address_types or
                "Customer Home" in address_types
            )
            if should_geocode:
                self._geocode_address(new_addr, address_data, current_user, db, commit=commit, country_name=country_name_for_log)

        return new_addr
    
    def _geocode_address(
        self,
        address: AddressDTO,
        address_data: Dict[str, Any],
        current_user: Dict[str, Any],
        db: psycopg2.extensions.connection,
        commit: bool = True,
        *,
        country_name: Optional[str] = None
    ) -> None:
        """
        Geocode an address and create geolocation record.

        Geocoding is performed for Restaurant, Customer Employer, and Customer Home addresses.
        Geocoding failures are logged but do not block address creation.
        This allows addresses to be created even when the geocoding API
        is unavailable (e.g., in development/testing environments).

        Args:
            address: Created address DTO
            address_data: Original address data (country_name not stored on address; pass via country_name)
            current_user: Current user information
            db: Database connection
            commit: Whether to commit geolocation creation immediately (default: True).
                    Set to False for atomic multi-operation transactions.
            country_name: Country name for geocoding string (from market_info lookup).
        """
        # Build full address string for geocoding (country_name from market, not stored on address)
        full_address = self._build_full_address_string(address_data, country_name=country_name)
        
        # Determine address type for logging
        address_types = address_data.get("address_type", [])
        address_type_str = ", ".join(address_types) if isinstance(address_types, list) else str(address_types)
        
        try:
            # Call geocoding API
            geocode_result = call_geocode_api(full_address)
            
            # Validate geocoding result
            if not geocode_result or "latitude" not in geocode_result or "longitude" not in geocode_result:
                log_warning(f"Geolocation failed for {address_type_str} address: {full_address}. Address created without geolocation.")
                return  # Non-blocking: address is already created, just skip geocoding
            
            # Create geolocation record
            geodata = {
                "address_id": address.address_id,
                "latitude": geocode_result["latitude"],
                "longitude": geocode_result["longitude"],
                "is_archived": False,
                "status": Status.ACTIVE,
                "modified_by": current_user["user_id"],
                "modified_date": datetime.now(timezone.utc)
            }
            
            new_geo = geolocation_service.create(geodata, db, commit=commit)
            
            log_info(f"{address_type_str} address geocoded and saved (Geo ID: {new_geo.geolocation_id}) for address ID {address.address_id}")
        except Exception as e:
            # Log but don't block - address is already created
            log_warning(f"Geocoding error for {address_type_str} address {address.address_id}: {e}. Address created without geolocation.")
    
    def _resolve_address_from_place_id(
        self,
        place_id: str,
        address_data: Dict[str, Any],
        current_user: Dict[str, Any],
    ) -> tuple:
        """
        Fetch Place Details for place_id, map to address, validate geography.
        Returns (address_data_with_mapped_fields, geoloc_dict_or_None).
        geoloc_dict has place_id, viewport, formatted_address_google, latitude, longitude.
        Raises HTTPException 400 if address is outside service area.
        """
        from app.gateways.google_places_gateway import get_google_places_gateway
        from app.services.address_autocomplete_mapping import (
            map_place_details_to_address,
            extract_place_details_geolocation,
            get_city_candidates_from_place_details,
        )
        from app.services.market_service import market_service
        from app.utils.country import normalize_country_code

        gateway = get_google_places_gateway()
        try:
            details = gateway.place_details(place_id)
        except Exception as e:
            log_warning(f"Place Details failed for place_id={place_id}: {e}")
            raise HTTPException(
                status_code=400,
                detail="Could not fetch address details for the selected place. Please try again or enter the address manually.",
            ) from e

        mapped = map_place_details_to_address(details)
        country_code = (mapped.get("country_code") or "").strip().upper()
        province = (mapped.get("province") or "").strip()

        if not country_code:
            raise HTTPException(
                status_code=400,
                detail="Address is outside our service area.",
            )
        market = market_service.get_by_country_code(country_code)
        if not market or market.get("country_code") == "GL":
            raise HTTPException(
                status_code=400,
                detail="Address is outside our service area.",
            )

        # Use first city candidate from Place Details. No city-in-supported-list restriction.
        city_candidates = get_city_candidates_from_place_details(details)
        city = city_candidates[0] if city_candidates else (mapped.get("city") or "—")
        mapped["city"] = city

        # Merge mapped address into address_data (preserve institution_id, user_id, etc.)
        for k, v in mapped.items():
            if k != "formatted_address":
                address_data[k] = v
        address_data["country_code"] = normalize_country_code(country_code) or country_code
        address_data.pop("place_id", None)

        geoloc = extract_place_details_geolocation(details)
        return address_data, geoloc if (geoloc.get("latitude") is not None and geoloc.get("longitude") is not None) else None

    def _create_geolocation_from_place_details(
        self,
        address: AddressDTO,
        geoloc: Dict[str, Any],
        current_user: Dict[str, Any],
        db: psycopg2.extensions.connection,
        commit: bool = True,
    ) -> None:
        """Create geolocation from Place Details (place_id, viewport, formatted_address_google, lat/lng)."""
        geodata = {
            "address_id": address.address_id,
            "latitude": geoloc["latitude"],
            "longitude": geoloc["longitude"],
            "place_id": geoloc.get("place_id"),
            "viewport": geoloc.get("viewport"),
            "formatted_address_google": geoloc.get("formatted_address_google"),
            "is_archived": False,
            "status": Status.ACTIVE,
            "modified_by": current_user["user_id"],
            "modified_date": datetime.now(timezone.utc),
        }
        geolocation_service.create(geodata, db, commit=commit)
        log_info(f"Geolocation created from Place Details (place_id={geoloc.get('place_id')}) for address ID {address.address_id}")

    def _build_full_address_string(self, address_data: Dict[str, Any], *, country_name: Optional[str] = None) -> str:
        """
        Build a full address string for geocoding.
        country_name is not stored on address; pass from market_info lookup or use country_code as fallback.
        """
        name = country_name or address_data.get("country_name") or address_data.get("country_code") or address_data.get("country", "")
        return f"{address_data['building_number']} {address_data['street_name']}, {address_data['city']}, {address_data['province']}, {name}"
    
    def validate_address_data(self, address_data: Dict[str, Any]) -> None:
        """
        Validate address data for business rules.
        
        Args:
            address_data: Address data dictionary
            
        Raises:
            HTTPException: For validation failures
        """
        # Check required fields for restaurant addresses
        address_types = address_data.get("address_type", [])
        if isinstance(address_types, list) and "Restaurant" in address_types:
            required_fields = ["building_number", "street_name", "city", "province", "country_code"]
            missing_fields = [field for field in required_fields if not address_data.get(field)]
            
            if missing_fields:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required fields for restaurant address: {', '.join(missing_fields)}"
                )
        
        # Validate country code format (alpha-2 after normalization)
        country_code = address_data.get("country_code", "").strip()
        country_raw = (address_data.get("country") or "").strip()
        if not country_code and country_raw and len(country_raw) == 3 and country_raw.isalpha():
            raise HTTPException(
                status_code=400,
                detail="Country must be a 2-letter country code (e.g. US) or full country name (e.g. United States).",
            )
        if country_code and len(country_code) != 2:
            raise HTTPException(
                status_code=400,
                detail="country_code must be valid ISO 3166-1 alpha-2 or alpha-3; API normalizes to alpha-2. Invalid or unsupported code."
            )

        # No city-in-supported-list check: any city within a supported country is accepted.
        # Structured create is DEV-only (guardrail above); place_id path gets city from Google.
    
    def get_address_with_geolocation(
        self, 
        address_id: UUID, 
        db: psycopg2.extensions.connection,
        scope: Optional[InstitutionScope] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get address with associated geolocation data.
        
        Args:
            address_id: Address ID
            db: Database connection
            
        Returns:
            Dictionary with address and geolocation data, or None if not found
        """
        # Get address
        address = address_service.get_by_id(address_id, db, scope=scope)
        if not address:
            return None
        
        # Get geolocation if exists
        geolocation = geolocation_service.get_by_address(address_id, db)
        
        result = {
            "address": address,
            "geolocation": geolocation
        }
        
        return result
    
    def update_address_with_geocoding(
        self, 
        address_id: UUID, 
        address_data: Dict[str, Any], 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection,
        scope: Optional[InstitutionScope] = None
    ) -> AddressDTO:
        """
        Update address subpremise only (floor, apartment_unit, is_default). Address core is immutable.
        """
        current_address = address_service.get_by_id(address_id, db, scope=scope)
        if not current_address:
            raise HTTPException(status_code=404, detail="Address not found")

        # Only floor, apartment_unit, is_default are updatable (go to address_subpremise)
        floor = address_data.get("floor")
        apartment_unit = address_data.get("apartment_unit")
        is_default = address_data.get("is_default")
        if "floor" not in address_data and "apartment_unit" not in address_data and "is_default" not in address_data:
            return current_address  # No-op

        user_id = UUID(str(current_user["user_id"])) if isinstance(current_user["user_id"], str) else current_user["user_id"]
        modified_by = UUID(str(current_user["user_id"])) if isinstance(current_user["user_id"], str) else current_user["user_id"]

        # Preserve existing subpremise values when field not in update
        existing_sp = db_read(
            "SELECT floor, apartment_unit, is_default FROM address_subpremise WHERE address_id = %s AND user_id = %s",
            (str(address_id), str(user_id)),
            connection=db,
            fetch_one=True,
        )
        floor_val = floor if "floor" in address_data else (existing_sp.get("floor") if existing_sp else None)
        unit_val = apartment_unit if "apartment_unit" in address_data else (existing_sp.get("apartment_unit") if existing_sp else None)
        default_val = is_default if "is_default" in address_data else (existing_sp.get("is_default", False) if existing_sp else False)

        _upsert_address_subpremise(
            address_id,
            user_id,
            modified_by,
            db,
            floor=floor_val,
            apartment_unit=unit_val,
            is_default=bool(default_val),
            commit=True,
        )

        # Re-fetch with subpremise data for current user
        return self._get_address_with_subpremise(address_id, user_id, db, scope=scope) or current_address

    def _get_address_with_subpremise(
        self,
        address_id: UUID,
        user_id: UUID,
        db: psycopg2.extensions.connection,
        scope: Optional[InstitutionScope] = None,
    ) -> Optional[AddressDTO]:
        """Fetch address with floor, apartment_unit, is_default from subpremise for given user."""
        addr = address_service.get_by_id(address_id, db, scope=scope)
        if not addr:
            return None
        row = db_read(
            """
            SELECT a.*, COALESCE(m.country_name, '') AS country_name,
                   sp.floor, sp.apartment_unit, sp.is_default
            FROM address_info a
            LEFT JOIN market_info m ON a.country_code = m.country_code
            LEFT JOIN address_subpremise sp ON sp.address_id = a.address_id AND sp.user_id = %s
            WHERE a.address_id = %s AND a.is_archived = FALSE
            """,
            (str(user_id), str(address_id)),
            connection=db,
            fetch_one=True,
        )
        if not row:
            return addr
        d = {**row, "floor": row.get("floor"), "apartment_unit": row.get("apartment_unit"), "is_default": row.get("is_default") or False}
        return AddressDTO(**d)
    
    def _update_geolocation_for_address(
        self, 
        address: AddressDTO, 
        address_data: Dict[str, Any], 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> None:
        """
        Update geolocation for an address.
        
        Args:
            address: Address DTO
            address_data: Address data for geocoding
            current_user: Current user information
            db: Database connection
        """
        # Get existing geolocation
        existing_geo = geolocation_service.get_by_address(address.address_id, db)
        
        # Build full address string for geocoding
        full_address = self._build_full_address_string(address_data)
        
        # Call geocoding API
        geocode_result = call_geocode_api(full_address)
        
        if geocode_result and "latitude" in geocode_result and "longitude" in geocode_result:
            geodata = {
                "latitude": geocode_result["latitude"],
                "longitude": geocode_result["longitude"],
                "modified_by": current_user["user_id"],
                "modified_date": datetime.now(timezone.utc)
            }
            
            if existing_geo:
                # Update existing geolocation
                geolocation_service.update(existing_geo.geolocation_id, geodata, db)
                log_info(f"Updated geolocation for address ID {address.address_id}")
            else:
                # Create new geolocation
                geodata.update({
                    "address_id": address.address_id,
                    "is_archived": False,
                    "status": Status.ACTIVE
                })
                geolocation_service.create(geodata, db)
                log_info(f"Created new geolocation for address ID {address.address_id}")
        else:
            log_warning(f"Geolocation failed for updated restaurant address: {full_address}")

    def geocode_address_if_required(
        self,
        address_id: UUID,
        current_user: Dict[str, Any],
        db: psycopg2.extensions.connection,
        *,
        commit: bool = True,
    ) -> None:
        """
        If the address's derived type is Restaurant, Customer Employer, or Customer Home,
        ensure it has geocoding. Used after linking (e.g. employer) when type becomes known.
        """
        address = address_service.get_by_id(address_id, db, scope=None)
        if not address:
            return
        types = getattr(address, "address_type", None) or []
        if not isinstance(types, list):
            types = [types] if types else []
        if not any(t in types for t in ("Restaurant", "Customer Employer", "Customer Home")):
            return
        addr_dict = {
            "building_number": address.building_number,
            "street_name": address.street_name,
            "city": address.city,
            "province": address.province,
            "country_code": address.country_code,
            "country_name": getattr(address, "country_name", None) or address.country_code,
        }
        self._geocode_address(
            address,
            addr_dict,
            current_user,
            db,
            commit=commit,
            country_name=getattr(address, "country_name", None),
        )


# Create service instance
address_business_service = AddressBusinessService()
