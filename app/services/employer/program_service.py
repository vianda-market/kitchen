"""Employer Benefits Program configuration service.

Supports three-tier cascade: entity override → institution default.
See docs/plans/MULTINATIONAL_INSTITUTIONS.md
"""

from typing import Any
from uuid import UUID

import psycopg2.extensions
import psycopg2.extras

from app.dto.models import EmployerBenefitsProgramDTO
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.services.crud_service import (
    employer_benefits_program_service,
    institution_service,
)
from app.utils.db import db_read
from app.utils.log import log_info


def create_program(
    data: dict[str, Any],
    db: psycopg2.extensions.connection,
    modified_by: UUID,
    locale: str = "en",
) -> EmployerBenefitsProgramDTO:
    """Create a benefits program for an Employer institution.

    If institution_entity_id is provided, creates an entity-level override.
    If omitted/None, creates institution-level defaults.
    """
    institution_id = data.get("institution_id")
    if not institution_id:
        raise envelope_exception(
            ErrorCode.VALIDATION_FIELD_REQUIRED,
            status=400,
            locale=locale,
        )

    institution = institution_service.get_by_id(institution_id, db, scope=None)
    if not institution:
        raise envelope_exception(
            ErrorCode.ENTITY_NOT_FOUND,
            status=404,
            locale=locale,
            entity="Institution",
        )
    inst_type = getattr(institution, "institution_type", None)
    inst_type_str = inst_type.value if hasattr(inst_type, "value") else str(inst_type)
    if inst_type_str != "employer":
        raise envelope_exception(
            ErrorCode.SECURITY_INSTITUTION_TYPE_MISMATCH,
            status=400,
            locale=locale,
        )

    entity_id = data.get("institution_entity_id")
    existing = _get_program_row(institution_id, entity_id, db)
    if existing:
        scope_label = f"entity {entity_id}" if entity_id else "institution"
        raise envelope_exception(
            ErrorCode.EMPLOYER_PROGRAM_ALREADY_EXISTS,
            status=409,
            locale=locale,
            scope=scope_label,
        )

    data["modified_by"] = str(modified_by)
    program = employer_benefits_program_service.create(data, db, scope=None)
    if not program:
        raise envelope_exception(ErrorCode.EMPLOYER_BENEFITS_PROGRAM_CREATION_FAILED, status=500, locale="en")
    log_info(
        f"Created employer benefits program {program.program_id} for institution {institution_id}"
        f" (entity={entity_id or 'institution-level'})"
    )
    return program


def get_program_by_institution(
    institution_id: UUID,
    db: psycopg2.extensions.connection,
) -> EmployerBenefitsProgramDTO | None:
    """Get the institution-level default program (entity IS NULL), or None."""
    return _get_program_row(institution_id, None, db)


def get_program_by_scope(
    institution_id: UUID,
    institution_entity_id: UUID | None,
    db: psycopg2.extensions.connection,
) -> EmployerBenefitsProgramDTO | None:
    """Get program by exact (institution, entity) scope.

    entity_id=None fetches the institution-level default (IS NULL).
    """
    return _get_program_row(institution_id, institution_entity_id, db)


def resolve_effective_program(
    institution_id: UUID,
    institution_entity_id: UUID | None,
    db: psycopg2.extensions.connection,
) -> EmployerBenefitsProgramDTO | None:
    """Resolve the effective program for an entity via two-tier cascade.

    1. Entity-level program (institution_id + entity_id) — if exists, return it
    2. Institution-level default (institution_id + entity IS NULL) — fallback

    For single-market employers (one entity, no entity-level override), this
    returns the institution-level default.
    """
    if institution_entity_id:
        entity_program = _get_program_row(institution_id, institution_entity_id, db)
        if entity_program:
            return entity_program
    return _get_program_row(institution_id, None, db)


def get_all_programs_for_institution(
    institution_id: UUID,
    db: psycopg2.extensions.connection,
) -> list:
    """Get all program rows for an institution (institution-level + all entity overrides)."""
    return employer_benefits_program_service.get_all_by_field("institution_id", institution_id, db, scope=None)


def update_program(
    program_id: UUID,
    updates: dict[str, Any],
    db: psycopg2.extensions.connection,
    modified_by: UUID,
    locale: str = "en",
) -> EmployerBenefitsProgramDTO:
    """Update a benefits program."""
    updates["modified_by"] = str(modified_by)
    updated = employer_benefits_program_service.update(program_id, updates, db, scope=None)
    if not updated:
        raise envelope_exception(
            ErrorCode.EMPLOYER_BENEFIT_PROGRAM_NOT_FOUND,
            status=404,
            locale=locale,
        )
    log_info(f"Updated employer benefits program {program_id}")
    return updated


def upsert_program_by_canonical_key(
    canonical_key: str,
    data: dict[str, Any],
    db: psycopg2.extensions.connection,
    modified_by: UUID,
    locale: str = "en",
) -> EmployerBenefitsProgramDTO:
    """Idempotent upsert a benefits program by canonical_key.

    INTERNAL SEED/FIXTURE ONLY. Never use for production program creation.

    INSERT path: validates institution is Employer-type, then inserts a new
    program row with the canonical_key stamped.

    UPDATE path: finds the existing row by canonical_key and updates all
    mutable fields. institution_id and institution_entity_id are immutable
    after creation.

    Returns HTTP 200 on both insert and update.
    """
    institution_id = data.get("institution_id")
    if not institution_id:
        raise envelope_exception(ErrorCode.VALIDATION_FIELD_REQUIRED, status=400, locale=locale)

    # Validate institution exists and is Employer-type
    institution = institution_service.get_by_id(institution_id, db, scope=None)
    if not institution:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Institution")
    inst_type = getattr(institution, "institution_type", None)
    inst_type_str = inst_type.value if hasattr(inst_type, "value") else str(inst_type)
    if inst_type_str != "employer":
        raise envelope_exception(ErrorCode.SECURITY_INSTITUTION_TYPE_MISMATCH, status=400, locale=locale)

    # Check for existing row by canonical_key
    existing = _get_program_by_canonical_key(canonical_key, db)

    if existing is not None:
        # UPDATE path — institution_id and institution_entity_id are immutable
        mutable_fields = {
            "benefit_rate",
            "benefit_cap",
            "benefit_cap_period",
            "price_discount",
            "minimum_monthly_fee",
            "billing_cycle",
            "billing_day",
            "enrollment_mode",
            "allow_early_renewal",
            "is_active",
        }
        updates = {k: v for k, v in data.items() if k in mutable_fields and v is not None}
        updates["modified_by"] = str(modified_by)
        updated = employer_benefits_program_service.update(existing.program_id, updates, db, scope=None)
        if not updated:
            raise envelope_exception(ErrorCode.EMPLOYER_BENEFIT_PROGRAM_NOT_FOUND, status=404, locale=locale)
        log_info(f"upsert_program_by_canonical_key: updated program {existing.program_id} (key={canonical_key})")
        return updated
    # INSERT path
    insert_data = dict(data)
    insert_data["canonical_key"] = canonical_key
    insert_data["modified_by"] = str(modified_by)
    # Strip None values to let DB defaults take effect
    insert_data = {
        k: v
        for k, v in insert_data.items()
        if v is not None or k in {"institution_entity_id", "benefit_cap", "minimum_monthly_fee", "billing_day"}
    }
    program = employer_benefits_program_service.create(insert_data, db, scope=None)
    if not program:
        raise envelope_exception(ErrorCode.EMPLOYER_BENEFITS_PROGRAM_CREATION_FAILED, status=500, locale="en")
    log_info(f"upsert_program_by_canonical_key: created program {program.program_id} (key={canonical_key})")
    return program


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _get_program_by_canonical_key(
    canonical_key: str,
    db: psycopg2.extensions.connection,
) -> EmployerBenefitsProgramDTO | None:
    """Fetch a program row by canonical_key, or None if not found."""
    row = db_read(
        "SELECT * FROM employer_benefits_program WHERE canonical_key = %s AND is_archived = FALSE",
        (canonical_key,),
        connection=db,
        fetch_one=True,
    )
    if not row:
        return None
    return EmployerBenefitsProgramDTO(**row)


def _get_program_row(
    institution_id: UUID,
    institution_entity_id: UUID | None,
    db: psycopg2.extensions.connection,
) -> EmployerBenefitsProgramDTO | None:
    """Fetch a specific program row by (institution, entity) scope.

    entity_id=None fetches the institution-level default (IS NULL).
    """
    if institution_entity_id is not None:
        row = db_read(
            "SELECT * FROM employer_benefits_program "
            "WHERE institution_id = %s AND institution_entity_id = %s "
            "AND is_active = TRUE AND is_archived = FALSE",
            (str(institution_id), str(institution_entity_id)),
            connection=db,
            fetch_one=True,
        )
    else:
        row = db_read(
            "SELECT * FROM employer_benefits_program "
            "WHERE institution_id = %s AND institution_entity_id IS NULL "
            "AND is_active = TRUE AND is_archived = FALSE",
            (str(institution_id),),
            connection=db,
            fetch_one=True,
        )
    if not row:
        return None
    return EmployerBenefitsProgramDTO(**row)
