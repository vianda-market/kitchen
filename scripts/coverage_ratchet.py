#!/usr/bin/env python3
"""Coverage ratchet suggester.

Reads coverage.xml (produced by `pytest --cov=app --cov-report=xml`) and either:

  * prints files with headroom above a configured floor (default mode — useful
    to scan for promotion candidates), or
  * with `--suggest FLOOR`, names the lowest-coverage file AT-OR-ABOVE that
    floor and proposes the next ratchet target (canonical pattern from
    infra-kitchen-gcp — the answer is always grounded in current numbers).

Usage:
    pytest -m "not integration and not database and not slow" \\
        --ignore=app/tests/database --ignore=app/tests/routes \\
        --cov=app --cov-report=xml --cov-fail-under=0

    python scripts/coverage_ratchet.py                          # default scan
    python scripts/coverage_ratchet.py --suggest 80             # next ratchet above 80
    python scripts/coverage_ratchet.py --floor 85 --headroom 5  # custom scan
    python scripts/coverage_ratchet.py --include utils/         # filter by substring

Informational only — never fails CI. Run before proposing a threshold bump.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_coverage(xml_path: Path) -> list[tuple[str, float, int]]:
    """Return [(filename, line_rate_percent, lines_valid), ...]."""
    if not xml_path.exists():
        sys.exit(f"coverage.xml not found at {xml_path}. Run pytest with --cov-report=xml first.")
    tree = ET.parse(xml_path)
    root = tree.getroot()
    rows: list[tuple[str, float, int]] = []
    for cls in root.iter("class"):
        filename = cls.get("filename") or ""
        if not filename:
            continue
        try:
            rate = float(cls.get("line-rate") or 0.0) * 100
        except ValueError:
            continue
        # Kitchen's coverage.xml omits the `lines-valid` attribute, so count
        # <line> children directly. (The previous version read the missing
        # attribute and silently filtered out every file.)
        lines_valid = len(cls.findall(".//line"))
        if lines_valid == 0:
            continue
        rows.append((filename, rate, lines_valid))
    return rows


def suggest_next(rows: list[tuple[str, float, int]], floor: float) -> int:
    """Print the next ratchet target: lowest file at-or-above `floor`.

    The next safe floor is floor(lowest_above - 1) — leaves a 1pt buffer so
    one bad PR can't immediately put the binding file below the new floor.
    """
    above = sorted([r for r in rows if r[1] >= floor], key=lambda r: r[1])
    below = sorted([r for r in rows if r[1] < floor], key=lambda r: -r[1])

    print(f"Ratchet suggestion (current floor: {floor:.0f}%):")
    if not above:
        print(f"  No files at or above {floor:.0f}% — floor cannot be raised.")
        return 0

    binding = above[0]
    suggested = int(binding[1]) - 1  # leave 1pt buffer
    if suggested <= floor:
        print(f"  Binding file already at {binding[1]:.1f}% — no headroom to raise floor past {floor:.0f}%.")
        print(f"  Binding: {binding[0]} ({binding[1]:.1f}%, {binding[2]} lines)")
        return 0

    print(f"  Suggested next floor: {suggested}% (binding file is 1pt above)")
    print(f"  Binding file: {binding[0]} — {binding[1]:.1f}% ({binding[2]} lines)")

    print("\nFive next-lowest files above floor (raise lifts these too):")
    for fn, rate, lines in above[:5]:
        print(f"  {rate:5.1f}%  {lines:>5}  {fn}")

    if below:
        print(f"\nFiles currently BELOW {floor:.0f}% (untouched by a raise — need tests):")
        for fn, rate, lines in below[:5]:
            print(f"  {rate:5.1f}%  {lines:>5}  {fn}")
    return 0


def scan(rows: list[tuple[str, float, int]], floor: float, headroom: float) -> int:
    threshold = floor + headroom
    candidates = sorted([r for r in rows if r[1] >= threshold], key=lambda r: -r[1])
    if not candidates:
        print(f"No files at or above {threshold:.0f}% (floor {floor:.0f}% + headroom {headroom:.0f}%).")
        return 0

    print(f"Files >= {threshold:.0f}% coverage — candidates to lock in at floor {floor:.0f}%:")
    print(f"{'COVERAGE':>10}  {'LINES':>6}  FILE")
    for filename, rate, lines in candidates:
        print(f"{rate:>9.1f}%  {lines:>6}  {filename}")
    print(f"\n{len(candidates)} candidate(s). Use --suggest {floor:.0f} to pick the next bump.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--xml", type=Path, default=Path("coverage.xml"), help="path to coverage.xml")
    parser.add_argument(
        "--suggest",
        type=float,
        default=None,
        help="name the lowest file at-or-above this floor; propose the next ratchet",
    )
    parser.add_argument("--floor", type=float, default=80.0, help="scan mode: current floor (default 80)")
    parser.add_argument(
        "--headroom", type=float, default=5.0, help="scan mode: required points above floor (default 5)"
    )
    parser.add_argument("--include", type=str, default=None, help="only show files containing this substring")
    parser.add_argument("--min-lines", type=int, default=10, help="ignore files with fewer than N lines (default 10)")
    args = parser.parse_args()

    rows = parse_coverage(args.xml)
    if args.include:
        rows = [r for r in rows if args.include in r[0]]
    rows = [r for r in rows if r[2] >= args.min_lines]

    if args.suggest is not None:
        return suggest_next(rows, args.suggest)
    return scan(rows, args.floor, args.headroom)


if __name__ == "__main__":
    sys.exit(main())
