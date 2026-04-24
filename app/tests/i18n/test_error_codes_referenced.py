"""
Referenceability test: every ErrorCode enum member must be referenced at
least once in app/ outside of error_codes.py itself.

This prevents codes from being added to the registry and then forgotten —
an unreferenced code is either (a) not yet wired (allowlisted below) or
(b) dead code that should be removed.

ALLOWLIST POLICY:
  All seeds introduced in K2 are allowlisted because their raise sites are
  wired in later PRs:
    - request.* and legacy.uncoded  → wired by K3 (catch-all handlers)
    - validation.*                  → wired by K3/K5 (RequestValidationError handler)
    - auth.*                        → wired by K6 (auth sweep)
    - subscription.already_active   → wired by a K6..KN sweep PR

  Remove a code from the allowlist in the same PR that wires its first raise
  site. The allowlist shrinks monotonically toward zero by K-last.

  Each entry below includes the PR that will remove it so reviewers can
  verify the allowlist is minimal and not growing indefinitely.
"""

import ast
from pathlib import Path

import pytest

from app.i18n.error_codes import ErrorCode

# Codes not yet raised at K2 time; wired incrementally by K3..KN.
# Format: ErrorCode member → PR that will remove the allowlist entry.
ALLOWLISTED: dict[str, str] = {
    # K3 — catch-all handlers
    "REQUEST_NOT_FOUND": "K3",
    "REQUEST_METHOD_NOT_ALLOWED": "K3",
    "REQUEST_MALFORMED_BODY": "K3",
    "REQUEST_TOO_LARGE": "K3",
    "REQUEST_RATE_LIMITED": "K3",
    "LEGACY_UNCODED": "K3",
    # K3/K5 — RequestValidationError handler + Pydantic 422 refinement
    "VALIDATION_FIELD_REQUIRED": "K5",
    "VALIDATION_INVALID_FORMAT": "K5",
    "VALIDATION_VALUE_TOO_SHORT": "K5",
    "VALIDATION_VALUE_TOO_LONG": "K5",
    "VALIDATION_CUSTOM": "K3",
    # K6 — auth sweep
    "AUTH_INVALID_TOKEN": "K6",
    "AUTH_CAPTCHA_REQUIRED": "K6",
    # K6..KN — subscription sweep
    "SUBSCRIPTION_ALREADY_ACTIVE": "K6",
}

pytestmark = pytest.mark.parity


def _collect_references(app_root: Path, registry_file: Path) -> set[str]:
    """
    Return the set of ErrorCode member names referenced in app/ outside
    the registry file itself.

    Uses a plain text search rather than full AST resolution: looks for
    "ErrorCode.<MEMBER_NAME>" in source files. This is fast, grep-friendly,
    and sufficient for the purpose (we want to know a member is *used*
    somewhere, not validate every call site).
    """
    referenced: set[str] = set()
    for py_file in app_root.rglob("*.py"):
        if py_file.resolve() == registry_file.resolve():
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for member in ErrorCode.__members__:
            if f"ErrorCode.{member}" in source:
                referenced.add(member)
    return referenced


def test_error_codes_are_referenced() -> None:
    """
    Every non-allowlisted ErrorCode member is referenced at least once
    outside error_codes.py.
    """
    app_root = Path(__file__).parent.parent.parent  # app/
    registry_file = app_root / "i18n" / "error_codes.py"

    referenced = _collect_references(app_root, registry_file)

    unreferenced_non_allowlisted = [
        member for member in ErrorCode.__members__ if member not in referenced and member not in ALLOWLISTED
    ]

    assert not unreferenced_non_allowlisted, (
        f"ErrorCode members are defined but never referenced outside error_codes.py "
        f"and are not in the allowlist: {unreferenced_non_allowlisted}\n"
        "Either wire the code at a raise site, or add it to ALLOWLISTED with the "
        "PR that will wire it."
    )


def test_allowlist_is_minimal() -> None:
    """
    Every entry in ALLOWLISTED corresponds to an actual ErrorCode member.
    Catches stale allowlist entries after a code is removed or renamed.
    """
    all_members = set(ErrorCode.__members__)
    stale = [name for name in ALLOWLISTED if name not in all_members]
    assert not stale, (
        f"ALLOWLISTED entries do not correspond to any ErrorCode member: {stale}\n"
        "Remove them from the allowlist in this test file."
    )


def _count_ast_references(app_root: Path, registry_file: Path) -> dict[str, int]:
    """
    Supplementary helper used only when running this test with -v for
    debugging. Not called during normal test execution.
    """
    counts: dict[str, int] = dict.fromkeys(ErrorCode.__members__, 0)
    for py_file in app_root.rglob("*.py"):
        if py_file.resolve() == registry_file.resolve():
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "ErrorCode"
                and node.attr in counts
            ):
                counts[node.attr] += 1
    return counts
