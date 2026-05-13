# Atomic Transaction Use Cases Analysis

## Purpose
Analyze whether `commit=False` parameter for `db_insert()` and `db_update()` is a one-off need or a common pattern that will recur.

---

## Current Atomic Transaction Patterns in Codebase

### Pattern 1: Raw SQL with Cursor (Existing)

**Example**: `qr_code_service.py` - `create_qr_code_atomic()`
```python
with db.cursor() as cursor:
    # 1. Insert QR code
    cursor.execute("INSERT INTO qr_code ...")
    # 2. Generate image (external operation)
    # 3. Update QR code with image paths
    cursor.execute("UPDATE qr_code ...")
    # Commit once at end
    db.commit()
```

**Use Case**: 
- Create QR code record
- Generate image file (external operation)
- Update QR code with image paths
- **All must succeed or all fail**

**Why Atomic**: If image generation fails, QR code record should not exist.

---

### Pattern 2: Multi-Operation via CRUD Service (Current Issue)

**Example**: `create_employer_with_address()` - **CURRENT IMPLEMENTATION**
```python
# 1. address_service.create() → db_insert() → COMMIT ✅
# 2. employer_service.create() → db_insert() → COMMIT ✅
# 3. address_service.update() → db_update() → COMMIT ✅
# 4. user_service.update() → db_update() → COMMIT ❌ (fails)
# Result: Steps 1-3 committed, step 4 failed → INCONSISTENT!
```

**Use Case**:
- Create address
- Create employer (references address)
- Update address (links to employer)
- Update user (assigns employer)
- **All must succeed or all fail**

**Why Atomic**: If user assignment fails, we shouldn't have orphaned employer/address.

---

### Pattern 3: Vianda Selection with Multiple Transactions (Refined)

**Example**: `create_vianda_selection_with_transactions()`
```python
# Creates multiple records in single workflow:
# 1. vianda_selection
# 2. vianda_pickup_live (created with Pending status)
# 3. restaurant_transaction
# 4. client_transaction
# 5. Updates subscription balance
```

**Current Behavior**: Uses CRUD service, each operation commits separately
**Issue**: If step 5 fails, steps 1-4 are already committed → inconsistent state

**Why Atomic**: All records represent the initial effects of vianda selection (single API call).
**NOT Atomic**: Vianda pickup happens later (separate client action, hours later).

**Refined Understanding**:
- **Atomic Group 1**: Selection workflow (create selection, pickup record, transactions, balance update)
- **Atomic Group 2**: Pickup workflow (update pickup status, update selection status, update transaction status)
- These are separate atomic groups because they happen at different times (selection vs pickup).

---

### Pattern 4: Restaurant Creation with Balance

**Example**: `create_restaurant()` in `app/routes/restaurant.py`
```python
# Creates:
# 1. restaurant_info
# 2. restaurant_balance (via create_restaurant_balance_record)
```

**Current Behavior**: Need to verify if atomic
**Why Atomic**: Restaurant should always have a balance record (data integrity).

---

## Business Limitations to Atomicity

### When Atomicity is NOT Appropriate

**Key Principle**: Atomicity should only apply to operations that happen in a single, continuous workflow. If there are:
- **Time delays** between operations (hours, days)
- **Human decision points** (approvals, reviews)
- **Batch processing** (end-of-day, scheduled jobs)
- **Separate client actions** (user selects vianda, then picks up later)

Then those operations should NOT be atomic together.

---

## Use Cases for `commit=False` Parameter

### Category 1: Parent-Child Entity Creation ✅

**Pattern**: Create parent entity, then child entity that references parent

**Examples**:
1. **Employer + Address** (current case) ✅
   - Create address → Create employer → Link address to employer → Assign to user
   - **All atomic**: All happen in single API call
   
2. **Restaurant + Balance** ✅
   - Create restaurant → Create restaurant_balance
   - **All atomic**: Balance must exist when restaurant is created
   
3. **Institution + Entity** ✅
   - Create institution → Create institution_entity → Create bank_account
   - **All atomic**: If creating together in single workflow
   
4. **User + Subscription** ✅
   - Create user → Create subscription → Create payment_method
   - **All atomic**: If creating together in single workflow

**Why Atomic**: Child cannot exist without parent. If child creation fails, parent should be rolled back.

---

### Category 2: Multi-Step Business Transactions (Refined)

**Pattern**: Multiple related records represent a single business operation

**Examples**:

1. **Vianda Selection - Initial Effects** ✅
   - **Atomic**: Create vianda_selection → Create restaurant_transaction → Create client_transaction → Update subscription balance
   - **Why Atomic**: All happen when user selects vianda (single API call)
   - **NOT Atomic**: Vianda pickup happens hours later (separate client action)
   
2. **Vianda Pickup - Backend Processing** ✅
   - **Atomic**: Update vianda_pickup_live status → Update vianda_selection status → Update transaction status
   - **Why Atomic**: All happen when user picks up vianda (single API call)
   - **NOT Atomic**: Initial selection (happened hours earlier)
   
3. **Payment Processing** ✅
   - Create payment_attempt → Create client_bill → Update subscription → Create transaction
   - **All atomic**: All happen in single payment processing workflow
   
4. **Discretionary Credit - Request Creation** ✅
   - Create discretionary_request → Create initial status records
   - **Atomic**: If creating request with initial data
   - **NOT Atomic**: Request → Resolution (SuperAdmin decision, time delay)
   
5. **Discretionary Credit - Resolution Processing** ✅
   - Create resolution → Update balances → Create transactions
   - **All atomic**: All happen when SuperAdmin approves/rejects (single workflow)
   - **NOT Atomic**: Request creation (happened earlier, separate workflow)

**Why Atomic**: All records represent one business event in a single continuous workflow. Partial success = data inconsistency.

---

### Category 3: Update Operations with Side Effects (Refined)

**Pattern**: Update multiple related records atomically

**Examples**:

1. **Status Updates with Cascading Effects** ✅
   - Update vianda_selection status → Update vianda_pickup_live status → Update transaction status
   - **All atomic**: All happen in single status update workflow
   
2. **Balance Updates - Transaction Level** ✅
   - Update restaurant_balance → Create restaurant_transaction
   - **All atomic**: Balance and transaction update together for each transaction
   - **NOT Atomic**: Institution bill generation (end-of-day batch process)
   
3. **Balance Updates - Batch Processing** ⚠️
   - Generate institution_bill (end-of-day) → Update institution balances
   - **Separate**: This is a scheduled batch job, not atomic with individual transactions
   - **Note**: Individual transactions update balance atomically, but bill generation is separate
   
4. **User Profile Updates** ✅
   - Update user → Update addresses → Update payment_methods
   - **All atomic**: If updating together in single API call

**Why Atomic**: Related records must stay in sync within a single workflow. Partial updates = inconsistent state.

---

## Assessment: One-Off vs Common Pattern

### Evidence for COMMON PATTERN:

✅ **Multiple Existing Cases**:
1. `create_employer_with_address()` - Current case
2. `create_vianda_selection_with_transactions()` - Already exists, likely has same issue
3. `create_restaurant()` with balance - Likely needs atomicity
4. `create_qr_code_atomic()` - Already uses raw SQL (workaround)

✅ **Business Logic Patterns**:
- Parent-child relationships are common (employer-address, restaurant-balance, user-subscription)
- Multi-step business transactions are common (vianda selection, payment processing)
- Cascading updates are common (status changes, balance updates)

✅ **Data Integrity Requirements**:
- Foreign key constraints require parent before child
- Business rules require related records to exist together
- Partial failures create orphaned records

### Evidence for ONE-OFF:

❌ **Limited Current Examples**:
- Only `qr_code_service` explicitly handles atomicity (uses raw SQL)
- Other services may have the issue but it's not exposed yet

❌ **Most Operations are Single-Entity**:
- Most CRUD operations create/update single records
- Multi-operation cases are the exception, not the rule

---

## Recommendation: **COMMON PATTERN - Add `commit` Parameter**

### Rationale

1. **Multiple Use Cases Identified**: At least 4-5 clear cases where atomic transactions are needed
2. **Pattern Will Recur**: Parent-child and multi-step transactions are common in business logic
3. **Backward Compatible**: Default `commit=True` maintains existing behavior
4. **Explicit Control**: Makes transaction boundaries clear in code
5. **Prevents Future Issues**: Other services likely have the same problem but haven't hit it yet

### Implementation Approach

**Modify `db_insert()` and `db_update()`**:
```python
def db_insert(table: str, data: dict, connection=None, *, commit: bool = True):
    # ... existing code ...
    if commit:
        connection.commit()
    # ... rest of code ...

def db_update(table: str, data: dict, where: dict, connection=None, *, commit: bool = True):
    # ... existing code ...
    if commit:
        connection.commit()
    # ... rest of code ...
```

**Modify CRUD Service**:
```python
def create(self, data: dict, db: psycopg2.extensions.connection, *, commit: bool = True, ...):
    # ... existing code ...
    record_id = db_insert(self.table_name, data, connection=db, commit=commit)
    # ... rest of code ...

def update(self, record_id: UUID, data: dict, db: psycopg2.extensions.connection, *, commit: bool = True, ...):
    # ... existing code ...
    db_update(self.table_name, data, where, connection=db, commit=commit)
    # ... rest of code ...
```

**Usage in Atomic Operations**:
```python
def create_employer_with_address(...):
    # All operations with commit=False
    address = address_service.create(address_data, db, commit=False)
    employer = employer_service.create(employer_data, db, commit=False)
    address_service.update(address.address_id, update_data, db, commit=False)
    user_service.update(user_id, user_data, db, commit=False)
    
    # Commit once at end
    db.commit()
```

---

## Alternative: Raw SQL Pattern (If One-Off)

**If this is truly a one-off**, we could use raw SQL like `qr_code_service`:

**Pros**:
- No changes to utility functions
- Full control
- Pattern already exists

**Cons**:
- More verbose
- Need to handle SQL building manually
- Doesn't solve the problem for other services
- Less reusable

---

## Conclusion

**Recommendation**: **Add `commit` parameter to `db_insert()` and `db_update()`**

**Reasoning**:
1. ✅ Multiple use cases identified (4-5+)
2. ✅ Pattern will recur (parent-child, multi-step transactions)
3. ✅ Backward compatible (default `True`)
4. ✅ Solves problem for current and future cases
5. ✅ Makes transaction boundaries explicit

**Priority**: **HIGH** - This is a data integrity issue affecting multiple operations

---

## Affected Services (Likely Have Same Issue)

1. ✅ `create_employer_with_address()` - **Current case** (4 operations)
2. ⚠️ `create_restaurant()` with balance - **Has issue** (2 operations, balance uses raw SQL but restaurant uses CRUD)
3. ⚠️ `create_vianda_selection_with_transactions()` - **Has issue** (5+ operations)
4. ⚠️ `create_with_conservative_balance_update()` - **Has issue** (create transaction + update balance)
5. ⚠️ Payment processing flows - **Likely has issue**
6. ⚠️ Discretionary credit flows - **Likely has issue**

**Action**: After fixing `create_employer_with_address()`, audit other multi-operation services for same issue.

---

## Why Atomic Transactions Are Needed

### Business Logic Requirements

**Parent-Child Relationships**:
- Employer cannot exist without address (foreign key constraint)
- Restaurant should always have balance record (business rule)
- User subscription requires payment method (business rule)

**Multi-Step Business Transactions** (Refined):
- **Vianda selection (initial)**: selection + pickup record + transactions + balance update (atomic - single API call)
- **Vianda pickup (later)**: update pickup status + update selection status + update transaction status (atomic - single API call)
- **Note**: Selection and pickup are separate atomic groups (hours apart, different client actions)
- **Payment**: attempt + bill + subscription update (atomic - single workflow)
- **Discretionary credit (request)**: request creation + initial records (atomic - single API call)
- **Discretionary credit (resolution)**: resolution + balance updates + transactions (atomic - single workflow)
- **Note**: Request and resolution are separate atomic groups (time delay, SuperAdmin decision)

**Data Consistency**:
- Partial failures create orphaned records
- Foreign key violations if parent fails after child created
- Business rule violations if related records don't exist together

### Real-World Scenarios

**Scenario 1: Employer Creation Failure**
- Address created ✅
- Employer created ✅
- Address linked ✅
- User assignment fails ❌
- **Result**: Employer exists but not assigned → User can't find their employer

**Scenario 2: Restaurant Creation Failure**
- Restaurant created ✅
- Balance creation fails ❌
- **Result**: Restaurant exists but no balance → Can't process transactions

**Scenario 3: Vianda Selection Failure (Initial Workflow)**
- Vianda selection created ✅
- Pickup record created ✅
- Restaurant transaction created ✅
- Client transaction created ✅
- Subscription update fails ❌
- **Result**: Order exists but credits not deducted → User gets free meal
- **Note**: This is the initial selection workflow. Pickup happens later (separate atomic group).

**Scenario 4: Vianda Pickup Failure (Later Workflow)**
- Pickup status updated ✅
- Selection status updated ✅
- Transaction status update fails ❌
- **Result**: Pickup marked complete but transaction still pending → Inconsistent state
- **Note**: This is the pickup workflow, separate from initial selection.

---

## Implementation Impact

### Files to Modify

1. `app/utils/db.py`
   - `db_insert()`: Add `commit: bool = True` parameter
   - `db_update()`: Add `commit: bool = True` parameter

2. `app/services/crud_service.py`
   - `CRUDService.create()`: Add `commit: bool = True` parameter, pass to `db_insert()`
   - `CRUDService.update()`: Add `commit: bool = True` parameter, pass to `db_update()`

3. `app/services/entity_service.py`
   - `create_employer_with_address()`: Use `commit=False` for all operations, commit at end

4. **Future**: Other services can use same pattern

### Backward Compatibility

✅ **100% Backward Compatible**:
- Default `commit=True` maintains existing behavior
- All existing code continues to work
- Only new atomic operations need to specify `commit=False`

### Testing Required

- Verify existing operations still work (commit=True default)
- Test atomic operations with commit=False
- Test rollback scenarios
- Test commit at end of atomic operations

---

## Implementation Plan

### Phase 1: Core Infrastructure Changes

#### Step 1.1: Modify Database Utility Functions
**File**: `app/utils/db.py`

**Changes**:
- Add `commit: bool = True` parameter to `db_insert()`
- Add `commit: bool = True` parameter to `db_update()`
- Conditionally commit based on parameter
- Maintain backward compatibility (default `True`)

**Code**:
```python
def db_insert(table: str, data: dict, connection=None, *, commit: bool = True):
    # ... existing code ...
    if commit:
        connection.commit()
    # ... rest of code ...

def db_update(table: str, data: dict, where: dict, connection=None, *, commit: bool = True):
    # ... existing code ...
    if commit:
        connection.commit()
    # ... rest of code ...
```

**Testing**:
- Verify existing calls still work (default behavior)
- Test with `commit=False` parameter

---

#### Step 1.2: Modify CRUD Service Methods
**File**: `app/services/crud_service.py`

**Changes**:
- Add `commit: bool = True` parameter to `CRUDService.create()`
- Add `commit: bool = True` parameter to `CRUDService.update()`
- Pass `commit` parameter to `db_insert()` and `db_update()`
- Maintain backward compatibility (default `True`)

**Code**:
```python
def create(
    self,
    data: Dict[str, Any],
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    commit: bool = True  # NEW
) -> Optional[T]:
    # ... existing code ...
    record_id = db_insert(self.table_name, data, connection=db, commit=commit)
    # ... rest of code ...

def update(
    self,
    record_id: UUID,
    data: Dict[str, Any],
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    commit: bool = True  # NEW
) -> Optional[T]:
    # ... existing code ...
    db_update(self.table_name, data, where, connection=db, commit=commit)
    # ... rest of code ...
```

**Testing**:
- Verify existing calls still work (default behavior)
- Test with `commit=False` parameter

---

### Phase 2: Refactor Atomic Operations

#### Step 2.1: Employer Creation with Address (Current Case)
**File**: `app/services/entity_service.py`
**Function**: `create_employer_with_address()`

**Current Issue**: 4 operations commit separately
**Solution**: Use `commit=False` for all operations, commit at end

**Changes**:
```python
def create_employer_with_address(...):
    try:
        # All operations with commit=False
        address = address_service.create(address_data, db, scope=scope, commit=False)
        employer = employer_service.create(employer_data, db, scope=scope, commit=False)
        address_service.update(address.address_id, update_data, db, scope=scope, commit=False)
        
        if assign_to_user:
            user_service.update(user_id, user_data, db, scope=scope, commit=False)
        
        # Commit once at end
        db.commit()
        return employer
    except Exception as e:
        db.rollback()
        raise
```

**Testing**:
- Test successful creation (all operations committed)
- Test failure scenarios (all operations rolled back)
- Test with and without user assignment

---

#### Step 2.2: Restaurant Creation with Balance
**File**: `app/routes/restaurant.py`
**Function**: `create_restaurant()`

**Current Issue**: Restaurant and balance created separately
**Solution**: Use `commit=False` for restaurant creation, commit after balance creation

**Changes**:
```python
def create_restaurant(...):
    try:
        # Create restaurant with commit=False
        restaurant = restaurant_service.create(restaurant_dict, db, scope=scope, commit=False)
        
        # Create balance (uses raw SQL, already commits)
        balance_created = create_restaurant_balance_record(...)
        
        if not balance_created:
            db.rollback()  # Rollback restaurant if balance fails
            raise HTTPException(...)
        
        # Commit restaurant (balance already committed)
        db.commit()
        return restaurant
    except Exception as e:
        db.rollback()
        raise
```

**Alternative**: Refactor `create_restaurant_balance_record()` to accept `commit` parameter

**Testing**:
- Test successful creation
- Test balance creation failure (restaurant rolled back)

---

#### Step 2.3: Vianda Selection - Initial Workflow
**File**: `app/services/vianda_selection_service.py`
**Function**: `create_vianda_selection_with_transactions()`

**Current Issue**: Multiple operations commit separately
**Solution**: Use `commit=False` for all operations in initial workflow, commit at end

**Changes**:
```python
def create_vianda_selection_with_transactions(...):
    try:
        # All operations with commit=False
        selection = vianda_selection_service.create(selection_data, db, commit=False)
        pickup = vianda_pickup_live_service.create(pickup_data, db, commit=False)
        restaurant_transaction = restaurant_transaction_service.create(rt_data, db, commit=False)
        client_transaction = client_transaction_service.create(ct_data, db, commit=False)
        
        # Update subscription balance (may need refactoring)
        subscription_service.update_balance(...)  # Check if this commits
        
        # Commit once at end
        db.commit()
        return selection
    except Exception as e:
        db.rollback()
        raise
```

**Note**: Need to check subscription balance update method - may need refactoring

**Testing**:
- Test successful selection (all operations committed)
- Test failure scenarios (all operations rolled back)
- Verify credits deducted atomically

---

#### Step 2.4: Vianda Pickup - Status Updates
**File**: `app/services/vianda_pickup_service.py`
**Function**: Update pickup status workflow

**Current Issue**: Status updates may commit separately
**Solution**: Use `commit=False` for all status updates, commit at end

**Changes**:
```python
def update_pickup_status(...):
    try:
        # All status updates with commit=False
        vianda_pickup_live_service.update(pickup_id, {"status": Status.COMPLETE}, db, commit=False)
        vianda_selection_service.update(selection_id, {"status": Status.COMPLETE}, db, commit=False)
        transaction_service.update(transaction_id, {"status": Status.COMPLETE}, db, commit=False)
        
        # Commit once at end
        db.commit()
    except Exception as e:
        db.rollback()
        raise
```

**Testing**:
- Test successful pickup (all statuses updated atomically)
- Test failure scenarios (all statuses rolled back)

---

#### Step 2.5: Transaction + Balance Update
**File**: `app/services/crud_service.py`
**Function**: `create_with_conservative_balance_update()`

**Current Issue**: Transaction and balance update commit separately
**Solution**: Use `commit=False` for transaction creation, commit after balance update

**Changes**:
```python
def create_with_conservative_balance_update(data: dict, db: psycopg2.extensions.connection):
    try:
        # Create transaction with commit=False
        transaction = restaurant_transaction_service.create(data, db, commit=False)
        
        if transaction:
            # Update balance (may need refactoring to accept commit parameter)
            balance_updated = update_balance_on_transaction_creation(
                transaction.restaurant_id,
                float(transaction.final_amount),
                db,
                commit=False  # NEW
            )
            
            if not balance_updated:
                db.rollback()
                return None
            
            # Commit once at end
            db.commit()
        
        return transaction
    except Exception as e:
        db.rollback()
        raise
```

**Note**: Need to refactor `update_balance_on_transaction_creation()` to accept `commit` parameter

**Testing**:
- Test successful transaction + balance update
- Test balance update failure (transaction rolled back)

---

### Phase 3: Audit and Refactor Additional Services

#### Step 3.1: Identify Other Atomic Operations
**Action**: Review codebase for other multi-operation workflows

**Areas to Check**:
- Payment processing flows
- Discretionary credit resolution workflows
- Institution entity creation workflows
- User profile update workflows

#### Step 3.2: Refactor Identified Operations
**Action**: Apply atomic transaction pattern to identified operations

---

### Phase 4: Testing and Validation

#### Step 4.1: Unit Tests
- Test all modified functions with `commit=False`
- Test rollback scenarios
- Test commit at end of atomic operations

#### Step 4.2: Integration Tests
- Test end-to-end workflows
- Test failure scenarios
- Verify data consistency

#### Step 4.3: Regression Tests
- Verify existing operations still work (backward compatibility)
- Test all CRUD operations with default `commit=True`

---

## Implementation Order

1. **Phase 1**: Core infrastructure (db_insert, db_update, CRUD service)
2. **Phase 2.1**: Employer creation (current priority)
3. **Phase 2.2**: Restaurant creation
4. **Phase 2.3**: Vianda selection initial workflow
5. **Phase 2.4**: Vianda pickup workflow
6. **Phase 2.5**: Transaction + balance update
7. **Phase 3**: Audit and refactor additional services
8. **Phase 4**: Testing and validation

---

## Risk Assessment

**Low Risk**:
- Adding optional parameter with default value (backward compatible)
- Existing code continues to work unchanged

**Medium Risk**:
- Refactoring existing atomic operations (need thorough testing)
- Ensuring rollback works correctly

**Mitigation**:
- Comprehensive testing at each phase
- Gradual rollout (one service at a time)
- Rollback plan if issues arise

---

## Additional Atomicity Investigation (Future)

### Payment Completion + Bill Status Update

**Status**: ⚠️ **NEEDS INVESTIGATION** - Add to roadmap

**Workflow**: When payment is registered as successful, update bill status atomically

**Business Context**:
- Bill generation and payment execution are NOT atomic (intentional time delay)
- Time between bill generation and payment allows:
  - Investigation of bills
  - Connection with bank for transaction verification
- But when payment is registered as successful, bill status update should be atomic

**Required Operations** (should be atomic):
1. Register payment as successful
2. Update bill status to "Paid" or "Completed"
3. Update related records (if any)

**Why Atomic**:
- Payment and bill status must stay in sync
- If payment registration fails, bill should not be marked paid
- If bill update fails, payment should not be registered

**Current Implementation**:
- `mark_paid()` in `crud_service.py` updates bill status
- Payment registration logic needs investigation
- Need to identify where payment is registered and ensure atomicity

**Implementation Needed**:
- Investigate current payment registration flow
- Create `register_payment_success()` function
- Update payment status + bill status atomically
- Use `commit=False` for both operations

**See**: `docs/roadmap/VIANDA_PICKUP_ATOMICITY_ANALYSIS.md` for detailed analysis

