"""
Currency Rate Refresh Cron - Fetch USD exchange rates from open.er-api.com.

Appends raw API payloads to currency_rate_raw for audit trail, validates rates
(outlier detection, zero check), and updates currency_metadata.currency_conversion_usd.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx

from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.utils.db import db_insert, db_read, db_update
from app.utils.db_pool import get_db_connection_context
from app.utils.log import log_error, log_info, log_warning

RATE_API_URL = "https://open.er-api.com/v6/latest/USD"
OUTLIER_THRESHOLD = 0.5  # Flag if rate changes more than 50% vs previous
SYSTEM_USER_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def fetch_usd_rate_for_currency(currency_code: str) -> tuple[float | None, dict | None]:
    """
    Fetch USD exchange rate for a single currency from open.er-api.com.

    Used by credit currency create. For USD returns 1.0 without API call.
    Raises HTTPException(503) on timeout or HTTP error.
    Returns (None, None) if currency not in response or rate is 0.
    """
    if currency_code == "USD":
        return (1.0, {"result": "success", "base_code": "USD", "rates": {"USD": 1}})
    try:
        response = httpx.get(RATE_API_URL, timeout=5.0)
        data = response.json()
        if data.get("result") != "success":
            return (None, None)
        rate = data["rates"].get(currency_code)
        if not rate or rate == 0:
            return (None, None)
        return (float(rate), data)
    except httpx.TimeoutException:
        raise envelope_exception(ErrorCode.CURRENCY_REFRESH_RATE_UNAVAILABLE, status=503, locale="en") from None
    except httpx.HTTPError:
        raise envelope_exception(ErrorCode.CURRENCY_REFRESH_RATE_UNAVAILABLE, status=503, locale="en") from None


def _get_target_currencies(connection) -> list[str]:
    """Get non-USD currency codes from currency_metadata (non-archived)."""
    query = """
        SELECT currency_code
        FROM currency_metadata
        WHERE currency_code != 'USD' AND is_archived = FALSE
    """
    rows = db_read(query, connection=connection)
    return [r["currency_code"] for r in rows] if rows else []


def _get_previous_rate(currency_code: str, connection) -> float | None:
    """Get the most recent valid rate for a currency from currency_rate_raw."""
    query = """
        SELECT rate
        FROM currency_rate_raw
        WHERE target_currency = %s AND is_valid = TRUE
        ORDER BY fetched_at DESC
        LIMIT 1
    """
    row = db_read(query, (currency_code,), connection=connection, fetch_one=True)
    return float(row["rate"]) if row else None


def run_currency_refresh() -> dict[str, Any]:
    """
    Fetch latest USD exchange rates and update currency_metadata.

    Single API call to open.er-api.com returns all rates. Filters to target
    currencies from currency_metadata. Appends raw payload to currency_rate_raw
    for audit trail. Validates each rate (zero check, outlier detection).
    """
    result: dict[str, Any] = {
        "status": "ok",
        "updated": [],
        "skipped": [],
        "errors": [],
    }

    with get_db_connection_context() as db:
        target_currencies = _get_target_currencies(db)
        if not target_currencies:
            log_info("Currency refresh: no non-USD currencies in currency_metadata")
            return result

        try:
            response = httpx.get(RATE_API_URL, timeout=10.0)
            response.raise_for_status()
        except httpx.RequestError as e:
            log_error(f"Currency refresh failed — Rate API error: {e}")
            result["status"] = "error"
            result["reason"] = str(e)
            return result

        data = response.json()
        if data.get("result") != "success":
            log_error("Currency refresh failed — Rate API response not success")
            result["status"] = "error"
            result["reason"] = "API response result != success"
            return result

        all_rates = data.get("rates", {})
        raw_payload = data

        # api_date from API timestamp or fallback to today
        if "time_last_update_unix" in data:
            try:
                api_date = datetime.fromtimestamp(data["time_last_update_unix"], tz=UTC).date()
            except (TypeError, ValueError, OSError):
                api_date = datetime.now(UTC).date()
        else:
            api_date = datetime.now(UTC).date()

        for currency_code in target_currencies:
            rate = all_rates.get(currency_code)
            if rate is None:
                result["errors"].append(currency_code)
                continue

            try:
                rate_val = float(rate)
            except (TypeError, ValueError) as e:
                log_warning(f"Currency refresh: invalid rate for {currency_code}: {e}")
                result["errors"].append(currency_code)
                continue

            is_valid = True
            notes = None

            # Rate of 0 check (before outlier detection)
            if rate_val == 0:
                is_valid = False
                notes = "Invalid: rate is zero"
                result["skipped"].append(currency_code)
            else:
                prev = _get_previous_rate(currency_code, db)
                if prev is not None:
                    change_pct = abs(rate_val - prev) / prev
                    if change_pct > OUTLIER_THRESHOLD:
                        is_valid = False
                        notes = f"Outlier: {prev:.4f} → {rate_val:.4f} ({change_pct:.1%} change)"
                        result["skipped"].append(currency_code)

            # Always insert raw record
            insert_data = {
                "base_currency": "USD",
                "target_currency": currency_code,
                "rate": rate_val,
                "api_source": "open.er-api",
                "api_date": api_date,
                "raw_payload": raw_payload,
                "is_valid": is_valid,
                "notes": notes,
            }
            db_insert("currency_rate_raw", insert_data, connection=db)

            # Only update currency_metadata if rate is valid
            if is_valid:
                now = datetime.now(UTC)
                db_update(
                    "currency_metadata",
                    {
                        "currency_conversion_usd": rate_val,
                        "modified_by": SYSTEM_USER_ID,
                        "modified_date": now,
                    },
                    {"currency_code": currency_code, "is_archived": False},
                    connection=db,
                )
                result["updated"].append(currency_code)

        log_info(f"Currency refresh completed: updated={result['updated']}, skipped={result['skipped']}")
        if result["errors"]:
            log_warning(f"Currency refresh errors: {result['errors']}")

    return result
