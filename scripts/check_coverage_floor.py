#!/usr/bin/env python3
"""Per-layer absolute coverage floor.

Complements diff-cover (changed-lines gate) with an absolute floor on the
layers that CLAUDE.md says are unit-testable (routes/services are tested via
Postman, not pytest).

Floors are deliberately below current measured weighted coverage — the goal
is to prevent regression, not to force new tests. Use scripts/coverage_ratchet.py
to suggest raises once real coverage has moved up.

Usage:
    pytest -m "not integration and not database and not slow" \\
        --ignore=app/tests/database --ignore=app/tests/routes \\
        --cov=app --cov-report=xml --cov-fail-under=0
    python scripts/check_coverage_floor.py
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Weighted line-coverage floor per layer. These are baselined against measured
# reality on 2026-04-19 with a ~5pt buffer below the then-current value:
#   layer      measured  floor
#   utils      49.5%     40
#   auth       34.5%     25
#   security   27.2%     20
#   gateways   55.9%     45
#   i18n       40.2%     30
# Raise these deliberately when coverage_ratchet.py shows headroom. Do NOT
# raise above current + 5 in a single jump — new tests land incrementally.
LAYER_FLOORS: dict[str, float] = {
    "utils": 40.0,
    "auth": 25.0,
    "security": 20.0,
    "gateways": 45.0,
    "i18n": 30.0,
}

# Files under the testable layers that we explicitly accept as untested today.
# Either the file is a thin wrapper around something mocked elsewhere (e.g. a
# gateway with real external SDK calls) or is covered end-to-end by Postman.
# Entries here are weighted out of the layer average. When adding, explain why.
EXCLUDED_FILES: frozenset[str] = frozenset(
    {
        # Untested ads gateways — exercised only in prod; no fakeable API.
        "gateways/ads/google/campaign_gateway.py",
        "gateways/ads/meta/campaign_gateway.py",
        # GCS wrapper — exercised via integration tests and Postman uploads.
        "utils/gcs.py",
        # DB pool bootstrap — exercised by every test indirectly, but its own
        # branches (retry, reconnect) fire only against a broken DB.
        "utils/db_pool.py",
    }
)

MIN_LINES_PER_FILE = 5


def load_layer_coverage(xml_path: Path) -> dict[str, float]:
    if not xml_path.exists():
        sys.exit(f"coverage.xml not found at {xml_path}. Run pytest with --cov-report=xml first.")
    tree = ET.parse(xml_path).getroot()
    per_layer: dict[str, list[tuple[float, int]]] = {layer: [] for layer in LAYER_FLOORS}
    for cls in tree.iter("class"):
        filename = cls.get("filename") or ""
        if filename in EXCLUDED_FILES:
            continue
        valid = len(cls.findall(".//line"))
        if valid < MIN_LINES_PER_FILE:
            continue
        try:
            rate = float(cls.get("line-rate") or 0.0) * 100
        except ValueError:
            continue
        for layer in per_layer:
            if filename.startswith(layer + "/"):
                per_layer[layer].append((rate, valid))
                break

    weighted: dict[str, float] = {}
    for layer, rows in per_layer.items():
        total = sum(v for _, v in rows)
        if total == 0:
            continue
        weighted[layer] = sum(r * v for r, v in rows) / total
    return weighted


def main() -> int:
    weighted = load_layer_coverage(Path("coverage.xml"))
    failures: list[str] = []
    print("Layer coverage floor check:")
    print(f"  {'LAYER':10s} {'MEASURED':>9s}  {'FLOOR':>6s}  RESULT")
    for layer, floor in LAYER_FLOORS.items():
        measured = weighted.get(layer)
        if measured is None:
            print(f"  {layer:10s} {'—':>9s}  {floor:5.1f}%  skipped (no matching files)")
            continue
        status = "OK" if measured >= floor else "FAIL"
        print(f"  {layer:10s} {measured:8.1f}%  {floor:5.1f}%  {status}")
        if measured < floor:
            failures.append(
                f"{layer} at {measured:.1f}% is below floor {floor:.1f}% (shortfall {floor - measured:.1f}pt)"
            )

    if failures:
        print("\nCoverage floor violations:")
        for f in failures:
            print(f"  - {f}")
        print(
            "\nEither add tests to raise coverage, or — if the drop is a deliberate "
            "restructure — lower the layer floor in scripts/check_coverage_floor.py with an explanation."
        )
        return 1
    print("\nAll layer floors respected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
