"""
Address autocomplete service.

Uses the configured address provider (Mapbox or Google) for suggest.
All address creation flows through autocomplete -> place_id/mapbox_id -> create.
All clients (web, iOS, Android, React Native) call the same backend endpoints.
"""

import uuid
from typing import Any

from app.gateways.address_provider import get_search_gateway
from app.utils.country import country_alpha3_to_alpha2, country_name_to_alpha2
from app.utils.log import log_error, log_info


class AddressAutocompleteService:
    """Service for address suggest (autocomplete) from partial input."""

    def __init__(self):
        self.gateway = get_search_gateway()

    def suggest(
        self,
        q: str,
        country: str | None = None,
        province: str | None = None,
        city: str | None = None,
        limit: int = 5,
        session_token: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return address suggestions for partial input.
        country: optional ISO 3166-1 alpha-2 (e.g. AR) or country name (e.g. Argentina) to bias/restrict results.
        province: optional province/state (e.g. WA, Washington) to bias results when used with country and city.
        city: optional city name to bias results when used with country and province.
        limit: max number of suggestions (default 5).
        session_token: optional UUIDv4 for Mapbox session billing. Auto-generated if omitted.
        Returns list of suggestion dicts with keys matching AddressSuggestionSchema.
        """
        if not (q and q.strip()):
            return []

        input_text = q.strip()
        if country and province and city:
            loc_prefix = f"{city.strip()}, {province.strip()} - "
            input_text = loc_prefix + input_text

        # Resolve country to alpha-2
        alpha2: str | None = None
        if country:
            raw = country.strip()
            if len(raw) == 2 and raw.isalpha():
                alpha2 = raw.upper()
            elif len(raw) == 3 and raw.isalpha():
                alpha2 = country_alpha3_to_alpha2(raw) or None
            else:
                alpha2 = country_name_to_alpha2(raw)

        # Generate session token if not provided (Mapbox billing optimization)
        if not session_token:
            session_token = str(uuid.uuid4())

        try:
            raw_response = self.gateway.suggest(
                query=input_text,
                country=alpha2,
                session_token=session_token,
                limit=limit,
            )
        except Exception as e:
            log_error(f"Address suggest autocomplete failed: {e}")
            return []

        # Determine country_code for output (when single-country filter applied)
        country_code: str | None = None
        if alpha2 and len(alpha2) == 2 and alpha2.isalpha():
            country_code = alpha2.upper()
        elif not alpha2:
            # Load supported countries as fallback filter info
            from app.config.supported_countries import SUPPORTED_COUNTRY_CODES

            if SUPPORTED_COUNTRY_CODES and len(SUPPORTED_COUNTRY_CODES) == 1:
                cc = list(SUPPORTED_COUNTRY_CODES)[0]
                if len(cc) == 2 and cc.isalpha():
                    country_code = cc.upper()

        # Parse response — handle both Mapbox and Google formats
        out: list[dict[str, Any]] = []
        suggestions_list = raw_response.get("suggestions") or []
        for i, item in enumerate(suggestions_list):
            if i >= limit:
                break
            sug = self._parse_suggestion(item, country_code)
            if sug:
                out.append(sug)

        log_info(f"Address suggest returned {len(out)} suggestions for q={input_text!r}")
        return out

    def _parse_suggestion(self, item: dict[str, Any], country_code: str | None) -> dict[str, Any] | None:
        """Parse a single suggestion from either Mapbox or Google format."""
        # Mapbox format: { mapbox_id, name, full_address, context }
        if "mapbox_id" in item:
            mapbox_id = item.get("mapbox_id", "")
            if not mapbox_id:
                return None
            display_text = item.get("full_address") or item.get("name") or ""
            sug: dict[str, Any] = {"place_id": mapbox_id, "display_text": display_text}
            # Extract country_code from context if available
            ctx_cc = (item.get("context", {}).get("country", {}).get("country_code") or "").upper()
            if ctx_cc and len(ctx_cc) == 2:
                sug["country_code"] = ctx_cc
            elif country_code:
                sug["country_code"] = country_code
            return sug

        # Google format: { placePrediction: { placeId, text: { text } } }
        place_pred = item.get("placePrediction") or item.get("place_prediction")
        if not place_pred:
            return None
        place_id = place_pred.get("placeId") or place_pred.get("place_id")
        if not place_id:
            return None
        text_obj = place_pred.get("text") or {}
        display_text = text_obj.get("text", "") if isinstance(text_obj, dict) else str(text_obj)
        if not display_text:
            display_text = place_pred.get("structuredFormat", {}).get("mainText", {}).get("text", "")
        sug = {"place_id": place_id, "display_text": display_text}
        if country_code:
            sug["country_code"] = country_code
        return sug


# Singleton for use in routes
address_autocomplete_service = AddressAutocompleteService()
