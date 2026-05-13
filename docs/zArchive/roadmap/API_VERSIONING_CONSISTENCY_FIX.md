# API Versioning Consistency Fix

## Date
2026-02-05

## Problem
The API had an architectural inconsistency where discretionary credit routes were split between versioned and non-versioned paths:
- **Admin Discretionary**: `/admin/discretionary/` (non-versioned) ❌
- **Super-Admin Discretionary**: `/api/v1/super-admin/discretionary/` (versioned) ✅

This violated the REST API versioning principle that **all business API routes must be versioned**.

## Solution
All discretionary routes are now consistently versioned under `/api/v1/`:

### Before (Inconsistent)
```
GET /admin/discretionary/requests/                    ❌ Non-versioned
POST /admin/discretionary/requests/                   ❌ Non-versioned
GET /admin/discretionary/pending-requests/            ❌ Non-versioned
PUT /admin/discretionary/requests/{id}                ❌ Non-versioned

GET /api/v1/super-admin/discretionary/requests/       ✅ Versioned
POST /api/v1/super-admin/discretionary/requests/{id}/approve  ✅ Versioned
POST /api/v1/super-admin/discretionary/requests/{id}/reject   ✅ Versioned
```

### After (Consistent)
```
GET /api/v1/admin/discretionary/requests/                    ✅ Versioned
POST /api/v1/admin/discretionary/requests/                   ✅ Versioned
GET /api/v1/admin/discretionary/pending-requests/            ✅ Versioned
PUT /api/v1/admin/discretionary/requests/{id}                ✅ Versioned

GET /api/v1/super-admin/discretionary/requests/              ✅ Versioned
POST /api/v1/super-admin/discretionary/requests/{id}/approve ✅ Versioned
POST /api/v1/super-admin/discretionary/requests/{id}/reject  ✅ Versioned
```

## Changes Made

### 1. Backend (`application.py`)
- Moved `admin_discretionary_router` from non-versioned `main_router` to a versioned wrapper
- Added `v1_admin_discretionary_router` with `/api/v1/` prefix
- Updated comments to clarify that `main_router` is for infrastructure/monitoring only

### 2. Route Organization (`app/routes/main.py`)
- Removed `admin_discretionary_router` import and inclusion
- Updated documentation to clarify that all business APIs are versioned in `application.py`
- `main_router` now only contains infrastructure endpoints like `/pool-stats`

### 3. Postman Collections
Updated all admin discretionary endpoints to use `/api/v1/` prefix:

**DISCRETIONARY_CREDIT_SYSTEM.postman_collection.json**:
- `POST /api/v1/admin/discretionary/requests/` - Create requests
- `GET /api/v1/admin/discretionary/requests/` - List requests
- `PUT /api/v1/admin/discretionary/requests/{id}` - Update request
- `GET /api/v1/admin/discretionary/pending-requests/` - Get pending requests

**Permissions Testing - Employee-Only Access.postman_collection.json**:
- All admin discretionary test endpoints updated to use `/api/v1/` prefix

## Architecture Principles

### Non-Versioned Endpoints (Infrastructure/Monitoring Only)
- `/` - Root redirect
- `/health` - Health check for load balancers
- `/pool-stats` - Database connection pool monitoring

### Versioned Endpoints (All Business APIs)
- `/api/v1/auth/` - Authentication
- `/api/v1/users/` - User management
- `/api/v1/admin/discretionary/` - Admin discretionary credit management
- `/api/v1/super-admin/discretionary/` - Super-Admin discretionary approval
- `/api/v1/restaurants/` - Restaurant management
- `/api/v1/viandas/` - Vianda management
- All other business endpoints

## Benefits
1. **Consistency**: All business APIs follow the same versioning pattern
2. **Future-proofing**: Makes it easier to introduce API v2 in the future
3. **Clear separation**: Infrastructure endpoints vs. business endpoints
4. **Documentation**: Clearer API structure for frontend developers
5. **Best practices**: Follows REST API versioning standards

## Testing
After this change, all Postman collections should pass without 404 errors. The discretionary credit system tests should run successfully with the updated paths.

## Related Documentation
- `docs/Claude.md` - API Versioning principles
- `app/core/versioning.py` - Versioning implementation
- `docs/api/client/API_PERMISSIONS_BY_ROLE.md` - Endpoint permissions by role
