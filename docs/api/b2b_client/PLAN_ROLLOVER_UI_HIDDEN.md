# Plan Rollover: UI Hidden (B2B)

**Audience:** B2B Vianda platform frontend.

---

## Summary

Rollover and rollover cap are currently **fixed** for all plans: rollover is enabled, cap is unlimited. The B2B platform **must not** expose these fields in the UI so users cannot configure them differently.

---

## Backend behavior

- **rollover**: Always `true` for all plans. Unused credits carry over to the next renewal.
- **rollover_cap**: Always `null` (no limit). All remaining credits roll over.

The backend enforces these defaults on plan create and ignores rollover/rollover_cap on plan update.

---

## B2B UI requirements

1. **Hide** the rollover toggle and rollover cap field from:
   - Plan create modal
   - Plan edit modal
   - Plan tables/lists

2. **Do not send** `rollover` or `rollover_cap` in POST or PUT requests. The API will apply defaults on create and will ignore these fields on update.

3. The API responses (GET plans, GET plans/enriched) may still include `rollover` and `rollover_cap` for internal consistency. The B2B UI should not display or offer to edit these values.

---

## Future flexibility

The API and database support rollover and rollover_cap. When we choose to allow configuration again:
- Remove the backend overrides in the plan create/update routes
- Unhide the fields in the B2B UI
- No database migration will be needed
