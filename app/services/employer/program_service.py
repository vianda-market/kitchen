"""Employer Benefits Program configuration service."""
from typing import Optional, Dict, Any
from uuid import UUID
import psycopg2.extensions
from fastapi import HTTPException, status

from app.services.crud_service import (
    employer_benefits_program_service,
    institution_service,
)
from app.dto.models import EmployerBenefitsProgramDTO
from app.utils.log import log_info


def create_program(
    data: Dict[str, Any],
    db: psycopg2.extensions.connection,
    modified_by: UUID,
) -> EmployerBenefitsProgramDTO:
    """Create a benefits program for an Employer institution."""
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

    existing = get_program_by_institution(institution_id, db)
    if existing:
        raise HTTPException(
            status_code=409,
            detail="A benefits program already exists for this institution",
        )

    data["modified_by"] = str(modified_by)
    program = employer_benefits_program_service.create(data, db, scope=None)
    if not program:
        raise HTTPException(status_code=500, detail="Failed to create benefits program")
    log_info(f"Created employer benefits program {program.program_id} for institution {institution_id}")
    return program


def get_program_by_institution(
    institution_id: UUID,
    db: psycopg2.extensions.connection,
) -> Optional[EmployerBenefitsProgramDTO]:
    """Get the benefits program for an institution, or None."""
    results = employer_benefits_program_service.get_all(
        db,
        scope=None,
        additional_conditions=[("institution_id = %s::uuid", str(institution_id))],
    )
    return results[0] if results else None


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
