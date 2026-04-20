#!/usr/bin/env python3
"""Ratchet suggestion tool — per-file and per-layer.

Reads coverage.xml (pytest --cov-report=xml) and answers one of two
questions grounded in current measurements:

- Per-file: given a candidate floor, what file is the binding constraint
  and what's the next safe floor? Invoke with `--file-floor FLOOR`.
- Per-layer: what are the current weighted coverage and a safe next floor
  for each testable layer (utils, auth, security, gateways, i18n)?
  Invoke with `--layer`.

Pattern from infra-kitchen-gcp — the answer always comes from the current
report, never from vibes. Informational; never fails CI.

Usage:
    pytest -m "not integration and not database and not slow" \\
        --ignore=app/tests/database --ignore=app/tests/routes \\
        --cov=app --cov-report=xml --cov-fail-under=0

    python scripts/suggest_ratchets.py --file-floor 40 --include utils/
    python scripts/suggest_ratchets.py --layer
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Must mirror LAYER_FLOORS in scripts/check_coverage_floor.py.
LAYER_FLOORS: dict[str, float] = {
    "utils": 40.0,
    "auth": 25.0,
    "security": 20.0,
    "gateways": 45.0,
    "i18n": 30.0,
}

# Mirrors EXCLUDED_FILES in scripts/check_coverage_floor.py — files
# legitimately untested today (exercised only in prod / via Postman).
EXCLUDED_FILES: frozenset[str] = frozenset(
    {
        "gateways/ads/google/campaign_gateway.py",
        "gateways/ads/meta/campaign_gateway.py",
        "utils/gcs.py",
        "utils/db_pool.py",
    }
)

# (filename, line-rate percent, line count)
Row = tuple[str, float, int]


def parse_coverage(xml_path: Path) -> list[Row]:
    """Return per-file rows parsed from coverage.xml."""
    if not xml_path.exists():
        sys.exit(f"coverage.xml not found at {xml_path}. Run pytest with --cov-report=xml first.")
    rows: list[Row] = []
    for cls in ET.parse(xml_path).getroot().iter("class"):
        filename = cls.get("filename") or ""
        if not filename:
            continue
        # Kitchen's coverage.xml omits `lines-valid`; count <line> children.
        lines = len(cls.findall(".//line"))
        if lines == 0:
            continue
        try:
            rate = float(cls.get("line-rate") or 0.0) * 100
        except ValueError:
            continue
        rows.append((filename, rate, lines))
    return rows


def suggest_file(rows: list[Row], floor: float) -> int:
    """Name the lowest-coverage file at-or-above `floor` and propose the next floor."""
    above = sorted([r for r in rows if r[1] >= floor], key=lambda r: r[1])
    below = sorted([r for r in rows if r[1] < floor], key=lambda r: -r[1])
    out = [f"File-ratchet suggestion (current floor: {floor:.0f}%):"]
    if not above:
        out.append(f"  No files >= {floor:.0f}%. Floor cannot be raised.")
        print("\n".join(out))
        return 0
    binding = above[0]
    # Leave a 1pt buffer so a small regression can't immediately breach.
    suggested = int(binding[1]) - 1
    out.append(f"  Binding file: {binding[0]} — {binding[1]:.1f}% ({binding[2]} lines)")
    out.append(f"  Suggested next floor: {max(suggested, int(floor))}%")
    out.append("\n  Next five above (raise lifts these too):")
    out.extend(f"    {r[1]:5.1f}%  {r[2]:>5}  {r[0]}" for r in above[:5])
    if below:
        out.append(f"\n  Below {floor:.0f}% (need tests, not a higher floor):")
        out.extend(f"    {r[1]:5.1f}%  {r[2]:>5}  {r[0]}" for r in below[:5])
    print("\n".join(out))
    return 0


def suggest_layers(rows: list[Row]) -> int:
    """Print per-layer weighted coverage and a safe next floor."""
    per_layer: dict[str, list[tuple[float, int]]] = {layer: [] for layer in LAYER_FLOORS}
    for filename, rate, lines in rows:
        if filename in EXCLUDED_FILES or lines < 5:
            continue
        for layer in per_layer:
            if filename.startswith(layer + "/"):
                per_layer[layer].append((rate, lines))
                break

    out = ["Per-layer ratchet suggestions:", f"  {'LAYER':10s} {'MEASURED':>9s} {'FLOOR':>7s} {'NEXT':>6s}"]
    for layer, floor in LAYER_FLOORS.items():
        layer_rows = per_layer[layer]
        if not layer_rows:
            continue
        total = sum(v for _, v in layer_rows)
        weighted = sum(r * v for r, v in layer_rows) / total
        # Halfway bump: leaves headroom so one regression can't breach the new floor.
        safe_next = int(floor + (weighted - floor) / 2) if weighted > floor else int(floor)
        tag = " (at/below floor — add tests)" if weighted <= floor else ""
        out.append(f"  {layer:10s} {weighted:8.1f}% {floor:6.1f}% {safe_next:5d}%{tag}")
    out.append(
        "\nTo bump: edit LAYER_FLOORS in scripts/check_coverage_floor.py, update the matching row "
        "in docs/testing/THRESHOLDS.md and docs/testing/thresholds.lock.yaml."
    )
    print("\n".join(out))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--xml", type=Path, default=Path("coverage.xml"))
    p.add_argument("--file-floor", type=float, default=None, help="per-file suggestion at this floor")
    p.add_argument("--layer", action="store_true", help="per-layer suggestions (all testable layers)")
    p.add_argument("--include", type=str, default=None, help="filter files by substring (file mode)")
    p.add_argument("--min-lines", type=int, default=10, help="ignore small files (default 10)")
    args = p.parse_args()
    if args.file_floor is None and not args.layer:
        p.error("pick one of --file-floor FLOOR or --layer")

    rows = parse_coverage(args.xml)
    if args.include:
        rows = [r for r in rows if args.include in r[0]]
    if args.file_floor is not None:
        rows = [r for r in rows if r[2] >= args.min_lines]
        return suggest_file(rows, args.file_floor)
    return suggest_layers(rows)


if __name__ == "__main__":
    sys.exit(main())
