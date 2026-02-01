"""
Archival Cron Job - Scheduled data lifecycle management

This module provides scheduled archival functionality that can be called
by external cron schedulers or monitoring systems.
"""

from datetime import datetime, timezone
from uuid import UUID
from typing import Dict, Any
import os
import sys

from app.services.archival import ArchivalService
from app.config.archival_config import get_config_source, get_archival_priority_order
from app.utils.log import log_info, log_warning, log_error

# System user ID for automated archival operations
SYSTEM_USER_ID = UUID("00000000-0000-0000-0000-000000000000")  # Placeholder - replace with actual system user


def run_daily_archival(batch_size: int = 200, max_tables: int = 15) -> Dict[str, Any]:
    """
    Daily cron job to archive records based on configured retention periods.
    
    Args:
        batch_size: Maximum number of records to process per table
        max_tables: Maximum number of tables to process per run
        
    Returns:
        Dictionary with archival results
    """
    log_info("Starting daily archival cron job")
    
    try:
        # Run the scheduled archival
        results = ArchivalService.run_scheduled_archival(
            modified_by=SYSTEM_USER_ID,
            batch_size=batch_size,
            max_tables=max_tables
        )
        
        # Log summary
        total_archived = results.get("total_archived", 0)
        duration = results.get("duration_seconds", 0)
        errors = results.get("errors", [])
        
        if results.get("success", False):
            log_info(f"Daily archival completed successfully: {total_archived} records archived in {duration:.2f}s")
        else:
            log_warning(f"Daily archival completed with errors: {total_archived} records archived, {len(errors)} errors")
            for error in errors[:5]:  # Log first 5 errors
                log_error(f"Archival error: {error}")
        
        # Add cron job metadata
        results.update({
            "cron_job": "daily_archival",
            "config_source": get_config_source(),
            "batch_size": batch_size,
            "max_tables": max_tables
        })
        
        return results
        
    except Exception as e:
        error_msg = f"Fatal error in daily archival cron job: {e}"
        log_error(error_msg)
        return {
            "cron_job": "daily_archival",
            "success": False,
            "fatal_error": error_msg,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def run_archival_validation() -> Dict[str, Any]:
    """
    Weekly cron job to validate archival system integrity.
    
    Returns:
        Dictionary with validation results
    """
    log_info("Starting archival validation cron job")
    
    try:
        validation_results = ArchivalService.validate_archival_integrity()
        
        # Log validation status
        overall_status = validation_results.get("overall_status", "unknown")
        issues_count = len(validation_results.get("issues", []))
        tables_checked = validation_results.get("tables_checked", 0)
        
        if overall_status == "healthy":
            log_info(f"Archival validation passed: {tables_checked} tables checked, system healthy")
        elif overall_status == "warning":
            log_warning(f"Archival validation found warnings: {issues_count} issues across {tables_checked} tables")
        else:
            log_error(f"Archival validation failed: {issues_count} issues across {tables_checked} tables")
        
        # Add cron job metadata
        validation_results.update({
            "cron_job": "archival_validation",
            "config_source": get_config_source()
        })
        
        return validation_results
        
    except Exception as e:
        error_msg = f"Fatal error in archival validation cron job: {e}"
        log_error(error_msg)
        return {
            "cron_job": "archival_validation",
            "overall_status": "error",
            "fatal_error": error_msg,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def get_archival_dashboard() -> Dict[str, Any]:
    """
    Get comprehensive archival dashboard data.
    
    Returns:
        Dictionary with dashboard statistics
    """
    log_info("Generating archival dashboard data")
    
    try:
        stats = ArchivalService.get_archival_stats()
        
        # Add additional dashboard metadata
        stats.update({
            "dashboard_generated": datetime.now(timezone.utc).isoformat(),
            "config_source": get_config_source(),
            "priority_order": get_archival_priority_order()[:10]  # Top 10 priority tables
        })
        
        return stats
        
    except Exception as e:
        error_msg = f"Error generating archival dashboard: {e}"
        log_error(error_msg)
        return {
            "dashboard_generated": datetime.now(timezone.utc).isoformat(),
            "error": error_msg
        }


def run_priority_archival(priority_category: str = "financial_critical", batch_size: int = 50) -> Dict[str, Any]:
    """
    Run archival for specific priority category (useful for urgent cleanup).
    
    Args:
        priority_category: Category to focus on (financial_critical, financial_operational, etc.)
        batch_size: Number of records to process per table
        
    Returns:
        Dictionary with archival results
    """
    log_info(f"Starting priority archival for category: {priority_category}")
    
    try:
        from app.config.archival_config import get_tables_by_category, ArchivalCategory
        
        # Get tables for the specified category
        try:
            category_enum = ArchivalCategory(priority_category)
            tables_to_process = get_tables_by_category(category_enum)
        except ValueError:
            log_error(f"Invalid category: {priority_category}")
            return {
                "cron_job": "priority_archival",
                "success": False,
                "error": f"Invalid category: {priority_category}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        if not tables_to_process:
            log_info(f"No tables found for category: {priority_category}")
            return {
                "cron_job": "priority_archival",
                "category": priority_category,
                "tables_processed": [],
                "total_archived": 0,
                "success": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        # Process each table in the category
        results = {
            "cron_job": "priority_archival",
            "category": priority_category,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "tables_processed": [],
            "total_archived": 0,
            "errors": []
        }
        
        for table_name in tables_to_process:
            try:
                log_info(f"Processing priority archival for table: {table_name}")
                
                # Get eligible records
                eligible_records = ArchivalService.get_eligible_records(table_name, limit=batch_size)
                
                if not eligible_records:
                    results["tables_processed"].append({
                        "table_name": table_name,
                        "eligible_count": 0,
                        "archived_count": 0
                    })
                    continue
                
                # Extract record IDs
                id_column = ArchivalService._get_primary_key_column(table_name)
                record_ids = []
                
                for record in eligible_records:
                    if isinstance(record, dict) and id_column in record:
                        record_ids.append(record[id_column])
                    elif hasattr(record, id_column):
                        record_ids.append(getattr(record, id_column))
                
                if not record_ids:
                    log_warning(f"Could not extract record IDs for {table_name}")
                    continue
                
                # Archive records
                archival_result = ArchivalService.archive_records(table_name, record_ids, SYSTEM_USER_ID)
                
                table_result = {
                    "table_name": table_name,
                    "eligible_count": len(eligible_records),
                    "archived_count": archival_result.get("archived_count", 0)
                }
                
                if "error" in archival_result:
                    table_result["error"] = archival_result["error"]
                    results["errors"].append(f"{table_name}: {archival_result['error']}")
                
                results["tables_processed"].append(table_result)
                results["total_archived"] += archival_result.get("archived_count", 0)
                
            except Exception as e:
                error_msg = f"Error processing {table_name}: {e}"
                log_error(error_msg)
                results["errors"].append(error_msg)
        
        end_time = datetime.now(timezone.utc)
        results.update({
            "end_time": end_time.isoformat(),
            "success": len(results["errors"]) == 0
        })
        
        log_info(f"Priority archival completed for {priority_category}: {results['total_archived']} records archived")
        return results
        
    except Exception as e:
        error_msg = f"Fatal error in priority archival: {e}"
        log_error(error_msg)
        return {
            "cron_job": "priority_archival",
            "category": priority_category,
            "success": False,
            "fatal_error": error_msg,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Entry points for external cron systems
def daily_cron_entry():
    """Entry point for daily cron job"""
    return run_daily_archival()


def weekly_validation_entry():
    """Entry point for weekly validation cron job"""
    return run_archival_validation()


def priority_financial_entry():
    """Entry point for urgent financial data archival"""
    return run_priority_archival("financial_critical", batch_size=100)


def dashboard_entry():
    """Entry point for dashboard data generation"""
    return get_archival_dashboard()


# CLI interface for testing and manual runs
if __name__ == "__main__":
    """
    Command-line interface for manual archival operations.
    
    Usage:
        python archival_job.py daily          # Run daily archival
        python archival_job.py validate       # Run validation
        python archival_job.py dashboard      # Generate dashboard
        python archival_job.py priority financial_critical  # Priority archival
    """
    
    if len(sys.argv) < 2:
        log_info("Usage: python archival_job.py [daily|validate|dashboard|priority]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "daily":
        batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 200
        max_tables = int(sys.argv[3]) if len(sys.argv) > 3 else 15
        result = run_daily_archival(batch_size, max_tables)
        
    elif command == "validate":
        result = run_archival_validation()
        
    elif command == "dashboard":
        result = get_archival_dashboard()
        
    elif command == "priority":
        category = sys.argv[2] if len(sys.argv) > 2 else "financial_critical"
        batch_size = int(sys.argv[3]) if len(sys.argv) > 3 else 50
        result = run_priority_archival(category, batch_size)
        
    else:
        log_warning(f"Unknown command: {command}")
        log_info("Valid commands: daily, validate, dashboard, priority")
        sys.exit(1)
    
    # Pretty print result
    import json
    log_info(json.dumps(result, indent=2, default=str))
    
    # Exit with appropriate code
    success = result.get("success", True)
    if result.get("overall_status") == "error":
        success = False
    
    sys.exit(0 if success else 1) 