# Payment Method Address Implementation Plan

## Purpose
Consolidate address storage to the `payment_method` table level. Move `address_id` from type-specific tables (`credit_card`, `bank_account`) to `payment_method` table to avoid duplication and provide a single source of truth. Includes handling atomic transactions when creating a payment method with a new address.

**Architecture Decision**: All addresses are stored at the `payment_method` level. Type-specific tables (`credit_card`, `bank_account`) no longer store addresses.

---

## Executive Summary

### Key Changes
1. **Add `address_id` to `payment_method` table** (nullable)
2. **Remove `address_id` from `credit_card` and `bank_account` tables**
3. **Add validation logic**: `credit_card` and `bank_account` payment methods require address, `fintech_link` does not
4. **Atomic transaction support**: Create payment method with new address atomically

### Validation Rules
- **Credit Card & Bank Account**: `address_id` is REQUIRED (enforced in business logic)
- **Fintech Link**: `address_id` is OPTIONAL (can be NULL)

### Database Rebuild Required
⚠️ **After implementing schema changes, tear down and rebuild the database**. No migration scripts needed - we're starting fresh.

---

## Current State Analysis

### Database Schema

**payment_method table** (current):
```sql
CREATE TABLE payment_method (
    payment_method_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    method_type VARCHAR(20) NOT NULL,
    method_type_id UUID,
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Pending'::status_enum,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- NO address_id column currently
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT
);
```

**Type-specific tables** (current):
- `credit_card.address_id UUID NOT NULL` - **TO BE REMOVED**
- `bank_account.address_id UUID NOT NULL` - **TO BE REMOVED**
- `fintech_link_info` - No address_id (correct, Fintech Link doesn't need addresses)

**Problem**: Address duplication across `payment_method` and type-specific tables. Need to consolidate to `payment_method` level.

**Solution**: 
- Add nullable `address_id` to `payment_method` table
- Remove `address_id` from `credit_card` and `bank_account` tables
- Add validation: `address_id` is required for `credit_card` and `bank_account` payment methods, optional for `fintech_link`

---

## Use Case: Atomic Payment Method + Address Creation

### Scenario
When creating a payment method, the client-side user must either:
1. **Select an existing address** - Provide `address_id` of an existing address
2. **Create a new address** - Provide address data, which should be created atomically with the payment method

### Business Requirement
- **If address creation fails**: Payment method should not be created (atomicity)
- **If payment method creation fails after address creation**: Address should be rolled back (atomicity)
- **All operations in single workflow**: Both address and payment method creation happen in single API call
- **Validation**: `address_id` is **required** for `credit_card` and `bank_account` payment methods, **optional** for `fintech_link`

### Why Atomic
- Payment provider may require address validation before accepting payment method
- Partial creation (payment_method without address) violates business rules for payment methods that require addresses
- Address created specifically for payment method should not exist if payment method creation fails
- Data integrity: Payment method and address must exist together (when required by method_type)

---

## Implementation Approach

### Option 1: Use Atomic Transaction Framework (Recommended)

**Status**: ✅ Framework already exists
- `db_insert()` and `db_update()` already support `commit: bool = True` parameter
- `CRUDService.create()` and `CRUDService.update()` already support `commit: bool = True` parameter
- `address_business_service.create_address_with_geocoding()` already supports `commit: bool = True` parameter

**Implementation Pattern** (from `ATOMIC_TRANSACTION_USE_CASES.md`):
```python
def create_payment_method_with_address(...):
    try:
        # Option 1: Create new address (if address_data provided)
        if address_data:
            address = address_business_service.create_address_with_geocoding(
                address_data, current_user, db, scope=scope, commit=False
            )
            address_id = address.address_id
        else:
            # Option 2: Use existing address_id
            address_id = existing_address_id
        
        # Create payment method with address_id
        payment_method_data["address_id"] = address_id
        payment_method = payment_method_service.create(
            payment_method_data, db, commit=False
        )
        
        # Commit once at end
        db.commit()
        return payment_method
    except Exception as e:
        db.rollback()
        raise
```

---

## Implementation Plan

### Phase 1: Database Schema Changes

#### Step 1.1: Add `address_id` Column to `payment_method` Table

**File**: `app/db/schema.sql`

**Changes**:
```sql
CREATE TABLE payment_method (
    payment_method_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    method_type VARCHAR(20) NOT NULL,
    method_type_id UUID,
    address_id UUID,  -- NEW: Nullable (required for credit_card/bank_account, optional for fintech_link)
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Pending'::status_enum,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by UUID NOT NULL,
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES user_info(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (address_id) REFERENCES address_info(address_id) ON DELETE RESTRICT  -- NEW
);

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_payment_method_address_id 
ON payment_method(address_id);
```

**Note**: `address_id` is **nullable** because `fintech_link` payment methods don't require addresses. Validation will enforce that `credit_card` and `bank_account` payment methods require `address_id`.

#### Step 1.2: Remove `address_id` from `credit_card` Table

**File**: `app/db/schema.sql`

**Changes**:
```sql
CREATE TABLE credit_card (
    credit_card_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_method_id UUID NOT NULL,
    -- address_id UUID NOT NULL,  -- REMOVED: Address now stored in payment_method table
    card_holder_name VARCHAR(100),
    card_number_last_4 VARCHAR(4),
    card_brand VARCHAR(50),
    expiry_date VARCHAR(5),
    credit_card_token VARCHAR(100),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (payment_method_id) REFERENCES payment_method(payment_method_id) ON DELETE RESTRICT
    -- FOREIGN KEY (address_id) REFERENCES address_info(address_id) ON DELETE RESTRICT  -- REMOVED
);
```

#### Step 1.3: Remove `address_id` from `bank_account` Table

**File**: `app/db/schema.sql`

**Changes**:
```sql
CREATE TABLE bank_account (
    bank_account_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_method_id UUID NOT NULL,
    -- address_id UUID NOT NULL,  -- REMOVED: Address now stored in payment_method table
    account_holder_name VARCHAR(100),
    account_number_last_4 VARCHAR(4),
    bank_name VARCHAR(100),
    routing_number VARCHAR(50),
    account_type VARCHAR(50),
    bank_account_token VARCHAR(100),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    status status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (payment_method_id) REFERENCES payment_method(payment_method_id) ON DELETE RESTRICT
    -- FOREIGN KEY (address_id) REFERENCES address_info(address_id) ON DELETE RESTRICT  -- REMOVED
);
```

**⚠️ IMPORTANT**: After schema changes, **tear down and rebuild the database**. No migration scripts needed since we're starting fresh.

---

### Phase 2: Pydantic Schema Updates

#### Step 2.1: Update PaymentMethodCreateSchema

**File**: `app/schemas/payment_method.py`

**Current Schema**:
```python
class PaymentMethodCreateSchema(BaseModel):
    method_type: str = Field(..., max_length=20)
    method_type_id: Optional[UUID] = None
    is_default: Optional[bool] = False
```

**Updated Schema** (Option A - Union Pattern):
```python
class PaymentMethodCreateSchema(BaseModel):
    method_type: str = Field(..., max_length=20)
    method_type_id: Optional[UUID] = None
    is_default: Optional[bool] = False
    address_id: Optional[UUID] = None  # Use existing address
    # If address_id is None, address_data must be provided (validated in business logic)
```

**Alternative Schema** (Option B - Explicit Pattern):
```python
class PaymentMethodCreateWithAddressSchema(BaseModel):
    """Schema for creating payment method with new address"""
    method_type: str = Field(..., max_length=20)
    method_type_id: Optional[UUID] = None
    is_default: Optional[bool] = False
    address_data: AddressCreateSchema  # New address to create

class PaymentMethodCreateWithExistingAddressSchema(BaseModel):
    """Schema for creating payment method with existing address"""
    method_type: str = Field(..., max_length=20)
    method_type_id: Optional[UUID] = None
    is_default: Optional[bool] = False
    address_id: UUID  # Existing address to use
```

**Recommendation**: **Option A** (simpler, maintains single endpoint). Validate in business logic that either `address_id` or `address_data` is provided (but not both).

#### Step 2.2: Update PaymentMethodResponseSchema

**File**: `app/schemas/payment_method.py`

**Updated Schema**:
```python
class PaymentMethodResponseSchema(BaseModel):
    payment_method_id: UUID
    user_id: UUID
    method_type: str = Field(..., max_length=20)
    method_type_id: Optional[UUID] = None
    address_id: Optional[UUID] = None  # NEW
    is_archived: bool
    status: Status
    is_default: bool
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True
```

#### Step 2.3: Update PaymentMethodEnrichedResponseSchema

**File**: `app/schemas/payment_method.py`

**Updated Schema**:
```python
class PaymentMethodEnrichedResponseSchema(BaseModel):
    payment_method_id: UUID
    user_id: UUID
    full_name: str
    username: str
    email: str
    cellphone: str
    method_type: str
    method_type_id: Optional[UUID] = None
    address_id: Optional[UUID] = None  # NEW
    is_archived: bool
    status: Status
    is_default: bool
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True
```

#### Step 2.4: Update PaymentMethodUpdateSchema (if needed)

**File**: `app/schemas/payment_method.py`

**Updated Schema**:
```python
class PaymentMethodUpdateSchema(BaseModel):
    method_type: Optional[str] = Field(None, max_length=20)
    method_type_id: Optional[UUID] = None
    address_id: Optional[UUID] = None  # NEW - allow updating address
    status: Optional[Status] = None
    is_default: Optional[bool] = None
```

---

### Phase 3: DTO Updates

#### Step 3.1: Update PaymentMethodDTO

**File**: `app/dto/models.py`

**Need to check if PaymentMethodDTO exists and update it**:
- Add `address_id: Optional[UUID] = None` field

---

### Phase 4: Business Logic Implementation

#### Step 4.1: Add Validation Constants

**File**: `app/services/payment_method_service.py`

**Add at top of file**:
```python
# Payment method types that require address
PAYMENT_METHODS_REQUIRING_ADDRESS = {"Credit Card", "Bank Account"}

# Payment method types that do NOT require address
PAYMENT_METHODS_NOT_REQUIRING_ADDRESS = {"Fintech Link"}
```

#### Step 4.2: Create Atomic Payment Method + Address Service Method

**File**: `app/services/payment_method_service.py`

**New Function**:
```python
def create_payment_method_with_address(
    payment_method_data: Dict[str, Any],
    address_id: Optional[UUID],
    address_data: Optional[Dict[str, Any]],
    current_user: Dict[str, Any],
    db: psycopg2.extensions.connection,
    scope: Optional[InstitutionScope] = None
) -> PaymentMethodDTO:
    """
    Create payment method with address (atomic transaction).
    
    Validation rules:
    - credit_card and bank_account: address_id OR address_data is REQUIRED
    - fintech_link: address_id and address_data are OPTIONAL (can be None)
    
    Args:
        payment_method_data: Payment method data (method_type, is_default, etc.)
        address_id: Optional UUID of existing address to use
        address_data: Optional address data to create new address
        current_user: Current user information
        db: Database connection
        scope: Optional institution scope
        
    Returns:
        Created payment method DTO
        
    Raises:
        HTTPException: For validation or creation failures
    """
    from app.services.address_service import address_business_service
    from app.services.crud_service import payment_method_service
    from app.utils.log import log_info, log_warning
    from fastapi import HTTPException, status
    
    method_type = payment_method_data.get("method_type")
    requires_address = method_type in PAYMENT_METHODS_REQUIRING_ADDRESS
    
    # Validate: cannot provide both address_id and address_data
    if address_id and address_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot provide both address_id and address_data. Provide one or the other."
        )
    
    # Validate: payment methods requiring address must have address_id or address_data
    if requires_address and not address_id and not address_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment method type '{method_type}' requires an address. Provide address_id or address_data."
        )
    
    try:
        resolved_address_id = None
        
        # Option 1: Create new address (atomic, commit=False)
        if address_data:
            log_info(f"Creating new address for payment method type '{method_type}'")
            address = address_business_service.create_address_with_geocoding(
                address_data,
                current_user,
                db,
                scope=scope,
                commit=False  # Atomic transaction
            )
            resolved_address_id = address.address_id
        elif address_id:
            # Option 2: Use existing address_id
            log_info(f"Using existing address {address_id} for payment method type '{method_type}'")
            resolved_address_id = address_id
        # Option 3: No address (only valid for fintech_link)
        else:
            log_info(f"Payment method type '{method_type}' created without address (not required)")
        
        # Create payment method with address_id (atomic, commit=False)
        payment_method_data["address_id"] = resolved_address_id
        payment_method_data["user_id"] = current_user["user_id"]
        payment_method_data["modified_by"] = current_user["user_id"]
        
        payment_method = payment_method_service.create(
            payment_method_data,
            db,
            commit=False  # Atomic transaction
        )
        
        if not payment_method:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create payment method"
            )
        
        # Commit once at end (both address and payment_method committed together)
        db.commit()
        log_info(f"Payment method {payment_method.payment_method_id} created successfully with address {resolved_address_id}")
        
        return payment_method
        
    except HTTPException:
        # Re-raise HTTP exceptions
        db.rollback()
        raise
    except Exception as e:
        # Rollback on any error
        db.rollback()
        log_warning(f"Failed to create payment method with address: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create payment method: {str(e)}"
        )
```

---

### Phase 5: Route Updates

#### Step 5.1: Update Payment Method Creation Route

**File**: `app/services/route_factory.py` (in `create_payment_method_routes()`)

**Current Route**:
```python
@router.post("/", response_model=PaymentMethodResponseSchema, status_code=status.HTTP_201_CREATED)
def create_payment_method(
    create_data: PaymentMethodCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a new payment method"""
    # ... existing implementation
```

**Updated Route** (Option A - Single Schema):
```python
@router.post("/", response_model=PaymentMethodResponseSchema, status_code=status.HTTP_201_CREATED)
def create_payment_method(
    create_data: PaymentMethodCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a new payment method with optional address creation"""
    from app.services.error_handling import handle_business_operation
    from app.utils.log import log_info
    from app.services.payment_method_service import create_payment_method_with_address
    from app.services.address_service import address_business_service
    
    def _create_payment_method():
        data = create_data.dict()
        
        # Extract address_id or address_data from request
        address_id = data.pop("address_id", None)
        address_data = data.pop("address_data", None)
        
        # Validate: exactly one must be provided
        if address_id and address_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot provide both address_id and address_data. Provide one or the other."
            )
        if not address_id and not address_data:
            # For backward compatibility: allow creation without address (if nullable)
            # Or require address: raise HTTPException(...)
            pass  # Depends on business requirement
        
        # Use atomic service method
        return create_payment_method_with_address(
            payment_method_data=data,
            address_id=address_id,
            address_data=address_data,
            current_user=current_user,
            db=db,
            scope=None  # Payment methods are user-scoped, not institution-scoped
        )
    
    return handle_business_operation(
        _create_payment_method,
        "payment method creation",
        "Payment method created successfully"
    )
```

**Alternative Route** (Option B - Two Separate Endpoints):
- Keep existing endpoint for backward compatibility
- Add new endpoint: `POST /payment-methods/with-address/` for atomic creation

**Recommendation**: **Option A** (single endpoint with optional fields).

---

### Phase 6: Address Schema Integration

#### Step 6.1: Handle AddressCreateSchema in PaymentMethodCreateSchema

**Option A**: Embed AddressCreateSchema fields directly in PaymentMethodCreateSchema
- Pros: Single schema, simpler API
- Cons: Schema becomes large, mixes concerns

**Option B**: Use Union or Optional nested schema
- Pros: Separation of concerns, reusable AddressCreateSchema
- Cons: More complex validation

**Option C**: Accept address_data as Dict in route, validate separately
- Pros: Flexible, keeps schemas separate
- Cons: Less type safety

**Recommendation**: **Option C** - Accept `address_data` as optional dict in PaymentMethodCreateSchema, validate using AddressCreateSchema in business logic.

**Updated PaymentMethodCreateSchema** (Option C):
```python
class PaymentMethodCreateSchema(BaseModel):
    method_type: str = Field(..., max_length=20)
    method_type_id: Optional[UUID] = None
    is_default: Optional[bool] = False
    address_id: Optional[UUID] = Field(None, description="UUID of existing address to use")
    address_data: Optional[Dict[str, Any]] = Field(None, description="Address data for new address creation")
    
    @validator('address_data')
    def validate_address_data(cls, v, values):
        """Ensure either address_id or address_data is provided, not both"""
        address_id = values.get('address_id')
        if address_id and v:
            raise ValueError("Cannot provide both address_id and address_data")
        return v
```

**Better Approach**: Use Pydantic's `root_validator`:
```python
from pydantic import root_validator

class PaymentMethodCreateSchema(BaseModel):
    method_type: str = Field(..., max_length=20)
    method_type_id: Optional[UUID] = None
    is_default: Optional[bool] = False
    address_id: Optional[UUID] = Field(None, description="UUID of existing address to use")
    address_data: Optional[Dict[str, Any]] = Field(None, description="Address data for new address creation")
    
    @root_validator
    def validate_address_fields(cls, values):
        address_id = values.get('address_id')
        address_data = values.get('address_data')
        
        if address_id and address_data:
            raise ValueError("Cannot provide both address_id and address_data. Provide one or the other.")
        # Note: We allow neither for backward compatibility (if address_id is nullable)
        # If address becomes required, add: if not address_id and not address_data: raise ValueError(...)
        
        return values
```

---

## Implementation Order

### Phase 1: Database Schema (Priority: HIGH)
1. Create migration SQL to add `address_id` column
2. Add foreign key constraint
3. Add index
4. Test migration on development database

### Phase 2: Schema & DTO Updates (Priority: HIGH)
1. Update PaymentMethodCreateSchema (add address_id, address_data fields with validation)
2. Update PaymentMethodResponseSchema (add address_id field)
3. Update PaymentMethodEnrichedResponseSchema (add address_id field)
4. Update PaymentMethodUpdateSchema (add address_id field)
5. Update PaymentMethodDTO (add address_id field)

### Phase 3: Business Logic (Priority: HIGH)
1. Add validation constants (PAYMENT_METHODS_REQUIRING_ADDRESS)
2. Create `create_payment_method_with_address()` service function
3. Implement atomic transaction logic (commit=False pattern)
4. Add validation:
   - Method type validation (credit_card/bank_account require address)
   - address_id XOR address_data validation
   - Address ownership validation (recommended)
5. Add error handling and rollback
6. Update credit_card and bank_account creation logic (remove address_id handling)

### Phase 4: Route Updates (Priority: HIGH)
1. Update payment method creation route
2. Handle address_id and address_data in request
3. Call atomic service function
4. Update error handling

### Phase 5: Update Type-Specific Creation Logic (Priority: HIGH)
1. Update credit_card creation routes/services (remove address_id parameter, use payment_method.address_id)
2. Update bank_account creation routes/services (remove address_id parameter, use payment_method.address_id)
3. Update fintech_link creation (no changes needed, already doesn't use address)

### Phase 6: Testing (Priority: HIGH)
1. Unit tests for atomic transaction (success case)
2. Unit tests for rollback scenarios (failure cases)
3. Integration tests for payment method + address creation
4. Backward compatibility tests (existing payment methods still work)

---

## Testing Requirements

### Test Cases

1. **Create Payment Method with Existing Address**
   - Provide `address_id`
   - Verify payment_method created with correct address_id
   - Verify transaction is atomic

2. **Create Payment Method with New Address**
   - Provide `address_data`
   - Verify address created first
   - Verify payment_method created with new address_id
   - Verify transaction is atomic (both committed together)

3. **Create Payment Method with New Address - Address Creation Fails**
   - Provide invalid `address_data`
   - Verify address creation fails
   - Verify payment_method is NOT created (rollback)
   - Verify no orphaned records

4. **Create Payment Method with New Address - Payment Method Creation Fails**
   - Provide valid `address_data` but invalid payment_method_data
   - Verify address creation succeeds
   - Verify payment_method creation fails
   - Verify address is rolled back (no orphaned address)

5. **Create Fintech Link Payment Method without Address**
   - Create payment method with method_type="Fintech Link"
   - Don't provide address_id or address_data
   - Verify payment_method created successfully
   - Verify address_id is NULL

6. **Validation - Credit Card without Address (Should Fail)**
   - Create payment method with method_type="Credit Card"
   - Don't provide address_id or address_data
   - Verify validation error (400 Bad Request)

7. **Validation - Bank Account without Address (Should Fail)**
   - Create payment method with method_type="Bank Account"
   - Don't provide address_id or address_data
   - Verify validation error (400 Bad Request)

8. **Validation - Both address_id and address_data Provided**
   - Provide both address_id and address_data
   - Verify validation error (400 Bad Request)

9. **Validation - Address Ownership (if implemented)**
   - Create payment method with address_id that belongs to different user
   - Verify validation error (403 Forbidden or 400 Bad Request)

---

## Database Rebuild Required

**⚠️ IMPORTANT**: After schema changes, the database must be torn down and rebuilt.

**Steps**:
1. Make all code changes (schema, schemas, DTOs, services, routes)
2. Update test scripts to account for new schema structure
3. **Tear down database**: Drop and recreate database
4. **Rebuild database**: Run schema.sql, seed.sql, etc.
5. Run tests to verify everything works

**No migration scripts needed** - we're starting fresh with the new schema structure.

---

## Relationship to Atomic Transaction Framework

This implementation uses the existing atomic transaction framework documented in `ATOMIC_TRANSACTION_USE_CASES.md`:

- ✅ Uses `commit=False` parameter in `address_business_service.create_address_with_geocoding()`
- ✅ Uses `commit=False` parameter in `payment_method_service.create()`
- ✅ Commits once at end of atomic operation
- ✅ Rolls back on error

This is a new use case for the atomic transaction framework, similar to:
- `create_employer_with_address()` (parent-child entity creation)
- `create_restaurant()` with balance (parent-child entity creation)

**Category**: Parent-Child Entity Creation (Category 1 from ATOMIC_TRANSACTION_USE_CASES.md)

---

## Validation Logic Summary

### Payment Method Types and Address Requirements

| Method Type | Requires Address | address_id Required |
|------------|------------------|---------------------|
| `Credit Card` | ✅ Yes | ✅ Required (NOT NULL) |
| `Bank Account` | ✅ Yes | ✅ Required (NOT NULL) |
| `Fintech Link` | ❌ No | ❌ Optional (NULL allowed) |

### Validation Rules

1. **credit_card and bank_account payment methods**:
   - `address_id` OR `address_data` must be provided
   - Cannot be NULL
   - Validation enforced in business logic (since column is nullable for fintech_link)

2. **fintech_link payment methods**:
   - `address_id` and `address_data` are optional
   - Can be NULL
   - No validation required

3. **General rules**:
   - Cannot provide both `address_id` and `address_data` (mutually exclusive)
   - If `address_data` provided, address is created atomically with payment method
   - If `address_id` provided, must be valid UUID referencing existing address

## Decisions Made

1. ✅ **`address_id` is nullable** - Required for fintech_link flexibility
2. ✅ **Address required based on method_type** - Validated in business logic
3. ✅ **Addresses consolidated to payment_method level** - Removed from credit_card and bank_account tables
4. ✅ **No backward compatibility** - Database rebuild required
5. ✅ **Address ownership validation** - Should validate address belongs to same user (recommended)
6. ✅ **Address updates allowed** - Via PaymentMethodUpdateSchema
7. ✅ **Institution_id** - Use user's institution_id for new addresses

---

## Related Files to Modify

1. `app/db/schema.sql` - Add address_id to payment_method, remove from credit_card and bank_account
2. `app/schemas/payment_method.py` - Update all schemas (add address_id, address_data)
3. `app/dto/models.py` - Update PaymentMethodDTO (add address_id field)
4. `app/services/payment_method_service.py` - Add validation constants and atomic creation function
5. `app/services/route_factory.py` - Update payment method creation route
6. Credit card creation routes/services - Remove address_id handling, use payment_method.address_id
7. Bank account creation routes/services - Remove address_id handling, use payment_method.address_id
8. `app/tests/` - Update all payment method tests, add new validation tests
9. Test scripts (seed.sql, etc.) - Update to match new schema structure

---

## Success Criteria

1. ✅ Payment method can be created with existing address (address_id)
2. ✅ Payment method can be created with new address (address_data) - atomic
3. ✅ Failed address creation rolls back payment method creation
4. ✅ Failed payment method creation rolls back address creation
5. ✅ Credit card and bank account payment methods require address (validation)
6. ✅ Fintech link payment methods can be created without address
7. ✅ Validation prevents providing both address_id and address_data
8. ✅ Address removed from credit_card and bank_account tables
9. ✅ All addresses stored at payment_method level
10. ✅ All tests pass
11. ✅ Database rebuilt successfully

