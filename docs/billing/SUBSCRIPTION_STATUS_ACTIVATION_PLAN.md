# Subscription Status Activation Plan

## Problem Statement

Subscriptions remain in `Pending` status even after credits are added through:
1. **Payment processing** - When customers pay and credits are loaded
2. **Discretionary credits** - When customers receive discretionary credits

Subscriptions should automatically transition from `Pending` → `Active` when:
- Balance becomes > 0 (from payment or discretionary credit)
- This allows customers to make vianda reservations

## Current State Analysis

### ✅ Assumptions Verified

1. **Subscription starts as `Pending`**: ✅ Confirmed - Default status in schema
2. **Balance = 0 prevents vianda reservations**: ✅ Confirmed - Credit validation checks balance
3. **Only credit additions possible when balance = 0**: ✅ Confirmed - Deductions require positive balance
4. **Transactions for subscriptions with balance 0 are credit additions**: ✅ Confirmed

### Current Credit Addition Flows

#### 1. Payment Processing Flow
**Location**: `app/routes/payment_methods/client_payment_attempt.py::process_successful_payment()`

**Current Behavior**:
- Updates subscription `balance` ✅
- Updates `renewal_date` ✅
- **Does NOT check/update `status`** ❌

**Code Path**:
```python
subscription_service.update(subscription.subscription_id, {
    "balance": new_balance,
    "renewal_date": new_renewal_date
}, db)
# Missing: status check/update
```

#### 2. Bill Processing Flow
**Location**: `app/services/billing.py::process_completed_bill()`

**Current Behavior**:
- Updates subscription `balance` ✅
- Updates `renewal_date` ✅
- **Has status check logic** ✅ (lines 38-46)
- **BUT**: This function may not be called in all payment flows

**Existing Logic** (lines 38-46):
```python
updated_sub = subscription_service.get_by_id(bill.subscription_id, db)
if hasattr(updated_sub, "balance") and hasattr(updated_sub, "status"):
    try:
        balance = float(updated_sub.balance)
        if balance > 0 and updated_sub.status == "Pending":
            subscription_service.update(bill.subscription_id, {"status": "Active"}, db)
            log_info(f"Subscription {bill.subscription_id} status changed from Pending to Active due to positive balance.")
    except Exception as e:
        log_warning(f"Error checking/updating subscription status: {e}")
```

**Issue**: This logic exists but:
- Requires an extra `get_by_id` call (performance overhead)
- May not be called in all payment processing paths
- Has error handling that silently fails

#### 3. Discretionary Credit Flow
**Location**: `app/services/credit_loading_service.py::create_client_credit_transaction()`

**Current Behavior**:
- Creates `client_transaction` record ✅
- **Comment says "Balance updates are handled automatically"** ⚠️
- **BUT**: No evidence of automatic balance update in code
- **Does NOT check/update subscription `status`** ❌

**Code Path**:
```python
client_transaction = client_transaction_service.create(transaction_data, db)
# No balance update visible
# No status check/update
```

**Investigation Needed**: Verify if `client_transaction` creation triggers balance update via:
- Database trigger (not found in trigger.sql)
- Service method hook (not found in CRUDService)
- Manual call elsewhere (needs verification)

#### 4. Balance Update Function
**Location**: `app/services/crud_service.py::update_balance()`

**Current Behavior**:
- Updates `subscription_info.balance` ✅
- Updates `modified_date` ✅
- **Does NOT check/update `status`** ❌

**Code**:
```python
def update_balance(subscription_id: UUID, balance_change: float, db: psycopg2.extensions.connection) -> bool:
    UPDATE subscription_info 
    SET balance = balance + %s, 
        modified_date = CURRENT_TIMESTAMP
    WHERE subscription_id = %s AND is_archived = FALSE
```

## Performance Considerations

### ❌ Avoid: Checking Status on Every Transaction

**Problem**: If we check subscription status on every transaction (including deductions), we add:
- Extra database queries (fetch subscription, check status, update if needed)
- Compute overhead on high-frequency operations (vianda selections = deductions)
- Unnecessary work for transactions that don't change status

**Impact**: 
- Vianda selections happen frequently (deductions)
- Status only needs to change once (first credit addition)
- Checking on every transaction = wasted compute

### ✅ Preferred: Check Status Only on Credit Additions

**Rationale**:
- Credit additions are infrequent (payments, discretionary credits)
- Status only changes from `Pending` → `Active` (one-time transition)
- Deductions never activate subscriptions (balance goes down, not up)
- Only need to check when balance increases

## Implementation Options

### Option 1: Database Trigger (Recommended for Performance)

**Approach**: Create a PostgreSQL trigger on `subscription_info` that automatically updates status when balance transitions from 0/negative to positive.

**Pros**:
- ✅ **Zero application overhead** - Database handles it atomically
- ✅ **Always consistent** - No code paths can miss it
- ✅ **Performance** - No extra queries, happens in same transaction
- ✅ **Simple** - One trigger function, works for all credit addition paths
- ✅ **Atomic** - Status update happens in same transaction as balance update

**Cons**:
- ⚠️ Requires database migration
- ⚠️ Business logic in database (some teams prefer application layer)

**Implementation**:
```sql
CREATE OR REPLACE FUNCTION subscription_status_activation_trigger()
RETURNS TRIGGER AS $$
BEGIN
    -- Only activate if transitioning from Pending to positive balance
    IF OLD.status = 'Pending' AND NEW.balance > 0 AND OLD.balance <= 0 THEN
        NEW.status := 'Active';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER subscription_status_activation
BEFORE UPDATE ON subscription_info
FOR EACH ROW
WHEN (OLD.status = 'Pending' AND NEW.balance > 0 AND OLD.balance <= 0)
EXECUTE FUNCTION subscription_status_activation_trigger();
```

**Trigger Logic**:
- Only fires when: `status = 'Pending'` AND `balance` transitions from `<= 0` to `> 0`
- Automatically sets `status = 'Active'`
- No performance impact on:
  - Deductions (balance goes down, trigger doesn't fire)
  - Already-active subscriptions (status != 'Pending', trigger doesn't fire)
  - Balance updates that don't cross the 0 threshold

### Option 2: Enhanced `update_balance()` Function

**Approach**: Modify `update_balance()` to check and update status when balance becomes positive.

**Pros**:
- ✅ Centralized logic - All balance updates go through this function
- ✅ Application-level control - Business logic in code
- ✅ Easy to test and debug

**Cons**:
- ⚠️ Requires checking subscription status on every balance update (including deductions)
- ⚠️ Extra database query to fetch current subscription state
- ⚠️ Performance overhead on high-frequency operations (vianda selections)

**Implementation**:
```python
def update_balance(subscription_id: UUID, balance_change: float, db: psycopg2.extensions.connection) -> bool:
    """Update subscription balance and activate if transitioning from Pending to positive balance"""
    with db.cursor() as cursor:
        # Use single UPDATE with conditional status change
        cursor.execute("""
            UPDATE subscription_info 
            SET balance = balance + %s,
                status = CASE 
                    WHEN status = 'Pending' AND (balance + %s) > 0 AND balance <= 0 
                    THEN 'Active' 
                    ELSE status 
                END,
                modified_date = CURRENT_TIMESTAMP
            WHERE subscription_id = %s AND is_archived = FALSE
        """, (balance_change, balance_change, str(subscription_id)))
        db.commit()
        return cursor.rowcount > 0
```

**Performance Impact**:
- Still requires checking status on every call (including deductions)
- But uses single SQL statement (no extra query)
- Conditional logic in SQL is fast

### Option 3: Separate Activation Function (Hybrid)

**Approach**: Create a dedicated `activate_subscription_if_pending()` function, call it only from credit addition paths.

**Pros**:
- ✅ Explicit control - Only called where needed
- ✅ No overhead on deductions
- ✅ Clear intent in code

**Cons**:
- ⚠️ Requires remembering to call it in all credit addition paths
- ⚠️ Easy to miss a code path (maintenance burden)
- ⚠️ Still requires extra query to check status

**Implementation**:
```python
def activate_subscription_if_pending(subscription_id: UUID, db: psycopg2.extensions.connection) -> bool:
    """Activate subscription if it's Pending and balance > 0"""
    with db.cursor() as cursor:
        cursor.execute("""
            UPDATE subscription_info 
            SET status = 'Active',
                modified_date = CURRENT_TIMESTAMP
            WHERE subscription_id = %s 
            AND status = 'Pending' 
            AND balance > 0
            AND is_archived = FALSE
        """, (str(subscription_id),))
        db.commit()
        return cursor.rowcount > 0
```

**Usage Points**:
- `process_successful_payment()` - After balance update
- `process_completed_bill()` - After balance update (replace existing logic)
- `create_client_credit_transaction()` - After transaction creation (if balance update happens)

## Recommended Solution: Option 1 (Database Trigger)

### Why Database Trigger is Best

1. **Performance**: 
   - Zero application overhead
   - No extra queries
   - Happens atomically with balance update
   - Only fires when conditions are met (Pending + balance transition)

2. **Reliability**:
   - Cannot be missed - triggers on every balance update
   - Works for all code paths automatically
   - No maintenance burden - one implementation

3. **Consistency**:
   - Status always matches balance state
   - No race conditions
   - Atomic operation

4. **Future-Proof**:
   - Any new code path that updates balance automatically gets status activation
   - No need to remember to call activation function

### Implementation Plan

#### Phase 1: Database Trigger (Primary Solution)

1. **Create trigger function** in `app/db/trigger.sql`:
   - Function: `subscription_status_activation_trigger()`
   - Logic: Check if `status = 'Pending'` AND `balance` transitions from `<= 0` to `> 0`
   - Action: Set `status = 'Active'`

2. **Create trigger** on `subscription_info`:
   - Trigger: `BEFORE UPDATE`
   - Condition: Only fires when status is Pending and balance crosses 0 threshold
   - Execution: Automatic on every balance update

3. **Test scenarios**:
   - Payment processing → balance 0 → positive → status Active
   - Discretionary credit → balance 0 → positive → status Active
   - Vianda selection (deduction) → balance positive → negative → status stays Active (no change)
   - Already Active subscription → balance update → status stays Active

#### Phase 2: Clean Up Existing Logic (Optional)

1. **Remove redundant status check** from `process_completed_bill()`:
   - Trigger handles it automatically
   - Remove lines 36-46 (extra get_by_id + status update)

2. **Verify discretionary credit flow**:
   - Ensure `create_client_credit_transaction()` actually updates balance
   - If not, add balance update call
   - Trigger will handle status activation automatically

#### Phase 3: Verification

1. **Test all credit addition paths**:
   - Payment processing
   - Discretionary credits
   - Any other credit addition mechanisms

2. **Verify performance**:
   - No performance degradation on vianda selections (deductions)
   - Trigger only fires when conditions are met

3. **Monitor logs**:
   - Verify status changes are happening
   - Check for any unexpected behavior

## Alternative: Option 2 (If Database Triggers Are Not Preferred)

If database triggers are not acceptable, use **Option 2** (Enhanced `update_balance()` function):

### Implementation Steps

1. **Modify `update_balance()`** in `app/services/crud_service.py`:
   - Add conditional status update in SQL
   - Single UPDATE statement with CASE logic
   - No extra queries needed

2. **Update all call sites**:
   - Verify all balance updates go through `update_balance()`
   - If any direct updates exist, route them through `update_balance()`

3. **Test and verify**:
   - All credit addition paths activate subscriptions
   - No performance issues on deductions

## Code Paths to Update (If Not Using Trigger)

If using Option 2 or 3, update these locations:

1. ✅ `app/routes/payment_methods/client_payment_attempt.py::process_successful_payment()`
   - Add status activation after balance update (line 103-106)

2. ✅ `app/services/billing.py::process_completed_bill()`
   - Replace existing status check (lines 36-46) with call to activation function
   - Or rely on enhanced `update_balance()` if using Option 2

3. ⚠️ `app/services/credit_loading_service.py::create_client_credit_transaction()`
   - **First verify**: Does this actually update subscription balance?
   - If yes: Add status activation call
   - If no: Add balance update + status activation

4. ✅ `app/services/vianda_selection_service.py::_create_client_transaction_and_update_balance()`
   - **No change needed** - This is for deductions (balance goes down)
   - Deductions should NOT activate subscriptions

## Edge Cases to Consider

1. **Partial credits**: Discretionary credits can be partial (e.g., 5.5 credits)
   - Trigger/function should handle decimal balances correctly
   - Activation should happen when balance > 0 (even if 0.1)

2. **Concurrent updates**: Multiple credit additions happening simultaneously
   - Database trigger handles this atomically
   - Application-level solution needs transaction handling

3. **Status transitions**: What if subscription is manually set to other statuses?
   - Trigger should only activate from `Pending` → `Active`
   - Other statuses (e.g., `Cancelled`, `Suspended`) should not be auto-activated

4. **Balance going negative**: What if balance goes below 0?
   - Should NOT deactivate subscription (status stays `Active`)
   - Only activation happens automatically, not deactivation

## Testing Strategy

### Unit Tests
- Test trigger/function with various balance transitions
- Test that deductions don't trigger activation
- Test that already-active subscriptions aren't affected

### Integration Tests
- Payment processing → verify status activation
- Discretionary credit → verify status activation
- Vianda selection (deduction) → verify status unchanged

### Performance Tests
- Measure overhead on high-frequency operations (vianda selections)
- Verify trigger/function doesn't impact transaction performance

## Migration Strategy

1. **Development**: Implement trigger/function
2. **Testing**: Verify all scenarios work correctly
3. **Staging**: Test with real data patterns
4. **Production**: Deploy trigger (no data migration needed)
5. **Cleanup**: Remove redundant status check logic from `process_completed_bill()` if using trigger

## Summary

**Recommended Approach**: **Option 1 (Database Trigger)**

**Rationale**:
- Best performance (zero application overhead)
- Most reliable (cannot be missed)
- Simplest maintenance (one implementation)
- Future-proof (works for all code paths)

**Key Benefits**:
- ✅ No performance impact on deductions
- ✅ Automatic activation on all credit addition paths
- ✅ Atomic operation (no race conditions)
- ✅ No code changes needed in multiple places

**Implementation Complexity**: Low
- Single trigger function
- Well-defined conditions
- Easy to test and verify

---

*Last Updated: 2025-11-17*

