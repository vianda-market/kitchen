"""
Address provider abstraction — factory functions that return the configured gateway.

Driven by settings.ADDRESS_PROVIDER ("mapbox" or "google").
Lazy imports avoid circular dependencies and load only the active provider.
"""

from app.config.settings import get_settings


def get_search_gateway():
    """Return address search gateway based on ADDRESS_PROVIDER setting.

    Mapbox: MapboxSearchGateway (suggest + retrieve)
    Google: GooglePlacesGateway (places_autocomplete + place_details)
    """
    provider = get_settings().ADDRESS_PROVIDER.lower()
    if provider == "google":
        from app.gateways.google_places_gateway import get_google_places_gateway
        return get_google_places_gateway()
    from app.gateways.mapbox_search_gateway import get_mapbox_search_gateway
    return get_mapbox_search_gateway()


def get_geocoding_gateway():
    """Return geocoding gateway based on ADDRESS_PROVIDER setting.

    Mapbox: MapboxGeocodingGateway (Geocoding API v6)
    Google: GoogleMapsGateway (Maps Geocoding API)
    """
    provider = get_settings().ADDRESS_PROVIDER.lower()
    if provider == "google":
        from app.gateways.google_maps_gateway import get_google_maps_gateway
        return get_google_maps_gateway()
    from app.gateways.mapbox_geocoding_gateway import get_mapbox_geocoding_gateway
    return get_mapbox_geocoding_gateway()
