# Country / City / Currency Data Structure

Authoritative reference for the two-tier geographic and currency data model.

---

## Two-Tier Model

### External Layer (read-only at runtime)

Bulk-seeded from GeoNames + ISO 4217 TSVs via `app/scripts/import_geonames.py`. Licensed under CC-BY 4.0.

| Table | Source | Purpose |
|-------|--------|---------|
| `external.geonames_country` | GeoNames `countryInfo.txt` | Country master: ISO alpha-2, name, continent, area, population, currencies |
| `external.geonames_admin1` | GeoNames `admin1CodesASCII.txt` | First-level admin divisions (provinces/states) |
| `external.geonames_city` | GeoNames `cities15000.txt` | Cities with population >= 15k: lat/lng, timezone, country_code, admin1_code |
| `external.geonames_alternate_name` | GeoNames `alternateNamesV2.txt` | Localized names for cities/countries (i18n display) |
| `external.iso4217_currency` | ISO 4217 | Currency master: code, name, numeric code, minor units |

These tables are **never written at runtime**. Re-import by running `import_geonames.py` with fresh TSVs placed in `app/db/seed/external/`.

### Metadata Layer (Vianda-owned operational config)

| Table | Purpose |
|-------|---------|
| `core.country_metadata` | Audience flags, status, pricing policy, display overrides per country |
| `core.city_metadata` | City-level config: `display_name_override`, `geonames_id` FK, status |
| `core.currency_metadata` | Currency operational config: `currency_code` FK to `iso4217_currency`, status |

Audited via `audit.country_metadata_history`, `audit.city_metadata_history`, `audit.currency_metadata_history` tables + triggers.

### Retired Tables

| Table/Column | Dropped in | Replacement |
|---|---|---|
| `core.city_info` | PR1 | `external.geonames_city` + `core.city_metadata` |
| `core.credit_currency_info` | PR1 | `external.iso4217_currency` + `core.currency_metadata` |
| `market_info.country_name` | PR2a | JOIN `external.geonames_country` on `iso_alpha2` |
| `market_info.timezone` | PR2b | `address_info.timezone` (per-address) |
| `currency_metadata.currency_name` | PR2a | JOIN `external.iso4217_currency` on `code` |

---

## Key JOIN Patterns

### Country name

```sql
SELECT gc.name AS country_name
FROM core.market_info m
JOIN external.geonames_country gc ON gc.iso_alpha2 = m.country_code
```

### Currency name

```sql
SELECT ic.name AS currency_name
FROM core.currency_metadata cc
JOIN external.iso4217_currency ic ON ic.code = cc.currency_code
```

### City display name

```sql
SELECT COALESCE(cm.display_name_override, gc.name) AS city_name
FROM core.city_metadata cm
JOIN external.geonames_city gc ON gc.geonames_id = cm.geonames_id
```

### Timezone

Timezone lives on `address_info.timezone` (per-address, per-restaurant). Derived from `external.geonames_city.timezone` via `city_metadata.geonames_id` at address write time.

Market-level fallback for cron jobs and contexts without a specific address: `TimezoneService._MARKET_PRIMARY_TIMEZONE` dict in `app/services/timezone_service.py`.

---

## Audience Flags (country_metadata)

Three boolean columns on `core.country_metadata`:

- `is_customer_audience` -- country appears in B2C market/city dropdowns
- `is_supplier_audience` -- country appears in supplier onboarding flows
- `is_employer_audience` -- country appears in employer registration flows

These flags control which countries appear in:
- `GET /leads/markets` (filtered by `audience` query param)
- `GET /leads/cities` (filtered by `audience` query param)

---

## Superadmin Promotion Flow (Future)

1. Admin browses external data via `/admin/external/*` picker endpoints
2. Selects a country/province/city from GeoNames data
3. Backend creates or updates the corresponding `core.country_metadata` or `core.city_metadata` row
4. Admin flips audience flags and transitions status from `pending` to `active`

This separates "data exists in GeoNames" from "Vianda operates here."

---

## Kitchen Hours

`market_info.kitchen_open_time` and `market_info.kitchen_close_time` are market-level templates.

Restaurants inherit these values at creation time into `restaurant_info.kitchen_open_time` and `restaurant_info.kitchen_close_time`. After creation, restaurant hours are independent of the market template.

---

## XG Pseudo-Country (Global)

`XG` is an ISO 3166-1 user-assigned X-series code used for Vianda's Global pseudo-market.

Synthetic rows:
- `external.geonames_country`: `iso_alpha2='XG'`, `name='Global'`
- `external.geonames_city`: `geonames_id=-1`, `country_code='XG'`
- `core.city_metadata`: UUID `aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa`, linked to `geonames_id=-1`

The Global market hosts system-wide entities that are not scoped to any geographic market (e.g., the Vianda Customers institution).

---

## Key Files

| Concern | Location |
|---------|----------|
| Schema definitions | `app/db/schema.sql` |
| Reference data seed | `app/db/seed/reference_data.sql` |
| External TSVs | `app/db/seed/external/` |
| GeoNames importer | `app/scripts/import_geonames.py` |
| Market service | `app/services/market_service.py` |
| City metrics service | `app/services/city_metrics_service.py` |
| Entity service | `app/services/entity_service.py` |
| Timezone service | `app/services/timezone_service.py` |
| Admin external picker | `app/routes/admin/external_data.py` |
| Leads (audience-aware) | `app/routes/leads.py` |
| Cities route | `app/routes/cities.py` |
| Country utilities | `app/utils/country.py` |
