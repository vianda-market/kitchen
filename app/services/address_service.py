"""
Address Business Logic Service

This service contains all business logic related to address operations,
including geocoding integration, timezone calculation, and address validation.
"""

from datetime import datetime
from uuid import UUID
from typing import Dict, Any, Optional
from fastapi import HTTPException
import psycopg2.extensions

from app.dto.models import AddressDTO, GeolocationDTO
from app.services.crud_service import address_service, geolocation_service
from app.security.institution_scope import InstitutionScope
from app.utils.log import log_info, log_warning
from app.services.geolocation_service import call_geocode_api, get_timezone_from_location
from app.config import Status


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
        
        # Fetch country_name from market_info using country_code
        from app.services.market_service import market_service
        country_code = address_data.get("country_code")
        if country_code:
            market = market_service.get_by_country_code(country_code)
            if market:
                address_data["country_name"] = market["country_name"]
            else:
                raise HTTPException(status_code=400, detail=f"Invalid country_code: {country_code}. Market not found.")
        else:
            raise HTTPException(status_code=400, detail="country_code is required")
        
        # Automatically set timezone based on country_name and city
        timezone = get_timezone_from_location(address_data["country_name"], address_data["city"])
        address_data["timezone"] = timezone
        log_info(f"Set timezone '{timezone}' for address in {address_data['city']}, {address_data['country_name']}")

        # Create the address first (even for restaurants), so we get an address_id
        # NOTE: address_service.create() should ONLY be called from this business service.
        # All external callers should use address_business_service.create_address_with_geocoding() instead.
        new_addr = address_service.create(address_data, db, scope=scope, commit=commit)

        # Handle geocoding for restaurant, customer home, and customer employer addresses
        address_types = address_data.get("address_type", [])
        if isinstance(address_types, list):
            should_geocode = (
                "Restaurant" in address_types or
                "Customer Employer" in address_types or
                "Customer Home" in address_types
            )
            if should_geocode:
                self._geocode_address(new_addr, address_data, current_user, db, commit=commit)

        return new_addr
    
    def _geocode_address(
        self, 
        address: AddressDTO, 
        address_data: Dict[str, Any], 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection,
        commit: bool = True
    ) -> None:
        """
        Geocode an address and create geolocation record.
        
        Geocoding is performed for Restaurant, Customer Employer, and Customer Home addresses.
        Geocoding failures are logged but do not block address creation.
        This allows addresses to be created even when the geocoding API
        is unavailable (e.g., in development/testing environments).
        
        Args:
            address: Created address DTO
            address_data: Original address data
            current_user: Current user information
            db: Database connection
            commit: Whether to commit geolocation creation immediately (default: True).
                    Set to False for atomic multi-operation transactions.
        """
        # Build full address string for geocoding
        full_address = self._build_full_address_string(address_data)
        
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
                "modified_date": datetime.utcnow()
            }
            
            new_geo = geolocation_service.create(geodata, db, commit=commit)
            
            log_info(f"{address_type_str} address geocoded and saved (Geo ID: {new_geo.geolocation_id}) for address ID {address.address_id}")
        except Exception as e:
            # Log but don't block - address is already created
            log_warning(f"Geocoding error for {address_type_str} address {address.address_id}: {e}. Address created without geolocation.")
    
    def _build_full_address_string(self, address_data: Dict[str, Any]) -> str:
        """
        Build a full address string for geocoding.
        
        Args:
            address_data: Address data dictionary
            
        Returns:
            Formatted address string
        """
        return f"{address_data['building_number']} {address_data['street_name']}, {address_data['city']}, {address_data['province']}, {address_data['country_name']}"
    
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
        
        # Validate country code format (basic validation)
        country_code = address_data.get("country_code", "").strip()
        if len(country_code) != 3:
            raise HTTPException(
                status_code=400,
                detail="country_code must be a 3-letter ISO 3166-1 alpha-3 country code (e.g., 'ARG', 'PER', 'CHL')"
            )
    
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
        Update address and re-geocode if it's a restaurant address.
        
        Args:
            address_id: Address ID to update
            address_data: Updated address data
            current_user: Current user information
            db: Database connection
            
        Returns:
            Updated address DTO
            
        Raises:
            HTTPException: For validation or geocoding failures
        """
        # Set modified_by field
        address_data["modified_by"] = current_user["user_id"]
        
        # Fetch country_name from market_info if country_code is provided
        if "country_code" in address_data:
            from app.services.market_service import market_service
            country_code = address_data.get("country_code")
            if country_code:
                market = market_service.get_by_country_code(country_code)
                if market:
                    address_data["country_name"] = market["country_name"]
                else:
                    raise HTTPException(status_code=400, detail=f"Invalid country_code: {country_code}. Market not found.")
        
        # Update timezone if country_code/city changed
        if "country_code" in address_data or "city" in address_data:
            # Get current address to merge with updates
            current_address = address_service.get_by_id(address_id, db, scope=scope)
            if current_address:
                merged_data = {
                    "country_name": address_data.get("country_name", current_address.country_name),
                    "city": address_data.get("city", current_address.city)
                }
                timezone = get_timezone_from_location(merged_data["country_name"], merged_data["city"])
                address_data["timezone"] = timezone
                log_info(f"Updated timezone to '{timezone}' for address in {merged_data['city']}, {merged_data['country_name']}")
        
        # Update the address
        updated_address = address_service.update(address_id, address_data, db, scope=scope)
        if not updated_address:
            raise HTTPException(status_code=404, detail="Address not found")
        
        # Re-geocode if it's a restaurant address and location fields changed
        address_types = address_data.get("address_type", [])
        current_address_types = updated_address.address_type if hasattr(updated_address, 'address_type') else []
        is_restaurant = (isinstance(address_types, list) and "Restaurant" in address_types) or \
                       (isinstance(current_address_types, list) and "Restaurant" in current_address_types)
        if (is_restaurant or 
            any(field in address_data for field in ["building_number", "street_name", "city", "province", "country_code"])):
            
            # Get updated address data for geocoding
            full_address_data = {
                "building_number": address_data.get("building_number", updated_address.building_number),
                "street_name": address_data.get("street_name", updated_address.street_name),
                "city": address_data.get("city", updated_address.city),
                "province": address_data.get("province", updated_address.province),
                "country_name": address_data.get("country_name", updated_address.country_name)
            }
            
            # Update geolocation
            self._update_geolocation_for_address(updated_address, full_address_data, current_user, db)
        
        return updated_address
    
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
                "modified_date": datetime.utcnow()
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


# Create service instance
address_business_service = AddressBusinessService()
