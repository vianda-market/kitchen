# Market-Currency Schema Normalization

**Date**: 2026-02-04  
**Status**: 🔍 Proposal - Awaiting Approval

---

## 🎯 **Problem Identified**

There's data duplication between `market_info` and `credit_currency_info` tables:

### **Current Schema (Denormalized)**

```sql
-- credit_currency_info table
CREATE TABLE credit_currency_info (
    credit_currency_id UUID PRIMARY KEY,
    currency_name VARCHAR(20) NOT NULL,        -- "Argentinean Peso"
    currency_code VARCHAR(10) NOT NULL UNIQUE, -- "ARS"
    credit_value NUMERIC NOT NULL,             -- 1.2 (fluctuates)
    -- ... other fields
);

-- market_info table
CREATE TABLE market_info (
    market_id UUID PRIMARY KEY,
    country_name VARCHAR(100) NOT NULL UNIQUE, -- "Argentina"
    country_code VARCHAR(3) NOT NULL UNIQUE,   -- "ARG"
    currency_code VARCHAR(10) NOT NULL,        -- "ARS" ← DUPLICATE!
    timezone VARCHAR(50) NOT NULL,
    -- ... other fields
    -- ❌ NO FOREIGN KEY TO credit_currency_info
);
```

### **Issues**

1. **Data Duplication**: `currency_code` exists in both tables
2. **No Referential Integrity**: No FK between market and currency
3. **Inconsistency Risk**: Currency codes could diverge between tables
4. **Redundant Data**: Currency information is split across tables

---

## ✅ **Proposed Solution: Add Foreign Key**

Replace `market_info.currency_code` with a foreign key to `credit_currency_info`:

### **Normalized Schema**

```sql
-- credit_currency_info remains the same (source of truth for currencies)
CREATE TABLE credit_currency_info (
    credit_currency_id UUID PRIMARY KEY,
    currency_name VARCHAR(20) NOT NULL,        -- "Argentinean Peso"
    currency_code VARCHAR(10) NOT NULL UNIQUE, -- "ARS"
    credit_value NUMERIC NOT NULL,             -- 1.2 (fluctuates)
    -- ... other fields
);

-- market_info now has FK to credit_currency_info
CREATE TABLE market_info (
    market_id UUID PRIMARY KEY,
    country_name VARCHAR(100) NOT NULL UNIQUE,     -- "Argentina"
    country_code VARCHAR(3) NOT NULL UNIQUE,       -- "ARG"
    credit_currency_id UUID NOT NULL,              -- ✅ FK to credit_currency_info
    timezone VARCHAR(50) NOT NULL,
    -- ... other fields
    FOREIGN KEY (credit_currency_id) REFERENCES credit_currency_info(credit_currency_id) ON DELETE RESTRICT
);
```

---

## 📊 **Benefits**

1. **Single Source of Truth**: Currency information lives in `credit_currency_info` only
2. **Referential Integrity**: FK ensures market always references a valid currency
3. **No Duplication**: `currency_code` and `currency_name` stored once
4. **Consistency**: Currency changes automatically reflect in all markets
5. **Easier Maintenance**: Update currency once, affects all markets
6. **Proper Normalization**: Follows database design best practices

---

## 🔄 **Data Relationships**

```
credit_currency_info (Source of Truth)
    ↓ FK
market_info (References Currency)
    ↓ FK
plan_info (References Both Market & Currency)
    ↓ FK
subscription_info (References Market & Plan)
```

### **Query Example**

```sql
-- Get market with currency details (requires JOIN)
SELECT 
    m.market_id,
    m.country_name,
    m.country_code,
    c.currency_code,    -- From credit_currency_info
    c.currency_name,    -- From credit_currency_info
    c.credit_value,     -- From credit_currency_info
    m.timezone
FROM market_info m
INNER JOIN credit_currency_info c ON m.credit_currency_id = c.credit_currency_id
WHERE m.market_id = '11111111-1111-1111-1111-111111111111';
```

---

## 🛠️ **Implementation Plan**

### **Phase 1: Schema Migration**

1. **Add new column** to `market_info`:
   ```sql
   ALTER TABLE market_info 
   ADD COLUMN credit_currency_id UUID;
   ```

2. **Populate the FK** (migrate existing data):
   ```sql
   -- Match currency_code between tables
   UPDATE market_info m
   SET credit_currency_id = (
       SELECT credit_currency_id 
       FROM credit_currency_info c 
       WHERE c.currency_code = m.currency_code
   );
   ```

3. **Add NOT NULL constraint**:
   ```sql
   ALTER TABLE market_info 
   ALTER COLUMN credit_currency_id SET NOT NULL;
   ```

4. **Add foreign key constraint**:
   ```sql
   ALTER TABLE market_info
   ADD CONSTRAINT fk_market_credit_currency
   FOREIGN KEY (credit_currency_id) 
   REFERENCES credit_currency_info(credit_currency_id) 
   ON DELETE RESTRICT;
   ```

5. **Remove redundant column**:
   ```sql
   ALTER TABLE market_info 
   DROP COLUMN currency_code;
   ```

### **Phase 2: Update History Table**

Update `market_history` to match:
```sql
-- Same steps as above for market_history table
ALTER TABLE market_history ADD COLUMN credit_currency_id UUID;
-- ... (migration steps)
ALTER TABLE market_history DROP COLUMN currency_code;
```

### **Phase 3: Update Triggers**

Update `market_history_trigger_func()` to include `credit_currency_id` in history inserts.

### **Phase 4: Update Application Code**

1. **DTOs** (`app/dto/models.py`):
   ```python
   class MarketDTO(BaseModel):
       market_id: UUID
       country_name: str
       country_code: str
       credit_currency_id: UUID  # ← Changed from currency_code
       timezone: str
       # ... other fields
   ```

2. **Pydantic Schemas** (`app/schemas/consolidated_schemas.py`):
   ```python
   class MarketResponseSchema(BaseModel):
       market_id: UUID
       country_name: str
       country_code: str
       credit_currency_id: UUID  # ← Changed
       currency_code: str        # ← Enriched from JOIN (optional)
       currency_name: str        # ← Enriched from JOIN (optional)
       timezone: str
   ```

3. **Market Service** (`app/services/market_service.py`):
   - Update SQL queries to JOIN `credit_currency_info`
   - Update CREATE to accept `credit_currency_id` instead of `currency_code`
   - Update UPDATE to handle `credit_currency_id`

4. **Seed Data** (`app/db/seed.sql`):
   ```sql
   -- Insert currencies first
   INSERT INTO credit_currency_info (credit_currency_id, currency_code, ...)
   VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'ARS', ...);
   
   -- Then insert markets with FK
   INSERT INTO market_info (market_id, country_name, credit_currency_id, ...)
   VALUES (
       '11111111-1111-1111-1111-111111111111', 
       'Argentina',
       'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',  -- FK to currency
       ...
   );
   ```

### **Phase 5: Update API Layer**

1. **Market Creation** - Accept `credit_currency_id` instead of `currency_code`
2. **Market Response** - Optionally enrich with currency details via JOIN
3. **Postman Collections** - Update to send `credit_currency_id`

---

## 🔒 **Validation Rules**

With the FK in place:
- ✅ Cannot create a market without a valid currency
- ✅ Cannot delete a currency that's used by a market
- ✅ Currency updates automatically affect all markets
- ✅ Data consistency guaranteed by database

---

## 📝 **Migration Checklist**

Following the 6-layer schema change process from `Claude.md`:

- [ ] 1. **Database Schema** - Add FK, remove redundant column
- [ ] 2. **Database Triggers** - Update history trigger
- [ ] 3. **Database Seed** - Update seed data to use FKs
- [ ] 4. **DTOs** - Update `MarketDTO` 
- [ ] 5. **Pydantic Schemas** - Update market schemas
- [ ] 6. **Postman Collection** - Update market creation requests

---

## 🤔 **Trade-offs**

### **Pros**
- ✅ Normalized data (no duplication)
- ✅ Referential integrity
- ✅ Single source of truth
- ✅ Easier to maintain
- ✅ Consistent currency information

### **Cons**
- ⚠️ Requires JOIN to get currency_code (slight performance cost)
- ⚠️ Breaking change (requires data migration)
- ⚠️ All dependent code must be updated

### **Mitigation**
- Create enriched endpoint that JOINs currency info automatically
- Use database views for common queries
- One-time migration script handles data transformation

---

## 🎯 **Recommendation**

**Proceed with normalization** because:
1. Database design best practices favor normalization
2. Referential integrity prevents data inconsistencies
3. Benefits outweigh the small performance cost of JOINs
4. We're in local dev - perfect time for schema changes
5. Aligns with the principle: "Single Source of Truth"

---

## 📊 **Alternative: Keep Current Schema**

If we decide NOT to normalize:

### **Add Constraint Instead**
```sql
-- Ensure currency_code in market matches credit_currency
ALTER TABLE market_info
ADD CONSTRAINT check_currency_exists
CHECK (
    EXISTS (
        SELECT 1 FROM credit_currency_info 
        WHERE currency_code = market_info.currency_code
    )
);
```

**Pros**: No breaking changes, no migration needed  
**Cons**: Still have duplication, no referential integrity, constraint only validates at insert

---

**Status**: Awaiting user approval to proceed with normalization

**Estimated Effort**: 2-3 hours (schema + code + testing)
