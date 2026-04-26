"""
Address Business Logic Service

This service contains all business logic related to address operations,
including geocoding integration, timezone calculation, and address validation.

Address type for customer addresses (home/work/other) is user-selected.
Address type for restaurant, entity, and billing addresses is derived from linkages.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg2.extensions

from app.config import Status
from app.config.enums.address_types import AddressType
from app.dto.models import AddressDTO
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.security.institution_scope import InstitutionScope
from app.services.crud_service import address_service, geolocation_service
from app.services.geolocation_service import call_geocode_api
from app.utils.db import db_insert, db_read, db_update
from app.utils.log import log_info, log_warning


def derive_address_type_from_linkages(
    address_id: UUID,
    db: psycopg2.extensions.connection,
) -> list[str]:
    """
    Derive address_type from connected objects (restaurant, institution entity,
    payment method). Customer address types (home/work/other) are user-selected.
    """
    types: list[str] = []
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

    # Customer Billing (payment method)
    pm = db_read(
        "SELECT 1 FROM payment_method WHERE address_id = %s AND NOT is_archived",
        (aid,),
        connection=db,
        fetch_one=True,
    )
    if pm:
        types.append(AddressType.CUSTOMER_BILLING.value)

    # Customer Home or Customer Other: address belongs to Customer institution and is NOT linked to payment method
    if not pm:
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
            if it in ("customer",) or (hasattr(it, "value") and getattr(it, "value", None) == "customer"):
                # Check if user tagged this address as "other" via map_center_label
                sp_label = db_read(
                    "SELECT map_center_label FROM core.address_subpremise WHERE address_id = %s AND map_center_label = 'other' LIMIT 1",
                    (aid,),
                    connection=db,
                    fetch_one=True,
                )
                if sp_label:
                    types.append(AddressType.CUSTOMER_OTHER.value)
                else:
                    types.append(AddressType.CUSTOMER_HOME.value)

    return sorted(set(types))


def _upsert_address_subpremise(
    address_id: UUID,
    user_id: UUID,
    modified_by: UUID,
    db: psycopg2.extensions.connection,
    *,
    floor: str | None = None,
    apartment_unit: str | None = None,
    is_default: bool = False,
    map_center_label: str | None = None,
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
        update_data = {
            "floor": floor,
            "apartment_unit": apartment_unit,
            "is_default": is_default,
            "modified_by": mby,
            "modified_date": datetime.now(UTC),
        }
        if map_center_label is not None:
            update_data["map_center_label"] = map_center_label
        db_update(
            "address_subpremise",
            update_data,
            {"address_id": aid, "user_id": uid},
            connection=db,
            commit=commit,
        )
    else:
        insert_data = {
            "address_id": address_id,
            "user_id": user_id,
            "floor": floor,
            "apartment_unit": apartment_unit,
            "is_default": is_default,
            "created_by": modified_by,
            "modified_by": modified_by,
        }
        if map_center_label is not None:
            insert_data["map_center_label"] = map_center_label
        db_insert(
            "address_subpremise",
            insert_data,
            connection=db,
            commit=commit,
        )


def get_addresses_for_customer(
    user_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    include_archived: bool = False,
) -> list[AddressDTO]:
    """
    Get addresses visible to a Customer for GET /addresses and GET /addresses/enriched.

    - Addresses owned by user (user_id) or linked via subpremise
    - Address type (home/work/other) is user-selected, not auto-derived
    - Enriches with floor, apartment_unit, is_default from address_subpremise
    """
    uid = str(user_id)

    params: list[Any] = [uid, uid]
    archived = "" if include_archived else " AND a.is_archived = FALSE"
    q = f"""
        SELECT a.*, gc.name AS country_name,
               sp.floor, sp.apartment_unit, sp.is_default,
               g.latitude, g.longitude
        FROM address_info a
        LEFT JOIN market_info m ON a.country_code = m.country_code
        LEFT JOIN external.geonames_country gc ON gc.iso_alpha2 = m.country_code
        LEFT JOIN address_subpremise sp ON sp.address_id = a.address_id AND sp.user_id = %s
        LEFT JOIN geolocation_info g ON g.address_id = a.address_id AND g.is_archived = FALSE
        WHERE (a.user_id = %s OR sp.user_id IS NOT NULL){archived}
    """
    rows = db_read(q, tuple(params), connection=db)
    if not rows:
        return []

    result: list[AddressDTO] = []
    for r in rows:
        d = {
            **r,
            "floor": r.get("floor"),
            "apartment_unit": r.get("apartment_unit"),
            "is_default": r.get("is_default") or False,
        }
        result.append(AddressDTO(**d))

    return result


def update_address_type_from_linkages(
    address_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    commit: bool = True,
) -> list[str]:
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
        address_data: dict[str, Any],
        current_user: dict[str, Any],
        db: psycopg2.extensions.connection,
        scope: InstitutionScope | None = None,
        commit: bool = True,
        session_token: str | None = None,
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
        session_token_raw = session_token or (address_data.pop("session_token", None) or "").strip() or None
        if place_id_raw:
            address_data, geoloc_from_place = self._resolve_address_from_place_id(
                place_id_raw, address_data, current_user, session_token=session_token_raw
            )
        else:
            # Structured (manual) create is internal/testing only. Production must use place_id.
            from app.config.settings import get_settings

            if not getattr(get_settings(), "DEV_MODE", False):
                raise envelope_exception(ErrorCode.ADDRESS_MANUAL_ENTRY_NOT_ALLOWED, status=403, locale="en")
            geoloc_from_place = None

        # floor, apartment_unit, is_default go to address_subpremise (not address_info); extract before create
        subpremise_floor = address_data.pop("floor", None)
        subpremise_unit = address_data.pop("apartment_unit", None)
        subpremise_is_default = address_data.pop("is_default", False)

        country_code, country_name_for_log = self._resolve_country(address_data)

        # Validate address data (required fields, country-province-city combination)
        self.validate_address_data(address_data)

        self._resolve_city_metadata_and_timezone(address_data, country_code, country_name_for_log, db)

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
            new_addr = (
                self._get_address_with_subpremise(new_addr.address_id, user_id, db, scope=scope)
                or address_service.get_by_id(new_addr.address_id, db, scope=scope)
                or new_addr
            )
        else:
            new_addr = address_service.get_by_id(new_addr.address_id, db, scope=scope) or new_addr

        # Handle geocoding: place_id path stores geolocation immediately; otherwise geocode from derived types
        self._handle_geocoding(
            new_addr,
            address_data,
            geoloc_from_place,
            derived_types,
            current_user,
            db,
            commit=commit,
            country_name=country_name_for_log,
        )

        return new_addr

    @staticmethod
    def _resolve_country(address_data: dict[str, Any]) -> tuple[str, str]:
        """Resolve country_code to alpha-2 and validate market. Returns (country_code, country_name)."""
        from app.services.market_service import market_service
        from app.utils.country import country_name_to_alpha2, normalize_country_code

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
        if not country_code:
            raise envelope_exception(ErrorCode.VALIDATION_ADDRESS_COUNTRY_REQUIRED, status=400, locale="en")
        address_data["country_code"] = country_code
        address_data.pop("country_name", None)
        market = market_service.get_by_country_code(country_code)
        if not market:
            raise envelope_exception(ErrorCode.ADDRESS_INVALID_COUNTRY, status=400, locale="en")
        if market.get("country_code") == "XG":
            raise envelope_exception(ErrorCode.ADDRESS_GLOBAL_MARKET_INVALID, status=400, locale="en")
        return country_code, market["country_name"]

    @staticmethod
    def _resolve_city_metadata_id(
        address_data: dict[str, Any],
        country_code: str,
        db: psycopg2.extensions.connection,
    ) -> Any:
        """Resolve city_metadata_id from address data, city name, or country fallback."""
        city_metadata_id = address_data.get("city_metadata_id")
        if city_metadata_id:
            return city_metadata_id
        city_name_from_place = (address_data.get("city") or "").strip()
        if city_name_from_place:
            resolve_row = db_read(
                """
                SELECT cm.city_metadata_id
                FROM core.city_metadata cm
                JOIN external.geonames_city gc ON gc.geonames_id = cm.geonames_id
                WHERE cm.country_iso = %s
                  AND cm.is_archived = FALSE
                  AND LOWER(gc.ascii_name) = LOWER(%s)
                ORDER BY gc.population DESC NULLS LAST
                LIMIT 1
                """,
                (country_code, city_name_from_place),
                connection=db,
                fetch_one=True,
            )
            if resolve_row and resolve_row.get("city_metadata_id"):
                return resolve_row["city_metadata_id"]
        # Fallback: pick any active seeded city_metadata for this country
        fallback_row = db_read(
            """
            SELECT cm.city_metadata_id
            FROM core.city_metadata cm
            WHERE cm.country_iso = %s AND cm.is_archived = FALSE
            LIMIT 1
            """,
            (country_code,),
            connection=db,
            fetch_one=True,
        )
        if fallback_row and fallback_row.get("city_metadata_id"):
            return fallback_row["city_metadata_id"]
        raise envelope_exception(ErrorCode.ADDRESS_CITY_METADATA_UNRESOLVABLE, status=400, locale="en")

    def _resolve_city_metadata_and_timezone(
        self,
        address_data: dict[str, Any],
        country_code: str,
        country_name_for_log: str,
        db: psycopg2.extensions.connection,
    ) -> None:
        """Resolve city_metadata_id and set timezone on address_data."""
        city_metadata_id = self._resolve_city_metadata_id(address_data, country_code, db)
        if not address_data.get("city_metadata_id"):
            address_data["city_metadata_id"] = city_metadata_id
            city_name = (address_data.get("city") or "").strip()
            log_info(
                f"Resolved city_metadata_id {city_metadata_id} from place_id → ({country_code}, {city_name or '<fallback>'})"
            )
        row = db_read(
            """
            SELECT gc.timezone AS tz, cm.country_iso
            FROM core.city_metadata cm
            JOIN external.geonames_city gc ON gc.geonames_id = cm.geonames_id
            WHERE cm.city_metadata_id = %s::uuid
              AND cm.is_archived = FALSE
            """,
            (str(city_metadata_id),),
            connection=db,
            fetch_one=True,
        )
        if not row:
            raise envelope_exception(ErrorCode.VALIDATION_ADDRESS_CITY_METADATA_ID_REQUIRED, status=400, locale="en")
        resolved_iso = (row.get("country_iso") or "").upper()
        if resolved_iso and resolved_iso != country_code:
            raise envelope_exception(ErrorCode.ADDRESS_CITY_COUNTRY_MISMATCH, status=400, locale="en")
        tz = row.get("tz") or "UTC"
        address_data["timezone"] = tz
        log_info(f"Set timezone '{tz}' from city_metadata_id for address in {country_name_for_log} ({country_code})")

    def _handle_geocoding(
        self,
        address: AddressDTO,
        address_data: dict[str, Any],
        geoloc_from_place: dict | None,
        derived_types: list | Any,
        current_user: dict[str, Any],
        db: psycopg2.extensions.connection,
        commit: bool = True,
        *,
        country_name: str | None = None,
    ) -> None:
        """Handle geocoding: place_id path stores immediately; otherwise geocode from derived types."""
        if geoloc_from_place:
            self._create_geolocation_from_place_details(address, geoloc_from_place, current_user, db, commit=commit)
            return
        if not isinstance(derived_types, list):
            return
        geocodable_types = {"restaurant", "customer_employer", "customer_home"}
        if geocodable_types & set(derived_types):
            self._geocode_address(address, address_data, current_user, db, commit=commit, country_name=country_name)

    def _geocode_address(
        self,
        address: AddressDTO,
        address_data: dict[str, Any],
        current_user: dict[str, Any],
        db: psycopg2.extensions.connection,
        commit: bool = True,
        *,
        country_name: str | None = None,
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
                log_warning(
                    f"Geolocation failed for {address_type_str} address: {full_address}. Address created without geolocation."
                )
                return  # Non-blocking: address is already created, just skip geocoding

            # Create geolocation record
            geodata = {
                "address_id": address.address_id,
                "latitude": geocode_result["latitude"],
                "longitude": geocode_result["longitude"],
                "is_archived": False,
                "status": Status.ACTIVE,
                "modified_by": current_user["user_id"],
                "modified_date": datetime.now(UTC),
            }

            new_geo = geolocation_service.create(geodata, db, commit=commit)

            log_info(
                f"{address_type_str} address geocoded and saved (Geo ID: {new_geo.geolocation_id}) for address ID {address.address_id}"
            )
        except Exception as e:
            # Log but don't block - address is already created
            log_warning(
                f"Geocoding error for {address_type_str} address {address.address_id}: {e}. Address created without geolocation."
            )

    def _resolve_address_from_place_id(
        self,
        place_id: str,
        address_data: dict[str, Any],
        current_user: dict[str, Any],
        session_token: str | None = None,
    ) -> tuple:
        """
        Fetch address details for place_id/mapbox_id, map to address, validate geography.
        Returns (address_data_with_mapped_fields, geoloc_dict_or_None).
        geoloc_dict has place_id, viewport, formatted_address_google, latitude, longitude.
        Raises HTTPException 400 if address is outside service area.
        """
        from app.gateways.address_provider import get_search_gateway
        from app.services.address_autocomplete_mapping import (
            extract_place_details_geolocation,
            get_city_candidates_from_place_details,
            map_place_details_to_address,
        )
        from app.services.market_service import market_service
        from app.utils.country import normalize_country_code

        gateway = get_search_gateway()
        try:
            # Mapbox: retrieve by mapbox_id; Google: place_details by place_id
            if hasattr(gateway, "retrieve"):
                details = gateway.retrieve(place_id, session_token=session_token)
            else:
                details = gateway.place_details(place_id)
        except Exception as e:
            log_warning(f"Address details fetch failed for id={place_id}: {e}")
            raise envelope_exception(ErrorCode.ADDRESS_PLACE_DETAILS_FAILED, status=400, locale="en") from e

        mapped = map_place_details_to_address(details)
        country_code = (mapped.get("country_code") or "").strip().upper()
        (mapped.get("province") or "").strip()

        if not country_code:
            raise envelope_exception(ErrorCode.ADDRESS_OUTSIDE_SERVICE_AREA, status=400, locale="en")
        market = market_service.get_by_country_code(country_code)
        if not market or market.get("country_code") == "XG":
            raise envelope_exception(ErrorCode.ADDRESS_OUTSIDE_SERVICE_AREA, status=400, locale="en")

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
        return address_data, geoloc if (
            geoloc.get("latitude") is not None and geoloc.get("longitude") is not None
        ) else None

    def _create_geolocation_from_place_details(
        self,
        address: AddressDTO,
        geoloc: dict[str, Any],
        current_user: dict[str, Any],
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
            "modified_date": datetime.now(UTC),
        }
        geolocation_service.create(geodata, db, commit=commit)
        log_info(
            f"Geolocation created from Place Details (place_id={geoloc.get('place_id')}) for address ID {address.address_id}"
        )

    def _build_full_address_string(self, address_data: dict[str, Any], *, country_name: str | None = None) -> str:
        """
        Build a full address string for geocoding.
        country_name is not stored on address; pass from market_info lookup or use country_code as fallback.
        """
        name = (
            country_name
            or address_data.get("country_name")
            or address_data.get("country_code")
            or address_data.get("country", "")
        )
        return f"{address_data['building_number']} {address_data['street_name']}, {address_data['city']}, {address_data['province']}, {name}"

    def validate_address_data(self, address_data: dict[str, Any]) -> None:
        """
        Validate address data for business rules.

        Args:
            address_data: Address data dictionary

        Raises:
            HTTPException: For validation failures
        """
        # Check required fields for restaurant addresses
        address_types = address_data.get("address_type", [])
        if isinstance(address_types, list) and "restaurant" in address_types:
            required_fields = ["building_number", "street_name", "city", "province", "country_code"]
            missing_fields = [field for field in required_fields if not address_data.get(field)]

            if missing_fields:
                raise envelope_exception(
                    ErrorCode.VALIDATION_ADDRESS_FIELD_REQUIRED, status=400, locale="en",
                    field=", ".join(missing_fields)
                )

        # Validate country code format (alpha-2 after normalization)
        country_code = address_data.get("country_code", "").strip()
        country_raw = (address_data.get("country") or "").strip()
        if not country_code and country_raw and len(country_raw) == 3 and country_raw.isalpha():
            raise envelope_exception(ErrorCode.VALIDATION_ADDRESS_COUNTRY_REQUIRED, status=400, locale="en")
        if country_code and len(country_code) != 2:
            raise envelope_exception(ErrorCode.ADDRESS_INVALID_COUNTRY, status=400, locale="en")

        # No city-in-supported-list check: any city within a supported country is accepted.
        # Structured create is DEV-only (guardrail above); place_id path gets city from Google.

    def get_address_with_geolocation(
        self, address_id: UUID, db: psycopg2.extensions.connection, scope: InstitutionScope | None = None
    ) -> dict[str, Any] | None:
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

        result = {"address": address, "geolocation": geolocation}

        return result

    def update_address_with_geocoding(
        self,
        address_id: UUID,
        address_data: dict[str, Any],
        current_user: dict[str, Any],
        db: psycopg2.extensions.connection,
        scope: InstitutionScope | None = None,
    ) -> AddressDTO:
        """
        Update address subpremise only (floor, apartment_unit, is_default). Address core is immutable.
        """
        current_address = address_service.get_by_id(address_id, db, scope=scope)
        if not current_address:
            raise envelope_exception(ErrorCode.ADDRESS_NOT_FOUND, status=404, locale="en")

        # Only floor, apartment_unit, is_default are updatable (go to address_subpremise)
        floor = address_data.get("floor")
        apartment_unit = address_data.get("apartment_unit")
        is_default = address_data.get("is_default")
        if "floor" not in address_data and "apartment_unit" not in address_data and "is_default" not in address_data:
            return current_address  # No-op

        user_id = (
            UUID(str(current_user["user_id"])) if isinstance(current_user["user_id"], str) else current_user["user_id"]
        )
        modified_by = (
            UUID(str(current_user["user_id"])) if isinstance(current_user["user_id"], str) else current_user["user_id"]
        )

        # Preserve existing subpremise values when field not in update
        existing_sp = db_read(
            "SELECT floor, apartment_unit, is_default FROM address_subpremise WHERE address_id = %s AND user_id = %s",
            (str(address_id), str(user_id)),
            connection=db,
            fetch_one=True,
        )
        floor_val = floor if "floor" in address_data else (existing_sp.get("floor") if existing_sp else None)
        unit_val = (
            apartment_unit
            if "apartment_unit" in address_data
            else (existing_sp.get("apartment_unit") if existing_sp else None)
        )
        default_val = (
            is_default
            if "is_default" in address_data
            else (existing_sp.get("is_default", False) if existing_sp else False)
        )

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
        scope: InstitutionScope | None = None,
    ) -> AddressDTO | None:
        """Fetch address with floor, apartment_unit, is_default from subpremise for given user."""
        addr = address_service.get_by_id(address_id, db, scope=scope)
        if not addr:
            return None
        row = db_read(
            """
            SELECT a.*, gc.name AS country_name,
                   sp.floor, sp.apartment_unit, sp.is_default,
                   g.latitude, g.longitude
            FROM address_info a
            LEFT JOIN market_info m ON a.country_code = m.country_code
            LEFT JOIN external.geonames_country gc ON gc.iso_alpha2 = m.country_code
            LEFT JOIN address_subpremise sp ON sp.address_id = a.address_id AND sp.user_id = %s
            LEFT JOIN geolocation_info g ON g.address_id = a.address_id AND g.is_archived = FALSE
            WHERE a.address_id = %s AND a.is_archived = FALSE
            """,
            (str(user_id), str(address_id)),
            connection=db,
            fetch_one=True,
        )
        if not row:
            return addr
        d = {
            **row,
            "floor": row.get("floor"),
            "apartment_unit": row.get("apartment_unit"),
            "is_default": row.get("is_default") or False,
        }
        return AddressDTO(**d)

    def _update_geolocation_for_address(
        self,
        address: AddressDTO,
        address_data: dict[str, Any],
        current_user: dict[str, Any],
        db: psycopg2.extensions.connection,
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
                "modified_date": datetime.now(UTC),
            }

            if existing_geo:
                # Update existing geolocation
                geolocation_service.update(existing_geo.geolocation_id, geodata, db)
                log_info(f"Updated geolocation for address ID {address.address_id}")
            else:
                # Create new geolocation
                geodata.update({"address_id": address.address_id, "is_archived": False, "status": Status.ACTIVE})
                geolocation_service.create(geodata, db)
                log_info(f"Created new geolocation for address ID {address.address_id}")
        else:
            log_warning(f"Geolocation failed for updated restaurant address: {full_address}")

    def geocode_address_if_required(
        self,
        address_id: UUID,
        current_user: dict[str, Any],
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
        if not any(t in types for t in ("restaurant", "customer_employer", "customer_home")):
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
