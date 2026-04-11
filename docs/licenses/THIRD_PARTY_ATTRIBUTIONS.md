# Third-Party Attributions

This document records the third-party datasets and code Vianda redistributes or incorporates, and the attribution text required by each license. Product surfaces that expose any of the data below must include the corresponding attribution in a user-reachable location (footer, about page, settings → attributions, or equivalent).

## GeoNames geographical database

**What we use:** country list, state/province codes, cities with population ≥ 5000, and localized name variants, ingested into the `external.geonames_*` tables and referenced by every downstream operational table (market, address, user, institution entity, restaurant).

**Source files:**
- `countryInfo.txt`
- `admin1CodesASCII.txt`
- `cities5000.zip`
- `alternateNamesV2.zip`

All sourced from https://download.geonames.org/export/dump/.

**License:** [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).

**Required attribution text:**

> This product includes geographical data created by [GeoNames](https://www.geonames.org/), licensed under CC BY 4.0.

This line must appear on any Vianda user-facing surface that displays country, city, or localized place-name data sourced from GeoNames — at minimum the marketing site (vianda-home), the customer app (vianda-app), and the employer/supplier platform (vianda-platform). A footer link on each site is sufficient; a dedicated attributions page linked from the footer is preferred.

## ISO 4217 currency list (datasets/currency-codes)

**What we use:** the canonical ISO 4217 currency list (alphabetic code, display name, numeric code, minor-unit precision), ingested into `external.iso4217_currency` and referenced by `core.currency_metadata` which carries Vianda's per-currency pricing policy.

**Source file:** `data/codes-all.csv` from https://github.com/datasets/currency-codes.

**License:** [Open Data Commons Public Domain Dedication and License (PDDL)](https://opendatacommons.org/licenses/pddl/). Attribution is not required, but it is good practice to acknowledge the source.

**Acknowledgement (optional, not required by license):**

> Currency codes sourced from the [datasets/currency-codes](https://github.com/datasets/currency-codes) open-data project, mirroring ISO 4217.

## How to update this file

Add a new section whenever a new external dataset or third-party code dependency is introduced. For each, document: what we use, source URL, license, and the exact attribution text plus where it must appear in product.
