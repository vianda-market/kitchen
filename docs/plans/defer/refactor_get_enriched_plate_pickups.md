# Follow-up: refactor `get_enriched_plate_pickups`

**Status:** Deferred — landed in `.complexity-baseline.txt` to unblock kitchen #85.

## Why it's on the baseline

Pass 1 of the cross-repo filter rollout (PR #85) added pagination + COUNT support to `get_enriched_plate_pickups` in `app/services/entity_service.py`. The new branches (page/page_size None-guards, joins-fragment extraction, COUNT-vs-list mode dispatch) pushed the function's cyclomatic complexity from ≤25 (clean) to **33** (grade E).

Rather than couple a refactor of an existing service function to the Pass 1 contract change, the function was added to `.complexity-baseline.txt` — same disposition as the other three functions already there (`get_restaurants_by_city_route`, `list_enriched_restaurants`, `create_lead_interest`).

## What to do when revisiting

The natural decomposition mirrors what was done in Pass 1 itself but only partially:

1. **Extract the COUNT path into a sibling function** (`count_enriched_plate_pickups`) that shares the joins-fragment with the list path. The COUNT-vs-list branch in the current function is responsible for ~5 of the new complexity points.
2. **Pull pagination param normalization into a small helper** (`_normalize_page_params(page, page_size) -> tuple[int, int]`) that asserts non-None and clamps. This eliminates the `page is not None and page_size is not None` guards that mypy needed.
3. **Consider whether the joins fragment** (extracted as a string in Pass 1) should be promoted to a SQLAlchemy construct or stay as raw SQL. If it stays raw, no further action; if it becomes a Select, the function naturally splits along that boundary.

After the refactor:
- Local: `bash scripts/check_complexity.sh` should pass without the baseline entry.
- Remove `app/services/entity_service.py:get_enriched_plate_pickups` from `.complexity-baseline.txt`.
- Update `mypy-baseline.txt` if the type-narrowing helper changes any assertion shapes.

## Not blocking

No behavioral problem with the current implementation; the function tests pass and the contract is correct. This is a code-health follow-up, not a bug.
