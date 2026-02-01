# Permissions Testing Guide - Employee-Only Access

## Overview

This Postman collection tests the employee-only access control system, verifying that system configuration APIs are properly protected based on `role_type` and `role_name`.

## Collection Structure

### 🔧 Test User Setup
- **Login Employee (Admin) - For User Creation** - Login as Employee Admin to create test users
- **Create Supplier Test User** - Employee Admin creates a Supplier user with unique username/email
- **Login Supplier (Newly Created)** - Login as the newly created Supplier user
- **Create Customer Test User** - Employee Admin creates a Customer user with unique username/email
- **Login Customer (Newly Created)** - Login as the newly created Customer user

**Note**: All credentials are stored in **collection variables** (not environment variables), making the collection self-contained and independent of database state.

### 🔐 Authentication
- **Login Employee (Admin)** - Authenticate as Employee with Admin role_name
- **Login Super Admin** - Authenticate as Super Admin (Employee + Super Admin)

### ✅ Employee Access Tests (Should Succeed)
- **Plans - GET (Employee)** - Employee can view plans
- **Plans - POST (Employee)** - Employee can create plans
- **Credit Currency - GET (Employee)** - Employee can view credit currencies
- **Discretionary - GET Requests (Employee)** - Employee can view discretionary requests
- **Fintech Link - GET (Employee)** - Employee can view fintech links
- **Fintech Link - POST (Employee)** - Employee can create fintech links

### ❌ Supplier Access Tests (Should Fail - 403)
- **Plans - GET (Supplier)** - Supplier should be denied access
- **Credit Currency - GET (Supplier)** - Supplier should be denied access
- **Discretionary - GET (Supplier)** - Supplier should be denied access
- **Fintech Link - GET (Supplier)** - Supplier should be denied access

### ✅ Customer Access Tests
- **Plans - GET (Customer)** - Customer can view plans (for subscription selection)
- **Fintech Link - GET (Customer)** - Customer can view fintech links (for payment)
- **Fintech Link - POST (Customer)** - Customer should be denied (403)

### ✅ Super Admin Access Tests
- **Discretionary - Approve (Super Admin)** - Super Admin can approve requests
- **Discretionary - Get Pending (Super Admin)** - Super Admin can view pending requests

### ❌ Employee Admin - Approve Test (Should Fail)
- **Discretionary - Approve (Employee Admin)** - Regular Employee Admin should be denied (only Super Admin can approve)

## Environment Variables

### Required Environment Variables
Only these environment variables are needed (all other credentials are stored in collection variables):

```json
{
  "baseUrl": "http://localhost:8000",
  "adminUsername": "admin",
  "adminPassword": "admin_password",
  "superAdminUsername": "superadmin",
  "superAdminPassword": "super_secret",
  "testPlanId": "uuid-here (optional, only if testing Fintech Link POST)",
  "testDiscretionaryRequestId": "uuid-here (optional, only if testing Discretionary approval)"
}
```

### Collection Variables (Auto-Generated)
These variables are automatically created and stored by the collection during execution:

- `employeeAuthToken` - Employee Admin authentication token
- `supplierUsername` - Automatically generated supplier username (e.g., `test_supplier_1234567890`)
- `supplierPassword` - Supplier password (`SupplierPassword123!`)
- `supplierAuthToken` - Supplier authentication token
- `customerUsername` - Automatically generated customer username (e.g., `test_customer_1234567890`)
- `customerPassword` - Customer password (`CustomerPassword123!`)
- `customerAuthToken` - Customer authentication token
- `superAdminAuthToken` - Super Admin authentication token

### How It Works

1. **Test User Setup** section runs first:
   - Employee Admin logs in (uses environment variables)
   - Employee Admin creates Supplier user with unique username/email (timestamp-based)
   - Supplier user logs in immediately after creation
   - Employee Admin creates Customer user with unique username/email (timestamp-based)
   - Customer user logs in immediately after creation

2. **All credentials are stored in collection variables** (not environment variables), making the collection self-contained and independent of database rebuilds.

3. **Authentication** section provides login endpoints for manual testing if needed.

### Note on Test Users

**Seeded Users** (from `app/db/seed.sql`):
- ✅ **Admin**: `admin` / `admin_password` (Employee + Admin)
- ✅ **Super Admin**: `superadmin` / `super_secret` (Employee + Super Admin)

**Auto-Generated Test Users** (created by collection):
- ✅ **Supplier**: Created automatically with unique `test_supplier_<timestamp>` username
  - Institution: `11111111-1111-1111-1111-111111111111` (La Parrilla Argentina)
  - Role: `bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb` (Supplier - Admin)
  - Password: `SupplierPassword123!`
- ✅ **Customer**: Created automatically with unique `test_customer_<timestamp>` username
  - Institution: `44444444-4444-4444-4444-444444444444` (Vianda Customers)
  - Role: `cccccccc-cccc-cccc-cccc-cccccccccccc` (Customer - Comensal)
  - Password: `CustomerPassword123!`

## Expected Results

### ✅ Success Indicators (200/201)
- Employees can access all system configuration APIs (Plans, Credit Currency, Discretionary)
- Super Admins can approve/disapprove discretionary requests
- Customers can view Plans and Fintech Links (GET only)
- All authentication tokens are properly set

### ❌ Access Denied Indicators (403)
- Suppliers cannot access any system configuration APIs
- Customers cannot POST/PUT/DELETE Fintech Links
- Employee Admins cannot approve discretionary requests (only Super Admin can)

### Error Messages
All 403 errors should include clear messages indicating why access was denied:
- "Employee access required for system configuration operations"
- "Customer access required for this operation"
- "Super-admin access required for discretionary credit operations"

## Testing Checklist

- [ ] Employee can access Plan APIs (GET, POST)
- [ ] Employee can access Credit Currency APIs
- [ ] Employee can access Discretionary APIs (GET, POST, PUT)
- [ ] Employee can access Fintech Link APIs (GET, POST)
- [ ] Supplier is denied access to Plan APIs (403)
- [ ] Supplier is denied access to Credit Currency APIs (403)
- [ ] Supplier is denied access to Discretionary APIs (403)
- [ ] Supplier is denied access to Fintech Link APIs (403)
- [ ] Customer can view Plans (200)
- [ ] Customer can view Fintech Links (200)
- [ ] Customer is denied POST/PUT/DELETE on Fintech Links (403)
- [ ] Super Admin can approve discretionary requests (200/201)
- [ ] Employee Admin cannot approve discretionary requests (403)
- [ ] Error messages are clear and consistent

## Running the Tests

1. **Set up environment variables** in Postman (only Admin and Super Admin credentials required)
   - `baseUrl`: `http://localhost:8000`
   - `adminUsername`: `admin`
   - `adminPassword`: `admin_password`
   - `superAdminUsername`: `superadmin`
   - `superAdminPassword`: `super_secret`

2. **Run the "🔧 Test User Setup" folder first** (this automatically creates and authenticates Supplier and Customer users)
   - **Important**: Run the entire folder using "Run folder" or run requests sequentially (don't skip the login step!)
   - The first request ("Login Employee (Admin) - For User Creation") stores the token in `employeeAuthToken` collection variable
   - Subsequent requests use this token for authentication
   - All credentials are stored in collection variables automatically
   - No manual user creation needed!
   - **If you get 401 "Not authenticated"**: Make sure you ran the login request first and wait for it to complete before running user creation requests

3. **Run the remaining test folders**:
   - **🔐 Authentication** - Manual login endpoints (optional, for testing)
   - **✅ Employee Access Tests** - Should return 200/201
   - **❌ Supplier Access Tests** - Should return 403
   - **✅ Customer Access Tests** - GET should return 200, POST should return 403
   - **✅ Super Admin Access Tests** - Should return 200/201
   - **❌ Employee Admin - Approve Test** - Should return 403

4. **Verify error messages** are clear and helpful

## Troubleshooting

### 401 "Not authenticated" When Creating Users
This error occurs when the `employeeAuthToken` collection variable is not set before running the user creation request.

**Solution**:
1. **Make sure you run requests in order**: Always run "Login Employee (Admin) - For User Creation" first
2. **Wait for login to complete**: Let the login request finish completely (the test script sets the collection variable after the response)
3. **Check collection variables**: Open Postman's "Variables" tab and verify `employeeAuthToken` is set after login
4. **Run as folder**: Use Postman's "Run folder" feature to execute all requests in the "🔧 Test User Setup" folder sequentially
5. **Check console**: The pre-request script will log an error if the token is missing

**Alternative**: If running requests individually, manually check that the `employeeAuthToken` collection variable exists and contains a valid JWT token after the login request completes.

### 403 Errors When Expected to Succeed
- ✅ Check that the user has the correct `role_type` in the database
- ✅ Verify the JWT token includes `role_type` and `role_name`
- ✅ Check that the API endpoint uses the correct dependency (`get_employee_user()`, etc.)

### 200/201 When Expected to Fail
- ❌ Verify that the route is using the correct dependency
- ❌ Check that `get_employee_user()` is checking `role_type == "Employee"`
- ❌ Ensure no global access is being granted incorrectly

