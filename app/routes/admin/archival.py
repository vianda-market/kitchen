"""
Admin Routes for Archival Management

These routes provide administrative control over the archival system,
including manual archival, statistics, and validation.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user, get_resolved_locale
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.services.archival import ArchivalService
from app.services.cron.archival_job import get_archival_dashboard, run_archival_validation, run_daily_archival
from app.services.error_handling import handle_business_operation
from app.utils.log import log_info

router = APIRouter(prefix="/admin/archival", tags=["Admin - Archival"])


@router.get("/stats", response_model=dict[str, Any])
async def get_archival_statistics(current_user: dict = Depends(get_current_user)):
    """
    Get comprehensive archival statistics across all entity types.

    Requires admin permissions.
    """
    # TODO: Add admin role check
    # if current_user.get("role_type") != "Admin":

    def _get_archival_statistics():
        stats = ArchivalService.get_archival_stats()
        log_info(f"Archival stats requested by user {current_user['user_id']}")
        return {"status": "success", "data": stats, "requested_by": current_user["user_id"]}

    return handle_business_operation(_get_archival_statistics, "archival statistics retrieval")


@router.get("/dashboard", response_model=dict[str, Any])
async def get_archival_dashboard_data(current_user: dict = Depends(get_current_user)):
    """
    Get archival dashboard with summary metrics and entity details.

    Requires admin permissions.
    """

    # TODO: Add admin role check
    def _get_archival_dashboard():
        dashboard = get_archival_dashboard()
        log_info(f"Archival dashboard requested by user {current_user['user_id']}")
        return dashboard

    return handle_business_operation(_get_archival_dashboard, "archival dashboard retrieval")


@router.get("/validate", response_model=dict[str, Any])
async def validate_archival_integrity(current_user: dict = Depends(get_current_user)):
    """
    Validate archival integrity across all entity types.

    Identifies records that should be archived but aren't.
    Requires admin permissions.
    """

    # TODO: Add admin role check
    def _validate_archival_integrity():
        validation_results = run_archival_validation()
        log_info(f"Archival validation requested by user {current_user['user_id']}")
        return validation_results

    return handle_business_operation(_validate_archival_integrity, "archival integrity validation")


@router.post("/run-manual", response_model=dict[str, Any])
async def run_manual_archival(current_user: dict = Depends(get_current_user)):
    """
    Manually trigger the archival process for all entity types.

    This runs the same process as the scheduled cron job.
    Requires admin permissions.
    """

    # TODO: Add admin role check
    def _run_manual_archival():
        log_info(f"Manual archival triggered by user {current_user['user_id']}")
        results = run_daily_archival()
        return {"triggered_by": current_user["user_id"], **results}

    return handle_business_operation(_run_manual_archival, "manual archival execution")


@router.get("/eligible/{entity_type}", response_model=dict[str, Any])
async def get_eligible_records(entity_type: str, current_user: dict = Depends(get_current_user)):
    """
    Get records eligible for archival for a specific entity type.

    Args:
        entity_type: Type of entity (orders, transactions, etc.)

    Requires admin permissions.
    """

    # TODO: Add admin role check
    def _get_eligible_records():
        eligible_records = ArchivalService.get_eligible_for_archival(entity_type)
        log_info(f"Eligible records for {entity_type} requested by user {current_user['user_id']}")

        return {
            "entity_type": entity_type,
            "eligible_count": len(eligible_records),
            "retention_period_days": ArchivalService.get_retention_period(entity_type),
            "records": eligible_records[:100],  # Limit to first 100 for display
            "total_eligible": len(eligible_records),
        }

    return handle_business_operation(_get_eligible_records, "eligible records retrieval")


@router.post("/archive/{entity_type}", response_model=dict[str, Any])
async def archive_specific_records(
    entity_type: str,
    record_ids: list[UUID],
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
):
    """
    Archive specific records for an entity type.

    Args:
        entity_type: Type of entity (orders, transactions, etc.)
        record_ids: List of record IDs to archive

    Requires admin permissions.
    """
    # TODO: Add admin role check
    if not record_ids:
        raise envelope_exception(ErrorCode.ARCHIVAL_NO_RECORDS_PROVIDED, status=400, locale=locale)

    if len(record_ids) > 1000:
        raise envelope_exception(ErrorCode.ARCHIVAL_TOO_MANY_RECORDS, status=400, locale=locale)

    # Archive specific records for an entity type
    def _archive_specific_records():
        archived_count = ArchivalService.archive_records(entity_type, record_ids, current_user["user_id"])

        log_info(
            f"Manual archival of {len(record_ids)} {entity_type} records by user {current_user['user_id']}: {archived_count} archived"
        )

        return {
            "entity_type": entity_type,
            "requested_count": len(record_ids),
            "archived_count": archived_count,
            "success_rate": round((archived_count / len(record_ids)) * 100, 2),
            "archived_by": current_user["user_id"],
        }

    return handle_business_operation(_archive_specific_records, "specific records archival")


@router.get("/retention-policy", response_model=dict[str, Any])
async def get_retention_policy(current_user: dict = Depends(get_current_user)):
    """
    Get current retention policy configuration.

    Requires admin permissions.
    """

    # TODO: Add admin role check
    def _get_retention_policy():
        from app.config.settings import settings

        policy = {
            "retention_periods": settings.RETENTION_PERIODS,
            "grace_period_days": settings.ARCHIVAL_GRACE_PERIOD,
            "auto_archival_enabled": settings.AUTO_ARCHIVAL_ENABLED,
        }

        return {"status": "success", "policy": policy, "note": "Retention periods are in days"}

    return handle_business_operation(_get_retention_policy, "retention policy retrieval")


@router.get("/health", response_model=dict[str, Any])
async def archival_health_check():
    """
    Health check endpoint for archival system.

    Can be used by monitoring systems to check archival status.
    Does not require authentication.
    """

    # Health check endpoint for archival system
    def _archival_health_check():
        # Quick validation check
        validation_results = ArchivalService.validate_archival_integrity()

        # Count issues
        issues = []
        for entity_type, result in validation_results.items():
            if result.get("status") == "needs_attention":
                issues.append(f"{entity_type}: {result.get('overdue_for_archival', 0)} overdue")
            elif "error" in result:
                issues.append(f"{entity_type}: error")

        health_status = "healthy" if not issues else "degraded"

        return {
            "status": health_status,
            "issues": issues,
            "issue_count": len(issues),
            "checked_at": ArchivalService.get_archival_stats(),
        }

    return handle_business_operation(_archival_health_check, "archival health check")
