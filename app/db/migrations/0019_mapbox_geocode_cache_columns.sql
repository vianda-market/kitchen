-- Migration 0019: Add Mapbox geocode cache tracking columns.
--
-- Adds two nullable columns to core.geolocation_info (and its audit mirror):
--   mapbox_geocoded_at         — UTC timestamp when coordinates were resolved via Mapbox
--                                (live API in record mode, or cache replay in replay_only mode).
--   mapbox_normalized_address  — Normalized address query string used as the
--                                seeds/mapbox_geocode_cache.json cache key.
--
-- Additive only — no column drops or renames. Existing rows are unaffected (NULLs).
-- The backfill script (scripts/backfill_mapbox_geocoding.py) populates these for
-- existing records when run in replay_only mode after a DB rebuild.

ALTER TABLE core.geolocation_info
ADD COLUMN IF NOT EXISTS mapbox_geocoded_at TIMESTAMPTZ NULL,
ADD COLUMN IF NOT EXISTS mapbox_normalized_address TEXT NULL;

COMMENT ON COLUMN core.geolocation_info.mapbox_geocoded_at IS
'UTC timestamp when coordinates were resolved via Mapbox geocoding '
'(live API call in record mode, or cache replay in replay_only mode). '
'NULL for rows created before the cache system or not yet backfilled.';

COMMENT ON COLUMN core.geolocation_info.mapbox_normalized_address IS
'Normalized address query string used as the seeds/mapbox_geocode_cache.json cache key '
'(lowercase, trimmed, whitespace-collapsed). Stored so the backfill can re-derive the key '
'without rebuilding the address string from scratch.';

-- Mirror in audit.geolocation_history (trigger-managed; never written by app code).
ALTER TABLE audit.geolocation_history
ADD COLUMN IF NOT EXISTS mapbox_geocoded_at TIMESTAMPTZ NULL,
ADD COLUMN IF NOT EXISTS mapbox_normalized_address TEXT NULL;
