# Trigger Fix for Market-Based Subscriptions

**Date**: 2026-02-04  
**Issue**: Triggers not updated for new schema columns

---

## 🐛 **Problem**

Database rebuild failed with:
```
ERROR:  null value in column "market_id" of relation "plan_history" violates not-null constraint
```

**Root Cause**: History triggers for `plan_info` and `subscription_info` were not updated to include new columns added in Phase 1.

---

## ✅ **Fix Applied**

### 1. Updated `plan_history_trigger_func()`
**File**: `app/db/trigger.sql`

**Added Column**:
- `market_id` - Now included in INSERT to `plan_history`

### 2. Updated `subscription_history_trigger_func()`
**File**: `app/db/trigger.sql`

**Added Columns**:
- `market_id` - Market reference
- `subscription_status` - Hold status tracking
- `hold_start_date` - When subscription was paused
- `hold_end_date` - When to resume

---

## 🔄 **Ready to Rebuild**

The triggers are now aligned with the new schema. Run:

```bash
./app/db/build_kitchen_db_dev.sh
```

**Expected**: Database should rebuild successfully with all market data seeded.

---

**Fixed By**: AI Assistant  
**Status**: ✅ Complete
