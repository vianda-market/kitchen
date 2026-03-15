# Status on Create

**Audience**: Frontend (B2B/B2C), API consumers  
**Last updated**: 2026-02

---

## Rule: Do not require status on creation

For **create** (POST) requests, the backend **does not expect** a `status` value from the client. Clients may **omit** `status` or send `null`; the backend assigns a default (typically **Active**) when creating the record.

| Client sends | Backend behavior |
|--------------|------------------|
| Omit `status` | Backend sets default (e.g. `Active`) |
| `"status": null` | Backend sets default (e.g. `Active`) |
| `"status": "Active"` or `"status": "Inactive"` | Value is accepted and stored as provided |

---

## Rationale

- Newly created entities are usually meant to be active; requiring the client to send `status` on every create is redundant.
- Letting the backend assign status keeps creation contracts simple and avoids client mistakes (e.g. sending an invalid or context-inappropriate status).

---

## Where this applies

Any create endpoint for an entity that has a `status` field:

- **Users** – backend sets default (e.g. Active) when creating users (admin or signup).
- **Markets** – omit or null `status`; backend assigns Active.
- **Plans**, **Plates**, **Restaurants**, **Products**, **Institutions**, **Addresses**, **Employers**, **Institution entities**, **Plate kitchen days**, **National holidays**, **Restaurant holidays**, **Credit currencies**, **QR codes**, **Discretionary requests**, **Subscriptions**, **Payment methods**, **Fintech links**, etc. – same rule: omit or null on create; backend assigns the appropriate default (usually Active; some flows such as bills may use Pending).

---

## Moving forward

- **New integrations**: Omit `status` (or send `null`) on all create requests; rely on backend defaults.
- **Existing integrations**: You may continue to send an explicit `status` if desired; the backend accepts it. To simplify payloads, you can remove `status` from create requests and rely on defaults.

---

## Exceptions

Some create flows use a **non-Active** default by design (e.g. **Pending** for bills or discretionary requests). The backend still does not *require* the client to send `status`; it sets the correct default for that entity type.
