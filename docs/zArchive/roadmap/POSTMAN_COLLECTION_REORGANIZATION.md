# Postman Collection Reorganization - Restaurant Staff Operations

## Summary of Changes

Successfully reorganized the E2E Plate Selection Postman collection to properly separate customer and restaurant staff operations.

---

## 🔄 Changes Made

### 1. Created New Folder Structure
**New Folder**: `🏪 Restaurant Staff Operations`

**Location**: Positioned after "Logout Customer User" (item #18 in collection)

**Purpose**: Groups all restaurant staff-specific API calls that require Supplier or Employee authentication

### 2. Moved API Calls

The following calls were moved from the main flow into the new folder:

1. **Get Restaurant Daily Orders**
   - Endpoint: `GET /api/v1/restaurant-staff/daily-orders`
   - Requires: Supplier or Employee authentication
   - Purpose: View daily orders with privacy-safe customer names

2. **Generate Daily Bills**
   - Endpoint: `POST /api/v1/institution-bills/generate-daily-bills`
   - Requires: Admin/Supplier authentication
   - Purpose: Generate daily bills for completed orders

### 3. Added Authentication Switching

Both API calls now include pre-request scripts to ensure proper authentication:

#### Get Restaurant Daily Orders - Pre-Request Script:
```javascript
// Switch to Supplier authentication
const supplierToken = pm.environment.get("supplierAuthToken");
if (!supplierToken) {
    throw new Error("❌ No supplier auth token found. Please run 'Login Supplier' first.");
}
pm.environment.set("authToken", supplierToken);
console.log("✅ Using Supplier authentication");
```

#### Generate Daily Bills - Pre-Request Script:
```javascript
// Ensure using Supplier authentication
const supplierToken = pm.environment.get("supplierAuthToken");
if (supplierToken) {
    pm.environment.set("authToken", supplierToken);
}
// ... (existing date calculation code)
```

---

## 📋 New Collection Flow

### Customer Flow (Items 1-17)
1. Authentication & Setup
2. Create Credit Currency
3. ... (other setup steps)
4. Register Client Subscription
5. Create Customer Subscription
6. List Plates for Customer
7. Create Plate Selection
8. Post QR Code Scan
9. **Logout Customer User** ← End of customer flow

### Restaurant Staff Flow (Item 18)
**🏪 Restaurant Staff Operations** folder:
1. Get Restaurant Daily Orders
2. Generate Daily Bills

### Admin/Employee Flow (Items 19+)
1. Login Admin
2. ... (other admin operations)

---

## 🎯 Benefits

### 1. Clear Separation of Concerns
- Customer operations are grouped separately from staff operations
- No more authentication conflicts between customer and staff calls

### 2. Correct Authentication Flow
- Customer logs out before staff operations begin
- Staff operations explicitly require and verify Supplier/Employee authentication

### 3. Better Organization
- Related operations grouped in logical folders
- Easier to understand and maintain the test flow

### 4. Prevents Access Denied Errors
- Pre-request scripts ensure correct authentication token is used
- Clear error messages if authentication is missing

---

## 🚀 How to Use

### Running the Full E2E Flow

1. **Run Customer Flow** (Items 1-17):
   - Starts with Login Customer
   - Goes through subscription, plate selection, QR scan
   - Ends with Logout Customer User

2. **Run Restaurant Staff Flow** (Item 18):
   - **Important**: First login as a Supplier using one of the Login endpoints in the Authentication folder
   - Then run the Restaurant Staff Operations folder
   - Calls will automatically use the Supplier authentication

3. **Run Admin Flow** (Items 19+):
   - Continue with admin operations as needed

### Running Individual Calls

If you want to test just the restaurant staff endpoints:

1. **Login as Supplier** (from Authentication & Setup folder)
2. Navigate to **🏪 Restaurant Staff Operations** folder
3. Run **Get Restaurant Daily Orders**
4. Run **Generate Daily Bills**

---

## ✅ Verification

The reorganization is complete and verified:

- ✅ 2 items moved to new folder
- ✅ Folder positioned after "Logout Customer User"
- ✅ Pre-request authentication scripts added
- ✅ Collection structure maintains logical flow
- ✅ No items duplicated or lost

---

## 📍 API Endpoints Reference

### Get Restaurant Daily Orders
```
GET {{baseUrl}}/api/v1/restaurant-staff/daily-orders

Query Parameters (optional):
- restaurant_id: UUID (filter to specific restaurant)
- order_date: YYYY-MM-DD (defaults to today)

Authentication: Supplier or Employee

Response: Daily orders grouped by restaurant with summary statistics
```

### Generate Daily Bills
```
POST {{baseUrl}}/api/v1/institution-bills/generate-daily-bills?bill_date={{billDate}}

Query Parameters:
- bill_date: YYYY-MM-DD (required)

Authentication: Admin/Supplier

Response: Statistics on bills created
```

---

## 🔍 Testing Notes

### For Suppliers
- Can view orders for all restaurants in their institution_entity
- Can filter by specific restaurant using `restaurant_id` parameter
- Can specify date using `order_date` parameter (defaults to today)

### For Employees
- Can view orders for any restaurant
- **Must** specify `restaurant_id` parameter
- This is by design for support/admin purposes

### Expected Responses

**Customer trying to access (should fail)**:
```json
{
  "detail": "Access denied: Must be Supplier or Employee role"
}
```

**Supplier without authentication (should fail)**:
```json
{
  "detail": "❌ No supplier auth token found. Please run 'Login Supplier' first."
}
```

**Successful request**:
```json
{
  "date": "2026-02-04",
  "restaurants": [
    {
      "restaurant_id": "uuid",
      "restaurant_name": "Restaurant Name",
      "orders": [...],
      "summary": {
        "total_orders": 15,
        "pending": 10,
        "arrived": 3,
        "completed": 2
      }
    }
  ]
}
```

---

## 📝 Summary

The Postman collection has been successfully reorganized to:
- Separate customer and restaurant staff operations
- Ensure proper authentication for each operation type
- Provide clear, logical flow for E2E testing
- Prevent authentication-related errors

The new structure makes it easier to test both customer-facing and staff-facing features independently or as part of the full E2E flow.
