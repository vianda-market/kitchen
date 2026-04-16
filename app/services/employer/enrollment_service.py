"""Employer Benefits Program enrollment service — single + bulk employee creation."""

import csv
import io
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg2.extensions
from fastapi import HTTPException

from app.auth.security import hash_password
from app.config import Status
from app.config.enums.subscription_status import SubscriptionStatus
from app.services.crud_service import subscription_service, user_service
from app.services.employer.program_service import resolve_effective_program
from app.services.subscription_action_service import cancel_subscription
from app.utils.db import db_read
from app.utils.log import log_error, log_info, log_warning

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def _email_exists(email: str, db: psycopg2.extensions.connection) -> bool:
    """Check if email already exists in user_info."""
    rows = db_read(
        "SELECT user_id FROM user_info WHERE email = %s AND is_archived = FALSE",
        (email.lower().strip(),),
        connection=db,
        fetch_one=True,
    )
    return rows is not None


def _create_benefit_employee(
    institution_id: UUID,
    employee_data: dict[str, Any],
    program,
    db: psycopg2.extensions.connection,
    modified_by: UUID,
):
    """Create a Customer Comensal user in the employer's institution. Returns the created user DTO."""
    random_password = secrets.token_urlsafe(32)
    hashed = hash_password(random_password)

    user_data = {
        "institution_id": str(institution_id),
        "role_type": "customer",
        "role_name": "comensal",
        "username": employee_data["email"].lower().strip(),
        "email": employee_data["email"].lower().strip(),
        "hashed_password": hashed,
        "first_name": employee_data.get("first_name", ""),
        "last_name": employee_data.get("last_name", ""),
        "mobile_number": employee_data.get("mobile_number"),
        "email_verified": False,
        "city_metadata_id": str(employee_data["city_metadata_id"]),
        "market_id": str(employee_data["market_id"]) if employee_data.get("market_id") else None,
        "locale": employee_data.get("locale", "en"),
        "modified_by": str(modified_by),
        "status": Status.ACTIVE.value,
    }

    created = user_service.create(user_data, db, scope=None)
    if not created:
        raise HTTPException(status_code=500, detail="Failed to create benefit employee")
    return created


def _send_invite(
    user_id: UUID, email: str, first_name: str | None, institution_id: UUID, db: psycopg2.extensions.connection
):
    """Send benefit employee invite email with app download links."""
    import secrets as _secrets

    import psycopg2.extras

    from app.config import Status
    from app.services.crud_service import institution_service
    from app.services.email_service import email_service

    try:
        institution = institution_service.get_by_id(institution_id, db, scope=None)
        employer_name = getattr(institution, "name", "your employer") if institution else "your employer"

        invite_expiry_hours = 24
        reset_code = str(_secrets.randbelow(1_000_000)).zfill(6)
        expiry_time = datetime.now(UTC) + timedelta(hours=invite_expiry_hours)
        with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                "UPDATE credential_recovery SET is_used = TRUE, is_archived = TRUE WHERE user_id = %s AND is_used = FALSE AND is_archived = FALSE",
                (str(user_id),),
            )
            cursor.execute(
                "INSERT INTO credential_recovery (user_id, recovery_code, token_expiry, is_used, status, is_archived) VALUES (%s, %s, %s, %s, %s, %s)",
                (str(user_id), reset_code, expiry_time, False, Status.ACTIVE.value, False),
            )
            db.commit()

        from app.utils.locale import get_user_locale

        email_service.send_benefit_employee_invite_email(
            to_email=email,
            reset_code=reset_code,
            user_first_name=first_name,
            employer_name=employer_name,
            expiry_hours=invite_expiry_hours,
            locale=get_user_locale(user_id, db),
        )
        log_info(f"Benefit employee invite email sent to {email}")
    except Exception as e:
        log_warning(f"Failed to send invite email to {email}: {e}")


def enroll_single_employee(
    institution_id: UUID,
    employee_data: dict[str, Any],
    db: psycopg2.extensions.connection,
    modified_by: UUID,
):
    """Enroll a single benefit employee. Creates user in employer institution and sends invite."""
    program = resolve_effective_program(institution_id, None, db)
    if not program or not program.is_active:
        raise HTTPException(status_code=400, detail="No active benefits program for this institution")

    email = employee_data.get("email", "").lower().strip()
    if not email or not EMAIL_REGEX.match(email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    if _email_exists(email, db):
        raise HTTPException(status_code=409, detail="Email already registered in the system")

    created = _create_benefit_employee(institution_id, employee_data, program, db, modified_by)
    _send_invite(created.user_id, created.email, created.first_name, institution_id, db)
    log_info(f"Enrolled benefit employee {created.user_id} in institution {institution_id}")
    return created


def enroll_bulk_employees(
    institution_id: UUID,
    csv_content: str,
    city_metadata_id: UUID,
    market_id: UUID,
    locale: str,
    db: psycopg2.extensions.connection,
    modified_by: UUID,
) -> dict[str, Any]:
    """Enroll employees from CSV. Never fails the batch on one bad row."""
    program = resolve_effective_program(institution_id, None, db)
    if not program or not program.is_active:
        raise HTTPException(status_code=400, detail="No active benefits program for this institution")

    reader = csv.DictReader(io.StringIO(csv_content))
    created: list[str] = []
    skipped: list[dict[str, str]] = []
    errors: list[dict[str, Any]] = []
    row_num = 0

    for row in reader:
        row_num += 1
        email = (row.get("email") or "").lower().strip()
        first_name = (row.get("first_name") or "").strip()
        last_name = (row.get("last_name") or "").strip()

        if not email:
            errors.append({"row": row_num, "email": "", "reason": "email is required"})
            continue
        if not EMAIL_REGEX.match(email):
            errors.append({"row": row_num, "email": email, "reason": "invalid email format"})
            continue
        if not first_name:
            errors.append({"row": row_num, "email": email, "reason": "first_name is required"})
            continue

        if _email_exists(email, db):
            skipped.append({"email": email, "reason": "email already registered"})
            continue

        try:
            employee_data = {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "city_metadata_id": city_metadata_id,
                "market_id": market_id,
                "locale": locale,
            }
            user = _create_benefit_employee(institution_id, employee_data, program, db, modified_by)
            _send_invite(user.user_id, user.email, user.first_name, institution_id, db)
            created.append(email)
        except Exception as e:
            log_error(f"Bulk enroll row {row_num} ({email}): {e}")
            errors.append({"row": row_num, "email": email, "reason": str(e)})

    log_info(
        f"Bulk enrollment for institution {institution_id}: created={len(created)}, skipped={len(skipped)}, errors={len(errors)}"
    )
    return {
        "created_count": len(created),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "created": created,
        "skipped": skipped,
        "errors": errors,
    }


def deactivate_employee(
    institution_id: UUID,
    user_id: UUID,
    db: psycopg2.extensions.connection,
    modified_by: UUID,
):
    """Deactivate a benefit employee — archive user and cancel active subscription."""
    user = user_service.get_by_id(user_id, db, scope=None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user_inst = str(getattr(user, "institution_id", ""))
    if user_inst != str(institution_id):
        raise HTTPException(status_code=403, detail="User does not belong to this institution")

    subscription = subscription_service.get_by_user(user_id, db)
    if subscription and subscription.subscription_status in (
        SubscriptionStatus.ACTIVE.value,
        SubscriptionStatus.ON_HOLD.value,
        SubscriptionStatus.PENDING.value,
    ):
        try:
            cancel_subscription(subscription.subscription_id, user_id, db)
        except Exception as e:
            log_warning(f"Could not cancel subscription for user {user_id}: {e}")

    user_service.update(
        user_id,
        {"is_archived": True, "status": Status.INACTIVE.value, "modified_by": str(modified_by)},
        db,
        scope=None,
    )
    log_info(f"Deactivated benefit employee {user_id} from institution {institution_id}")


def list_benefit_employees(
    institution_id: UUID,
    db: psycopg2.extensions.connection,
) -> list[dict[str, Any]]:
    """List benefit employees in an employer institution with subscription status."""
    rows = db_read(
        """
        SELECT
            u.user_id,
            u.email,
            u.first_name,
            u.last_name,
            u.mobile_number,
            u.status as user_status,
            s.subscription_id,
            s.subscription_status,
            p.name as plan_name,
            p.price as plan_price,
            s.balance,
            s.renewal_date,
            u.created_date
        FROM user_info u
        LEFT JOIN subscription_info s ON u.user_id = s.user_id AND s.is_archived = FALSE
        LEFT JOIN plan_info p ON s.plan_id = p.plan_id
        WHERE u.institution_id = %s::uuid
          AND u.role_type = 'customer'
          AND u.is_archived = FALSE
        ORDER BY u.created_date DESC
        """,
        (str(institution_id),),
        connection=db,
    )
    return rows or []


def subscribe_employee(
    institution_id: UUID,
    user_id: UUID,
    plan_id: UUID,
    db: psycopg2.extensions.connection,
    modified_by: UUID,
):
    """Subscribe a benefit employee to a plan with no payment (100% subsidy).
    Creates an active subscription immediately."""
    from app.services.crud_service import plan_service

    user = user_service.get_by_id(user_id, db, scope=None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if str(getattr(user, "institution_id", "")) != str(institution_id):
        raise HTTPException(status_code=403, detail="User does not belong to this institution")

    employer_entity_id = getattr(user, "employer_entity_id", None)
    program = resolve_effective_program(institution_id, employer_entity_id, db)
    if not program or not program.is_active:
        raise HTTPException(status_code=400, detail="No active benefits program for this institution")

    existing = subscription_service.get_by_user(user_id, db)
    if existing and existing.subscription_status in (
        SubscriptionStatus.ACTIVE.value,
        SubscriptionStatus.PENDING.value,
    ):
        raise HTTPException(status_code=409, detail="User already has an active or pending subscription")

    plan = plan_service.get_by_id(plan_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan_price = float(getattr(plan, "price", 0))
    benefit_rate = program.benefit_rate
    rate_amount = plan_price * (benefit_rate / 100)
    benefit_cap = float(program.benefit_cap) if program.benefit_cap is not None else None
    if benefit_cap is not None:
        employee_benefit = min(rate_amount, benefit_cap)
    else:
        employee_benefit = rate_amount
    employee_share = plan_price - employee_benefit

    if employee_share > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Employee share is ${employee_share:.2f}. For partial subsidy, the employee must subscribe through the app and pay their share via POST /subscriptions/with-payment.",
        )

    plan_credit = int(getattr(plan, "credit", 0))
    market_id = str(getattr(plan, "market_id", ""))

    early_threshold = None if not program.allow_early_renewal else 10

    subscription_data = {
        "user_id": str(user_id),
        "plan_id": str(plan_id),
        "market_id": market_id,
        "balance": plan_credit,
        "subscription_status": SubscriptionStatus.ACTIVE.value,
        "status": Status.ACTIVE.value,
        "early_renewal_threshold": early_threshold,
        "modified_by": str(modified_by),
    }

    subscription = subscription_service.create(subscription_data, db, scope=None)
    if not subscription:
        raise HTTPException(status_code=500, detail="Failed to create subscription")
    log_info(
        f"Created fully-subsidized subscription {subscription.subscription_id} "
        f"for user {user_id} in institution {institution_id} (plan={plan_id}, credits={plan_credit})"
    )
    return subscription


def migrate_existing_users_for_domain(
    domain: str,
    institution_id: UUID,
    db: psycopg2.extensions.connection,
    modified_by: UUID,
) -> int:
    """Migrate existing Customer Comensals with matching email domain from Vianda Customers to the employer institution.
    Returns count of migrated users."""
    from app.config.settings import get_vianda_customers_institution_id

    vianda_customers_id = get_vianda_customers_institution_id()

    rows = db_read(
        """
        SELECT user_id FROM user_info
        WHERE email LIKE %s
          AND institution_id = %s::uuid
          AND role_type = 'customer'
          AND is_archived = FALSE
        """,
        (f"%@{domain.lower()}", str(vianda_customers_id)),
        connection=db,
    )
    if not rows:
        return 0

    program = resolve_effective_program(institution_id, None, db)
    early_threshold = None if (program and not program.allow_early_renewal) else 10

    count = 0
    for row in rows:
        uid = row["user_id"]
        update_data = {
            "institution_id": str(institution_id),
            "modified_by": str(modified_by),
        }
        user_service.update(uid, update_data, db, scope=None)

        if early_threshold is None:
            sub = subscription_service.get_by_user(uid, db)
            if sub:
                subscription_service.update(
                    sub.subscription_id,
                    {"early_renewal_threshold": None, "modified_by": str(modified_by)},
                    db,
                    scope=None,
                )
        count += 1

    log_info(f"Migrated {count} existing users for domain '{domain}' to institution {institution_id}")
    return count
