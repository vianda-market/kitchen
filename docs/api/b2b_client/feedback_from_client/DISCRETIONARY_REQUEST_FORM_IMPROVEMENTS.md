# Discretionary Request Form - Improvements Proposal

**Document Version**: 1.0  
**Date**: February 10, 2026  
**For**: Backend Team  
**From**: Frontend Team  
**Status**: Awaiting Backend Decision  

---

## **Executive Summary**

The Discretionary Request form currently has UX and data integrity issues. The `category` field is free-form text with no validation, and there's ambiguity about when to use `category` vs `reason`. Additionally, the form doesn't clearly distinguish between user-only credits and restaurant-related credits.

**Key Issues**:
1. ✅ Enum service exists for `discretionary_reason` but frontend uses free-form text for `category`
2. ❌ Unclear purpose of `category` vs `reason` fields
3. ❌ No clear UI pattern to differentiate user-only vs restaurant-related requests

**Frontend Request**: Backend guidance on preferred approach before implementing form changes.

---

## **Current State**

### **Database Schema (DiscretionaryRequest)**

```python
{
  discretionary_id: UUID,
  user_id: UUID,                    # Required: Who receives the credit
  restaurant_id: UUID | null,       # Optional: Related restaurant
  category: string | null,          # ❌ Free-form text, no validation
  reason: string | null,            # Free-form textarea
  amount: Decimal,                  # Required: Credit amount
  status: Status,
  created_date: datetime,
  resolved_date: datetime | null,
  resolved_by: UUID | null,
  resolution_comment: string | null
}
```

### **Current Form Fields (Frontend)**

```typescript
{
  user_id: Dropdown (required),         // Select user from /users/enriched/
  restaurant_id: Dropdown (optional),   // Select restaurant from /restaurants/enriched/
  category: Text input (free-form),     // ❌ No validation, unclear purpose
  reason: Textarea (free-form),         // Free explanation
  amount: Number (required)             // Credit amount
}
```

### **Existing Backend Enum Service**

The backend **already provides** a `discretionary_reason` enum via `/api/v1/enums/`:

```json
{
  "discretionary_reason": [
    "Marketing Campaign",
    "Credit Refund",
    "Order incorrectly marked as not collected",
    "Full Order Refund"
  ]
}
```

**Problem**: Frontend is not using this enum for either `category` or `reason` fields.

---

## **Problems Identified**

### **1. Data Integrity Issue**

**Current Behavior**:
- `category` accepts any string: "promo", "Promo", "PROMO", "marketing", "general credit", etc.
- No validation or standardization
- Makes reporting and analytics difficult

**Impact**:
- Inconsistent data in database
- Hard to filter/group by category
- Poor data quality

---

### **2. Unclear Field Semantics**

**Questions we can't answer from current schema**:
- What's the difference between `category` and `reason`?
- When should admins use `category` vs `reason`?
- Is `category` meant to be a controlled list or free-form?
- Is `reason` meant to be the explanation or the classification?

**Example of confusion**:
```json
// What's the difference between these two?
{
  "category": "Marketing Campaign",
  "reason": "Q1 2026 signup promotion"
}

{
  "category": "Signup promo",
  "reason": "Marketing Campaign for new users"
}
```

---

### **3. Missing User vs Restaurant Differentiation**

**Business Logic Question**: Are there two types of discretionary requests?

**Type A: User-Only Credits**
- General marketing campaigns
- Customer satisfaction gestures
- Loyalty rewards
- **Restaurant not involved**

**Type B: Restaurant-Related Credits**
- Order issues
- Pickup problems
- Restaurant service failures
- **Specific to a restaurant**

**Current Form**: Doesn't guide users toward this distinction. Both `user_id` and `restaurant_id` are just dropdowns with no context.

---

## **Analysis of Existing Enum Values**

| Enum Value | User Credit? | Restaurant Credit? | Typical Use Case |
|------------|--------------|--------------------|--------------------|
| **Marketing Campaign** | ✅ Primary | ⚠️ Rare | General promo, usually no specific restaurant |
| **Credit Refund** | ✅ Yes | ✅ Yes | Refunding user for any reason (could be restaurant-related or not) |
| **Order incorrectly marked as not collected** | ✅ Yes | ✅ Yes | User didn't collect → restaurant error → needs restaurant context |
| **Full Order Refund** | ✅ Yes | ✅ Yes | Complete order problem → needs restaurant context |

**Observation**: 3 out of 4 reasons can apply to both user-only and restaurant-related contexts. Only "Marketing Campaign" is primarily user-only.

---

## **Proposed Solutions**

### **Solution 1: Simplify - Use Enum for Classification** (✅ **RECOMMENDED**)

**Changes**:
1. **Replace `category`** with enum dropdown using `discretionary_reason`
2. **Keep `reason`** as free-form textarea for detailed explanation
3. **Use `restaurant_id` presence** to differentiate user-only vs restaurant-related

**New Field Mapping**:

| Field | Type | Purpose | Required? |
|-------|------|---------|-----------|
| `user_id` | Dropdown (FK) | Who gets the credit | Always |
| `restaurant_id` | Dropdown (FK) | Related restaurant (if applicable) | Conditional |
| `category` | Dropdown (Enum) | Classification using `discretionary_reason` enum | Always |
| `reason` | Textarea | Free-form explanation/details | Optional |
| `amount` | Number | Credit amount | Always |

**Updated Form Flow**:
```
1. Select User: [Dropdown]
2. Select Category: [Dropdown from enum]
   - "Marketing Campaign"
   - "Credit Refund"
   - "Order incorrectly marked as not collected"
   - "Full Order Refund"
3. Select Restaurant: [Dropdown - Required if order/restaurant-related category]
4. Enter Amount: [Number]
5. Explain Reason: [Textarea - Additional details/context]
```

**Backend Schema Change Required**:
```python
class DiscretionaryRequestCreate(BaseModel):
    user_id: UUID
    category: DiscretionaryReason  # ✅ Use enum instead of string
    restaurant_id: Optional[UUID] = None
    reason: Optional[str] = None  # Free-form explanation
    amount: Decimal
```

**Pros**:
- ✅ Uses existing enum service
- ✅ Enforces data integrity
- ✅ Clear semantics: category = classification, reason = explanation
- ✅ Minimal schema changes (just type change for `category`)
- ✅ Frontend dropdown automatically updates when enum changes

**Cons**:
- ⚠️ Breaking change: `category` type changes from `string | null` to enum
- ⚠️ Existing data may have invalid `category` values (migration needed)

---

### **Solution 2: Deprecate Category, Use Reason as Enum**

**Changes**:
1. **Deprecate `category` field** (set to null, ignore in API)
2. **Change `reason`** from free-form text to enum dropdown
3. **Add new `details` field** for free-form explanation

**New Field Mapping**:

| Field | Type | Purpose | Required? |
|-------|------|---------|-----------|
| `user_id` | Dropdown (FK) | Who gets the credit | Always |
| `restaurant_id` | Dropdown (FK) | Related restaurant (if applicable) | Conditional |
| ~~`category`~~ | Deprecated | (Not used) | - |
| `reason` | Dropdown (Enum) | Classification using `discretionary_reason` enum | Always |
| `details` | Textarea | Free-form explanation | Optional |
| `amount` | Number | Credit amount | Always |

**Backend Schema Change Required**:
```python
class DiscretionaryRequestCreate(BaseModel):
    user_id: UUID
    reason: DiscretionaryReason  # ✅ Use enum instead of string
    restaurant_id: Optional[UUID] = None
    details: Optional[str] = None  # New field for explanation
    amount: Decimal
    # category: deprecated, accept but ignore
```

**Pros**:
- ✅ Cleaner semantics: reason = why (enum), details = explanation
- ✅ Removes ambiguity between category and reason
- ✅ More intuitive field names

**Cons**:
- ⚠️ Breaking change: `reason` type changes from text to enum
- ⚠️ Requires adding new `details` field to schema
- ⚠️ More complex migration (existing `reason` values may not match enum)

---

### **Solution 3: Add Request Type Field** (❌ **NOT RECOMMENDED**)

**Changes**:
1. Add new `request_type` field: "User" | "Restaurant"
2. Use `category` as enum dropdown
3. Keep `reason` as free-form text

**New Field Mapping**:

| Field | Type | Purpose | Required? |
|-------|------|---------|-----------|
| `user_id` | Dropdown (FK) | Who gets the credit | Always |
| `request_type` | Dropdown (Enum) | "User" or "Restaurant" | Always |
| `restaurant_id` | Dropdown (FK) | Related restaurant (required if type=Restaurant) | Conditional |
| `category` | Dropdown (Enum) | Classification using `discretionary_reason` enum | Always |
| `reason` | Textarea | Free-form explanation | Optional |
| `amount` | Number | Credit amount | Always |

**Pros**:
- ✅ Explicit user vs restaurant differentiation
- ✅ Clear validation rules

**Cons**:
- ❌ Redundant with `restaurant_id` presence (if restaurant_id exists → it's restaurant-related)
- ❌ Requires new schema field
- ❌ More complex validation logic
- ❌ Extra field for users to fill out

---

### **Solution 4: Keep Current Schema, Add Validation Only** (⚠️ **MINIMAL CHANGE**)

**Changes**:
1. Add backend enum validation for `category` field (accept only enum values)
2. Frontend changes to use dropdown instead of text input
3. No schema changes

**Backend Change**:
```python
class DiscretionaryRequestCreate(BaseModel):
    user_id: UUID
    category: Optional[DiscretionaryReason] = None  # ✅ Accept enum values only
    restaurant_id: Optional[UUID] = None
    reason: Optional[str] = None
    amount: Decimal
```

**Pros**:
- ✅ Minimal backend changes
- ✅ No migration needed (existing null/invalid values stay as-is)
- ✅ Non-breaking change

**Cons**:
- ⚠️ Keeps semantic ambiguity (category vs reason)
- ⚠️ Doesn't address field purpose confusion
- ⚠️ Suboptimal long-term solution

---

## **Frontend Implementation Impact**

### **Current Frontend Code**

```typescript
// formConfigs.ts
{ name: 'category', label: 'Category', type: 'text' },
{ name: 'reason', label: 'Reason', type: 'textarea' },
```

### **Solution 1: Updated Frontend Code**

```typescript
// formConfigs.ts
{ 
  name: 'category', 
  label: 'Category', 
  type: 'select', 
  enumType: 'discretionary_reason',  // ✅ Use enum service
  required: true
},
{ name: 'reason', label: 'Additional Details', type: 'textarea' },
{
  name: 'restaurant_id',
  label: 'Restaurant (if applicable)',
  type: 'select',
  dropdownSource: '/api/v1/restaurants/enriched/',
  // ✅ Could add conditional validation based on category
}
```

**Frontend Work Required**:
- ✅ Change field type from `text` to `select`
- ✅ Add `enumType: 'discretionary_reason'`
- ✅ Update label for clarity
- ✅ ~30 minutes of work

---

## **Migration Considerations**

### **Existing Data Analysis Needed**

**Questions for Backend**:
1. What are the current distinct values in the `category` column?
2. How many records have `category = null`?
3. Can existing `category` values be mapped to the enum?
4. What's the distribution of records with/without `restaurant_id`?

**Example Migration Query**:
```sql
-- Analyze current category usage
SELECT 
  category, 
  COUNT(*) as count,
  COUNT(restaurant_id) as with_restaurant,
  COUNT(*) - COUNT(restaurant_id) as without_restaurant
FROM discretionary_requests
GROUP BY category
ORDER BY count DESC;
```

### **Migration Strategy (if Solution 1 adopted)**

**Option A: Strict Migration**
```sql
-- Map existing values to enum
UPDATE discretionary_requests
SET category = CASE
  WHEN LOWER(category) LIKE '%marketing%' THEN 'Marketing Campaign'
  WHEN LOWER(category) LIKE '%refund%' THEN 'Credit Refund'
  WHEN LOWER(category) LIKE '%order%' THEN 'Order incorrectly marked as not collected'
  WHEN LOWER(category) LIKE '%full%' THEN 'Full Order Refund'
  ELSE NULL
END
WHERE category IS NOT NULL;

-- Optionally: set NULL to default
UPDATE discretionary_requests
SET category = 'Credit Refund'
WHERE category IS NULL;
```

**Option B: Lenient Migration**
```sql
-- Keep existing data as-is
-- New records use enum validation
-- Old records grandfathered in
ALTER TABLE discretionary_requests
  ALTER COLUMN category TYPE varchar(255);
  
-- Add check constraint for new records only
-- (depends on backend ORM implementation)
```

---

## **Conditional Logic Recommendations**

### **Should `restaurant_id` be Required?**

**Scenario-Based Requirement**:

| Category | Restaurant Required? | Rationale |
|----------|---------------------|-----------|
| Marketing Campaign | ❌ Optional | Usually user-only, but could be restaurant-specific promo |
| Credit Refund | ❌ Optional | Could be general refund or restaurant-related |
| Order incorrectly marked as not collected | ✅ **Required** | Always tied to specific restaurant/order |
| Full Order Refund | ✅ **Required** | Always tied to specific restaurant/order |

**Backend Validation Logic**:
```python
@validator('restaurant_id')
def validate_restaurant_for_category(cls, v, values):
    """Require restaurant_id for order-related categories"""
    category = values.get('category')
    
    restaurant_required = [
        DiscretionaryReason.ORDER_NOT_COLLECTED,
        DiscretionaryReason.FULL_ORDER_REFUND
    ]
    
    if category in restaurant_required and v is None:
        raise ValueError(
            f"restaurant_id is required for category: {category.value}"
        )
    
    return v
```

**Frontend Form Behavior**:
```typescript
// Show helper text based on selected category
if (category === 'Order incorrectly marked as not collected' ||
    category === 'Full Order Refund') {
  // Make restaurant required
  // Show red asterisk and validation error if not provided
}
```

---

## **Questions for Backend Team**

Please provide feedback on the following:

### **1. Preferred Solution**

Which solution do you prefer?
- [ ] **Solution 1**: Use enum for `category`, keep `reason` as text (**Frontend recommends this**)
- [ ] **Solution 2**: Deprecate `category`, use enum for `reason`, add `details` field
- [ ] **Solution 3**: Add `request_type` field
- [ ] **Solution 4**: Minimal change - just add validation
- [ ] **Other**: (Please specify)

---

### **2. Field Semantics**

What is the intended purpose of each field?

**`category`**:
- [ ] Meant to be a classification from a controlled list (enum)
- [ ] Meant to be free-form description
- [ ] Not sure / needs discussion

**`reason`**:
- [ ] Meant to be a classification from a controlled list (enum)
- [ ] Meant to be free-form explanation
- [ ] Not sure / needs discussion

---

### **3. Restaurant Requirement**

Should `restaurant_id` be conditionally required?
- [ ] Yes, required for order-related categories
- [ ] No, always optional
- [ ] Let's discuss business logic first

---

### **4. Migration Strategy**

If we change field types to use enum:
- [ ] Migrate existing data to match enum values (provide mapping query)
- [ ] Keep existing data as-is, apply enum only to new records
- [ ] Analyze current data first, then decide (please run analysis query)

---

### **5. Enum Completeness**

Are the current 4 enum values sufficient?
```
- "Marketing Campaign"
- "Credit Refund"
- "Order incorrectly marked as not collected"
- "Full Order Refund"
```

Missing any common scenarios?
- [ ] These cover all cases
- [ ] Need to add: ___________________
- [ ] Need to discuss business requirements

---

### **6. API Versioning**

If this is a breaking change:
- [ ] Create new API version (e.g., `/api/v2/discretionary/`)
- [ ] Update existing API with migration period
- [ ] Make changes backward compatible
- [ ] Frontend will handle any format

---

## **Frontend Next Steps**

Once backend provides guidance, frontend will:

1. ✅ Update form configuration to use enum dropdown
2. ✅ Update TypeScript types to match backend schema
3. ✅ Add conditional validation for `restaurant_id`
4. ✅ Update table display if field names change
5. ✅ Test enum service integration
6. ✅ Update documentation

**Estimated Frontend Implementation**: 2-4 hours (depending on solution complexity)

---

## **Recommended Timeline**

1. **Backend Review** (This Week)
   - Review this document
   - Make decision on preferred solution
   - Provide feedback on questions above

2. **Backend Implementation** (Next Week)
   - Update schema (if needed)
   - Add validation logic
   - Run migration (if needed)
   - Update API documentation

3. **Frontend Implementation** (Following Week)
   - Update form to use enum
   - Add conditional logic
   - Test integration
   - Deploy to staging

4. **Testing & Deployment** (Week After)
   - E2E testing
   - Production deployment

---

## **Related Documentation**

- **Enum Service API**: `docs/api/shared_client/ENUM_SERVICE_API.md`
- **Frontend Application Summary**: `docs/api/feedback_for_backend/FRONTEND_APPLICATION_SUMMARY.md`
- **API Permissions**: `docs/api/API_PERMISSIONS_BY_ROLE.md` (Section 3: Discretionary Credit API)

---

## **Contact**

For questions or discussion, please reach out to the frontend team. We're happy to discuss any aspect of this proposal and adjust based on backend constraints or preferences.

**Document Status**: ⏳ Awaiting Backend Decision  
**Next Action**: Backend team to review and provide feedback on questions above

---

**END OF DOCUMENT**
