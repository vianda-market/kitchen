# Discretionary Request – Category Enums Split by Recipient Type (Customer vs Restaurant)

**Date**: February 2026  
**Context**: Discretionary credit request category options must differ by recipient type (Customer vs Restaurant). Backend serves enums; frontend keeps hardcoded fallbacks and warns when used.  
**Status**: Frontend proposal and backend requirements (no prescriptive backend implementation)

---

## Situation

Discretionary requests are created for **either** a customer (user) **or** a restaurant. The **Category** dropdown should show different options depending on the recipient type:

- **Customer**: categories applicable to end-user credits (e.g. Marketing Campaign, Credit Refund).
- **Restaurant**: categories applicable to restaurant credits (e.g. Marketing Campaign, Order incorrectly marked as not collected, Full Order Refund).

The frontend already has a "Credit for" (recipient_type) toggle and only shows the Category field after the user selects Customer or Restaurant. The frontend needs the correct list of category values for each recipient type. The same pattern as **Status** (and **status_user**) should be used: the backend serves enum values via the enums API; the client may keep hardcoded fallbacks and log a console warning when they are used (e.g. when the API does not yet expose the new keys or the request fails).

---

## Frontend Proposal

### 1. Two enum keys from the backend

The frontend will request **two** distinct enum keys from the enums API (e.g. **GET** **`/api/v1/enums/`** or equivalent):

| Key | When used | Purpose |
|-----|-----------|--------|
| **`discretionary_reason_customer`** | When "Credit for" = Customer | Categories allowed for discretionary credit to a **customer** (user). |
| **`discretionary_reason_restaurant`** | When "Credit for" = Restaurant | Categories allowed for discretionary credit to a **restaurant**. |

The frontend will call the same enums endpoint it uses today and will read these two keys when present. It will **not** use a single `discretionary_reason` key for the create form when recipient type is known; it may keep using `discretionary_reason` only for backward compatibility or legacy views if needed.

### 2. Hardcoded fallbacks and warning

The frontend will keep **hardcoded fallback** arrays for both keys. If the backend does not yet expose one or both keys, or the enums request fails, the frontend will use the fallback and log a **console warning** (e.g. `[EnumService] Using discretionary_reason_customer fallback — API did not include discretionary_reason_customer`).

**Fallback values (exact strings):**

- **`discretionary_reason_customer`**:  
  - Marketing Campaign  
  - Credit Refund  

- **`discretionary_reason_restaurant`**:  
  - Marketing Campaign  
  - Order incorrectly marked as not collected  
  - Full Order Refund  

The backend is not required to use these exact strings; the frontend uses them only so the form works before the backend exposes the new keys. Once the backend exposes the two keys, the frontend will use the API values and the fallback (and warning) will no longer be used for that key.

### 3. UI behaviour

- User selects "Credit for" = **Customer** → Category dropdown is shown and populated from **`discretionary_reason_customer`** (API or fallback).
- User selects "Credit for" = **Restaurant** → Category dropdown is shown and populated from **`discretionary_reason_restaurant`** (API or fallback).
- When the user changes "Credit for", the selected Category is cleared so that a category from the other type cannot be submitted.

---

## Backend Requirements (functional, non‑prescriptive)

### 1. Expose two category enum keys

- The backend **SHALL** expose, via the same enums API used by the frontend (e.g. **GET** **`/api/v1/enums/`**), **two** keys whose values are **string arrays** of category labels (or codes) allowed for discretionary requests:
  - One key for **customer** recipient (e.g. **`discretionary_reason_customer`**).
  - One key for **restaurant** recipient (e.g. **`discretionary_reason_restaurant`**).
- The **names** of the keys are for the backend and frontend to agree on (e.g. `discretionary_reason_customer` and `discretionary_reason_restaurant`); the frontend will request exactly these keys once agreed.
- The **values** in each array **SHALL** be the set of categories that the backend accepts for that recipient type when creating or validating a discretionary request. The backend may use the same or different naming (e.g. display labels vs internal codes) as long as the frontend can send a value that the backend accepts.

### 2. Consistency with validation

- When the backend validates or processes a create discretionary request (e.g. **POST** **`/api/v1/admin/discretionary/requests/`** or equivalent), it **SHALL** accept only categories that belong to the correct set for the given recipient:
  - If the request has **`user_id`** (customer), the backend **SHALL** accept only categories from the **customer** set.
  - If the request has **`restaurant_id`** (restaurant), the backend **SHALL** accept only categories from the **restaurant** set.
- If the client sends a category that is not in the correct set for the recipient, the backend **SHALL** reject the request (e.g. 400 Bad Request) with a clear message.

### 3. No prescribed implementation

- How the backend stores or derives the two lists (e.g. single table with a recipient_type column, two tables, config, or enum types) is **not** specified here.
- Whether the backend returns the same strings as the frontend fallbacks (e.g. "Marketing Campaign", "Credit Refund") or maps from internal codes to display strings is a backend design choice; the frontend will display whatever string array the API returns for each key.

---

## Out of scope

- Other discretionary request fields or approval flows.
- Changes to the enums API beyond adding the two new keys.
- Backend implementation details (database schema, caches, etc.).

---

## References

- Frontend: Discretionary create form with "Credit for" (Customer | Restaurant) and Category dropdown driven by **`discretionary_reason_customer`** or **`discretionary_reason_restaurant`**; fallbacks and warning in EnumService.
- Existing enum pattern: **status_user** and Status (backend serves, frontend fallback with warning). See e.g. `src/services/enumService.ts`.
- Existing docs: `docs/backend/feedback_for_backend/DISCRETIONARY_REQUEST_ONE_RECIPIENT_AND_CUSTOMER_FILTER.md`, `docs/backend/ENUM_SERVICE_API.md`.
