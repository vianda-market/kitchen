-- Migration 0017: Add canonical_key to core.employer_benefits_program
-- Enables PUT /employer/program/by-key idempotent upsert endpoint.

-- Add column
ALTER TABLE core.employer_benefits_program
ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

-- Add column to history table too
ALTER TABLE audit.employer_benefits_program_history
ADD COLUMN IF NOT EXISTS canonical_key VARCHAR(200) NULL;

-- Partial unique index (sparse: only indexed when non-null)
CREATE UNIQUE INDEX IF NOT EXISTS uq_employer_benefits_program_canonical_key
ON core.employer_benefits_program (canonical_key)
WHERE canonical_key IS NOT NULL;

COMMENT ON COLUMN core.employer_benefits_program.canonical_key IS
'Stable human-readable key for idempotent upsert via PUT /employer/program/by-key. '
'NULL for programs created via POST /employer/program. '
'Convention: EMPLOYER_<INSTITUTION_SLUG>_PROGRAM[_ENTITY_<CC>]. '
'Once set, never rename — renaming creates a new row and orphans the old one.';
