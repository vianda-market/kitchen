# Role Coverage Analysis - Postman Collection

## 🔑 **CRITICAL: Token Management Requirements**

**Every login request MUST:**
1. ✅ Store the `access_token` in a collection variable (format: `{roleType}{roleName}Token`)
2. ✅ Store the `user_id` in a collection variable (format: `{roleType}{roleName}UserId`)

**Every test request MUST:**
1. ✅ Use a prerequest script to get the token from the collection variable
2. ✅ Validate the token exists before making the request
3. ✅ Set the Authorization header using the collection variable token
4. ✅ Never use environment variables or hardcoded tokens

**Example Pattern:**
```javascript
// Login Test Script
pm.collectionVariables.set("employeeManagementToken", response.access_token);
pm.collectionVariables.set("employeeManagementUserId", response.user_id);

// Test Request Prerequest Script
const token = pm.collectionVariables.get("employeeManagementToken");
if (!token) {
    throw new Error("employeeManagementToken not set. Run login first.");
}
pm.request.headers.add({
    key: "Authorization",
    value: "Bearer " + token
});
```

See the [Token Management Pattern](#-token-management-pattern-critical) section for complete details.

---

## Current Test Coverage

### ✅ Currently Tested Roles

| Role Type | Role Name | Test Coverage | Notes |
|-----------|-----------|---------------|-------|
| Employee | Admin | ✅ Partial | Tests system config APIs, but not scope differences |
| Employee | Super Admin | ✅ Partial | Tests discretionary approval, but not scope differences |
| Supplier | Admin | ✅ Complete | Tests system config denial |
| Customer | Comensal | ✅ Complete | Tests read-only access |

### ❌ Missing Role Combinations

| Role Type | Role Name | Status | Critical Test Cases Missing |
|-----------|-----------|--------|---------------------------|
| Employee | Management | ❌ **NOT TESTED** | Institution scope vs global scope |
| Employee | Operator | ❌ **NOT TESTED** | Self-updates only, blocked from managing others |

## Required Test Cases

### 1. Employee Management (Institution Scope)

**Purpose**: Verify Employee Management can manage users within their institution but NOT across institutions.

**Test Cases Needed**:

#### Setup Required:
- [ ] Create Employee Management user in Institution A
- [ ] **Login Employee Management** → Store token in `employeeManagementToken` collection variable
- [ ] Create test user in Institution A (same institution)
- [ ] Create test user in Institution B (different institution)
- [ ] Store user IDs: `employeeManagementUserId`, `institutionAUserId`, `institutionBUserId`

#### Test Cases:
1. **GET /users/** - Should return only users from Institution A
2. **GET /users/{institutionAUserId}** - Should succeed (same institution)
3. **GET /users/{institutionBUserId}** - Should fail with 403 (different institution)
4. **PUT /users/{institutionAUserId}** - Should succeed (same institution)
5. **PUT /users/{institutionBUserId}** - Should fail with 403 (different institution)
6. **GET /users/enriched/{institutionAUserId}** - Should succeed
7. **GET /users/enriched/{institutionBUserId}** - Should fail with 403

**Expected Behavior**:
- ✅ Can access/manage users in their own institution
- ❌ Cannot access/manage users in other institutions (403 Forbidden)
- ✅ Can use `/me` endpoints for self-updates

### 2. Employee Operator (Self-Updates Only)

**Purpose**: Verify Employee Operator can ONLY update themselves, cannot manage other users.

**Test Cases Needed**:

#### Setup Required:
- [ ] Create Employee Operator user
- [ ] **Login Employee Operator** → Store token in `employeeOperatorToken` collection variable
- [ ] Create test user (different user)
- [ ] Store user IDs: `employeeOperatorUserId`, `otherUserId`

#### Test Cases:
1. **GET /users/** - Should return only themselves (or fail with 403)
2. **GET /users/{otherUserId}** - Should fail with 403 (cannot read others)
3. **PUT /users/{otherUserId}** - Should fail with 403 (cannot update others)
4. **GET /users/enriched/{otherUserId}** - Should fail with 403
5. **PUT /users/me** - Should succeed (self-update via `/me`)
6. **GET /users/me** - Should succeed (self-read via `/me`)

**Expected Behavior**:
- ✅ Can use `/me` endpoints for self-updates
- ❌ Cannot access/manage other users (403 Forbidden)
- ❌ Cannot use `/{user_id}` endpoints for others

### 3. Employee Admin vs Employee Management Scope Comparison

**Purpose**: Verify scope differences between global (Admin) and institution-scoped (Management).

**Test Cases Needed**:

#### Setup Required:
- [ ] Employee Admin token (already exists: `employeeAdminToken` collection variable)
- [ ] Employee Management token (needs creation: `employeeManagementToken` collection variable)
- [ ] Test user in Institution A
- [ ] Test user in Institution B

#### Comparison Tests:
1. **GET /users/** - Compare results:
   - Employee Admin: Should see ALL users (global scope)
   - Employee Management: Should see only Institution A users
2. **GET /users/{institutionBUserId}**:
   - Employee Admin: Should succeed (global scope)
   - Employee Management: Should fail with 403 (institution scope)

### 4. Employee Admin vs Employee Super Admin

**Purpose**: Verify both have global scope (they should behave identically for user management).

**Test Cases Needed**:
- [ ] Both should be able to access users from any institution
- [ ] Both should be able to update users from any institution
- [ ] Only Super Admin can approve discretionary requests (already tested)

## Recommended Test Structure

### New Folder: "🔍 Employee Role Scope Tests"

#### Subfolder: "Employee Management (Institution Scope)"
- [ ] Setup: Create Employee Management User
- [ ] **Setup: Login Employee Management** → Store `employeeManagementToken`
- [ ] Setup: Create Test Users (Institution A & B)
- [ ] GET /users/ (should filter by institution) → Uses `{{employeeManagementToken}}`
- [ ] GET /users/{sameInstitutionUserId} (should succeed) → Uses `{{employeeManagementToken}}`
- [ ] GET /users/{differentInstitutionUserId} (should fail 403) → Uses `{{employeeManagementToken}}`
- [ ] PUT /users/{sameInstitutionUserId} (should succeed) → Uses `{{employeeManagementToken}}`
- [ ] PUT /users/{differentInstitutionUserId} (should fail 403) → Uses `{{employeeManagementToken}}`

#### Subfolder: "Employee Operator (Self-Only)"
- [ ] Setup: Create Employee Operator User
- [ ] **Setup: Login Employee Operator** → Store `employeeOperatorToken`
- [ ] Setup: Create Other Test User
- [ ] GET /users/me (should succeed) → Uses `{{employeeOperatorToken}}`
- [ ] PUT /users/me (should succeed) → Uses `{{employeeOperatorToken}}`
- [ ] GET /users/{otherUserId} (should fail 403) → Uses `{{employeeOperatorToken}}`
- [ ] PUT /users/{otherUserId} (should fail 403) → Uses `{{employeeOperatorToken}}`
- [ ] GET /users/enriched/{otherUserId} (should fail 403) → Uses `{{employeeOperatorToken}}`

#### Subfolder: "Scope Comparison Tests"
- [ ] GET /users/ - Employee Admin (all users) → Uses `{{employeeAdminToken}}`
- [ ] GET /users/ - Employee Management (institution only) → Uses `{{employeeManagementToken}}`
- [ ] GET /users/{crossInstitutionUserId} - Employee Admin (should succeed) → Uses `{{employeeAdminToken}}`
- [ ] GET /users/{crossInstitutionUserId} - Employee Management (should fail 403) → Uses `{{employeeManagementToken}}`

## Implementation Checklist

### Phase 1: User Creation Setup
- [ ] Add "Create Employee Management User" request
- [ ] Add "Create Employee Operator User" request
- [ ] Add "Create Test User (Institution A)" request
- [ ] Add "Create Test User (Institution B)" request
- [ ] Store all user IDs in collection variables

### Phase 1.5: Authentication & Token Storage (CRITICAL)
- [ ] Add "Login Employee Management" request
  - [ ] **MUST** store token in `employeeManagementToken` collection variable
  - [ ] **MUST** store user_id in `employeeManagementUserId` collection variable
- [ ] Add "Login Employee Operator" request
  - [ ] **MUST** store token in `employeeOperatorToken` collection variable
  - [ ] **MUST** store user_id in `employeeOperatorUserId` collection variable
- [ ] Verify all existing login requests store tokens in collection variables:
  - [ ] "Login Employee (Admin)" → stores `employeeAdminToken` ✅ (already done)
  - [ ] "Login Super Admin" → stores `employeeSuperAdminToken` ✅ (already done)
  - [ ] "Login Supplier" → stores `supplierAdminToken` ✅ (already done)
  - [ ] "Login Customer" → stores `customerAuthToken` ✅ (already done)

### Phase 2: Employee Management Tests
**CRITICAL: All requests MUST use `employeeManagementToken` collection variable**

- [ ] Add GET /users/ test (should filter by institution)
  - [ ] **MUST** use `{{employeeManagementToken}}` in Authorization header
  - [ ] Add prerequest script to set Authorization header from collection variable
- [ ] Add GET /users/{institutionAUserId} test (should succeed)
  - [ ] **MUST** use `{{employeeManagementToken}}` in Authorization header
- [ ] Add GET /users/{institutionBUserId} test (should fail 403)
  - [ ] **MUST** use `{{employeeManagementToken}}` in Authorization header
- [ ] Add PUT /users/{institutionAUserId} test (should succeed)
  - [ ] **MUST** use `{{employeeManagementToken}}` in Authorization header
- [ ] Add PUT /users/{institutionBUserId} test (should fail 403)
  - [ ] **MUST** use `{{employeeManagementToken}}` in Authorization header
- [ ] Add GET /users/enriched/{institutionAUserId} test (should succeed)
  - [ ] **MUST** use `{{employeeManagementToken}}` in Authorization header
- [ ] Add GET /users/enriched/{institutionBUserId} test (should fail 403)
  - [ ] **MUST** use `{{employeeManagementToken}}` in Authorization header

### Phase 3: Employee Operator Tests
**CRITICAL: All requests MUST use `employeeOperatorToken` collection variable**

- [ ] Add GET /users/me test (should succeed)
  - [ ] **MUST** use `{{employeeOperatorToken}}` in Authorization header
- [ ] Add PUT /users/me test (should succeed)
  - [ ] **MUST** use `{{employeeOperatorToken}}` in Authorization header
- [ ] Add GET /users/{otherUserId} test (should fail 403)
  - [ ] **MUST** use `{{employeeOperatorToken}}` in Authorization header
- [ ] Add PUT /users/{otherUserId} test (should fail 403)
  - [ ] **MUST** use `{{employeeOperatorToken}}` in Authorization header
- [ ] Add GET /users/enriched/{otherUserId} test (should fail 403)
  - [ ] **MUST** use `{{employeeOperatorToken}}` in Authorization header
- [ ] Verify error messages indicate "Employee Operators cannot manage other users"

### Phase 4: Scope Comparison Tests
**CRITICAL: Each test MUST use the appropriate role's token collection variable**

- [ ] Add side-by-side comparison tests for Admin vs Management
  - [ ] GET /users/ - Employee Admin (uses `{{employeeAdminToken}}`)
    - [ ] Should see ALL users (global scope)
  - [ ] GET /users/ - Employee Management (uses `{{employeeManagementToken}}`)
    - [ ] Should see only Institution A users (institution scope)
- [ ] Add cross-institution access comparison
  - [ ] GET /users/{institutionBUserId} - Employee Admin (uses `{{employeeAdminToken}}`)
    - [ ] Should succeed (global scope)
  - [ ] GET /users/{institutionBUserId} - Employee Management (uses `{{employeeManagementToken}}`)
    - [ ] Should fail with 403 (institution scope)

## Collection Variables Needed

### 🔑 **CRITICAL: Token Storage Pattern**

**Every login request MUST:**
1. Store the `access_token` in a collection variable named `{roleType}{roleName}Token`
2. Use the collection variable in ALL subsequent requests for that role
3. Never use environment variables for tokens (collection variables are self-contained)

### Token Collection Variables (Auto-Generated):
- `employeeAdminToken` - Employee Admin auth token (from existing "Login Employee (Admin)")
- `employeeSuperAdminToken` - Employee Super Admin auth token (from existing "Login Super Admin")
- `employeeManagementToken` - Employee Management auth token (NEW - must be stored)
- `employeeOperatorToken` - Employee Operator auth token (NEW - must be stored)
- `supplierAdminToken` - Supplier Admin auth token (from existing "Login Supplier")
- `customerAuthToken` - Customer auth token (from existing "Login Customer")

### User ID Collection Variables:
- `employeeAdminUserId` - Employee Admin user ID
- `employeeSuperAdminUserId` - Employee Super Admin user ID
- `employeeManagementUserId` - Employee Management user ID
- `employeeOperatorUserId` - Employee Operator user ID
- `supplierAdminUserId` - Supplier Admin user ID
- `customerUserId` - Customer user ID
- `institutionAUserId` - Test user in same institution as Management
- `institutionBUserId` - Test user in different institution
- `otherUserId` - Test user for Operator blocking tests

### Institution IDs Needed:
- Institution A: Use existing institution (e.g., `11111111-1111-1111-1111-111111111111` - Vianda Enterprises)
- Institution B: Use different institution (e.g., `33333333-3333-3333-3333-333333333333` - La Parrilla Argentina)

## Test Execution Order

1. **🔧 Test User Setup** (existing)
   - Login Employee Admin
   - Create Supplier User
   - Create Customer User

2. **🔧 Employee Role Setup** (NEW)
   - Create Employee Management User
   - Create Employee Operator User
   - Create Test Users (Institution A & B)

3. **✅ Employee Access Tests** (existing)
   - System config APIs (Plans, Credit Currency, etc.)

4. **🔍 Employee Role Scope Tests** (NEW)
   - Employee Management scope tests
   - Employee Operator blocking tests
   - Scope comparison tests

5. **❌ Supplier Access Tests** (existing)
   - System config denial tests

6. **✅ Customer Access Tests** (existing)
   - Read-only access tests

7. **✅ Super Admin Access Tests** (existing)
   - Discretionary approval tests

## Expected Test Results Summary

| Test Case | Employee Admin | Employee Management | Employee Operator | Supplier Admin | Customer |
|-----------|----------------|---------------------|-------------------|---------------|----------|
| GET /users/ | ✅ All users | ✅ Institution only | ✅ Self only | ✅ Institution only | ✅ Self only |
| GET /users/{sameInstUserId} | ✅ Success | ✅ Success | ❌ 403 | ✅ Success | ✅ Success (if self) |
| GET /users/{diffInstUserId} | ✅ Success | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 403 |
| PUT /users/{sameInstUserId} | ✅ Success | ✅ Success | ❌ 403 | ✅ Success | ❌ 403 |
| PUT /users/{diffInstUserId} | ✅ Success | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 403 |
| PUT /users/me | ✅ Success | ✅ Success | ✅ Success | ✅ Success | ✅ Success |
| GET /users/me | ✅ Success | ✅ Success | ✅ Success | ✅ Success | ✅ Success |

## Priority

### 🔴 **HIGH PRIORITY** - Must Add Before Testing
1. Employee Management scope tests (institution vs global)
2. Employee Operator blocking tests (cannot manage others)

### 🟡 **MEDIUM PRIORITY** - Should Add
3. Scope comparison tests (Admin vs Management side-by-side)
4. Cross-institution access tests

### 🟢 **LOW PRIORITY** - Nice to Have
5. Edge case tests (archived users, etc.)

## 🔑 Token Management Pattern (CRITICAL)

### Login Request Pattern
Every login request MUST follow this pattern:

```javascript
// Test script (after successful login)
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

const response = pm.response.json();
pm.test("Response has access_token", function () {
    pm.expect(response).to.have.property('access_token');
});

// CRITICAL: Store token in collection variable
pm.collectionVariables.set("employeeManagementToken", response.access_token);

// Also store user_id if available
if (response.user_id) {
    pm.collectionVariables.set("employeeManagementUserId", response.user_id);
}
```

### Test Request Pattern
Every test request MUST use the appropriate token collection variable:

```javascript
// Prerequest script (before each test request)
const token = pm.collectionVariables.get("employeeManagementToken");
if (!token) {
    throw new Error("employeeManagementToken not set. Run 'Login Employee Management' first.");
}

// Set Authorization header from collection variable
pm.request.headers.add({
    key: "Authorization",
    value: "Bearer " + token
});
```

### Token Variable Naming Convention
- Format: `{roleType}{roleName}Token`
- Examples:
  - `employeeAdminToken` (Employee + Admin)
  - `employeeSuperAdminToken` (Employee + Super Admin)
  - `employeeManagementToken` (Employee + Management)
  - `employeeOperatorToken` (Employee + Operator)
  - `supplierAdminToken` (Supplier + Admin)
  - `customerAuthToken` (Customer - exception to naming convention)

### Why Collection Variables?
1. **Self-contained**: Collection works independently of environment
2. **Portable**: Can be shared without exposing tokens
3. **Reliable**: Tokens persist across requests in the same collection run
4. **Testable**: Easy to verify token is set before making requests

## Notes

- All new test users should be created with unique usernames/emails (timestamp-based)
- **ALL tokens MUST be stored in collection variables (never environment variables)**
- **ALL test requests MUST use collection variable tokens (never hardcoded or environment tokens)**
- Test users should be created in the setup phase before running scope tests
- Error messages should be verified to ensure they're clear and helpful
- Prerequest scripts should validate token exists before making requests

