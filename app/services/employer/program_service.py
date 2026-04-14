"""Employer Benefits Program configuration service.

Supports three-tier cascade: entity override → institution default.
See docs/plans/MULTINATIONAL_INSTITUTIONS.md
"""
from typing import Optional, Dict, Any
from uuid import UUID
import psycopg2.extensions
from fastapi import HTTPException, status

from app.services.crud_service import (
    employer_benefits_program_service,
    institution_service,
)
from app.dto.models import EmployerBenefitsProgramDTO
from app.utils.db import db_read
from app.utils.log import log_info


def create_program(
    data: Dict[str, Any],
    db: psycopg2.extensions.connection,
    modified_by: UUID,
) -> EmployerBenefitsProgramDTO:
    """Create a benefits program for an Employer institution.

    If institution_entity_id is provided, creates an entity-level override.
    If omitted/None, creates institution-level defaults.
    """
    institution_id = data.get("institution_id")
    if not institution_id:
        raise HTTPException(status_code=400, detail="institution_id is required")

    institution = institution_service.get_by_id(institution_id, db, scope=None)
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")
    inst_type = getattr(institution, "institution_type", None)
    inst_type_str = inst_type.value if hasattr(inst_type, "value") else str(inst_type)
    if inst_type_str != "employer":
        raise HTTPException(
            status_code=400,
            detail=f"Institution must be of type 'employer', got '{inst_type_str}'",
        )

    entity_id = data.get("institution_entity_id")
    existing = _get_program_row(institution_id, entity_id, db)
    if existing:
        scope_label = f"entity {entity_id}" if entity_id else "institution"
        raise HTTPException(
            status_code=409,
            detail=f"A benefits program already exists for this {scope_label}",
        )

    data["modified_by"] = str(modified_by)
    program = employer_benefits_program_service.create(data, db, scope=None)
    if not program:
        raise HTTPException(status_code=500, detail="Failed to create benefits program")
    log_info(f"Created employer benefits program {program.program_id} for institution {institution_id}"
             f" (entity={entity_id or 'institution-level'})")
    return program


def get_program_by_institution(
    institution_id: UUID,
    db: psycopg2.extensions.connection,
) -> Optional[EmployerBenefitsProgramDTO]:
    """Get the institution-level default program (entity IS NULL), or None."""
    return _get_program_row(institution_id, None, db)


def get_program_by_scope(
    institution_id: UUID,
    institution_entity_id: Optional[UUID],
    db: psycopg2.extensions.connection,
) -> Optional[EmployerBenefitsProgramDTO]:
    """Get program by exact (institution, entity) scope.

    entity_id=None fetches the institution-level default (IS NULL).
    """
    return _get_program_row(institution_id, institution_entity_id, db)


def resolve_effective_program(
    institution_id: UUID,
    institution_entity_id: Optional[UUID],
    db: psycopg2.extensions.connection,
) -> Optional[EmployerBenefitsProgramDTO]:
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
    return employer_benefits_program_service.get_all_by_field(
        "institution_id", institution_id, db, scope=None
    )


def update_program(
    program_id: UUID,
    updates: Dict[str, Any],
    db: psycopg2.extensions.connection,
    modified_by: UUID,
) -> EmployerBenefitsProgramDTO:
    """Update a benefits program."""
    updates["modified_by"] = str(modified_by)
    updated = employer_benefits_program_service.update(program_id, updates, db, scope=None)
    if not updated:
        raise HTTPException(status_code=404, detail="Program not found")
    log_info(f"Updated employer benefits program {program_id}")
    return updated


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _get_program_row(
    institution_id: UUID,
    institution_entity_id: Optional[UUID],
    db: psycopg2.extensions.connection,
) -> Optional[EmployerBenefitsProgramDTO]:
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
