# Demo Day Data Plan — v4 (3 markets, cluster + savings + billing + supplier admins)

**Status:** active (v4 — primary supplier admin per market)
**Files in scope:**
- `app/db/seed/demo_baseline.sql` — Layer A SQL seed (institutions, addresses, entities, billing backfill)
- `docs/postman/collections/900_DEMO_DAY_SEED.postman_collection.json` — Layer B API seed
- `scripts/load_demo_data.sh` — loader orchestrator
- `scripts/purge_demo_data.sh` — idempotent teardown

For the durable how-to guide (adding a new market, gotchas, per-market checklist):
see [`docs/internal/demo-day-buildup.md`](../internal/demo-day-buildup.md).

---

## Purpose

Provide a realistic, demo-ready dataset covering three markets (PE / AR / US) for
stakeholder demos. The dataset must:

1. Show a **clustered map** of multiple restaurants per market (5 per market, within 300 m).
2. Show customers in distinguishable **subscription/order states** (active subscriber with
   orders, subscriber without orders, user without subscription).
3. Show plates with **positive, visible savings** (~15–25 % per plate, fleet average ~20 %).
4. Show **two supplier tenants** per market (primary cluster + secondary outlier) for
   multi-tenant admin views.
5. Show **supplier billing rows** per market (pipeline-generated for primary, SQL-seeded for
   secondary).
6. Allow the demo operator to **log in as a per-tenant supplier admin** for both tenants in
   each market.

---

## Markets

| Market | Country | City | Primary cluster street | Credit currency |
|---|---|---|---|---|
| PE | Peru | Lima (Miraflores / San Isidro) | Larco Ave + Dasso | PEN |
| AR | Argentina | Buenos Aires (CABA microcentro) | Lavalle / Florida | ARS |
| US | United States | Seattle (Pike Place / Capitol Hill) | Pike Place Market | USD |

---

## Dataset shape per market

| Dimension | Count |
|---|---|
| Supplier institutions | 2 (primary cluster + secondary outlier) |
| Restaurants | 6 total (5 primary cluster + 1 secondary outlier) |
| Plates | 11 total (10 primary cluster + 1 secondary outlier) |
| Plans | 1 (primary cluster plan, repriced for ~20 % avg savings) |
| Customers | 7 (C01–C07; C06 no-plan, C07 no-orders) |
| Billing rows | ≥ 4 per market (≥ 2 pipeline + 2 SQL backfill) |
| Supplier admins | 2 (SUP01 primary, SUP02 secondary) |

---

## Plan pricing

### Peru (PE)

| Field | Value |
|---|---|
| `price` | S/ 80 PEN |
| `credit` | 20 |
| `credit_cost_per_credit` | 4 PEN |

### Argentina (AR)

| Field | Value |
|---|---|
| `price` | ARS 16,000 |
| `credit` | 20 |
| `credit_cost_per_credit` | 800 ARS |

### United States (US)

| Field | Value |
|---|---|
| `price` | USD 15.00 |
| `credit` | 20 |
| `credit_cost_per_credit` | 0.75 USD |

---

## Savings tables

### Peru (PE) — 4 PEN/credit

| Restaurant | Plate | Price (S/) | Credits | Cost (S/) | Savings % |
|---|---|---|---|---|---|
| Sabores del Pacifico | Ceviche Clasico | 45 | 9 | 36 | **20.0 %** |
| Sabores del Pacifico | Lomo Saltado | 52 | 10 | 40 | **23.1 %** |
| Sabores del Pacifico | Aji de Gallina | 42 | 8 | 32 | **23.8 %** |
| Sabores del Pacifico | Causa Limena | 35 | 7 | 28 | **20.0 %** |
| Doña Lucha Sangucheria | Butifarra | 35 | 7 | 28 | **20.0 %** |
| Doña Lucha Sangucheria | Pan con Chicharrón | 38 | 8 | 32 | **15.8 %** |
| Anticuchería Don Tomás | Anticuchos de Res | 42 | 8 | 32 | **23.8 %** |
| La Esquina del Tiradito | Tiradito de Lenguado | 48 | 9 | 36 | **25.0 %** |
| La Esquina del Tiradito | Pulpo al Olivo | 52 | 10 | 40 | **23.1 %** |
| Pollos a la Brasa Don Lucho | Pollo a la Brasa (cuarto) | 32 | 6 | 24 | **25.0 %** |
| (secondary) La Alpaca Barranco | Lomo Saltado de Alpaca | 48 | 9 | 36 | **25.0 %** |

Fleet average (primary 10): ~21.9 %

### Argentina (AR) — 800 ARS/credit

| Restaurant | Plate | Price (ARS) | Credits | Cost (ARS) | Savings % |
|---|---|---|---|---|---|
| Parrilla La Lavalle | Milanesa a la Napolitana | 22,000 | 23 | 18,400 | **16.4 %** |
| Parrilla La Lavalle | Asado de Tira con Chimichurri | 26,000 | 27 | 21,600 | **16.9 %** |
| Pizzeria Don Vicente | Pizza Mozzarella | 18,000 | 19 | 15,200 | **15.6 %** |
| Pizzeria Don Vicente | Fugazzeta Rellena | 21,000 | 22 | 17,600 | **16.2 %** |
| Cafe del Centro | Choripan con Chimichurri | 15,000 | 16 | 12,800 | **14.7 %** |
| Cafe del Centro | Provoleta con Oregano | 17,000 | 18 | 14,400 | **15.3 %** |
| Bodegon San Martin | Empanadas (6 unidades) | 19,000 | 20 | 16,000 | **15.8 %** |
| Bodegon San Martin | Noquis del 29 con Tuco | 20,000 | 21 | 16,800 | **16.0 %** |
| Empanadas de Florida | Bondiola Braseada | 23,000 | 24 | 19,200 | **16.5 %** |
| Empanadas de Florida | Lomo de Cerdo a la Criolla | 24,000 | 25 | 20,000 | **16.7 %** |

Fleet average (primary 10): ~16.0 %

### United States (US) — 0.75 USD/credit

| Restaurant | Plate | Price (USD) | Credits | Cost (USD) | Savings % |
|---|---|---|---|---|---|
| Pike Place Chowder | Clam Chowder | 14.00 | 15 | 11.25 | **19.6 %** |
| Pike Place Chowder | Fish and Chips | 16.00 | 17 | 12.75 | **20.3 %** |
| Beecher's Deli | Flagship Mac and Cheese | 13.00 | 14 | 10.50 | **19.2 %** |
| Beecher's Deli | Grilled Cheese on Sourdough | 12.00 | 13 | 9.75 | **18.8 %** |
| Post Alley Pizza | Margherita Pizza Slice | 11.00 | 12 | 9.00 | **18.2 %** |
| Post Alley Pizza | Pepperoni Pizza Slice | 12.00 | 13 | 9.75 | **18.8 %** |
| Market Street Poke | Salmon Poke Bowl | 17.00 | 18 | 13.50 | **20.6 %** |
| Market Street Poke | Ahi Tuna Poke Bowl | 16.00 | 17 | 12.75 | **20.3 %** |
| Stewart Street Diner | Northwest Clam Bake Plate | 18.00 | 19 | 14.25 | **20.8 %** |
| Stewart Street Diner | Turkey Club Sandwich | 14.00 | 15 | 11.25 | **19.6 %** |

Fleet average (primary 10): ~19.6 %

---

## Customer table (21 rows)

| Code | Email | Neighborhood | Subscription | Orders | Demo role |
|---|---|---|---|---|---|
| PE C01 | `demo.cliente.pe.01@vianda.demo` | Miraflores | yes | 5 | Active subscriber with history |
| PE C02 | `demo.cliente.pe.02@vianda.demo` | Barranco | yes | 5 | Active subscriber with history |
| PE C03 | `demo.cliente.pe.03@vianda.demo` | San Isidro | yes | 5 | Active subscriber with history |
| PE C04 | `demo.cliente.pe.04@vianda.demo` | Surco | yes | 5 | Active subscriber with history |
| PE C05 | `demo.cliente.pe.05@vianda.demo` | Jesus Maria | yes | 5 | Active subscriber with history |
| PE C06 | `demo.cliente.pe.06.no_plan@vianda.demo` | (any) | **none** | 0 | Show subscription purchase flow |
| PE C07 | `demo.cliente.pe.07.no_orders@vianda.demo` | (any) | yes | **0** | Show first-order flow |
| AR C01 | `demo.cliente.ar.01@vianda.demo` | Recoleta | yes | 5 | Active subscriber with history |
| AR C02 | `demo.cliente.ar.02@vianda.demo` | Palermo | yes | 5 | Active subscriber with history |
| AR C03 | `demo.cliente.ar.03@vianda.demo` | Belgrano | yes | 5 | Active subscriber with history |
| AR C04 | `demo.cliente.ar.04@vianda.demo` | San Telmo | yes | 5 | Active subscriber with history |
| AR C05 | `demo.cliente.ar.05@vianda.demo` | Caballito | yes | 5 | Active subscriber with history |
| AR C06 | `demo.cliente.ar.06.no_plan@vianda.demo` | (any) | **none** | 0 | Show subscription purchase flow |
| AR C07 | `demo.cliente.ar.07.no_orders@vianda.demo` | (any) | yes | **0** | Show first-order flow |
| US C01 | `demo.cliente.us.01@vianda.demo` | Capitol Hill | yes | 5 | Active subscriber with history |
| US C02 | `demo.cliente.us.02@vianda.demo` | Ballard | yes | 5 | Active subscriber with history |
| US C03 | `demo.cliente.us.03@vianda.demo` | Fremont | yes | 5 | Active subscriber with history |
| US C04 | `demo.cliente.us.04@vianda.demo` | Wallingford | yes | 5 | Active subscriber with history |
| US C05 | `demo.cliente.us.05@vianda.demo` | West Seattle | yes | 5 | Active subscriber with history |
| US C06 | `demo.cliente.us.06.no_plan@vianda.demo` | (any) | **none** | 0 | Show subscription purchase flow |
| US C07 | `demo.cliente.us.07.no_orders@vianda.demo` | (any) | yes | **0** | Show first-order flow |

Shared password for all customers: `DemoPass1!`

---

## Supplier credentials

| Key | Email | Password | Role | Institution |
|---|---|---|---|---|
| Super Admin | `demo-admin@vianda.market` | (generated at load time) | Internal Super Admin | — |
| SUP01_PE | `demo.proveedor.pe.01.admin@vianda.demo` | `DemoPass1!` | Supplier Admin | Vianda Demo Supplier (PE) |
| SUP02_PE | `demo.proveedor.pe.02.admin@vianda.demo` | `DemoPass1!` | Supplier Admin | Cocina Andina S.A.C. |
| SUP01_AR | `demo.proveedor.ar.01.admin@vianda.demo` | `DemoPass1!` | Supplier Admin | Vianda Demo Supplier (AR) |
| SUP02_AR | `demo.proveedor.ar.02.admin@vianda.demo` | `DemoPass1!` | Supplier Admin | Cocina de Recoleta S.R.L. |
| SUP01_US | `demo.proveedor.us.01.admin@vianda.demo` | `DemoPass1!` | Supplier Admin | Vianda Demo Supplier (US) |
| SUP02_US | `demo.proveedor.us.02.admin@vianda.demo` | `DemoPass1!` | Supplier Admin | Capitol Hill Kitchen LLC |

All SUP01/SUP02 users are scoped to `market_id` for their respective market.
SUP01 users are scoped to `demoInstitutionId` (`dddddddd-dec0-0001-0000-000000000001`).
SUP02 users are scoped to the secondary institution for their market (dec0-0002 sub-range).

---

## UUID scheme

All demo UUIDs share the prefix `dddddddd-dec0-NNNN-XXXX-YYYYYYYYYYYY`.

| Sub-range | Entities |
|---|---|
| `0001-0000-000000000001` | Primary demo supplier institution (shared PE/AR/US) |
| `0001-0000-000000000002` | Demo super-admin user |
| `0001-0000-000000000003` | PE institution entity (primary supplier) |
| `0001-0000-000000000004` | AR institution entity (primary supplier) |
| `0001-0000-000000000005` | US institution entity (primary supplier) |
| `0002-0000-000000000001` | PE secondary institution (Cocina Andina S.A.C.) |
| `0002-0000-000000000002` | AR secondary institution (Cocina de Recoleta S.R.L.) |
| `0002-0000-000000000003` | US secondary institution (Capitol Hill Kitchen LLC) |
| `0002-0000-000000000004–6` | PE/AR/US secondary institution entities |
| `0010-0000-00000000000N` | PE primary addresses (N=1 office, 2–6 restaurants) |
| `0011-0000-00000000000N` | PE secondary addresses |
| `0020-0000-00000000000N` | AR primary addresses |
| `0021-0000-00000000000N` | AR secondary addresses |
| `0030-0000-00000000000N` | US primary addresses |
| `0031-0000-00000000000N` | US secondary addresses |
| `0050-0000-00000000000N` | SQL-seeded institution_bill_info for secondary suppliers |

Canonical key prefix for all Postman-seeded entities: `DEMO_*`

---

## Folder structure (collection 900)

| Folder | Contents |
|---|---|
| `00 Setup` | Login as demo-admin@vianda.market |
| `10 Supplier menu (PE)` | 5 restaurants, 5 QR codes, 10 products, 10 plates, 50 PKDs, 1 plan |
| `12 Secondary supplier (PE)` | Institution + entity + **SUP01_PE primary admin** + SUP02_PE secondary admin + outlier restaurant + plate + PKDs + activate |
| `20 Customers (PE)` | Signup + verify + login + address for C01–C07 |
| `30 Subscribe each customer` | Subscribe C01–C05 + C07; C06 intentionally skipped |
| `40 Order history loop` | 5 orders each for C01–C05 |
| `45 Supplier billing (PE)` | POST run-settlement-pipeline?country_code=PE |
| `10 Supplier menu (AR)` | 5 restaurants, QR codes, products, plates, PKDs, 1 plan |
| `12 Secondary supplier (AR)` | Institution + entity + **SUP01_AR primary admin** + SUP02_AR secondary admin + outlier restaurant + plate + PKDs + activate |
| `20 Customers (AR)` | Signup + verify + login + address for C01–C07 |
| `30 Subscribe each customer (AR)` | Subscribe C01–C05 + C07 |
| `40 Order history (AR)` | 5 orders each for C01–C05 |
| `45 Supplier billing (AR)` | POST run-settlement-pipeline?country_code=AR |
| `10 Supplier menu (US)` | 5 restaurants, QR codes, products, plates, PKDs, 1 plan |
| `12 Secondary supplier (US)` | Institution + entity + **SUP01_US primary admin** + SUP02_US secondary admin + outlier restaurant + plate + PKDs + activate |
| `20 Customers (US)` | Signup + verify + login + address for C01–C07 |
| `30 Subscribe each customer (US)` | Subscribe C01–C05 + C07 |
| `40 Order history (US)` | 5 orders each for C01–C05 |
| `45 Supplier billing (US)` | POST run-settlement-pipeline?country_code=US |
| `99 Sanity checks` | Assertions for all markets + primary admin existence checks |

---

## Sanity check assertions (folder 99)

Per market (PE / AR / US):
1. Exactly 5 primary demo restaurants exist.
2. All demo plates in `by-city` response have `savings` between 15 and 30 (none are 0).
3. Demo plan exists with correct `price` and `credit=20`.
4. Exactly 7 demo customers exist.
5. Exactly 10 demo plates exist (primary cluster).
6. 6 active subscriptions (C01–C05 + C07; C06 excluded) — PE only.
7. At least 25 completed orders — PE only.
8. C06 has 0 subscriptions.
9. C07 has ≥ 1 active subscription (no orders in folder 40) — PE only.
10. Exactly 2 demo supplier institutions visible for the market.
11. Secondary outlier restaurant visible in `by-city` (using customer token).
12. Billing rows exist (≥ 2 pipeline + 2 SQL backfill).
13. **Primary supplier admin user exists and is scoped to primary institution.** (new in v4)

---

## Purge safety

`scripts/purge_demo_data.sh` catches all demo data via three filters:
- UUID prefix `dddddddd-dec0-` (SQL-seeded rows)
- Username `LIKE 'demo.cliente.<cc>.%@vianda.demo'` for PE, AR, US
- Username `LIKE 'demo.proveedor.%@vianda.demo'` (all SUP01 + SUP02 for all markets)
- Canonical key `LIKE 'DEMO_%'` (Postman-seeded rows)

The `demo.proveedor.%@vianda.demo` wildcard covers both the `.01.admin` (primary, added in v4)
and `.02.admin` (secondary) patterns without any change to the purge script.

---

## Dataset Decisions

| Date | Decision |
|---|---|
| 2026-04-10 | v1: PE-only dataset, 1 restaurant, 4 plates, 5 customers. |
| 2026-04-20 | v2: Plan repriced from S/ 150 / 7.5 PEN to S/ 80 / 4 PEN to achieve positive savings. |
| 2026-04-28 | v3: Cluster expanded to 5 PE restaurants (San Isidro tight cluster). C06/C07 demo roles added. |
| 2026-05-07 | v4 step 1: AR market added (Buenos Aires / Lavalle cluster). Same 7-customer + billing shape. |
| 2026-05-07 | v4 step 2: US market added (Seattle / Pike Place cluster). Same shape. |
| 2026-05-08 | v4 step 3: Secondary supplier per market added (Cocina Andina PE, Cocina de Recoleta AR, Capitol Hill Kitchen US). Outlier restaurant + 1 plate + SQL-seeded billing backfill. |
| 2026-05-08 | v4 step 4: Supplier billing rows added via `45 Supplier billing (<CC>)` folders (settlement pipeline) + SQL backfill for secondary supplier entities. |
| 2026-05-08 | v4 step 5: Primary supplier admin user per market added (SUP01_PE/AR/US, scoped to `demoInstitutionId`). Enables demo operator to log in as primary tenant admin. |

---

## Implementation Checklist

- [x] `demo_baseline.sql` — PE institution, addresses (R1–R5), entity, super-admin user
- [x] Plan repriced: 20 credits / S/ 80 (credit cost = 4 PEN)
- [x] PE cluster: 5 restaurants + 10 plates + 50 PKDs
- [x] C06 and C07 demo roles (no-plan, no-orders)
- [x] Folder 99: PE assertions (restaurants, savings, 7 customers, 6 subs, C06/C07 state checks)
- [x] AR market: `demo_baseline.sql` addresses + entity + institution_market binding
- [x] AR collection folders: 10/12/20/30/40/45 + folder 99 assertions
- [x] US market: `demo_baseline.sql` addresses + entity + institution_market binding
- [x] US collection folders: 10/12/20/30/40/45 + folder 99 assertions
- [x] Secondary supplier institutions + entities pre-seeded in `demo_baseline.sql` (dec0-0002 sub-range)
- [x] Folder `12 Secondary supplier (<CC>)` per market: institution + entity + admin + restaurant + plate + PKDs + activate
- [x] SQL billing backfill for secondary supplier entities (dec0-0050 sub-range)
- [x] Folder `45 Supplier billing (<CC>)` per market: settlement pipeline call
- [x] `load_demo_data.sh` — SUP02_<CC> credentials in both early-write and final-write blocks
- [x] `purge_demo_data.sh` — `demo.proveedor.%@vianda.demo` LIKE pattern covers all supplier admins
- [x] **Primary supplier admin per market (v4 step 5):** SUP01_PE/AR/US upserted via `PUT /users/by-key` in folder 12, scoped to `demoInstitutionId`
- [x] **Folder 99 extended:** 3 new assertions for primary admin existence per market
- [x] **`load_demo_data.sh` credentials block:** SUP01_<CC> added under "Primary supplier:" subheader in both blocks
