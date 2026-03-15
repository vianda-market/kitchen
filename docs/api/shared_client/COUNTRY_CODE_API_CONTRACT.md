# Country Code API Contract

**Audience**: Frontend (B2B/B2C), Postman users, API consumers  
**Last updated**: 2026-02

---

## Rule: Accept alpha-2 or alpha-3; store and return alpha-2 only

`country_code` **accepts** ISO 3166-1 **alpha-2** (e.g. `AR`, `US`) or **alpha-3** (e.g. `ARG`, `USA`). The API **normalizes at entry**: alpha-3 is converted to alpha-2 (uppercase), and the backend logs an info message when a conversion occurs. **Storage and responses use only alpha-2** (uppercase).

| Send (either form) | Stored / returned |
|--------------------|--------------------|
| `AR` or `ARG`      | `AR`               |
| `US` or `USA`      | `US`               |
| `PE` or `PER`      | `PE`               |
| `CL` or `CHL`      | `CL`               |
| `BR` or `BRA`      | `BR`               |
| `CA` or `CAN`      | `CA`               |
| `MX` or `MEX`      | `MX`               |

**Documentation**: *"country_code accepts ISO 3166-1 alpha-2 or alpha-3; the API normalizes to alpha-2 (uppercase) at the boundary. When alpha-3 is supplied, the backend converts to alpha-2 and logs the conversion; storage and responses are alpha-2 only."*

---

## Normalization

- **Request**: Case-insensitive **alpha-2** or **alpha-3** is accepted. The API normalizes to **uppercase alpha-2** at the boundary (e.g. `"ar"` → `"AR"`, `"ARG"` → `"AR"`). When alpha-3 is converted, an **info log** is written (e.g. `country_code alpha-3 converted to alpha-2: ARG -> AR`).
- **Response**: Stored and returned values are always **uppercase alpha-2** (e.g. `"AR"`, `"US"`).
- **Default**: For endpoints that allow omitting `country_code` (e.g. lead zipcode metrics), the default is **`US`** when omitted.

---

## Where country_code is used

- **Addresses**: Create/update, suggest — see [ADDRESSES_API_CLIENT.md](ADDRESSES_API_CLIENT.md).
- **Markets**: List/available, create/update — see [MARKET_SCOPE_FOR_CLIENTS.md](MARKET_SCOPE_FOR_CLIENTS.md). Response `country_code` is alpha-2.
- **Leads**: Zipcode metrics query param — default `US` when omitted.
- **Restaurant holidays**, **employers**, **location-info**: Same rule; use alpha-2 in all request bodies and query/path params.

---

## Postman collections

Postman collections in `docs/postman/collections/` may use **alpha-2** or **alpha-3** in request bodies and query parameters; both are accepted and normalized to alpha-2.

---

## Quick checklist

- [ ] Send **alpha-2** (AR, US, PE, CL, BR, CA, MX) or **alpha-3** (ARG, USA, PER, CHL, BRA, CAN, MEX); API normalizes to alpha-2.
- [ ] You may send lowercase; API normalizes to uppercase.
- [ ] When matching markets by `country_code`, compare to uppercase alpha-2 (e.g. `m.country_code === 'AR'`).
- [ ] Storage and responses are **alpha-2 only**; the backend logs when alpha-3 was converted at entry.
