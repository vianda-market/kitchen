-- Migration 0014: Create ops.image_asset table
--
-- Part of the image-processing pipeline feature (Phase 2: atomic slice 2a/2b/2c).
-- Tracks upload state and processing status for product images.
-- Dev DBs should be rebuilt — no real customer data exists on dev.
--
-- Key design decisions:
--   • UNIQUE (product_id): one image_asset per product (v1)
--   • pipeline_status: 'pending' until the Cloud Run job processes the original
--   • moderation_status: 'pending' until Cloud Vision SafeSearch runs
--   • processing_version: bumped when pipeline standards change; enables backfill
--   • institution_id: denormalized for scoping (avoids JOIN on every scope check)
--   • original_checksum: nullable so upload route can insert before the client
--     sends the file (checksum confirmed by the pipeline worker)

CREATE TABLE IF NOT EXISTS ops.image_asset (
    image_asset_id UUID PRIMARY KEY DEFAULT uuidv7(),
    product_id UUID NOT NULL REFERENCES ops.product_info (product_id) ON DELETE CASCADE,
    institution_id UUID NOT NULL REFERENCES core.institution_info (institution_id) ON DELETE RESTRICT,
    original_storage_path TEXT,
    original_checksum TEXT,
    pipeline_status TEXT NOT NULL CHECK (pipeline_status IN ('pending', 'processing', 'ready', 'rejected', 'failed')),
    moderation_status TEXT NOT NULL CHECK (moderation_status IN ('pending', 'passed', 'rejected')),
    moderation_signals JSONB NULL,
    processing_version INTEGER NOT NULL DEFAULT 1,
    failure_count INTEGER NOT NULL DEFAULT 0,
    created_date TIMESTAMPTZ NOT NULL DEFAULT now(),
    modified_date TIMESTAMPTZ NOT NULL DEFAULT now(),
    modified_by UUID NULL REFERENCES core.user_info (user_id) ON DELETE RESTRICT,
    UNIQUE (product_id)
);

COMMENT ON TABLE ops.image_asset IS
'Tracks the upload and processing lifecycle of a product image. '
'One row per product (v1). pipeline_status starts as pending and is '
'flipped to ready by the Cloud Run image processor after pyvips + SafeSearch. '
'institution_id is denormalized for fast scope checks.';

COMMENT ON COLUMN ops.image_asset.image_asset_id IS 'UUIDv7 primary key. Time-ordered.';
COMMENT ON COLUMN ops.image_asset.product_id IS
'FK to ops.product_info. One image per product (v1).';
COMMENT ON COLUMN ops.image_asset.institution_id IS
'Denormalized FK to core.institution_info. Used for supplier scoping without JOIN.';
COMMENT ON COLUMN ops.image_asset.original_storage_path IS
'GCS path of the supplier-uploaded original: products/{institution_id}/{product_id}/original.';
COMMENT ON COLUMN ops.image_asset.original_checksum IS
'SHA-256 hex checksum of the uploaded original bytes. NULL until pipeline confirms.';
COMMENT ON COLUMN ops.image_asset.pipeline_status IS
'Processing lifecycle: pending → processing → ready | rejected | failed.';
COMMENT ON COLUMN ops.image_asset.moderation_status IS
'SafeSearch result: pending → passed | rejected.';
COMMENT ON COLUMN ops.image_asset.moderation_signals IS
'Raw Cloud Vision SafeSearch likelihoods JSON for audit. NULL until moderation runs.';
COMMENT ON COLUMN ops.image_asset.processing_version IS
'Pipeline standard version applied. Backfill iterates WHERE processing_version < CURRENT.';
COMMENT ON COLUMN ops.image_asset.failure_count IS
'Number of processing attempts that ended in failure.';
COMMENT ON COLUMN ops.image_asset.modified_by IS
'FK to core.user_info. Last user to trigger an upload or delete. NULL for pipeline updates.';

-- Audit history table
CREATE TABLE IF NOT EXISTS audit.image_asset_history (
    event_id UUID PRIMARY KEY DEFAULT uuidv7(),
    image_asset_id UUID NOT NULL,
    product_id UUID NOT NULL,
    institution_id UUID NOT NULL,
    original_storage_path TEXT,
    original_checksum TEXT,
    pipeline_status TEXT NOT NULL,
    moderation_status TEXT NOT NULL,
    moderation_signals JSONB NULL,
    processing_version INTEGER NOT NULL,
    failure_count INTEGER NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity'
);

COMMENT ON TABLE audit.image_asset_history IS
'Trigger-managed history mirror of ops.image_asset. Never written by application code.';

-- Index for future backfill query: WHERE processing_version < CURRENT_PROCESSING_VERSION
CREATE INDEX IF NOT EXISTS idx_image_asset_processing_version ON ops.image_asset (processing_version);
