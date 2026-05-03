# Subscription Management – Future / Out of Scope

**Context**: B2C subscription actions (cancel, hold, resume) were implemented per [SUBSCRIPTION_ACTIONS_B2C.md](../api/b2c_client/feedback_from_client/SUBSCRIPTION_ACTIONS_B2C.md). The following items were left out of scope for the initial release and can be revisited during roadmap review.

---

## 1. Employee cancel / hold / resume on behalf of users

**Idea**: Allow Employees (e.g. support or ops) to perform cancel, put on hold, or resume for any subscription, not only the owning customer.

**Current**: Only Customers can call `POST .../cancel`, `.../hold`, `.../resume`, and only for their own subscription (enforced in route + `subscription_action_service`).

**Future**: Same service functions can be reused; add a second set of routes or a role check in the existing routes so that when `role_type == "Employee"` (or specific roles), skip the “must be owner” check and allow acting on any subscription by ID. Document which roles are allowed and any audit logging.

**When to revisit**: Support/ops need to cancel or pause a customer subscription from an admin tool.

---

## 2. Dedicated cron for hold-end reconciliation

**Idea**: A scheduled job (e.g. daily) that runs `reconcile_hold_subscriptions(db)` so that subscriptions whose `hold_end_date` has passed are moved to Active even if no one calls the enriched list or by-id endpoints.

**Current**: Reconciliation runs on-read: when a client calls `GET /subscriptions/enriched/` or `GET /subscriptions/enriched/{id}`, we call `reconcile_hold_subscriptions(db)` first, then return data. So status is corrected as soon as the client fetches.

**Future**: Add a small cron entry that opens a DB connection and calls `reconcile_hold_subscriptions(connection)` (e.g. daily). Ensures status is correct for reporting or other consumers that do not hit the enriched endpoints. Optional; on-read is sufficient for B2C.

**When to revisit**: Need consistent “Active” status for billing runs, reporting, or internal tools that read subscriptions without going through the enriched API.

---

## 3. Generic PUT subscription to allow subscription_status / hold dates

**Idea**: Allow updating `subscription_status`, `hold_start_date`, and `hold_end_date` via the generic `PUT /subscriptions/{id}` (e.g. for admin or internal tools) with validation.

**Current**: Action endpoints (`POST .../cancel`, `.../hold`, `.../resume`) are the supported contract for B2C. `SubscriptionUpdateSchema` does not expose `subscription_status` or hold dates, so generic PUT cannot change them.

**Future**: Add optional `subscription_status`, `hold_start_date`, `hold_end_date` to `SubscriptionUpdateSchema` and enforce the same business rules (valid transitions, hold max 3 months, etc.) in a shared validator used by both the action endpoints and the generic update. Restrict to certain roles (e.g. Employee) if desired. Keeps one source of truth for rules while allowing flexible updates from admin UIs.

**When to revisit**: Admin or internal tools need to correct status or hold dates without calling multiple action endpoints.
