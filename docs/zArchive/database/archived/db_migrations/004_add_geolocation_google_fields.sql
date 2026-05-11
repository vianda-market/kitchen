-- Add Google Place fields to geolocation_info and geolocation_history
-- For address autocomplete flow: place_id, viewport, formatted_address_google

ALTER TABLE geolocation_info
  ADD COLUMN IF NOT EXISTS place_id VARCHAR(255) NULL,
  ADD COLUMN IF NOT EXISTS viewport JSONB NULL,
  ADD COLUMN IF NOT EXISTS formatted_address_google VARCHAR(500) NULL;

ALTER TABLE geolocation_history
  ADD COLUMN IF NOT EXISTS place_id VARCHAR(255) NULL,
  ADD COLUMN IF NOT EXISTS viewport JSONB NULL,
  ADD COLUMN IF NOT EXISTS formatted_address_google VARCHAR(500) NULL;

-- Note: geolocation_history_trigger_func must be recreated to include new columns.
-- Run app/db/trigger.sql after this migration to update the trigger.
