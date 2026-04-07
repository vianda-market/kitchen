# Cuisine Management Roadmap

**Document Version**: 1.0
**Date**: April 2026
**Status**: Planning
**Supersedes**: Static cuisine list in `app/config/supported_cuisines.py`

---

## Problem Statement

Cuisine classification touches three critical surfaces:

1. **Supplier product registration** — suppliers assign a cuisine when creating restaurants/plates; input must be structured and guided (autocomplete or dropdown)
2. **Customer discovery** — customers filter and browse by cuisine; data must be clean and consistent
3. **Recommendation engine** — cuisine is a parameter for plate recommendations; data quality directly impacts recommendation accuracy

The current implementation uses a hardcoded Python tuple (`SUPPORTED_CUISINES`) validated at the API layer. This has three problems:

- **Rigid**: Adding a cuisine requires a code change and redeploy
- **Incomplete**: 9 cuisines is insufficient for a multi-market platform (AR, PE, US)
- **No governance**: No process for suppliers to suggest missing cuisines or for admins to curate the list

---

## Current State

| Component | Location | Description |
|-----------|----------|-------------|
| Static list | `app/config/supported_cuisines.py` | 9 hardcoded cuisines (American, Chinese, French, Indian, Italian, Japanese, Mediterranean, Mexican, Thai) |
| API endpoint | `app/routes/cuisines.py` | `GET /api/v1/cuisines/` — returns static list |
| DB column | `restaurant_info.cuisine` | `VARCHAR(50)`, no FK, no constraint |
| Validation | `is_supported_cuisine()` | Case-insensitive match against static tuple |
| Client doc | `docs/api/shared_client/CUISINES_API_CLIENT.md` | Frontend integration guide |

---

## Design Decision: Database-Managed Lookup Table

**Rejected alternatives:**

| Approach | Why rejected |
|----------|-------------|
| PostgreSQL enum type | Requires ALTER TYPE + redeploy for each new value; cannot be managed by admins |
| Free-text field | Leads to duplicates, typos, inconsistent data ("Itallian", "Italian!", "Italy food") — destroys filtering and recommendations |
| External API on-demand (Spoonacular, HERE) | Expensive per-call; strict ToU prevents permanent storage; dependency on third-party availability |

**Chosen approach: `cuisine` lookup table** — database-managed records that act as dynamic enums. Admins curate the list via API, suppliers select from it, and an "Other" escape hatch feeds a review queue.

---

## Phase 1 — Cuisine Lookup Table + Seed Data

### 1.1 Schema

```sql
-- Canonical cuisine list, managed by Internal admins
CREATE TABLE cuisine (
    cuisine_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cuisine_name VARCHAR(80) NOT NULL,             -- default / English name, used as fallback
    cuisine_name_i18n JSONB,                       -- localized names: { "en": "Italian", "es": "Italiana", "pt": "Italiana" }
    slug VARCHAR(80) NOT NULL UNIQUE,              -- lowercase, hyphenated, for URLs and dedup
    parent_cuisine_id UUID REFERENCES cuisine(cuisine_id),  -- optional hierarchy (e.g. Tuscan → Italian)
    description VARCHAR(500),                                -- nullable, can be filled later to describe the cuisine
    origin_source VARCHAR(20) NOT NULL DEFAULT 'seed',      -- seed | supplier
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    display_order INT,                         -- optional manual sort weight
    created_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modified_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID,
    modified_by UUID
);

-- Supplier suggestions awaiting Internal review
CREATE TABLE cuisine_suggestion (
    suggestion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suggested_name VARCHAR(120) NOT NULL,
    suggested_by UUID NOT NULL,                -- user_id of the supplier
    restaurant_id UUID,                        -- restaurant that triggered the suggestion
    status VARCHAR(20) NOT NULL DEFAULT 'Pending',  -- Pending | Approved | Rejected
    reviewed_by UUID,                          -- Internal user who reviewed
    reviewed_date TIMESTAMPTZ,
    review_notes VARCHAR(500),
    resolved_cuisine_id UUID REFERENCES cuisine(cuisine_id),  -- set on approval (new or mapped to existing)
    created_date TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Note on fields:**
- `parent_cuisine_id` enables hierarchy (e.g. "Poke" under "Japanese"). Seeded with examples so frontend can test parent/child display from day one.
- `description` is nullable — can be filled later by admins to describe each cuisine for tooltip/info display.
- `origin_source` tracks provenance: `seed` for records from our seed file, `supplier` for records submitted by suppliers through the suggestion flow.
- `created_by` / `modified_by` on seed records point to the `bot_chef` system user (`bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb`). On supplier-submitted records, `created_by` is the supplier who suggested it and `modified_by` is the Internal employee who approved it.

### 1.2 Seed Strategy

**Goal**: Provide a minimal, curated starting set. The system (supplier suggestions + admin review) grows the list organically.

**No external APIs or third-party data sources.** For legal and cost reasons, we author our own seed data. Cuisine names are standard industry terms — no licensing concerns when we define them ourselves.

#### Seed file: `app/db/cuisine_seed.sql`

All records use `origin_source = 'seed'` and `created_by = modified_by = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'` (bot_chef).

**Parent cuisines** — one per country we serve, plus global classics:

| Parent cuisine | Rationale |
|---------------|-----------|
| Argentinean | AR market |
| Peruvian | PE market |
| American | US market + global classic |
| Chinese | Global classic |
| Japanese | Global classic |
| Indian | Global classic |
| African | Global classic |
| Italian | Global classic |
| Spaniard | Global classic |
| English | Global classic |
| French | Global classic |
| Portuguese | Global classic |
| German | Global classic |
| Polish | Global classic |
| Russian | Global classic |

**Child cuisines** — a few examples so the UI can test hierarchical display:

| Child cuisine | Parent |
|--------------|--------|
| Poke | Japanese |
| Tapas | Spaniard |
| Pizza | Italian |
| Burger | American |
| Minutas | Argentinean |
| Chifa | Peruvian |
| Seafood | Peruvian |

**Total seed: 15 parents + 7 children = 22 records.** The rest comes from suppliers using the suggestion flow (Phase 2.2) and Internal employees approving them.

### 1.3 DB Change: `restaurant_info.cuisine` VARCHAR → `cuisine_id` FK

No migration needed — tear down and rebuild via `bash app/db/build_kitchen_db.sh`.

Changes (follow full SCHEMA_CHANGE_GUIDE):
1. `schema.sql` — Add `cuisine` and `cuisine_suggestion` tables; replace `cuisine VARCHAR(50)` with `cuisine_id UUID REFERENCES cuisine(cuisine_id)` on `restaurant_info`
2. `trigger.sql` — Add audit triggers for new tables; update `restaurant_info` audit to mirror `cuisine_id`
3. `seed.sql` — Insert cuisine seed data (bot_chef as author); update restaurant seeds to reference `cuisine_id` FK
4. `app/dto/models.py` — Add `CuisineDTO`, `CuisineSuggestionDTO`; update `RestaurantDTO`
5. `app/schemas/consolidated_schemas.py` — Add cuisine schemas; update restaurant schemas
6. Services and routes — update to use FK

---

## Phase 2 — API Layer

### 2.1 Public Cuisines Endpoint (replaces current)

```
GET /api/v1/cuisines/
```

**Changes from current**:
- Source: DB query instead of Python tuple
- Response adds `cuisine_id` and `slug`
- Supports `?search=` for autocomplete
- Supports `?language=` for localized names (Phase 5)
- Supports `?include_inactive=true` for admin views

**Response**:
```json
[
  { "cuisine_id": "uuid", "cuisine_name": "Italian", "slug": "italian", "parent_cuisine_id": null },
  { "cuisine_id": "uuid", "cuisine_name": "Tuscan", "slug": "tuscan", "parent_cuisine_id": "uuid-of-italian" }
]
```

**Auth**: Same as current — Customer, Employee, or Supplier.

### 2.2 Supplier "Other" Flow

When a supplier selects "Other" on the restaurant form:

1. Frontend shows a free-text input for `suggested_name`
2. `POST /api/v1/cuisines/suggestions` creates a `cuisine_suggestion` record with status `Pending`
3. The restaurant is created with `cuisine_id = NULL` (cuisine pending review)
4. Backend sends notification to Internal team (email or dashboard flag)

**Endpoint**:
```
POST /api/v1/cuisines/suggestions
Body: { "suggested_name": "Nikkei", "restaurant_id": "uuid" }
Auth: Supplier
Response: 201 { "suggestion_id": "uuid", "status": "Pending" }
```

### 2.3 Admin Cuisine CRUD

Internal-only endpoints for managing the canonical list:

```
POST   /api/v1/admin/cuisines              — Add a new cuisine
PUT    /api/v1/admin/cuisines/{cuisine_id}  — Edit name, slug, parent, active status
DELETE /api/v1/admin/cuisines/{cuisine_id}  — Soft-delete (set is_active = false)
```

### 2.4 Admin Suggestion Review

```
GET  /api/v1/admin/cuisines/suggestions              — List pending suggestions
PUT  /api/v1/admin/cuisines/suggestions/{id}/approve  — Approve: creates cuisine (or maps to existing) + updates restaurant
PUT  /api/v1/admin/cuisines/suggestions/{id}/reject   — Reject: adds review_notes, restaurant keeps NULL cuisine
```

**On approval**:
1. If the suggestion maps to an existing cuisine → set `resolved_cuisine_id` to that cuisine
2. If it's genuinely new → create a new `cuisine` row, set `resolved_cuisine_id`
3. Update the originating restaurant's `cuisine_id` to `resolved_cuisine_id`
4. Optionally notify the supplier that their cuisine was approved

---

## Phase 3 — Frontend Integration (Autocomplete)

### Supplier Form (B2B — vianda-platform)

Replace the current dropdown with an **autocomplete input**:

1. On keystroke, call `GET /api/v1/cuisines/?search={query}` (debounced)
2. Show matching cuisines as suggestions
3. Last option in the list: **"Other — suggest a new cuisine"**
4. Selecting "Other" reveals a free-text input + submit to suggestions API
5. Restaurant is saved; cuisine shows as "Pending review" until approved

### Customer Filters (B2C — vianda-app)

- Filter chips or searchable dropdown populated from `GET /api/v1/cuisines/`
- Only active cuisines with at least one restaurant shown
- Group by parent cuisine optionally (Italian > Tuscan, Neapolitan)

### Customer Plate Display (B2C — vianda-app)

- Show cuisine name on plate cards (resolved from restaurant's cuisine)
- Cuisine used as a parameter in recommendation engine queries

---

## Phase 4 — Localization

Resolves Phase 3 of `LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md`. **Decision: JSONB column** (not static label map).

### Why JSONB, not enum labels

A static label map in `app/i18n/enum_labels.py` only works for a fixed, developer-managed list. Since cuisines are DB-managed and suppliers inject new records through the suggestion flow, a static Python dict would require a code deploy every time a new cuisine is approved. The JSONB column keeps translations co-located with the cuisine record and lets Internal admins author translations without a deploy.

### Schema (already included in Phase 1.1)

```sql
cuisine_name VARCHAR(80) NOT NULL,       -- default / English name, used as fallback
cuisine_name_i18n JSONB,                 -- { "en": "Italian", "es": "Italiana", "pt": "Italiana" }
```

### Resolution rules

| Context | How `cuisine_name` is resolved |
|---------|-------------------------------|
| `GET /api/v1/cuisines/?language=es` | `cuisine_name_i18n->>'es'`, falling back to `cuisine_name` if key missing |
| `GET /api/v1/cuisines/` (no language) | `cuisine_name` (English default) |
| Enriched endpoints (`/leads/restaurants`, etc.) | Resolve from `Accept-Language` header → `cuisine_name_i18n->>$locale` with fallback to `cuisine_name` |
| Admin CRUD (`PUT /api/v1/admin/cuisines/{id}`) | Accepts full `cuisine_name_i18n` locale map for editing translations |

### Seed data localization

Seed records include `cuisine_name_i18n` for `en`, `es`, and `pt` — covering the continent (US, AR, PE, BR). Example:

```json
{ "en": "Italian", "es": "Italiana", "pt": "Italiana" }
{ "en": "Japanese", "es": "Japonesa", "pt": "Japonesa" }
{ "en": "Peruvian", "es": "Peruana", "pt": "Peruana" }
{ "en": "Argentinean", "es": "Argentina", "pt": "Argentina" }
{ "en": "Burger", "es": "Hamburguesa", "pt": "Hambúrguer" }
{ "en": "Seafood", "es": "Mariscos", "pt": "Frutos do Mar" }
```

### Supplier-submitted cuisines

When a supplier suggestion is approved and a new `cuisine` row is created, `cuisine_name_i18n` starts as `NULL` (only `cuisine_name` is set from the suggestion). Internal admins can add translations later via the admin CRUD endpoint. The fallback to `cuisine_name` ensures the cuisine displays correctly in all locales until translations are authored.

### Applies to

- `/api/v1/cuisines/` — autocomplete and dropdown
- `/leads/restaurants`, `/leads/featured-restaurant` — enriched restaurant endpoints
- Enriched plate endpoints — cuisine resolved from restaurant's FK
- B2C explore filters — filter chips show localized cuisine names

---

## Phase 5 — AI-Assisted Cuisine Review (Future)

Replace or augment the human reviewer with an AI agent that processes `cuisine_suggestion` records.

### Agent Skill: `review-cuisine-suggestion`

**Input**: `cuisine_suggestion` record (suggested_name, restaurant context)

**Agent workflow**:
1. **Normalize** — check for typos, alternate spellings, transliterations (e.g. "Nippon" → "Japanese")
2. **Deduplicate** — search existing `cuisine` table for semantic matches (e.g. "BBQ" ≈ "Barbecue")
3. **Validate** — web search to confirm the cuisine is a real, recognized cuisine category
4. **Classify** — determine if it should be a top-level cuisine or a sub-cuisine (assign `parent_cuisine_id`)
5. **Recommend** — output one of:
   - `APPROVE_NEW` — create as new cuisine with suggested parent
   - `APPROVE_MAP` — map to existing cuisine (with explanation)
   - `REJECT` — not a valid cuisine (with explanation)
   - `ESCALATE` — ambiguous, needs human review

**Trigger**: Cron job or event-driven when new suggestions arrive.

**Guardrail**: Agent recommendations are auto-applied only if confidence is high. Low-confidence or `ESCALATE` results go to the human review queue.

---

## Implementation Order

| Step | Phase | Description | Depends on |
|------|-------|-------------|------------|
| 1 | 1.1 | Create `cuisine` and `cuisine_suggestion` tables in `schema.sql` | — |
| 2 | 1.2 | Seed `cuisine` table with 22 records (15 parents + 7 children) including i18n | Step 1 |
| 3 | 1.3 | Replace `restaurant_info.cuisine` VARCHAR with `cuisine_id` FK (tear down + rebuild) | Steps 1-2 |
| 4 | 2.1 | Replace `GET /api/v1/cuisines/` to read from DB, add `?search=` | Step 1 |
| 5 | 2.2 | Add `POST /api/v1/cuisines/suggestions` | Step 1 |
| 6 | 2.3 | Add admin CRUD endpoints | Step 1 |
| 7 | 2.4 | Add admin suggestion review endpoints | Steps 1, 5 |
| 8 | 3 | Frontend integration (autocomplete + "Other" flow) | Steps 4-5 |
| 9 | 4 | Localization — populate `cuisine_name_i18n` on seed records, wire `?language=` resolution | Steps 4, 6 |
| 10 | 5 | AI review agent | Steps 5, 7 |

---

## Files Affected

| File | Change |
|------|--------|
| `app/db/schema.sql` | Add `cuisine` and `cuisine_suggestion` tables; modify `restaurant_info` |
| `app/db/trigger.sql` | Add audit triggers for new tables; update `restaurant_info` audit |
| `app/db/seed.sql` | Seed cuisine data; update restaurant seeds to use FK |
| `app/dto/models.py` | Add `CuisineDTO`, `CuisineSuggestionDTO`; update `RestaurantDTO` |
| `app/schemas/consolidated_schemas.py` | Add cuisine schemas; update restaurant schemas |
| `app/routes/cuisines.py` | Rewrite to query DB, add search, add suggestion endpoint |
| `app/routes/admin_cuisines.py` | New — admin CRUD + suggestion review |
| `app/services/cuisine_service.py` | New — cuisine CRUD, suggestion workflow, search |
| `app/config/supported_cuisines.py` | **Delete** — replaced by DB table |
| `app/services/entity_service.py` | Update restaurant create/update to use `cuisine_id` FK |
| `docs/api/shared_client/CUISINES_API_CLIENT.md` | Update for new response shape and suggestion flow |
| `application.py` | Register admin cuisines router |

---

## Cross-Repo Impact

| Repo | Impact | Doc to produce |
|------|--------|---------------|
| **vianda-platform** (B2B) | Replace cuisine dropdown with autocomplete + "Other" flow; add admin cuisine management page | Updated `CUISINES_API_CLIENT.md` |
| **vianda-app** (B2C) | Update cuisine filter to use new response shape; display cuisine on plate cards | Updated `CUISINES_API_CLIENT.md` |
| **vianda-home** (marketing) | Restaurant cards show cuisine from new field | No change if already consuming `cuisine` string |

---

## References

- [LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md](./LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md) — Phase 3 (cuisine localization)
- [CUISINES_API_CLIENT.md](../api/shared_client/CUISINES_API_CLIENT.md) — Current client guide (to be updated)
- [SCHEMA_CHANGE_GUIDE.md](../guidelines/SCHEMA_CHANGE_GUIDE.md) — Required process for DB changes
- [EXPLORE_FILTERS_ROADMAP.md](./b2c_client/EXPLORE_FILTERS_ROADMAP.md) — B2C cuisine filter context
- [PLATE_RECOMMENDATION_AND_FAVORITES_B2C.md](../api/b2c_client/PLATE_RECOMMENDATION_AND_FAVORITES_B2C.md) — Recommendation engine context
