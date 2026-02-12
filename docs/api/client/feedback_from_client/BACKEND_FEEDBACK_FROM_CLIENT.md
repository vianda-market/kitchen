# Backend Feedback from Client Agent

## Questions for Backend Team

### Market Management UI

1. **Super Admin Check**: How does the frontend verify if the current user is a Super Admin vs Regular Admin?
   - Should we check `role_name === "Super Admin"` from JWT?
   - Or call a backend endpoint like `GET /api/v1/users/me` and check `role_name`?

2. **Market Dropdown Scoping**: For Suppliers creating plans, should the market dropdown:
   - Show all markets?
   - Show only markets where their institution operates?
   - How do we determine which markets an institution operates in?

3. **Market Selection During Registration**: When a new Customer registers, how do they select their market?
   - Is there a public endpoint `GET /api/v1/markets/public/` for unauthenticated users?
   - Or do they register first, then select market during onboarding?

4. **Multiple Subscriptions UI**: For users with subscriptions in multiple markets:
   - Should the UI show a market switcher in the navigation bar?
   - How do we handle plate browsing across markets? (Filter by active subscription's market?)

### Enriched Endpoints

5. **Pagination**: Do enriched endpoints support pagination?
   - If yes, what query parameters? (`limit`, `offset`, `page`, `per_page`?)

6. **Filtering**: Can enriched endpoints be filtered by market?
   - Example: `GET /api/v1/plans/enriched/?market_id=xxx`
   - Which endpoints support this?

7. **Sorting**: Do enriched endpoints support sorting?
   - Example: `GET /api/v1/plans/enriched/?sort_by=price&order=asc`

### Error Handling

8. **403 vs 404**: When a user tries to access a market they don't have permission for:
   - Should backend return 403 (Forbidden) or 404 (Not Found)?
   - What's the recommended UI behavior?

9. **Market Archived**: If a user has a subscription in a market that gets archived:
   - What happens to their subscription?
   - Should the UI show a warning?
   - Can they still view their order history in that market?

---

## Customer API Security - ID Exposure Concerns

### Critical Security Issue

**Problem**: Current enriched endpoints expose internal UUIDs (e.g., `restaurant_id`, `plate_id`, `institution_id`, `plan_id`) to all API consumers, including customer-facing mobile apps.

**Risk**: Customers should NOT see internal system identifiers. They should only see:
- ✅ Display names (restaurant names, plate names, product names)
- ✅ Their own information (email, phone, full name)
- ✅ Public-facing codes (QR codes, confirmation codes)
- ❌ Internal UUIDs (security risk, information leakage)

**Supplier ID Exposure**: Needs separate security audit. Consider:
- Which IDs should suppliers see?
- Restaurant staff should see confirmation codes, NOT customer UUIDs
- Payment/billing IDs may be acceptable for financial reconciliation

### Proposed Solution (Post-UAT Security Audit)

**Option A: Separate Customer Endpoints** (Recommended)
- Create `/api/v1/customer/plates/` endpoint with display-only data
- Create `/api/v1/customer/subscriptions/me` endpoint without internal IDs
- Backoffice/admin endpoints (`/enriched/`) keep full UUID exposure

**Option B: Role-Based Filtering**
- Existing enriched endpoints filter response fields based on `role_type`
- Customers get display-only schema (no UUIDs)
- Employees/Suppliers get full enriched schema

**Option C: Dedicated Customer Schemas**
- Create `PlateCustomerResponseSchema` without IDs
- Create `SubscriptionCustomerResponseSchema` without IDs
- Keep admin schemas as-is

### Required Security Audit

**Questions for Backend Team**:

10. **Customer Endpoint Inventory**: Which endpoints do customers currently access?
    - `GET /api/v1/plates/` - Browsing meals
    - `GET /api/v1/subscriptions/me` - View my subscription
    - `POST /api/v1/plate-selection/` - Order a meal
    - `GET /api/v1/plate-pickup/pending` - Check active order
    - **Full list needed**

11. **ID Exposure Severity**: For each customer endpoint, which UUIDs are exposed?
    - Are customers seeing `restaurant_id`, `plate_id`, `product_id`?
    - Can customers infer relationships from exposed IDs?
    - What information can be leaked from sequential or predictable IDs?

12. **Migration Strategy**: How to implement customer-facing endpoints without breaking existing admin UI?
    - Should customer apps use a separate base URL (`/customer/` vs `/api/v1/`)?
    - Should we version customer APIs separately (`/api/customer/v1/`)?
    - What's the rollout plan?

13. **Confirmation Code Strategy**: For customer-facing features like plate pickup:
    - Use short confirmation codes (e.g., "ABC123") instead of UUIDs
    - Customers show code to restaurant staff
    - Staff enters code to find order (no UUID exposure)

14. **Backwards Compatibility**: If customer apps are already using UUID-based endpoints:
    - What's the deprecation timeline?
    - How do we migrate existing mobile apps?

### Immediate Action for This Plan

**Decision**: Document the security concern now, implement fixes in separate post-UAT security audit.

**This Plan Scope**: 
- ✅ All enriched endpoints documented are for **backoffice/admin use only**
- ✅ Include security warning in `BACKEND_FEEDBACK_FROM_CLIENT.md`
- ✅ Document customer endpoint separation as future requirement
- ❌ Do NOT implement customer-facing endpoints in this plan

---

## Pending Clarifications

- **Geolocation + Markets**: How do markets relate to geolocation filtering? (Separate from this plan, but future concern)
- **Multi-Currency Handling**: Frontend display of prices in different currencies (formatting, symbols)
- **Customer API Security**: Full audit of customer-facing endpoints and ID exposure (post-UAT security review)
- **Supplier ID Sharing**: Analysis of which IDs suppliers should/shouldn't see (future security audit)

---

## Response Format

Please respond to each numbered question with:
- **Question Number**
- **Answer**
- **Implementation Guidance** (if applicable)
- **Related Documentation Links** (if available)

---

## Priority Questions

**High Priority** (needed for immediate frontend development):
- Questions 1, 2, 3, 4, 6

**Medium Priority** (needed within 2 weeks):
- Questions 5, 7, 8, 9

**Low Priority** (post-UAT):
- Questions 10-14 (Customer API Security)
