# Structured Ingredients Roadmap

**Status**: Planning
**Last Updated**: 2026-03
**Markets**: AR (Argentina), PE (Peru), US (United States), BR (Brazil)

---

## 1. Problem Statement

`ops.product_info.ingredients` is a `VARCHAR(255)` free-form text field. Suppliers type whatever they want — "chicken, rice, veggies", "Pollo y arroz", "Zanahoria, tomate fresco". This makes it impossible to:

- Display ingredients consistently in the vianda-app (React Native B2C)
- Cross-reference the same ingredient across different suppliers and markets
- Power a recommendation engine ("user likes plates with carrots → suggest other carrot plates")
- Support allergen filtering or dietary warnings down the line

---

## 2. Strategy — Two-Phase Hybrid

The solution uses two external sources in sequence, each doing what it does best:

### Phase 1 — Open Food Facts (real-time, all markets)

[Open Food Facts](https://world.openfoodfacts.org) is a free, open-source, community-driven food database that is natively multilingual. Its taxonomy system provides stable canonical IDs (`en:carrot`, `es:zanahoria`) that exist in multiple languages simultaneously. It is used for real-time autocomplete for all markets — Spanish and English alike.

**Why OFF for all markets, not just Spanish:**
- The taxonomy IDs use English as the canonical language key (`en:carrot`) — the English name is embedded in the ID itself, for free
- No quota, no API key required at launch
- Covers all three markets from a single integration

### Phase 2 — Spoonacular enrichment cron (async, background)

[Spoonacular](https://spoonacular.com/food-api) is a curated, English-language food API that provides per-ingredient images and rich nutritional data. It is **never called in real time** — it runs as a background cron job that enriches catalog entries already saved from OFF.

**The bridge**: the `off_taxonomy_id` field (e.g. `en:carrot`) gives us the English name for free by stripping the prefix. The enrichment cron uses that English name to query Spoonacular accurately — no translation service needed, no wasted quota on speculative searches.

**Result**: a unified catalog where every ingredient eventually has an OFF taxonomy ID (multilingual anchor), a Spoonacular ID (image + nutrition hook), and display names in Spanish, English, and Portuguese.

---

## 3. Open Food Facts API — Expected Responses

### Suggest endpoint (used for real-time autocomplete)

**Request:**
```
GET https://world.openfoodfacts.org/cgi/suggest.pl
  ?tagtype=ingredients
  &term=zanah
  &lc=es
```

**Response (array of strings):**
```json
[
  "zanahoria",
  "zanahoria rallada",
  "zanahoria baby",
  "zanahoria cocida"
]
```

After receiving suggestions, the backend resolves each string to a taxonomy entry (see below) before upserting into the catalog.

---

### Taxonomy API (used after suggestion — resolves stable ID and multilingual names)

**Request:**
```
GET https://world.openfoodfacts.org/api/v2/taxonomy
  ?type=ingredients
  &tags=es:zanahoria
  &fields=name,parents
  &lc=es
```

**Response:**
```json
{
  "en:carrot": {
    "name": {
      "en": "Carrot",
      "es": "Zanahoria",
      "fr": "Carotte",
      "pt": "Cenoura"
    },
    "parents": ["en:root-vegetable"]
  }
}
```

Key observations:
- The response key is always the canonical English taxonomy ID (`en:carrot`) — even when querying by Spanish tag
- `name.es` is the Spanish display label
- `name.en` is extracted from the key itself (strip `en:` prefix); also present in `name.en` directly
- `parents` enables traversal to find a more common English term if the matched entry is too specific

---

## 4. Spoonacular — Future Partnership Only

> **ToS constraint**: Spoonacular's Terms of Use prohibit storing any data from the API, including derived or transformed data. Caching is limited to 1 hour with prior written permission, and only for user-requested data. A background enrichment cron that permanently stores Spoonacular IDs and image filenames would violate these terms.

**Current status**: Spoonacular is not used. If a partnership with written storage permission is secured in the future:
- Spoonacular images would be served **transiently** (no permanent storage)
- Spoonacular nutrition data would go into `ops.ingredient_nutrition` via `source='spoonacular'`
- Settings `SPOONACULAR_ENABLED` and `SPOONACULAR_API_KEY` already exist for this purpose

**Image enrichment instead uses Wikidata** (CC licensed, permanent storage permitted). See §7.
**Nutrition enrichment instead uses USDA FoodData Central** (CC0, permanent storage permitted). See §7.

---

## 5. Data Model

### `ops.ingredient_catalog` — unified multilingual catalog

```sql
CREATE TABLE IF NOT EXISTS ops.ingredient_catalog (
    ingredient_id       UUID         PRIMARY KEY DEFAULT uuidv7(),

    -- Search / dedup key (lowercase, unaccented — for ILIKE and UNIQUE constraint)
    name                VARCHAR(150) NOT NULL,

    -- Display labels
    name_display        VARCHAR(150) NOT NULL,           -- original casing + accents
    name_es             VARCHAR(150) NULL,               -- Spanish label (from OFF taxonomy name.es)
    name_en             VARCHAR(150) NULL,               -- English label (from OFF taxonomy key / name.en)
    name_pt             VARCHAR(150) NULL,               -- Portuguese/Brazil label (from OFF taxonomy name.pt)

    -- Open Food Facts (Phase 1 source for all markets)
    off_taxonomy_id     VARCHAR(100) NULL UNIQUE,        -- e.g. 'en:carrot'

    -- Spoonacular (Phase 5 enrichment — populated by async cron job, never at insert time)
    -- All four columns are intentionally nullable: every new row starts with these as NULL
    -- and stays that way until the enrichment cron runs and finds a confident match.
    spoonacular_id      INTEGER      NULL UNIQUE,        -- set by cron; NULL = not yet enriched
    image_filename      VARCHAR(255) NULL,               -- set by cron; NULL = render generic icon
    off_wikidata_id     VARCHAR(30)  NULL,               -- set by cron if OFF taxonomy includes wikidata link

    -- Enrichment pipeline state (cron uses these to find pending work)
    enriched            BOOLEAN      NOT NULL DEFAULT FALSE,
    -- FALSE = enrichment cron has not yet processed this row
    -- TRUE  = cron has run (spoonacular_id may still be NULL if no confident match was found)
    enrichment_skipped  BOOLEAN      NOT NULL DEFAULT FALSE,
    -- TRUE = cron ran but confidence score was below threshold; flagged for manual review

    -- Provenance
    source              VARCHAR(20)  NOT NULL DEFAULT 'off',
    -- 'off' | 'custom' (supplier-added, unverified) | 'seed' (pre-loaded at launch)

    is_verified         BOOLEAN      NOT NULL DEFAULT FALSE,
    -- TRUE = reviewed by vianda team; safe to surface in all UI contexts

    created_date        TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_date       TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by         UUID         NOT NULL REFERENCES core.user_info(user_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ingredient_catalog_name
    ON ops.ingredient_catalog (name);

-- Full-text search indexes
CREATE INDEX IF NOT EXISTS idx_ingredient_catalog_fts_es
    ON ops.ingredient_catalog USING gin(to_tsvector('spanish', COALESCE(name_es, name_display)));
CREATE INDEX IF NOT EXISTS idx_ingredient_catalog_fts_en
    ON ops.ingredient_catalog USING gin(to_tsvector('english', COALESCE(name_en, '')));

-- Enrichment cron index
CREATE INDEX IF NOT EXISTS idx_ingredient_catalog_enrichment
    ON ops.ingredient_catalog (enriched, enrichment_skipped)
    WHERE enriched = FALSE AND enrichment_skipped = FALSE;
```

---

### `ops.product_ingredient` — product ↔ ingredient junction

```sql
CREATE TABLE IF NOT EXISTS ops.product_ingredient (
    product_ingredient_id UUID     PRIMARY KEY DEFAULT uuidv7(),
    product_id            UUID     NOT NULL REFERENCES ops.product_info(product_id) ON DELETE CASCADE,
    ingredient_id         UUID     NOT NULL REFERENCES ops.ingredient_catalog(ingredient_id) ON DELETE RESTRICT,
    sort_order            SMALLINT NOT NULL DEFAULT 0,   -- display order; 0 = most prominent
    created_date          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by           UUID     NOT NULL REFERENCES core.user_info(user_id),
    UNIQUE (product_id, ingredient_id)
);

CREATE INDEX IF NOT EXISTS idx_product_ingredient_product_id
    ON ops.product_ingredient (product_id);
CREATE INDEX IF NOT EXISTS idx_product_ingredient_ingredient_id
    ON ops.product_ingredient (ingredient_id);
-- The ingredient_id index supports: "find all products containing ingredient X"
-- which is the core query for the future recommendation engine
```

---

### Dialect aliases (Phase 7) — `ops.ingredient_alias`

Handles regional Spanish variants that share the same canonical concept:

```sql
CREATE TABLE IF NOT EXISTS ops.ingredient_alias (
    alias_id        UUID         PRIMARY KEY DEFAULT uuidv7(),
    ingredient_id   UUID         NOT NULL REFERENCES ops.ingredient_catalog(ingredient_id) ON DELETE CASCADE,
    alias           VARCHAR(150) NOT NULL,       -- lowercase, e.g. 'jitomate', 'aguacate', 'elote'
    region_code     VARCHAR(10)  NULL,           -- e.g. 'MX', 'PE' — NULL = universal
    UNIQUE (alias)
);
```

Common alias pairs:

| Canonical (`name_es`) | Alias | Region |
|----------------------|-------|--------|
| tomate | jitomate | MX |
| palta | aguacate | MX |
| choclo | elote | MX |
| ají | chile | MX |
| maracuyá | parchita | VE |

---

## 6. Backend Architecture — Search Gateway

### `GET /api/v1/ingredients/search?query=zanah&lang=es`

**Auth**: Supplier Admin or Internal

`lang` defaults to the market's primary language (`es` for AR/PE, `en` for US, `pt` for BR), derived server-side from the authenticated user's `market_id`. Explicit `lang` param overrides.

**Logic:**
```
1. Normalize query: lowercase, strip whitespace
   (unaccent() for DB search; keep original for display)

2. Search local catalog — all matching rows, verified and unverified:
   SELECT ic.*, ia.alias AS market_alias
   FROM ops.ingredient_catalog ic
   LEFT JOIN ops.ingredient_alias ia
     ON ia.ingredient_id = ic.ingredient_id
     AND ia.region_code = {user_market_country_code}
   WHERE ic.name ILIKE '%{query}%'
      OR ic.name_es ILIKE '%{query}%'
      OR ic.name_en ILIKE '%{query}%'
      OR ic.name_pt ILIKE '%{query}%'
      OR ia.alias ILIKE '%{query}%'
   ORDER BY ic.is_verified DESC, ic.enriched DESC, ic.name_display ASC
   LIMIT 10

3. Count verified results only (is_verified = TRUE).
   If verified count >= 5 → return immediately (no external call).
   Unverified entries are included in the response regardless — they
   are visible to suppliers but do not count toward the local threshold.

4. If verified count < 5:
   a. GET suggest.pl?tagtype=ingredients&term={query}&lc={lang}
   b. For each suggestion string:
      - GET taxonomy API to resolve off_taxonomy_id, name.es, name.en, name.pt
      - UPSERT into ingredient_catalog
        (ON CONFLICT ON name DO NOTHING; is_verified=FALSE, enriched=FALSE)
   c. Re-query local DB (now includes newly upserted rows)
   d. On OFF API error: log warning, return local results only

5. For each result, resolve display name:
   - If market_alias IS NOT NULL → use alias as name_display for this user
     (e.g. AR/PE supplier sees "Palta"; future MX supplier sees "Aguacate")
   - Otherwise → use name_es / name_en / name_pt per lang param

6. Return deduplicated list; verified + enriched entries ranked first
```

**Response:**
```json
[
  {
    "ingredient_id": "uuid",
    "name_display": "Zanahoria",
    "name_en": "Carrot",
    "off_taxonomy_id": "en:carrot",
    "image_url": "https://spoonacular.com/cdn/ingredients_100x100/sliced-carrot.jpg",
    "source": "off",
    "is_verified": true,
    "enriched": true
  },
  {
    "ingredient_id": "uuid",
    "name_display": "Zanahoria baby",
    "name_en": "Baby Carrot",
    "off_taxonomy_id": "en:baby-carrot",
    "image_url": null,
    "source": "off",
    "is_verified": false,
    "enriched": false
  }
]
```

`image_url` is `null` when `image_filename` is null — frontend renders a generic ingredient icon. Backend assembles the full URL from `SPOONACULAR_IMAGE_BASE_URL + image_filename` when available.

---

### `POST /api/v1/products/{product_id}/ingredients`

Replaces the product's ingredient list. Full replacement (delete existing rows, insert fresh) — no partial update needed at this stage.

**Request:**
```json
{ "ingredient_ids": ["uuid-1", "uuid-2", "uuid-3"] }
```

`sort_order` is assigned by array index. Response: the product's updated ingredient list.

---

### `GET /api/v1/products/{product_id}/ingredients`

Returns the ingredient list ordered by `sort_order`.

---

### `POST /api/v1/ingredients/custom`

Fallback when the supplier's ingredient is not found via search. Attempts an exact-match lookup first (prevents duplicate custom entries for things already in the catalog). Creates with `source='custom'`, `is_verified=false`, `enriched=false`.

**Request:**
```json
{ "name": "Rocoto", "lang": "es" }
```

---

## 7. Enrichment Cron — Spoonacular Bridge

Runs on a schedule (suggested: every 6 hours). Targets rows where `enriched=FALSE AND enrichment_skipped=FALSE`.

```
1. SELECT ingredient_id, name_en, off_taxonomy_id
   FROM ops.ingredient_catalog
   WHERE enriched = FALSE AND enrichment_skipped = FALSE
   LIMIT 50  -- process in small batches to stay within Spoonacular quota

2. For each row:
   a. If name_en is NULL: derive it from off_taxonomy_id
      (strip 'en:' prefix, replace hyphens with spaces → 'baby-carrot' → 'baby carrot')

   b. GET /food/ingredients/autocomplete?query={name_en}&number=5

   c. Score each result: fuzzy match between result.name and name_en
      - Accept if similarity >= 0.85 (e.g. 'carrots' ≈ 'carrot')
      - Skip if best match < 0.85 (e.g. query='coriander', top result='carrot cake')

   d. On confident match:
      UPDATE ingredient_catalog SET
        spoonacular_id = {id},
        image_filename = {image},
        enriched = TRUE,
        modified_date = NOW()
      WHERE ingredient_id = {id}

   e. On no confident match:
      UPDATE ingredient_catalog SET
        enriched = TRUE,
        enrichment_skipped = TRUE,
        modified_date = NOW()
      WHERE ingredient_id = {id}
      -- flagged for manual review in admin panel

3. Commit per row (not per batch) — partial progress survives if cron is interrupted
4. Log summary: {n} enriched, {k} skipped, {quota_used} Spoonacular points used
```

**Quota management**: Spoonacular autocomplete costs 1 point per call. At 50 rows/run, 4 runs/day = 200 points/day — within the free tier (150 points/day at current pricing). Adjust batch size via `SPOONACULAR_ENRICHMENT_BATCH_SIZE` env var.

---

## 8. Dietary Flags — Two-Phase Approach

### Phase 1 (MVP) — Supplier declares dietary restrictions

The existing `dietary` field on `ops.product_info` is converted from a free-text `VARCHAR(255)` to a structured multi-select. Suppliers explicitly select applicable flags from a dropdown when editing a product. This is the authoritative source — the supplier is legally responsible for what they declare.

Supported dietary flags (initial set):

| Value | Label (EN) | Label (ES) | Label (PT) |
|-------|-----------|-----------|-----------|
| `vegan` | Vegan | Vegano | Vegano |
| `vegetarian` | Vegetarian | Vegetariano | Vegetariano |
| `gluten_free` | Gluten-Free | Sin gluten | Sem glúten |
| `dairy_free` | Dairy-Free | Sin lácteos | Sem laticínios |
| `nut_free` | Nut-Free | Sin frutos secos | Sem nozes |
| `halal` | Halal | Halal | Halal |
| `kosher` | Kosher | Kosher | Kosher |

Stored as a PostgreSQL array or enum set on `product_info`. Supplier selects zero or more.

### Phase 2 (Post-enrichment) — Cron-derived dietary validation

After the Spoonacular enrichment cron has run, a separate validation pass uses each ingredient's `categoryPath` from Spoonacular to compute a *suggested* dietary profile for the product. This is compared against what the supplier declared.

**Behavior:**
- Derived flags **never override** the supplier's declaration
- Discrepancies (e.g. product marked vegan but an ingredient has `categoryPath: ["dairy"]`) are surfaced in the internal admin review queue as a flag for manual review
- This layer adds confidence to the supplier-declared data; it does not replace supplier responsibility

This phase runs only after enough catalog entries are enriched (Phase 5+) to make the validation meaningful.

---

## 10. Recommendation Engine Hook

The `product_ingredient` table is the data foundation for future recommendation logic. No additional schema migration is needed when that phase starts.

**Signal path:**
```
User likes plate → product_id
  → JOIN product_ingredient → ingredient_ids
  → Store as user_preference_signal(user_id, ingredient_id, weight)

Candidate scoring:
  → For a new plate, fetch its ingredient_ids
  → Score = sum of user's preference weight for each matching ingredient_id
  → Rank candidates by score → return as /recommendations
```

The `spoonacular_id` on each catalog row is the future hook for allergen filtering (e.g., "exclude dairy ingredient_ids") without requiring a separate lookup at recommendation time.

---

## 11. Progressive Independence from External APIs

| Stage | Local catalog size | Behavior |
|-------|-------------------|----------|
| **Cold** | 0 entries | All searches hit OFF; catalog grows entirely from supplier usage |
| **Warm** | ~300 entries | Most searches stay local; Spoonacular enrichment fills images |
| **Hot** | ~1 500+ entries | >90% of searches local; external calls are edge cases |
| **Independent** | Curated catalog complete | OFF/Spoonacular calls disabled; used only for discovery of new items |

**Kill switches:**
- `OFF_ENABLED=false` — disables real-time OFF calls; local-only search
- `SPOONACULAR_ENABLED=false` — disables enrichment cron
- `SPOONACULAR_ENRICHMENT_BATCH_SIZE` — controls quota consumption

---

## 12. Settings Required

| Setting | Description |
|---------|-------------|
| `SPOONACULAR_API_KEY` | Stored in GCP Secret Manager |
| `SPOONACULAR_ENABLED` | `true` / `false` kill switch for enrichment cron |
| `SPOONACULAR_IMAGE_BASE_URL` | `https://spoonacular.com/cdn/ingredients_100x100/` |
| `SPOONACULAR_ENRICHMENT_BATCH_SIZE` | Rows per cron run (default: `50`) |
| `SPOONACULAR_MATCH_THRESHOLD` | Fuzzy match minimum confidence (default: `0.85`) |
| `OFF_ENABLED` | `true` / `false` kill switch for OFF real-time calls |
| `OFF_LOCAL_MIN_VERIFIED_RESULTS` | Min **verified** local results before calling OFF (default: `5`) |

---

## 13. Legacy Migration

The existing `ingredients VARCHAR(255)` column on `ops.product_info` is **not dropped at launch**. Both fields coexist during migration:

- New products → use `product_ingredient` rows only; `ingredients` set to `NULL`
- Existing products → legacy `ingredients` text remains readable
- A migration cron parses legacy text, attempts fuzzy match against `ingredient_catalog`, creates `product_ingredient` rows with `is_verified=false` for internal review
- Legacy column dropped once >95% of active products are migrated

---

## 14. Implementation Phases

**MVP launches with OFF integration** — no backward compatibility with the legacy free-text field for new products.

### Schema-first principle

The DB schema and DTOs for **both Phase 1 and Phase 2 are built together in Phase 1**. Spoonacular-related columns (`spoonacular_id`, `image_filename`, `enriched`, `enrichment_skipped`, `off_wikidata_id`) are included from the start as nullable — they simply stay `NULL` until the enrichment cron runs in Phase 5. This avoids any future schema migration or DTO change when Spoonacular is wired up.

What Phase 1 establishes permanently:
- Full `ops.ingredient_catalog` schema including all Spoonacular and OFF fields
- Full `ops.product_ingredient` junction table
- Full `ops.ingredient_alias` table (empty until Phase 7 populates it)
- `InstitutionIngredientCatalogDTO` and response schemas covering all fields
- `product_info.dietary` as a structured multi-select (replaces `VARCHAR(255)`)

What Phase 5 adds (code only, no schema change):
- `app/services/cron/ingredient_enrichment.py` — the Spoonacular enrichment cron
- `app/services/payment_provider/spoonacular/` — Spoonacular gateway
- `SPOONACULAR_API_KEY` in GCP Secret Manager
- Cron schedule entry in Cloud Run / cron config

| Phase | Scope |
|-------|-------|
| **1 — Schema** | Add `ingredient_catalog` (with `name_es`, `name_en`, `name_pt`) and `product_ingredient` tables; convert `product_info.dietary` to structured multi-select enum |
| **2 — OFF search gateway** | `GET /ingredients/search?query=&lang=` with verified-local-first + OFF fallback + upsert; `POST /ingredients/custom` |
| **3 — Product ingredient endpoints** | `GET/POST /products/{id}/ingredients` |
| **4 — Supplier UI** | vianda-platform: multi-select tag component (react-select); debounce 300ms; generic food icon for unenriched entries; dialect alias resolved from supplier's market |
| **5 — Image enrichment cron** | Wikidata P18 (image) → Wikimedia Commons URL; `image_enriched` / `image_skipped` flags; CC licensed, permanent storage |
| **6 — B2C display** | vianda-app: ingredient chips with Wikidata thumbnails on plate detail; generic icon while `image_enriched=false` |
| **7 — USDA nutrition enrichment** | USDA FoodData Central cron: `usda_fdc_id`, `food_group`, `ingredient_nutrition` table; CC0, permanent storage |
| **8 — Dialect aliases** | `ingredient_alias` table; alias-aware search; alias display driven by `market_id` |
| **9 — Dedup admin tooling** | vianda-platform internal view: `image_skipped=true` and duplicate-taxonomy queues; merge workflow |
| **10 — Dietary validation cron** | USDA food group → dietary flag mapping; surface conflicts with supplier-declared flags in admin review queue |
| **10 — Legacy migration** | Cron to parse legacy `VARCHAR(255)` text → match against catalog → create `product_ingredient` rows for review |
| **11 — Deprecate legacy field** | Drop `ingredients VARCHAR(255)` from `product_info` and `product_history` once migration complete |
| **12 — Recommendation signals** | `user_preference_signal` table; ingredient overlap scoring; `/recommendations` endpoint |

---

## 15. Decisions Log

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Fuzzy match library: `rapidfuzz`** | Significantly faster than `difflib` at batch scale; same confidence scoring interface |
| 2 | **Canonical dialect: `name_es` (common LATAM term); market alias shown per `market_id`** | `name_es` stores the most widely-used LATAM term (e.g. "palta"). The `ingredient_alias` table holds per-country variants. The search gateway resolves the alias for the supplier's country server-side — the supplier always sees their regional term, never the canonical raw name |
| 3 | **`is_verified=false` entries appear in search results** — the OFF call threshold counts **verified** records only | Unverified entries (custom or recently upserted from OFF) are shown to suppliers so they are immediately usable. They do not satisfy the local threshold, so OFF is still called until 5 verified entries exist for that query. The verified queue is processed by Internal Operators via an admin panel view — not an engineering task |
| 4 | **Generic food icon for unenriched entries** | Per-category icon requires storing the OFF parent tag on every entry; not worth the complexity at launch. All unenriched entries use a single universal icon; Wikidata images appear once the enrichment cron runs |
| 5 | **No catalog seed at launch** | The catalog is populated entirely by supplier usage. OFF is the source from day one; the cold-start period is acceptable since every supplier search enriches the catalog for subsequent users |
| 6 | **`pt-BR` (Portuguese/Brazil) added as third language** | `name_pt` column on `ingredient_catalog`; `lang=pt` handled by search gateway; BR market derives locale `pt-BR` from `language=pt` + `market_id` |
| 7 | **No locale selector in UI — language picker only** | Users select from 3 languages (ES / EN / PT). Full locale (`es-AR`, `es-PE`, `pt-BR`, `en-US`) is derived server-side from `language + market_id`. Dialect alias display is market-driven, not user-preference-driven. See `LANGUAGE_AND_LOCALE_FOR_CLIENTS.md` |
| 8 | **Dietary flags: supplier declares, cron validates** | Supplier selects from a structured multi-select (vegan, vegetarian, gluten-free, etc.) — they hold responsibility. Post-enrichment cron derives dietary profile from USDA food group classification and flags conflicts for admin review; it never overrides supplier declaration |
| 9 | **MVP launches with OFF — no backward compatibility** | New products use `product_ingredient` rows from day one. Legacy `ingredients VARCHAR(255)` is migrated asynchronously and dropped in a later phase |
| 10 | **Schema-first: full schema for all enrichment phases built in Phase 1** | All enrichment columns (`image_url`, `image_source`, `usda_fdc_id`, `food_group`, `off_wikidata_id`, enrichment flags) plus `ingredient_nutrition` table are included from the start as nullable. Phase 5 (Wikidata images) and Phase 7 (USDA nutrition) add only code — cron services — with zero schema migration. DTOs and response schemas cover all fields from Phase 1 |

---

## References

- `app/db/schema.sql` — `ops.product_info` (current `ingredients VARCHAR(255)` field)
- `docs/guidelines/SCHEMA_CHANGE_GUIDE.md` — required sync order for schema additions
- `docs/api/b2b_client/API_CLIENT_PRODUCTS.md` — existing product CRUD endpoints
- `docs/api/b2c_client/PLATE_RECOMMENDATION_AND_FAVORITES_B2C.md` — existing favorites signal
- Open Food Facts taxonomy API: https://wiki.openfoodfacts.org/API
- Open Food Facts ODbL license: https://opendatacommons.org/licenses/odbl/
- Spoonacular autocomplete: https://spoonacular.com/food-api/docs#Autocomplete-Ingredient-Search
