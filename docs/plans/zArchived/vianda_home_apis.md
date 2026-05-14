> **ARCHIVED** — Durable content promoted to `docs/api/marketing_site/LEADS_COVERAGE_CHECKER.md`.
> This file is preserved as the original implementation plan (context, file analysis, pre-implementation notes). For current reference on the marketing site API contract, read the permanent doc above.

# vianda-home Marketing Site — Public Leads API

**Status:** Implemented (2026-04-05)
**Source requirements:** `/Users/cdeachaval/learn/vianda/vianda-home/docs/frontend/feedback_for_backend/api-requirements.md`
**Frontend index:** `/Users/cdeachaval/learn/vianda/vianda-home/docs/frontend/AGENT_INDEX.md`

---

## Context

vianda-home (marketing site) needs 4 new unauthenticated endpoints to make the landing page data-driven. Currently all sections use hardcoded stub data. The frontend has typed API client stubs ready to activate (`src/api/leads.ts`) the moment these endpoints exist.

The kitchen already has a `leads` router (`app/routes/leads.py`) with 5 public, rate-limited endpoints. The 4 new endpoints belong in this same router following the same pattern. CORS is already `allow_origins=["*"]` — no CORS changes needed.

---

## Files Analyzed When Creating This Plan

To avoid re-exploration, these are the files that were read to produce this plan:

| File | What was learned |
|---|---|
| `app/routes/leads.py` | All 5 existing public endpoints, caching pattern, rate-limit decorators, `@limiter.limit()` usage |
| `app/schemas/consolidated_schemas.py` | `MarketPublicMinimalSchema`, `CityMetricsResponseSchema`, `EmailRegisteredResponseSchema` — the lead schema patterns |
| `app/dto/models.py` | `RestaurantDTO` (14 fields, no tagline/cover/rating), `PlanDTO` (16 fields, no yearly_price/features/highlighted) |
| `app/db/schema.sql` | `ops.restaurant_info` (13 columns), `customer.plan_info` (15 columns), no `platform_metrics_config` table exists |
| `app/db/trigger.sql` | `restaurant_history_trigger_func` and `plan_history_trigger_func` — both active, both need updating if columns are added to main tables |
| `app/utils/locale.py` | `resolve_locale_from_header(accept_language: Optional[str]) -> str` — parses Accept-Language header, returns `"en"` / `"es"` / `"pt"`. Use this for all 4 endpoints. |
| `application.py` | CORS is `allow_origins=["*"]`, leads router registered as `v1_leads_router` under `/api/v1/` |
| `app/services/city_metrics_service.py` | COUNT(DISTINCT restaurant_id) aggregate query pattern, two-query approach (fetch list → count for match) |

---

## Endpoints to Build

| Endpoint | Purpose | Landing section |
|---|---|---|
| `GET /api/v1/leads/platform-metrics` | Trust bar — kitchen count + financial impact stats | TrustBar | **Implemented** |
| `GET /api/v1/leads/restaurants` | Kitchen card grid (`?featured=bool&limit=int`) | LocalKitchensPreview | **Implemented** |
| `GET /api/v1/leads/featured-restaurant` | Single spotlight restaurant with perks | FeaturedVendorSpotlight | **Already existed** |
| `GET /api/v1/leads/plans` | Public pricing table | SubscriptionTiers | **Implemented** |

Implemented endpoints: no auth, `@limiter.limit("60/minute")`, reCAPTCHA v3 required via `X-Recaptcha-Token` header.

---

## Design Decisions

### Financial metrics (member_savings_usd, restaurant_revenue_usd) — IMPLEMENTED
Admin-editable values in `core.platform_metrics_config` single-row table. `partner_kitchen_count` computed live from active restaurants.

### average_rating and review_count
No reviews system exists. Store as **admin-settable fields on `restaurant_info`** (defaulting to `NULL` / `0`). Frontend receives null/0 until admin populates. Become real computed fields when a reviews feature is built.

### Localization
`resolve_locale_from_header()` already exists in `app/utils/locale.py`. **Phase 1: wire the header infrastructure (Accept-Language → X-Content-Language) and store all text fields in English only.** Spanish translation columns are Phase 2 (requires a translation workflow).

---

## Schema Changes Required

### New table: `core.platform_metrics_config`
```sql
CREATE TABLE IF NOT EXISTS core.platform_metrics_config (
    id                      INTEGER PRIMARY KEY DEFAULT 1,
    member_savings_usd      NUMERIC(15,2) NOT NULL DEFAULT 0,
    restaurant_revenue_usd  NUMERIC(15,2) NOT NULL DEFAULT 0,
    updated_by              UUID NULL,
    updated_date            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_platform_metrics_single_row CHECK (id = 1)
);
```
Seed: one row with placeholder values `(1, 2400000.00, 890000.00, NULL, NOW())`.
No history trigger needed (config table, not a business entity).

### New columns on `ops.restaurant_info`
```sql
tagline          TEXT         NULL,
cover_image_url  TEXT         NULL,
average_rating   NUMERIC(3,1) NULL,
review_count     INTEGER      NOT NULL DEFAULT 0,
is_featured      BOOLEAN      NOT NULL DEFAULT FALSE,
verified_badge   BOOLEAN      NOT NULL DEFAULT FALSE,
spotlight_label  TEXT         NULL,
member_perks     TEXT[]       NULL
```
Same 8 columns must also be added to `audit.restaurant_history` and to the INSERT in `restaurant_history_trigger_func()`.

### New columns on `customer.plan_info`
```sql
-- yearly_price REMOVED — all prices are monthly, no yearly pricing exists
marketing_description   TEXT             NULL,     -- already existed
features                TEXT[]           NULL,     -- already existed
cta_label               VARCHAR(50)      NULL,     -- already existed
highlighted             BOOLEAN          NOT NULL DEFAULT FALSE  -- added 2026-04-05
```
Only `highlighted` was new — `marketing_description`, `features`, and `cta_label` already existed. `yearly_price` was removed from scope (all prices are monthly). Same column added to `audit.plan_history` and `plan_history_trigger_func()`.

---

## DTO Changes (`app/dto/models.py`)

**RestaurantDTO — add:**
```python
tagline: Optional[str] = None
cover_image_url: Optional[str] = None
average_rating: Optional[Decimal] = None
review_count: int = 0
is_featured: bool = False
verified_badge: bool = False
spotlight_label: Optional[str] = None
member_perks: Optional[list[str]] = None
```

**PlanDTO — added:**
```python
highlighted: bool = False  # only new field; marketing_description, features, cta_label already existed
# yearly_price REMOVED — all prices are monthly
```

**PlatformMetricsConfigDTO — IMPLEMENTED**

---

## Pydantic Schemas — Implemented (`app/schemas/consolidated_schemas.py`)

```python
# PlatformMetricsResponseSchema — DEFERRED

class LeadsRestaurantSchema(BaseModel):  # Implemented
    restaurant_id: UUID
    name: str
    cuisine_name: Optional[str] = None
    tagline: Optional[str] = None
    average_rating: Optional[Decimal] = None
    review_count: int = 0
    cover_image_url: Optional[str] = None

class LeadsFeaturedRestaurantSchema(BaseModel):  # Already existed
    # ... (spotlight_label, verified_badge, member_perks)

class LeadsPlanSchema(BaseModel):  # Implemented
    plan_id: UUID
    name: str
    marketing_description: Optional[str] = None
    features: List[str] = []
    cta_label: Optional[str] = None
    credit: int
    price: float  # monthly price — all prices are monthly
    highlighted: bool = False
    currency: str
```

---

## New Service File (`app/services/leads_public_service.py`)

Four functions:

```python
def get_platform_metrics(db) -> dict:
    # 1. SELECT member_savings_usd, restaurant_revenue_usd FROM platform_metrics_config WHERE id = 1
    # 2. SELECT COUNT(*) FROM restaurant_info WHERE status = 'Active' AND is_archived = FALSE
    # Merge and return dict

def get_public_restaurants(db, *, featured_only: bool = False, limit: int = 10) -> list:
    # SELECT restaurant_id, name, cuisine, tagline, average_rating, review_count, cover_image_url
    # FROM restaurant_info
    # WHERE status = 'Active' AND is_archived = FALSE
    # [AND is_featured = TRUE if featured_only]
    # LIMIT limit

def get_featured_restaurant(db) -> Optional[dict]:
    # Same fields as above + spotlight_label, verified_badge, member_perks
    # WHERE is_featured = TRUE LIMIT 1
    # Returns None if no featured restaurant → route returns 404

def get_public_plans(db) -> list:
    # SELECT plan_info.*, credit_currency_info.currency_code
    # FROM plan_info
    # JOIN market_info ON plan_info.market_id = market_info.market_id
    # JOIN credit_currency_info ON market_info.credit_currency_id = credit_currency_info.credit_currency_id
    # WHERE plan_info.status = 'Active' AND plan_info.is_archived = FALSE
    # AND plan_info.market_id != '00000000-0000-0000-0000-000000000001'  -- exclude Global
```

---

## Route Handlers (add to `app/routes/leads.py`)

Pattern for all 4 — reads Accept-Language, resolves locale, sets X-Content-Language:

```python
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from app.utils.locale import resolve_locale_from_header

@router.get("/platform-metrics", response_model=PlatformMetricsResponseSchema)
@limiter.limit("60/minute")
async def get_platform_metrics_endpoint(request: Request, db = Depends(get_db)):
    data = get_platform_metrics(db)
    locale = resolve_locale_from_header(request.headers.get("accept-language"))
    response = JSONResponse(content=jsonable_encoder(PlatformMetricsResponseSchema(**data)))
    response.headers["X-Content-Language"] = locale
    return response
```

---

## All Files to Change

| File | Change |
|---|---|
| `app/db/schema.sql` | Add `platform_metrics_config` table; 8 columns on `restaurant_info` + `restaurant_history`; 5 columns on `plan_info` + `plan_history` |
| `app/db/trigger.sql` | Update `restaurant_history_trigger_func` and `plan_history_trigger_func` |
| `app/db/seed.sql` | Seed 1 row into `platform_metrics_config` |
| `app/dto/models.py` | Add fields to `RestaurantDTO`, `PlanDTO`; add `PlatformMetricsConfigDTO` |
| `app/schemas/consolidated_schemas.py` | Add `PlatformMetricsResponseSchema`, `LeadsRestaurantSchema`, `LeadsFeaturedRestaurantSchema`, `LeadsPlanSchema` |
| `app/services/leads_public_service.py` *(new)* | `get_platform_metrics`, `get_public_restaurants`, `get_featured_restaurant`, `get_public_plans` |
| `app/routes/leads.py` | Add 4 route handlers with locale header wiring |

---

## Verification Checklist

1. `bash app/db/build_kitchen_db.sh` — no errors
2. `psql kitchen -c "\d restaurant_info"` — confirm 8 new columns
3. `psql kitchen -c "\d plan_info"` — confirm 5 new columns
4. `psql kitchen -c "SELECT * FROM platform_metrics_config;"` — confirm seed row exists
5. `GET /api/v1/leads/platform-metrics` — returns `member_savings_usd`, `restaurant_revenue_usd`, `partner_kitchen_count`
6. `GET /api/v1/leads/restaurants?featured=true&limit=3` — returns empty list (until admin sets `is_featured = TRUE`)
7. `GET /api/v1/leads/featured-restaurant` — returns 404 (until admin sets a featured restaurant)
8. `GET /api/v1/leads/plans` — returns active plans (empty marketing fields until admin populates)
9. All 4 responses include `X-Content-Language: en` header
10. `python3 -c "from application import app; print('OK')"` — import check passes
