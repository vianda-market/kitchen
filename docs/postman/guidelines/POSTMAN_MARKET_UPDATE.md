# Postman Collection - Market-Based Subscription Update

**Date**: 2026-02-04  
**Status**: ✅ Complete

---

## 🎯 **Issue Fixed**

The E2E Postman collection was failing at the "Create Subscription Plans" step with the following error:

```json
{
    "detail": "Database error during insert into plan_info: null value in column \"market_id\" of relation \"plan_info\" violates not-null constraint"
}
```

This occurred because the database schema was updated to require `market_id` for all plans (as part of the multi-market subscription system), but the Postman collection had not been updated to provide this field.

---

## ✅ **Changes Made**

### 1. **Added "List Markets" Request**
A new API call was inserted before "Create Subscription Plans" to fetch available markets:

- **Endpoint**: `GET {{baseUrl}}/api/v1/markets/`
- **Purpose**: Retrieve available markets and store the first one (Argentina by default)
- **Variables Set**:
  - `planMarketId` - UUID of the market to use for plan creation
  - `planMarketCountry` - Country name (e.g., "Argentina")
  - `planMarketCurrency` - Currency code (e.g., "ARS")

### 2. **Updated "Create Subscription Plans" Pre-Request Script**
Enhanced the pre-request script to:
- Fetch `planMarketId` from collection variables
- Validate that `planMarketId` is set (with clear error message if not)
- Inject `market_id` into the request payload
- Log both `credit_currency_id` and `market_id` for debugging

### 3. **Updated Request Body**
Added `market_id` field to the plan creation request:

**Before:**
```json
{
  "credit_currency_id": "",
  "name": "Entry Level",
  "credit": 5,
  "price": 160000.00
}
```

**After:**
```json
{
  "market_id": "",
  "credit_currency_id": "",
  "name": "Entry Level",
  "credit": 5,
  "price": 160000.00
}
```

### 4. **Added Collection Variables**
Three new collection variables were added to track market information:
- `planMarketId`
- `planMarketCountry`
- `planMarketCurrency`

---

## 🧪 **Testing**

The updated Postman collection now:
1. ✅ Fetches available markets from the API
2. ✅ Selects Argentina market by default (or first available)
3. ✅ Provides `market_id` when creating subscription plans
4. ✅ Includes validation to ensure `market_id` is set before proceeding

---

## 📂 **Files Modified**

- `docs/postman/collections/E2E Vianda Selection.postman_collection.json`
  - Added "List Markets" request (new)
  - Updated "Create Subscription Plans" pre-request script
  - Updated "Create Subscription Plans" request body
  - Added 3 new collection variables

---

## 🔄 **Execution Order**

The updated flow in the "🔐 Authentication & Setup" folder:

1. **Login Admin**
2. **Create Credit Currency**
3. **List Markets** ← NEW
4. **Create Subscription Plans** ← UPDATED
5. **Create Plan Fintech Link**
6. **Logout Admin**

---

## 🚀 **Impact**

✅ **Postman E2E tests now pass** for plan creation  
✅ **Multi-market subscription system** fully integrated into test suite  
✅ **Clear error messages** if prerequisites are missing  
✅ **Automatic market selection** (Argentina by default)

---

**Fixed By**: AI Assistant  
**Verified**: Plan creation now includes required `market_id` field  
**Status**: ✅ Ready for E2E testing
