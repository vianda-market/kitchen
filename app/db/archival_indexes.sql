-- Archival Performance Indexes
-- These indexes optimize queries for the archival system

-- Orders (plate_pickup_live) archival indexes
CREATE INDEX IF NOT EXISTS idx_plate_pickup_archival 
ON plate_pickup_live(status, completion_time, is_archived) 
WHERE completion_time IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_plate_pickup_archival_eligible 
ON plate_pickup_live(is_archived, status, completion_time) 
WHERE is_archived = FALSE AND status = 'Completed';

-- Transactions (restaurant_transaction) archival indexes  
CREATE INDEX IF NOT EXISTS idx_restaurant_transaction_archival
ON restaurant_transaction(status, completion_time, is_archived)
WHERE completion_time IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_restaurant_transaction_archival_eligible
ON restaurant_transaction(is_archived, status, completion_time)
WHERE is_archived = FALSE AND status = 'Completed';

-- Client transactions archival indexes
CREATE INDEX IF NOT EXISTS idx_client_transaction_archival
ON client_transaction(status, created_date, is_archived);

CREATE INDEX IF NOT EXISTS idx_client_transaction_archival_eligible
ON client_transaction(is_archived, status, created_date)
WHERE is_archived = FALSE;

-- Subscriptions archival indexes
CREATE INDEX IF NOT EXISTS idx_subscription_archival
ON subscription_info(status, modified_date, is_archived);

CREATE INDEX IF NOT EXISTS idx_subscription_archival_eligible
ON subscription_info(is_archived, status, modified_date)
WHERE is_archived = FALSE;

-- User data archival indexes
CREATE INDEX IF NOT EXISTS idx_user_archival
ON user_info(status, modified_date, is_archived);

CREATE INDEX IF NOT EXISTS idx_user_archival_eligible
ON user_info(is_archived, status, modified_date)
WHERE is_archived = FALSE;

-- Restaurant data archival indexes
CREATE INDEX IF NOT EXISTS idx_restaurant_archival
ON restaurant_info(status, modified_date, is_archived);

CREATE INDEX IF NOT EXISTS idx_restaurant_archival_eligible
ON restaurant_info(is_archived, status, modified_date)
WHERE is_archived = FALSE;

-- Composite indexes for archival statistics queries
CREATE INDEX IF NOT EXISTS idx_plate_pickup_stats
ON plate_pickup_live(is_archived, created_date);

CREATE INDEX IF NOT EXISTS idx_restaurant_transaction_stats  
ON restaurant_transaction(is_archived, created_date);

CREATE INDEX IF NOT EXISTS idx_client_transaction_stats
ON client_transaction(is_archived, created_date);

-- Performance note: These indexes will speed up:
-- 1. Finding records eligible for archival
-- 2. Archival validation queries  
-- 3. Statistics generation
-- 4. Dashboard queries 