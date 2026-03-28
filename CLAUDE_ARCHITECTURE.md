# Kitchen API Architecture

**Purpose:** Fast reference for AI-assisted development. Reduces exploratory searches and provides structural context in one place.

**Keep in context with:** [CLAUDE.md](./CLAUDE.md)

---

## Directory Structure

```
app/
├── auth/                    # JWT auth, dependencies, permission checks
│   ├── dependencies.py      # get_current_user, get_employee_user, get_super_admin_user, etc.
│   ├── routes.py            # Login, JWT token creation
│   └── middleware/
│       └── permission_cache.py
├── config/                  # Settings, enums, static config
│   ├── settings.py          # App settings, env vars
│   ├── enums/               # Python enums (kitchen_days, address_types, status, etc.)
│   ├── location_config.py   # Location/city configuration
│   ├── market_config.py     # Market-specific configuration
│   └── supported_*.py       # supported_cities, supported_countries, supported_currencies, etc.
├── core/                    # Versioning infrastructure
│   └── versioning.py        # create_versioned_router, APIVersion
├── db/                      # Schema, triggers, seed
│   ├── schema.sql           # Table definitions, enums
│   ├── trigger.sql          # History triggers
│   ├── seed.sql
│   └── index.sql            # Index definitions
├── dependencies/            # FastAPI request-scoped dependencies
│   └── database.py          # get_db() - connection from pool
├── dto/                     # Data Transfer Objects (DB ↔ services)
│   ├── models.py            # Pure Pydantic models, no logic
│   └── dynamic_models.py    # Dynamic DTO generation
├── gateways/                # External service abstractions
│   ├── base_gateway.py
│   ├── google_maps_gateway.py
│   └── google_places_gateway.py
├── routes/                  # API endpoints
│   ├── crud_routes.py       # Admin CRUD (Product, Plan, Restaurant, etc.)
│   ├── crud_routes_user.py  # User CRUD (Subscription, PaymentMethod)
│   ├── admin/               # Admin-only (markets, discretionary, archival, archival_config)
│   ├── super_admin/         # Super Admin only (discretionary approval)
│   ├── billing/             # Client bills, institution bills
│   ├── customer/            # B2C payment methods
│   ├── payment_methods/     # Mercado Pago, etc.
│   └── *.py                 # Domain routes (plate_selection, restaurant, address, etc.)
├── schemas/                 # Pydantic API contracts (request/response)
│   ├── consolidated_schemas.py
│   ├── billing/             # client_bill, institution_bill
│   ├── institution_entity.py
│   ├── payment_method.py
│   ├── subscription.py
│   └── versioned_schemas.py
├── security/                # Scoping, access control
│   ├── scoping.py           # InstitutionScope, UserScope (central implementation)
│   ├── institution_scope.py # Re-exports from scoping.py (backward compat)
│   ├── entity_scoping.py    # EntityScopingService - per-entity scope rules
│   └── field_policies.py    # Field-level access policies
├── services/                # Business logic
│   ├── crud_service.py      # Generic CRUD
│   ├── route_factory.py     # create_crud_routes, create_*_routes()
│   ├── versioned_route_factory.py
│   ├── billing/             # client_bill, institution_billing, tax_doc_service
│   ├── cron/                # billing_events, currency_refresh, holiday_refresh, kitchen_start_promotion, etc.
│   ├── payment_provider/    # Stripe (live, mock)
│   └── supplier_payout/     # Stripe payout, mock
└── utils/                   # Helpers
    ├── db.py                # db_read, db_write, get_db_connection
    ├── db_pool.py           # Connection pool, get_db_connection_context
    ├── log.py
    ├── gcs.py               # Google Cloud Storage
    ├── checksum.py
    └── rate_limit.py

application.py               # FastAPI app, route registration, lifespan
```

---

## Route Registration Flow

1. **`application.py`** creates the app and registers all routers.
2. **Versioned wrappers:** Every business route uses `create_versioned_router("api", ["Tag"], APIVersion.V1)` → prefix `/api/v1`.
3. **Two CRUD routers:**
   - **`crud_routes.py`** → Admin/System CRUD (no user context): Product, Plan, Restaurant, CreditCurrency, Institution, Plate, Geolocation, InstitutionEntity.
   - **`crud_routes_user.py`** → User CRUD (user_id from `current_user`): Subscription, PaymentMethod; includes subscription_payment (with-payment, confirm-payment) before generic CRUD.
4. **Route factory** (`app/services/route_factory.py`) generates standard CRUD routes via `create_plan_routes()`, `create_product_routes()`, etc.
5. **Custom/manual routes** (not in CRUD routers): plate_selection, plate_pickup, plate_review, favorite, employer, address, qr_code, restaurant, restaurant_balance, restaurant_transaction, restaurant_staff, plate_kitchen_days, national_holidays, restaurant_holidays, client_bill, institution_bill, markets, countries, currencies, cities, provinces, cuisines, leads, webhooks, customer payment_methods, enums, admin discretionary, super_admin discretionary, archival, archival_config.
6. **Registration order:** Institution entities router registered before CRUD so `/enriched` matches before `/{entity_id}`. Manual/custom routes must be registered before auto-generated if they share paths (FastAPI matches first).

---

## Data Flow

```
Request
  → Middleware (CORS, PermissionCache)
  → Route (FastAPI)
  → Depends(get_current_user, get_db)
  → Service (business logic)
  → db_read / db_write (app/utils/db.py)
  → psycopg2 via connection from pool (app/utils/db_pool.py)
  → PostgreSQL
```

**Lifespan:** `application.py` lifespan initializes `app.state.db_pool` at startup and closes it at shutdown. Routes use `get_db()` which yields connections from `get_db_connection_context()`.

---

## Key Entry Points

| Concern | Location |
|--------|----------|
| Auth / permissions | `app/auth/dependencies.py` |
| Institution scoping | `app/security/scoping.py` (InstitutionScope, UserScope), `app/security/entity_scoping.py` (EntityScopingService) |
| Database connection | `app/dependencies/database.py` (get_db), `app/utils/db_pool.py` (get_db_connection_context, get_db_pool) |
| CRUD generation | `app/services/route_factory.py`, `versioned_route_factory.py` |
| DTOs | `app/dto/models.py`, `app/dto/dynamic_models.py` |
| API schemas | `app/schemas/consolidated_schemas.py`, `app/schemas/billing/`, domain-specific schemas |
| DB schema | `app/db/schema.sql` |

---

## Route Categories

| Category | Example | Auth |
|----------|---------|------|
| Infrastructure | `/health`, `/pool-stats` | `/health` none; `/pool-stats` JWT |
| Versioned v1 | `/api/v1/plans/`, `/api/v1/restaurants/` | JWT |
| Admin (versioned) | `/api/v1/admin/archival/*`, `/api/v1/admin/archival-config/*`, `/api/v1/admin/discretionary/*`, `/api/v1/admin/markets/*` | Internal |
| Super-Admin (versioned) | `/api/v1/super-admin/discretionary/*` | Super Admin only |
| Webhooks | `/api/v1/webhooks/*` | Stripe signature |
| Leads | `/api/v1/leads/*` | None, rate-limited |

---

## Versioning

- **Strategy:** URL path (`/api/v1/...`).
- **Implementation:** `app/core/versioning.py` — `create_versioned_router(prefix, tags, version)`.
- Route files define prefix without version (e.g. `/plans`); the wrapper adds `/api/v1`.

---

## Scoping

- **Employee (Internal):** Global (all institutions).
- **Supplier:** Scoped to `institution_id` from JWT.
- **Employer:** Institution-scoped (like Supplier).
- **EntityScopingService** (`app/security/entity_scoping.py`) maps entity types to scope logic for both base and enriched endpoints. Use `EntityScopingService.get_scope_for_entity(entity_type, current_user)` in routes.
- **InstitutionScope** and **UserScope** live in `app/security/scoping.py`; `institution_scope.py` re-exports for backward compatibility.
