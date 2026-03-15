# Archived Records Pattern - API Documentation

## Overview

**As of the API change to remove `include_archived` from production APIs**, all GET endpoints **always** return only non-archived records. The `include_archived` query parameter is **no longer exposed** in the API contract. Archived data remains viewable via direct SQL for audits. A future internal-support API may reintroduce `include_archived` if needed.

## Current Behavior

**All production GET endpoints exclude archived records.** There is no parameter to include them.

This means:
- ✅ **Always non-archived**: All GET endpoints return only records where `is_archived = FALSE`
- ✅ **Safe for UI**: UI never receives archived records from the API
- ✅ **Consistent**: All endpoints follow the same pattern
- ✅ **No query parameter**: Do not pass `include_archived` — it is not part of the API

## UI Best Practices

### ✅ Recommended: Omit Any include_archived Parameter

The UI should **not pass `include_archived`** in requests. If present, it will be ignored:

```typescript
// ✅ GOOD: No include_archived parameter
const response = await fetch('/api/v1/users/enriched/', {
  headers: { 'Authorization': `Bearer ${token}` }
});
```

## API Endpoint Examples

### Users Endpoints

**Base Endpoints:**
```
GET /api/v1/users/           # Non-archived only
GET /api/v1/users/{user_id}  # Non-archived only
```

**Enriched Endpoints:**
```
GET /api/v1/users/enriched/           # Non-archived only
GET /api/v1/users/enriched/{user_id}  # Non-archived only
```

### Other Entity Endpoints

All entity endpoints follow the same pattern (non-archived only):
- `/addresses/`
- `/restaurants/`
- `/products/`
- `/employers/`
- etc.

## Response Schema

Response schemas may include an `is_archived` field for consistency, but production APIs will not return archived records.

## Implementation Details

### Backend Behavior

1. **Always Filter**: All GET endpoints add `WHERE is_archived = FALSE` (or equivalent) to SQL queries
2. **No Override**: There is no API parameter to include archived records
3. **Archived Access**: Archived records are viewable via direct SQL for audits only

### Frontend Filtering

**The UI does NOT need to filter archived records** because:
- ✅ The backend never returns archived records
- ✅ No client-side filtering required

## Summary

| Scenario | API Behavior |
|----------|---------------|
| **All production GET requests** | ✅ Only non-archived records returned |

**Recommendation for UI**: Do not pass `include_archived` — it is not part of the API.
