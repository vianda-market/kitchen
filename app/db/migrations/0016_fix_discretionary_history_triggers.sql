-- 0016_fix_discretionary_history_triggers.sql
--
-- Fixes a latent FK ordering bug in two history triggers:
--   • discretionary_info_history_trigger
--   • discretionary_resolution_info_history_trigger
--
-- These were the only two history triggers in the codebase that fire on
-- DELETE.  On a DELETE, the AFTER trigger inserts an audit row whose
-- (discretionary_id | approval_id) FK references the main row that is
-- being deleted in the same statement.  The FK on the audit table is
-- ON DELETE RESTRICT (matching every other audit table), so the insert
-- fails with a FK violation and the DELETE is rolled back.
--
-- Every other history trigger in the codebase handles only INSERT and
-- UPDATE — DELETE is implicitly a no-op.  Soft delete via `is_archived`
-- is the project convention; the audit trail of `is_archived = true`
-- captures the lifecycle event without requiring a physical DELETE.
--
-- This migration brings the two outliers in line with the rest of the
-- codebase: the trigger event list drops DELETE, and the function body
-- drops the DELETE branch.
--
-- Surfaced by: feature/demo-day-data purge script (#247).
-- Resolves: github.com/vianda-market/kitchen/issues/247

-- -----------------------------------------------------------------------------
-- discretionary_info history trigger
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION discretionary_info_history_trigger()
RETURNS TRIGGER AS $$
DECLARE
    v_operation audit_operation_enum;
    v_changed_by UUID;
BEGIN
    IF (TG_OP = 'INSERT') THEN
        v_operation := 'create'::audit_operation_enum;
        v_changed_by := NEW.modified_by;
        INSERT INTO audit.discretionary_history (
            discretionary_id, user_id, restaurant_id, approval_id,
            category, reason, amount, comment,
            is_archived, status,
            created_date, created_by, modified_date, modified_by,
            operation, changed_by
        ) VALUES (
            NEW.discretionary_id, NEW.user_id, NEW.restaurant_id, NEW.approval_id,
            NEW.category, NEW.reason, NEW.amount, NEW.comment,
            NEW.is_archived, NEW.status,
            NEW.created_date, NEW.created_by, NEW.modified_date, NEW.modified_by,
            v_operation, v_changed_by
        );
        RETURN NEW;
    ELSIF (TG_OP = 'UPDATE') THEN
        v_operation := 'update'::audit_operation_enum;
        v_changed_by := NEW.modified_by;
        INSERT INTO audit.discretionary_history (
            discretionary_id, user_id, restaurant_id, approval_id,
            category, reason, amount, comment,
            is_archived, status,
            created_date, created_by, modified_date, modified_by,
            operation, changed_by
        ) VALUES (
            NEW.discretionary_id, NEW.user_id, NEW.restaurant_id, NEW.approval_id,
            NEW.category, NEW.reason, NEW.amount, NEW.comment,
            NEW.is_archived, NEW.status,
            NEW.created_date, NEW.created_by, NEW.modified_date, NEW.modified_by,
            v_operation, v_changed_by
        );
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS discretionary_info_history_trigger ON billing.discretionary_info;
CREATE TRIGGER discretionary_info_history_trigger
AFTER INSERT OR UPDATE ON billing.discretionary_info
FOR EACH ROW EXECUTE FUNCTION discretionary_info_history_trigger();

-- -----------------------------------------------------------------------------
-- discretionary_resolution_info history trigger
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION discretionary_resolution_info_history_trigger()
RETURNS TRIGGER AS $$
DECLARE
    v_operation audit_operation_enum;
    v_changed_by UUID;
BEGIN
    IF (TG_OP = 'INSERT') THEN
        v_operation := 'create'::audit_operation_enum;
        v_changed_by := NEW.resolved_by;
        INSERT INTO audit.discretionary_resolution_history (
            approval_id, discretionary_id, resolution,
            is_archived, status,
            resolved_by, resolved_date, created_date, resolution_comment,
            operation, changed_by
        ) VALUES (
            NEW.approval_id, NEW.discretionary_id, NEW.resolution,
            NEW.is_archived, NEW.status,
            NEW.resolved_by, NEW.resolved_date, NEW.created_date, NEW.resolution_comment,
            v_operation, v_changed_by
        );
        RETURN NEW;
    ELSIF (TG_OP = 'UPDATE') THEN
        v_operation := 'update'::audit_operation_enum;
        v_changed_by := NEW.resolved_by;
        INSERT INTO audit.discretionary_resolution_history (
            approval_id, discretionary_id, resolution,
            is_archived, status,
            resolved_by, resolved_date, created_date, resolution_comment,
            operation, changed_by
        ) VALUES (
            NEW.approval_id, NEW.discretionary_id, NEW.resolution,
            NEW.is_archived, NEW.status,
            NEW.resolved_by, NEW.resolved_date, NEW.created_date, NEW.resolution_comment,
            v_operation, v_changed_by
        );
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS discretionary_resolution_info_history_trigger ON billing.discretionary_resolution_info;
CREATE TRIGGER discretionary_resolution_info_history_trigger
AFTER INSERT OR UPDATE ON billing.discretionary_resolution_info
FOR EACH ROW EXECUTE FUNCTION discretionary_resolution_info_history_trigger();
