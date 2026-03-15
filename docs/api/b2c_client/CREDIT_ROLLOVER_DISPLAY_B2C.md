# Credit Rollover Display (B2C)

**Audience:** B2C client (mobile app).  
**Purpose:** Guide the display of rollover behavior so customers understand that unused credits carry over.

---

## Backend behavior

All plans currently have:
- **rollover**: `true` – Unused credits carry over to the next renewal.
- **rollover_cap**: `null` – No limit; all remaining credits roll over.

On each renewal, the customer's balance becomes **rolled credits + plan.credit**. Rolled credits = the previous balance (uncapped).

---

## UI recommendation

1. **Display a rollover sign/badge** on plan cards and subscription details to indicate that credits carry over.

2. **Show reassurance copy** so customers understand they keep unused credits. Examples:
   - "Unused credits carry over to next month alongside your renewal credits."
   - "Your credits roll over every month—no limit."
   - "Unused credits carry over with your renewal."

3. **Where to show it:**
   - Plan picker (when selecting a plan)
   - Profile-plan (subscription details)
   - Success screen after payment

---

## API fields

The subscription enriched response includes `plan_rollover` and `plan_rollover_cap` (when available). For now these will be `true` and `null` respectively. The B2C client can use them to conditionally show the rollover badge, or simply always show it given current behavior.
