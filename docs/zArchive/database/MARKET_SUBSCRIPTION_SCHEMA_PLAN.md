# Market-Based Subscription Schema Plan

**Date**: 2026-02-04  
**Status**: 🚧 In Progress

---

## 🎯 **Business Requirements**

### User Stories
1. **Multi-Market Subscriptions**: Users can subscribe to multiple markets (e.g., Argentina + Peru)
2. **Market = Currency**: Each market is defined by its currency (ARS, PEN, USD, etc.)
3. **Subscription Hold**: Users can put subscriptions on hold (no billing, no plate selection)
4. **Independent Management**: Each market subscription is independent (can pause one, keep another active)

### Key Concepts
- **Market**: A country/region with its own currency and restaurant ecosystem
- **Subscription per Market**: Users have separate subscriptions for each market
- **Hold Status**: New subscription status to pause billing and plate selection

---

## 📊 **Current Schema Analysis**

### Existing Tables
```
credit_currency_info (currency_code, country)
  ↓
plan_info (credit_currency_id, name, price)
  ↓
subscription_info (user_id, plan_id, status)
```

### Issues with Current Design
1. ❌ No explicit market concept
2. ❌ No way to distinguish between markets
3. ❌ No subscription hold status
4. ❌ Currency is indirect (through plan → credit_currency)

---

## 🏗️ **Proposed Schema Changes**

### 1. Create `market_info` Table

```sql
CREATE TABLE market_info (
    market_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_name VARCHAR(100) NOT NULL UNIQUE,  -- 'Argentina', 'Peru', 'Chile'
    country_code VARCHAR(3) NOT NULL UNIQUE,     -- 'ARG', 'PER', 'CHL' (ISO 3166-1 alpha-3)
    currency_code VARCHAR(10) NOT NULL,          -- 'ARS', 'PEN', 'CLP'
    timezone VARCHAR(50) NOT NULL,               -- 'America/Argentina/Buenos_Aires'
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);

CREATE TABLE market_history (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    market_id UUID NOT NULL,
    country_name VARCHAR(100) NOT NULL,
    country_code VARCHAR(3) NOT NULL,
    currency_code VARCHAR(10) NOT NULL,
    timezone VARCHAR(50) NOT NULL,
    is_archived BOOLEAN NOT NULL,
    status status_enum NOT NULL,
    created_date TIMESTAMPTZ NOT NULL,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,
    valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (market_id) REFERENCES market_info(market_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);
```

**Rationale:**
- Central place to define markets
- Links currency to country
- Supports future expansion (timezone for billing cycles, etc.)
- Allows market-level configuration (active/inactive)

---

### 2. Add `subscription_status_enum` with Hold

```sql
CREATE TYPE subscription_status_enum AS ENUM (
    'Active',       -- User can select plates, billing active
    'On Hold',      -- User CANNOT select plates, billing PAUSED
    'Pending',      -- Awaiting payment/activation
    'Expired',      -- Renewal date passed, needs payment
    'Cancelled',    -- User cancelled subscription
    'Suspended'     -- Admin suspended (e.g., fraud)
);
```

**Rationale:**
- Explicit "On Hold" status for user-initiated pause
- Clear distinction from system-level suspension
- Enables business logic for hold periods

---

### 3. Update `subscription_info` Table

```sql
ALTER TABLE subscription_info ADD COLUMN market_id UUID;
ALTER TABLE subscription_info ADD COLUMN hold_start_date TIMESTAMPTZ;
ALTER TABLE subscription_info ADD COLUMN hold_end_date TIMESTAMPTZ;
ALTER TABLE subscription_info ADD CONSTRAINT fk_market 
    FOREIGN KEY (market_id) REFERENCES market_info(market_id) ON DELETE RESTRICT;

-- Add unique constraint: one active subscription per user per market
CREATE UNIQUE INDEX idx_user_market_active 
    ON subscription_info(user_id, market_id) 
    WHERE is_archived = FALSE;
```

**New Columns:**
- `market_id`: Links subscription to a specific market
- `hold_start_date`: When user put subscription on hold
- `hold_end_date`: When subscription will resume (nullable for indefinite hold)

**Business Rules:**
- User can have multiple subscriptions (one per market)
- Only one active subscription per market per user
- Hold dates track pause period for billing adjustments

---

### 4. Update `plan_info` to Reference Market

```sql
ALTER TABLE plan_info ADD COLUMN market_id UUID;
ALTER TABLE plan_info ADD CONSTRAINT fk_plan_market 
    FOREIGN KEY (market_id) REFERENCES market_info(market_id) ON DELETE RESTRICT;
```

**Rationale:**
- Plans are market-specific (Argentina plans, Peru plans)
- Simplifies querying plans by market
- Maintains backward compatibility (plan still has credit_currency_id)

---

### 5. Update `credit_currency_info` to Reference Market (Optional)

```sql
ALTER TABLE credit_currency_info ADD COLUMN market_id UUID;
ALTER TABLE credit_currency_info ADD CONSTRAINT fk_currency_market 
    FOREIGN KEY (market_id) REFERENCES market_info(market_id) ON DELETE RESTRICT;
```

**Rationale:**
- Explicit link between currency and market
- Prevents currency/market mismatches
- Optional: Can be added later if needed

---

## 🔄 **Data Migration Strategy**

### Step 1: Create market_info and Seed Initial Markets

```sql
-- Insert initial markets
INSERT INTO market_info (market_id, country_name, country_code, currency_code, timezone, modified_by)
VALUES 
    (uuid_generate_v4(), 'Argentina', 'ARG', 'ARS', 'America/Argentina/Buenos_Aires', (SELECT user_id FROM user_info WHERE role_name = 'Super Admin' LIMIT 1)),
    (uuid_generate_v4(), 'Peru', 'PER', 'PEN', 'America/Lima', (SELECT user_id FROM user_info WHERE role_name = 'Super Admin' LIMIT 1)),
    (uuid_generate_v4(), 'Chile', 'CHL', 'CLP', 'America/Santiago', (SELECT user_id FROM user_info WHERE role_name = 'Super Admin' LIMIT 1));
```

### Step 2: Update Existing Plans with market_id

```sql
-- Assign market_id to existing plans based on their currency
UPDATE plan_info p
SET market_id = m.market_id
FROM credit_currency_info c
JOIN market_info m ON c.currency_code = m.currency_code
WHERE p.credit_currency_id = c.credit_currency_id;
```

### Step 3: Update Existing Subscriptions with market_id

```sql
-- Assign market_id to existing subscriptions based on their plan's market
UPDATE subscription_info s
SET market_id = pl.market_id
FROM plan_info pl
WHERE s.plan_id = pl.plan_id;
```

### Step 4: Make market_id NOT NULL

```sql
ALTER TABLE subscription_info ALTER COLUMN market_id SET NOT NULL;
ALTER TABLE plan_info ALTER COLUMN market_id SET NOT NULL;
```

---

## 📝 **Updated ERD**

```
market_info (new)
  ├─→ plan_info (updated: + market_id)
  │     └─→ subscription_info (updated: + market_id, + hold_start_date, + hold_end_date)
  └─→ credit_currency_info (optional: + market_id)
```

---

## 🎯 **Business Logic Changes**

### Subscription Creation
```python
# Old: user_id + plan_id
subscription = create_subscription(user_id, plan_id)

# New: user_id + plan_id (market_id derived from plan)
subscription = create_subscription(user_id, plan_id)
# Automatically sets market_id from plan.market_id
```

### Multi-Market Check
```python
# Check if user already has subscription in this market
def can_subscribe_to_market(user_id: UUID, market_id: UUID) -> bool:
    existing = get_active_subscription(user_id, market_id)
    return existing is None
```

### Hold Management
```python
# Put subscription on hold
def hold_subscription(subscription_id: UUID, hold_until: Optional[datetime] = None):
    update_subscription(
        subscription_id,
        status='On Hold',
        hold_start_date=datetime.now(),
        hold_end_date=hold_until
    )

# Check if subscription is on hold
def is_on_hold(subscription: Subscription) -> bool:
    return subscription.status == 'On Hold'

# Resume subscription
def resume_subscription(subscription_id: UUID):
    update_subscription(
        subscription_id,
        status='Active',
        hold_start_date=None,
        hold_end_date=None
    )
```

### Plate Selection Validation
```python
# Block plate selection for held subscriptions
def can_select_plate(user_id: UUID, plate_id: UUID) -> bool:
    plate_market = get_plate_market(plate_id)  # From restaurant's market
    subscription = get_active_subscription(user_id, plate_market)
    
    if not subscription:
        raise Exception("No active subscription in this market")
    
    if subscription.status == 'On Hold':
        raise Exception("Subscription is on hold. Resume to select plates.")
    
    return True
```

### Billing Logic
```python
# Skip billing for held subscriptions
def process_billing():
    for subscription in get_all_subscriptions():
        if subscription.status == 'On Hold':
            continue  # Skip billing
        
        if subscription.renewal_date <= datetime.now():
            charge_subscription(subscription)
```

---

## 🧪 **Testing Requirements**

### Database Tests
- [ ] User can create multiple subscriptions (one per market)
- [ ] User cannot create duplicate subscriptions in same market
- [ ] Hold start/end dates are tracked correctly
- [ ] Market cascades to plans and subscriptions
- [ ] Migration assigns correct market_id to existing data

### Service Tests (Postman)
- [ ] Create subscription in Market A (Argentina)
- [ ] Create subscription in Market B (Peru)
- [ ] Put Market A subscription on hold
- [ ] Verify cannot select plates in Market A
- [ ] Verify can select plates in Market B
- [ ] Resume Market A subscription
- [ ] Verify can select plates in Market A again

---

## 📋 **Implementation Steps**

1. ✅ **Design Schema** (this document)
2. ⏳ **Update schema.sql**
   - Add market_info table
   - Add market_history table
   - Add subscription_status_enum
   - Update subscription_info
   - Update plan_info
   - Add indexes

3. ⏳ **Update seed.sql**
   - Seed initial markets (Argentina, Peru)
   - Update plan seed data with market_id
   - Update subscription seed data with market_id

4. ⏳ **Update Pydantic Schemas**
   - Create MarketSchema
   - Update SubscriptionSchema (+ market_id, hold dates)
   - Update PlanSchema (+ market_id)

5. ⏳ **Update Services**
   - Create market_service.py
   - Update subscription_service.py (hold logic)
   - Update plate_selection_validation (check hold status)
   - Update billing service (skip held subscriptions)

6. ⏳ **Update Routes**
   - Add /api/v1/markets endpoints
   - Add /api/v1/subscriptions/{id}/hold endpoint
   - Add /api/v1/subscriptions/{id}/resume endpoint

7. ⏳ **Rebuild Database**
   ```bash
   ./app/db/build_kitchen_db_dev.sh
   ```

8. ⏳ **Test**
   - Unit tests for new services
   - Postman collection for multi-market flow
   - Postman collection for hold/resume flow

---

## 🚧 **Open Questions**

1. **Hold Duration Limits**: Should there be a max hold period (e.g., 3 months)?
2. **Billing Adjustments**: How to handle partial month when resuming?
3. **Credit Rollover on Hold**: Do credits expire during hold period?
4. **Market Discovery**: Should users see available markets in UI?
5. **Market-Specific Features**: Will some features be market-specific?

---

**Next Step**: Implement changes in `app/db/schema.sql` and `app/db/seed.sql`
