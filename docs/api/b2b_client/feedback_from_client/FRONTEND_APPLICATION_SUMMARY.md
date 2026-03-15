# Vianda Platform Frontend Application Summary

## Top-Level Configuration

### Language & Framework
- **Language**: TypeScript (ES2020 target)
- **Framework**: React 18.3.1
- **Build Tool**: Vite 5.2.10
- **Module System**: ESNext modules with Node resolution

### Key Dependencies
- **React Router DOM**: ^6.23.1 - Client-side routing
- **Axios**: ^1.7.4 - HTTP client for API requests
- **React**: ^18.3.1 - UI framework
- **React DOM**: ^18.3.1 - React rendering

### Development Tools
- **TypeScript**: ^5.4.5 - Type checking
- **ESLint**: ^8.57.0 - Code linting
- **Vite React Plugin**: ^4.2.1 - React support for Vite

### Build Configuration
- **Development Server**: Port 5173
- **Preview Server**: Port 4173
- **API Base URL**: Configurable via `VITE_API_BASE_URL` environment variable (defaults to `http://localhost:8000`)

## Key Highlights from CLAUDE.MD

### Authentication
- Uses OAuth2 password flow (`POST /v1/auth/token`)
- Bearer token stored in localStorage and attached to all API requests via Axios interceptors
- Automatic 401 handling redirects to login page

### RBAC Awareness
- JWT includes `role_type`, `role_name`, and `institution_id`
- UI visibility driven by user role (employee vs. restaurant_admin)
- Scoped data access based on institution_id

### Enriched Endpoint Pattern
- **Enriched endpoints** (`/enriched/` suffix) return denormalized data with related entity names
- Eliminates N+1 queries by using SQL JOINs
- Used when UI needs to display related entity names (e.g., `role_name`, `institution_name`)
- Base endpoints used when only raw UUIDs are needed

### Decimal Handling
- Monetary fields returned as strings from FastAPI (Decimal serialization)
- Client-side parsing with care to avoid floating-point issues

### Client-Side Transformations
The application performs several client-side transformations that could potentially be moved to the backend:
- String formatting (null/undefined handling)
- Date formatting (`formatDate`)
- Boolean to string conversion (`formatBoolean` - "Yes"/"No")
- Number formatting with thousand separators (`formatNumber`, `formatPrice`)
- String concatenation (e.g., `full_name` from enriched endpoints)

## Application Structure

The application is organized into three main sections in the navigation menu:

1. **Core** - Core platform management features
2. **Supplier** - Restaurant and institution management
3. **Customers** - Customer-facing features and data

**Note**: The UI currently displays "Clients" in the navigation menu, but this should be replaced with "Customers" for consistency.

---

## Core Section

### 1. Addresses

**Route**: `/addresses`  
**API Endpoint**: `GET /api/v1/addresses/enriched/` (Enriched)  
**Component**: `AddressesPage`

**Table Columns**:
- Institution Name
- Full Name
- Status
- Country
- Province
- City
- Postal Code

**Data Transformation**:
- `institution_name` → `institutionName` (formatted)
- `user_full_name` → `fullName` (formatted)
- `postal_code` → `postalCode` (formatted)

---

### 2. Credit Currencies

**Route**: `/credit-currencies`  
**API Endpoint**: `GET /api/v1/credit-currencies/` (Base)  
**Component**: `CreditCurrenciesPage`

**Table Columns**:
- Currency Name
- Currency Code
- Credit Value
- Status
- Modified Date

**Data Transformation**:
- `credit_value` → `creditValue` (formatted as integer)
- `modified_date` → `modifiedDate` (formatted date)

---

### 3. Discretionary

**Route**: `/discretionary`  
**API Endpoint**: `GET /api/v1/super-admin/discretionary/pending-requests/` (Base)  
**Component**: `DiscretionaryRequestsPage`

**Table Columns** (Custom table, not using ResourcePage):
- Request ID
- User
- Restaurant
- Category
- Reason
- Amount
- Created
- Actions

**Data Transformation**:
- `amount` → formatted with 2 decimal places
- `created_date` → formatted date/time

**Note**: This page uses a custom table implementation rather than the standard `ResourcePage` component.

---

### 4. Fintech Links

**Route**: `/fintech-links`  
**API Endpoint**: `GET /api/v1/fintech-links/enriched/` (Enriched)  
**Component**: `FintechLinksPage`

**Table Columns**:
- Provider
- Fintech Link
- Plan Name
- Price
- Currency Code
- Credit
- Status

**Data Transformation**:
- `price` → formatted as currency
- `credit` → formatted as string

---

### 5. National Holidays

**Route**: `/national-holidays`  
**API Endpoint**: `GET /api/v1/national-holidays/` (Base)  
**Component**: `NationalHolidaysPage`

**Table Columns**:
- Country Code
- Holiday Name
- Holiday Date
- Is Recurring
- Recurring Month
- Recurring Day

**Data Transformation**:
- `holiday_date` → formatted date
- `is_recurring` → "Yes"/"No"
- `recurring_month` → month name (e.g., "January")
- `recurring_day` → formatted string

---

### 6. Plans

**Route**: `/plans`  
**API Endpoint**: `GET /api/v1/plans/enriched/` (Enriched)  
**Component**: `PlansPage`

**Table Columns**:
- Plan Name
- Price
- Currency Code
- Credit
- Rollover
- Status

**Data Transformation**:
- `name` → `planName`
- `price` → formatted as currency
- `credit` → formatted as string
- `rollover` → "Yes"/"No"

---

### 7. Users

**Route**: `/users`  
**API Endpoint**: `GET /api/v1/users/enriched/` (Enriched)  
**Component**: `UsersPage`

**Table Columns**:
- Full Name
- Username
- Email
- Status
- Role Name
- Institution Name

**Data Transformation**:
- `full_name` → `fullName` (formatted)
- `role_name` → `roleName`
- `institution_name` → `institutionName`

---

## Supplier Section

### 1. Institution Banking

**Route**: `/institution-banking`  
**API Endpoint**: `GET /api/v1/institution-bank-accounts/enriched/` (Enriched)  
**Component**: `InstitutionBankingPage`

**Table Columns**:
- Institution Name
- Entity Name
- Country
- Bank Name
- Account Type
- Status

**Data Transformation**:
- Direct mapping from enriched endpoint (no additional formatting)

---

### 2. Institution Billing

**Route**: `/billing`  
**API Endpoint**: `GET /api/v1/institution-bills/enriched/` (Enriched)  
**Component**: `BillingPage`

**Table Columns**:
- Institution Name
- Institution Entity Name
- Restaurant Name
- Currency Code
- Transaction Count
- Amount
- Period Start
- Period End
- Status
- Resolution

**Data Transformation**:
- `transaction_count` → formatted as string
- `amount` → formatted with 2 decimal places and thousand separators
- `period_start` → formatted date
- `period_end` → formatted date
- `resolution` → "—" if null

**Note**: This page uses a custom column definition rather than importing from `columnConfigs.ts`.

---

### 3. Institution Entities

**Route**: `/institution-entities`  
**API Endpoint**: `GET /api/v1/institution-entities/enriched/?include_archived=false` (Enriched)  
**Component**: `InstitutionEntitiesPage`

**Table Columns**:
- Institution Name
- Entity Name
- Tax ID
- Country
- Province
- City

**Data Transformation**:
- `name` → `entityName`
- `address_country` → `country` (formatted)
- `address_province` → `province` (formatted)
- `address_city` → `city`

---

### 4. Institutions

**Route**: `/institutions`  
**API Endpoint**: `GET /api/v1/institutions/` (Base)  
**Component**: `InstitutionsPage`

**Table Columns**:
- Name
- Status
- Modified Date

**Data Transformation**:
- `modified_date` → `modifiedDate` (formatted date)

---

### 5. Kitchen Days

**Route**: `/kitchen-days`  
**API Endpoint**: `GET /api/v1/plate-kitchen-days/enriched/` (Enriched)  
**Component**: `KitchenDaysPage`

**Table Columns**:
- Institution Name
- Restaurant Name
- Plate Name
- Dietary
- Kitchen Day
- Status

**Data Transformation**:
- `dietary` → formatted string

---

### 6. Payment Attempts

**Route**: `/institution-payment-attempts`  
**API Endpoint**: `GET /api/v1/institution-payment-attempts/enriched/` (Enriched)  
**Component**: `InstitutionPaymentAttemptsPage`

**Table Columns**:
- Institution Name
- Country
- Entity Name
- Bank Name
- Currency Code
- Amount
- Status

**Data Transformation**:
- `amount` → formatted with 2 decimal places

---

### 7. Pickups

**Route**: `/pickups`  
**API Endpoint**: `GET /api/v1/plate-pickup/enriched` (Enriched)  
**Component**: `PickupMonitorPage`

**Table Columns**:
- Restaurant Name
- Product Name
- Credit
- Was Collected
- Status
- Arrival Time
- Expected Completion Time
- Completion Time

**Data Transformation**:
- `credit` → formatted as string
- `was_collected` → "Yes"/"No"
- `arrival_time` → formatted date/time
- `expected_completion_time` → formatted date/time
- `completion_time` → formatted date/time

**Note**: This page uses a custom column definition rather than importing from `columnConfigs.ts`.

---

### 8. Plates

**Route**: `/plates`  
**API Endpoint**: `GET /api/v1/plates/enriched/` (Enriched)  
**Component**: `PlatesPage`

**Table Columns**:
- Institution Name
- Product Name
- Restaurant Name
- Price
- Credit
- Has Image
- Status

**Data Transformation**:
- `price` → formatted as currency
- `credit` → formatted as string
- `has_image` → "Yes"/"No"

---

### 9. Products

**Route**: `/products`  
**API Endpoint**: `GET /api/v1/products/enriched/` (Enriched)  
**Component**: `ProductsPage`

**Table Columns**:
- Institution Name
- Product Name
- Dietary
- Has Image
- Status

**Data Transformation**:
- `name` → `productName`
- `dietary` → formatted string
- `has_image` → "Yes"/"No"

---

### 10. QR Codes

**Route**: `/qr-codes`  
**API Endpoint**: `GET /api/v1/qr-codes/enriched/` (Enriched)  
**Component**: `QRCodesPage`

**Table Columns**:
- Institution Name
- Restaurant Name
- Country
- Province
- City
- Zipcode
- Has Image
- Status

**Data Transformation**:
- `country` → formatted string
- `province` → formatted string
- `postal_code` → `zipcode` (formatted)
- `has_image` → "Yes"/"No"

---

### 11. Restaurant Balance

**Route**: `/restaurant-balance`  
**API Endpoint**: `GET /api/v1/restaurant-balances/enriched/` (Enriched)  
**Component**: `RestaurantBalancePage`

**Table Columns**:
- Institution Name
- Country
- Entity Name
- Restaurant Name
- Currency Code
- Balance
- Transaction Count
- Status

**Data Transformation**:
- `balance` → formatted with 2 decimal places
- `transaction_count` → formatted as string

---

### 12. Restaurant Holidays

**Route**: `/restaurant-holidays`  
**API Endpoint**: `GET /api/v1/restaurant-holidays/enriched/` (Enriched)  
**Component**: `RestaurantHolidaysPage`

**Table Columns**:
- Institution Name
- Restaurant Name
- Holiday Name
- Holiday Date
- Is Editable
- Status

**Data Transformation**:
- `institution_name` → formatted string
- `restaurant_name` → formatted string
- `holiday_date` → formatted date
- `is_editable` → "Yes"/"No"

---

### 13. Restaurant Transactions

**Route**: `/restaurant-transactions`  
**API Endpoint**: `GET /api/v1/restaurant-transactions/enriched/` (Enriched)  
**Component**: `RestaurantTransactionsPage`

**Table Columns**:
- Institution Name
- Country
- Entity Name
- Restaurant Name
- Transaction Type
- Plate Name
- Currency Code
- Credit
- Was Collected
- Status

**Data Transformation**:
- `credit` → formatted as string
- `was_collected` → "Yes"/"No"

---

### 14. Restaurants

**Route**: `/restaurants`  
**API Endpoint**: `GET /api/v1/restaurants/enriched/` (Enriched)  
**Component**: `RestaurantOnboardingPage`

**Table Columns**:
- Institution Name
- Country
- Province
- City
- Zipcode
- Restaurant Name
- Cuisine
- Status

**Data Transformation**:
- `country` → formatted string
- `province` → formatted string
- `postal_code` → `zipcode` (formatted)
- `name` → `restaurantName`
- `cuisine` → formatted string

---

## Customers Section

### 1. Employers

**Route**: `/employers`  
**API Endpoint**: `GET /api/v1/employers/enriched/` (Enriched)  
**Component**: `EmployersPage`

**Table Columns**:
- Name
- Country
- Province
- City
- Status

**Data Transformation**:
- `country` → formatted string
- `province` → formatted string
- `city` → formatted string

---

### 2. Fintech Link Assignments

**Route**: `/fintech-link-assignments`  
**API Endpoint**: `GET /api/v1/fintech-link-assignment/enriched/` (Enriched)  
**Component**: `FintechLinkAssignmentsPage`

**Table Columns**:
- Provider
- Plan Name
- Full Name
- Username
- Email
- Credit
- Price
- Status

**Data Transformation**:
- `full_name` → formatted string
- `username` → formatted string
- `email` → formatted string
- `credit` → formatted as string
- `price` → formatted as currency

---

### 3. Payment Methods

**Route**: `/payment-methods`  
**API Endpoint**: `GET /api/v1/payment-methods/enriched/` (Enriched)  
**Component**: `PaymentMethodsPage`

**Table Columns**:
- Username
- Full Name
- Email
- Method Type
- Status
- Is Default

**Data Transformation**:
- `username` → formatted string
- `full_name` → formatted string
- `email` → formatted string
- `method_type` → formatted string
- `is_default` → "Yes"/"No"

---

### 4. Subscriptions

**Route**: `/subscriptions`  
**API Endpoint**: `GET /api/v1/subscriptions/enriched/` (Enriched)  
**Component**: `SubscriptionsPage`

**Table Columns**:
- Plan Name
- Full Name
- Username
- Email
- Balance
- Renewal Date
- Status
- Modified Date

**Data Transformation**:
- `plan_name` → `planName`
- `user_full_name` → `fullName`
- `user_username` → `username`
- `user_email` → `email`
- `balance` → formatted as integer
- `renewal_date` → formatted date
- `modified_date` → formatted date

---

## Summary Statistics

### API Endpoint Usage
- **Enriched Endpoints**: 23 views
- **Base Endpoints**: 4 views (Credit Currencies, Discretionary, National Holidays, Institutions)
- **Custom Endpoints**: 1 view (Discretionary uses `/super-admin/discretionary/pending-requests/`)

### Common Patterns
1. **Enriched endpoints** are used for 85% of views to display related entity names
2. **Client-side transformations** are applied for:
   - Date formatting (all date fields)
   - Boolean to "Yes"/"No" conversion
   - Number formatting with thousand separators
   - String null/undefined handling
3. **Column configurations** are centralized in `src/utils/columnConfigs.ts` for most views
4. **Data fetching** uses the `useResourceData` hook for consistent error handling and loading states

### Navigation Menu Update Required
The navigation menu in `src/components/Layout.tsx` currently displays "Clients" but should be updated to "Customers" for consistency with the application terminology.
