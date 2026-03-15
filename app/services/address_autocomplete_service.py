"""
Address autocomplete service.

Uses Google Places API (New) for suggest. All address creation flows through
autocomplete → place_id → create. All clients (web, iOS, Android, React Native)
call the same backend endpoints.
"""

from typing import Any, Dict, List, Optional

from app.gateways.google_places_gateway import (
    get_google_places_gateway,
    country_name_to_alpha2,
    country_alpha3_to_alpha2,
)
from app.services.address_autocomplete_mapping import map_place_details_to_address
from app.utils.log import log_info, log_error


class AddressAutocompleteService:
    """Service for address suggest (autocomplete) from partial input."""

    def __init__(self):
        self.gateway = get_google_places_gateway()

    def suggest(
        self,
        q: str,
        country: Optional[str] = None,
        province: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Return address suggestions for partial input.
        country: optional ISO 3166-1 alpha-2 (e.g. AR) or country name (e.g. Argentina) to bias/restrict results.
        province: optional province/state (e.g. WA, Washington) to bias results when used with country and city.
        city: optional city name to bias results when used with country and province.
        limit: max number of suggestions (default 5).
        Returns list of suggestion dicts with keys matching AddressSuggestionSchema.
        """
        if not (q and q.strip()):
            return []

        input_text = q.strip()
        if country and province and city:
            loc_prefix = f"{city.strip()}, {province.strip()} - "
            input_text = loc_prefix + input_text

        included_region_codes: Optional[List[str]] = None
        if country:
            raw = country.strip()
            if len(raw) == 2 and raw.isalpha():
                # Alpha-2 code only
                included_region_codes = [raw.upper()]
            elif len(raw) == 3 and raw.isalpha():
                # Alpha-3 code; resolve to alpha-2 for Google
                alpha2 = country_alpha3_to_alpha2(raw)
                if alpha2:
                    included_region_codes = [alpha2]
            else:
                # Treat as country name; resolve to alpha-2
                alpha2 = country_name_to_alpha2(raw)
                if alpha2:
                    included_region_codes = [alpha2]
                # If unresolved, we do not send region filter (broader results)
        else:
            # Phase 3: Limit suggestions to supported countries when no country specified
            from app.config.supported_countries import SUPPORTED_COUNTRY_CODES
            included_region_codes = list(SUPPORTED_COUNTRY_CODES) if SUPPORTED_COUNTRY_CODES else None

        # No city bounds restriction: suggestions return addresses anywhere in the country.
        # Country/province/city params bias relevance only (loc_prefix above).
        try:
            raw = self.gateway.places_autocomplete(
                input_text=input_text,
                included_region_codes=included_region_codes,
                location_restriction=None,
            )
        except Exception as e:
            log_error(f"Address suggest autocomplete failed: {e}")
            return []

        suggestions_list = raw.get("suggestions") or []
        out: List[Dict[str, Any]] = []
        # When a single country filter was applied, include country_code so clients can rely on it
        country_code: Optional[str] = None
        if included_region_codes and len(included_region_codes) == 1:
            cc = (included_region_codes[0] or "").strip().upper()
            if len(cc) == 2 and cc.isalpha():
                country_code = cc
        for i, item in enumerate(suggestions_list):
            if i >= limit:
                break
            place_pred = item.get("placePrediction") or item.get("place_prediction")
            if not place_pred:
                continue
            place_id = place_pred.get("placeId") or place_pred.get("place_id")
            if not place_id:
                continue
            text_obj = place_pred.get("text") or {}
            display_text = text_obj.get("text", "") if isinstance(text_obj, dict) else str(text_obj)
            if not display_text:
                display_text = place_pred.get("structuredFormat", {}).get("mainText", {}).get("text", "")
            sug: Dict[str, Any] = {"place_id": place_id, "display_text": display_text}
            if country_code:
                sug["country_code"] = country_code
            out.append(sug)
        log_info(f"Address suggest returned {len(out)} suggestions for q={input_text!r}")
        return out


# Singleton for use in routes
address_autocomplete_service = AddressAutocompleteService()
