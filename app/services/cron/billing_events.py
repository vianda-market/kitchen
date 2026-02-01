"""
Billing Cron Job - Scheduled institution bill generation

This module provides automated billing functionality that can be triggered
by external cron schedulers or monitoring systems.
"""

from datetime import date, datetime, timezone
from typing import Dict, Any, Optional
from uuid import UUID
from app.services.billing.institution_billing import InstitutionBillingService
from app.utils.log import log_info, log_warning, log_error

# System user ID for automated operations - using existing bot_chef user
SYSTEM_USER_ID = UUID("22222222-2222-2222-2222-222222222222")

def run_daily_billing(bill_date: Optional[date] = None, country_code: Optional[str] = None) -> Dict[str, Any]:
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
            yesterday = datetime.now(timezone.utc).date()
            bill_date = yesterday
        
        log_info(f"Starting daily billing cron job for {bill_date}")
        if country_code:
            log_info(f"Using country code override: {country_code}")
        else:
            log_info("Country code not provided - will auto-detect from restaurant addresses")
        
        # Generate bills for the specified date and market
        result = InstitutionBillingService.generate_daily_bills(
            bill_date=bill_date,
            system_user_id=SYSTEM_USER_ID,
            country_code=country_code
        )
        
        # Add cron job metadata
        result.update({
            "cron_job": "daily_billing",
            "bill_date": bill_date.isoformat(),
            "country_code": country_code,
            "execution_time": datetime.now(timezone.utc).isoformat(),
            "success": True
        })
        
        log_info(f"Daily billing cron job completed successfully: {result}")
        return result
        
    except Exception as e:
        error_msg = f"Fatal error in daily billing cron job: {e}"
        log_error(error_msg)
        
        return {
            "cron_job": "daily_billing",
            "bill_date": bill_date.isoformat() if bill_date else None,
            "country_code": country_code,
            "execution_time": datetime.now(timezone.utc).isoformat(),
            "success": False,
            "error": str(e),
            "bills_created": 0,
            "total_amount": 0.0,
            "restaurants_processed": 0
        }

def run_kitchen_day_closure_billing(country_code: Optional[str] = None) -> Dict[str, Any]:
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
        current_time = datetime.now(timezone.utc)
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
                "reason": f"Not yet time to bill for market {country_code}"
            }
        
        # Generate bills for the current day and market
        result = InstitutionBillingService.generate_daily_bills(
            bill_date=current_day,
            system_user_id=SYSTEM_USER_ID,
            country_code=country_code
        )
        
        # Add cron job metadata
        result.update({
            "cron_job": "kitchen_day_closure_billing",
            "bill_date": current_day.isoformat(),
            "country_code": country_code,
            "execution_time": current_time.isoformat(),
            "success": True
        })
        
        log_info(f"Kitchen day closure billing completed successfully: {result}")
        return result
        
    except Exception as e:
        error_msg = f"Fatal error in kitchen day closure billing: {e}"
        log_error(error_msg)
        
        return {
            "cron_job": "kitchen_day_closure_billing",
            "bill_date": current_time.date().isoformat() if 'current_time' in locals() else None,
            "country_code": country_code,
            "execution_time": datetime.now(timezone.utc).isoformat(),
            "success": False,
            "error": str(e),
            "bills_created": 0,
            "total_amount": 0.0,
            "restaurants_processed": 0
        }

def run_multi_market_billing() -> Dict[str, Any]:
    """
    Run billing for all configured markets.
    This is useful for a single cron job that handles multiple markets.
    
    Returns:
        Dict with results for all markets
    """
    try:
        from app.config.market_config import MarketConfiguration
        
        all_markets = MarketConfiguration.get_all_markets()
        results = {}
        
        log_info(f"Starting multi-market billing for {len(all_markets)} markets")
        
        for country_code, market_config in all_markets.items():
            try:
                log_info(f"Processing market: {country_code} ({market_config.market_name})")
                
                # Run billing for this market
                market_result = run_kitchen_day_closure_billing(country_code)
                results[country_code] = market_result
                
            except Exception as e:
                log_error(f"Error processing market {country_code}: {e}")
                results[country_code] = {
                    "success": False,
                    "error": str(e),
                    "bills_created": 0,
                    "total_amount": 0.0,
                    "restaurants_processed": 0
                }
        
        # Calculate totals
        total_bills = sum(r.get("bills_created", 0) for r in results.values())
        total_amount = sum(r.get("total_amount", 0.0) for r in results.values())
        total_restaurants = sum(r.get("restaurants_processed", 0) for r in results.values())
        
        multi_market_result = {
            "cron_job": "multi_market_billing",
            "execution_time": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "markets_processed": len(all_markets),
            "total_bills_created": total_bills,
            "total_amount": total_amount,
            "total_restaurants_processed": total_restaurants,
            "market_results": results
        }
        
        log_info(f"Multi-market billing completed: {total_bills} bills, ${total_amount} total")
        return multi_market_result
        
    except Exception as e:
        error_msg = f"Fatal error in multi-market billing: {e}"
        log_error(error_msg)
        
        return {
            "cron_job": "multi_market_billing",
            "execution_time": datetime.now(timezone.utc).isoformat(),
            "success": False,
            "error": str(e),
            "markets_processed": 0,
            "total_bills_created": 0,
            "total_amount": 0.0,
            "total_restaurants_processed": 0
        }

def run_monthly_billing(bill_date: Optional[date] = None) -> Dict[str, Any]:
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
            now = datetime.now(timezone.utc)
            bill_date = now.replace(day=1).date()
        
        log_info(f"Starting monthly billing cron job for {bill_date}")
        
        # Generate bills for the month
        result = InstitutionBillingService.generate_daily_bills(
            bill_date=bill_date,
            system_user_id=SYSTEM_USER_ID
        )
        
        # Add cron job metadata
        result.update({
            "cron_job": "monthly_billing",
            "bill_date": bill_date.isoformat(),
            "execution_time": datetime.now(timezone.utc).isoformat(),
            "success": True
        })
        
        log_info(f"Monthly billing cron job completed successfully: {result}")
        return result
        
    except Exception as e:
        error_msg = f"Fatal error in monthly billing cron job: {e}"
        log_error(error_msg)
        
        return {
            "cron_job": "monthly_billing",
            "bill_date": bill_date.isoformat() if bill_date else None,
            "execution_time": datetime.now(timezone.utc).isoformat(),
            "success": False,
            "error": str(e),
            "bills_created": 0,
            "total_amount": 0.0,
            "restaurants_processed": 0
        }

def get_billing_dashboard() -> Dict[str, Any]:
    """
    Generate billing dashboard with current status and statistics.
    
    Returns:
        Dict with billing dashboard data
    """
    try:
        log_info("Generating billing dashboard")
        
        # Get pending bills across all institutions
        pending_bills = InstitutionBillingService.get_pending_bills()
        
        # Calculate totals
        total_pending_amount = sum((bill.amount or 0) for bill in pending_bills)
        total_pending_bills = len(pending_bills)
        
        # Group by institution
        institution_summary = {}
        for bill in pending_bills:
            inst_id = str(bill.institution_id)
            if inst_id not in institution_summary:
                institution_summary[inst_id] = {
                    "institution_id": inst_id,
                    "pending_bills": 0,
                    "pending_amount": 0,
                    "restaurants": set()
                }
            
            institution_summary[inst_id]["pending_bills"] += 1
            institution_summary[inst_id]["pending_amount"] += (bill.amount or 0)
            institution_summary[inst_id]["restaurants"].add(str(bill.restaurant_id))
        
        # Convert sets to counts
        for inst in institution_summary.values():
            inst["restaurant_count"] = len(inst["restaurants"])
            del inst["restaurants"]
        
        dashboard = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_pending_bills": total_pending_bills,
                "total_pending_amount": float(total_pending_amount),
                "institutions_with_pending_bills": len(institution_summary)
            },
            "institution_breakdown": list(institution_summary.values()),
            "recent_bills": [
                {
                    "bill_id": str(bill.institution_bill_id),
                    "institution_id": str(bill.institution_id),
                    "restaurant_id": str(bill.restaurant_id),
                    "amount": float(bill.amount or 0),
                    "status": bill.status,
                    "created_date": bill.created_date.isoformat()
                }
                for bill in pending_bills[:10]  # Show last 10
            ]
        }
        
        log_info(f"Billing dashboard generated: {dashboard['summary']}")
        return dashboard
        
    except Exception as e:
        log_error(f"Error generating billing dashboard: {e}")
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
            "summary": {
                "total_pending_bills": 0,
                "total_pending_amount": 0.0,
                "institutions_with_pending_bills": 0
            }
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

def multi_market_billing_entry():
    """Entry point for multi-market billing cron job"""
    result = run_multi_market_billing()
    return result

def monthly_billing_entry():
    """Entry point for monthly billing cron job"""
    result = run_monthly_billing()
    return result

def dashboard_entry():
    """Entry point for billing dashboard generation"""
    result = get_billing_dashboard()
    return result

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
            result = run_multi_market_billing()
            log_info(f"Multi-market billing result: {result}")
        else:
            log_warning(f"Unknown command: {command}")
            log_info("Available commands: daily, monthly, dashboard, kitchen_closure, multi_market")
    else:
        result = run_daily_billing()
        log_info(f"Daily billing result: {result}")
