"""
Post-rebuild FX + national holiday sync (invoked from build_kitchen_db.sh).

Uses the same services as cron; never exits non-zero so DB rebuild is not aborted.
Log lines are prefixed with [post-rebuild-sync] for easy grep in CI logs.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict


def _ensure_db_password() -> None:
    if not os.getenv("DB_PASSWORD") and os.getenv("PGPASSWORD"):
        os.environ["DB_PASSWORD"] = os.environ["PGPASSWORD"]


def _check_network(url: str, timeout: float = 3.0) -> bool:
    """Return True if host appears reachable (HEAD, or GET if HEAD returns 405)."""
    import httpx

    try:
        r = httpx.head(url, timeout=timeout, follow_redirects=True)
        if r.status_code == 405:
            r = httpx.get(url, timeout=timeout, follow_redirects=True)
        return True
    except httpx.RequestError:
        return False
    except Exception:
        return False


def _log_currency(result: Dict[str, Any]) -> None:
    prefix = "[post-rebuild-sync] currency:"
    if result.get("status") == "ok":
        updated = result.get("updated", [])
        skipped = result.get("skipped", [])
        errors = result.get("errors", [])
        print(
            f"{prefix} status=ok updated={updated!s} skipped={skipped!s} errors={errors!s}",
            file=sys.stdout,
        )
    else:
        reason = result.get("reason", "unknown")
        print(f"{prefix} status=error reason={reason}", file=sys.stderr)


def _log_holidays(result: Dict[str, Any]) -> None:
    prefix = "[post-rebuild-sync] holidays:"
    if result.get("status") == "error":
        reason = result.get("reason", "unknown")
        print(f"{prefix} status=error reason={reason}", file=sys.stderr)
        return
    errors = result.get("errors") or []
    years = result.get("years")
    inserted = result.get("inserted", {})
    if errors:
        print(
            f"{prefix} status=ok partial_errors={errors!s} inserted={inserted!s}",
            file=sys.stderr,
        )
    else:
        print(
            f"{prefix} status=ok years={years!s} inserted={inserted!s}",
            file=sys.stdout,
        )


def _run_currency() -> None:
    if not _check_network("https://open.er-api.com"):
        print(
            "[post-rebuild-sync] currency: skipped (open.er-api.com unreachable)",
            file=sys.stderr,
        )
        return
    try:
        from app.services.cron.currency_refresh import run_currency_refresh

        _log_currency(run_currency_refresh())
    except Exception as e:
        print(f"[post-rebuild-sync] currency: exception {e!s}", file=sys.stderr)


def _run_holidays() -> None:
    if not _check_network("https://date.nager.at"):
        print(
            "[post-rebuild-sync] holidays: skipped (date.nager.at unreachable)",
            file=sys.stderr,
        )
        return
    try:
        from app.services.cron.holiday_refresh import run_holiday_refresh

        _log_holidays(run_holiday_refresh(years=None))
    except Exception as e:
        print(f"[post-rebuild-sync] holidays: exception {e!s}", file=sys.stderr)


def main() -> None:
    _ensure_db_password()
    _run_currency()
    _run_holidays()


if __name__ == "__main__":
    main()
    sys.exit(0)
