# B2C Address Create: institution_id and user_id Optional

**Audience:** B2C client (Customer role only)  
**Last updated:** 2026-02

---

## Summary

For **POST /api/v1/addresses/** when the authenticated user is a **Customer** (B2C), the backend **does not require** `institution_id` or `user_id` in the request body. The API sets both from the current user’s JWT (e.g. Vianda Customers institution). The B2C app should **omit** these fields when creating addresses.

---

## Request

- **Endpoint:** `POST /api/v1/addresses/`
- **Auth:** Required (Bearer token; Customer role).

**Body:** Send address fields only. Do **not** send `institution_id` or `user_id`.

Example (B2C):

```json
{
  "country_code": "AR",
  "province": "Ciudad Autonoma de Buenos Aires",
  "city": "Ciudad Autonoma de Buenos Aires",
  "postal_code": "1414",
  "street_type": "Ave",
  "street_name": "Santa Fe",
  "building_number": "2567",
  "apartment_unit": "1A"
}
```

Do **not** send `address_type`; the backend derives it from linkages. Allowed types for Customers are Customer Home, Customer Billing, Customer Employer only.

---

## Response

- **201 Created:** Address created. Response includes `institution_id` and `user_id` set by the backend (from JWT).
- **400 Bad Request:**  
  - If the user’s JWT has no `institution_id`: message like *"Customer address requires institution context; missing institution_id on user."*  
  - Fix: ensure the Customer user is associated with an institution (e.g. Vianda Customers) when the token is issued.

---

## Safeguard (B2B vs B2C)

- **B2C (Customer):** Omitting `institution_id` and `user_id` is **allowed**; backend sets them from JWT.
- **B2B (Supplier/Employee):** Omitting either field returns **400** with a message that they are required for B2B. This is intentional so that B2B flows always send institution context.

---

## References

- Full address API (timezone, validation, types): [ADDRESSES_API_CLIENT.md](../shared_client/ADDRESSES_API_CLIENT.md)
- Address autocomplete (suggest/validate): [ADDRESS_AUTOCOMPLETE_CLIENT.md](../shared_client/ADDRESS_AUTOCOMPLETE_CLIENT.md)
