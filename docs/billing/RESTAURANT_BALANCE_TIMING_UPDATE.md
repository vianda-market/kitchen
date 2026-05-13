# Restaurant Balance Timing Update

## 🎯 Business Logic Change

**Updated the restaurant balance system to ensure restaurants only get paid when customers actually show up, not when orders are placed.**

## 📋 Updated Flow

### ❌ OLD Flow (Immediate Payment)
1. Customer places order → **Restaurant balance updated immediately**
2. Customer scans QR → Status update only
3. Customer completes pickup → Final adjustments
4. **Problem:** Restaurant gets paid even if customer doesn't show up

### ✅ NEW Flow (Pay-on-Arrival)
1. **Customer places order** → Transaction created, **NO balance update**
2. **Customer scans QR (arrives)** → **Restaurant balance updated with FULL amount**
3. **Customer completes pickup** → Final status updates
4. **End of kitchen_day** → No-show orders get **discounted amount**

## 🏗️ Technical Implementation

### Updated Methods

#### 1. Order Placement (`vianda_selection.py`)
```python
# OLD: RestaurantTransaction.create_with_balance_update(data)
# NEW: RestaurantTransaction.create(data)  # No immediate balance update
```

#### 2. QR Scan - Customer Arrival (`vianda_pickup.py`)
```python
# NEW: Update balance when customer actually shows up
RestaurantTransaction.update_balance_on_arrival(
    transaction_id, arrival_time, user_id
)
```

#### 3. No-Show Processing (End of Day)
```python
# NEW: Handle customers who never arrived
RestaurantTransaction.process_no_show_balance_update(
    transaction_id, system_user_id
)
```

## 💰 Financial Impact Examples

### Scenario 1: Customer Shows Up
```
Order: 10 credits × $3.00 = $30.00
1. Order placed → Restaurant balance: $0 (no update yet)
2. Customer arrives (QR scan) → Restaurant balance: +$30.00 ✅
3. Customer completes → Restaurant keeps: $30.00
```

### Scenario 2: Customer No-Show (20% discount)
```
Order: 10 credits × $3.00 = $30.00
1. Order placed → Restaurant balance: $0 (no update yet)
2. Customer never arrives → End of day processing
3. No-show discount applied → Restaurant gets: $24.00 (80% of $30.00)
```

### Scenario 3: Customer Arrives but Doesn't Complete
```
Order: 10 credits × $3.00 = $30.00
1. Order placed → Restaurant balance: $0
2. Customer arrives (QR scan) → Restaurant balance: +$30.00 ✅
3. Customer leaves without pickup → Restaurant still keeps: $30.00
   (They showed up, so restaurant gets full payment)
```

## 🔧 Code Changes Made

### Files Modified:

1. **`app/models/restaurant_transaction.py`**
   - ✅ Removed `create_with_balance_update()` 
   - ✅ Added `update_balance_on_arrival()`
   - ✅ Added `process_no_show_balance_update()`

2. **`app/routes/vianda_selection.py`**
   - ✅ Changed to use `RestaurantTransaction.create()` (no balance update)

3. **`app/routes/vianda_pickup.py`** 
   - ✅ Added balance update on QR scan (customer arrival)

4. **`app/tests/models/test_restaurant_balance.py`**
   - ✅ Updated test to verify new timing logic
   - ✅ Added test for pickup flow timing

5. **`RESTAURANT_BALANCE_SYSTEM.md`**
   - ✅ Updated documentation with new flow

## 🎯 Business Benefits

### For Restaurants:
- ✅ **Fair payment model** - only get paid when customers actually show up
- ✅ **Automatic discount handling** for no-shows (configurable percentage)
- ✅ **Reduced risk** of lost revenue from customer no-shows
- ✅ **Accurate financial tracking** based on actual customer behavior

### For Platform:
- ✅ **Better customer accountability** - encourages actual pickup
- ✅ **Reduced disputes** between restaurants and platform
- ✅ **Configurable discount rates** for different restaurant agreements
- ✅ **Automated processing** at end of kitchen day

## 🔄 Processing Timeline

### During Kitchen Day:
1. **Orders placed** → Transactions created (status: "Pending")
2. **Customers arrive** → QR scans trigger balance updates (status: "Arrived")
3. **Customers complete** → Pickup completion (status: "Complete")

### End of Kitchen Day:
4. **No-show processing** → Automated job processes all remaining "Pending" orders
   - Applies configured discount rate
   - Updates restaurant balance with reduced amount
   - Changes status to "No-Show"

## 🚀 Production Ready

All tests pass and the system is ready for production with the new timing logic. The implementation ensures:

- ✅ **Restaurants get paid fairly** based on customer behavior
- ✅ **No-show discounts** are automatically applied
- ✅ **Full audit trail** of all payment decisions
- ✅ **Configurable discount rates** per restaurant/vianda
- ✅ **Automatic end-of-day processing** for pending orders

The restaurant balance system now provides a **fair and automated** payment model that protects restaurants while encouraging customer accountability. 