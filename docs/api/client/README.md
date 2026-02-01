# Client Repository Documentation

This folder contains all documentation files that should be copied to the client repository (React Native/UI) for frontend development.

## 📋 Summary: Files to Copy

**Copy these 9 essential files to the client repo:**

1. `API_PERMISSIONS_BY_ROLE.md` ⭐
2. `USER_SELF_UPDATE_PATTERN.md` ⭐ **NEW** - `/me` endpoint pattern and deprecation warnings
3. `EMPLOYER_ASSIGNMENT_WORKFLOW.md` ⭐ **NEW** - Backoffice employer management workflow
4. `ENRICHED_ENDPOINT_PATTERN.md` ⭐
5. `ENRICHED_ENDPOINT_UI_IMPLEMENTATION.md` ⭐
6. `ARCHIVED_RECORDS_PATTERN.md` ⭐
7. `SCOPING_BEHAVIOR_FOR_UI.md` ⭐
8. `BULK_API_PATTERN.md` ⭐
9. `ENDPOINT_DEPRECATION_GUIDE.md` ⭐ **NEW** - Deprecated endpoints and migration guide

**Optional but recommended:**
10. `PLATE_PICKUP_PENDING_API.md` - Specific API documentation for the plate pickup pending endpoint

All files are located in this `client/` folder, ready to copy.

**Note**: The enriched endpoints documentation has been updated to reflect the current implementation using the centralized `EnrichedService` class. All enriched endpoints now follow a consistent pattern and are fully implemented.

---

## Essential Documentation Files

### 1. **API_PERMISSIONS_BY_ROLE.md** ⭐ CRITICAL
**Why**: This is the most important document for the UI. It shows:
- Which APIs each role type (Employee, Supplier, Customer) can access
- Which HTTP methods (GET, POST, PUT, DELETE) are allowed for each role
- Permission matrices for all APIs
- Scoping behavior (institution-scoped, user-scoped, global access)

### 2. **USER_SELF_UPDATE_PATTERN.md** ⭐ CRITICAL **NEW**
**Why**: Documents the new `/me` endpoint pattern and deprecation of legacy `/{user_id}` endpoints for self-updates.

**What the UI needs to know**:
- **Use `/me` endpoints for all self-updates** (all user types)
- `GET /api/v1/users/me` - Get current user's profile (enriched)
- `PUT /api/v1/users/me` - Update current user's profile
- `PUT /api/v1/users/me/terminate` - Terminate account
- `PUT /api/v1/users/me/employer` - Assign employer
- **Legacy `/{user_id}` endpoints are deprecated** for self-operations (will log warnings)
- Use `/{user_id}` endpoints only for admin operations (managing other users)
- Migration guide and TypeScript examples included

### 3. **EMPLOYER_ASSIGNMENT_WORKFLOW.md** ⭐ CRITICAL **NEW**
**Why**: Complete guide for backoffice employer management (React web app).

**What the UI needs to know**:
- **Backoffice Employer Management Page**: List all employers, search, add new
- **Edit Employer Page**: Edit employer name, manage multiple addresses
- **Create Employer Page**: Single form to create employer + address atomically
- Use `POST /api/v1/employers/` for atomic creation (employer + address in one call)
- Use `GET /api/v1/employers/{employer_id}/addresses` to fetch all addresses for an employer
- Use `POST /api/v1/employers/{employer_id}/addresses` to add additional addresses
- TypeScript interfaces, error handling, and UI/UX recommendations included

---

### 4. **ENRICHED_ENDPOINT_PATTERN.md** ⭐ CRITICAL
**Why**: Explains the enriched endpoint pattern that eliminates N+1 queries.

**What the UI needs to know**:
- Use `/api/v1/users/enriched/` instead of `/api/v1/users/` when you need `role_name` and `institution_name`
- Use `/api/v1/addresses/enriched/` when you need `institution_name` and user details
- Use `/api/v1/plates/enriched/` when you need restaurant, product, and address details
- Enriched endpoints return denormalized data in a single query
- All enriched endpoints support the same `include_archived` parameter

---

### 3. **EMPLOYER_ASSIGNMENT_WORKFLOW.md** ⭐ CRITICAL **NEW**
**Why**: Complete guide for backoffice employer management (React web app).

**What the UI needs to know**:
- **Backoffice Employer Management Page**: List all employers, search, add new
- **Edit Employer Page**: Edit employer name, manage multiple addresses
- **Create Employer Page**: Single form to create employer + address atomically
- Use `POST /api/v1/employers/` for atomic creation (employer + address in one call)
- Use `GET /api/v1/employers/{employer_id}/addresses` to fetch all addresses for an employer
- Use `POST /api/v1/employers/{employer_id}/addresses` to add additional addresses
- TypeScript interfaces, error handling, and UI/UX recommendations included

### 5. **ENRICHED_ENDPOINT_UI_IMPLEMENTATION.md** ⭐ CRITICAL
**Why**: Provides TypeScript interfaces, React examples, and implementation patterns.

**What the UI needs to know**:
- TypeScript interface definitions for enriched responses
- React component examples
- API service function patterns
- How to use `full_name` field (pre-concatenated)
- Error handling patterns

---

### 6. **ARCHIVED_RECORDS_PATTERN.md** ⭐ CRITICAL
**Why**: Explains how archived records are handled by default.

**What the UI needs to know**:
- **By default, all GET endpoints exclude archived records** (`include_archived=false`)
- **UI should omit the `include_archived` parameter** to use the safe default
- Only set `include_archived=true` when specifically needing archived records (e.g., admin restore page)
- The `is_archived` field is always present in responses
- **Do NOT filter archived records client-side** - backend already does this

---

### 7. **SCOPING_BEHAVIOR_FOR_UI.md** ⭐ CRITICAL
**Why**: Explains the behavior of institution and user scoping from a UI perspective.

**What the UI needs to know**:
- **Institution Scoping**: Suppliers only see data from their institution
- **User Scoping**: Customers only see their own user records and addresses
- **Global Access**: Employees see all data
- **Address Assignment**: 
  - Customers: `user_id` is auto-set from their own user_id (don't send it)
  - Suppliers: Can assign `user_id` to any user within their institution
- The backend enforces this automatically - UI doesn't need to filter
- How to handle 403 errors when accessing out-of-scope data
- Implementation examples for different scenarios

---

### 8. **BULK_API_PATTERN.md** ⭐ CRITICAL

### 9. **ENDPOINT_DEPRECATION_GUIDE.md** ⭐ CRITICAL **NEW**
**Why**: Lists all deprecated endpoints that will be removed in the future.

**What the UI needs to know**:
- **Authentication**: Use `POST /api/v1/auth/token` (not `/auth/token` or `/v1/auth/token`)
- **User Self-Operations**: Use `/api/v1/users/me` instead of `/api/v1/users/{user_id}` for self-reads/updates
- **Migration Checklist**: Step-by-step guide to replace deprecated endpoints
- **Timeline**: When deprecated endpoints will be removed
- **FAQ**: Common questions about deprecation

**Action Required**: Review and migrate deprecated endpoints before they are removed.

---

### 9. **BULK_API_PATTERN.md** ⭐ CRITICAL
**Why**: Explains how to use bulk operations that create/update multiple records in a single atomic API call.

**What the UI needs to know**:
- Which endpoints support bulk operations (e.g., `POST /plate-kitchen-days/`, `POST /national-holidays/bulk`)
- Two patterns: Array in POST body vs. separate `/bulk` endpoint
- All bulk operations are atomic (all succeed or all fail)
- Responses are always arrays, even for single items
- How to handle errors (entire operation rolls back on any validation failure)
- TypeScript examples and best practices

**Use Cases**:
- Creating multiple kitchen days for a plate in one call
- Bulk creating national holidays for a country
- Any scenario where atomicity matters (all or nothing)

---

### 10. **PLATE_PICKUP_PENDING_API.md** (Optional but Recommended)
**Why**: Specific API documentation for the `/plate-pickup/pending` endpoint with detailed response structure and frontend parsing examples.

**What the UI needs to know**:
- Response structure: Returns `null` or a single object (NOT an array)
- How to handle null responses (no pending orders)
- TypeScript interfaces and parsing examples
- Error handling patterns
- UI state examples (empty, single order, multiple orders)

---

## 🚀 Quick Start

### Copy Files to Client Repo

1. Copy all files from this folder to your client repo:
   ```bash
   cp -r docs/api/client/* /path/to/client-repo/docs/api/
   ```

2. Or copy the entire `client/` folder:
   ```bash
   cp -r docs/api/client /path/to/client-repo/docs/api/
   ```

### Recommended Client Repo Structure

When copying documentation to the client repo, organize it as follows:

```
client-repo/
  docs/
    api/
      API_PERMISSIONS_BY_ROLE.md          ⭐
      USER_SELF_UPDATE_PATTERN.md         ⭐
      EMPLOYER_ASSIGNMENT_WORKFLOW.md     ⭐
      ENRICHED_ENDPOINT_PATTERN.md        ⭐
      ENRICHED_ENDPOINT_UI_IMPLEMENTATION.md  ⭐
      ARCHIVED_RECORDS_PATTERN.md         ⭐
      SCOPING_BEHAVIOR_FOR_UI.md          ⭐
      BULK_API_PATTERN.md                 ⭐
      ENDPOINT_DEPRECATION_GUIDE.md       ⭐
      PLATE_PICKUP_PENDING_API.md        (optional)
```

---

## Quick Reference Checklist

When developing a new UI page, check:

- [ ] **Permissions**: Can this role access this API? (See `API_PERMISSIONS_BY_ROLE.md`)
- [ ] **Self-Updates**: Use `/me` endpoints for self-updates (See `USER_SELF_UPDATE_PATTERN.md`)
- [ ] **Employer Management**: Use atomic `POST /api/v1/employers/` for creating employer + address (See `EMPLOYER_ASSIGNMENT_WORKFLOW.md`)
- [ ] **Enriched Endpoints**: Do I need related entity names? Use `/enriched/` endpoints
- [ ] **Archived Records**: Omit `include_archived` parameter (default excludes archived)
- [ ] **Scoping**: Backend handles scoping automatically - don't filter client-side
- [ ] **Bulk Operations**: If creating/updating multiple records, use bulk endpoints (See `BULK_API_PATTERN.md`)
- [ ] **Error Handling**: Handle 403 (Forbidden) when user tries to access out-of-scope data
- [ ] **Full Name**: Use `full_name` field from enriched endpoints (pre-concatenated)
- [ ] **Deprecation Warnings**: Don't use `/{user_id}` endpoints for self-updates (use `/me` instead)
- [ ] **Authentication**: Use `POST /api/v1/auth/token` for login (See `ENDPOINT_DEPRECATION_GUIDE.md`)
- [ ] **Migration**: Review deprecated endpoints and migrate before removal (See `ENDPOINT_DEPRECATION_GUIDE.md`)

---

## Example: Building a Users Page

Based on the documentation:

1. **Check Permissions** (`API_PERMISSIONS_BY_ROLE.md`):
   - Employees: ✅ Full access
   - Suppliers: ✅ Can see users in their institution
   - Customers: ✅ Can see only their own user

2. **Choose Endpoint** (`ENRICHED_ENDPOINT_PATTERN.md`):
   - Use `GET /api/v1/users/enriched/` to get `role_name` and `institution_name` in one call

3. **Handle Archived Records** (`ARCHIVED_RECORDS_PATTERN.md`):
   - Omit `include_archived` parameter (default excludes archived)

4. **Display Data**:
   - Use `user.full_name` (pre-concatenated)
   - Use `user.role_name` (already included)
   - Use `user.institution_name` (already included)

5. **Error Handling**:
   - Handle 403 if user tries to access another user's record (Customers)
   - Handle 401 if token is invalid

---

## 📝 Keeping Files Updated

These files are automatically synchronized with the main documentation in `docs/api/`. When new endpoints or features are added, the files in this folder are updated to reflect the latest changes.

**Last Updated**: December 2024

**Recent Updates**:
- ✅ Added `ENDPOINT_DEPRECATION_GUIDE.md` - Complete deprecation guide with migration checklist
- ✅ Added `USER_SELF_UPDATE_PATTERN.md` - New `/me` endpoint pattern and deprecation warnings
- ✅ Added `EMPLOYER_ASSIGNMENT_WORKFLOW.md` - Backoffice employer management workflow
- ✅ Updated `API_PERMISSIONS_BY_ROLE.md` - Added `/me` endpoints section
- ✅ Updated `SCOPING_BEHAVIOR_FOR_UI.md` - Added `/me` endpoint examples
- ✅ Updated `ENRICHED_ENDPOINT_PATTERN.md` - Added `GET /users/me` as preferred endpoint
- ✅ Updated all endpoint references to use `/api/v1/` prefix (versioned endpoints)

---

## Optional Documentation (Backend-Focused, Not Needed for UI)

These documents are more backend-focused and are **not** included in this folder:

- `PERMISSIONS_IMPLEMENTATION_PLAN.md` - Implementation details, not needed for UI
- `INSTITUTION_SCOPING_DESIGN.md` - Backend architecture, UI doesn't need implementation details
- `USER_DEPENDENT_ROUTES_PATTERN.md` - Backend pattern, UI just needs to know which endpoints require user context
- `API_VERSIONING_GUIDE.md` - Currently all APIs use v1, not critical for UI
- `STATUS_MANAGEMENT_PATTERN.md` - Backend pattern, UI just needs to know status values
