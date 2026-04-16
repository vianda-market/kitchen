"""
Supplier stall detection cron job.

Daily job: find active Supplier institutions that have stalled during onboarding
and send escalating email outreach. Respects suppression windows to avoid spam.

Rules:
  - not_started + 2d since creation  → getting_started email
  - in_progress + 3d no activity     → need_help email
  - in_progress + 7d no activity     → incomplete email
  - in_progress + 14d no activity    → log manual escalation (no email)
  - just became complete              → celebration email (only if previously nudged)

Suppression:
  - Max 1 email per 3-day window (auto cooldown after each send)
  - Manual override via support_email_suppressed_until on institution_info
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.services.email_service import email_service
from app.services.onboarding_service import (
    NEXT_STEP_LABELS,
    SUPPLIER_CHECKLIST_ORDER,
    get_onboarding_status,
)
from app.utils.db import close_db_connection, db_read, db_update, get_db_connection
from app.utils.log import log_error, log_info, log_warning

SYSTEM_USER_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

# Cooldown: minimum days between outreach emails to the same institution
EMAIL_COOLDOWN_DAYS = 3


def _get_supplier_admin_email(institution_id: UUID, connection) -> str | None:
    """Find the Supplier Admin's email for an institution."""
    row = db_read(
        """
        SELECT email FROM core.user_info
        WHERE institution_id = %s
          AND role_type = 'supplier' AND role_name = 'admin'
          AND status = 'active' AND NOT is_archived
        ORDER BY created_date ASC
        LIMIT 1
        """,
        (str(institution_id),),
        connection=connection,
        fetch_one=True,
    )
    return row["email"] if row else None


def _is_suppressed(institution: dict, now: datetime) -> bool:
    """Check if the institution is within a suppression window."""
    suppressed_until = institution.get("support_email_suppressed_until")
    if suppressed_until and suppressed_until > now:
        return True

    last_email = institution.get("last_support_email_date")
    if last_email:
        if last_email.tzinfo is None:
            last_email = last_email.replace(tzinfo=UTC)
        if (now - last_email).days < EMAIL_COOLDOWN_DAYS:
            return True

    return False


def _record_email_sent(institution_id: UUID, now: datetime, connection) -> None:
    """Update institution with email tracking fields after sending."""
    cooldown_until = now + timedelta(days=EMAIL_COOLDOWN_DAYS)
    db_update(
        "core.institution_info",
        {
            "last_support_email_date": now,
            "support_email_suppressed_until": cooldown_until,
            "modified_by": str(SYSTEM_USER_ID),
            "modified_date": now,
        },
        {"institution_id": str(institution_id)},
        connection,
        commit=True,
    )


def run_supplier_stall_detection() -> dict[str, Any]:
    """
    Detect stalled suppliers and send escalating onboarding emails.
    Returns a result dict with metrics for logging/monitoring.
    """
    now_utc = datetime.now(UTC)
    result: dict[str, Any] = {
        "cron_job": "supplier_stall_detection",
        "run_at_utc": now_utc.isoformat(),
        "institutions_checked": 0,
        "emails_sent": 0,
        "emails_suppressed": 0,
        "manual_escalations": 0,
        "celebrations_sent": 0,
        "errors": [],
        "success": True,
    }

    connection = get_db_connection()
    try:
        # Fetch all active Supplier institutions with suppression fields
        institutions = db_read(
            """
            SELECT institution_id, name, institution_type,
                   support_email_suppressed_until, last_support_email_date
            FROM core.institution_info
            WHERE institution_type = 'supplier'
              AND status = 'active'
              AND NOT is_archived
            """,
            connection=connection,
        )

        if not institutions:
            log_info("Stall detection: no active Supplier institutions found.")
            return result

        result["institutions_checked"] = len(institutions)

        for inst in institutions:
            inst_id = inst["institution_id"]
            inst_name = inst["name"]

            try:
                status = get_onboarding_status(inst_id, "supplier", connection)
                if not status:
                    continue

                onboarding_status = status["onboarding_status"]
                days_since_creation = status["days_since_creation"]
                days_since_last_activity = status["days_since_last_activity"]
                completion_pct = status["completion_percentage"]
                checklist = status["checklist"]

                # Skip complete institutions (unless celebration is due)
                if onboarding_status == "complete":
                    # Send celebration only if we previously sent outreach
                    if inst.get("last_support_email_date") is not None:
                        if not _is_suppressed(inst, now_utc):
                            admin_email = _get_supplier_admin_email(inst_id, connection)
                            if admin_email:
                                email_service.send_onboarding_complete_email(
                                    to_email=admin_email,
                                    institution_name=inst_name,
                                )
                                _record_email_sent(inst_id, now_utc, connection)
                                result["celebrations_sent"] += 1
                    continue

                # Check suppression
                if _is_suppressed(inst, now_utc):
                    result["emails_suppressed"] += 1
                    continue

                # Determine which email to send based on stall rules
                missing_steps = [NEXT_STEP_LABELS[k] for k in SUPPLIER_CHECKLIST_ORDER if not checklist.get(k, False)]

                email_type = None
                if onboarding_status == "not_started" and days_since_creation >= 2:
                    email_type = "getting_started"
                elif onboarding_status in ("in_progress", "stalled"):
                    if days_since_last_activity is not None:
                        if days_since_last_activity >= 14:
                            email_type = "manual_escalation"
                        elif days_since_last_activity >= 7:
                            email_type = "incomplete"
                        elif days_since_last_activity >= 3:
                            email_type = "need_help"

                if not email_type:
                    continue

                # Manual escalation — log only, no email
                if email_type == "manual_escalation":
                    log_warning(
                        f"Stall detection: MANUAL ESCALATION needed for {inst_name} "
                        f"(institution_id={inst_id}, days_inactive={days_since_last_activity}, "
                        f"completion={completion_pct}%, missing={missing_steps})"
                    )
                    result["manual_escalations"] += 1
                    continue

                # Find recipient
                admin_email = _get_supplier_admin_email(inst_id, connection)
                if not admin_email:
                    log_warning(f"Stall detection: no Supplier Admin email for {inst_name} ({inst_id})")
                    continue

                # Send the appropriate email
                sent = False
                if email_type == "getting_started":
                    sent = email_service.send_onboarding_getting_started_email(
                        to_email=admin_email,
                        institution_name=inst_name,
                    )
                elif email_type == "need_help":
                    sent = email_service.send_onboarding_need_help_email(
                        to_email=admin_email,
                        institution_name=inst_name,
                        completion_percentage=completion_pct,
                        missing_steps=missing_steps,
                    )
                elif email_type == "incomplete":
                    sent = email_service.send_onboarding_incomplete_email(
                        to_email=admin_email,
                        institution_name=inst_name,
                        completion_percentage=completion_pct,
                        missing_steps=missing_steps,
                    )

                if sent:
                    _record_email_sent(inst_id, now_utc, connection)
                    result["emails_sent"] += 1
                    log_info(f"Stall detection: sent {email_type} email to {admin_email} for {inst_name}")

            except Exception as e:
                log_error(f"Stall detection error for {inst_name} ({inst_id}): {e}")
                result["errors"].append(f"{inst_id}: {e}")
                result["success"] = False

        log_info(f"Stall detection cron completed: {result}")
        return result

    finally:
        close_db_connection(connection)
