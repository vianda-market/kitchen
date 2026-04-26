"""AST scan: detect bare-string ``detail=`` in 4xx HTTPException raises.

**Enforcing mode** — any ``raise HTTPException(status_code=<4xx>, detail=<str>)``
in the scanned scope fails this test.  5xx raises remain exempt (they are
server-error signals for ops logging, not user-facing messages).

K-last (this PR) flips from report mode to enforcing after the K6..KN sweep
completes.  All 4xx bare-string raises have been migrated; only 5xx bare-string
raises remain (52 sites) and those are intentionally exempt.

Scan scope:
- All ``*.py`` files under ``app/``.
- Excluded: ``app/tests/``, ``app/i18n/``, ``app/utils/error_messages.py``,
  all paths under ``app/schemas/`` (Pydantic schema validators — K5 scope).

Detection pattern:
  ``raise HTTPException(status_code=<4xx>, detail=<str_literal_or_fstring> ...)``

Allowed patterns (not flagged):
  ``raise envelope_exception(...)``
  ``raise HTTPException(... detail={...dict...} ...)``
  ``raise HTTPException(... detail=build_envelope(...) ...)``
  ``raise HTTPException(status_code=5xx, ...)``   ← 5xx always exempt
"""

import ast
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Directories/files excluded from the scan
# ---------------------------------------------------------------------------
_APP_ROOT = Path(__file__).resolve().parent.parent.parent  # kitchen/app/
_EXCLUDED_DIRS = {"tests", "i18n", "schemas"}
_EXCLUDED_FILES = {
    str(_APP_ROOT / "utils" / "error_messages.py"),
}

# 5xx status codes are exempt — they are server-error signals for ops, not
# user-facing messages; leave them as bare strings per Decision 3.
_5XX_RANGE = range(500, 600)


def _is_bare_string_detail(kw: ast.keyword) -> bool:
    """Return True if the keyword is detail=<str literal or f-string>."""
    if kw.arg != "detail":
        return False
    val = kw.value
    is_bare = isinstance(val, ast.Constant) and isinstance(val.value, str)
    is_fstring = isinstance(val, ast.JoinedStr)
    return is_bare or is_fstring


def _extract_status_code(call: ast.Call) -> int | None:
    """
    Return the integer status_code from a Call node if it is a plain integer
    constant, or None if it cannot be determined statically.
    """
    for kw in call.keywords:
        if kw.arg == "status_code":
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, int):
                return kw.value.value
    return None


def _callable_name(call: ast.Call) -> str:
    """Return the callable name for a Call node, or empty string."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _scan_file(fpath: str) -> list[tuple[str, int]]:
    """Scan a single file for 4xx bare-string HTTPException detail raises."""
    violations: list[tuple[str, int]] = []
    try:
        with open(fpath, encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src, filename=fpath)
    except (OSError, SyntaxError):
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise):
            continue
        exc = node.exc
        if exc is None or not isinstance(exc, ast.Call):
            continue
        if _callable_name(exc) != "HTTPException":
            continue

        # Exempt 5xx raises — leave bare per Decision 3 (server error signals).
        status_code = _extract_status_code(exc)
        if status_code is not None and status_code in _5XX_RANGE:
            continue

        for kw in exc.keywords:
            if _is_bare_string_detail(kw):
                violations.append((fpath, node.lineno))
    return violations


def _collect_violations() -> list[tuple[str, int]]:
    """Return list of (filepath, lineno) for 4xx bare-string HTTPException raises."""
    violations: list[tuple[str, int]] = []

    for dirpath, dirnames, filenames in os.walk(_APP_ROOT):
        # Prune excluded directories in-place so os.walk skips their subtrees.
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIRS]

        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(dirpath, fname)
            if fpath in _EXCLUDED_FILES:
                continue
            violations.extend(_scan_file(fpath))

    return sorted(violations)


def test_no_bare_string_raises(capfd) -> None:
    """All 4xx HTTPException raises must use envelope_exception — enforcing mode (K-last).

    5xx raises are exempt (server-error signals; left as bare strings per Decision 3).
    The K6..KN sweep migrated all 4xx sites; this test now gates future regressions.
    """
    violations = _collect_violations()

    if violations:
        lines = [f"  {path}:{lineno}" for path, lineno in violations]
        report = (
            f"\nFAIL: {len(violations)} bare-string 4xx HTTPException detail raise(s) found.\n"
            "Use envelope_exception(ErrorCode.X, status=4xx, locale=locale, **params) instead.\n" + "\n".join(lines)
        )
        print(report, file=sys.stderr)

    # Enforcing mode (K-last): any 4xx violation fails CI.
    assert not violations, f"{len(violations)} bare-string 4xx HTTPException raise(s) — see stderr"
