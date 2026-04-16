"""
Billing Cron Job - Scheduled institution bill generation

This module provides automated billing functionality that can be triggered
by external cron schedulers or monitoring systems.
"""

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from app.services.billing.institution_billing import InstitutionBillingService
from app.utils.log import log_error, log_info, log_warning

# System user ID for automated operations - using existing bot_chef user
SYSTEM_USER_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def run_daily_billing(bill_date: date | None = None, country_code: str | None = None) -> dict[str, Any]:
    """
    Daily cron job to generate institution bills from restaurant balances.
    Bills are generated when kitchen days close, not at midnight.
    Country is automatically detected from restaurant address if not provided.

    Args:
        bill_date: Date to generate bills for (defaults to yesterday)
        country_code: Optional country code override (if not provided, detected from restaurant address)

    Returns:
        Dict with billing results and metadata
    """
    try:
        # Default to yesterday if no date specified
        if not bill_date:
            yesterday = datetime.now(UTC).date()
            bill_date = yesterday

        log_info(f"Starting daily billing cron job for {bill_date}")
        if country_code:
            log_info(f"Using country code override: {country_code}")
        else:
            log_info("Country code not provided - will auto-detect from restaurant addresses")

        # Run settlement → bill → payout pipeline
        result = InstitutionBillingService.run_daily_settlement_bill_and_payout(
            bill_date=bill_date,
            system_user_id=SYSTEM_USER_ID,
            country_code=country_code,
        )
        if result.get("error"):
            return {
                "cron_job": "daily_billing",
                "bill_date": bill_date.isoformat(),
                "country_code": country_code,
                "execution_time": datetime.now(UTC).isoformat(),
                "success": False,
                "error": result["error"],
                "settlements_created": result.get("settlements_created", 0),
                "bills_created": result.get("bills_created", 0),
                "total_amount": result.get("total_amount", 0.0),
            }
        # Add cron job metadata
        result.update(
            {
                "cron_job": "daily_billing",
                "bill_date": bill_date.isoformat(),
                "country_code": country_code,
                "execution_time": datetime.now(UTC).isoformat(),
                "success": True,
            }
        )
        result.setdefault("restaurants_processed", result.get("settlements_created", 0))
        log_info(f"Daily billing cron job completed successfully: {result}")
        return result

    except Exception as e:
        error_msg = f"Fatal error in daily billing cron job: {e}"
        log_error(error_msg)

        return {
            "cron_job": "daily_billing",
            "bill_date": bill_date.isoformat() if bill_date else None,
            "country_code": country_code,
            "execution_time": datetime.now(UTC).isoformat(),
            "success": False,
            "error": str(e),
            "settlements_created": 0,
            "bills_created": 0,
            "total_amount": 0.0,
            "restaurants_processed": 0,
        }


def run_daily_settlement_bill_and_payout(
    bill_date: date | None = None,
    country_code: str | None = None,
) -> dict[str, Any]:
    """
    Atomic closeout-to-payout pipeline: Phase 1 settlements (one per restaurant with balance),
    Phase 2 one bill per entity, then tax doc stub, payout (mock/live), mark_paid.
    Schedule at 3:30 PM local (or configurable) via external cron.
    """
    try:
        if not bill_date:
            bill_date = datetime.now(UTC).date()
        log_info(f"Starting daily settlement-bill-payout pipeline for {bill_date}")
        result = InstitutionBillingService.run_daily_settlement_bill_and_payout(
            bill_date=bill_date,
            system_user_id=SYSTEM_USER_ID,
            country_code=country_code,
        )
        result.update(
            {
                "cron_job": "daily_settlement_bill_and_payout",
                "bill_date": bill_date.isoformat(),
                "country_code": country_code,
                "execution_time": datetime.now(UTC).isoformat(),
                "success": "error" not in result,
            }
        )
        log_info(f"Daily settlement-bill-payout completed: {result}")
        return result
    except Exception as e:
        log_error(f"Fatal error in daily settlement-bill-payout: {e}")
        return {
            "cron_job": "daily_settlement_bill_and_payout",
            "bill_date": bill_date.isoformat() if bill_date else None,
            "country_code": country_code,
            "execution_time": datetime.now(UTC).isoformat(),
            "success": False,
            "error": str(e),
            "settlements_created": 0,
            "bills_created": 0,
            "bills_paid": 0,
        }


def run_kitchen_day_closure_billing(country_code: str | None = None) -> dict[str, Any]:
    """
    Real-time billing trigger when a kitchen day closes for a specific market.
    This should be called shortly after kitchen closure time.
    Country is automatically detected from restaurant address if not provided.

    Args:
        country_code: Optional country code override (if not provided, detected from restaurant address)

    Returns:
        Dict with billing results and metadata
    """
    try:
        current_time = datetime.now(UTC)
        current_day = current_time.date()

        log_info(f"Starting kitchen day closure billing for {current_day}")
        if country_code:
            log_info(f"Using country code override: {country_code}")
        else:
            log_info("Country code not provided - will auto-detect from restaurant addresses")

        # Check if it's time to bill for this market (only if country_code is provided)
        if country_code and not InstitutionBillingService.should_generate_bills_now(country_code):
            log_info(f"Not time to bill yet for market {country_code}. Current time: {current_time}")
            return {
                "cron_job": "kitchen_day_closure_billing",
                "bill_date": current_day.isoformat(),
                "country_code": country_code,
                "execution_time": current_time.isoformat(),
                "success": True,
                "bills_created": 0,
                "total_amount": 0.0,
                "restaurants_processed": 0,
                "reason": f"Not yet time to bill for market {country_code}",
            }

        # Run settlement → bill → payout pipeline
        result = InstitutionBillingService.run_daily_settlement_bill_and_payout(
            bill_date=current_day,
            system_user_id=SYSTEM_USER_ID,
            country_code=country_code,
        )
        if result.get("error"):
            return {
                "cron_job": "kitchen_day_closure_billing",
                "bill_date": current_day.isoformat(),
                "country_code": country_code,
                "execution_time": current_time.isoformat(),
                "success": False,
                "error": result["error"],
                "settlements_created": result.get("settlements_created", 0),
                "bills_created": result.get("bills_created", 0),
                "total_amount": result.get("total_amount", 0.0),
                "restaurants_processed": result.get("settlements_created", 0),
            }
        # Add cron job metadata
        result.update(
            {
                "cron_job": "kitchen_day_closure_billing",
                "bill_date": current_day.isoformat(),
                "country_code": country_code,
                "execution_time": current_time.isoformat(),
                "success": True,
            }
        )
        result.setdefault("restaurants_processed", result.get("settlements_created", 0))
        log_info(f"Kitchen day closure billing completed successfully: {result}")
        return result

    except Exception as e:
        error_msg = f"Fatal error in kitchen day closure billing: {e}"
        log_error(error_msg)

        return {
            "cron_job": "kitchen_day_closure_billing",
            "bill_date": current_time.date().isoformat() if "current_time" in locals() else None,
            "country_code": country_code,
            "execution_time": datetime.now(UTC).isoformat(),
            "success": False,
            "error": str(e),
            "bills_created": 0,
            "total_amount": 0.0,
            "restaurants_processed": 0,
        }


def run_billing_for_location(location_id: str) -> dict[str, Any]:
    """
    Run billing for a single location (timezone-region).
    Filters restaurants by address.timezone; uses location's market for kitchen config.
    """
    try:
        from app.config.location_config import get_location_config

        loc_config = get_location_config(location_id)
        if not loc_config:
            log_error(f"Unknown location_id: {location_id}")
            return {
                "cron_job": "billing_for_location",
                "location_id": location_id,
                "success": False,
                "error": f"Unknown location_id: {location_id}",
                "bills_created": 0,
                "total_amount": 0.0,
                "restaurants_processed": 0,
            }
        if not InstitutionBillingService.should_generate_bills_now_for_location(location_id):
            return {
                "cron_job": "billing_for_location",
                "location_id": location_id,
                "success": True,
                "bills_created": 0,
                "total_amount": 0.0,
                "restaurants_processed": 0,
                "reason": f"Not yet time to bill for location {location_id}",
            }
        current_day = datetime.now(UTC).date()
        result = InstitutionBillingService.run_daily_settlement_bill_and_payout(
            bill_date=current_day,
            system_user_id=SYSTEM_USER_ID,
            location_id=location_id,
            connection=None,
        )
        result.update(
            {
                "cron_job": "billing_for_location",
                "location_id": location_id,
                "success": "error" not in result,
            }
        )
        result.setdefault("restaurants_processed", result.get("settlements_created", 0))
        return result
    except Exception as e:
        log_error(f"Fatal error in billing for location {location_id}: {e}")
        return {
            "cron_job": "billing_for_location",
            "location_id": location_id,
            "success": False,
            "error": str(e),
            "bills_created": 0,
            "total_amount": 0.0,
            "restaurants_processed": 0,
        }


def run_multi_market_billing(location_id: str | None = None) -> dict[str, Any]:
    """
    Run billing for configured locations.
    When location_id is provided, process only that location.
    When None, process all locations (AR, PE, US-Eastern, US-Central, US-Mountain, US-Pacific).

    Args:
        location_id: Optional. If provided, only process this location.

    Returns:
        Dict with results for all processed locations
    """
    try:
        from app.config.location_config import get_all_locations, get_location_config

        all_locations = get_all_locations()
        locations_to_process = [get_location_config(location_id)] if location_id else all_locations
        locations_to_process = [loc for loc in locations_to_process if loc]
        results = {}

        log_info(f"Starting multi-market billing for {len(locations_to_process)} location(s)")

        for loc in locations_to_process:
            loc_id = loc["location"]
            try:
                log_info(f"Processing location: {loc_id} ({loc['timezone']})")
                market_result = run_billing_for_location(loc_id)
                results[loc_id] = market_result
            except Exception as e:
                log_error(f"Error processing location {loc_id}: {e}")
                results[loc_id] = {
                    "success": False,
                    "error": str(e),
                    "bills_created": 0,
                    "total_amount": 0.0,
                    "restaurants_processed": 0,
                }

        total_bills = sum(r.get("bills_created", 0) for r in results.values())
        total_amount = sum(r.get("total_amount", 0.0) for r in results.values())
        total_restaurants = sum(r.get("restaurants_processed", 0) for r in results.values())

        multi_market_result = {
            "cron_job": "multi_market_billing",
            "execution_time": datetime.now(UTC).isoformat(),
            "success": True,
            "locations_processed": len(locations_to_process),
            "total_bills_created": total_bills,
            "total_amount": total_amount,
            "total_restaurants_processed": total_restaurants,
            "location_results": results,
        }

        log_info(f"Multi-market billing completed: {total_bills} bills, ${total_amount} total")
        return multi_market_result

    except Exception as e:
        error_msg = f"Fatal error in multi-market billing: {e}"
        log_error(error_msg)

        return {
            "cron_job": "multi_market_billing",
            "execution_time": datetime.now(UTC).isoformat(),
            "success": False,
            "error": str(e),
            "locations_processed": 0,
            "total_bills_created": 0,
            "total_amount": 0.0,
            "total_restaurants_processed": 0,
        }


def run_monthly_billing(bill_date: date | None = None) -> dict[str, Any]:
    """
    Monthly cron job to generate comprehensive institution bills.

    Args:
        bill_date: Date to generate bills for (defaults to first of current month)

    Returns:
        Dict with monthly billing results
    """
    try:
        # Default to first of current month if no date specified
        if not bill_date:
            now = datetime.now(UTC)
            bill_date = now.replace(day=1).date()

        log_info(f"Starting monthly billing cron job for {bill_date}")

        # Run settlement → bill → payout pipeline
        result = InstitutionBillingService.run_daily_settlement_bill_and_payout(
            bill_date=bill_date,
            system_user_id=SYSTEM_USER_ID,
            country_code=None,
        )
        if result.get("error"):
            return {
                "cron_job": "monthly_billing",
                "bill_date": bill_date.isoformat(),
                "execution_time": datetime.now(UTC).isoformat(),
                "success": False,
                "error": result["error"],
                "settlements_created": result.get("settlements_created", 0),
                "bills_created": result.get("bills_created", 0),
                "total_amount": result.get("total_amount", 0.0),
                "restaurants_processed": result.get("settlements_created", 0),
            }
        # Add cron job metadata
        result.update(
            {
                "cron_job": "monthly_billing",
                "bill_date": bill_date.isoformat(),
                "execution_time": datetime.now(UTC).isoformat(),
                "success": True,
            }
        )
        result.setdefault("restaurants_processed", result.get("settlements_created", 0))
        log_info(f"Monthly billing cron job completed successfully: {result}")
        return result

    except Exception as e:
        error_msg = f"Fatal error in monthly billing cron job: {e}"
        log_error(error_msg)

        return {
            "cron_job": "monthly_billing",
            "bill_date": bill_date.isoformat() if bill_date else None,
            "execution_time": datetime.now(UTC).isoformat(),
            "success": False,
            "error": str(e),
            "bills_created": 0,
            "total_amount": 0.0,
            "restaurants_processed": 0,
        }


def get_billing_dashboard() -> dict[str, Any]:
    """
    Generate billing dashboard with current status and statistics.
    Restaurant count per institution is derived from institution_settlement (bills no longer have restaurant_id).
    """
    from app.utils.db import close_db_connection, db_read, get_db_connection

    try:
        log_info("Generating billing dashboard")
        connection = get_db_connection()
        try:
            pending_bills = InstitutionBillingService.get_pending_bills(connection=connection)
            total_pending_amount = sum((bill.amount or 0) for bill in pending_bills)
            total_pending_bills = len(pending_bills)
            bill_ids = [str(bill.institution_bill_id) for bill in pending_bills]
            institution_summary = {}
            for bill in pending_bills:
                inst_id = str(bill.institution_id)
                if inst_id not in institution_summary:
                    institution_summary[inst_id] = {
                        "institution_id": inst_id,
                        "pending_bills": 0,
                        "pending_amount": 0,
                        "restaurants": set(),
                    }
                institution_summary[inst_id]["pending_bills"] += 1
                institution_summary[inst_id]["pending_amount"] += bill.amount or 0
            if bill_ids:
                placeholders = ",".join(["%s"] * len(bill_ids))
                query = f"""
                    SELECT ibi.institution_id, s.restaurant_id
                    FROM institution_bill_info ibi
                    INNER JOIN institution_settlement s ON s.institution_bill_id = ibi.institution_bill_id
                    WHERE ibi.institution_bill_id IN ({placeholders})
                      AND ibi.is_archived = FALSE AND s.is_archived = FALSE
                """
                rows = db_read(query, tuple(bill_ids), connection=connection)
                for row in rows or []:
                    inst_id = str(row["institution_id"])
                    if inst_id in institution_summary:
                        institution_summary[inst_id]["restaurants"].add(str(row["restaurant_id"]))
            for inst in institution_summary.values():
                inst["restaurant_count"] = len(inst["restaurants"])
                del inst["restaurants"]
        finally:
            close_db_connection(connection)
        dashboard = {
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": {
                "total_pending_bills": total_pending_bills,
                "total_pending_amount": float(total_pending_amount),
                "institutions_with_pending_bills": len(institution_summary),
            },
            "institution_breakdown": list(institution_summary.values()),
            "recent_bills": [
                {
                    "bill_id": str(bill.institution_bill_id),
                    "institution_id": str(bill.institution_id),
                    "amount": float(bill.amount or 0),
                    "status": bill.status,
                    "created_date": bill.created_date.isoformat(),
                }
                for bill in pending_bills[:10]
            ],
        }

        log_info(f"Billing dashboard generated: {dashboard['summary']}")
        return dashboard

    except Exception as e:
        log_error(f"Error generating billing dashboard: {e}")
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "error": str(e),
            "summary": {"total_pending_bills": 0, "total_pending_amount": 0.0, "institutions_with_pending_bills": 0},
        }


# Entry points for external cron systems
def daily_billing_entry():
    """Entry point for daily billing cron job"""
    result = run_daily_billing()
    return result


def kitchen_day_closure_billing_entry():
    """Entry point for kitchen day closure billing cron job"""
    result = run_kitchen_day_closure_billing()
    return result


def multi_market_billing_entry(location_id: str | None = None):
    """Entry point for multi-market billing cron job. When location_id is provided, process only that location; when None, process all locations."""
    result = run_multi_market_billing(location_id=location_id)
    return result


def monthly_billing_entry():
    """Entry point for monthly billing cron job"""
    result = run_monthly_billing()
    return result


def dashboard_entry():
    """Entry point for billing dashboard generation"""
    result = get_billing_dashboard()
    return result


def kitchen_start_promotion_entry(location_id: str | None = None):
    """Entry point for kitchen start promotion cron. Promotes locked plate selections to live."""
    from app.services.cron.kitchen_start_promotion import run_kitchen_start_promotion

    return run_kitchen_start_promotion(location_id=location_id)


def currency_refresh_entry():
    """Entry point for currency rate refresh cron. Fetches USD rates from open.er-api.com and updates currency_metadata."""
    from app.services.cron.currency_refresh import run_currency_refresh

    return run_currency_refresh()


def holiday_refresh_entry():
    """Entry point for national public holiday sync from Nager.Date (market countries)."""
    from app.services.cron.holiday_refresh import run_holiday_refresh

    return run_holiday_refresh()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "daily":
            result = run_daily_billing()
            log_info(f"Daily billing result: {result}")
        elif command == "monthly":
            result = run_monthly_billing()
            log_info(f"Monthly billing result: {result}")
        elif command == "dashboard":
            result = get_billing_dashboard()
            log_info(f"Dashboard result: {result}")
        elif command == "kitchen_closure":
            result = run_kitchen_day_closure_billing()
            log_info(f"Kitchen day closure billing result: {result}")
        elif command == "multi_market":
            result = run_multi_market_billing(location_id=sys.argv[2] if len(sys.argv) > 2 else None)
            log_info(f"Multi-market billing result: {result}")
        elif command == "kitchen_start":
            from app.services.cron.kitchen_start_promotion import run_kitchen_start_promotion

            result = run_kitchen_start_promotion(location_id=sys.argv[2] if len(sys.argv) > 2 else None)
            log_info(f"Kitchen start promotion result: {result}")
        elif command == "currency_refresh":
            from app.services.cron.currency_refresh import run_currency_refresh

            result = run_currency_refresh()
            log_info(f"Currency refresh result: {result}")
        elif command == "holiday_refresh":
            from app.services.cron.holiday_refresh import run_holiday_refresh

            optional_years = [int(x) for x in sys.argv[2:]] if len(sys.argv) > 2 else None
            result = run_holiday_refresh(years=optional_years)
            log_info(f"Holiday refresh result: {result}")
        else:
            log_warning(f"Unknown command: {command}")
            log_info(
                "Available commands: daily, monthly, dashboard, kitchen_closure, "
                "multi_market, kitchen_start, currency_refresh, holiday_refresh"
            )
    else:
        result = run_daily_billing()
        log_info(f"Daily billing result: {result}")
