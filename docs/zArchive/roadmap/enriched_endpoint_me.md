# Enriched `/me` Endpoint Enhancement Roadmap

## Executive Summary

**Current State**: `GET /users/me` already returns enriched data (`UserEnrichedResponseSchema`). No separate `/users/me/enriched` endpoint is needed.

**Question**: Should other user-scoped entities have `/me` endpoints with enriched data?

**Recommendation**: **Selective implementation** - Only add `/me` endpoints for entities where:
1. Users frequently access their own data
2. Enriched data provides significant value
3. Current endpoints require `user_id` in path (security risk)

---

## Current State Analysis

### ✅ Users: Already Implemented

| Endpoint | Returns | Status |
|----------|---------|--------|
| `GET /users/me` | `UserEnrichedResponseSchema` | ✅ **Already enriched** |
| `PUT /users/me` | `UserResponseSchema` | ✅ Implemented |
| `PUT /users/me/terminate` | `dict` | ✅ Implemented |
| `PUT /users/me/employer` | `UserResponseSchema` | ✅ Implemented |

**Conclusion**: No action needed - `/users/me` IS the enriched version.

---

## Candidate Entities for `/me` Endpoints

### 1. Addresses

**Current Endpoints**:
- `GET /addresses/` - List all addresses (user-scoped for Customers)
- `GET /addresses/{address_id}` - Get single address
- `GET /addresses/enriched/` - List enriched addresses
- `GET /addresses/enriched/{address_id}` - Get single enriched address

**Current Behavior**:
- Customers: Auto-filtered to their own addresses
- Backend handles scoping automatically

**Analysis**:
- ✅ Users frequently access their own addresses
- ✅ Enriched endpoints exist (`institution_name`, `user_username`, `user_first_name`, `user_last_name`)
- ⚠️ Current endpoints don't require `user_id` in path (no security risk)
- ⚠️ Backend already filters by `user_id` from JWT

**Recommendation**: ⚠️ **OPTIONAL** - Low priority
- Current pattern works well (backend auto-filters)
- `/addresses/me` would be convenience only, not security improvement
- Consider if UI frequently needs "my addresses" as a distinct operation

**If Implemented**:
```typescript
GET /addresses/me  // Returns user's addresses (enriched)
GET /addresses/me/enriched  // Same as above (redundant)
```

---

### 2. Payment Methods

**Current Endpoints**:
- `GET /payment-methods/` - List payment methods (user-scoped)
- `GET /payment-methods/{payment_method_id}` - Get single payment method
- `POST /payment-methods/` - Create payment method
- `PUT /payment-methods/{payment_method_id}` - Update payment method

**Current Behavior**:
- User-scoped: `user_id` extracted from JWT automatically
- No enriched endpoints exist

**Analysis**:
- ✅ Users frequently access their own payment methods
- ❌ No enriched endpoints exist (no related entity names needed)
- ✅ Current endpoints don't require `user_id` in path (no security risk)
- ✅ Backend already filters by `user_id` from JWT

**Recommendation**: ❌ **NOT NEEDED**
- No enriched data to add
- Current pattern is secure (no path parameter manipulation risk)
- `/payment-methods/me` would be redundant

---

### 3. Subscriptions

**Current Endpoints**:
- `GET /subscriptions/` - List subscriptions (user-scoped)
- `GET /subscriptions/{subscription_id}` - Get single subscription
- `POST /subscriptions/` - Create subscription
- `PUT /subscriptions/{subscription_id}` - Update subscription

**Enriched Schema**: `SubscriptionEnrichedResponseSchema` exists (includes `user_full_name`, `plan_name`, `currency_code`)

**Current Behavior**:
- User-scoped: `user_id` extracted from JWT automatically
- No enriched endpoints exist yet

**Analysis**:
- ✅ Users frequently access their own subscription
- ✅ Enriched schema exists (could add `plan_name`, `currency_code`)
- ✅ Current endpoints don't require `user_id` in path (no security risk)
- ✅ Backend already filters by `user_id` from JWT

**Recommendation**: ⚠️ **OPTIONAL** - Medium priority
- Enriched data would be valuable (`plan_name`, `currency_code`)
- But current pattern is secure
- Consider if users typically have only one subscription (then `/subscriptions/me` makes sense)

**If Implemented**:
```typescript
GET /subscriptions/me  // Returns user's subscription (enriched)
// Would include: plan_name, currency_code, user_full_name
```

---

### 4. Client Bills

**Current Endpoints**:
- `GET /client-bills/` - List client bills (user-scoped)
- `GET /client-bills/{bill_id}` - Get single bill
- `POST /client-bills/` - Create bill

**Current Behavior**:
- User-scoped: `user_id` extracted from JWT automatically
- No enriched endpoints exist

**Analysis**:
- ✅ Users frequently access their own bills
- ❌ No enriched endpoints exist (no related entity names needed)
- ✅ Current endpoints don't require `user_id` in path (no security risk)
- ✅ Backend already filters by `user_id` from JWT

**Recommendation**: ❌ **NOT NEEDED**
- No enriched data to add
- Current pattern is secure
- `/client-bills/me` would be redundant

---

### 5. Vianda Selections

**Current Endpoints**:
- `GET /vianda-selections/` - List vianda selections (user-scoped)
- `GET /vianda-selections/{selection_id}` - Get single selection
- `POST /vianda-selections/` - Create selection

**Current Behavior**:
- User-scoped: `user_id` extracted from JWT automatically
- No enriched endpoints exist

**Analysis**:
- ✅ Users frequently access their own selections
- ⚠️ Could benefit from enriched data (restaurant_name, vianda_name, product_name)
- ✅ Current endpoints don't require `user_id` in path (no security risk)
- ✅ Backend already filters by `user_id` from JWT

**Recommendation**: ⚠️ **OPTIONAL** - Medium priority
- Enriched data would be valuable (restaurant_name, vianda_name, product_name)
- But would require creating enriched endpoints first
- Consider if UI frequently displays selection details with restaurant/vianda names

**If Implemented**:
```typescript
GET /vianda-selections/me  // Returns user's selections (enriched)
// Would require: ViandaSelectionEnrichedResponseSchema
```

---

## Decision Matrix

| Entity | Has Enriched Schema? | Security Risk? | User Frequency | Priority | Recommendation |
|--------|---------------------|----------------|----------------|----------|----------------|
| **Users** | ✅ Yes | ✅ Fixed | High | ✅ **DONE** | Already implemented |
| **Addresses** | ✅ Yes | ❌ No | High | ⚠️ Low | Optional convenience |
| **Payment Methods** | ❌ No | ❌ No | High | ❌ None | Not needed |
| **Subscriptions** | ✅ Yes | ❌ No | High | ⚠️ Medium | Optional if single subscription |
| **Client Bills** | ❌ No | ❌ No | Medium | ❌ None | Not needed |
| **Vianda Selections** | ❌ No* | ❌ No | High | ⚠️ Medium | Optional if enriched schema created |

*Vianda Selections could benefit from enriched data but schema doesn't exist yet.

---

## Key Insight: Security vs. Convenience

### Why `/users/me` Was Needed

**Problem**: `GET /users/{user_id}` and `PUT /users/{user_id}` required `user_id` in the URL path, creating a security risk:
- Path parameter manipulation
- Accidental updates to wrong user
- Confusion between self-updates and admin operations

**Solution**: `/me` endpoints extract `user_id` from JWT token (no path parameter).

### Why Other Entities Don't Need `/me`

**Current Pattern**: Most user-scoped entities already extract `user_id` from JWT:
- `GET /payment-methods/` - Backend filters by `current_user["user_id"]`
- `GET /subscriptions/` - Backend filters by `current_user["user_id"]`
- `GET /addresses/` - Backend filters by `current_user["user_id"]` (for Customers)

**No Security Risk**: These endpoints don't require `user_id` in the path, so there's no path parameter manipulation risk.

**Conclusion**: `/me` endpoints for these entities would be **convenience only**, not security improvements.

---

## Recommendations

### ✅ High Priority: None

All critical security issues are resolved with `/users/me` endpoints.

### ⚠️ Medium Priority: Optional Enhancements

1. **Subscriptions** (`GET /subscriptions/me`):
   - **If**: Users typically have only one subscription
   - **Then**: `/subscriptions/me` makes semantic sense
   - **Enriched**: Include `plan_name`, `currency_code`, `user_full_name`
   - **Value**: Convenience and clarity

2. **Vianda Selections** (`GET /vianda-selections/me`):
   - **If**: UI frequently displays selection details with restaurant/vianda names
   - **Then**: Create enriched schema first, then add `/me` endpoint
   - **Enriched**: Include `restaurant_name`, `vianda_name`, `product_name`
   - **Value**: Reduced N+1 queries

### ⚠️ Low Priority: Optional Convenience

1. **Addresses** (`GET /addresses/me`):
   - **Value**: Semantic clarity ("my addresses")
   - **Trade-off**: Redundant with current `/addresses/` (already filtered)
   - **Decision**: Only if UI frequently needs "my addresses" as distinct operation

### ❌ Not Recommended

1. **Payment Methods**: No enriched data, current pattern is secure
2. **Client Bills**: No enriched data, current pattern is secure

---

## Implementation Plan (If Proceeding)

### Phase 1: Analysis & Design (1-2 days)

- [ ] Confirm UI needs for each candidate entity
- [ ] Design enriched schemas (if needed)
- [ ] Review current endpoint usage patterns
- [ ] Get stakeholder approval

### Phase 2: Schema Creation (If Needed)

- [ ] Create `ViandaSelectionEnrichedResponseSchema` (if proceeding with vianda selections)
- [ ] Add enriched service methods
- [ ] Update database queries with JOINs

### Phase 3: Endpoint Implementation (2-3 days per entity)

For each entity:
- [ ] Add `GET /{entity}/me` endpoint
- [ ] Return enriched data (if applicable)
- [ ] Add deprecation warnings to `/{entity_id}` endpoints (if they exist)
- [ ] Update documentation
- [ ] Add unit tests
- [ ] Update Postman collections

### Phase 4: Documentation & Migration (1 day)

- [ ] Update client documentation
- [ ] Add migration guide
- [ ] Update API documentation
- [ ] Monitor usage

---

## Decision Criteria

**Add `/me` endpoint if**:
1. ✅ Users frequently access their own data
2. ✅ Enriched data provides significant value (reduces N+1 queries)
3. ✅ Semantic clarity improves (e.g., "my subscription" vs "subscriptions")
4. ✅ Current endpoint requires `user_id` in path (security risk)

**Don't add `/me` endpoint if**:
1. ❌ No enriched data available or needed
2. ❌ Current pattern is already secure (no path parameter risk)
3. ❌ Backend already filters by JWT `user_id` automatically
4. ❌ Low user frequency or unclear use case

---

## Conclusion

**Current Status**: ✅ **No immediate action needed**

- `GET /users/me` already returns enriched data
- Other entities don't have security risks (no path parameter manipulation)
- Current patterns are secure and functional

**Future Consideration**: 
- Monitor UI needs for "my X" operations
- Consider `/subscriptions/me` if users typically have single subscription
- Consider `/vianda-selections/me` if enriched data is needed and schema is created

**Priority**: Low - These would be convenience enhancements, not security fixes.

---

## Related Documentation

- `USER_SELF_UPDATE_PATTERN.md` - `/me` endpoint pattern for users
- `ENRICHED_ENDPOINT_PATTERN.md` - Enriched endpoint pattern
- `API_DEPRECATION_PLAN.md` - Deprecation strategy for legacy endpoints

---

**Last Updated**: December 2024

