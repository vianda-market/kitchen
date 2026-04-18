#!/usr/bin/env python3
"""C.R.A.P. (Change Risk Anti-Patterns) analysis.

Joins radon cyclomatic complexity with pytest-cov line coverage to produce
a per-function CRAP score, which ranks functions by how complex *and*
under-tested they are — the best targets for a refactor investment.

    CRAP(f) = comp(f)^2 * (1 - cov(f)/100)^3 + comp(f)

Rule of thumb:
  CRAP <= 30 : acceptable
  CRAP >  30 : risky (complex AND under-tested)
  CRAP > 100 : priority refactor target

Usage:
    # 1. Generate coverage data (if you don't already have coverage.xml).
    pytest -m "not integration and not database and not slow" \\
        --ignore=app/tests/database --ignore=app/tests/routes \\
        --cov=app --cov-report=xml --cov-fail-under=0

    # 2. Rank functions.
    python scripts/analyze_crap.py            # top 20
    python scripts/analyze_crap.py --top 50   # top 50
    python scripts/analyze_crap.py --min 30   # only risky ones

This is an analysis tool, not a gate — it does not fail CI. Run it
periodically (e.g. start of a quarter) to pick refactor targets.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COVERAGE_XML_DEFAULT = REPO_ROOT / "coverage.xml"
ANALYZE_ROOTS = ("app",)
EXCLUDE_SUBSTRINGS = ("/tests/", "/__pycache__/")


@dataclass(frozen=True, slots=True)
class Function:
    file: str
    name: str
    qualname: str
    lineno: int
    endline: int
    complexity: int


@dataclass(frozen=True, slots=True)
class Score:
    func: Function
    coverage_pct: float
    crap: float


def _collect_complexity() -> list[Function]:
    # `-n A` overrides pyproject.toml's cc_min = "D" — we need all functions
    # so that low-complexity-but-untested ones still surface via their CRAP
    # score (a CC 3 function with 0% coverage still has a CRAP of ~12).
    raw = subprocess.check_output(["radon", "cc", "-j", "-s", "-n", "A", *ANALYZE_ROOTS], text=True)
    data = json.loads(raw)
    out: list[Function] = []
    for file, items in data.items():
        if any(s in file for s in EXCLUDE_SUBSTRINGS):
            continue
        if isinstance(items, dict) and items.get("error"):
            continue  # unparsable file
        for item in items:
            if item["type"] not in ("function", "method"):
                continue
            name = item["name"]
            qualname = f"{item.get('classname')}.{name}" if item.get("classname") else name
            out.append(
                Function(
                    file=file,
                    name=name,
                    qualname=qualname,
                    lineno=item["lineno"],
                    endline=item["endline"],
                    complexity=item["complexity"],
                )
            )
    return out


def _load_coverage(xml_path: Path) -> dict[str, tuple[set[int], set[int]]]:
    """Return {filename: (all_measured_lines, uncovered_lines)}.

    Cobertura encodes covered lines with hits>=1 and uncovered with hits=0.
    We need both the measured set (denominator for coverage %) and the
    uncovered subset (numerator of the miss rate).
    """
    tree = ET.parse(xml_path)
    uncovered: dict[str, set[int]] = {}
    all_lines: dict[str, set[int]] = {}
    for cls in tree.iterfind(".//class"):
        filename = cls.get("filename", "")
        # Cobertura paths are relative to the source root recorded in
        # <sources>. pytest-cov emits paths like "auth/abac.py" when run
        # with --cov=app; radon emits "app/auth/abac.py". Normalise.
        if filename and not filename.startswith("app/"):
            filename = f"app/{filename}"
        unc = uncovered.setdefault(filename, set())
        all_ = all_lines.setdefault(filename, set())
        for line in cls.iterfind(".//line"):
            num = int(line.get("number", "0"))
            hits = int(line.get("hits", "0"))
            all_.add(num)
            if hits == 0:
                unc.add(num)
    return {f: (all_lines.get(f, set()), uncovered.get(f, set())) for f in all_lines}


def _function_coverage(fn: Function, coverage: dict[str, tuple[set[int], set[int]]]) -> float | None:
    pair = coverage.get(fn.file)
    if pair is None:
        return None
    all_lines, uncovered = pair
    in_range = {n for n in all_lines if fn.lineno <= n <= fn.endline}
    if not in_range:
        return None
    missed = in_range & uncovered
    return 100.0 * (1 - len(missed) / len(in_range))


def _crap(comp: int, cov_pct: float) -> float:
    return comp * comp * (1 - cov_pct / 100) ** 3 + comp


def _score_all(functions: list[Function], coverage: dict[str, tuple[set[int], set[int]]]) -> list[Score]:
    scored: list[Score] = []
    for fn in functions:
        cov = _function_coverage(fn, coverage)
        if cov is None:
            # Treat unmeasured functions as 0% covered — they're more likely
            # to be untested than fully covered, so surfacing them is right.
            cov = 0.0
        scored.append(Score(fn, cov, _crap(fn.complexity, cov)))
    return scored


def _print_table(scores: list[Score]) -> None:
    if not scores:
        print("(no functions matched the filter)")
        return
    fmt = "{:>6}  {:>4}  {:>5}  {:<40}  {}"
    print(fmt.format("CRAP", "CC", "COV%", "FUNCTION", "LOCATION"))
    print(fmt.format("----", "--", "----", "--------", "--------"))
    for s in scores:
        loc = f"{s.func.file}:{s.func.lineno}"
        qn = s.func.qualname[:40]
        print(
            fmt.format(
                f"{s.crap:.0f}",
                s.func.complexity,
                f"{s.coverage_pct:.0f}",
                qn,
                loc,
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--coverage-xml",
        type=Path,
        default=COVERAGE_XML_DEFAULT,
        help=f"Path to Cobertura XML (default: {COVERAGE_XML_DEFAULT.name} at repo root)",
    )
    parser.add_argument("--top", type=int, default=20, help="Show the top N functions (default: 20)")
    parser.add_argument(
        "--min",
        type=float,
        default=0.0,
        help="Only show functions with CRAP score >= this (default: 0)",
    )
    args = parser.parse_args()

    if not args.coverage_xml.exists():
        print(
            f"Coverage file not found: {args.coverage_xml}\n"
            f"Generate it with:\n"
            f"  pytest -m 'not integration and not database and not slow' \\\n"
            f"      --ignore=app/tests/database --ignore=app/tests/routes \\\n"
            f"      --cov=app --cov-report=xml --cov-fail-under=0",
            file=sys.stderr,
        )
        return 1

    functions = _collect_complexity()
    coverage = _load_coverage(args.coverage_xml)
    scored = _score_all(functions, coverage)
    scored.sort(key=lambda s: s.crap, reverse=True)

    filtered = [s for s in scored if s.crap >= args.min][: args.top]
    _print_table(filtered)

    risky = sum(1 for s in scored if s.crap > 30)
    priority = sum(1 for s in scored if s.crap > 100)
    print(
        f"\nAnalyzed {len(scored)} functions. {risky} with CRAP > 30 (risky), {priority} with CRAP > 100 (priority).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
