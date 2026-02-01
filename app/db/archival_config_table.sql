-- Archival Configuration Table
-- This allows business users to modify archival policies without code changes

\echo 'Creating table: archival_config'
CREATE TABLE IF NOT EXISTS archival_config (
    config_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50) NOT NULL CHECK (category IN (
        'financial_critical',
        'financial_operational', 
        'customer_service',
        'operational_data',
        'reference_data',
        'security_compliance',
        'system_configuration'
    )),
    retention_days INTEGER NOT NULL CHECK (retention_days >= 0),
    grace_period_days INTEGER NOT NULL CHECK (grace_period_days >= 0),
    priority INTEGER NOT NULL CHECK (priority >= 1),
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    effective_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_archival_config_active ON archival_config(is_active, table_name);
CREATE INDEX IF NOT EXISTS idx_archival_config_category ON archival_config(category, is_active);

-- Archival Configuration History Table
\echo 'Creating table: archival_config_history'
CREATE TABLE IF NOT EXISTS archival_config_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_id UUID NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    retention_days INTEGER NOT NULL,
    grace_period_days INTEGER NOT NULL,
    priority INTEGER NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL,
    effective_date TIMESTAMPTZ NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    -- History metadata
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    change_reason TEXT,
    FOREIGN KEY (config_id) REFERENCES archival_config(config_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

-- Index for history queries
CREATE INDEX IF NOT EXISTS idx_archival_config_history_config_id ON archival_config_history(config_id);
CREATE INDEX IF NOT EXISTS idx_archival_config_history_current ON archival_config_history(config_id, is_current);

-- Trigger for archival_config history logging
CREATE OR REPLACE FUNCTION archival_config_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuid_generate_v4();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark previous version as no longer current
        UPDATE archival_config_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE config_id = OLD.config_id AND is_current = TRUE;
    END IF;

    -- Insert new version
    INSERT INTO archival_config_history (
        event_id, config_id, table_name, category, retention_days, grace_period_days,
        priority, description, is_active, effective_date, created_date, modified_by, 
        modified_date, is_current, valid_until, change_reason
    )
    VALUES (
        new_event_id, NEW.config_id, NEW.table_name, NEW.category, NEW.retention_days, 
        NEW.grace_period_days, NEW.priority, NEW.description, NEW.is_active, 
        NEW.effective_date, NEW.created_date, NEW.modified_by, NEW.modified_date,
        TRUE, 'infinity', 
        CASE 
            WHEN TG_OP = 'INSERT' THEN 'Initial configuration'
            WHEN TG_OP = 'UPDATE' THEN 'Configuration updated'
            ELSE 'Unknown change'
        END
    );
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER archival_config_history_trigger
AFTER INSERT OR UPDATE ON archival_config
FOR EACH ROW
EXECUTE FUNCTION archival_config_history_trigger_func(); 