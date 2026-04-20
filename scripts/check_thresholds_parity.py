#!/usr/bin/env python3
"""Assert every threshold in docs/testing/thresholds.lock.yaml matches its
configured location (CI workflow, script, pyproject.toml, etc.) AND appears
verbatim in docs/testing/THRESHOLDS.md.

Each numeric gate lives in three places: the config file that actually
enforces it, the machine-readable lock (this script reads it), and the
human-readable table. Without binding them mechanically, the doc rots
into a lie. This check fails CI if any one of them disagrees.

Pattern lifted from infra-kitchen-gcp.

Usage: python scripts/check_thresholds_parity.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCK_PATH = REPO_ROOT / "docs" / "testing" / "thresholds.lock.yaml"
DOC_PATH = REPO_ROOT / "docs" / "testing" / "THRESHOLDS.md"


def main() -> int:
    if not LOCK_PATH.exists():
        print(f"FAIL: {LOCK_PATH.relative_to(REPO_ROOT)} not found.")
        return 2
    if not DOC_PATH.exists():
        print(f"FAIL: {DOC_PATH.relative_to(REPO_ROOT)} not found.")
        return 2

    manifest = yaml.safe_load(LOCK_PATH.read_text())
    doc_text = DOC_PATH.read_text()

    failures: list[str] = []
    for gate in manifest.get("gates", []):
        name = gate["name"]
        expected = str(gate["value"])

        if expected not in doc_text:
            failures.append(f"{name}: value {expected} not present in THRESHOLDS.md")

        for src in gate.get("sources", []):
            src_path = REPO_ROOT / src["file"]
            if not src_path.exists():
                failures.append(f"{name}: source file {src['file']} not found")
                continue
            text = src_path.read_text()
            matches = re.findall(src["pattern"], text, flags=re.MULTILINE)
            if not matches:
                failures.append(f"{name}: pattern {src['pattern']!r} not found in {src['file']}")
                continue
            for actual in matches:
                if actual != expected:
                    failures.append(f"{name}: {src['file']} captured {actual!r}, lock says {expected!r}")

    if failures:
        print("Threshold parity check FAILED:")
        for f in failures:
            print(f"  {f}")
        print()
        print("Fix: update docs/testing/thresholds.lock.yaml AND the source file(s) AND")
        print("docs/testing/THRESHOLDS.md so all three agree.")
        return 1

    n = len(manifest.get("gates", []))
    print(f"Threshold parity check passed ({n} gates checked across docs + sources).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
