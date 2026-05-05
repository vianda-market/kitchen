-- Migration 0015: Drop inline image columns from ops.product_info
--
-- Part of the image-processing pipeline feature (Phase 2: atomic slice 2a/2b/2c).
-- The new ops.image_asset table (migration 0014) is now the authoritative source
-- for product image state. These five inline columns on product_info are replaced.
--
-- Dev DBs should be rebuilt — no real customer data exists on dev.
-- No data migration is needed: the image_asset table starts empty.

-- Drop the inline image columns from ops.product_info
ALTER TABLE ops.product_info DROP COLUMN IF EXISTS image_storage_path;
ALTER TABLE ops.product_info DROP COLUMN IF EXISTS image_checksum;
ALTER TABLE ops.product_info DROP COLUMN IF EXISTS image_url;
ALTER TABLE ops.product_info DROP COLUMN IF EXISTS image_thumbnail_storage_path;
ALTER TABLE ops.product_info DROP COLUMN IF EXISTS image_thumbnail_url;

-- Mirror column removals in audit.product_history (history columns may be NULL)
ALTER TABLE audit.product_history DROP COLUMN IF EXISTS image_storage_path;
ALTER TABLE audit.product_history DROP COLUMN IF EXISTS image_checksum;
ALTER TABLE audit.product_history DROP COLUMN IF EXISTS image_url;
ALTER TABLE audit.product_history DROP COLUMN IF EXISTS image_thumbnail_storage_path;
ALTER TABLE audit.product_history DROP COLUMN IF EXISTS image_thumbnail_url;
