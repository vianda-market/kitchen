# Postman Collection Update Verification

## Issue
User reported that when running the collection, they see non-versioned paths like:
- `{{baseUrl}}/admin/discretionary/requests/` ❌

Instead of the updated versioned paths:
- `{{baseUrl}}/api/v1/admin/discretionary/requests/` ✅

## Root Cause
Postman may be using a **cached version** of the collection, not the updated file on disk.

## Solution
The collection file has been updated with:
1. **New Collection ID**: `discretionary-credit-system-2026-v1` (was: `discretionary-credit-system-2024`)
2. **New Collection Name**: `Discretionary Credit System - Basic Tests (v1 Versioned)`
3. **Updated Description**: Includes timestamp and v1 versioning note

## Steps to Fix in Postman

### Option 1: Delete and Re-import (Recommended)
1. **Delete the old collection** in Postman:
   - Right-click on "Discretionary Credit System - Basic Tests"
   - Select "Delete"
   - Confirm deletion

2. **Import the updated collection**:
   - Click "Import" button
   - Select `docs/postman/DISCRETIONARY_CREDIT_SYSTEM.postman_collection.json`
   - The collection should now show as "(v1 Versioned)"

### Option 2: Replace Collection
1. Right-click on the existing collection
2. Select "Replace"
3. Choose the updated JSON file
4. Postman will update the collection in place

## Verification

After re-importing, verify these endpoints in the collection:

### Admin Discretionary (Should all have `/api/v1/`)
✅ POST `/api/v1/admin/discretionary/requests/` - Create Client Credit Request
✅ POST `/api/v1/admin/discretionary/requests/` - Create Restaurant Credit Request
✅ POST `/api/v1/admin/discretionary/requests/` - Create Pending Client Request
✅ GET `/api/v1/admin/discretionary/requests/` - Get Admin Requests
✅ PUT `/api/v1/admin/discretionary/requests/{id}` - Update Pending Request
✅ GET `/api/v1/admin/discretionary/pending-requests/` - Get Pending Requests

### Super-Admin Discretionary (Should all have `/api/v1/`)
✅ GET `/api/v1/super-admin/discretionary/requests/{id}` - Get Request Details
✅ POST `/api/v1/super-admin/discretionary/requests/{id}/approve` - Approve Request
✅ POST `/api/v1/super-admin/discretionary/requests/{id}/reject` - Reject Request
✅ GET `/api/v1/super-admin/discretionary/requests/` - Get All Requests

## How to Verify in Postman UI

1. Open any request (e.g., "Create Client Credit Request")
2. Look at the URL field at the top
3. It should show: `{{baseUrl}}/api/v1/admin/discretionary/requests/`
4. NOT: `{{baseUrl}}/admin/discretionary/requests/`

If you still see the old paths without `/api/v1/`, then Postman is definitely using a cached version.

## File Verification

You can verify the file on disk is correct:

```bash
grep -n "admin/discretionary/requests" docs/postman/DISCRETIONARY_CREDIT_SYSTEM.postman_collection.json | head -5
```

Should show lines with `/api/v1/admin/discretionary/requests/`

## Additional Notes

- The backend server MUST be restarted after the `application.py` changes
- All admin discretionary routes are now at `/api/v1/admin/discretionary/`
- All super-admin discretionary routes are now at `/api/v1/super-admin/discretionary/`
- Old non-versioned paths `/admin/discretionary/` will return 404
