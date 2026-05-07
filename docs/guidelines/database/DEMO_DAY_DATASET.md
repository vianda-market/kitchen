# Demo-Day Dataset — What's In It, What It Shows

**Audience:** anyone presenting Vianda to stakeholders against the dev environment.
**Companion docs:**
- `DATABASE_REBUILD_PERSISTENCE.md` — how to load / purge / reset.
- `~/learn/vianda/docs/plans/demo_day_data.md` — current rollout plan (ephemeral).

This is a **living reference**. Update it when the dataset changes, when stakeholders ask "can we show X?" and we add it, or when you find something that doesn't render the way it should.

---

## What "demo-day" is and isn't

The demo-day dataset is a **moment-in-time snapshot** of what a healthy Vianda deployment looks like with real activity. It is not a historical backfill, a load test, or a representative production sample. Specifically:

- **One supplier, one restaurant, one plan.** A single Lima-based supplier called *Vianda Demo Peru SAC*, operating *Sabores del Pacifico* in Miraflores, on a single plan called *Estandar*.
- **One market.** Peru only (v1). Argentina and US demos are deferred — the goal of v1 is to get one market end-to-end demoable rather than three half-built ones.
- **Five customers in Lima.** Distributed across Miraflores, Barranco, San Isidro, Surco, and Jesús María — to make the geo and map UIs render meaningfully.
- **One active order per customer.** Each customer has placed an order today, scanned the QR code at the kiosk, and is awaiting completion. This populates dashboards, queues, and "today's activity" widgets. It does **not** populate weekly trends, retention curves, or historical charts.
- **No order history.** The API enforces one plate-selection per customer per day; we don't backdate via SQL because we want the demo to mirror real API behavior. A "looks like Tuesday afternoon at lunch rush" snapshot.

If a stakeholder asks "where are the trend charts?", the honest answer is *"this is dev with one day of activity — staging will eventually give you those."*

---

## The supplier

| Field | Value |
|---|---|
| Institution name | Vianda Demo Peru SAC |
| Institution type | supplier |
| Market | Peru (PE) |
| Currency | PEN (Peruvian Sol) |
| Tax ID (RUC) | 20601234567 |
| Office address | Av. Javier Prado Este 3580, San Isidro, Lima |
| Stripe payout onboarding | `complete` (so restaurants can activate) |
| UUID prefix | `dddddddd-dec0-0001-...` |

Created via SQL in `app/db/seed/demo_baseline.sql` because the supplier institution must exist before the API boots and the Postman collection authenticates.

## The demo super-admin

The Postman collection authenticates as this user to upsert the menu, activate the restaurant, and run the demo. Customers authenticate as themselves.

| Field | Value |
|---|---|
| Username / email | `demo-admin@vianda.demo` |
| Role type | Internal |
| Role name | Super Admin |
| Password | **Generated per load.** Printed at the end of `scripts/load_demo_data.sh` and written to gitignored `.demo_credentials.local`. |

## The restaurant

| Field | Value |
|---|---|
| Name | Sabores del Pacifico |
| Address | Av. Larco 345, Miraflores, Lima |
| Status | active (after PKDs are added) |
| QR code | one demo QR registered |
| Kitchen days | Mon–Fri, all 4 plates available every day |

## The menu

Four Peruvian plates, each backed by a `product_info` row owned by the demo supplier.

| Plate | Product | Notes |
|---|---|---|
| Ceviche | Ceviche | Classic |
| Lomo Saltado | Lomo Saltado | Classic |
| Ají de Gallina | Ají de Gallina | Classic |
| Causa | Causa | Classic |

Plate names, prices, and images are placeholders. Image URLs use the `mediaBaseUrl` collection variable (default `https://placehold.co`) so they're swappable for real GCS-hosted assets later without restructuring the seed.

## The plan

| Field | Value |
|---|---|
| Name | Estandar (PE) |
| Market | Peru |
| Currency | PEN |
| Canonical key | `DEMO_PLAN_PE_ESTANDAR` |

One plan. All 5 customers subscribe to it.

## The customers

Five customers, all Peruvian, distributed across Lima neighborhoods. Each is meant to evoke a stakeholder-readable persona — but they're all in `active` subscription state right now. Future iterations may give them differentiated states (lapsed, on-hold, employer-benefit) once the demo has tooling for it.

| # | Username | First name | Neighborhood | Address |
|---|---|---|---|---|
| 01 | demo.cliente.pe.01@vianda.demo | Camila | Miraflores | Av. Larco 500 |
| 02 | demo.cliente.pe.02@vianda.demo | (Barranco persona) | Barranco | Av. Grau 120 |
| 03 | demo.cliente.pe.03@vianda.demo | (San Isidro persona) | San Isidro | Av. Javier Prado Este 890 |
| 04 | demo.cliente.pe.04@vianda.demo | (Surco persona) | Surco | Av. Benavides 3400 |
| 05 | demo.cliente.pe.05@vianda.demo | (Jesús María persona) | Jesús María | Av. Cuba 780 |

All 5 share the password `DemoPass1!` (printed in the loader's credentials block — not a secret, just a known dev value).

## The activity

After the loader completes, each of the 5 customers has:

1. **An active subscription** to the Estandar plan, paid via mock-Stripe (`POST /subscriptions/with-payment` + mock confirm-payment). Subscription status = `active`.
2. **One plate selection** for today, on one of the 4 plates. (`POST /plate-selections`)
3. **A kitchen-promotion record** — the supplier ran kitchen-start, materializing the selection into a `plate_pickup_live` row.
4. **A QR scan** at the restaurant — `was_collected = true`. The pickup is in "ready to complete" state.

What is **NOT** populated yet (known gaps as of v1):
- `completion_time` on `plate_pickup_live` — the Complete Order step in the collection runs but doesn't actually mark completion. Pickups stay in "scanned, not yet completed" state.
- `plate_review_info` rows — the review step is gated on having a `plate_pickup_id` from the prior steps; in current runs the variable resolution doesn't propagate, so reviews are silently skipped.
- Restaurant balance / settlement / institution-bill rows — these are produced by the daily settlement pipeline, not by the Postman collection. Run the settlement pipeline manually in dev if you need to demo billing.
- Order history older than today.
- Multiple orders per customer per day (API enforces uniqueness).
- Plate favorites, restaurant favorites — not seeded.

Capture stakeholder feedback that needs more here:

| Date | Stakeholder | Observed gap | Status |
|---|---|---|---|
| _e.g. 2026-05-08_ | _Sales lead_ | _"Can we see the supplier's revenue dashboard?"_ | _follow-up: run settlement pipeline post-load_ |
| | | | |

---

## How the data is loaded

Two layers, run by `scripts/load_demo_data.sh`:

1. **Layer A — `app/db/seed/demo_baseline.sql`** — direct SQL for the supplier institution, demo super-admin, and the two pre-existing addresses. These must exist before the API can authenticate the Postman collection.
2. **Layer B — Newman + `docs/postman/collections/900_DEMO_DAY_SEED.postman_collection.json`** — drives the API as if a real supplier were onboarding: upserts the restaurant, products, plates, plate-kitchen-days, plan; activates the restaurant; signs up 5 customers via the verified-email flow; subscribes each via mock-Stripe; runs each through the order happy path.

Prerequisites:
- `PAYMENT_PROVIDER=mock` in `.env` (and the API restarted so it's loaded).
- API up at `http://localhost:8000`.
- `newman` installed globally.

The demo data is **never** loaded automatically by `build_kitchen_db.sh`. It must be invoked explicitly. Demo files are not hashed into the `kitchen_template` fingerprint.

## How the data is purged

`scripts/purge_demo_data.sh` deletes all demo rows in dependency order (children → parents) inside a single transaction. It matches by:
- UUID prefix `dddddddd-dec0-` for SQL-seeded rows.
- Canonical key `DEMO_*` for entities upserted via Newman.
- Username pattern `demo.cliente.pe.%@vianda.demo` for transactional rows tied to demo customers (which get system-generated UUIDs).

Re-running the loader on a previously-loaded DB will fail (duplicate username). The standard reset is `bash scripts/purge_demo_data.sh && bash scripts/load_demo_data.sh`.

---

## How to evolve this dataset

When a stakeholder demo surfaces a gap:

1. **Capture it in the feedback table above** with a date and stakeholder reference, even if you don't fix it immediately. Future iterations work from this list.
2. **For one-off fixes** (typo in plate name, wrong address): edit the corresponding step in `docs/postman/collections/900_DEMO_DAY_SEED.postman_collection.json`, re-run the loader, verify in the UI.
3. **For new categories of activity** (favorites, reviews, multi-day order history, lapsed subscriptions): decide whether the gap can be filled via the API (preferred — keeps the demo realistic) or requires a SQL bypass. Document the trade-off here before implementing.
4. **For new markets** (AR, US): copy the PE pattern. Each market needs its own institution_entity (currency-bound), restaurant, plates, plan, customers. Don't multiplex AR/US/PE customers under a single institution.
5. **Always update this doc when you change the dataset**, especially the persona table and the "NOT populated yet" list.

## When to retire this dataset

The demo-day dataset stops being useful when:
- Staging exists with realistic data, and stakeholders should see staging instead.
- Production has stakeholder-relevant tenants whose data we can show under NDA.

Until then, this is the canonical "what Vianda looks like in motion" surface.
