# Discretionary Endpoint Enhancement Plan

## Overview
This plan outlines the implementation of category standardization, validation, enriched endpoints, and query filtering for the discretionary credit request system.

## Current State Analysis

### Database Schema
- `discretionary_info` table:
  - `user_id` UUID NOT NULL
  - `restaurant_id` UUID NULLABLE
  - `category` VARCHAR(50) NULLABLE
  - `reason` VARCHAR(50) NULLABLE
  - `amount` NUMERIC
  - `status` VARCHAR(20) DEFAULT 'Pending'

### Current Validation
- **Category values**: `["client_refund", "restaurant_refund", "promotion", "compensation"]`
- **Reason values**: `["service_issue", "quality_complaint", "promotion", "compensation", "other"]`
- No enforcement of category based on user_id/restaurant_id relationship
- No enriched endpoint exists
- No query parameter filtering

### Current Endpoints
- `POST /admin/discretionary/requests/` - Create request
- `GET /admin/discretionary/requests/` - Get admin's requests
- `GET /admin/discretionary/requests/{id}` - Get specific request
- `PUT /admin/discretionary/requests/{id}` - Update request
- `GET /super-admin/discretionary/pending-requests/` - Get pending requests
- `GET /super-admin/discretionary/requests/` - Get all requests
- `POST /super-admin/discretionary/requests/{id}/approve` - Approve request
- `POST /super-admin/discretionary/requests/{id}/reject` - Reject request

---

## Implementation Plan

### Phase 1: Database Schema Updates

#### 1.1 Add CHECK Constraint for Category
**File**: `app/db/schema.sql`

Add database-level constraint to enforce category values:
```sql
ALTER TABLE discretionary_info 
ADD CONSTRAINT chk_discretionary_category 
CHECK (category IN ('Client', 'Supplier'));

-- Update history table as well
ALTER TABLE discretionary_history 
ADD CONSTRAINT chk_discretionary_history_category 
CHECK (category IN ('Client', 'Supplier'));
```

**Impact**: 
- Enforces category values at database level
- Prevents invalid category values
- No data migration needed (user will rebuild DB)

#### 1.2 Reason Field Structure Decision
**Decision**: Keep as VARCHAR(50) with standardized enum values (simple string format)

**Rationale**: 
- JSON may be overkill for MVP
- Simple enum values are easier to query and filter
- Can migrate to JSON later if needed
- Maintains backward compatibility

**Reason Values**:
- **Client requests**: 
  - `"Marketing Campaign"`
  - `"Credit Refund"`
- **Supplier requests**:
  - `"Order incorrectly marked as not collected"`
  - `"Full Order Refund"`
  - `"Marketing Campaign"`

**Note**: These values will be maintained as a findable list and can be updated over time.

---

### Phase 2: Postman Collection Updates

#### 2.1 Update Discretionary Postman Collections
**Files**: 
- `docs/postman/collections/Discretionary Credit System - E2E Tests.postman_collection.json` (if present)
- `docs/postman/collections/DISCRETIONARY_CREDIT_SYSTEM.postman_collection.json`

**Changes Required**:

1. **Update Category Values**:
   - Replace `"client_refund"` → `"Client"`
   - Replace `"restaurant_refund"` → `"Supplier"`
   - Remove old category values from all requests

2. **Update Reason Values**:
   - **Client requests**: Use `"Marketing Campaign"` or `"Credit Refund"`
   - **Supplier requests**: Use `"Order incorrectly marked as not collected"`, `"Full Order Refund"`, or `"Marketing Campaign"`
   - Remove old reason values (`service_issue`, `quality_complaint`, etc.)

3. **Fix Request Structure**:
   - **Client requests**: Remove `restaurant_id` field (should not be present)
   - **Supplier requests**: Ensure `restaurant_id` is present, `user_id` can be null
   - Update test assertions to check for new category values

4. **Add Pending Request Step**:
   - Create a new request: "Create Pending Client Request (Leave Open)"
   - This request should create a discretionary request but NOT approve/reject it
   - Purpose: Leave one request in "Pending" status for UI testing
   - Should use valid Client category and reason

5. **Update Test Scripts**:
   - Update all test assertions that check category values
   - Update reason validation tests
   - Ensure tests validate category rules (Client = no restaurant_id, Supplier = has restaurant_id)

**Example Updated Request Body**:

**Client Request**:
```json
{
  "user_id": "{{customerUserId}}",
  "category": "Client",
  "reason": "Marketing Campaign",
  "amount": 20.00,
  "comment": "Marketing campaign credit for new customer"
}
```

**Supplier Request**:
```json
{
  "restaurant_id": "{{restaurantId}}",
  "category": "Supplier",
  "reason": "Full Order Refund",
  "amount": 50.00,
  "comment": "Full refund for order incorrectly processed"
}
```

**New: Pending Request (Leave Open)**:
```json
{
  "user_id": "{{customerUserId}}",
  "category": "Client",
  "reason": "Credit Refund",
  "amount": 15.00,
  "comment": "Credit refund request - leave pending for UI testing"
}
```

**Execution**: Update collections before database rebuild. User will re-import collections after DB rebuild.

---

### Phase 3: Schema Updates

#### 3.1 Update Pydantic Schemas
**File**: `app/schemas/consolidated_schemas.py`

**Changes**:
1. **DiscretionaryCreateSchema**:
   - Make `category` optional (will be auto-set based on user_id/restaurant_id)
   - Add validator to enforce category rules
   - Update `reason` field description/validation

2. **DiscretionaryUpdateSchema**:
   - Add validation to prevent invalid category changes
   - Ensure category consistency with user_id/restaurant_id

3. **DiscretionaryResponseSchema**:
   - Ensure category is always present
   - Add documentation

4. **New: DiscretionaryEnrichedResponseSchema**:
   ```python
   class DiscretionaryEnrichedResponseSchema(BaseModel):
       discretionary_id: UUID
       user_id: Optional[UUID]
       user_full_name: Optional[str]  # For client requests
       restaurant_id: Optional[UUID]
       restaurant_name: Optional[str]  # For supplier requests
       category: str  # "Client" or "Supplier"
       reason: Optional[str]
       amount: Decimal
       comment: Optional[str]
       status: str
       created_date: datetime
       modified_date: datetime
       approval_id: Optional[UUID]
       # ... other fields
   ```

#### 3.2 Update DTO
**File**: `app/dto/models.py`

**Changes**:
- Update `DiscretionaryDTO.category` to use Literal type: `Literal["Client", "Supplier"]`
- Add validation comments

---

### Phase 4: Service Layer Validation

#### 4.1 Update DiscretionaryService
**File**: `app/services/discretionary_service.py`

**Changes**:

1. **`_validate_discretionary_request_data()` method**:
   ```python
   def _validate_discretionary_request_data(self, request_data: Dict[str, Any]) -> None:
       # Validate category rules
       category = request_data.get("category")
       user_id = request_data.get("user_id")
       restaurant_id = request_data.get("restaurant_id")
       
       # Auto-set category if not provided
       if not category:
           if restaurant_id:
               category = "Supplier"
           elif user_id:
               category = "Client"
           else:
               raise HTTPException(
                   status_code=400,
                   detail="Either user_id or restaurant_id must be provided"
               )
           request_data["category"] = category
       
       # Validate category matches user_id/restaurant_id
       if category == "Client":
           if not user_id:
               raise HTTPException(
                   status_code=400,
                   detail="Client requests require user_id"
               )
           if restaurant_id is not None:
               raise HTTPException(
                   status_code=400,
                   detail="Client requests should not have restaurant_id"
               )
       elif category == "Supplier":
           if not restaurant_id:
               raise HTTPException(
                   status_code=400,
                   detail="Supplier requests require restaurant_id"
               )
           # user_id can be null for supplier requests
       else:
           raise HTTPException(
               status_code=400,
               detail=f"Invalid category. Must be 'Client' or 'Supplier'"
           )
       
       # Validate reason format (if structured)
       # ... reason validation logic
   ```

2. **`create_discretionary_request()` method**:
   - Call validation before creation
   - Ensure category is set correctly

3. **Add validation to update operations**:
   - Prevent changing category in a way that violates rules
   - Validate user_id/restaurant_id changes maintain category consistency

#### 4.2 Update CRUD Service (if needed)
**File**: `app/services/crud_service.py`

- Ensure update operations respect category validation
- Add validation hook if needed

---

### Phase 5: Enriched Endpoint Implementation

#### 5.1 Create Enriched Service Function
**File**: `app/services/entity_service.py`

**New Function**:
```python
def get_enriched_discretionary_requests(
    db: psycopg2.extensions.connection,
    *,
    category: Optional[str] = None,
    status: Optional[str] = None,
    user_id: Optional[UUID] = None,
    restaurant_id: Optional[UUID] = None,
    include_archived: bool = False
) -> List[DiscretionaryEnrichedResponseSchema]:
    """
    Get all discretionary requests with enriched data.
    Includes: user_full_name (for Client), restaurant_name (for Supplier).
    """
    # Use EnrichedService with JOINs to user_info and restaurant_info
    # Filter by category, status, user_id, restaurant_id as needed
```

**Implementation Details**:
- Use `EnrichedService` pattern (similar to other enriched endpoints)
- LEFT JOIN with `user_info` for `user_full_name`
- LEFT JOIN with `restaurant_info` for `restaurant_name`
- Apply filters based on query parameters

#### 5.2 Create Enriched Route
**File**: `app/routes/admin/discretionary.py` or new file

**New Endpoint**:
```python
@router.get("/requests/enriched/", response_model=List[DiscretionaryEnrichedResponseSchema])
def get_enriched_discretionary_requests(
    category: Optional[str] = Query(None, description="Filter by category: Client or Supplier"),
    status: Optional[str] = Query(None, description="Filter by status"),
    user_id: Optional[UUID] = Query(None, description="Filter by user_id"),
    restaurant_id: Optional[UUID] = Query(None, description="Filter by restaurant_id"),
    include_archived: bool = Query(False, description="Include archived records"),
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get all discretionary requests with enriched data.
    
    Enriched fields:
    - user_full_name (for Client requests)
    - restaurant_name (for Supplier requests)
    
    Query Parameters:
    - category: Filter by "Client" or "Supplier"
    - status: Filter by status (e.g., "Pending", "Approved", "Rejected")
    - user_id: Filter by user_id
    - restaurant_id: Filter by restaurant_id
    - include_archived: Include archived records
    """
```

**Access Control**: Employee-only (same as base endpoint)

---

### Phase 6: Query Parameter Filtering

#### 6.1 Update Base Endpoints
**Files**: 
- `app/routes/admin/discretionary.py`
- `app/routes/super_admin/discretionary.py`

**Changes**:

1. **`GET /admin/discretionary/requests/`**:
   - Add `category` query parameter
   - Add `status` query parameter
   - Filter results in service layer

2. **`GET /super-admin/discretionary/pending-requests/`**:
   - Add `category` query parameter
   - Ensure returns both Client and Supplier requests
   - Verify category field is properly set

3. **`GET /super-admin/discretionary/requests/`**:
   - Add `category` query parameter
   - Add `status` query parameter
   - Add `user_id` query parameter
   - Add `restaurant_id` query parameter

#### 6.2 Update Service Methods
**File**: `app/services/discretionary_service.py`

**Changes**:
- `get_pending_requests()`: Add category filter parameter
- `get_requests_by_admin()`: Add category filter parameter
- Add new method: `get_requests_filtered()` for complex filtering

---

### Phase 7: API Response Consistency

#### 7.1 Verify Pending Requests Endpoint
**File**: `app/routes/super_admin/discretionary.py`

**Ensure**:
- `GET /super-admin/discretionary/pending-requests/` returns:
  - Both Client and Supplier requests
  - Properly set category field
  - All required fields populated
  - Consistent response format

#### 7.2 Update DiscretionarySummarySchema
**File**: `app/schemas/consolidated_schemas.py`

**Verify**:
- Category field is included
- All fields are properly documented
- Response is consistent across endpoints

---

## Implementation Order

### Step 1: Postman Collection Updates
1. Update category values (Client/Supplier)
2. Update reason values (new enum list)
3. Fix request structure (remove restaurant_id from Client requests)
4. Add pending request step (leave one open for UI)
5. Update test assertions

### Step 2: Schema Updates
1. Update database constraints
2. Update Pydantic schemas
3. Update DTOs

### Step 3: Validation Logic
1. Update service validation
2. Add category auto-setting logic
3. Test validation rules

### Step 4: Enriched Endpoint
1. Create enriched schema
2. Implement enriched service function
3. Create enriched route
4. Test enriched endpoint

### Step 5: Query Parameters
1. Add query parameters to routes
2. Update service methods for filtering
3. Test filtering functionality

### Step 6: Testing & Verification
1. Test all endpoints
2. Verify category enforcement
3. Verify enriched endpoint returns correct data
4. Verify filtering works correctly
5. Test edge cases

---

## Testing Checklist

### Unit Tests
- [ ] Category validation: Client requires user_id, no restaurant_id
- [ ] Category validation: Supplier requires restaurant_id
- [ ] Category auto-setting when not provided
- [ ] Reason format validation (if structured)
- [ ] Enriched endpoint returns user_full_name for Client
- [ ] Enriched endpoint returns restaurant_name for Supplier
- [ ] Query parameter filtering works

### Integration Tests
- [ ] Create Client request
- [ ] Create Supplier request
- [ ] Update request maintains category consistency
- [ ] Enriched endpoint with filters
- [ ] Pending requests returns both categories
- [ ] All endpoints return consistent category values

### Edge Cases
- [ ] Request with both user_id and restaurant_id (should fail)
- [ ] Request with neither user_id nor restaurant_id (should fail)
- [ ] Update category (should validate)
- [ ] Filter by category returns correct results
- [ ] Enriched endpoint handles NULL user/restaurant gracefully

---

## Breaking Changes

### API Changes
1. **Category values change**: 
   - Old: `["client_refund", "restaurant_refund", "promotion", "compensation"]`
   - New: `["Client", "Supplier"]`
   - **Impact**: Frontend must update category handling

2. **Category auto-setting**:
   - Category can now be omitted in create requests
   - **Impact**: Backward compatible (category still accepted)

3. **Validation stricter**:
   - Category must match user_id/restaurant_id relationship
   - **Impact**: Invalid requests will be rejected

### Database Changes
1. **Category constraint**: Only "Client" or "Supplier" allowed
2. **No migration needed**: User will rebuild database from scratch

---

## Rollback Plan

1. **Remove database constraints** (if needed)
2. **Revert schema changes** (keep old category values)
3. **Revert validation logic** (allow old categories)
4. **Keep enriched endpoint** (additive, no breaking changes)

---

## Documentation Updates

1. **API Documentation**:
   - Update category field description
   - Document category rules
   - Document enriched endpoint
   - Document query parameters

2. **Developer Guide**:
   - Document category standardization
   - Document validation rules
   - Document enriched endpoint usage

---

## Estimated Effort

- **Phase 1 (Schema)**: 2 hours
- **Phase 2 (Migration)**: 1 hour
- **Phase 3 (Schemas)**: 3 hours
- **Phase 4 (Validation)**: 4 hours
- **Phase 5 (Enriched)**: 4 hours
- **Phase 6 (Filtering)**: 3 hours
- **Phase 7 (Consistency)**: 2 hours
- **Testing**: 4 hours

**Total**: ~23 hours

---

## Approved Decisions

1. **Reason field structure**: ✅ **Simple string format (VARCHAR enum)** - JSON may be overkill for MVP, can migrate later if needed
2. **Category migration**: ✅ **No migration needed** - User will tear down and rebuild DB, will re-import Postman collections
3. **Enriched endpoint location**: ✅ **Admin can read enriched endpoint** - `/admin/discretionary/requests/enriched/`
4. **Backward compatibility**: ✅ **No support for old categories** - Clean break, new system only
5. **Reason values**:
   - **Client requests**: `"Marketing Campaign"`, `"Credit Refund"`
   - **Supplier requests**: `"Order incorrectly marked as not collected"`, `"Full Order Refund"`, `"Marketing Campaign"`
   - These will be maintained as a findable list and can be updated over time

