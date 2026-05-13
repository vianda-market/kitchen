# Other Google Maps APIs – Future Roadmap

**Last Updated**: 2026-03-09  
**Purpose**: High-level value add for additional Google Maps APIs beyond address autocomplete and geocoding.

---

## Overview

The backend already uses Places API (Autocomplete, Place Details) and Geocoding API for address normalization and coordinates. This roadmap outlines further Google APIs that can enhance user experience, operations, and product decisions.

| Initiative           | API / Feature             | Use Case                                      | Value Add |
| -------------------- | ------------------------- | --------------------------------------------- | --------- |
| Distance matrix      | Distance Matrix API       | Estimate travel time restaurant ↔ pickup     | **UX**: Show “~15 min by car” so users can plan pickup timing |
| Restaurant discovery | Places Search (nearby)    | “Restaurants near my work”                    | **Growth**: Expand explore beyond city to proximity search |
| Delivery zones       | Directions API + polygons | Define delivery areas                         | **Operations**: Enforce delivery boundaries; show “outside zone” |
| Store locator        | Place Details + Maps     | Restaurant location detail page               | **Conversion**: One-tap directions; richer location context |
| Analytics            | Maps usage reports        | Usage and cost monitoring                     | **FinOps**: Track API spend, optimize call patterns |

---

## Distance Matrix – Travel Time Estimation

**API**: Distance Matrix API

**Use case**: Estimate travel time from restaurant to pickup or from user to restaurant.

**Value add**:
- **User experience**: Display “~12 min drive” so users can judge pickup timing and avoid late arrivals.
- **Vianda selection**: Surface restaurants within a time range (e.g. &lt; 20 min).
- **Operations**: Help pickup volunteers plan routes.

**Considerations**: Cost per element; batch requests for multiple origins/destinations.

---

## Restaurant Discovery – Nearby Search

**API**: Places API (Places Search – Nearby Search)

**Use case**: “Restaurants near my work” or “near my current location.”

**Value add**:
- **Growth**: Extend B2C explore from city-based to location-based discovery.
- **Personalization**: Results tuned to user’s work or home location.
- **Differentiation**: Compete on convenience rather than only cuisine/city.

**Considerations**: Requires user location; overlap with existing city/zipcode explore.

---

## Delivery Zones – Boundaries and Polygons

**API**: Directions API + custom polygon logic (or similar)

**Use case**: Define delivery zones per restaurant or market; enforce or display “outside delivery area.”

**Value add**:
- **Operations**: Clear rules for which addresses can receive delivery.
- **Cost control**: Avoid deliveries to far or unprofitable areas.
- **Transparency**: Show users whether their address is in-zone before ordering.

**Considerations**: Polygon definition and storage; integration with address validation.

---

## Store Locator – Location Detail Page

**API**: Place Details (already in use) + Maps URLs / embedding

**Use case**: Restaurant location page with map, directions, hours, photos.

**Value add**:
- **Conversion**: “View on map” and “Get directions” reduce friction to visit.
- **Trust**: Map and photos make locations feel real and accessible.
- **SEO**: Rich location pages can improve search visibility.

**Considerations**: Place Details is already used; this is mostly UX and embedding.

---

## Analytics – Maps Usage and Cost Monitoring

**API**: Maps usage reports (Cloud Console / APIs dashboard)

**Use case**: Track API calls, costs, error rates, and usage patterns.

**Value add**:
- **FinOps**: Predict and control Google Maps spend; spot spikes.
- **Optimization**: Identify high-cost endpoints or flows for caching/rate limiting.
- **Reliability**: Monitor failures and latency to improve SLAs.

**Considerations**: No new integration; dashboard usage and possibly exported metrics.
