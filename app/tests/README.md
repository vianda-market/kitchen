# Test suite

- **Project rules**: See [cursorrules.md](../../cursorrules.md) at the repo root for paths, DB (tear-down/rebuild, no migrations), Postman expectations, and updating unit tests when changing DB/triggers/DTOs.
- **Database tests**: Schema and seed validation live under [app/tests/database](database/). They replace the former pgTAP SQL tests that were in `app/db/tests`.
- **Legacy `app/db/tests`**: That folder is **archived**. Coverage is superseded by `app/tests/database` (e.g. `test_schema.py`, `test_seed.py`). The SQL file `03_supplier_onboarding.sql` targeted an older schema (e.g. `address_info.country`, pre–country_code normalization) and is not migrated. You can delete the `app/db/tests` folder.

Structure:

- **auth/** – authentication dependencies
- **database/** – schema existence, seed data, integration (requires DB)
- **gateways/** – external service gateways
- **routes/** – route integration tests (with dependency overrides)
- **services/** – business logic and mapping
