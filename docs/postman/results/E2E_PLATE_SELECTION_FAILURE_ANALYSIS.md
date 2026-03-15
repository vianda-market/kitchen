# E2E Plate Selection – Postman Run Failure Analysis

**Run**: `E2E Plate Selection.postman_test_run.json`  
**Status**: error (71 pass, 8 fail in latest run after DB rebuild)  
**Date**: 2026-02-17

---

## Latest run (after DB rebuild)

After rebuilding the DB with the new schema:

- **Customer Signup Request** now returns **201 Created** and passes.
- **Get Dev Pending Token** returns **404 Not Found** → still one root cause (see below).
- The remaining 7 failures (Verify, Login, Register Address, etc.) cascade from that 404.

---

## Summary (original run)

The original 9 failures formed a **single chain**:

1. **Customer Signup Request** → **500 Internal Server Error** ← **fixed** (table existed after DB rebuild)
2. **Get Dev Pending Token** → **404 Not Found** ← **current root cause** (email query param: `+` decoded as space)
3. **Customer Signup Verify** → **422** (token empty because step 2 failed)
4. **Login Customer User** → **400** (user never created)
5. **Register Customer Address** → **401** (no auth token)

Fix the 404 (step 2) and re-run; steps 3–5 should then pass.

---

## Get Dev Pending Token – 404 (current root cause after DB fix)

| Item     | Value |
|----------|--------|
| Request  | `GET /api/v1/customers/signup/dev-pending-token?email=...` |
| Expected | 200 OK, `{ "token": "..." }` |
| Actual   | **404 Not Found** ("No pending signup found for this email") |

**Why it fails**

The customer email was generated as `client+<timestamp>@example.com`. In URL query strings, **`+` is decoded as a space** (application/x-www-form-urlencoded). So the server receives `email=client 1771309030158@example.com` (with a space) while the DB has `client+1771309030158@example.com` → no row found → 404.

**Fix applied**

The collection was updated so the signup email no longer contains `+`: it now uses `client_<timestamp>@example.com` (underscore). Re-run the collection; **Get Dev Pending Token** should then return 200 and set `signupVerificationToken`, and the rest of the flow should pass.

---

## 1. Customer Signup Request – 500 (original root cause, now fixed)

| Item        | Value |
|------------|--------|
| Request    | `POST /api/v1/customers/signup/request` |
| Expected   | 201 Created |
| Actual     | **500 Internal Server Error** |
| Failing test | "Signup request accepted" |

**Why it fails**

The handler calls `request_customer_signup`, which:

1. Validates the body and checks email/username in `user_info`.
2. Inserts a row into **`pending_customer_signup`** and sends the verification email.

A **500** here almost always means an **unhandled exception** in that path. The response body from the API should contain something like:

`"Error in customer signup request: <actual error>"`

**Most likely cause: missing table**

If the database does **not** have the table `pending_customer_signup`, the `INSERT` (or the `DELETE` before it) will raise a PostgreSQL error (e.g. `relation "pending_customer_signup" does not exist`). That is caught by `handle_business_operation` and turned into a 500.

**What to do**

1. **Apply schema/migrations** so that `pending_customer_signup` exists (see `app/db/schema.sql`).
2. In Postman (or logs), open the **response body** of **Customer Signup Request** and read the `detail` message to confirm the exact exception (e.g. missing table, constraint, or connection issue).
3. Check server logs for the full traceback (logged by `handle_business_operation`).

---

## 2. Get Dev Pending Token – 500

| Item     | Value |
|----------|--------|
| Request  | `GET /api/v1/customers/signup/dev-pending-token?email=...` |
| Expected | 200 OK, `{ "token": "..." }` |
| Actual   | **500 Internal Server Error** |

**Why it fails**

- If **DEV_MODE** is false, this endpoint returns **403**, not 500. So a **500** indicates a **server error**, usually in the DB read.
- The endpoint runs:  
  `SELECT verification_token FROM pending_customer_signup WHERE email = %s AND used = FALSE ...`
- So again, if **`pending_customer_signup`** does not exist (or the query fails for another reason), you get 500.

**What to do**

- Same as step 1: ensure the DB has `pending_customer_signup` and that migrations are applied.
- Ensure **DEV_MODE** is true if you want to use this dev-only endpoint (otherwise you’ll get 403 after fixing the DB).

---

## 3. Customer Signup Verify – 422

| Item     | Value |
|----------|--------|
| Request  | `POST /api/v1/customers/signup/verify` |
| Body     | `{ "token": "{{signupVerificationToken}}" }` |
| Expected | 201 Created, user + `access_token` |
| Actual   | **422 Unprocessable Entity** |

**Why it fails**

- **Get Dev Pending Token** failed, so **`signupVerificationToken`** was never set (or is empty).
- The request is sent with `"token": ""` (or missing), and the schema requires a non-empty token → validation fails → **422**.

This is a **downstream** effect of the signup request and dev-token steps failing.

**What to do**

- Fix the 500s on **Customer Signup Request** and **Get Dev Pending Token** so that the collection variable `signupVerificationToken` is set. Then **Customer Signup Verify** should receive a valid token and return 201.

---

## 4. Login Customer User – 400

| Item     | Value |
|----------|--------|
| Request  | `POST /api/v1/auth/token` (username/password) |
| Expected | 200 OK, `access_token` |
| Actual   | **400 Bad Request** |

**Why it fails**

- No user was created because **Customer Signup Verify** never succeeded.
- Login with the generated customer username/password fails (user does not exist or credentials invalid) → backend returns **400**.

**What to do**

- Once the signup flow (request → dev token → verify) succeeds, the customer user exists and login should return 200.

---

## 5. Register Customer Address – 401

| Item     | Value |
|----------|--------|
| Request  | `POST /api/v1/addresses` |
| Expected | 201 Created |
| Actual   | **401 Unauthorized** |

**Why it fails**

- **Login Customer User** failed, so **`authToken`** (and/or `clientUserAuthToken`) was never set.
- The request is sent without a valid Bearer token → **401**.

**What to do**

- Fix the signup and login steps so that the collection/environment has a valid `authToken` for the customer; then **Register Customer Address** should succeed.

---

## Checklist to fix the run

1. **Database**
   - [x] Ensure `pending_customer_signup` exists (run migrations / apply `app/db/schema.sql`). *(Done – Signup Request now 201.)*
2. **Customer Signup Request**
   - [x] Re-run **Customer Signup Request** and confirm **201**. *(Done.)*
3. **Get Dev Pending Token (404 fix)**
   - [x] Use an email format without `+` in the query (collection updated: `client_<timestamp>@example.com`).
   - [ ] Re-run collection; **Get Dev Pending Token** should return **200** and set `signupVerificationToken`.
4. **Dev token (for E2E)**
   - [ ] Set **DEV_MODE=true** if you use **Get Dev Pending Token**.
5. **Order**
   - [ ] Run the Client Setup folder in order: **Customer Signup Request** → **Get Dev Pending Token** → **Customer Signup Verify** → **Login Customer User** (optional if Verify already set `authToken`) → **Register Customer Address** and following requests.

After the email-format fix, the same collection run should show the remaining 8 failures passing.
