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
├── config/                  # Settings, enums, static config (supported cities, cuisines, etc.)
├── core/                    # Versioning infrastructure
│   └── versioning.py        # create_versioned_router, APIVersion
├── db/                      # Schema, migrations, triggers, seed
│   ├── schema.sql           # Table definitions, enums
│   ├── trigger.sql          # History triggers
│   ├── seed.sql
│   └── migrations/          # ALTER scripts
├── dependencies/            # FastAPI request-scoped dependencies
│   └── database.py          # get_db() - connection from pool
├── dto/                     # Data Transfer Objects (DB ↔ services)
│   └── models.py            # Pure Pydantic models, no logic
├── gateways/                # External service abstractions
│   ├── base_gateway.py
│   ├── google_maps_gateway.py
│   └── google_places_gateway.py
├── routes/                  # API endpoints
│   ├── crud_routes.py       # Admin CRUD (Product, Plan, Restaurant, etc.)
│   ├── crud_routes_user.py  # User CRUD (Subscription, PaymentMethod)
│   ├── admin/               # Admin-only routes
│   ├── super_admin/         # Super Admin only
│   ├── billing/             # Client bills, institution bills
│   ├── customer/            # B2C payment methods
│   └── *.py                 # Domain routes (plate_selection, restaurant, etc.)
├── schemas/                 # Pydantic API contracts (request/response)
│   └── consolidated_schemas.py
├── security/                # Scoping, access control
│   ├── institution_scope.py # InstitutionScope, get_institution_scope()
│   ├── entity_scoping.py    # EntityScopingService - per-entity scope rules
│   └── scoping.py
├── services/                # Business logic
│   ├── crud_service.py      # Generic CRUD
│   ├── route_factory.py     # create_crud_routes, create_*_routes()
│   └── versioned_route_factory.py
└── utils/                   # Helpers (db, log, address formatting, etc.)

application.py               # FastAPI app, route registration, lifespan
```

---

## Route Registration Flow

1. **`application.py`** creates the app and registers all routers.
2. **Versioned wrappers:** Every business route uses `create_versioned_router("api", ["Tag"], APIVersion.V1)` → prefix `/api/v1`.
3. **Two CRUD routers:**
   - **`crud_routes.py`** → Admin/System CRUD (no user context): Product, Plan, Restaurant, CreditCurrency, Institution, Plate, Geolocation, InstitutionEntity.
   - **`crud_routes_user.py`** → User CRUD (user_id from `current_user`): Subscription, PaymentMethod.
4. **Route factory** (`app/services/route_factory.py`) generates standard CRUD routes via `create_plan_routes()`, `create_product_routes()`, etc.
5. **Manual routes** for custom logic: plate_selection, plate_pickup, restaurant, address, billing, etc.
6. **Registration order:** Manual/custom routes must be registered before auto-generated if they share paths (FastAPI matches first).

---

## Data Flow

```
Request
  → Middleware (CORS, PermissionCache)
  → Route (FastAPI)
  → Depends(get_current_user, get_db)
  → Service (business logic)
  → db_read / db_write (app/utils/db.py)
  → psycopg2 / connection pool
  → PostgreSQL
```

---

## Key Entry Points

| Concern | Location |
|--------|----------|
| Auth / permissions | `app/auth/dependencies.py` |
| Institution scoping | `app/security/institution_scope.py`, `entity_scoping.py` |
| Database connection | `app/dependencies/database.py`, `app/utils/db_pool.py` |
| CRUD generation | `app/services/route_factory.py`, `versioned_route_factory.py` |
| DTOs | `app/dto/models.py` |
| API schemas | `app/schemas/consolidated_schemas.py` |
| DB schema | `app/db/schema.sql` |

---

## Route Categories

| Category | Example | Auth |
|----------|---------|------|
| Infrastructure | `/health`, `/pool-stats` | None |
| Versioned v1 | `/api/v1/plans/`, `/api/v1/restaurants/` | JWT |
| Admin (non-versioned) | `/admin/archival/*` | Internal |
| Webhooks | `/api/v1/webhooks/*` | Stripe signature |
| Leads | `/api/v1/leads/*` | None, rate-limited |

---

## Versioning

- **Strategy:** URL path (`/api/v1/...`).
- **Implementation:** `app/core/versioning.py` — `create_versioned_router(prefix, tags, version)`.
- Route files define prefix without version (e.g. `/plans`); the wrapper adds `/api/v1`.

---

## Scoping

- **Employee:** Global (all institutions).
- **Supplier:** Scoped to `institution_id` from JWT.
- **EntityScopingService** (`app/security/entity_scoping.py`) maps entity types to scope logic for both base and enriched endpoints.
