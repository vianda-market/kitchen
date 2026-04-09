-- Archival Performance Indexes
-- These indexes optimize queries for the archival system

-- Orders (customer.plate_pickup_live) archival indexes
CREATE INDEX IF NOT EXISTS idx_plate_pickup_archival 
ON customer.plate_pickup_live(status, completion_time, is_archived) 
WHERE completion_time IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_plate_pickup_archival_eligible 
ON customer.plate_pickup_live(is_archived, status, completion_time) 
WHERE is_archived = FALSE AND status = 'completed';

-- Transactions (billing.restaurant_transaction) archival indexes  
CREATE INDEX IF NOT EXISTS idx_restaurant_transaction_archival
ON billing.restaurant_transaction(status, completion_time, is_archived)
WHERE completion_time IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_restaurant_transaction_archival_eligible
ON billing.restaurant_transaction(is_archived, status, completion_time)
WHERE is_archived = FALSE AND status = 'completed';

-- Client transactions archival indexes
CREATE INDEX IF NOT EXISTS idx_client_transaction_archival
ON billing.client_transaction(status, created_date, is_archived);

CREATE INDEX IF NOT EXISTS idx_client_transaction_archival_eligible
ON billing.client_transaction(is_archived, status, created_date)
WHERE is_archived = FALSE;

-- Subscriptions archival indexes
CREATE INDEX IF NOT EXISTS idx_subscription_archival
ON customer.subscription_info(status, modified_date, is_archived);

CREATE INDEX IF NOT EXISTS idx_subscription_archival_eligible
ON customer.subscription_info(is_archived, status, modified_date)
WHERE is_archived = FALSE;

-- User data archival indexes
CREATE INDEX IF NOT EXISTS idx_user_archival
ON core.user_info(status, modified_date, is_archived);

CREATE INDEX IF NOT EXISTS idx_user_archival_eligible
ON core.user_info(is_archived, status, modified_date)
WHERE is_archived = FALSE;

-- Restaurant data archival indexes
CREATE INDEX IF NOT EXISTS idx_restaurant_archival
ON ops.restaurant_info(status, modified_date, is_archived);

CREATE INDEX IF NOT EXISTS idx_restaurant_archival_eligible
ON ops.restaurant_info(is_archived, status, modified_date)
WHERE is_archived = FALSE;

-- Composite indexes for archival statistics queries
CREATE INDEX IF NOT EXISTS idx_plate_pickup_stats
ON customer.plate_pickup_live(is_archived, created_date);

CREATE INDEX IF NOT EXISTS idx_restaurant_transaction_stats  
ON billing.restaurant_transaction(is_archived, created_date);

CREATE INDEX IF NOT EXISTS idx_client_transaction_stats
ON billing.client_transaction(is_archived, created_date);

-- Performance note: These indexes will speed up:
-- 1. Finding records eligible for archival
-- 2. Archival validation queries  
-- 3. Statistics generation
-- 4. Dashboard queries 