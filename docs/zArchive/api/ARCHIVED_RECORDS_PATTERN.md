# Archived Records Pattern - API Documentation

## Overview

All FastAPI endpoints that return entity lists or individual entities support filtering archived records via the `include_archived` query parameter. This ensures that by default, only active (non-archived) records are returned.

## Default Behavior

**By default, all GET endpoints exclude archived records** (`include_archived=false`).

This means:
- ✅ **Default behavior**: Only returns records where `is_archived = FALSE`
- ✅ **Safe for UI**: UI doesn't need to filter archived records client-side
- ✅ **Consistent**: All endpoints follow the same pattern

## Query Parameter

### Parameter Name
`include_archived`

### Type
`boolean` (optional)

### Default Value
`false` (archived records are excluded by default)

### Usage

**Exclude archived records (default):**
```
GET /users/
GET /users/?include_archived=false
```

**Include archived records:**
```
GET /users/?include_archived=true
```

## UI Best Practices

### ✅ Recommended: Omit the Parameter (Use Default)

The UI should **omit the `include_archived` parameter** to rely on the default behavior:

```typescript
// ✅ GOOD: Uses default (excludes archived)
const response = await fetch('/users/enriched/', {
  headers: { 'Authorization': `Bearer ${token}` }
});
```

### ✅ Alternative: Explicitly Set to False

If you want to be explicit for clarity:

```typescript
// ✅ GOOD: Explicitly excludes archived
const response = await fetch('/users/enriched/?include_archived=false', {
  headers: { 'Authorization': `Bearer ${token}` }
});
```

### ❌ Avoid: Setting to True Unless Needed

Only set `include_archived=true` when you specifically need archived records:

```typescript
// ⚠️ Only use when you need archived records (e.g., admin restore page)
const response = await fetch('/users/enriched/?include_archived=true', {
  headers: { 'Authorization': `Bearer ${token}` }
});
```

## API Endpoint Examples

### Users Endpoints

**Base Endpoints:**
```
GET /users/                          # Excludes archived (default)
GET /users/?include_archived=false   # Explicitly excludes archived
GET /users/?include_archived=true    # Includes archived
GET /users/{user_id}                 # Excludes archived (default)
GET /users/{user_id}?include_archived=true  # Includes archived
```

**Enriched Endpoints:**
```
GET /users/enriched/                          # Excludes archived (default)
GET /users/enriched/?include_archived=false   # Explicitly excludes archived
GET /users/enriched/?include_archived=true    # Includes archived
GET /users/enriched/{user_id}                 # Excludes archived (default)
GET /users/enriched/{user_id}?include_archived=true  # Includes archived
```

### Other Entity Endpoints

All entity endpoints follow the same pattern:
- `/addresses/`
- `/restaurants/`
- `/products/`
- `/institution-bank-accounts/`
- `/institution-payment-attempts/`
- `/employers/`
- etc.

## Response Schema

All response schemas include an `is_archived` field so the UI can identify archived records if they are included:

```typescript
interface UserEnrichedResponse {
  user_id: string;
  // ... other fields
  is_archived: boolean;  // ← Always present in response
  // ... other fields
}
```

## Implementation Details

### Backend Behavior

1. **Default Filtering**: When `include_archived=false` (or omitted), the backend adds `WHERE is_archived = FALSE` to SQL queries
2. **Include Archived**: When `include_archived=true`, the backend removes the archived filter
3. **Consistent Across Endpoints**: All GET endpoints follow this pattern

### Frontend Filtering

**The UI should NOT filter archived records client-side** because:
- ✅ The backend already filters by default
- ✅ Reduces data transfer (fewer records)
- ✅ Consistent behavior across all endpoints
- ✅ Better performance (database-level filtering)

## Error Handling

If you explicitly request archived records but don't have permission:
- The endpoint will still return archived records (if `include_archived=true`)
- Institution scoping still applies (you'll only see archived records from your institution)

## Migration Guide

If you're currently filtering archived records client-side:

**Before (Client-Side Filtering):**
```typescript
// ❌ BAD: Filtering client-side
const allUsers = await fetchUsers();
const activeUsers = allUsers.filter(u => !u.is_archived);
```

**After (Server-Side Filtering):**
```typescript
// ✅ GOOD: Let backend filter (default behavior)
const activeUsers = await fetchUsers();  // Already filtered!
```

## Summary

| Scenario | Parameter Value | Result |
|----------|----------------|--------|
| **Normal UI usage** | Omit parameter | ✅ Only active records |
| **Normal UI usage** | `include_archived=false` | ✅ Only active records |
| **Admin restore page** | `include_archived=true` | ⚠️ Includes archived records |

**Recommendation for UI**: **Omit the parameter** to use the safe default behavior.

