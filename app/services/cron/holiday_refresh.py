"""
National public holiday sync from Nager.Date (api v3).

UPSERT for nager_date rows (refresh names); skip when an active manual row owns the date.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import psycopg2.extensions

from app.config.market_config import MarketConfiguration
from app.services.cron.currency_refresh import SYSTEM_USER_ID
from app.utils.db import db_read
from app.utils.db_pool import get_db_connection_context
from app.utils.log import log_error, log_info, log_warning

NAGER_PUBLIC_HOLIDAYS_URL = "https://date.nager.at/api/v3/PublicHolidays"
VALID_YEAR_MIN = 2024


def _valid_year_max_utc() -> int:
    return datetime.now(UTC).year + 2


def _market_country_codes() -> list[str]:
    codes: set[str] = {cfg.country_code for cfg in MarketConfiguration.MARKETS.values()}
    return sorted(codes)


def _resolve_years(
    years: list[int] | None,
) -> tuple[list[int] | None, str | None]:
    """Returns (resolved_years, error_reason). error_reason set if explicit years invalid."""
    y_max = _valid_year_max_utc()

    if years is not None and len(years) > 0:
        for y in years:
            if y < VALID_YEAR_MIN or y > y_max:
                return None, (f"Year {y} is out of bounds; allowed [{VALID_YEAR_MIN}, {y_max}] inclusive (UTC).")
        return sorted(set(years)), None

    now_y = datetime.now(UTC).year
    raw = [now_y, now_y + 1]
    resolved = sorted({max(VALID_YEAR_MIN, min(y, y_max)) for y in raw})
    return resolved, None


def _upsert_nager_holiday(
    connection: psycopg2.extensions.connection,
    *,
    country_code: str,
    holiday_name: str,
    holiday_date: str,
    modified_by: UUID,
) -> str:
    """
    Insert or update a Nager-sourced holiday (non-recurring, source=nager_date).

    Does not touch active manual rows for the same (country_code, holiday_date).

    Returns:
        'inserted' | 'updated' | 'skipped_manual'
    """
    prior = db_read(
        """
        SELECT source FROM national_holidays
        WHERE country_code = %s AND holiday_date = %s::date AND is_archived = FALSE
        """,
        (country_code, holiday_date),
        connection=connection,
        fetch_one=True,
    )
    if prior and prior.get("source") == "manual":
        return "skipped_manual"

    had_nager = prior and prior.get("source") == "nager_date"

    sql = """
        INSERT INTO national_holidays (
            country_code,
            holiday_name,
            holiday_date,
            is_recurring,
            recurring_month,
            recurring_day,
            status,
            is_archived,
            modified_by,
            source
        ) VALUES (
            %s,
            %s,
            %s::date,
            FALSE,
            NULL,
            NULL,
            'active'::status_enum,
            FALSE,
            %s::uuid,
            'nager_date'
        )
        ON CONFLICT (country_code, holiday_date) WHERE NOT is_archived
        DO UPDATE SET
            holiday_name = EXCLUDED.holiday_name,
            modified_by = EXCLUDED.modified_by,
            modified_date = NOW()
        WHERE national_holidays.source = 'nager_date'
    """
    cursor = connection.cursor()
    try:
        cursor.execute(
            sql,
            (country_code, holiday_name, holiday_date, str(modified_by)),
        )
        rc = cursor.rowcount
        if rc == 0:
            return "skipped_manual"
        if had_nager:
            return "updated"
        return "inserted"
    finally:
        cursor.close()


def run_holiday_refresh(years: list[int] | None = None) -> dict[str, Any]:
    """
    Fetch public holidays from Nager.Date for all market country codes.

    Args:
        years: Optional explicit calendar years (UTC bounds). If omitted, uses
            current UTC year and next, clamped to [VALID_YEAR_MIN, VALID_YEAR_MAX].

    Returns:
        status ok|error, years processed, per-country inserted / updated / skipped counts,
        errors list (e.g. HTTP failures per country).
    """
    countries = _market_country_codes()
    empty_counts: dict[str, int] = dict.fromkeys(countries, 0)

    resolved, err = _resolve_years(years)
    if err:
        log_error(f"Holiday refresh: invalid years — {err}")
        return {
            "status": "error",
            "reason": err,
            "years": [],
            "inserted": {},
            "updated": {},
            "skipped": {},
            "errors": [],
        }

    assert resolved is not None
    inserted: dict[str, int] = dict.fromkeys(countries, 0)
    updated: dict[str, int] = dict.fromkeys(countries, 0)
    skipped: dict[str, int] = dict.fromkeys(countries, 0)
    errors: list[str] = []

    result: dict[str, Any] = {
        "status": "ok",
        "years": resolved,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }

    try:
        with get_db_connection_context() as db:
            for country_code in countries:
                for year in resolved:
                    url = f"{NAGER_PUBLIC_HOLIDAYS_URL}/{year}/{country_code}"
                    try:
                        response = httpx.get(url, timeout=15.0)
                        response.raise_for_status()
                        payload = response.json()
                    except httpx.HTTPStatusError as e:
                        msg = f"{country_code}: HTTP {e.response.status_code} for {year}"
                        log_warning(f"Holiday refresh — {msg}")
                        errors.append(msg)
                        continue
                    except httpx.HTTPError as e:
                        msg = f"{country_code}: {e!s}"
                        log_warning(f"Holiday refresh — {msg}")
                        errors.append(msg)
                        continue

                    if not isinstance(payload, list):
                        msg = f"{country_code}: unexpected JSON for {year}"
                        errors.append(msg)
                        continue

                    for holiday in payload:
                        raw_date = holiday.get("date")
                        if not raw_date:
                            continue
                        holiday_name = (holiday.get("localName") or holiday.get("name") or "")[:100]
                        holiday_name = holiday_name.strip()
                        if not holiday_name:
                            log_warning(
                                "Holiday refresh — skipping row with empty name "
                                f"after truncate ({country_code} {raw_date})"
                            )
                            continue

                        outcome = _upsert_nager_holiday(
                            db,
                            country_code=country_code,
                            holiday_name=holiday_name,
                            holiday_date=str(raw_date),
                            modified_by=SYSTEM_USER_ID,
                        )
                        if outcome == "inserted":
                            inserted[country_code] += 1
                        elif outcome == "updated":
                            updated[country_code] += 1
                        else:
                            skipped[country_code] += 1

            db.commit()
    except Exception as e:
        log_error(f"Holiday refresh failed — {e}")
        return {
            "status": "error",
            "reason": str(e),
            "years": resolved,
            "inserted": empty_counts,
            "updated": empty_counts,
            "skipped": empty_counts,
            "errors": errors + [f"database: {e!s}"],
        }

    log_info(
        f"Holiday refresh completed: years={resolved}, "
        f"inserted={inserted}, updated={updated}, skipped={skipped}, errors={len(errors)}"
    )
    if errors:
        log_warning(f"Holiday refresh completed with errors: {errors}")

    return result
