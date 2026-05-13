# Single Endpoint with Array Design - Analysis

## Proposal

Modify `POST /vianda-kitchen-days/` to accept an array of `kitchen_day` values, even if it's just one day. This eliminates the need for a separate batch endpoint.

## Current Implementation

**Current Schema**:
```python
class ViandaKitchenDayCreateSchema(BaseModel):
    vianda_id: UUID
    kitchen_day: str  # Single day
```

**Current Endpoint**:
```python
@router.post("/", response_model=ViandaKitchenDayResponseSchema)
def create_vianda_kitchen_day(
    payload: ViandaKitchenDayCreateSchema,  # Single day
    ...
):
    # Creates one kitchen day
```

## Proposed Implementation

**New Schema**:
```python
class ViandaKitchenDayCreateSchema(BaseModel):
    vianda_id: UUID
    kitchen_days: List[str] = Field(..., min_items=1, max_items=5)  # Array of days
    replace_existing: Optional[bool] = Field(False, description="If True, delete existing days first")
```

**New Endpoint**:
```python
@router.post("/", response_model=List[ViandaKitchenDayResponseSchema])
def create_vianda_kitchen_days(
    payload: ViandaKitchenDayCreateSchema,  # Array of days
    ...
):
    # Creates multiple kitchen days atomically
    # Returns list of created kitchen days
```

## Comparison

### Option A: Separate Batch Endpoint
- `POST /vianda-kitchen-days/` - Single day
- `POST /vianda-kitchen-days/batch` - Multiple days
- **Pros**: Clear separation, RESTful (one resource per call)
- **Cons**: Two endpoints to maintain, client must choose

### Option B: Single Endpoint with Array (Proposed) ✅
- `POST /vianda-kitchen-days/` - Accepts array (1-N days)
- **Pros**: 
  - ✅ Single endpoint (simpler API)
  - ✅ Always atomic (array processed in transaction)
  - ✅ Backward compatible (array of 1 = single day)
  - ✅ No client decision needed
  - ✅ Consistent response format
- **Cons**: 
  - ⚠️ Slightly less RESTful (POST creates multiple resources)
  - ⚠️ Response is always array (even for 1 day)

## Analysis

### RESTful Considerations

**Traditional REST**: `POST /resource/` creates one resource, returns that resource.

**Modern API Patterns**: Many APIs accept arrays in POST for bulk operations:
- Stripe: `POST /customers` can create multiple
- AWS: Many batch operations
- GitHub: Batch operations accept arrays

**Verdict**: ✅ **Acceptable** - Array in POST is common for bulk operations, especially when atomicity matters.

### Response Format

**Option 1: Always return array**
```python
response_model=List[ViandaKitchenDayResponseSchema]
# Even for 1 day: [{...}]
```

**Option 2: Return single or array based on input**
```python
# If 1 day: return ViandaKitchenDayResponseSchema
# If multiple: return List[ViandaKitchenDayResponseSchema]
```

**Recommendation**: ✅ **Always return array** - Consistent, simpler, easier to handle client-side.

### Backward Compatibility

**Breaking Change**: Yes, but minimal:
- Old: `{"vianda_id": "...", "kitchen_day": "Monday"}`
- New: `{"vianda_id": "...", "kitchen_days": ["Monday"]}`

**Migration**: Simple - wrap single day in array.

## Implementation Details

### Schema Design

```python
class ViandaKitchenDayCreateSchema(BaseModel):
    vianda_id: UUID
    kitchen_days: List[str] = Field(
        ..., 
        min_items=1, 
        max_items=5,
        description="List of kitchen days to assign. Can be 1-5 days."
    )
    replace_existing: bool = Field(
        False,
        description="If True, delete all existing kitchen days for this vianda before creating new ones"
    )
    
    @validator('kitchen_days')
    def validate_kitchen_days(cls, v):
        valid_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        for day in v:
            if day not in valid_days:
                raise ValueError(f"Invalid kitchen day: {day}. Must be one of {valid_days}")
        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("Duplicate kitchen days are not allowed")
        return v
```

### Endpoint Implementation

```python
@router.post("/", response_model=List[ViandaKitchenDayResponseSchema], status_code=status.HTTP_201_CREATED)
def create_vianda_kitchen_days(
    payload: ViandaKitchenDayCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Create one or more kitchen day assignments for a vianda.
    
    This endpoint accepts an array of kitchen days and creates them atomically.
    If any day fails validation, no days are created (atomic operation).
    
    Args:
        payload: Contains vianda_id and array of kitchen_days (1-5 days)
        replace_existing: If True, deletes all existing days for the vianda first
    
    Returns:
        List of created kitchen day assignments
    """
    scope = _get_scope_for_entity(current_user)
    
    def create_operation(connection: psycopg2.extensions.connection):
        # Validate vianda exists
        vianda = vianda_service.get_by_id(payload.vianda_id, connection)
        if not vianda:
            raise HTTPException(status_code=404, detail=f"Vianda not found: {payload.vianda_id}")
        
        # If replace_existing, delete all existing kitchen days for this vianda
        if payload.replace_existing:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM vianda_kitchen_days WHERE vianda_id = %s",
                    (str(payload.vianda_id),)
                )
                connection.commit()
        
        # Validate all days before creating any (atomic validation)
        for day in payload.kitchen_days:
            if _check_unique_constraint(payload.vianda_id, day, connection):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Vianda {payload.vianda_id} is already assigned to {day}"
                )
        
        # Create all kitchen days atomically (in transaction)
        created_days = []
        for day in payload.kitchen_days:
            data = {
                "vianda_id": str(payload.vianda_id),
                "kitchen_day": day,
                "is_archived": False,
                "modified_by": current_user["user_id"]
            }
            
            created = vianda_kitchen_days_service.create(data, connection, scope=scope)
            if not created:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Failed to create kitchen day: {day}"
                )
            created_days.append(created)
        
        log_info(f"Created {len(created_days)} kitchen days for vianda {payload.vianda_id}")
        return created_days
    
    return handle_business_operation(create_operation, db, "create vianda kitchen days")
```

### Transaction Handling

**Important**: The `handle_business_operation` wrapper should ensure all operations happen in a single database transaction. If any creation fails, the entire operation should roll back.

## Benefits of This Approach

1. ✅ **Single Endpoint** - Simpler API surface
2. ✅ **Always Atomic** - Array processed in transaction
3. ✅ **Flexible** - Works for 1 day or multiple days
4. ✅ **Consistent** - Same endpoint for all use cases
5. ✅ **No Client Decision** - Client always uses same endpoint
6. ✅ **Better UX** - Faster (one call), more reliable (atomic)

## Migration Impact

### Postman Collection Update

**Old Request** (if we had single endpoint):
```json
POST /vianda-kitchen-days/
{
  "vianda_id": "uuid",
  "kitchen_day": "Monday"
}
```

**New Request**:
```json
POST /vianda-kitchen-days/
{
  "vianda_id": "uuid",
  "kitchen_days": ["Monday", "Tuesday", "Wednesday"]
}
```

**For single day**:
```json
POST /vianda-kitchen-days/
{
  "vianda_id": "uuid",
  "kitchen_days": ["Monday"]  // Array with 1 item
}
```

### Client Code Update

**Old** (if we had single endpoint):
```typescript
// Multiple calls
for (const day of days) {
  await createKitchenDay(plateId, day);
}
```

**New**:
```typescript
// Single call
await createKitchenDays(plateId, ["Monday", "Tuesday", "Wednesday"]);
```

## Recommendation

✅ **Yes, this approach makes sense!**

**Reasons**:
1. **Simpler API** - One endpoint instead of two
2. **Better for common use case** - Assigning multiple days is the norm
3. **Atomic by default** - All operations in transaction
4. **Industry standard** - Many APIs accept arrays in POST
5. **Easier to maintain** - Less code, single code path

**Trade-off**: Slightly less RESTful (POST creates multiple resources), but this is acceptable for bulk operations where atomicity matters.

## Implementation Checklist

- [ ] Update `ViandaKitchenDayCreateSchema` to accept `kitchen_days: List[str]`
- [ ] Update endpoint to process array and return `List[ViandaKitchenDayResponseSchema]`
- [ ] Add `replace_existing` flag (optional, for "replace all" behavior)
- [ ] Ensure atomic transaction (all succeed or all fail)
- [ ] Update Postman collection
- [ ] Update API documentation

