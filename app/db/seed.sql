-- Seed loader: loads reference data + dev fixtures.
-- Kept as a shim so existing scripts that \i seed.sql keep working.
-- For selective loading, use the files in app/db/seed/ directly.
\i app/db/seed/reference_data.sql
\i app/db/seed/dev_fixtures.sql
