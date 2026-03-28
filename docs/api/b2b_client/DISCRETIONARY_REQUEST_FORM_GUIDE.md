# Discretionary Request Form Implementation Guide

## Overview

This guide provides frontend developers with implementation instructions for the improved Discretionary Request form. The schema has been updated to better align with the actual use case and provide a more intuitive user experience.

## Schema Changes Summary

### **IMPORTANT: Field Swap**

The `category` and `reason` fields have **swapped semantics**:

| Field | Old Behavior | New Behavior |
|-------|--------------|--------------|
| `category` | Free-form text ("Client"/"Supplier") | **Enum dropdown** (Marketing Campaign, Credit Refund, etc.) |
| `reason` | Enum dropdown | **Free-form text field** (optional explanation) |

## Backend Schema (as of Feb 2026)

```typescript
interface DiscretionaryRequest {
  user_id?: UUID;              // For customer credits (mutually exclusive with restaurant_id)
  restaurant_id?: UUID;         // For restaurant credits (mutually exclusive with user_id)
  category: DiscretionaryCategory;  // REQUIRED: Enum classification
  reason?: string;              // OPTIONAL: Free-form explanation (max 500 chars)
  amount: number;               // REQUIRED: Must be > 0
  comment?: string;             // OPTIONAL: Internal admin notes (max 500 chars)
}

enum DiscretionaryCategory {
  MARKETING_CAMPAIGN = "Marketing Campaign",
  CREDIT_REFUND = "Credit Refund",
  ORDER_INCORRECTLY_MARKED = "Order incorrectly marked as not collected",
  FULL_ORDER_REFUND = "Full Order Refund"
}
```

## Form Field Configuration

### 1. **Recipient Selection** (Required)

```tsx
// Radio button group or tabs
<RecipientSelector>
  <Option value="customer">Customer Credit</Option>
  <Option value="restaurant">Restaurant Credit</Option>
</RecipientSelector>

// Conditional field based on selection:
// If "customer" selected:
<UserSearchField 
  name="user_id" 
  placeholder="Search customer by email, name, or ID" 
  required 
/>

// If "restaurant" selected:
<RestaurantSearchField 
  name="restaurant_id" 
  placeholder="Search restaurant by name or ID" 
  required 
/>
```

**Validation:**
- Exactly one of `user_id` or `restaurant_id` must be provided
- Cannot specify both

### 2. **Category** (Required) - **NEW: Now a Dropdown**

```tsx
<CategoryDropdown name="category" required>
  <Option value="Marketing Campaign">Marketing Campaign</Option>
  <Option value="Credit Refund">Credit Refund</Option>
  <Option value="Order incorrectly marked as not collected">
    Order Incorrectly Marked as Not Collected
  </Option>
  <Option value="Full Order Refund">Full Order Refund</Option>
</CategoryDropdown>
```

**Conditional Logic:**
- If `category` is "Order incorrectly marked as not collected" or "Full Order Refund":
  - **REQUIRE** `restaurant_id` to be selected
  - Show validation error if user tries to select these with customer credit

**Suggested Labels:**
- **Marketing Campaign**: General promotional credits for customers or restaurants
- **Credit Refund**: Standard credit refunds
- **Order Incorrectly Marked**: Restaurant-specific issue (requires restaurant selection)
- **Full Order Refund**: Complete order refund (requires restaurant selection)

### 3. **Reason** (Optional) - **NEW: Now Free Text**

```tsx
<ReasonTextArea 
  name="reason" 
  placeholder="Provide additional details or explanation (optional)" 
  maxLength={500}
  rows={3}
/>
```

**Validation:**
- Optional field
- Max 500 characters
- Should be used for contextual explanation (e.g., "Customer experienced app crash during checkout")

### 4. **Amount** (Required)

```tsx
<AmountInput 
  name="amount" 
  type="number" 
  min={0.01} 
  step={0.01}
  required 
  placeholder="0.00"
/>
```

**Validation:**
- Required field
- Must be greater than 0
- Recommended: Show currency symbol based on selected user/restaurant's market

### 5. **Comment** (Optional)

```tsx
<CommentTextArea 
  name="comment" 
  placeholder="Internal notes for admin review (optional)" 
  maxLength={500}
  rows={2}
/>
```

**Validation:**
- Optional field
- Max 500 characters
- For internal admin use only (not visible to customers/restaurants)

## Form Layout Recommendations

### Recommended Field Order

1. **Recipient Type** (Customer/Restaurant radio buttons)
2. **Recipient Search** (User or Restaurant search field)
3. **Category** (Dropdown)
4. **Amount** (Number input)
5. **Reason** (Optional text area)
6. **Comment** (Optional text area)

### Progressive Disclosure Pattern

```
┌──────────────────────────────────────────┐
│ Credit Recipient                          │
│ ○ Customer  ● Restaurant                  │
├──────────────────────────────────────────┤
│ Restaurant Search                         │
│ [La Parrilla Argentina        🔍]        │
├──────────────────────────────────────────┤
│ Category *                                │
│ [Full Order Refund            ▼]         │
├──────────────────────────────────────────┤
│ Amount *                        Currency  │
│ [25.00                          ] ARS     │
├──────────────────────────────────────────┤
│ Reason (Optional)                         │
│ ┌──────────────────────────────────────┐ │
│ │ Order was marked as not collected    │ │
│ │ but customer confirmed pickup        │ │
│ └──────────────────────────────────────┘ │
│ 0/500 characters                          │
├──────────────────────────────────────────┤
│ Internal Comment (Optional)               │
│ ┌──────────────────────────────────────┐ │
│ │ Verified via support ticket #12345   │ │
│ └──────────────────────────────────────┘ │
│ 0/500 characters                          │
└──────────────────────────────────────────┘
```

## Enriched Discretionary API (Super-Admin Table / List View)

For the **super-admin dashboard** (pending-requests table or all-requests list), use the **super-admin** endpoints. They return a summary that includes **created_by**, **created_by_name**, and **recipient metadata** (user_full_name, user_username for Customer; restaurant_name for Supplier).

### Enriched Endpoints (Super-Admin)

| Method | Endpoint | Use Case |
|--------|----------|----------|
| `GET` | `/api/v1/super-admin/discretionary/pending-requests/` | Pending requests only (enriched summary with created_by, recipient) |
| `GET` | `/api/v1/super-admin/discretionary/requests/` | All discretionary requests (enriched summary + resolution details) |

**Authorization**: Admin or Super Admin employee.

### Response Schema (Summary with Enriched Fields)

```typescript
interface DiscretionarySummary {
  discretionary_id: UUID;
  user_id?: UUID;
  restaurant_id?: UUID;
  category: DiscretionaryCategory;
  reason?: string;
  amount: number;
  status: string;
  created_date: string;
  resolved_date?: string | null;
  resolved_by?: UUID | null;
  resolution_comment?: string | null;
  // Enriched (creator and recipient)
  created_by?: UUID | null;
  created_by_name?: string | null;
  user_full_name?: string | null;   // Recipient (Customer)
  user_username?: string | null;    // Recipient (Customer)
  restaurant_name?: string | null;  // Recipient (Supplier)
}
```

### Recipient Metadata

For **Customer** requests: `user_full_name`, `user_username`.  
For **Supplier** requests: `restaurant_name`.  
Use for "Recipient" or "Credited to" in the table.

### Example: Pending Requests Table (Super-Admin)

```tsx
// Fetch pending requests with created_by and recipient
const response = await fetch('/api/v1/super-admin/discretionary/pending-requests/', {
  headers: { Authorization: `Bearer ${token}` }
});
const requests: DiscretionarySummary[] = await response.json();

// Table columns: Recipient and Created by
<Table>
  {requests.map(r => (
    <TableRow key={r.discretionary_id}>
      <TableCell>
        {r.user_id
          ? `${r.user_full_name ?? '—'}${r.user_username ? ` (@${r.user_username})` : ''}`
          : (r.restaurant_name ?? '—')}
      </TableCell>
      <TableCell>{r.created_by_name ?? r.created_by ?? '—'}</TableCell>
      {/* ... category, amount, status, etc. ... */}
    </TableRow>
  ))}
</Table>
```

---

## API Request Examples

### Customer Credit Request

```json
POST /api/v1/admin/discretionary/requests/

{
  "user_id": "86ebd82e-fcc9-4896-afe0-b020f4549378",
  "category": "Marketing Campaign",
  "reason": "New customer onboarding incentive - Welcome credit for first order",
  "amount": 15.50,
  "comment": "Part of Q1 2026 customer acquisition campaign"
}
```

### Restaurant Credit Request

```json
POST /api/v1/admin/discretionary/requests/

{
  "restaurant_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "category": "Full Order Refund",
  "reason": "Order was marked as not collected but customer confirmed pickup via support",
  "amount": 25.00,
  "comment": "Support ticket #12345 - Verified with restaurant owner"
}
```

## Validation Rules

### Frontend Validation

```typescript
interface ValidationRules {
  user_id: {
    required: "if restaurant_id is empty",
    mutuallyExclusive: ["restaurant_id"]
  },
  restaurant_id: {
    required: "if user_id is empty",
    mutuallyExclusive: ["user_id"]
  },
  category: {
    required: true,
    enum: ["Marketing Campaign", "Credit Refund", "Order incorrectly marked as not collected", "Full Order Refund"],
    conditionalValidation: {
      if: ["Order incorrectly marked as not collected", "Full Order Refund"],
      then: { restaurant_id: { required: true } }
    }
  },
  reason: {
    optional: true,
    maxLength: 500
  },
  amount: {
    required: true,
    min: 0.01,
    type: "number"
  },
  comment: {
    optional: true,
    maxLength: 500
  }
}
```

### Backend Error Responses

```json
// Missing required field
{
  "detail": "Missing required fields: category, amount"
}

// Invalid category
{
  "detail": "Invalid category. Must be one of: Marketing Campaign, Credit Refund, Order incorrectly marked as not collected, Full Order Refund"
}

// Restaurant required for category
{
  "detail": "Category 'Full Order Refund' requires restaurant_id to be specified"
}

// Amount validation
{
  "detail": "Amount must be greater than 0"
}

// Mutual exclusivity violation
{
  "detail": "Cannot specify both user_id and restaurant_id"
}
```

## UI/UX Best Practices

### 1. **Smart Category Filtering**

When user selects "Customer Credit":
- Show all categories
- If user attempts to select "Order incorrectly marked" or "Full Order Refund", show warning:
  > ⚠️ This category requires a restaurant to be selected. Switch to "Restaurant Credit" to use this category.

When user selects "Restaurant Credit":
- Show all categories
- Highlight restaurant-specific categories ("Order incorrectly marked", "Full Order Refund")

### 2. **Contextual Help Text**

```tsx
<CategoryDropdown helpText={getCategoryHelpText(selectedCategory)} />

function getCategoryHelpText(category: string): string {
  switch (category) {
    case "Marketing Campaign":
      return "Use for promotional credits, referral bonuses, or marketing initiatives";
    case "Credit Refund":
      return "Use for general refunds or credit adjustments";
    case "Order incorrectly marked as not collected":
      return "Use when restaurant credit is needed for incorrectly marked orders";
    case "Full Order Refund":
      return "Use for complete order refunds requiring restaurant compensation";
    default:
      return "";
  }
}
```

### 3. **Real-time Validation**

- Validate `user_id` XOR `restaurant_id` on blur
- Validate `amount > 0` on blur
- Show character count for `reason` and `comment` fields
- Disable submit button until all required fields are valid

### 4. **Currency Display**

```tsx
// Fetch market/currency info when user/restaurant is selected
useEffect(() => {
  if (selectedUserId) {
    fetchUserMarket(selectedUserId).then(market => {
      setCurrency(market.currency_code); // e.g., "ARS", "PEN", "CLP"
    });
  }
}, [selectedUserId]);

// Display currency next to amount field
<AmountInput suffix={currency} />
```

## Migration Checklist

- [ ] Update form field definitions (swap category/reason)
- [ ] Replace category text input with dropdown
- [ ] Replace reason dropdown with text area
- [ ] Implement conditional validation for restaurant-specific categories
- [ ] Update API request payload structure
- [ ] Update form validation rules
- [ ] Test all error scenarios
- [ ] Update user documentation/tooltips
- [ ] Verify backward compatibility (if needed)
- [ ] Update E2E tests

## Testing Scenarios

### Happy Path Tests

1. ✅ Create customer credit with "Marketing Campaign" category
2. ✅ Create customer credit with "Credit Refund" category
3. ✅ Create restaurant credit with "Full Order Refund" category
4. ✅ Create request with optional `reason` field filled
5. ✅ Create request with optional `reason` field empty

### Validation Tests

1. ❌ Submit with both `user_id` and `restaurant_id` → Error
2. ❌ Submit with neither `user_id` nor `restaurant_id` → Error
3. ❌ Submit with invalid category value → Error
4. ❌ Submit "Full Order Refund" with `user_id` instead of `restaurant_id` → Error
5. ❌ Submit with `amount = 0` → Error
6. ❌ Submit with `amount < 0` → Error
7. ❌ Submit with `reason` exceeding 500 characters → Error

## Support

For questions or issues with this implementation:

1. **Backend API Documentation**: `docs/zArchive/roadmap/API_VERSIONING_CONSISTENCY_FIX.md`
2. **Schema Reference**: `app/schemas/consolidated_schemas.py` (line 1074+)
3. **Validation Logic**: `app/services/discretionary_service.py` (line 276+)
4. **Enum Definition**: `app/config/enums/discretionary_reasons.py`

## Changelog

- **Feb 10, 2026**: Added Enriched Discretionary API documentation (endpoints, response schema, `created_by` / `created_by_name`, table and detail-view examples)
- **Feb 10, 2026**: Initial guide created for schema swap (Option A implementation)
