# Supplier and Client Access Requirements - Clarification Needed

## Context

Before implementing Phase 2 (Employee-Only Access), we need to clarify what Suppliers and Clients need to access to ensure we don't break existing functionality.

## Phase 2 Scope - System Configuration APIs

The Phase 2 plan only targets **system-level configuration** APIs that should be Employee-only:

1. **Plan Info** (`/plans/*`) - All operations Employee-only
   - ✅ **Safe**: Suppliers and Clients should NOT create/modify plans (these define subscription tiers)

2. **Credit Currency** (`/credit-currencies/*`) - All operations Employee-only
   - ✅ **Safe**: Suppliers and Clients should NOT create/modify currencies (these are system-wide settings)

3. **Discretionary** (`/admin/discretionary/*`) - All operations Employee-only
   - ✅ **Safe**: This is specifically for Employee admins to request discretionary credits (not Suppliers)

4. **Fintech Link** (`/fintech-link/*`)
   - GET: Available to all authenticated users (including Suppliers and Clients - they need to see payment links)
   - POST/PUT/DELETE: Employee-only (configuration management)
   - ⚠️ **Needs Confirmation**: Should Suppliers be able to create their own fintech links?

## Supplier Access Requirements (Backoffice App)

**Suppliers** (`role_type='Supplier'`) need to manage their restaurant's data:

### Confirmed Based on Codebase:
- ✅ **Products** (`/products/*`) - Suppliers need to create/update/delete products
- ✅ **Plates** (`/plates/*`) - Suppliers need to create/update/delete plates
- ✅ **Restaurants** (`/restaurants/*`) - Suppliers need to manage their restaurants
- ✅ **QR Codes** (`/qr-codes/*`) - Suppliers need to create/manage QR codes for their restaurants
- ✅ **Institution Entities** (`/institution-entities/*`) - Suppliers need to manage their entity info
- ✅ **Addresses** (`/addresses/*`) - Suppliers need to manage addresses for their restaurants
- ✅ **Institution Bank Accounts** (`/institution-bank-accounts/*`) - Suppliers need to manage payment accounts
- ✅ **Institution Payment Attempts** - Suppliers need to view their payment history
- ✅ **Institution Bills** - Suppliers need to view their bills

### Questions for Clarification:

1. **Fintech Links**:
   - Can Suppliers create their own fintech links for their restaurants?
   - Or should only Employees create/manage fintech links system-wide?

2. **Plans**:
   - Do Suppliers need to VIEW plans (to understand pricing tiers)?
   - Or should plans be completely hidden from Suppliers?

3. **Credit Currencies**:
   - Do Suppliers need to VIEW credit currencies?
   - Or should currencies be completely hidden from Suppliers?

## Client Access Requirements (iOS/Android Apps)

**Clients** (`role_type='Customer'`) need to:

### Confirmed Based on Codebase:
- ✅ **Public Registration** (`POST /customers/signup`) - Clients can self-register (no auth required)
- ✅ **Plate Selection** (`POST /plate-selection/*`) - Clients need to select plates
- ✅ **Plate Pickup** (`POST /plate-pickup/scan-qr`) - Clients need to scan QR codes to arrive
- ✅ **Pending Orders** (`GET /plate-pickup/pending`) - Clients need to see their pending orders
- ✅ **View Products** - Clients need to see available products
- ✅ **View Plates** - Clients need to see available plates
- ✅ **View Restaurants** - Clients need to see restaurants
- ✅ **View QR Codes** - Clients might need to see QR codes (for scanning)
- ✅ **View Fintech Links** - Clients need to see payment links for plans

### Questions for Clarification:

1. **User Management**:
   - Can Clients update their own profile?
   - Can Clients view their own user data?
   - Can Clients delete their account?

2. **Payment Methods**:
   - Can Clients add payment methods?
   - Can Clients view their payment history?

3. **Bills/Transactions**:
   - Can Clients view their own bills?
   - Can Clients view their transaction history?

## Current Institution Scoping

The existing **institution scoping** already handles most of the access control:

- **Employees**: Global access (can see all institutions)
- **Suppliers**: Scoped to their `institution_id` (can only see/modify their own institution's data)
- **Clients**: May need institution scoping or may need public access (depends on entity)

## Proposed Phase 2 Implementation

### APIs That Will Be Employee-Only (No Impact on Suppliers/Clients):

1. ✅ **Plan Info** - All operations (GET, POST, PUT, DELETE) → Employee-only
   - **Impact**: Suppliers and Clients will NOT be able to create/modify plans
   - **Status**: ✅ Safe - Plans are system configuration

2. ✅ **Credit Currency** - All operations (GET, POST, PUT, DELETE) → Employee-only
   - **Impact**: Suppliers and Clients will NOT be able to create/modify currencies
   - **Status**: ✅ Safe - Currencies are system configuration

3. ✅ **Discretionary Admin Routes** (`/admin/discretionary/*`) - All operations → Employee-only
   - **Impact**: Only Employees can create discretionary credit requests
   - **Status**: ✅ Safe - Suppliers are NOT employees, they can't create discretionary requests anyway

4. ⚠️ **Fintech Link** - POST/PUT/DELETE → Employee-only, GET → All authenticated users
   - **Impact**: Suppliers will NOT be able to create/modify fintech links
   - **Status**: ⚠️ **NEEDS CONFIRMATION** - Can Suppliers create their own fintech links?

### APIs That Will NOT Be Changed (Already Protected by Institution Scoping):

- ✅ **Products** - Suppliers can manage (scoped to their institution)
- ✅ **Plates** - Suppliers can manage (scoped to their institution)
- ✅ **Restaurants** - Suppliers can manage (scoped to their institution)
- ✅ **QR Codes** - Suppliers can manage (scoped to their institution)
- ✅ **Institution Entities** - Suppliers can manage (scoped to their institution)
- ✅ **Addresses** - Suppliers can manage (scoped to their institution)
- ✅ **Institution Bank Accounts** - Suppliers can manage (scoped to their institution)

## Clarifications Received ✅

1. **Plans**:
   - ✅ **GET**: Available to **Clients** (they need to see plans for payment/subscription selection)
   - ❌ **GET**: NOT available to Suppliers (suppliers don't need to see plans)
   - ❌ **POST/PUT/DELETE**: Employee-only (system configuration)

2. **Credit Currency**:
   - ❌ **All operations**: Employee-only (suppliers cannot access API directly)
   - ✅ **Backend usage**: Backend still uses credit_currency data for plate calculations (suppliers see plates with price→credit conversions, but don't access currency API directly)

3. **Discretionary**:
   - ✅ **All operations**: Employee-only (confirmed)

4. **Fintech Link**:
   - ✅ **GET**: Available to **Customers only** (they need to see payment links)
   - ❌ **GET**: NOT available to Suppliers (suppliers don't need to see fintech links)
   - ❌ **POST/PUT/DELETE**: Employee-only (only employees manage these links)

## Updated Phase 2 Implementation Plan

### Plan Info (`/plans/*`)
- **GET** `/plans/` and `/plans/{plan_id}`: Available to **Clients** (`role_type='Customer'`) and **Employees** (`role_type='Employee'`)
- **POST/PUT/DELETE**: Employee-only (`get_employee_user`)

### Credit Currency (`/credit-currencies/*`)
- **All operations** (GET, POST, PUT, DELETE): Employee-only (`get_employee_user`)
- **Backend Note**: Credit currency data is still used internally for plate price→credit calculations when serving plates to suppliers

### Discretionary (`/admin/discretionary/*`)
- **All operations**: Employee-only (`get_employee_user`)

### Fintech Link (`/fintech-link/*`)
- **GET** `/fintech-link/` and `/fintech-link/{fintech_link_id}`: Available to **Customers** (`role_type='Customer'`) only
- **POST/PUT/DELETE**: Employee-only (`get_employee_user`)

## Additional Dependencies Needed

1. **`get_client_or_employee_user()`**: For Plans GET endpoint (Clients and Employees can view)
2. **`get_client_user()`**: For Fintech Link GET endpoint (Customers only)

## Next Steps

1. ✅ **Add new dependencies**: `get_client_user()` and `get_client_or_employee_user()`
2. ✅ **Implement Phase 2** with the clarified access rules
3. ✅ **Test** with Suppliers, Clients, and Employees to ensure proper restrictions

