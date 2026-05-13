# Demo-Day Dataset — What's In It, What It Shows

**Audience:** anyone presenting Vianda to stakeholders against the dev environment.
**Companion docs:**
- `DATABASE_REBUILD_PERSISTENCE.md` — how to load / purge / reset the dev DB.
- `docs/internal/demo-day-buildup.md` — guide for adding a new market to the dataset.

**Rollout doc (ephemeral):** `docs/plans/demo_day_data.md` tracks the in-flight rollout state and is
archived once stable. The document you are reading is the permanent reference.

This is a **living reference**. Update it whenever the dataset shape changes — new
markets, repriced plans, new credential blocks, new known workarounds.

---

## 1. Scope — v5 (three markets, employer flow)

The demo-day dataset is a **moment-in-time snapshot** of what a healthy Vianda
deployment looks like with real activity. It covers three markets (PE / AR / US),
two supplier institutions per market (1 primary 5-restaurant cluster + 1 secondary
outlier), and one employer institution per market with 3 benefit-enrolled employees.

**Per market at a glance:**

- 1 primary supplier institution (shared legal entity with 3 currency-bound entities)
- 5 cluster restaurants (primary) + 1 outlier restaurant (secondary)
- 11 viandas per market (10 primary + 1 secondary), each available Mon–Fri
- 1 subscription plan
- 7 customers: C01–C05 with active subscriptions and order history; C06 = no plan;
  C07 = plan but no orders
- 4 employer users: 1 employer admin + 3 enrolled employees with employer-sponsored
  subscriptions
- 2 supplier admin users per market (SUP01 is the primary supplier admin seeded via
  `demo_baseline.sql`; SUP02 is the secondary institution's admin)
- ~one week of order activity for C01–C05 per market (5 pickups each)
- Pre-seeded billing rows for the secondary suppliers (no pipeline orders)
- Pipeline-generated billing rows for the primary supplier (produced by folder 45)

**What it is not:** historical backfill, load-test scale, or a representative
production sample. No trend charts. No multi-week retention curves.

---

## 2. Markets

| Market | Currency | Plan price | Credit cost | Primary cluster street | Secondary outlier | Employer institution |
|---|---|---|---|---|---|---|
| PE | PEN (S/) | S/ 80 | S/ 4 / credit | Calle Miguel Dasso, San Isidro, Lima | Barranco | Empresa Demo Lima SAC |
| AR | ARS ($) | $ 16,000 | $ 800 / credit | Calle Lavalle, Microcentro, CABA | Recoleta | Demo Argentina S.A. |
| US | USD ($) | $15.00 | $0.75 / credit | Pike Place Market, Seattle | Capitol Hill | Demo Seattle Inc. |

**Primary supplier institution** (shared across all markets): `Vianda Demo Supplier`
(`DEMO_INSTITUTION_PE_VIANDA_DEMO`). It has three currency-bound legal entities:

| Entity name | Market | Currency | Address |
|---|---|---|---|
| Vianda Demo Peru SAC | PE | PEN | Av. Javier Prado Este 3580, San Isidro, Lima |
| Vianda Demo Argentina SRL | AR | ARS | Florida 455, Microcentro, CABA |
| Vianda Demo US LLC | US | USD | 2nd Ave 800, Downtown Seattle |

---

## 3. Restaurants and menu

### PE — primary cluster (San Isidro, Lima)

All 5 cluster restaurants are within ~300 m of Calle Miguel Dasso, San Isidro.

| # | Restaurant | Address | Viandas | price (S/) | credits | savings |
|---|---|---|---|---|---|---|
| R1 | Sabores del Pacifico | Av. Larco 345, Miraflores | Ceviche Clasico | 45 | 9 | 20% |
| R1 | Sabores del Pacifico | | Lomo Saltado | 52 | 10 | 23% |
| R1 | Sabores del Pacifico | | Aji de Gallina | 42 | 8 | 24% |
| R1 | Sabores del Pacifico | | Causa Limena | 35 | 7 | 20% |
| R2 | Dona Lucha Sangucheria | Miguel Dasso 137 | Butifarra | 35 | 7 | 20% |
| R2 | Dona Lucha Sangucheria | | Pan con Chicharron | 38 | 8 | 16% |
| R3 | Anticucheria Don Tomas | Coronel Andres Reyes 218 | Anticuchos de Res | 42 | 8 | 24% |
| R4 | La Esquina del Tiradito | Manuel Banon 295 | Tiradito de Lenguado | 48 | 9 | 25% |
| R4 | La Esquina del Tiradito | | Pulpo al Olivo | 52 | 10 | 23% |
| R5 | Pollos a la Brasa Don Lucho | Conquistadores 510 | Pollo a la Brasa (cuarto) | 32 | 6 | 25% |

PE secondary (Barranco outlier):

| Restaurant | Address | Vianda | price (S/) | credits | savings |
|---|---|---|---|---|---|
| La Alpaca Barranco | Pedro de Osma 150, Barranco | Lomo Saltado de Alpaca | 44 | 9 | 18% |

### AR — primary cluster (Microcentro, CABA)

All 5 cluster restaurants are within ~300 m of Calle Lavalle, Microcentro.

| # | Restaurant | Address | Viandas | price (ARS) | credits | savings |
|---|---|---|---|---|---|---|
| R1 | Parrilla La Lavalle | Lavalle 402 | Milanesa a la Napolitana | 20,000 | 20 | 20% |
| R1 | Parrilla La Lavalle | | Asado de Tira con Chimichurri | 23,000 | 22 | 23% |
| R2 | Pizzeria Don Vicente | Reconquista 380 | Pizza Mozzarella | 18,000 | 18 | 20% |
| R2 | Pizzeria Don Vicente | | Fugazzeta Rellena | 21,000 | 20 | 24% |
| R3 | Cafe del Centro | Florida 355 | Choripan con Chimichurri | 16,000 | 16 | 20% |
| R3 | Cafe del Centro | | Provoleta con Oregano | 18,500 | 18 | 22% |
| R4 | Bodegon San Martin | San Martin 280 | Empanadas (6 unidades) | 15,000 | 15 | 20% |
| R4 | Bodegon San Martin | | Noquis del 29 con Tuco | 17,000 | 17 | 20% |
| R5 | Empanadas de Florida | 25 de Mayo 489 | Bondiola Braseada | 21,000 | 21 | 20% |
| R5 | Empanadas de Florida | | Lomo de Cerdo a la Criolla | 19,000 | 19 | 20% |

AR secondary (Recoleta outlier):

| Restaurant | Address | Vianda | price (ARS) | credits | savings |
|---|---|---|---|---|---|
| El Clasico de Recoleta | Av. Santa Fe 2450, Recoleta | Noquis de Papa al Estofado | 21,000 | 21 | 20% |

### US — primary cluster (Pike Place Market, Seattle)

All 5 cluster restaurants are within ~300 m of Pike Place Market.

| # | Restaurant | Address | Viandas | price (USD) | credits | savings |
|---|---|---|---|---|---|---|
| R1 | Pike Place Chowder | Pike Pl 1428 | Clam Chowder | $13 | 14 | 19% |
| R1 | Pike Place Chowder | | Fish and Chips | $15 | 16 | 20% |
| R2 | Beecher's Deli | Pike Pl 1916 | Flagship Mac and Cheese | $12 | 13 | 19% |
| R2 | Beecher's Deli | | Grilled Cheese on Sourdough | $14 | 15 | 20% |
| R3 | Post Alley Pizza | 1st Ave 94 | Margherita Pizza Slice | $13 | 14 | 19% |
| R3 | Post Alley Pizza | | Pepperoni Pizza Slice | $14 | 15 | 20% |
| R4 | Market Street Poke | Pike Pl 1500 | Salmon Poke Bowl | $16 | 17 | 20% |
| R4 | Market Street Poke | | Ahi Tuna Poke Bowl | $15 | 16 | 20% |
| R5 | Stewart Street Diner | Western Ave 2000 | Northwest Clam Bake Vianda | $18 | 19 | 21% |
| R5 | Stewart Street Diner | | Turkey Club Sandwich | $12 | 13 | 19% |

US secondary (Capitol Hill outlier):

| Restaurant | Address | Vianda | price (USD) | credits | savings |
|---|---|---|---|---|---|
| Summit Bowl Capitol Hill | E Pike St 500, Capitol Hill | Grains and Greens Bowl | $15 | 16 | 20% |

**Note on `acknowledge_spread_compression`:** The US plan sets this flag to `true`
on the plan upsert. This is an audit-logged toggle in `app/services/credit_spread.py`
that fires when the supplier spread compresses below the configured floor. Demo plans
are deliberately priced thin so customers see ~19–21% savings without overpaying
suppliers; the flag acknowledges the compression with an audit record. It does not
indicate negative savings — US savings are positive ~19–21% across all viandas
(plan price $15 / 20 credits = $0.75 per credit; a 14-credit vianda costs $10.50 in
plan value vs. $13 retail = 19.2% savings).

---

## 4. Plans and savings math

The savings percentage displayed in the app is computed by
`app/services/restaurant_explorer_service.py:_compute_savings_pct`:

```
savings_pct = round((price - credit * credit_cost_per_credit) / price * 100)
```

where `credit_cost_per_credit = plan.price / plan.credit`.

Per-market plan numbers:

| Market | Plan canonical key | Plan price | Credits | Credit cost | ~savings range |
|---|---|---|---|---|---|
| PE | `DEMO_PLAN_PE_ESTANDAR` | S/ 80 | 20 | S/ 4 | 16–25% |
| AR | `DEMO_PLAN_AR_ESTANDAR` | ARS 16,000 | 20 | ARS 800 | 20–24% |
| US | `DEMO_PLAN_US_STANDARD` | USD 15.00 | 20 | USD 0.75 | 19–21% |

All three plans are set to `highlighted: true` and `status: active`.

---

## 5. Customers — full credentials catalog

All customer passwords: `DemoPass1!`

### PE customers

| ID | Email | Neighborhood | Role | Password |
|---|---|---|---|---|
| C01 | `demo.cliente.pe.01@vianda.demo` | Miraflores | Active subscriber with order history | `DemoPass1!` |
| C02 | `demo.cliente.pe.02@vianda.demo` | Barranco | Active subscriber with order history | `DemoPass1!` |
| C03 | `demo.cliente.pe.03@vianda.demo` | San Isidro | Active subscriber with order history | `DemoPass1!` |
| C04 | `demo.cliente.pe.04@vianda.demo` | Surco | Active subscriber with order history | `DemoPass1!` |
| C05 | `demo.cliente.pe.05@vianda.demo` | Jesus Maria | Active subscriber with order history | `DemoPass1!` |
| C06 | `demo.cliente.pe.06.no_plan@vianda.demo` | (Lima) | No plan — show subscription purchase flow | `DemoPass1!` |
| C07 | `demo.cliente.pe.07.no_orders@vianda.demo` | (Lima) | Subscribed but no orders — show first-order flow | `DemoPass1!` |

### AR customers

| ID | Email | Neighborhood | Role | Password |
|---|---|---|---|---|
| C01 | `demo.cliente.ar.01@vianda.demo` | Recoleta | Active subscriber with order history | `DemoPass1!` |
| C02 | `demo.cliente.ar.02@vianda.demo` | Palermo | Active subscriber with order history | `DemoPass1!` |
| C03 | `demo.cliente.ar.03@vianda.demo` | Belgrano | Active subscriber with order history | `DemoPass1!` |
| C04 | `demo.cliente.ar.04@vianda.demo` | San Telmo | Active subscriber with order history | `DemoPass1!` |
| C05 | `demo.cliente.ar.05@vianda.demo` | Caballito | Active subscriber with order history | `DemoPass1!` |
| C06 | `demo.cliente.ar.06.no_plan@vianda.demo` | (CABA) | No plan — show subscription purchase flow | `DemoPass1!` |
| C07 | `demo.cliente.ar.07.no_orders@vianda.demo` | (CABA) | Subscribed but no orders — show first-order flow | `DemoPass1!` |

### US customers

| ID | Email | Neighborhood | Role | Password |
|---|---|---|---|---|
| C01 | `demo.cliente.us.01@vianda.demo` | Capitol Hill | Active subscriber with order history | `DemoPass1!` |
| C02 | `demo.cliente.us.02@vianda.demo` | Ballard | Active subscriber with order history | `DemoPass1!` |
| C03 | `demo.cliente.us.03@vianda.demo` | Fremont | Active subscriber with order history | `DemoPass1!` |
| C04 | `demo.cliente.us.04@vianda.demo` | Wallingford | Active subscriber with order history | `DemoPass1!` |
| C05 | `demo.cliente.us.05@vianda.demo` | West Seattle | Active subscriber with order history | `DemoPass1!` |
| C06 | `demo.cliente.us.06.no_plan@vianda.demo` | (Seattle) | No plan — show subscription purchase flow | `DemoPass1!` |
| C07 | `demo.cliente.us.07.no_orders@vianda.demo` | (Seattle) | Subscribed but no orders — show first-order flow | `DemoPass1!` |

---

## 6. Supplier credentials

### Super-admin (all markets)

| Field | Value |
|---|---|
| Email | `demo-admin@vianda.market` |
| Password | **Generated per load.** Printed at the end of `scripts/load_demo_data.sh` and written to `.demo_credentials.local` (gitignored). |
| Role | Internal / Super Admin |

`demo-admin@vianda.market` is a real Gmail alias that forwards to the admin inbox.
This makes the password-recovery flow demoable live. Do not confuse it with the
built-in `superadmin` user seeded by `reference_data.sql` (password `SuperAdmin1`),
which is the canonical internal super-admin and should not be shared during demos.

### Supplier admins — all markets

| Market | Role | Email | Password | Scope |
|---|---|---|---|---|
| PE | SUP01 (primary) | `demo.proveedor.pe.01.admin@vianda.demo` | `DemoPass1!` | Vianda Demo Supplier (Sabores del Pacifico cluster, Miraflores) |
| PE | SUP02 (secondary) | `demo.proveedor.pe.02.admin@vianda.demo` | `DemoPass1!` | Cocina Andina S.A.C. (Barranco outlier) |
| AR | SUP01 (primary) | `demo.proveedor.ar.01.admin@vianda.demo` | `DemoPass1!` | Vianda Demo Supplier (Parrilla La Lavalle cluster, Microcentro) |
| AR | SUP02 (secondary) | `demo.proveedor.ar.02.admin@vianda.demo` | `DemoPass1!` | Cocina de Recoleta S.R.L. (Recoleta outlier) |
| US | SUP01 (primary) | `demo.proveedor.us.01.admin@vianda.demo` | `DemoPass1!` | Vianda Demo Supplier (Pike Place Chowder cluster, Seattle) |
| US | SUP02 (secondary) | `demo.proveedor.us.02.admin@vianda.demo` | `DemoPass1!` | Capitol Hill Kitchen LLC (Capitol Hill outlier) |

All SUP01 accounts are scoped to the primary supplier institution
`dddddddd-dec0-0001-0000-000000000001` (Vianda Demo Supplier). SUP02 accounts are
scoped to the respective secondary institution in each market.

---

## 7. Employer credentials

All employer passwords: `DemoPass1!`

### PE employer

Institution: **Empresa Demo Lima SAC** (`DEMO_INSTITUTION_PE_EMPLOYER`)

| ID | Email | Role | Password |
|---|---|---|---|
| EM01 | `demo.empresa.pe.admin@vianda.demo` | Employer Admin | `DemoPass1!` |
| EE01 | `demo.empleado.pe.01@vianda.demo` | Enrolled employee | `DemoPass1!` |
| EE02 | `demo.empleado.pe.02@vianda.demo` | Enrolled employee | `DemoPass1!` |
| EE03 | `demo.empleado.pe.03@vianda.demo` | Enrolled employee | `DemoPass1!` |

### AR employer

Institution: **Demo Argentina S.A.** (`DEMO_INSTITUTION_AR_EMPLOYER`)

| ID | Email | Role | Password |
|---|---|---|---|
| EM01 | `demo.empresa.ar.admin@vianda.demo` | Employer Admin | `DemoPass1!` |
| EE01 | `demo.empleado.ar.01@vianda.demo` | Enrolled employee | `DemoPass1!` |
| EE02 | `demo.empleado.ar.02@vianda.demo` | Enrolled employee | `DemoPass1!` |
| EE03 | `demo.empleado.ar.03@vianda.demo` | Enrolled employee | `DemoPass1!` |

### US employer

Institution: **Demo Seattle Inc.** (`DEMO_INSTITUTION_US_EMPLOYER`)

| ID | Email | Role | Password |
|---|---|---|---|
| EM01 | `demo.empresa.us.admin@vianda.demo` | Employer Admin | `DemoPass1!` |
| EE01 | `demo.empleado.us.01@vianda.demo` | Enrolled employee | `DemoPass1!` |
| EE02 | `demo.empleado.us.02@vianda.demo` | Enrolled employee | `DemoPass1!` |
| EE03 | `demo.empleado.us.03@vianda.demo` | Enrolled employee | `DemoPass1!` |

Each employer has one benefits program with `benefit_rate = 100` (fully subsidized).
Employee subscriptions are upserted via `PUT /employer/employee-link/by-key`.

---

## 8. Billing rows

### Primary supplier (pipeline-generated)

After folder 45 (`Run settlement pipeline`) completes, the primary supplier institution
gets billing rows for each market produced by the settlement pipeline from the 5-order
history of C01–C05. These are live-computed rows in `billing.institution_bill_info`.

### Secondary suppliers (pre-seeded)

Two `institution_bill_info` rows are pre-seeded per market secondary supplier
in `demo_baseline.sql` (sub-range `dddddddd-dec0-0050-...`):

| Market | Institution | Row 1 | Row 2 |
|---|---|---|---|
| PE | Cocina Andina S.A.C. | `pending` — Apr 2026, 8 txns, S/ 352 | `paid` — Mar 2026, 12 txns, S/ 528 |
| AR | Cocina de Recoleta S.R.L. | `pending` — Apr 2026, 6 txns, ARS 126,000 | `paid` — Mar 2026, 9 txns, ARS 189,000 |
| US | Capitol Hill Kitchen LLC | `pending` — Apr 2026, 7 txns, $105 | `paid` — Mar 2026, 11 txns, $165 |

These rows exist so the vianda-platform Billing / Invoices / Payouts pages render
for institutions that have no live order flow in the demo.

---

## 9. What this enables in the apps

| Scenario | vianda-app (B2C) | vianda-platform (B2B) |
|---|---|---|
| Explore / map | Multi-restaurant cluster (5 pins + 1 outlier per market). Positive savings on PE and AR viandas. | — |
| Subscription purchase | C06 (no plan): shows the full subscription purchase flow. | Subscription appears on supplier dashboard. |
| First order | C07 (subscribed, no orders): shows vianda-selection flow for a subscriber who has never ordered. | — |
| Active order history | C01–C05: have completed pickups and vianda reviews. | Dashboard order counts, revenue, activity feed. |
| Multi-tenant supplier | Two institutions per market visible in the restaurant explorer (primary cluster + outlier). | Separate institution rows, billing, entity admin. |
| Employer program | — | Employer admin sees enrolled employees, active benefit program. Employee accounts show employer-sponsored subscriptions. |
| Billing / payouts | — | Primary supplier: pipeline-computed bills. Secondary supplier: pre-seeded pending + paid rows. |

---

## 10. Load / refresh — local

With the kitchen API running locally (`bash scripts/run_dev_quiet.sh` in another terminal):

```bash
cd ~/learn/vianda/kitchen
PAYMENT_PROVIDER=mock bash scripts/load_demo_data.sh
```

Refresh anytime — purge + reload is idempotent:

```bash
bash scripts/purge_demo_data.sh && PAYMENT_PROVIDER=mock bash scripts/load_demo_data.sh
```

Credentials are printed at the end of the loader and persisted to gitignored `.demo_credentials.local`.

### Where to look once the API is running

`http://localhost:8000/` returns the API's health JSON — that's the health endpoint, not a UI. To see actual content:

- Swagger UI: `http://localhost:8000/docs`
- Direct API hit: `http://localhost:8000/api/v1/restaurants/by-city?city=Lima` (after auth)
- Live frontends: start vianda-app or vianda-platform locally — they read `localhost:8000` in dev mode.

### Logs that look scary but aren't

- `RequestsDependencyWarning: urllib3 ... doesn't match a supported version!` — cosmetic Homebrew Python version-pin warning.
- `GET /favicon.ico HTTP/1.1 404` — your browser asks for a favicon; we don't ship one.

## 10b. Load / refresh — gcp-dev

Deploys ship code + migrations only. Demo data is opt-in and must be loaded against dev separately. The GCP loader wraps the bastion tunnel for the private-IP Cloud SQL.

```bash
cd ~/learn/vianda/kitchen
bash scripts/purge_demo_data.sh --target=gcp-dev    # wipe stale demo data first
bash scripts/load_demo_data_gcp.sh                  # tunnels through bastion, runs Layer A SQL + Newman
```

If credentials don't work after a deploy: the deploy ran migrations but the loader hasn't been re-run since. Run the purge + reload pair above.

See `~/learn/vianda/docs/commands/local_commands.md` and `~/learn/vianda/docs/commands/gcp_commands.md` for the orchestrator-root command catalog (same content, different surface).

For DB rebuild procedures, worktree clone patterns, and migration sequence, see
`DATABASE_REBUILD_PERSISTENCE.md`. Demo data is never loaded automatically by
`build_kitchen_db.sh` — it must be invoked explicitly.

---

## 11. Known workarounds

**Folder 40 pins `target_kitchen_day` to dodge kitchen#257.** AR and US vianda
selection requests in folder 40 include `"target_kitchen_day": "wednesday"` (AR) or
`"target_kitchen_day": "monday"` (US). This bypasses the auto-selection logic in
`vianda_selection_validation._find_next_available_kitchen_day_in_week`, which skips
national holidays and, in `DEV_MODE`, maps Saturdays to `"friday"`. Pinning an
explicit mid-week day makes the order history loop day-of-week agnostic. PE folder 40
does not pin `target_kitchen_day` — it runs against the current date and works on any
weekday. If you need to reload on a weekend, run the PE loader on a weekday or add the
same pin.

---

## 12. What changes when

This document is the durable reference for the demo-day dataset. It is updated every
time the dataset shape changes: new markets, repriced plans, new users, changed
institution names, or new known workarounds.

`docs/plans/demo_day_data.md` is the in-flight rollout tracker. It holds the
implementation checklist, the UUID scheme table, and decisions made during a major
revision. Once a major revision ships and stabilises, the plan doc is archived and
this document is the only active reference.

Do not reference an archived plan to understand the current dataset shape — use this
document. If something is missing here that should be here, add it now.
