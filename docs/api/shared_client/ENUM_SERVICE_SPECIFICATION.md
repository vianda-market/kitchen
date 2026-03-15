# Enum Service API Specification

## Request from Frontend Team

**Date**: 2026-02-08  
**Priority**: High  
**Type**: New Feature - Backend API Enhancement

---

## Executive Summary

The frontend currently has **27+ entity types** with enum fields (status, method_type, account_type, etc.) that are implemented as free-form text inputs. This creates data integrity issues and maintenance burden. We need a centralized Enum Service API that exposes all valid enum values, allowing the frontend to dynamically render dropdowns that automatically update when new enum values are added to the backend.

---

## Problem Statement

### Current Issues

1. **Data Integrity**: Frontend forms use text inputs for enum fields, allowing invalid values
2. **Inconsistency**: No enforcement of valid enum values at the UI level
3. **Maintenance Burden**: Adding new enum values requires frontend code changes and deployment
4. **Poor UX**: Users must guess valid values instead of selecting from a list
5. **Type Safety**: TypeScript types show `string` instead of specific union types

### Impact

- Every entity with a `status` field (27+ entities) is affected
- Multiple entity-specific enum fields need proper validation
- Risk of invalid data being submitted to the backend

---

## Discovered Enum Fields from Frontend Types

### 1. **status** (HIGHEST PRIORITY - Used in 27+ entities)

**Entities affected**: User, Institution, InstitutionEntity, Address, CreditCurrency, Market, Plan, FintechLink, Product, Plate, QRCode, Restaurant, NationalHoliday, RestaurantHoliday, PlateKitchenDay, Subscription, PaymentMethod, Employer, InstitutionBill, InstitutionBankAccount, InstitutionPaymentAttempt, RestaurantBalance, RestaurantTransaction, PlatePickup, PendingPickupSummary, DiscretionaryRequest, FintechLinkTransaction

**Current frontend default**: `"active"`

**Expected values** (based on common usage patterns):
- `"active"`
- `"inactive"` 
- `"pending"`
- `"archived"`
- Other status-specific values per entity type

**Question for Backend**: 
- Is `status` a global enum shared across all entities?
- Or does each entity type have its own status values?
- What are the complete, authoritative status values for each entity?

---

### 2. **subscription_status** (Subscription entity)

**Backend enum values** (from `GET /api/v1/enums/` or `GET /api/v1/enums/subscription_status`):
- `"Active"`
- `"On Hold"`
- `"Pending"`
- `"Expired"`
- `"Cancelled"`

**On Hold**: When `subscription_status` is `"On Hold"`, the subscription record includes:
- **`hold_start_date`** (ISO 8601): when the subscription was put on hold.
- **`hold_end_date`** (ISO 8601 or `null`): when the subscription will resume; `null` = indefinite hold.

Use the **On Hold** value (not a generic "Inactive") so UI can show hold dates and Resume/Cancel actions. See [ENUM_SERVICE_API.md](../../shared_client/ENUM_SERVICE_API.md#subscription-status-and-on-hold) for full client documentation.

---

### 3. **method_type** (PaymentMethod entity)

**Current frontend type**: `string`

**Expected values** (needs backend confirmation):
- `"credit_card"`
- `"debit_card"`
- `"bank_transfer"`
- `"cash"`
- Other payment method types?

**Question for Backend**: What are the valid payment method types?

---

### 4. **account_type** (InstitutionBankAccount entity)

**Current frontend type**: `string`

**Expected values** (needs backend confirmation):
- `"checking"`
- `"savings"`
- `"business"`
- Other account types?

**Question for Backend**: What are the valid bank account types?

---

### 5. **holiday_type** (RestaurantHoliday entity)

**Current frontend type**: `string`

**Expected values** (needs backend confirmation):
- `"national"`
- `"restaurant"`
- `"custom"`
- Other holiday types?

**Question for Backend**: What are the valid holiday types?

---

### 6. **transaction_type** (RestaurantTransaction entity)

**Current frontend type**: `string`

**Expected values** (needs backend confirmation):
- `"order"`
- `"refund"`
- `"adjustment"`
- `"credit"`
- Other transaction types?

**Question for Backend**: What are the valid transaction types?

---

### 7. **role_type** (User entity)

**Current frontend type**: `string`

**Known values** (from auth context):
- `"Employee"`
- `"Supplier"`
- `"Customer"`

**Confirmed as RBAC roles** ✓

---

### 8. **street_type** (Address entity)

**Current frontend type**: `string | null`

**Expected values** (needs backend confirmation):
- `"St"`
- `"Ave"`
- `"Blvd"`
- `"Rd"`
- `"Dr"`
- `"Ln"`
- `"Way"`
- `"Ct"`
- `"Pl"`
- Other street type abbreviations?

**Question for Backend**: What street type abbreviations are supported?

---

### 9. **address_type** (Address entity)

**Current frontend type**: `string | null`

**Expected values** (needs backend confirmation):
- `"home"`
- `"work"`
- `"billing"`
- `"shipping"`
- `"restaurant"`
- Other address types?

**Question for Backend**: What are the valid address types?

---

## Proposed API Design

### Option A: Single Enums Endpoint (RECOMMENDED)

```http
GET /api/v1/enums/
```

**Response**:
```json
{
  "status": ["active", "inactive", "pending", "archived"],
  "subscription_status": ["Active", "On Hold", "Cancelled"],
  "method_type": ["credit_card", "debit_card", "bank_transfer", "cash"],
  "account_type": ["checking", "savings", "business"],
  "holiday_type": ["national", "restaurant", "custom"],
  "transaction_type": ["order", "refund", "adjustment", "credit"],
  "role_type": ["Employee", "Supplier", "Customer"],
  "street_type": ["St", "Ave", "Blvd", "Rd", "Dr", "Ln", "Way", "Ct", "Pl"],
  "address_type": ["home", "work", "billing", "shipping", "restaurant"]
}
```

**Benefits**:
- Single API call to fetch all enums
- Easy to cache on frontend
- Consistent structure
- Simple to extend with new enum types

---

### Option B: Individual Enum Endpoints (ALTERNATIVE)

```http
GET /api/v1/enums/status
GET /api/v1/enums/subscription_status
GET /api/v1/enums/method_type
... (one endpoint per enum type)
```

**Response per endpoint**:
```json
["value1", "value2", "value3"]
```

**Benefits**:
- Granular control over caching
- Can fetch only needed enums
- Easier to add enum-specific metadata

---

## Requirements for Backend Implementation

### 1. **Enum Source of Truth**

The backend must be the single source of truth for all enum values. Please confirm:

- Are enums defined in Python Enum classes?
- Are they stored in database lookup tables?
- Are they hardcoded constants?
- How are they currently validated?

### 2. **Response Format**

**Required**:
- JSON object with enum type keys and string array values
- Enum values should match exactly what the database expects (case-sensitive)
- Order should be consistent (preferably logical order or alphabetical)

**Example**:
```json
{
  "status": ["active", "inactive", "pending", "archived"]
}
```

### 3. **Authentication**

**Requirement**: All authenticated users should have access to enums

- Use standard Bearer token authentication
- No special permissions required (enums are configuration, not sensitive data)

### 4. **Caching Headers**

**Requirement**: Support frontend caching to minimize API calls

Recommended headers:
```http
Cache-Control: public, max-age=3600
ETag: "enum-version-hash"
```

This allows frontend to cache enums for 1 hour and validate with ETags.

### 5. **Error Handling**

**Requirement**: Graceful handling if enum service is unavailable

- Return 200 OK if successful
- Return 500 if enum service fails (frontend will use fallback)
- Return 401 if authentication fails

### 6. **Extensibility**

**Requirement**: Easy to add new enum types without breaking changes

- Adding a new enum type should not break existing clients
- Enum values can be added (non-breaking)
- Enum values should not be removed (breaking change - needs migration)

### 7. **Documentation**

**Requirement**: Each enum type should be documented

Please provide:
- Description of each enum type
- Valid values for each enum
- When to use each value
- Any business rules or constraints

---

## Frontend Implementation Plan (After Backend Delivery)

Once the backend Enum Service is available, the frontend will:

1. **Create Enum Service** - Fetch and cache enum values
2. **Update Form Components** - Render enums as dropdowns instead of text inputs
3. **Update All Form Configs** - Convert 50+ enum fields to use dynamic dropdowns
4. **Remove Hardcoded Defaults** - Delete all `defaultValue: 'active'` and similar hardcoding
5. **Add Type Safety** - Update TypeScript types to use union types for enums

**Estimated Frontend Work**: 2-3 hours after backend API is available

---

## Benefits of This Implementation

### For Backend
- Centralized enum management
- Easier to add new values (single change point)
- Better data validation at API level
- Documentation of valid values

### For Frontend
- Dynamic dropdowns that auto-update
- Better UX (select instead of type)
- Data integrity (only valid values)
- No code changes when enums are added
- Type safety improvements

### For Product
- Faster feature delivery (no frontend deploy for enum changes)
- Consistent data quality
- Better user experience
- Reduced bugs from invalid enum values

---

## Questions for Backend Team

Please confirm the following before implementation:

1. **Global vs Entity-Specific Status**
   - Is `status` a single global enum?
   - Or does each entity have its own status values?
   - If entity-specific, should the API return nested structure?

2. **Complete Enum Values**
   - What are the authoritative values for each enum type?
   - Are there additional enum fields we haven't discovered?
   - Are there deprecated values we should exclude?

3. **Enum Versioning**
   - How will you handle enum changes over time?
   - Should we version the enums API?
   - What's the migration strategy for value changes?

4. **Implementation Timeline**
   - When can this API be available?
   - Can we get a staging environment endpoint first?
   - Who is the backend POC for this feature?

5. **Database Schema**
   - Are enums enforced at database level (CHECK constraints)?
   - Are they Python Enum classes?
   - Are they in lookup tables?

---

## Testing Requirements

### Backend Testing

Please ensure the endpoint returns:
- ✅ Valid JSON structure
- ✅ All enum types listed in this document
- ✅ Consistent casing (as used in database)
- ✅ No null or empty arrays
- ✅ Authentication is enforced
- ✅ CORS headers for frontend access

### Frontend Testing (After Backend Delivery)

We will verify:
- ✅ Enums load correctly on app startup
- ✅ Dropdowns show correct values
- ✅ Forms submit valid enum values
- ✅ Caching works properly
- ✅ Error handling for API failures
- ✅ New enum values appear without frontend deploy

---

## Priority and Timeline

**Priority**: High - This affects data integrity across 27+ entity types

**Requested Timeline**:
- Backend API implementation: 1-2 days
- Frontend integration: 2-3 hours (after backend is ready)
- Testing: 1 day
- **Total**: ~3-4 days from start to production

**Blockers**: Frontend cannot proceed with dropdown implementation until backend API is available. We can prepare the infrastructure, but need the actual endpoint to complete the work.

---

## Contact

**Frontend POC**: [Your Team]  
**Questions**: Please respond to this document with answers to the questions above  
**Updates**: Please notify us when the staging endpoint is available for testing

---

## Appendix: Current Frontend Form Config Examples

**Before** (Current - Free-form text):
```typescript
{ name: 'status', label: 'Status', type: 'text', defaultValue: 'active' }
```

**After** (Desired - Dynamic dropdown):
```typescript
{ name: 'status', label: 'Status', type: 'select', enumType: 'status', defaultValue: 'active' }
```

This change will be applied to 50+ field configurations across 27+ form configs once the backend API is available.
