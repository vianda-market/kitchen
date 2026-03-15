# Feedback: Coworker eligibility — greyed-out coworkers and unexpected ineligibility

**Context:** After a user reserves a plate and selects "Offer to pick up", the app shows a list of coworkers from `GET /plate-selections/{id}/coworkers`. Per [POST_RESERVATION_PICKUP_B2C.md](./POST_RESERVATION_PICKUP_B2C.md), each coworker has `eligible: boolean`:
- **Eligible:** Coworker has not ordered yet for the same kitchen day
- **Ineligible:** Coworker already ordered from a different restaurant or different pickup time

The app displays ineligible coworkers as greyed out and disables selection. Users cannot notify ineligible coworkers.

---

## Issue reported

A user saw **one coworker** in the list who was **greyed out**. When tapping that greyed-out coworker, the modal closed unexpectedly (this was a frontend bug; fixed in the app).

---

## Ask for backend

1. **Verify eligibility logic**  
   When a coworker is returned with `eligible: false`, confirm the backend correctly applies:
   - Same kitchen day
   - Same pickup time window
   - Different restaurant vs same restaurant

   If a coworker appears ineligible but the user believes they should be eligible (e.g. same restaurant, same time, no prior order), there may be a bug or mis-scoping (e.g. employer address scoping per [EMPLOYER_ADDRESS_SCOPING_FEEDBACK.md](./EMPLOYER_ADDRESS_SCOPING_FEEDBACK.md)).

2. **Optional: reason for ineligibility**  
   **Implemented (March 2026).** The API now returns `ineligibility_reason` when `eligible: false`:
   - `"already_ordered_different_restaurant"` — Coworker has an order at a different restaurant
   - `"already_ordered_different_pickup_time"` — Coworker has an order at the same restaurant but a different pickup time window
   - `null` when eligible

3. **Edge cases**  
   - Same user with multiple orders for the same kitchen day
   - Coworker has employer but no order yet (should be eligible)
   - Time window comparisons across timezones

---

## Client-side behavior (current)

- Ineligible coworkers are shown greyed out with helper text: "Already ordered for a different time or restaurant"
- Tapping a greyed-out coworker does nothing (no longer closes the modal)
- Only eligible coworkers can be selected and notified
