# Plates filter `plate_date_from/to` — pickup_date proxy

**Status:** Open follow-up. Not blocking any current work.

Plates filter `plate_date_from/to` currently maps to `plate_info.created_date` as a proxy.
The arguably-correct column is `plate_selection.pickup_date`, which would require a JOIN.
Re-evaluate when a real product question arises about the difference (e.g. orders span
midnight, suppliers see "wrong" date in their dashboard, etc.). Not blocking any current work.

## Context

Registry entry (`app/config/filter_registry.py`):

```python
"plate_date_from": {"col": "created_date", "alias": "p", "op": "gte", "cast": "date"},
"plate_date_to":   {"col": "created_date", "alias": "p", "op": "lte", "cast": "date"},
```

The `created_date` column on `ops.plate_info` is the plate's creation date (when the plate
was added to the system), not the pickup date. For most analytical uses (e.g. "show plates
created this month") this is fine.

The correct semantics for "show plates available on date X" would be
`plate_selection_info.pickup_date`, but this table is joined to `plate_info` via a separate
enriched query and adding the JOIN just for this filter would inflate row count (1:N) and
require `DISTINCT` deduplication.

## Decision (2026-04-24)

Retain `created_date` proxy for v1 (Pass 1 scope). The frontend filter UI is date-range-bound;
`created_date` is a monotonically increasing proxy that is "close enough" for the CRUD table
use case (filtering by rough date range to find plates added around a given time).

Re-evaluate if:
- Suppliers report seeing unexpected results when filtering by date in their dashboard.
- A product question explicitly distinguishes "plate creation date" from "pickup date".
- The `plate_selection_info` JOIN is added to the plates enriched query for other reasons (at
  that point, swapping the filter column is a single-line registry edit).
