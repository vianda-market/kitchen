# Market Create/Update – country_code Only; Derive country_name from Code

**Date**: February 2026  
**Context**: The vianda-platform frontend (Markets page) now sends only **country_code** (ISO 3166-1 alpha-2) when creating or updating a market. The client no longer sends **country_name**. The backend should remove **country_name** from the Pydantic request schema and derive the country name from the code, then store both in the DB.  
**Status**: Request and recommendation for backend; no prescribed implementation.

---

## Request

### 1. Remove country_name from request schema

- For **POST /api/v1/markets/** (create) and **PUT /api/v1/markets/{id}** (update), remove **country_name** from the request body schema.
- The client will send only **country_code** (and other existing fields: e.g. credit_currency_id, timezone, status). **country_code** is **ISO 3166-1 alpha-2** (e.g. `"AR"`, `"DE"`, `"GB"`, `"US"`).

### 2. Derive country_name from country_code and store in DB

- When creating or updating a market, the backend must **resolve the country name** for the given **country_code** (alpha-2) and **store it in the DB** so the market row has both **country_code** and **country_name**.
- If the code is invalid (e.g. not in the backend’s source of truth), the backend **SHALL** return **400 Bad Request** with a clear message (e.g. `"Invalid country_code"`).
- **Response** bodies for market create/update/get **SHALL** continue to include **country_code** and **country_name** so the frontend table and edit form can display both; **country_name** is read from the DB after it was set from the resolution step.

---

## Recommendation: use pycountry to resolve code → name

- Use **[pycountry](https://pypi.org/project/pycountry/)** (Python, free, offline, no API key or registration) to look up the country name for a given alpha-2 code:
  - `country = pycountry.countries.get(alpha_2=country_code)`
  - `country_name = country.name` (pycountry’s **name** attribute is the standard short name, e.g. "Argentina", "Germany", "United Kingdom")
- If `get()` returns `None` (invalid code), return **400 Bad Request**.
- Then persist both **country_code** and **country_name** in the market record. No client-supplied **country_name** is used.

---

## Summary

| Aspect | Current (before change) | Requested |
|--------|--------------------------|-----------|
| Request body (create/update) | country_name, country_code, ... | **country_code** only (and other fields); **country_name** removed |
| Backend behavior | Accepts client’s country_name | Derive **country_name** from **country_code** (e.g. via pycountry) and store in DB |
| Response | country_code, country_name | Unchanged; still return both |

---

## References

- Frontend: Markets page; country dropdown with alpha-2 as value; payloads send only **country_code**.
- Plan: `docs/plans/MARKET_COUNTRY_DROPDOWN_PLAN.md`.
