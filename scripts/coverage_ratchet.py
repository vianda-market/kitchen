#!/usr/bin/env python3
"""Suggest per-file coverage threshold bumps.

Reads coverage.xml (produced by `pytest --cov=app --cov-report=xml`) and prints
files whose live coverage exceeds a configured floor by the headroom margin —
those are candidates for promoting into a stricter per-file gate.

Today the gate is `--cov-fail-under=0` plus diff-coverage on changed lines
(>=80%). This script is the manual ratchet that lets us migrate, file by file,
toward absolute per-file floors without a big-bang threshold edit.

Usage:
    pytest -m "not integration and not database and not slow" \\
        --ignore=app/tests/database --ignore=app/tests/routes \\
        --cov=app --cov-report=xml --cov-fail-under=0

    python scripts/coverage_ratchet.py                 # default floor=80, headroom=5
    python scripts/coverage_ratchet.py --floor 85      # only show >=90% files (floor+headroom)
    python scripts/coverage_ratchet.py --headroom 10   # require 10pt buffer
    python scripts/coverage_ratchet.py --include app/utils/

Pattern lifted from vianda-app's `scripts/coverage-ratchet.js` — purely
informational, never fails CI. Run periodically (e.g. start of a sprint) to
pick the next file to lock in.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_coverage(xml_path: Path) -> list[tuple[str, float, int]]:
    """Return list of (filename, line_rate_percent, lines_valid) for every file in coverage.xml."""
    if not xml_path.exists():
        sys.exit(f"coverage.xml not found at {xml_path}. Run pytest with --cov-report=xml first.")
    tree = ET.parse(xml_path)
    root = tree.getroot()
    rows: list[tuple[str, float, int]] = []
    for cls in root.iter("class"):
        filename = cls.get("filename") or ""
        try:
            rate = float(cls.get("line-rate") or 0.0) * 100
        except ValueError:
            continue
        try:
            lines_valid = int(cls.get("lines-valid") or 0)
        except ValueError:
            lines_valid = 0
        if not filename or lines_valid == 0:
            continue
        rows.append((filename, rate, lines_valid))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--xml", type=Path, default=Path("coverage.xml"), help="path to coverage.xml")
    parser.add_argument("--floor", type=float, default=80.0, help="current floor percent (default 80)")
    parser.add_argument("--headroom", type=float, default=5.0, help="required points above floor (default 5)")
    parser.add_argument("--include", type=str, default=None, help="only show files containing this substring")
    parser.add_argument("--min-lines", type=int, default=10, help="ignore files with fewer than N lines (default 10)")
    args = parser.parse_args()

    threshold = args.floor + args.headroom
    rows = parse_coverage(args.xml)
    if args.include:
        rows = [r for r in rows if args.include in r[0]]
    rows = [r for r in rows if r[2] >= args.min_lines]

    candidates = sorted([r for r in rows if r[1] >= threshold], key=lambda r: -r[1])

    if not candidates:
        print(f"No files at or above {threshold:.0f}% (floor {args.floor:.0f}% + headroom {args.headroom:.0f}%).")
        return 0

    print(f"Files >= {threshold:.0f}% coverage — candidates to lock in at floor {args.floor:.0f}%:")
    print(f"{'COVERAGE':>10}  {'LINES':>6}  FILE")
    for filename, rate, lines in candidates:
        print(f"{rate:>9.1f}%  {lines:>6}  {filename}")
    print(f"\n{len(candidates)} candidate(s). Bump per-file thresholds in pytest.ini or via diff-cover --exclude.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
