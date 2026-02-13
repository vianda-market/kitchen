"""
Address autocomplete and validation service.

Uses Google Places API (New) for suggest and Address Validation API for validate.
All clients (web, iOS, Android, React Native) call the same backend endpoints.
"""

from typing import Any, Dict, List, Optional

from app.gateways.google_places_gateway import (
    get_google_places_gateway,
    country_alpha3_to_alpha2,
)
from app.services.address_autocomplete_mapping import (
    map_place_details_to_address,
    map_validation_result_to_address,
    build_validation_api_request,
)
from app.utils.log import log_info, log_error


class AddressAutocompleteService:
    """Service for address suggest (autocomplete) and validate (normalize)."""

    def __init__(self):
        self.gateway = get_google_places_gateway()

    def suggest(
        self,
        q: str,
        country: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Return address suggestions for partial input.
        country: optional ISO alpha-2 or alpha-3 to bias/restrict results.
        limit: max number of suggestions (default 5).
        Returns list of suggestion dicts with keys matching AddressSuggestionSchema.
        """
        if not (q and q.strip()):
            return []

        input_text = q.strip()
        included_region_codes: Optional[List[str]] = None
        if country:
            country = country.strip().upper()
            if len(country) == 3:
                included_region_codes = [country_alpha3_to_alpha2(country)]
            else:
                included_region_codes = [country[:2]]

        try:
            raw = self.gateway.places_autocomplete(
                input_text=input_text,
                included_region_codes=included_region_codes,
            )
        except Exception as e:
            log_error(f"Address suggest autocomplete failed: {e}")
            return []

        suggestions_list = raw.get("suggestions") or []
        out: List[Dict[str, Any]] = []
        for i, item in enumerate(suggestions_list):
            if i >= limit:
                break
            place_pred = item.get("placePrediction") or item.get("place_prediction")
            if not place_pred:
                continue
            place_id = place_pred.get("placeId") or place_pred.get("place_id")
            if not place_id:
                continue
            try:
                details = self.gateway.place_details(place_id)
            except Exception as e:
                log_error(f"Place details failed for {place_id}: {e}")
                continue
            mapped = map_place_details_to_address(details)
            # Add country_name if we want to resolve from market (optional later)
            mapped["country_name"] = None
            out.append(mapped)
        log_info(f"Address suggest returned {len(out)} suggestions for q={input_text!r}")
        return out

    def validate(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize address. body must contain address fields
        (street_name, street_type, building_number, city, province, postal_code, country_code, etc.).
        Returns dict with is_valid, normalized, formatted_address, confidence, message.
        """
        try:
            payload = build_validation_api_request(
                street_name=body.get("street_name", ""),
                street_type=body.get("street_type", ""),
                building_number=body.get("building_number", ""),
                city=body.get("city", ""),
                province=body.get("province", ""),
                postal_code=body.get("postal_code", ""),
                country_code=body.get("country_code", ""),
                apartment_unit=body.get("apartment_unit"),
                floor=body.get("floor"),
            )
        except Exception as e:
            log_error(f"Address validate request build failed: {e}")
            return {
                "is_valid": False,
                "normalized": None,
                "formatted_address": None,
                "confidence": "none",
                "message": "Invalid address request.",
            }

        try:
            raw = self.gateway.validate_address(payload)
        except Exception as e:
            log_error(f"Address validation API failed: {e}")
            return {
                "is_valid": False,
                "normalized": None,
                "formatted_address": None,
                "confidence": "none",
                "message": "Address could not be validated. Please check and try again.",
            }

        is_valid, normalized, formatted_address, confidence, message = map_validation_result_to_address(raw)
        return {
            "is_valid": is_valid,
            "normalized": normalized,
            "formatted_address": formatted_address or None,
            "confidence": confidence,
            "message": message,
        }


# Singleton for use in routes
address_autocomplete_service = AddressAutocompleteService()
