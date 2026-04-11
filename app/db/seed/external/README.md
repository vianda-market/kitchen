# `app/db/seed/external/` — Raw external reference data

This directory holds TSV snapshots of reference datasets that Vianda ingests from external sources into the `external.*` Postgres schema. The data is public, the schema is a verbatim mirror of the source, and the application is forbidden from writing here — only ingest scripts touch these tables.

See `docs/plans/country_city_data_structure.md` for the full architecture. The short version: `external.*` holds raw external data as-is, `core.*_metadata` layers Vianda's own flags + policy on top, and everywhere downstream references both via FK joins.

## Files

Row counts and sizes below are from the current committed snapshot; they will drift as GeoNames publishes updates.

| File | Source | Shape | Purpose |
|---|---|---|---|
| `geonames_country_info.tsv` | [`countryInfo.txt`](https://download.geonames.org/export/dump/countryInfo.txt) | 19 cols, 252 rows, 28 KB | Country list (ISO 3166 alpha-2/alpha-3/numeric, currency code, phone prefix, languages, capital, GeoNames id, neighbours). Comment lines stripped. |
| `geonames_admin1_codes.tsv` | [`admin1CodesASCII.txt`](https://download.geonames.org/export/dump/admin1CodesASCII.txt) | 6 cols, 3862 rows, 172 KB | State/province names per country. Transformed: the source `US.CA`-style code is split into `country_iso` + `admin1_code` at import time. |
| `geonames_cities5000.tsv` | [`cities5000.zip`](https://download.geonames.org/export/dump/cities5000.zip) → `cities5000.txt` | 19 cols, 68306 rows, 13 MB | Every city with population ≥ 5000. Each row carries its `admin1_code` (joinable to `geonames_admin1_codes.tsv` via `(country_iso, admin1_code)`). Includes per-city timezone. |
| `geonames_alternate_names.tsv` | [`alternateNamesV2.zip`](https://download.geonames.org/export/dump/alternateNamesV2.zip) → `alternateNamesV2.txt` | 8 cols, 51933 rows, 1.9 MB | Localized names (Córdoba, Brasil, Ciudad de México). **Filtered** at ingest time — only `iso_language ∈ {en, es, pt}` and only rows whose `geonameid` appears in the country/admin1/city files above. Filtered from 18.7M source rows. From/to historic date columns dropped; booleans normalized to Postgres text-format `t`/`f`. |
| `iso4217_currencies.tsv` | [`datasets/currency-codes`](https://github.com/datasets/currency-codes) → `data/codes-all.csv` | 4 cols, 178 rows, 4 KB | Authoritative ISO 4217 currency list: alphabetic code, display name, numeric code, minor-unit precision. Withdrawn currencies dropped; deduped by alphabetic code. |

Total committed size: ~15 MB (dominated by `geonames_cities5000.tsv` at 13 MB).

## How to refresh

All TSVs in this directory are produced by a single script:

```
python3 app/scripts/import_geonames.py
```

The script downloads from the canonical sources, applies the alternate-names filter, and writes everything back into this directory. It's idempotent — running twice against the same upstream snapshot produces byte-identical output.

**When to re-run:** when GeoNames ships a newer monthly dump and we want the refreshed data (new cities, renamed places, corrected timezones), or when we add a new supported locale and want the alternate-names filter to pick it up. Until either of those happens, the committed TSVs are the single source of truth for the `external.*` schema.

**After a refresh, inspect the diff** before committing. GeoNames occasionally renames or deletes rows, and any column change in `countryInfo.txt` that affects `market_info` copies (phone prefix, currency suggestion) should be surfaced for ops review before the `build_kitchen_db.sh` rebuild runs against a shared environment. A future diff-vs-review automation is captured as a backlog item in `docs/plans/country_city_data_structure.md`.

## Loader

The TSVs are loaded into Postgres via `COPY` statements in `app/db/seed/reference_data.sql` (invoked by `app/db/build_kitchen_db.sh` on a full rebuild, and by the corresponding migration file on an incremental apply). Loaders use the `text` format with `\t` delimiter and `\N` for NULL, matching the GeoNames convention. Alternate-name booleans are Postgres text-format (`t`/`f`), set by the import script.

## Licensing

GeoNames data is licensed under [Creative Commons Attribution 4.0 International (CC-BY 4.0)](https://creativecommons.org/licenses/by/4.0/) — redistribution and commercial use permitted, attribution required. The ISO 4217 list from datasets/currency-codes is Public Domain Dedication (PDDL). See `docs/licenses/THIRD_PARTY_ATTRIBUTIONS.md` for the attribution text we surface in product.

## Known exceptions

### `GL` pseudo-country

Vianda's historic data model uses `GL` (`'Global'`) as a market-level sentinel for institution entities that aren't tied to a specific country. GeoNames has no `GL` row — `GL` is ISO 3166 Greenland. To preserve the FK constraint from `market_info.country_code → external.geonames_country.iso_alpha2`, the bootstrap seed in `app/db/seed/reference_data.sql` inserts a **synthetic row** into `external.geonames_country` with `iso_alpha2 = 'GL'`, `name = 'Global'`, and other fields left NULL. This is the one documented exception to "raw is verbatim GeoNames data."

If GeoNames ever fills in their GL row with real Greenland data, the synthetic bootstrap will conflict on the PK and the load will fail — intentionally. Investigate and resolve by choosing either (a) renaming Vianda's Global sentinel to a non-ISO code, or (b) moving Greenland to the real ISO 3166 Greenland code `GL` and auditing downstream references.
