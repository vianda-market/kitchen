# Phase 1: Market-Based Subscription Implementation

**Date**: 2026-02-04  
**Status**: 🚧 Implementing

---

## 🎯 Implementation Decision

After analyzing the schema, we'll add a **subscription_status column** to `subscription_info` instead of changing the global `status_enum`. This allows:
- ✅ Subscription-specific statuses without affecting other tables
- ✅ Backward compatibility with existing status_enum usage
- ✅ Clearer intent (subscription status vs. general status)

---

## 📋 Implementation Plan

### Step 1: Add Market Table ✅
Create `market_info` table for currency-based markets.

### Step 2: Update Subscription Schema ✅
Add `market_id` and subscription-specific status column.

### Step 3: Update Plan Schema ✅
Link plans to markets.

### Step 4: Seed Market Data ✅
Add initial markets (Argentina, Peru).

### Step 5: Update Seed Data ⏳
Link existing plans/subscriptions to markets.

---

## 🔑 Key Design Decisions

###Decision 1: Subscription Status Column
**Approach**: Add `subscription_status VARCHAR(20)` instead of creating new enum
**Rationale**:
- Flexible (can add new statuses without ALTER TYPE)
- Clear intent (separate from general status_enum)
- Easier to query and debug

**Status Values**:
- `'Active'` - User can select plates, billing active
- `'On Hold'` - User CANNOT select plates, billing PAUSED
- `'Pending'` - Awaiting payment/activation
- `'Expired'` - Renewal date passed
- `'Cancelled'` - User cancelled

### Decision 2: Market Identification
**Approach**: Use `country_code` (ISO 3166-1 alpha-3) as business key
**Rationale**:
- Standard international format
- Unique and recognizable
- Good for APIs and external integrations

### Decision 3: Hold Date Tracking
**Approach**: Add `hold_start_date` and `hold_end_date`
**Rationale**:
- Track hold period for billing adjustments
- `hold_end_date` NULL = indefinite hold
- Enables automated resume on specific date

---

## 📝 Schema Changes Summary

### New Tables
- `market_info` - Currency-based markets
- `market_history` - Audit trail for markets

### Modified Tables
- `subscription_info` - Add `market_id`, `subscription_status`, hold dates
- `plan_info` - Add `market_id`

### New Indexes
- `idx_user_market_active` - Enforce one subscription per user per market
- `idx_subscription_market` - Fast market-based queries
- `idx_plan_market` - Fast plan queries by market

---

Continuing implementation in `schema.sql`...
