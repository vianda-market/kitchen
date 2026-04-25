"""
K5 parity test: all validation.* ErrorCode members have en/es/pt entries in
MESSAGES, and every I18nValueError first-arg in app/schemas/ is a registered
ErrorCode member.

Two test functions:
1. test_validation_codes_have_messages — subset of the broader error_codes_parity
   test, scoped only to validation.* codes.
2. test_schema_i18n_codes_are_registered — AST scan of app/schemas/ for
   I18nValueError("...") call sites; asserts each code arg is in ErrorCode.
"""

import ast
from pathlib import Path

import pytest

from app.i18n.error_codes import ErrorCode
from app.i18n.messages import MESSAGES

REQUIRED_LOCALES = ("en", "es", "pt")
# parents[2] = app/  →  app/schemas/
SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"

pytestmark = pytest.mark.parity


@pytest.mark.parametrize("locale", REQUIRED_LOCALES)
def test_validation_codes_have_messages(locale: str) -> None:
    """Every validation.* ErrorCode value must have a message entry in the given locale."""
    catalog = MESSAGES.get(locale, {})
    validation_codes = [code.value for code in ErrorCode if code.value.startswith("validation.")]
    missing = [code for code in validation_codes if code not in catalog]
    assert not missing, (
        f"MESSAGES['{locale}'] is missing entries for validation.* ErrorCode values: {missing}\n"
        "Add en/es/pt rows to app/i18n/messages.py for each missing code."
    )


def _collect_i18n_value_error_codes() -> list[tuple[str, int, str]]:
    """
    Walk app/schemas/ and collect all I18nValueError("literal") first arguments.

    Returns a list of (file_path_str, lineno, code_string) tuples.
    """
    results: list[tuple[str, int, str]] = []
    for py_file in SCHEMAS_DIR.rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            # Match I18nValueError("code", ...)
            func = node.func
            if (
                isinstance(func, ast.Name)
                and func.id == "I18nValueError"
                or isinstance(func, ast.Attribute)
                and func.attr == "I18nValueError"
            ):
                pass
            else:
                continue

            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                results.append((str(py_file), node.lineno, node.args[0].value))

    return results


def test_schema_i18n_codes_are_registered() -> None:
    """Every I18nValueError first-arg in app/schemas/ must be a registered ErrorCode member."""
    all_code_values = {code.value for code in ErrorCode}
    sites = _collect_i18n_value_error_codes()

    assert sites, (
        "No I18nValueError(...) call sites found in app/schemas/. "
        "Either the migration was not done or the AST walker has a bug."
    )

    violations: list[str] = []
    for file_path, lineno, code_str in sites:
        if code_str not in all_code_values:
            violations.append(f"  {file_path}:{lineno}  code={code_str!r}")

    assert not violations, (
        "I18nValueError codes not registered in ErrorCode:\n"
        + "\n".join(violations)
        + "\nAdd each code to app/i18n/error_codes.py."
    )
