# Enriched Endpoint Pattern

## Overview

The FastAPI backend implements an **Enriched Endpoint Pattern** to eliminate N+1 queries when the UI needs to display related entity names (e.g., `role_name`, `institution_name`) alongside base entity data.

## Problem Statement

When base endpoints only return foreign key IDs (e.g., `role_id`, `institution_id`), the UI would need to:
- Make N+1 queries (one for the list + one per related entity)
- Or make multiple round trips to fetch related data separately

This results in poor performance and a complex frontend implementation.

## Solution: Enriched Endpoints

The backend provides dedicated `/enriched/` endpoints that use SQL JOINs to return denormalized data in a single query. This eliminates N+1 queries and provides a better developer experience.

## Pattern Structure

### Base Endpoints (Standard)
- `GET /users/` → Returns `UserResponseSchema` with `role_id` and `institution_id` (UUIDs)
- `GET /users/{user_id}` → Returns `UserResponseSchema` with `role_id` and `institution_id` (UUIDs) ⚠️ **DEPRECATED for self-reads** (use `GET /users/me`)

### Enriched Endpoints (New Pattern)
- `GET /api/v1/users/enriched/` → Returns `UserEnrichedResponseSchema` with `role_name`, `role_type`, and `institution_name`
- `GET /api/v1/users/enriched/{user_id}` → Returns `UserEnrichedResponseSchema` with `role_name`, `role_type`, and `institution_name` ⚠️ **DEPRECATED for self-reads** (use `GET /users/me` which returns enriched data)
- `GET /users/me` → Returns `UserEnrichedResponseSchema` with `role_name`, `role_type`, and `institution_name` ✅ **NEW: Use this for self-reads**

## Implementation Details

### Response Schema Structure

**Base Schema** (`UserResponseSchema`):
```json
{
  "user_id": "uuid",
  "institution_id": "uuid",
  "role_id": "uuid",
  "username": "string",
  "email": "string",
  "first_name": "string",
  "last_name": "string",
  "status": "string",
  // ... other fields
}
```

**Enriched Schema** (`UserEnrichedResponseSchema`):
```json
{
  "user_id": "uuid",
  "institution_id": "uuid",
  "institution_name": "string",  // ← Denormalized from institution_info
  "role_id": "uuid",
  "role_name": "string",          // ← Denormalized from role_info
  "role_type": "string",          // ← Denormalized from role_info
  "username": "string",
  "email": "string",
  "first_name": "string",
  "last_name": "string",
  "status": "string",
  // ... other fields (same as base schema)
}
```

### Key Features

1. **Single Query**: Uses SQL JOINs to fetch all data in one database round trip
2. **Backward Compatible**: Base endpoints remain unchanged
3. **Automatic Scoping**: Enriched endpoints automatically filter results based on user role type:
   - Employees see all records (global access)
   - Suppliers see records from their institution
   - Customers see their own records (for user-scoped resources) or institution records (for standard resources)
4. **Same Filtering**: Supports `include_archived` parameter like base endpoints
5. **No Client-Side Filtering Needed**: The backend handles all scoping logic automatically
6. **Centralized Implementation**: All enriched endpoints use the `EnrichedService` class, ensuring consistency and maintainability

## When to Use

### Use Enriched Endpoints When:
- ✅ UI needs to display related entity names frequently (e.g., user list with role/institution names)
- ✅ You want to avoid multiple API calls or N+1 queries
- ✅ Performance is important (fewer round trips = faster page loads)

### Use Base Endpoints When:
- ✅ UI only needs the entity itself
- ✅ UI will fetch related data separately (e.g., lazy loading)
- ✅ You need the raw UUIDs for further operations

## API Endpoints Reference

### Users Enriched Endpoints

**List Enriched Users**
```
GET /api/v1/users/enriched/
Query Parameters:
  - include_archived: bool (optional, default: false)
    - If false (or omitted), only returns active users (is_archived = FALSE)
    - If true, includes archived users in the response
    - **Recommendation**: Omit parameter to use safe default
  
Response: List[UserEnrichedResponseSchema]
```

**Get Single Enriched User**
```
GET /api/v1/users/enriched/{user_id}
Path Parameters:
  - user_id: UUID
  
Query Parameters:
  - include_archived: bool (optional, default: false)
    - If false (or omitted), only returns active users (is_archived = FALSE)
    - If true, includes archived users in the response
    - **Recommendation**: Omit parameter to use safe default
  
Response: UserEnrichedResponseSchema
```

**Note**: See [Archived Records Pattern](./ARCHIVED_RECORDS_PATTERN.md) for complete documentation on how `include_archived` works across all endpoints.

## Authentication & Authorization

- **Authentication**: Bearer token required (same as base endpoints)
- **Authorization**: Respects scoping rules based on user role type and resource type

### Scoping Behavior

Enriched endpoints automatically filter results based on the authenticated user's role type:

#### Standard Institution Scoping (Most Entities)
For most enriched endpoints (users, restaurants, products, etc.):
- **Employees** (`role_type = "Employee"`): See all records across all institutions (global access)
- **Suppliers** (`role_type = "Supplier"`): See only records from their institution (`institution_id` match)
- **Customers** (`role_type = "Customer"`): See only records from their institution (if applicable)

#### User-Level Scoping (Special Cases)
For certain enriched endpoints that track user-specific data (e.g., plate pickups):
- **Employees** (`role_type = "Employee"`): See all records across all institutions (global access)
- **Suppliers** (`role_type = "Supplier"`): See records for restaurants in their institution (filtered by restaurant's `institution_id`)
- **Customers** (`role_type = "Customer"`): See only their own records (filtered by `user_id`)

**Example**: The `/plate-pickup/enriched/` endpoint:
- Employees see all plate pickups from all restaurants
- Suppliers see plate pickups for restaurants belonging to their institution
- Customers see only their own plate pickups

**Note**: The UI does not need to implement any filtering logic - the backend automatically applies the correct scoping based on the authenticated user's role type.

## Error Handling

- **404 Not Found**: User doesn't exist or is outside user's institution scope
- **500 Internal Server Error**: Database or system error
- **401 Unauthorized**: Missing or invalid authentication token
- **403 Forbidden**: User doesn't have permission to access the resource

## Full Name Fields

Enriched endpoints that include user information automatically include a `full_name` field that concatenates `first_name` and `last_name`:

- **User Enriched Endpoints**: Include `full_name` field
- **Address Enriched Endpoints**: Include `user_full_name` field

The `full_name` is computed in SQL using `TRIM(COALESCE(CONCAT_WS(' ', first_name, last_name), ''))`, which:
- Handles NULL values gracefully (skips NULL parts automatically)
- Returns empty string `""` if both names are NULL
- Returns only the non-NULL name if one is missing (e.g., `"John"` or `"Doe"`)
- Returns properly formatted `"First Last"` if both are present (e.g., `"John Doe"`)
- No extra spaces or formatting issues

**Benefits:**
- Consistent name formatting across all clients
- No client-side concatenation logic needed
- Handles edge cases (NULL values) automatically

## Available Enriched Endpoints

The following enriched endpoints are currently available:

### User Management
- `GET /api/v1/users/enriched/` - Users with role and institution names
- `GET /api/v1/users/enriched/{user_id}` - Single user with role and institution names

### Institution & Address Management
- `GET /institution-entities/enriched/` - Institution entities with institution and address details
- `GET /institution-entities/enriched/{entity_id}` - Single entity with institution and address details
- `GET /addresses/enriched/` - Addresses with institution and user details
- `GET /addresses/enriched/{address_id}` - Single address with institution and user details

### Restaurant & Product Management
- `GET /restaurants/enriched/` - Restaurants with institution, entity, and address details
- `GET /restaurants/enriched/{restaurant_id}` - Single restaurant with institution, entity, and address details
- `GET /restaurant-balances/enriched/` - Restaurant balances with institution, entity, restaurant, and address details (read-only)
- `GET /restaurant-balances/enriched/{restaurant_id}` - Single restaurant balance with institution, entity, restaurant, and address details (read-only)
- `GET /restaurant-transactions/enriched/` - Restaurant transactions with institution, entity, restaurant, plate, and address details (read-only)
- `GET /restaurant-transactions/enriched/{transaction_id}` - Single restaurant transaction with institution, entity, restaurant, plate, and address details (read-only)
- `GET /restaurant-holidays/enriched/` - Restaurant holidays with applicable national holidays (includes both restaurant-specific and national holidays)
- `GET /restaurant-holidays/enriched/{restaurant_id}` - Restaurant holidays for a specific restaurant with applicable national holidays
- `GET /qr-codes/enriched/` - QR codes with restaurant, institution, and address details
- `GET /qr-codes/enriched/{qr_code_id}` - Single QR code with restaurant, institution, and address details
- `GET /products/enriched/` - Products with institution names
- `GET /products/enriched/{product_id}` - Single product with institution name
- `GET /plates/enriched/` - Plates with institution, restaurant, product, and address details
- `GET /plates/enriched/{plate_id}` - Single plate with institution, restaurant, product, and address details
- `GET /plate-kitchen-days/enriched/` - Plate kitchen day assignments with institution, restaurant, plate, and product details
- `GET /plate-kitchen-days/enriched/{kitchen_day_id}` - Single plate kitchen day assignment with institution, restaurant, plate, and product details

### Subscription & Billing
- `GET /subscriptions/enriched/` - Subscriptions with user and plan details
- `GET /subscriptions/enriched/{subscription_id}` - Single subscription with user and plan details
- `GET /institution-bills/enriched/` - Institution bills with institution, entity, and restaurant names
- `GET /institution-bank-accounts/enriched/` - Bank accounts with institution, entity, and address details
- `GET /institution-payment-attempts/enriched/` - Payment attempts with institution, entity, bank account, and bill details
- `GET /institution-payment-attempts/enriched/{payment_id}` - Single payment attempt with institution, entity, bank account, and bill details

### Plans & Payment
- `GET /plans/enriched/` - Plans with currency name and code
- `GET /plans/enriched/{plan_id}` - Single plan with currency name and code
- `GET /fintech-link/enriched/` - Fintech links with plan and currency details
- `GET /fintech-link/enriched/{fintech_link_id}` - Single fintech link with plan and currency details

### Plate Pickup
- `GET /plate-pickup/enriched/` - Plate pickups with restaurant, address, product, and credit details

All enriched endpoints follow the same pattern and support the `include_archived` query parameter.

## Example Usage

### Frontend Implementation

```typescript
// Fetch enriched users for display in a table
const fetchEnrichedUsers = async () => {
  const response = await fetch('/users/enriched/', {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  const users = await response.json();
  
  // Users now include role_name, role_type, and institution_name
  // No need for additional API calls!
  return users.map(user => ({
    name: `${user.first_name} ${user.last_name}`,
    email: user.email,
    role: user.role_name,        // ← Already included!
    institution: user.institution_name,  // ← Already included!
    status: user.status
  }));
};
```

## Benefits

1. **Performance**: Single query eliminates N+1 problem
2. **Simplicity**: Frontend doesn't need complex data fetching logic
3. **Consistency**: Same authentication, scoping, and error handling as base endpoints
4. **Backward Compatibility**: Base endpoints remain available for other use cases

