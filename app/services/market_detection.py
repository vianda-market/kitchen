# app/services/market_detection.py
"""
Market Detection Service

This service detects the market/country code (ISO format) from entity addresses
to enable market-specific business logic, particularly for billing and timing configurations.

Key Features:
- Extracts country codes directly from institution entities, restaurants, and institutions
- Uses ISO 3166-1 alpha-2 country codes stored in address records (e.g., "AR", "PE", "CL")
- Limited to Americas countries only (from Canada to Argentina)
- Used primarily by the billing service to determine market-specific kitchen day timing

Supported Countries:
- North America: Canada, United States, Mexico
- Central America: Guatemala, Belize, El Salvador, Honduras, Nicaragua, Costa Rica, Panama
- Caribbean: Cuba, Jamaica, Haiti, Dominican Republic, Puerto Rico, Trinidad and Tobago, Barbados, Bahamas
- South America: Colombia, Venezuela, Guyana, Suriname, French Guiana, Brazil, Ecuador, Peru,
  Bolivia, Paraguay, Uruguay, Argentina, Chile

Usage:
- get_country_from_entity(entity_id, db) - Get country from institution entity address
- get_country_from_restaurant(restaurant_id, db) - Get country from restaurant address
- get_country_from_institution(institution_id, db) - Get country from institution's primary entity
- get_country_from_restaurant_balance(restaurant_id, db) - Get country for billing purposes
"""

from uuid import UUID

import psycopg2
import psycopg2.extensions

from app.services.crud_service import (
    address_service,
    get_institution_entities_by_institution,
    institution_entity_service,
    restaurant_service,
)
from app.utils.log import log_error, log_info, log_warning


class MarketDetectionService:
    """Service for detecting market/country from entity addresses (Americas only)"""

    @staticmethod
    def get_country_from_entity(entity_id: UUID, db: psycopg2.extensions.connection) -> str | None:
        """
        Get the country code for an institution entity based on its address.

        Args:
            entity_id: Institution entity ID

        Returns:
            Country code (AR, PE, etc.) or None if not found
        """
        try:
            # Get the entity record
            entity_obj = institution_entity_service.get_by_id(entity_id, db)
            if not entity_obj:
                log_warning(f"Institution entity {entity_id} not found")
                return None

            entity = entity_obj

            # Get the address for this entity
            address_obj = address_service.get_by_id(entity.address_id, db)
            if not address_obj:
                log_warning(f"Address {entity.address_id} not found for entity {entity_id}")
                return None

            address = address_obj

            # Extract country code directly from address
            country_code = address.country_code
            if not country_code:
                log_warning(f"No country_code found in address {entity.address_id}")
                return None

            log_info(f"Detected country {country_code} for entity {entity_id}")
            return country_code

        except Exception as e:
            log_error(f"Error detecting country for entity {entity_id}: {e}")
            return None

    @staticmethod
    def get_country_from_restaurant(restaurant_id: UUID, db: psycopg2.extensions.connection) -> str | None:
        """
        Get the country code for a restaurant based on its address.

        Args:
            restaurant_id: Restaurant ID

        Returns:
            Country code (AR, PE, etc.) or None if not found
        """
        try:
            # Get the restaurant record
            restaurant_obj = restaurant_service.get_by_id(restaurant_id, db)
            if not restaurant_obj:
                log_warning(f"Restaurant {restaurant_id} not found")
                return None

            restaurant = restaurant_obj

            # Get the address for this restaurant
            address_obj = address_service.get_by_id(restaurant.address_id, db)
            if not address_obj:
                log_warning(f"Address {restaurant.address_id} not found for restaurant {restaurant_id}")
                return None

            address = address_obj

            # Extract country code directly from address
            country_code = address.country_code
            if not country_code:
                log_warning(f"No country_code found in address {restaurant.address_id}")
                return None

            log_info(f"Detected country {country_code} for restaurant {restaurant_id}")
            return country_code

        except Exception as e:
            log_error(f"Error detecting country for restaurant {restaurant_id}: {e}")
            return None

    @staticmethod
    def get_country_from_institution(institution_id: UUID, db: psycopg2.extensions.connection) -> str | None:
        """
        Get the country code for an institution based on its primary entity address.

        Args:
            institution_id: Institution ID

        Returns:
            Country code (AR, PE, etc.) or None if not found
        """
        try:
            # Get all entities for this institution
            entities = get_institution_entities_by_institution(institution_id, db)
            if not entities:
                log_warning(f"No entities found for institution {institution_id}")
                return None

            # Use the first entity (primary)
            primary_entity = entities[0]

            # Get country from entity address
            return MarketDetectionService.get_country_from_entity(primary_entity.institution_entity_id, db)

        except Exception as e:
            log_error(f"Error detecting country for institution {institution_id}: {e}")
            return None

    @staticmethod
    def get_country_from_restaurant_balance(restaurant_id: UUID, db: psycopg2.extensions.connection) -> str | None:
        """
        Get the country code for a restaurant based on its balance record.
        This is used in the billing service to determine market-specific timing.

        Args:
            restaurant_id: Restaurant ID

        Returns:
            Country code (AR, PE, etc.) or None if not found
        """
        try:
            # Get the restaurant record
            restaurant_obj = restaurant_service.get_by_id(restaurant_id, db)
            if not restaurant_obj:
                log_warning(f"Restaurant {restaurant_id} not found")
                return None

            # Get country from restaurant address
            return MarketDetectionService.get_country_from_restaurant(restaurant_id, db)

        except Exception as e:
            log_error(f"Error detecting country for restaurant balance {restaurant_id}: {e}")
            return None

    @staticmethod
    def _country_name_to_code(country_name: str) -> str | None:
        """
        Convert country name to ISO country code.

        This service is limited to Americas countries only (from Canada to Argentina).
        Used primarily for market-specific billing and timing configurations.

        Args:
            country_name: Full country name

        Returns:
            ISO country code (AR, PE, etc.) or None if not found
        """
        # Map Americas country names to ISO codes (from Canada to Argentina)
        # Includes: North America, Central America, Caribbean, and South America
        country_mapping = {
            # North America
            "canada": "CA",
            "united states": "US",
            "usa": "US",
            "united states of america": "US",
            "mexico": "MX",
            # Central America
            "guatemala": "GT",
            "belize": "BZ",
            "el salvador": "SV",
            "honduras": "HN",
            "nicaragua": "NI",
            "costa rica": "CR",
            "panama": "PA",
            # Caribbean (major countries)
            "cuba": "CU",
            "jamaica": "JM",
            "haiti": "HT",
            "dominican republic": "DO",
            "puerto rico": "PR",
            "trinidad and tobago": "TT",
            "barbados": "BB",
            "bahamas": "BS",
            # South America
            "colombia": "CO",
            "venezuela": "VE",
            "guyana": "GY",
            "suriname": "SR",
            "french guiana": "GF",
            "brazil": "BR",
            "ecuador": "EC",
            "peru": "PE",
            "bolivia": "BO",
            "paraguay": "PY",
            "uruguay": "UY",
            "argentina": "AR",
            "chile": "CL",
        }

        # Normalize country name and look up code
        normalized_name = country_name.lower().strip()
        return country_mapping.get(normalized_name)
