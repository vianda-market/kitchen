# Plans Page Market Filter – Backend Functional Requirements

**Date**: February 2026  
**Context**: Frontend Plans page filter by market  
**Status**: Feedback / requirements for backend

---

## Situation

The Plans page in the frontend lets users filter subscription plans by market via a "Filter by Market" dropdown. The UI calls the plans API with an optional `market_id` query parameter. If the backend does not support this filter, or returns a different response shape when the parameter is present, the filter appears not to work (empty list, error, or no change when selecting a market).

This document states the **functional requirements** the backend must satisfy so the filter works as intended. It does not prescribe implementation (query design, indexing, or response formatting).

---

## Functional Requirements

### 1. Filtering by market

- The backend **SHALL** support an optional query parameter that restricts the list of plans to a single market.
- The parameter name used by the frontend is **`market_id`** (value: UUID of the market).
- When **`market_id`** is present and valid:
  - The response **SHALL** contain only plans that belong to that market (or an empty list if none).
- When **`market_id`** is absent:
  - The response **SHALL** contain all plans (subject to existing auth/scoping and archiving rules).
- When **`market_id`** is present but invalid (e.g. unknown UUID, archived market):
  - The backend **SHALL** indicate an error (e.g. 400 Bad Request or 404) with a clear message, **OR** return an empty list, depending on product policy. The frontend should not receive a 200 with a non-array body or an ambiguous structure.

### 2. Response shape

- For the endpoint used by the Plans page list (e.g. **GET** **`/api/v1/plans/enriched/`**), the response body **SHALL** be a **single JSON array** of plan objects (or an empty array).
- The same response shape **SHALL** be used whether **`market_id`** is present or not (so the frontend can parse the response the same way in both cases).
- Each plan object **SHALL** include whatever fields the frontend needs to display the table and support create/edit (e.g. plan identifier, name, market info, price, credit, rollover, status). The exact field set is defined by existing API contract or separate spec.

### 3. Consistency with existing behaviour

- Filtering by **`market_id`** **SHALL** respect the same authorization and scoping rules as the unfiltered list (e.g. role-based access, institution scoping if any).
- Archived plans **SHALL** be included or excluded in the filtered response in the same way as in the unfiltered response (e.g. governed by an existing `include_archived` or equivalent).

---

## Out of scope

- How the backend implements the filter (DB queries, indexes, caches).
- Other query parameters (pagination, sort, search) unless they are required for the filter to work correctly.
- Create/update/delete of plans; this document concerns only the **list/filter** behaviour.

---

## References

- Frontend: Plans page uses **GET** **`/api/v1/plans/enriched/`** with optional **`?market_id={uuid}`**.
- Existing docs: e.g. `docs/api/MARKET_BASED_SUBSCRIPTIONS.md`, `docs/api/feedback_for_backend/MARKET_MIGRATION_COMPLETED.md`.
