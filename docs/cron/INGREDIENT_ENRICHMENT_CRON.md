# Ingredient Image Enrichment Cron — Wikidata (Phase 5)

**Status:** Implemented — kill switch `WIKIDATA_ENRICHMENT_ENABLED=false`
**Roadmap:** `docs/plans/STRUCTURED_INGREDIENTS_ROADMAP.md` §7
**Infra config key:** `wikidata_enrichment` (to be added to `infra-kitchen-gcp:cron_jobs`)

---

## 1. What This Cron Does

The OFF search gateway (Phase 1) populates `ops.ingredient_catalog` with multilingual entries (`name_es`, `name_en`, `name_pt`) but no images. Every new catalog row has `image_enriched=FALSE` and `image_url=NULL`.

This cron enriches those rows via the Wikidata API to fetch:
- `image_url` — full Wikimedia Commons image URL, constructed from the P18 (image) claim
- `image_source` — set to `'wikidata'` for provenance tracking

It runs in the background on a schedule. It is **never called from request handlers** — all OFF logic is real-time; all Wikidata enrichment logic is async.

---

## 2. Cron Schedule

| config_key | Schedule | Timezone | Description |
|------------|----------|----------|-------------|
| `wikidata_enrichment` | `0 */6 * * *` | UTC | Enrichment every 6 hours |

**Enabling in a stack** (in `Pulumi.{stack}.yaml`):
```yaml
infra-kitchen-gcp:cron_jobs: |
  {
    "wikidata_enrichment": true,
    ...
  }
```

---

## 3. Implementation

### File: `app/services/cron/wikidata_enrichment.py`

**Entry point:** `run_wikidata_enrichment()`

**Kill switch:** `WIKIDATA_ENRICHMENT_ENABLED=false` (default) — cron is a no-op until set to `true`.

**How it works:**

1. Fetches a batch of `ops.ingredient_catalog` rows where `image_enriched=FALSE` and `image_skipped=FALSE`, up to `ENRICHMENT_BATCH_SIZE` (default 50).
2. Collects Wikidata entity IDs for the batch and issues a single batch Wikidata API call (up to 50 IDs per request via `wbgetentities`).
3. Parses P18 (image) claims from each entity's response.
4. Constructs Wikimedia Commons URLs using the pattern:
   ```
   https://commons.wikimedia.org/wiki/Special:FilePath/{filename}
   ```
5. Stores the URL as `image_url` with `image_source='wikidata'` and sets `image_enriched=TRUE`.
6. Rows with no P18 claim are marked `image_skipped=TRUE` for admin review.
7. Uses **per-row commit** for crash resilience — if the process dies mid-batch, already-committed rows are not reprocessed.

No API key is required — Wikidata is a free, open API.

---

## 4. Settings

The following settings control the enrichment cron. No API key is needed.

In `app/config/settings.py`:
```python
WIKIDATA_ENRICHMENT_ENABLED: bool = False
ENRICHMENT_BATCH_SIZE: int = 50
```

In `.env.example`:
```
WIKIDATA_ENRICHMENT_ENABLED=false
ENRICHMENT_BATCH_SIZE=50
```

---

## 5. Dependency addition

`rapidfuzz` must be in `requirements.txt` (already present) — needed for future Spoonacular partnership fuzzy matching if that integration is activated:

```
rapidfuzz>=3.0.0
```

---

## 6. How to trigger manually

```bash
# From the project root, with venv active:
python3 -c "
from app.services.cron.wikidata_enrichment import run_wikidata_enrichment
import json
print(json.dumps(run_wikidata_enrichment(), indent=2, default=str))
"
```

Expected output (cold catalog, first run):
```json
{
  "status": "ok",
  "enriched": 12,
  "skipped": 3,
  "errors": 0
}
```

---

## 7. Cheatsheet entry

Add to `docs/cron/CRON_JOBS_CHEATSHEET.md`:

```markdown
## Wikidata ingredient enrichment

| | |
|--|--|
| **Callable** | `wikidata_enrichment.run_wikidata_enrichment()` |
| **Module** | `app.services.cron.wikidata_enrichment` |
| **Purpose** | Enrich `ops.ingredient_catalog` rows (image_enriched=FALSE) via Wikidata P18 claims. Sets `image_url`, `image_source='wikidata'`, `image_enriched=TRUE`. Rows with no P18 claim are marked `image_skipped=TRUE` for admin review. |
| **Kill switch** | `WIKIDATA_ENRICHMENT_ENABLED=false` — cron is a no-op until set to `true` |
| **Quota** | Free — Wikidata has no usage limits or API key requirements. |
| **Scheduling** | Every 6 hours (`0 */6 * * *` UTC). Infra config key: `wikidata_enrichment`. |
```

---

## 8. Infra request for `infra-kitchen-gcp`

The following is a request to the infra team. File the infra feedback at
`/Users/cdeachaval/learn/vianda/infra-kitchen-gcp/docs/infrastructure/feedback_for_infra.md`
or communicate directly to the infra agent.

**What infra needs to do:**

1. **Cloud Run Job** — add a new job named `wikidata-enrichment` with:
   - Command: `python3 -c "from app.services.cron.wikidata_enrichment import run_wikidata_enrichment; run_wikidata_enrichment()"`
   - Environment variable: `WIKIDATA_ENRICHMENT_ENABLED=true` (the cron is a no-op without this)
   - No Secret Manager bindings needed — Wikidata requires no API key

2. **Cloud Scheduler** — schedule the job:
   - Schedule: `0 */6 * * *` (UTC)
   - Config key: `wikidata_enrichment`
   - Default: `false` in all stacks until tested

3. **Stack activation** — when ready in a stack, add `"wikidata_enrichment": true` to that stack's `infra-kitchen-gcp:cron_jobs` config.

---

## 9. Activation checklist

- [ ] `app/services/cron/wikidata_enrichment.py` created with `run_wikidata_enrichment()`
- [ ] `WIKIDATA_ENRICHMENT_ENABLED` and `ENRICHMENT_BATCH_SIZE` in `app/config/settings.py`
- [ ] `rapidfuzz` in `requirements.txt`
- [ ] `.env.example` updated with Wikidata enrichment keys
- [ ] Manual test run passes (`status: ok`, at least some rows enriched)
- [ ] `infra-kitchen-gcp` Cloud Run Job `wikidata-enrichment` provisioned
- [ ] `wikidata_enrichment` config key added to target stack and set to `true`
- [ ] `WIKIDATA_ENRICHMENT_ENABLED=true` set in that stack's environment
- [ ] `docs/cron/CRON_JOBS_CHEATSHEET.md` updated

---

## 10. Admin review queue (Phase 8 prerequisite)

Rows with `image_skipped=TRUE` need manual review. Until a dedicated admin panel exists (Phase 8), query directly:

```sql
-- Rows that could not be matched to a Wikidata image
SELECT ingredient_id, name, name_display, name_en, off_taxonomy_id
FROM ops.ingredient_catalog
WHERE image_skipped = TRUE
ORDER BY created_date DESC;

-- Summary count
SELECT
    COUNT(*) FILTER (WHERE image_enriched = FALSE AND image_skipped = FALSE) AS pending,
    COUNT(*) FILTER (WHERE image_enriched = TRUE  AND image_skipped = FALSE) AS enriched,
    COUNT(*) FILTER (WHERE image_skipped = TRUE)                             AS needs_review
FROM ops.ingredient_catalog;
```

For manual override (e.g. Internal operator finds the correct Wikimedia Commons image):
```sql
UPDATE ops.ingredient_catalog
SET image_url       = 'https://commons.wikimedia.org/wiki/Special:FilePath/<filename>',
    image_source    = 'manual',
    image_enriched  = TRUE,
    image_skipped   = FALSE,
    modified_date   = NOW()
WHERE ingredient_id = '<uuid>';
```

---

## 11. Future: USDA Nutrition Enrichment (Phase 7)

A future cron will enrich ingredients with nutrition data from the USDA FoodData Central API.

**Key details:**
- **API:** USDA FoodData Central — free, no API key required, CC0 license
- **Schema is ready:** `usda_fdc_id` and `food_group` columns already exist on `ops.ingredient_catalog`, and the `ops.ingredient_nutrition` table is provisioned
- **Kill switch:** `USDA_ENRICHMENT_ENABLED`
- **User stories covered:**
  - **User story 3** — dietary audit via `food_group` classification (e.g. "Dairy", "Legumes", "Vegetables")
  - **User story 4** — nutrient data (calories, protein, fat, carbs, fiber, etc.) stored in `ops.ingredient_nutrition`

Implementation will follow the same per-row-commit, batch-fetch, kill-switch pattern as the Wikidata enrichment cron.

---

## 12. Future: Spoonacular Partnership

Spoonacular data **cannot be stored** under its current Terms of Service (ToS prohibits caching nutritional data permanently).

**If a partnership with written permission is secured:**
- Spoonacular images would be served **transiently** (not stored in `image_url`), displayed via the Spoonacular CDN URL at render time
- Spoonacular nutrition data would be written to `ops.ingredient_nutrition` with `source='spoonacular'`
- `SPOONACULAR_ENABLED` and `SPOONACULAR_API_KEY` settings already exist in `app/config/settings.py` for this purpose
- `rapidfuzz>=3.0.0` is already in `requirements.txt` for fuzzy name matching against Spoonacular autocomplete results

Until a written partnership agreement is in place, Spoonacular integration remains disabled.

---

## References

- `docs/plans/STRUCTURED_INGREDIENTS_ROADMAP.md` §7 — enrichment algorithm design
- `docs/plans/STRUCTURED_INGREDIENTS_ROADMAP.md` §12 — settings reference
- `app/services/cron/wikidata_enrichment.py` — the implementation file
- `app/services/open_food_facts_service.py` — Phase 1 OFF gateway (compare pattern)
- `app/services/cron/currency_refresh.py` — reference cron pattern in this codebase
- `docs/cron/CRON_JOBS_CHEATSHEET.md` — full cron inventory
- `/Users/cdeachaval/learn/vianda/infra-kitchen-gcp/docs/infrastructure/CRON_JOBS_CHEATSHEET.md` — Cloud Scheduler job inventory
- Wikidata API docs: https://www.wikidata.org/wiki/Wikidata:Data_access
- Wikimedia Commons file path: https://commons.wikimedia.org/wiki/Special:FilePath
- USDA FoodData Central: https://fdc.nal.usda.gov/api-guide
