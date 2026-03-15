# Plate Kitchen Days – Edit Guardrails Recommendation

**Date**: February 10, 2026  
**Purpose**: Backend guardrails for `plate_kitchen_days` so only intended fields are editable and audit history stays clear.  
**Status**: ✅ Implemented (Option B – Reject)

---

## Summary

`plate_kitchen_days` has an audit table. To keep history meaningful and avoid surprising edits, we recommend:

- **Immutable on update**: `plate_id` (and any other fields that define *which* plate/restaurant the record belongs to).
- **Editable on update**: `kitchen_day`, `status` (and any other lifecycle/attribute fields the API already allows).

Backend should enforce this so that even if a client sends `plate_id` on PUT/PATCH, the server ignores or rejects it.

---

## Rationale

1. **Audit clarity**  
   Changing `plate_id` turns one record into a different business thing (a kitchen day for another plate/restaurant). That’s clearer in the audit log as “old record archived, new record created” rather than “plate_id changed from A to B.”

2. **One record = one (plate, day) pair**  
   Keeping `plate_id` immutable keeps the meaning of each row stable and avoids ambiguous history.

3. **“Move” a day to another plate**  
   Correct flow: create a new kitchen day for the new plate and archive the old one. No need to allow editing `plate_id`.

4. **Corrections vs identity**  
   - **Editable**: `kitchen_day` (e.g. wrong day selected), `status` (e.g. activate/deactivate/archive). Same logical record, clear audit: “kitchen_day changed from Monday to Tuesday” or “status changed to Inactive.”  
   - **Immutable**: `plate_id` — changing it is “different record,” so it should be done via create + archive.

---

## Recommended Backend Behavior

### PUT / PATCH `plate_kitchen_days/{id}`

- **Accept for update**: `kitchen_day`, `status` (and any other fields that are explicitly defined as updatable in your API spec).
- **Ignore or reject**: `plate_id` (and any other identity/link fields that should not change after creation).

Concrete options:

- **Option A – Ignore**: Do not read `plate_id` from the request body on update; never change it after insert.
- **Option B – Reject**: If `plate_id` (or other immutable fields) is present in the body, return `400 Bad Request` with a message such as: `"plate_id cannot be changed on an existing kitchen day; create a new record and archive the old one if needed."`

Option B is stricter and makes the contract obvious to API consumers.

---

## Frontend Alignment

The frontend will:

- Only send **editable** fields on update (e.g. `kitchen_day`, `status`).
- Not send `plate_id` on edit.

Backend guardrails are still recommended so that:

- Misbehaving or legacy clients cannot change `plate_id` by mistake.
- The rule is enforced in one place (backend) and documented for all consumers.

---

## References

- Audit table: existing audit/versioning for `plate_kitchen_days`.
- Bulk create: `POST /api/v1/plate-kitchen-days/` with `plate_id` + `kitchen_days` (create only; no conflict with this recommendation).
