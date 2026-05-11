# Archived Tech Debt (2026-03-14)

Archived as part of API documentation cleanup for client-facing exposure.

## Contents

- **routes/location_info.py** — Deprecated location-info endpoints (city-based timezone). Use Markets API (`/api/v1/markets/`), Countries, and Provinces instead.

## Migration Notes

- `GET /location-info/countries/{country_code}/provinces` → `GET /api/v1/provinces/` or equivalent
- Timezone deduction: Use country_code + province during address creation; Markets API provides country info.
