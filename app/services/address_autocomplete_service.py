"""
Address autocomplete service.

Uses the configured autocomplete provider (controlled by ADDRESS_AUTOCOMPLETE_PROVIDER):
  "geocoding"  — MapboxGeocodingGateway (forward search, permanent dataset). Default.
  "search_box" — MapboxSearchGateway (ephemeral session). Q2 fallback.

Both providers expose an identical canonical suggestion shape:
  {"place_id": str, "display_text": str, "country_code": str (optional)}

Q2 rule (enforced regardless of provider): every persisted address field —
text, lat/lng, place_id, normalized address, neighborhood, context — comes from
the places-permanent geocoding response. Search Box outputs never reach the DB.
"""

import uuid
from typing import Any, Protocol

from app.utils.country import country_alpha3_to_alpha2, country_name_to_alpha2
from app.utils.log import log_error, log_info

# ---------------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------------


class AutocompleteProvider(Protocol):
    """Protocol for autocomplete providers.

    Both ``SearchBoxAutocompleteProvider`` and ``GeocodingAutocompleteProvider``
    must return suggestions in the canonical shape:
      [{"place_id": str, "display_text": str, "country_code": str (optional)}, ...]
    """

    def suggest(
        self,
        query: str,
        country: str | None,
        session_token: str | None,
        limit: int,
    ) -> list[dict[str, Any]]: ...


# ---------------------------------------------------------------------------
# SearchBox provider (Q2 fallback)
# ---------------------------------------------------------------------------


class SearchBoxAutocompleteProvider:
    """Wraps MapboxSearchGateway for autocomplete.

    Q2 rule: the place_id returned here is a Search Box mapbox_id.  The
    address-save flow calls _resolve_address_from_place_id, which uses the Search
    Box retrieve endpoint to extract address fields (street, city, etc.), but
    intentionally discards geolocation from the retrieve response and re-geocodes
    via places-permanent.  Nothing from the Search Box retrieve response is
    persisted to geolocation_info.

    place_id format: Search Box mapbox_id (e.g. "dXJuOm1ieHBsYzo0NTk2Mjg").
    This is the same underlying Mapbox entity ID as geocoding mapbox_id, so both
    providers return IDs that the downstream retrieve / geocode flow can consume.
    """

    def __init__(self) -> None:
        from app.gateways.mapbox_search_gateway import get_mapbox_search_gateway

        self._gateway = get_mapbox_search_gateway()

    def suggest(
        self,
        query: str,
        country: str | None,
        session_token: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        raw = self._gateway.suggest(
            query=query,
            country=country,
            session_token=session_token,
            limit=limit,
        )
        return _parse_search_box_suggestions(raw.get("suggestions") or [], limit, country_code=None)


# ---------------------------------------------------------------------------
# Geocoding provider (Plan B default)
# ---------------------------------------------------------------------------


class GeocodingAutocompleteProvider:
    """Wraps MapboxGeocodingGateway (permanent=True) for autocomplete.

    Uses the v6 forward endpoint with autocomplete=true for partial-match
    ranking.  The persistent-storage token and permanent=true param are sent,
    making this TOS-clean for workflows that ultimately persist the resolved
    address.

    place_id format: Geocoding API mapbox_id (e.g. "dXJuOm1ieHBsYzo0NTk2Mjg").
    This is the same underlying Mapbox entity ID as Search Box mapbox_id, so the
    downstream address-save flow (which calls Search Box retrieve or geocode_full)
    consumes both ID formats without modification.

    Q2 rule: geolocation is always resolved via places-permanent downstream —
    never from this forward_search response.
    """

    def __init__(self) -> None:
        from app.gateways.mapbox_geocoding_gateway import get_mapbox_geocoding_gateway

        # Always use the permanent gateway so autocomplete calls originate from
        # the places-permanent dataset (TOS-clean, single paid call).
        self._gateway = get_mapbox_geocoding_gateway(permanent=True)

    def suggest(
        self,
        query: str,
        country: str | None,
        session_token: str | None,  # noqa: ARG002 — unused; Geocoding API has no session billing
        limit: int,
    ) -> list[dict[str, Any]]:
        raw = self._gateway.forward_search(
            query=query,
            country=country,
            limit=limit,
        )
        return _parse_geocoding_suggestions(raw.get("features") or [], limit, country_code=country)


# ---------------------------------------------------------------------------
# Canonical shape parsers
# ---------------------------------------------------------------------------


def _parse_search_box_suggestions(
    suggestions: list[dict[str, Any]],
    limit: int,
    country_code: str | None,
) -> list[dict[str, Any]]:
    """Translate Search Box suggest items to the canonical autocomplete shape."""
    out: list[dict[str, Any]] = []
    for item in suggestions:
        if len(out) >= limit:
            break
        sug = _parse_search_box_item(item, country_code)
        if sug:
            out.append(sug)
    return out


def _parse_search_box_item(item: dict[str, Any], country_code: str | None) -> dict[str, Any] | None:
    """Parse a single Search Box suggestion to the canonical shape."""
    mapbox_id = item.get("mapbox_id", "")
    if not mapbox_id:
        return None
    display_text = item.get("full_address") or item.get("name") or ""
    sug: dict[str, Any] = {"place_id": mapbox_id, "display_text": display_text}
    ctx_cc = (item.get("context", {}).get("country", {}).get("country_code") or "").upper()
    if ctx_cc and len(ctx_cc) == 2:
        sug["country_code"] = ctx_cc
    elif country_code:
        sug["country_code"] = country_code
    return sug


def _parse_geocoding_suggestions(
    features: list[dict[str, Any]],
    limit: int,
    country_code: str | None,
) -> list[dict[str, Any]]:
    """Translate Geocoding API v6 forward features to the canonical autocomplete shape."""
    out: list[dict[str, Any]] = []
    for feature in features:
        if len(out) >= limit:
            break
        sug = _parse_geocoding_feature(feature, country_code)
        if sug:
            out.append(sug)
    return out


def _parse_geocoding_feature(feature: dict[str, Any], country_code: str | None) -> dict[str, Any] | None:
    """Parse a single Geocoding API v6 Feature to the canonical autocomplete shape.

    place_id  ← properties.mapbox_id  (same entity-ID namespace as Search Box mapbox_id)
    display_text ← properties.full_address (or properties.name as fallback)
    country_code ← properties.context.country.country_code (ISO 3166-1 alpha-2) when present
    """
    props = feature.get("properties", {})
    mapbox_id = props.get("mapbox_id", "")
    if not mapbox_id:
        return None
    display_text = props.get("full_address") or props.get("name") or ""
    sug: dict[str, Any] = {"place_id": mapbox_id, "display_text": display_text}
    ctx_cc = (props.get("context", {}).get("country", {}).get("country_code") or "").upper()
    if ctx_cc and len(ctx_cc) == 2:
        sug["country_code"] = ctx_cc
    elif country_code and len(country_code) == 2:
        sug["country_code"] = country_code.upper()
    return sug


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AddressAutocompleteService:
    """Service for address suggest (autocomplete) from partial input."""

    def __init__(self, provider: AutocompleteProvider | None = None):
        if provider is not None:
            self._provider = provider
        else:
            self._provider = get_autocomplete_provider()

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

        # Generate session token if not provided (Mapbox billing optimization for Search Box)
        if not session_token:
            session_token = str(uuid.uuid4())

        try:
            out = self._provider.suggest(
                query=input_text,
                country=alpha2,
                session_token=session_token,
                limit=limit,
            )
        except Exception as e:
            log_error(f"Address suggest autocomplete failed: {e}")
            return []

        log_info(f"Address suggest returned {len(out)} suggestions for q={input_text!r}")
        return out


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_autocomplete_provider() -> AutocompleteProvider:
    """Return the active autocomplete provider based on ADDRESS_AUTOCOMPLETE_PROVIDER setting.

    "geocoding"  → GeocodingAutocompleteProvider (Plan B, default)
    "search_box" → SearchBoxAutocompleteProvider (Q2 fallback)

    This is the single place in the codebase that branches on the setting.
    All other code is provider-agnostic.
    """
    from app.config.settings import get_settings

    provider_setting = get_settings().ADDRESS_AUTOCOMPLETE_PROVIDER
    if provider_setting == "search_box":
        return SearchBoxAutocompleteProvider()
    return GeocodingAutocompleteProvider()


# Singleton for use in routes
address_autocomplete_service = AddressAutocompleteService()
