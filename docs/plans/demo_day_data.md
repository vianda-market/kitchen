# Demo Day Data Plan — PE Seed (v3)

**Status:** active (v3 — cluster + savings expansion)
**Files in scope:**
- `app/db/seed/demo_baseline.sql` — Layer A SQL seed (institutions, addresses, entity)
- `docs/postman/collections/900_DEMO_DAY_SEED.postman_collection.json` — Layer B API seed
- `scripts/load_demo_data.sh` — loader orchestrator
- `scripts/purge_demo_data.sh` — idempotent teardown

---

## Purpose

Provide a realistic, demo-ready PE market dataset for stakeholder demos. The dataset must:
1. Show a **clustered map** of multiple restaurants (San Isidro, Lima).
2. Show customers in distinguishable **subscription/order states** (active subscriber with orders, subscriber without orders, user without subscription).
3. Show plates with **positive, visible savings** (~15–25% per plate).

---

## Dataset Decisions

### Plan pricing (v3)

| Field | v2 (old) | v3 (current) |
|---|---|---|
| `price` | S/ 150 | **S/ 80** |
| `credit` | 20 | 20 |
| `credit_cost_per_credit` | 7.5 PEN | **4 PEN** |

At 7.5 PEN/credit every plate yielded negative savings (clamped to 0 by `_compute_savings_pct`). At 4 PEN/credit all plates score 15–25%.

### Savings sanity check (all 10 plates, 4 PEN/credit)

| Restaurant | Plate | Price (S/) | Credits | Cost (S/) | Savings % |
|---|---|---|---|---|---|
| Sabores del Pacifico | Ceviche Clasico | 45 | 9 | 36 | **20.0%** |
| Sabores del Pacifico | Lomo Saltado | 52 | 10 | 40 | **23.1%** |
| Sabores del Pacifico | Aji de Gallina | 42 | 8 | 32 | **23.8%** |
| Sabores del Pacifico | Causa Limena | 35 | 7 | 28 | **20.0%** |
| Doña Lucha Sangucheria | Butifarra | 35 | 7 | 28 | **20.0%** |
| Doña Lucha Sangucheria | Pan con Chicharrón | 38 | 8 | 32 | **15.8%** |
| Anticuchería Don Tomás | Anticuchos de Res | 42 | 8 | 32 | **23.8%** |
| La Esquina del Tiradito | Tiradito de Lenguado | 48 | 9 | 36 | **25.0%** |
| La Esquina del Tiradito | Pulpo al Olivo | 52 | 10 | 40 | **23.1%** |
| Pollos a la Brasa Don Lucho | Pollo a la Brasa (cuarto) | 32 | 6 | 24 | **25.0%** |

Formula: `savings_pct = round((price - credit * 4) / price * 100)`

### Restaurant cluster (San Isidro)

Four new restaurants added around Calle Miguel Dasso, San Isidro (~300 m radius):

| Restaurant | Canonical Key | Address (SQL UUID) | Approx lat/lon |
|---|---|---|---|
| Doña Lucha Sangucheria | `DEMO_RESTAURANT_PE_DONA_LUCHA` | `…0003` | -12.0975, -77.0381 |
| Anticuchería Don Tomás | `DEMO_RESTAURANT_PE_ANTICUCHERIA` | `…0004` | -12.0972, -77.0389 |
| La Esquina del Tiradito | `DEMO_RESTAURANT_PE_TIRADITO` | `…0005` | -12.0980, -77.0375 |
| Pollos a la Brasa Don Lucho | `DEMO_RESTAURANT_PE_POLLOS_BRASA` | `…0006` | -12.0968, -77.0395 |

Existing R1 (Sabores del Pacifico, Miraflores) stays unchanged.

### Customer roles (C01–C07)

| Code | Email | Subscription | Orders | Demo role |
|---|---|---|---|---|
| C01 | `demo.cliente.pe.01@vianda.demo` | yes | 5 | Active subscriber with history |
| C02 | `demo.cliente.pe.02@vianda.demo` | yes | 5 | Active subscriber with history |
| C03 | `demo.cliente.pe.03@vianda.demo` | yes | 5 | Active subscriber with history |
| C04 | `demo.cliente.pe.04@vianda.demo` | yes | 5 | Active subscriber with history |
| C05 | `demo.cliente.pe.05@vianda.demo` | yes | 5 | Active subscriber with history |
| C06 | `demo.cliente.pe.06@vianda.demo` | **none** | 0 | Show subscription purchase flow |
| C07 | `demo.cliente.pe.07@vianda.demo` | yes | **0** | Show first-order flow |

Shared password for all customers: `DemoPass1!`

---

## UUID Scheme

All demo UUIDs share the prefix `dddddddd-dec0-NNNN-XXXX-YYYYYYYYYYYY`.

| Sub-range | Entities |
|---|---|
| `0001` | Institution, admin user, institution entity |
| `0010` | Addresses: `…0001` office, `…0002` R1 (Miraflores), `…0003` R2, `…0004` R3, `…0005` R4, `…0006` R5 |

Canonical key prefix for all Postman-seeded entities: `DEMO_*`

---

## Folder structure (collection 900)

| Folder | Contents |
|---|---|
| `00 Setup` | Login as demo-admin@vianda.market |
| `10 Supplier menu (PE)` | 5 restaurants, 5 QR codes, 10 products, 10 plates, 50 PKDs (Mon–Fri), 1 plan |
| `20 Customers (PE)` | Signup + verify + login + register address for C01–C07 |
| `30 Subscribe each customer` | Subscribe C01–C05 + C07; C06 intentionally skipped |
| `40 Order history loop` | 5 orders each for C01–C05 (C06/C07 not in this folder) |
| `99 Sanity checks` | Read-only assertions (see below) |

---

## Sanity check assertions (folder 99)

1. ≥ 5 PE demo restaurants exist.
2. All demo plates in `by-city` response have `savings` between 15 and 30 (none are 0).
3. `DEMO_PLAN_PE_ESTANDAR` exists with `price=80.0` and `credit=20`.
4. ≥ 7 PE demo customers exist.
5. ≥ 10 PE demo plates exist.
6. ≥ 6 active subscriptions (C01–C05 + C07; C06 excluded).
7. ≥ 5 completed plate pickups.
8. C06 has 0 subscriptions.
9. C07 has ≥ 1 active subscription (verified via C07 token — no orders in folder 40).

---

## Purge safety

`scripts/purge_demo_data.sh` catches all demo data via two filters:
- UUID prefix `dddddddd-dec0-` (SQL-seeded rows)
- Username `LIKE 'demo.cliente.pe.%@vianda.demo'` (all C01–C07)
- Canonical key `LIKE 'DEMO_%'` (Postman-seeded rows)

C06 and C07 usernames (`demo.cliente.pe.06@vianda.demo`, `demo.cliente.pe.07@vianda.demo`) both match the LIKE pattern — confirmed safe to purge.

---

## Checklist

- [x] `demo_baseline.sql` — 4 new restaurant addresses (R2–R5) with deterministic dec0 UUIDs
- [x] Plan repriced: 20 credits / S/ 80 (credit cost = 4 PEN)
- [x] Plan marketing_description and features updated to reflect new price
- [x] 4 new restaurants in collection 10 (upsert + QR + activate)
- [x] 6 new products in collection 10
- [x] 6 new plates in collection 10 (R2: 2, R3: 1, R4: 2, R5: 1)
- [x] 30 new PKD rows in collection 10 (6 plates × Mon–Fri)
- [x] C06 and C07 added to collection 20 (signup + verify + login + address)
- [x] C07 added to collection 30 (subscribe; C06 skipped)
- [x] Folder 99 updated: 5 restaurants, savings 15–30%, 7 customers, 6 active subs, C06/C07 state checks
- [x] `load_demo_data.sh` credentials block updated (C06 + C07 with role labels)
- [x] `purge_demo_data.sh` verified — existing LIKE pattern catches C06/C07
