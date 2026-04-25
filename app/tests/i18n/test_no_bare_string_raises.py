"""AST scan: detect bare-string ``detail=`` in HTTPException raises.

**Report mode** — this test never fails CI. It collects all violations,
emits a summary to stderr, then asserts True unconditionally.

Flip to enforcing in K-last (the sweep PR that removes the legacy-wrapping
handler branch and sets ``assert not violations``).

Initial count at K3: 801 bare-string raises (established on first run 2026-04-24).
Every K6..KN sweep PR should shrink this number toward zero.

Scan scope:
- All ``*.py`` files under ``app/``.
- Excluded: ``app/tests/``, ``app/i18n/``, ``app/utils/error_messages.py``,
  all paths under ``app/schemas/`` (Pydantic schema validators — K5 scope).

Detection pattern:
  ``raise HTTPException(... detail=<str_literal_or_fstring> ...)``

Allowed patterns (not flagged):
  ``raise envelope_exception(...)``
  ``raise HTTPException(... detail={...dict...} ...)``
  ``raise HTTPException(... detail=build_envelope(...) ...)``
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


def _is_bare_string_detail(kw: ast.keyword) -> bool:
    """Return True if the keyword is detail=<str literal or f-string>."""
    if kw.arg != "detail":
        return False
    val = kw.value
    is_bare = isinstance(val, ast.Constant) and isinstance(val.value, str)
    is_fstring = isinstance(val, ast.JoinedStr)
    return is_bare or is_fstring


def _callable_name(call: ast.Call) -> str:
    """Return the callable name for a Call node, or empty string."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _scan_file(fpath: str) -> list[tuple[str, int]]:
    """Scan a single file for bare-string HTTPException detail raises."""
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
        for kw in exc.keywords:
            if _is_bare_string_detail(kw):
                violations.append((fpath, node.lineno))
    return violations


def _collect_violations() -> list[tuple[str, int]]:
    """Return list of (filepath, lineno) for bare-string HTTPException raises."""
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
    """Report all bare-string HTTPException detail raises (report mode — never fails)."""
    violations = _collect_violations()

    if violations:
        lines = [f"  {path}:{lineno}" for path, lineno in violations]
        report = (
            f"\nWARN: {len(violations)} bare-string HTTPException detail raises still present.\n"
            "These will be migrated in K6..KN and this test will be flipped to enforcing in K-last.\n"
            + "\n".join(lines)
        )
        print(report, file=sys.stderr)

    # Report mode: always pass. Flip to ``assert not violations`` in K-last.
    assert True  # report mode — see module docstring
