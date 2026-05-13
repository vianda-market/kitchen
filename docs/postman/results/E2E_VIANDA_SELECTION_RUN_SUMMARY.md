# E2E Vianda Selection – test run summary (7 failures)

From **E2E Vianda Selection.postman_test_run.json** (run 2026-02-12): **104 passed**, **7 failed**.

---

## Fixes applied

- **Create Customer Subscription (500):** Backend now resolves `market_id` from the plan when creating a subscription (`app/services/crud_service.py`), so POST /subscriptions no longer fails with missing `market_id`.
- **Get Bills:** Collection updated to use `institutionId` (not `institutionEntityId`) for the `institution_id` query parameter.
- **Record Manual Payment:** Replaced with **Get institution bill by ID (payment via pipeline)**. The `POST .../record-payment` and `POST .../mark-paid` endpoints were removed; supplier payment is now via the settlement→bill→payout pipeline (see docs/api/internal/SUPPLIER_INSTITUTION_PAYMENT.md). The step now uses `GET .../institution-bills/{{entityBillId}}` to verify the bill.
- **Register vianda selection:** Pre-request script now ensures a valid `vianda_id` is set (from `plateSelectionId` from List Viandas for Customer, or fallback `plateId` from Register Supplier Vianda).

---

## 1. Create Customer Subscription — **500 Internal Server Error** ✅ FIXED

- **Request:** `POST {{baseUrl}}/api/v1/subscriptions`
- **Body:** `plan_id` from collection variable `planId` (set in "Create Subscription Plans").
- **Effect:** Test "Created subscription" fails; `subscriptionId` is never set.
- **Downstream:** Register Client Bill, Update Subscription Balance, and related steps depend on `subscriptionId`; they will fail or use empty values.

**Next step:** No longer needed; backend sets `market_id` from plan.

---

## 2. ~~Fintech Link Assignment~~ — **REMOVED**

- **Request:** `POST {{baseUrl}}/api/v1/fintech-link-assignment`
- **Effect:** All 4 tests fail (endpoint removed; payment methods use Stripe/external_payment_method).
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

## 5. Register vianda selection — **404 Not Found**

- **Request:** `POST {{baseUrl}}/api/v1/vianda-selections/`
- **Body:** `vianda_id`: `{{plateSelectionId}}`, `pickup_time_range`: `"12:00-12:15"`.
- **Note:** `plateSelectionId` is set in "List Viandas for Customer" from the first vianda’s `vianda_id` (variable name is misleading but value is a vianda_id).
- **Possible causes:** Route not registered as expected, or backend returns 404 for invalid/unauthorized vianda (e.g. vianda not available for customer/market).

**Next step:** Confirm POST /api/v1/vianda-selections/ is registered and which conditions return 404; check server logs for this request.

---

## 6. Issue bills — **400 Bad Request**

- **Request:** `POST {{baseUrl}}/api/v1/institution-bills/`
- **Effect:** No test assertions; failure is from status 400.
- **Likely cause:** Backend returns 400 when the restaurant has **no balance to bill** (e.g. no vianda selections / transactions in the period). The service creates a bill only when `balance_record.balance > 0`.

**Next step:** Ensure the E2E flow has created vianda selections and completed orders so the restaurant has balance; then Issue bills can succeed.

---

## 7. Get institution bill by ID (formerly Record Manual Payment)

- **Request:** `GET {{baseUrl}}/api/v1/institution-bills/{{entityBillId}}`
- **Note:** The record-payment and mark-paid endpoints were removed. This step now only verifies the bill exists. Supplier payment is done via the settlement→bill→payout pipeline (cron / `run_daily_settlement_bill_and_payout`).
- If this step fails with 404 or 422, ensure `entityBillId` is set from Get Bills or Issue bills (valid UUID).

---

## Cascade summary

| Root / early failure     | Dependent failures |
|--------------------------|--------------------|
| (1) Create Customer Subscription 500 | (3) Register Client Bill 422 → (4) Update Subscription Balance 422 |
| (3) No clientBillId      | (7) Get bill may 404/422 if entityBillId invalid |
| (6) Issue bills 400      | (7) No valid bills → entityBillId not set |

**Suggested order to fix:**  
1) Resolve **Create Customer Subscription** 500 (backend + variables).  
2) Resolve **Fintech Link Assignment** 403 (auth/role).  
3) Resolve **Issue bills** 400 (body/params).  
4) Re-run; then debug **Register vianda selection** 404 if it still fails (route or business logic).
