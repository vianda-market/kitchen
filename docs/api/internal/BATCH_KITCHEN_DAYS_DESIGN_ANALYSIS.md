# Batch Kitchen Days Assignment - Design Analysis

## Problem Statement

When a user wants to assign a plate to multiple kitchen days (e.g., Monday, Tuesday, Wednesday), we need to decide on the best approach:

1. **Client-side queuing**: Client makes multiple individual `POST /plate-kitchen-days/` calls
2. **Batch endpoint**: Single `POST /plate-kitchen-days/batch` call with array of days

## Use Case Analysis

### Typical Scenarios

1. **Initial plate setup**: Assign 5 days (Monday-Friday) - **Most common**
2. **Partial assignment**: Assign 2-3 days (e.g., Monday, Wednesday, Friday)
3. **Single day**: Assign 1 day (rare, but possible)
4. **Update existing**: Change from 3 days to 5 days

### Current Legacy Endpoint Behavior

The legacy `POST /plate-selections/kitchen-days/{plate_id}` endpoint:
- **Hard deletes** ALL existing kitchen days for the plate
- **Creates** new ones in batch
- **Atomic operation** (all or nothing)
- **Returns** list of created days

This is a **"replace all"** operation, not an additive operation.

---

## Design Options

### Option 1: Client-Side Queuing (Current Approach) ⚠️

**Implementation**:
```typescript
// Client code
const days = ["Monday", "Tuesday", "Wednesday"];
for (const day of days) {
  await fetch('/plate-kitchen-days/', {
    method: 'POST',
    body: JSON.stringify({ plate_id, kitchen_day: day })
  });
}
```

**Pros**:
- ✅ Uses existing RESTful endpoints
- ✅ No additional backend code
- ✅ Simple to understand
- ✅ Follows REST principles (one resource per call)

**Cons**:
- ❌ **Multiple HTTP calls** (3-5 requests per operation)
- ❌ **No atomicity** - Partial failures leave inconsistent state
- ❌ **Complex error handling** - Client must handle rollback
- ❌ **Slower** - Network latency × number of days
- ❌ **Client logic complexity** - Must queue, handle errors, retry
- ❌ **Race conditions** - If user clicks twice quickly

**Error Handling Example**:
```typescript
// Client must handle this complexity
const created = [];
try {
  for (const day of days) {
    const result = await createKitchenDay(plateId, day);
    created.push(result);
  }
} catch (error) {
  // Rollback: Delete all created days
  for (const item of created) {
    await deleteKitchenDay(item.kitchen_day_id);
  }
  throw error;
}
```

---

### Option 2: Batch Create Endpoint (Recommended) ✅

**Implementation**:
```python
# Backend
@router.post("/batch", response_model=List[PlateKitchenDayResponseSchema])
def create_plate_kitchen_days_batch(
    payload: PlateKitchenDayBatchCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Create multiple kitchen day assignments for a plate in a single atomic operation.
    
    This endpoint is optimized for the common use case of assigning multiple days
    to a plate at once (e.g., Monday-Friday).
    """
    # Atomic operation: all succeed or all fail
    # Returns list of created kitchen days
```

**Schema**:
```python
class PlateKitchenDayBatchCreateSchema(BaseModel):
    plate_id: UUID
    kitchen_days: List[str] = Field(..., min_items=1, max_items=5)
    replace_existing: bool = False  # If True, delete existing first
```

**Pros**:
- ✅ **Single HTTP call** - Better performance
- ✅ **Atomic operation** - All succeed or all fail (database transaction)
- ✅ **Simple client logic** - One call, handle one response
- ✅ **Better error handling** - Backend handles rollback automatically
- ✅ **No race conditions** - Single operation
- ✅ **Optimized for common use case** - Assigning multiple days is the norm
- ✅ **Flexible** - Can add `replace_existing` flag for "replace all" behavior

**Cons**:
- ⚠️ Additional endpoint to maintain
- ⚠️ Slightly less RESTful (but acceptable for batch operations)

**Client Code**:
```typescript
// Simple client code
const result = await fetch('/plate-kitchen-days/batch', {
  method: 'POST',
  body: JSON.stringify({
    plate_id: plateId,
    kitchen_days: ["Monday", "Tuesday", "Wednesday"],
    replace_existing: false  // Add to existing
  })
});
// One call, one response, atomic operation
```

---

### Option 3: Array in Single POST (Hybrid) ⚠️

**Implementation**:
```python
# Modify existing POST endpoint to accept array
@router.post("/", response_model=List[PlateKitchenDayResponseSchema])
def create_plate_kitchen_day(
    payload: Union[PlateKitchenDayCreateSchema, PlateKitchenDayBatchCreateSchema],
    ...
):
    # If array provided, create multiple
    # If single day provided, create one
```

**Pros**:
- ✅ Single endpoint
- ✅ Backward compatible (can accept single or array)

**Cons**:
- ❌ **Type confusion** - Union types are harder to validate
- ❌ **Less clear API** - Unclear if single or batch operation
- ❌ **Complex validation** - Must handle both cases
- ❌ **Not RESTful** - POST should create one resource

---

## Recommendation: **Option 2 - Batch Endpoint** ✅

### Rationale

1. **Common Use Case**: Assigning multiple days (3-5) is the **primary use case**, not the exception
2. **Atomicity Matters**: Kitchen day assignments should be atomic - you don't want partial assignments
3. **Client Simplicity**: Reduces client-side complexity significantly
4. **Performance**: Single HTTP call is faster than 3-5 calls
5. **Error Handling**: Backend handles rollback automatically (database transaction)
6. **Industry Standard**: Batch endpoints are common for bulk operations (e.g., AWS, Stripe)

### Implementation Details

**Endpoint**: `POST /plate-kitchen-days/batch`

**Request Schema**:
```python
class PlateKitchenDayBatchCreateSchema(BaseModel):
    plate_id: UUID
    kitchen_days: List[str] = Field(
        ..., 
        min_items=1, 
        max_items=5,
        description="List of kitchen days to assign (Monday-Friday)"
    )
    replace_existing: bool = Field(
        False,
        description="If True, delete all existing kitchen days for this plate before creating new ones"
    )
```

**Response Schema**:
```python
class PlateKitchenDayBatchResponseSchema(BaseModel):
    plate_id: UUID
    created: List[PlateKitchenDayResponseSchema]
    skipped: List[str] = Field(default_factory=list, description="Days that already existed (if replace_existing=False)")
    message: str
```

**Behavior**:
- **Atomic**: All days created in a single database transaction
- **Validation**: Validates all days before creating any
- **Unique constraint**: Handles conflicts gracefully (skip or error)
- **Scoping**: Uses same JOIN-based scoping as individual endpoint

**Error Handling**:
- If any day is invalid → 400 Bad Request (no days created)
- If plate doesn't belong to institution → 403 Forbidden (no days created)
- If unique constraint violation and `replace_existing=False` → Skip existing, create new
- If database error → 500 Internal Server Error (transaction rolled back)

---

## Migration Strategy

### Phase 1: Add Batch Endpoint (Keep Individual Endpoints)
- Add `POST /plate-kitchen-days/batch` endpoint
- Keep individual `POST /plate-kitchen-days/` for single-day assignments
- Update Postman collection to use batch endpoint

### Phase 2: Update Clients
- Update UI to use batch endpoint for multiple days
- Keep individual endpoint for single-day use cases (if needed)

### Phase 3: Deprecate Legacy Endpoint
- Delete `POST /plate-selections/kitchen-days/{plate_id}` after clients migrated

---

## Comparison Table

| Criteria | Client Queuing | Batch Endpoint | Array in POST |
|----------|---------------|----------------|---------------|
| **HTTP Calls** | 3-5 calls | 1 call | 1 call |
| **Atomicity** | ❌ No | ✅ Yes | ✅ Yes |
| **Client Complexity** | ❌ High | ✅ Low | ✅ Low |
| **Error Handling** | ❌ Client rollback | ✅ Backend rollback | ✅ Backend rollback |
| **Performance** | ❌ Slow | ✅ Fast | ✅ Fast |
| **RESTful** | ✅ Yes | ⚠️ Acceptable | ❌ No |
| **Maintainability** | ✅ Simple | ✅ Simple | ❌ Complex |
| **Use Case Fit** | ❌ Poor | ✅ Excellent | ⚠️ Good |

---

## Conclusion

**Recommendation**: Implement **Option 2 - Batch Endpoint**

**Reasoning**:
- Assigning multiple days is the **primary use case** (not edge case)
- Atomicity is **critical** for data consistency
- Client-side queuing adds **unnecessary complexity**
- Batch endpoints are **industry standard** for bulk operations
- Better **user experience** (faster, more reliable)

**Implementation Priority**: **High** - This should be implemented before deleting the legacy endpoint, as it provides a better replacement than client-side queuing.

