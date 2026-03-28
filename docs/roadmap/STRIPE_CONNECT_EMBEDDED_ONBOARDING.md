# Supplier Payout Aggregator Onboarding — Roadmap

**Status**: Roadmap (next implementation phase)
**Last Updated**: 2026-03
**Depends on**: `STRIPE_SUPPLIER_OUTBOUND_CONNECT_ROADMAP.md` (Phase 1 complete)

---

## 1. Context and motivation

Phase 1 implemented redirect-based onboarding via Stripe Account Links for supplier payout setup.
This roadmap replaces that with:

1. **Aggregator-agnostic onboarding** — the DB and API model the concept of a "payout provider"
   per market, not Stripe specifically. Peru (and future markets) may use a different aggregator.
2. **Embedded onboarding for Stripe markets** — instead of redirecting suppliers to Stripe's hosted
   page, the Stripe Account Onboarding component renders inside vianda-platform. Suppliers never
   leave the site.

---

## 2. Aggregator support by market

| Market | Country | Supported aggregator | Notes |
|--------|---------|----------------------|-------|
| Argentina | AR | Stripe | ✓ Stripe Connect supported |
| Brazil | BR | Stripe | ✓ Stripe Connect supported |
| Chile | CL | Stripe | ✓ Stripe Connect supported |
| Mexico | MX | Stripe | ✓ Stripe Connect supported |
| USA | US | Stripe | ✓ Stripe Connect supported |
| Peru | PE | TBD | ✗ Stripe Connect not supported — alternative TBD (e.g. dLocal, Culqi, Niubiz) |

The aggregator for a market is stored in DB and drives which onboarding flow the UI presents
and which gateway the API calls at payout time.

---

## 3. DB changes

### 3.1 New table: `billing.market_payout_aggregator`

Maps each market to its active payout aggregator. One row per market.

```sql
CREATE TABLE billing.market_payout_aggregator (
    market_id       UUID        PRIMARY KEY,
    aggregator      VARCHAR(50) NOT NULL,   -- 'stripe', 'dlocal', 'culqi', etc.
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    notes           TEXT        NULL,
    FOREIGN KEY (market_id) REFERENCES core.market_info(market_id) ON DELETE RESTRICT
);
```

Seeded at DB build time with the supported markets above.
Peru row has `is_active = FALSE` and `aggregator = 'none'` until an alternative is selected.

### 3.2 Replace `stripe_connect_account_id` with provider-agnostic field

Rename `stripe_connect_account_id` → `payout_provider_account_id` on `institution_entity_info`.
Add `payout_aggregator VARCHAR(50) NULL` to record which aggregator the ID belongs to
(e.g. `'stripe'`, `'dlocal'`) since the ID format differs per aggregator.

```sql
-- On ops.institution_entity_info and audit.institution_entity_history:
payout_provider_account_id VARCHAR(255) NULL,  -- replaces stripe_connect_account_id
payout_aggregator           VARCHAR(50)  NULL,  -- 'stripe' | 'dlocal' | etc.
```

### 3.3 New field: `payout_onboarding_status`

Replace the planned `stripe_onboarding_status` with a provider-agnostic name.

```sql
payout_onboarding_status VARCHAR(50) NULL
-- values: null (not started), 'pending', 'complete'
-- meaning is aggregator-independent: has the entity completed payout setup?
```

Updated by the aggregator webhook handler when onboarding is confirmed.

---

## 4. New API endpoint: get aggregator for entity's market

```
GET /api/v1/institution-entities/{entity_id}/payout-aggregator
```

Returns the aggregator configured for the entity's market:
```json
{
  "market_id": "uuid",
  "aggregator": "stripe",
  "is_active": true
}
```

Frontend uses this to decide which onboarding UI to show (Stripe embedded, dLocal form, or
"coming soon" for unsupported markets).

---

## 5. Onboarding flow — Stripe markets (embedded)

Replaces the redirect-based Account Links flow for AR, BR, CL, MX, US.

```
vianda-platform (React)                    kitchen API                    Stripe
       |                                        |                            |
       | GET /payout-aggregator          ──────>|                            |
       |<── { aggregator: "stripe" }            |                            |
       |                                        |                            |
       | POST /stripe-connect/account-session ─>| stripe.Account.create()   |
       |                                        |────────────────────────────>
       |                                        |<── acct_…                  |
       |                                        | stripe.AccountSession      |
       |                                        |   .create(acct_…)  ───────>|
       |<── { client_secret }  ─────────────────|<── client_secret           |
       |                                        |                            |
       | render <ConnectAccountOnboarding>      |                            |
       | [supplier fills KYC on-page]           |                            |
       | onExit callback                        |                            |
       |                                        |                            |
       |              [account.updated webhook] |                            |
       |                                        |<── account.updated         |
       |                                        | SET payout_onboarding_status='complete'
       |                                        | SET payout_aggregator='stripe'
```

### 5.1 New endpoint: Account Session

```
POST /api/v1/institution-entities/{entity_id}/stripe-connect/account-session
```

- Creates (or reuses) `payout_provider_account_id` for Stripe
- Calls `stripe.AccountSession.create(account=acct_…, components={"account_onboarding": {"enabled": True}})`
- Returns `{ client_secret, payout_provider_account_id }`
- `client_secret` expires in minutes — always regenerate, never cache
- Prefill at account creation: entity `name`, market country

### 5.2 Frontend: Stripe embedded component

```typescript
// After GET /payout-aggregator returns aggregator: "stripe"
const { client_secret } = await api.post(
  `/institution-entities/${entityId}/stripe-connect/account-session`
);

const stripeConnectInstance = loadConnectAndInitialize({
  publishableKey: STRIPE_PUBLISHABLE_KEY,
  fetchClientSecret: async () => client_secret,
  appearance: { variables: { colorPrimary: "#your-brand-color" } },
});

<ConnectComponentsProvider connectInstance={stripeConnectInstance}>
  <ConnectAccountOnboarding
    onExit={() => checkOnboardingStatus(entityId)}
  />
</ConnectComponentsProvider>
```

After `onExit`, call `GET /stripe-connect/status` to check `payouts_enabled`.

---

## 6. Onboarding flow — unsupported markets (Peru and future)

When `GET /payout-aggregator` returns `is_active: false`:

- Show message: "Payout setup for your market is coming soon. Contact support to be notified."
- No onboarding component rendered
- `payout_onboarding_status` stays null

When a new aggregator is integrated for Peru, only the backend gateway and the
`market_payout_aggregator` row need to change — the frontend logic (`is_active` check) stays the same.

---

## 7. Fix Connect webhook (Stripe)

**Root cause from testing**: The Stripe Dashboard webhook was configured as a **platform webhook**
("Events on your account"), not a **Connect webhook** ("Events on Connected accounts"). This caused
all `account.updated` events for connected accounts to be silently dropped.

**Required**: Create a new webhook endpoint in Stripe Dashboard as type **"Events on Connected accounts"**.

Events:
- `account.updated` → sync `payout_onboarding_status` and `payouts_enabled` to entity
- `transfer.created` → confirm `provider_transfer_id` on payout row
- `transfer.reversed` → mark payout/bill Failed
- `payout.paid` → mark payout Completed, bill Paid
- `payout.failed` → mark payout/bill Failed

Update `_handle_account_updated` to write to `payout_onboarding_status` (not `stripe_onboarding_status`).

---

## 8. Implementation checklist

### Backend
- [ ] Add `billing.market_payout_aggregator` table + seed rows to `schema.sql` + `seed.sql`
- [ ] Rename `stripe_connect_account_id` → `payout_provider_account_id`; add `payout_aggregator` and `payout_onboarding_status` to `institution_entity_info` + history + trigger
- [ ] Update `InstitutionEntityDTO` and response schemas with new field names
- [ ] Update `connect_gateway.py` and `connect_mock.py` to use `payout_provider_account_id`
- [ ] New endpoint `GET /institution-entities/{entity_id}/payout-aggregator`
- [ ] New endpoint `POST /institution-entities/{entity_id}/stripe-connect/account-session`
- [ ] Add `stripe.AccountSession.create()` to `connect_gateway.py` and mock
- [ ] Update `_handle_account_updated` webhook handler to sync `payout_onboarding_status`
- [ ] Stripe Dashboard: create Connect-type webhook (sandbox + live); update `STRIPE_CONNECT_WEBHOOK_SECRET`

### Frontend (vianda-platform)
- [ ] Call `GET /payout-aggregator` to determine which onboarding UI to render
- [ ] Stripe path: install `@stripe/connect-js`, call `account-session`, render `<ConnectAccountOnboarding>`
- [ ] Unsupported market path: render "coming soon" message
- [ ] Show `payout_onboarding_status` on entity detail page
- [ ] Add "Complete payout setup" re-entry for incomplete onboarding

### Documentation
- [ ] Update `docs/api/b2b_client/STRIPE_CONNECT_SUPPLIER_PAYOUT_B2B.md` with embedded flow and aggregator model
- [ ] Create `docs/api/b2b_client/SUPPLIER_PAYOUT_ONBOARDING_B2B.md` — aggregator-agnostic onboarding guide for vianda-platform agent

---

## 9. Future: Peru aggregator integration

When a Peru aggregator (dLocal, Culqi, Niubiz, or other) is selected:
1. Add new gateway file `app/services/payment_provider/{aggregator}/connect_gateway.py`
2. Update `billing.market_payout_aggregator` row for PE: set `aggregator` + `is_active = TRUE`
3. Frontend: add aggregator-specific onboarding component/form for PE
4. No changes to the entity model or payout table — `payout_provider_account_id` and
   `payout_aggregator` already accommodate any provider

---

## 10. References

- Stripe Embedded Onboarding: https://docs.stripe.com/connect/embedded-onboarding
- Connect.js React: https://docs.stripe.com/connect/connect-js-react
- Account Sessions API: https://docs.stripe.com/api/account_sessions/create
- Phase 1 implementation: `app/services/payment_provider/stripe/connect_gateway.py`
- B2B integration guide: `docs/api/b2b_client/STRIPE_CONNECT_SUPPLIER_PAYOUT_B2B.md`
- Peru market context: `docs/roadmap/VIANDA_EMPLOYER_BENEFITS_PROGRAM.md` (multi-market design)
