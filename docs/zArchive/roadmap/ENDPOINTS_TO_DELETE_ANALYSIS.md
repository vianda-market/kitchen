# Endpoints to Delete Analysis

## Summary

**Endpoints that can be deleted**: 2 legacy endpoints in `vianda_selection.py`
**Postman collections that need updates**: 1 collection (E2E Vianda Selection)

---

## Endpoints to Delete

### 1. `POST /vianda-selections/kitchen-days/{vianda_id}` ❌ DELETE
**Location**: `app/routes/vianda_selection.py:82-153`

**Status**: ✅ **DEPRECATED** (marked in code)

**Replacement**: Use `/vianda-kitchen-days/` endpoints instead

**Current Behavior**:
- Hard deletes ALL existing kitchen days for a vianda
- Creates new kitchen days in batch
- Returns list of created kitchen days

**Replacement Strategy**:
The new `/vianda-kitchen-days/` endpoints provide granular control:
- `POST /vianda-kitchen-days/` - Create individual kitchen day
- `PUT /vianda-kitchen-days/{kitchen_day_id}` - Update individual kitchen day
- `DELETE /vianda-kitchen-days/{kitchen_day_id}` - Delete individual kitchen day

**Migration Path**:
To replace the batch operation, you would:
1. Get all existing kitchen days: `GET /vianda-kitchen-days/?vianda_id={vianda_id}` (filter client-side)
2. Delete each one: `DELETE /vianda-kitchen-days/{kitchen_day_id}` (for each)
3. Create new ones: `POST /vianda-kitchen-days/` (for each day)

**Alternative**: Create a batch endpoint in `/vianda-kitchen-days/` if batch operations are needed.

---

### 2. `GET /vianda-selections/kitchen-days/{vianda_id}` ❌ DELETE
**Location**: `app/routes/vianda_selection.py:155-188`

**Status**: ✅ **DEPRECATED** (marked in code)

**Replacement**: Use `/vianda-kitchen-days/` endpoints instead

**Current Behavior**:
- Gets all kitchen days for a specific vianda
- Returns simplified format: `{"vianda_id": "...", "kitchen_days": ["Monday", "Tuesday"]}`

**Replacement Strategy**:
Use the new endpoint:
- `GET /vianda-kitchen-days/` - List all kitchen days (filter by `vianda_id` client-side or add query param)
- `GET /vianda-kitchen-days/enriched/` - List with enriched data

**Migration Path**:
1. Call `GET /vianda-kitchen-days/` (or add `?vianda_id={vianda_id}` query param)
2. Filter results client-side by `vianda_id`
3. Extract `kitchen_day` values from results

**Note**: The new endpoint returns full `ViandaKitchenDayResponseSchema` objects, not just day names.

---

## Postman Collections That Need Updates

### 1. **E2E Vianda Selection Collection** ⚠️ REQUIRES UPDATE

**File**: `docs/postman/collections/E2E Vianda Selection.postman_collection.json`

**Current Usage**:
- **Request**: `POST /vianda-selections/kitchen-days/{{plateId}}`
- **Location**: Line 1122
- **Request Name**: "Register Supplier Vianda Kitchen Days"

**Required Changes**:

#### Option A: Replace with Multiple Calls (Recommended)
Replace the single batch call with individual calls:

1. **Get existing kitchen days** (optional, for cleanup):
   ```
   GET /vianda-kitchen-days/?vianda_id={{plateId}}
   ```
   Then delete each one if needed.

2. **Create new kitchen days** (one per day):
   ```
   POST /vianda-kitchen-days/
   Body: {
     "vianda_id": "{{plateId}}",
     "kitchen_day": "Monday"
   }
   ```
   Repeat for each day: Tuesday, Wednesday, Thursday, Friday

#### Option B: Add Batch Endpoint (Future Enhancement)
Create a new batch endpoint in `/vianda-kitchen-days/`:
```
POST /vianda-kitchen-days/batch
Body: {
  "vianda_id": "{{plateId}}",
  "kitchen_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
  "replace_existing": true
}
```

**Recommendation**: Use **Option A** for now (multiple individual calls). The new endpoints provide better granularity and follow RESTful principles.

---

## Impact Analysis

### Code to Delete
- **File**: `app/routes/vianda_selection.py`
- **Lines**: 82-188 (2 functions, ~106 lines)
- **Functions**:
  - `assign_kitchen_days_to_vianda()` (lines 82-153)
  - `get_vianda_kitchen_days()` (lines 155-188)

### Benefits of Deletion
1. ✅ **Reduces code duplication** - Single source of truth for kitchen days API
2. ✅ **Simplifies maintenance** - One set of endpoints to maintain
3. ✅ **Better RESTful design** - Granular operations instead of batch operations
4. ✅ **Consistent with new architecture** - Uses CRUDService with JOIN-based scoping
5. ✅ **Clearer API surface** - Less confusion about which endpoint to use

### Risks of Deletion
1. ⚠️ **Breaking change** - E2E collection will break if not updated
2. ⚠️ **Batch operation lost** - No direct replacement for "replace all" operation
3. ⚠️ **Client code updates** - Any client code using these endpoints needs updates

---

## Migration Checklist

### Before Deleting Endpoints

1. ✅ **Update E2E Vianda Selection Postman Collection**
   - Replace `POST /vianda-selections/kitchen-days/{{plateId}}` with multiple `POST /vianda-kitchen-days/` calls
   - Update test scripts to handle multiple responses
   - Verify collection still works end-to-end

2. ⚠️ **Check for other usages** (if any)
   - Search codebase for `/vianda-selections/kitchen-days`
   - Check if any client applications use these endpoints
   - Check API documentation

3. ⚠️ **Consider batch endpoint** (optional)
   - If batch operations are common, consider adding `POST /vianda-kitchen-days/batch`
   - This would provide a direct replacement for the legacy endpoint

### After Deleting Endpoints

1. ✅ **Remove code** from `app/routes/vianda_selection.py`
2. ✅ **Update API documentation** (if any)
3. ✅ **Update route registration** (if needed)
4. ✅ **Test E2E collection** to ensure it still works

---

## Recommendation

**✅ Safe to delete** after updating the E2E Postman collection.

The legacy endpoints are:
- ✅ Already marked as deprecated
- ✅ Have clear replacements
- ✅ Only used in one Postman collection
- ✅ Not part of the core API design

**Suggested Timeline**:
1. **Now**: Update E2E Postman collection to use new endpoints
2. **After testing**: Delete legacy endpoints from `vianda_selection.py`
3. **Future** (optional): Add batch endpoint if batch operations are needed frequently

---

## No Other Endpoints to Delete

The following endpoints are **NOT deprecated** and should **NOT** be deleted:
- ✅ `/restaurant-balances/` - New read-only endpoints (not replacing anything)
- ✅ `/restaurant-transactions/` - New read-only endpoints (not replacing anything)
- ✅ `/vianda-kitchen-days/` - New dedicated endpoints (replacing legacy ones)
- ✅ All other endpoints in `vianda_selection.py` - Still in active use

