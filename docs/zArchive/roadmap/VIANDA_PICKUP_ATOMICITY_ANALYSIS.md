# Vianda Pickup Scenarios - Atomicity Analysis

## Purpose
Analyze the three main vianda pickup scenarios to identify atomicity opportunities and ensure data consistency.

---

## Scenario Analysis

### Scenario 1: Vianda Selection ✅ (Already Atomic)

**Workflow**: Customer selects a vianda from their office desk

**Current Status**: ✅ **FULLY ATOMIC**

**Operations** (all atomic):
1. Create `vianda_selection` record
2. Create `vianda_pickup_live` record (status: Pending)
3. Create `restaurant_transaction` record (status: Pending, was_collected: false)
4. Create `client_transaction` record (status: Pending)
5. Update subscription balance (deduct credits)

**Atomic Group**: All operations in `create_vianda_selection_with_transactions()`
- All use `commit=False`
- Single `db.commit()` at end
- Rollback on any failure

**Why Not Fully Atomic**: 
- Pickup happens hours later (separate client action)
- Cannot be atomic with selection (time delay)

**Status**: ✅ **COMPLETE** - No further action needed

---

### Scenario 2: Vianda Pickup ✅ (Already Atomic)

**Workflow**: Customer arrives at restaurant and scans QR code, then completes order

**Current Status**: ✅ **FULLY ATOMIC**

**Operations - Arrival** (all atomic):
1. Update `vianda_pickup_live` status → ARRIVED
2. Update `restaurant_transaction` status → ARRIVED, was_collected → true
3. Update `restaurant_balance` (add difference to reach full amount)

**Operations - Completion** (all atomic):
1. Update `vianda_pickup_live` status → COMPLETE
2. Update `restaurant_transaction` status → COMPLETE
3. Mark transaction as collected (via `mark_collected_with_balance_update`)

**Atomic Groups**:
- **Arrival**: `scan_qr_code()` - all operations atomic
- **Completion**: `complete_order()` - all operations atomic

**Why Separate Atomic Groups**:
- Arrival and completion happen at different times (minutes apart)
- Customer scans QR code, then waits for order, then completes
- Cannot be atomic together (time delay between actions)

**Status**: ✅ **COMPLETE** - No further action needed

---

### Scenario 3: Vianda Not Picked Up ⚠️ (Needs Implementation)

**Workflow**: When generating bills, transactions that were not picked up need to be closed

**Current Status**: ⚠️ **NOT IMPLEMENTED** - Missing functionality

**Required Operations** (should be atomic):
1. **Query uncollected transactions** for the billing period
   - `restaurant_transaction` where `was_collected = false` AND `status = Pending`
   - Within `period_start` and `period_end`
   
2. **Close pickup records** (prevent claiming after hours)
   - Update `vianda_pickup_live` records linked to uncollected transactions
   - Set status to appropriate "closed" status (e.g., `EXPIRED`, `NOT_COLLECTED`)
   - Set `is_archived = true` or appropriate flag
   - Prevent customers from claiming after kitchen day closes
   
3. **Close transactions** (move to bill)
   - Update `restaurant_transaction` records
   - Set status to `COMPLETE` or `BILLED` (depending on status enum)
   - Mark as ready for billing
   
4. **Generate bill** (existing logic)
   - Create `institution_bill` record
   - Reset restaurant balance
   - Link transactions to bill (if needed)

**Current Implementation Gap**:
- `create_bill_for_restaurant()` only:
  - Creates bill
  - Resets balance
  - Does NOT close pickup records
  - Does NOT close uncollected transactions

**Why Atomic**:
- All operations represent "closing the kitchen day"
- If bill generation fails, pickup records should not be closed
- If pickup closure fails, bill should not be generated
- Prevents inconsistent state (closed pickups but no bill, or bill but open pickups)

**Implementation Needed**:
```python
def create_bill_for_restaurant_with_closure(
    restaurant_id: UUID,
    period_start: datetime,
    period_end: datetime,
    system_user_id: UUID,
    db: psycopg2.extensions.connection
) -> Optional[InstitutionBillDTO]:
    """
    Create bill and close uncollected transactions atomically.
    
    All operations use commit=False for atomic transaction:
    1. Close uncollected pickup records
    2. Close uncollected transactions
    3. Create bill
    4. Reset balance
    5. Commit all at once
    """
    try:
        # 1. Find uncollected transactions for this restaurant in period
        uncollected_transactions = get_uncollected_transactions(
            restaurant_id, period_start, period_end, db
        )
        
        # 2. Close pickup records (commit=False)
        for transaction in uncollected_transactions:
            close_pickup_record(transaction.vianda_selection_id, db, commit=False)
        
        # 3. Close transactions (commit=False)
        for transaction in uncollected_transactions:
            close_transaction(transaction.transaction_id, db, commit=False)
        
        # 4. Create bill (commit=False)
        bill = create_bill_for_restaurant(...)
        
        # 5. Reset balance (commit=False)
        reset_restaurant_balance(restaurant_id, db, commit=False)
        
        # 6. Commit all operations atomically
        db.commit()
        
        return bill
    except Exception as e:
        db.rollback()
        raise
```

**Status**: ⚠️ **NEEDS IMPLEMENTATION**

---

## Additional Atomicity Opportunities

### Payment Completion + Bill Status Update (Future)

**Workflow**: When payment is registered as successful, update bill status atomically

**Current Status**: ⚠️ **NOT IMPLEMENTED** - Needs investigation

**Required Operations** (should be atomic):
1. Register payment as successful
2. Update bill status to "Paid" or "Completed"
3. Update related records (if any)

**Why Atomic**:
- Payment and bill status must stay in sync
- If payment registration fails, bill should not be marked paid
- If bill update fails, payment should not be registered

**Business Context**:
- Bill generation and payment execution are NOT atomic (intentional time delay)
- Time between bill generation and payment allows:
  - Investigation of bills
  - Connection with bank for transaction verification
- But when payment is registered as successful, bill status update should be atomic

**Implementation Needed**:
```python
def register_payment_success(
    payment_id: UUID,
    bill_id: UUID,
    db: psycopg2.extensions.connection
) -> bool:
    """
    Register payment as successful and update bill status atomically.
    
    All operations use commit=False for atomic transaction:
    1. Update payment status to SUCCESS
    2. Update bill status to PAID/COMPLETED
    3. Commit all at once
    """
    try:
        # 1. Update payment status (commit=False)
        payment_service.update(payment_id, {"status": Status.SUCCESS}, db, commit=False)
        
        # 2. Update bill status (commit=False)
        bill_service.update(bill_id, {"status": Status.PAID}, db, commit=False)
        
        # 3. Commit all operations atomically
        db.commit()
        
        return True
    except Exception as e:
        db.rollback()
        raise
```

**Status**: ⚠️ **NEEDS INVESTIGATION** - Add to roadmap

---

## Summary

### ✅ Complete (No Action Needed)
- **Scenario 1**: Vianda selection - Fully atomic
- **Scenario 2**: Vianda pickup (arrival + completion) - Fully atomic

### ⚠️ Needs Implementation
- **Scenario 3**: Bill generation with transaction/pickup closure - Missing functionality
- **Payment Completion**: Payment + bill status update - Needs investigation

---

## Implementation Plan

### Phase 1: Bill Generation with Closure (Scenario 3)

#### Step 1.1: Create Helper Functions
- `get_uncollected_transactions()` - Query uncollected transactions for period
- `close_pickup_record()` - Close pickup record (status update, archive)
- `close_transaction()` - Close transaction (status update)

#### Step 1.2: Refactor Bill Generation
- Modify `create_bill_for_restaurant()` to include closure logic
- OR create new `create_bill_for_restaurant_with_closure()`
- Use `commit=False` for all operations
- Single `db.commit()` at end

#### Step 1.3: Update Balance Reset
- Modify `reset_restaurant_balance()` to accept `commit` parameter
- Use `commit=False` in bill generation workflow

#### Step 1.4: Testing
- Test bill generation with uncollected transactions
- Test rollback scenarios
- Verify pickup records are closed
- Verify transactions are closed

### Phase 2: Payment Completion (Future)

#### Step 2.1: Investigate Current Payment Flow
- Review payment registration logic
- Review bill status update logic
- Identify where atomicity is needed

#### Step 2.2: Implement Atomic Payment Registration
- Create `register_payment_success()` function
- Update payment status + bill status atomically
- Use `commit=False` for both operations

#### Step 2.3: Testing
- Test payment registration with bill update
- Test rollback scenarios
- Verify data consistency

---

## Files to Modify

### Phase 1: Bill Generation with Closure

1. `app/services/billing/institution_billing.py`
   - Add `get_uncollected_transactions()` helper
   - Add `close_pickup_record()` helper
   - Add `close_transaction()` helper
   - Refactor `create_bill_for_restaurant()` to include closure logic
   - Use `commit=False` for all operations

2. `app/services/crud_service.py`
   - Modify `reset_restaurant_balance()` to accept `commit` parameter

3. `app/services/crud_service.py` (if needed)
   - Add helper functions for closing pickup records and transactions

### Phase 2: Payment Completion (Future)

1. `app/services/billing/` (new or existing)
   - Create `register_payment_success()` function
   - Update payment and bill status atomically

2. `app/services/crud_service.py`
   - Modify payment update methods to accept `commit` parameter (if needed)

---

## Risk Assessment

**Low Risk**:
- Adding closure logic to existing bill generation
- Using existing `commit` parameter pattern

**Medium Risk**:
- Identifying all uncollected transactions correctly
- Ensuring pickup records are properly closed
- Ensuring transactions are properly closed

**Mitigation**:
- Comprehensive testing
- Clear status enum values for closed states
- Logging for audit trail

---

## Status Enum Considerations

**Pickup Record Status**:
- Current: `PENDING`, `ARRIVED`, `COMPLETE`
- Needed: `NOT_COLLECTED` or `EXPIRED` (for uncollected pickups)

**Transaction Status**:
- Current: `PENDING`, `ARRIVED`, `COMPLETE`
- Needed: `BILLED` or use `COMPLETE` with `was_collected=false` flag

**Bill Status**:
- Current: `PENDING`, `COMPLETE`
- Needed: `PAID` (for when payment is registered)

---

## Next Steps

1. **Immediate**: Implement Scenario 3 (bill generation with closure)
2. **Future**: Investigate and implement payment completion atomicity
3. **Documentation**: Update status enum documentation with new states

