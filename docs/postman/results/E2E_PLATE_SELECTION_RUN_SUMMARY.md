# E2E Plate Selection – test run summary (7 failures)

From **E2E Plate Selection.postman_test_run.json** (run 2026-02-12): **104 passed**, **7 failed**.

---

## Fixes applied

- **Create Customer Subscription (500):** Backend now resolves `market_id` from the plan when creating a subscription (`app/services/crud_service.py`), so POST /subscriptions no longer fails with missing `market_id`.
- **Get Bills:** Collection updated to use `institutionId` (not `institutionEntityId`) for the `institution_id` query parameter.
- **Record Manual Payment:** Pre-request script added to throw a clear error when `entityBillId` is not a valid UUID (e.g. `NO_BILLS_FOUND`), so the flow fails fast with a helpful message.
- **Register plate selection:** Pre-request script now ensures a valid `plate_id` is set (from `plateSelectionId` from List Plates for Customer, or fallback `plateId` from Register Supplier Plate).

---

## 1. Create Customer Subscription — **500 Internal Server Error** ✅ FIXED

- **Request:** `POST {{baseUrl}}/api/v1/subscriptions`
- **Body:** `plan_id` from collection variable `planId` (set in "Create Subscription Plans").
- **Effect:** Test "Created subscription" fails; `subscriptionId` is never set.
- **Downstream:** Register Client Bill, Update Subscription Balance, and related steps depend on `subscriptionId`; they will fail or use empty values.

**Next step:** No longer needed; backend sets `market_id` from plan.

---

## 2. Fintech Link Assignment — **403 Forbidden**

- **Request:** `POST {{baseUrl}}/api/v1/fintech-link-assignment`
- **Effect:** All 4 tests fail (Status 201, fintech_link_assignment_id, method_type_id, status).
- **Likely cause:** Endpoint may require admin or a different role; current request uses customer auth.

**Next step:** Ensure the request uses the **customer** auth token (same as for Register Payment Method as Link). If the token is from a different user than the payment method’s `user_id`, the backend returns 403.

---

## 3. Register Client Bill — **422 Unprocessable Entity**

- **Request:** `POST {{baseUrl}}/api/v1/client-bills/`
- **Pre-request:** Injects `paymentId`, `subscriptionId`, `customerUserId`, `planId`, `planCreditCurrencyId`, `planPrice`, `planCreditCurrencyCode`.
- **Cause:** Create Customer Subscription failed, so `subscriptionId` is missing/empty; payload is invalid.
- **Effect:** `clientBillId` is never set.

**Next step:** Fix Create Customer Subscription (1) first; then re-run. If 422 persists, inspect response body for validation errors.

---

## 4. Update Subscription Balance and Renewal — **422 Unprocessable Entity**

- **Request:** `POST {{baseUrl}}/api/v1/client-bills/{{clientBillId}}/process`
- **Cause:** Register Client Bill (3) failed, so `clientBillId` is empty or invalid.
- **Effect:** "Bill processed and archived" test fails.

**Next step:** Depends on fixing (3) and (1).

---

## 5. Register plate selection — **404 Not Found**

- **Request:** `POST {{baseUrl}}/api/v1/plate-selections/`
- **Body:** `plate_id`: `{{plateSelectionId}}`, `pickup_time_range`: `"12:00-12:15"`.
- **Note:** `plateSelectionId` is set in "List Plates for Customer" from the first plate’s `plate_id` (variable name is misleading but value is a plate_id).
- **Possible causes:** Route not registered as expected, or backend returns 404 for invalid/unauthorized plate (e.g. plate not available for customer/market).

**Next step:** Confirm POST /api/v1/plate-selections/ is registered and which conditions return 404; check server logs for this request.

---

## 6. Issue bills — **400 Bad Request**

- **Request:** `POST {{baseUrl}}/api/v1/institution-bills/`
- **Effect:** No test assertions; failure is from status 400.
- **Likely cause:** Backend returns 400 when the restaurant has **no balance to bill** (e.g. no plate selections / transactions in the period). The service creates a bill only when `balance_record.balance > 0`.

**Next step:** Ensure the E2E flow has created plate selections and completed orders so the restaurant has balance; then Issue bills can succeed.

---

## 7. Record Manual Payment — **422 Unprocessable Entity**

- **Request:** `POST {{baseUrl}}/api/v1/institution-bills/NO_BILLS_FOUND/record-payment`
- **Cause:** URL uses literal `NO_BILLS_FOUND` (or empty `clientBillId`), set when no bills are found earlier (e.g. Get Bills / Issue bills). Register Client Bill and Issue bills failed, so no valid bill ID is available.
- **Effect:** Server rejects invalid bill id.

**Next step:** Depends on fixing bill flow (1 → 3, then Issue bills). Ensure Record Manual Payment uses a valid bill id from collection/environment (e.g. from Get Bills or Issue bills).

---

## Cascade summary

| Root / early failure     | Dependent failures |
|--------------------------|--------------------|
| (1) Create Customer Subscription 500 | (3) Register Client Bill 422 → (4) Update Subscription Balance 422 |
| (3) No clientBillId      | (7) Record Manual Payment 422 (bad bill id) |
| (6) Issue bills 400      | (7) No valid bills for payment |

**Suggested order to fix:**  
1) Resolve **Create Customer Subscription** 500 (backend + variables).  
2) Resolve **Fintech Link Assignment** 403 (auth/role).  
3) Resolve **Issue bills** 400 (body/params).  
4) Re-run; then debug **Register plate selection** 404 if it still fails (route or business logic).
