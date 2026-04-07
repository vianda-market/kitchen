"""
Admin Cuisines API — CRUD for cuisine management and suggestion review.

Internal-only endpoints for managing the canonical cuisine list
and reviewing supplier suggestions.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg2.extensions import connection

from app.auth.dependencies import get_admin_user
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import (
    CuisineCreateSchema,
    CuisineUpdateSchema,
    CuisineDetailResponseSchema,
    CuisineSuggestionResponseSchema,
    CuisineSuggestionApproveSchema,
    CuisineSuggestionRejectSchema,
)
from app.services.crud_service import cuisine_crud_service
from app.services import cuisine_service

router = APIRouter(prefix="/admin/cuisines", tags=["Admin Cuisines"])


# ---- Cuisine CRUD ----

@router.post("", response_model=CuisineDetailResponseSchema, status_code=201)
def create_cuisine(
    data: CuisineCreateSchema,
    current_user: dict = Depends(get_admin_user),
    db: connection = Depends(get_db),
):
    """Create a new cuisine. Auto-generates slug from cuisine_name if not provided."""
    create_data = data.model_dump(exclude_unset=True)
    user_id = current_user["user_id"]
    create_data["modified_by"] = user_id
    create_data["created_by"] = user_id
    create_data["origin_source"] = "supplier"

    if not create_data.get("slug"):
        create_data["slug"] = cuisine_service._generate_slug(data.cuisine_name, db)

    result = cuisine_crud_service.create(create_data, db)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create cuisine")
    return result


@router.get("", response_model=List[CuisineDetailResponseSchema])
def list_all_cuisines(
    current_user: dict = Depends(get_admin_user),
    db: connection = Depends(get_db),
):
    """List all cuisines including archived (admin view)."""
    rows = cuisine_service.search_cuisines(db, include_archived=True)
    return [CuisineDetailResponseSchema(**row) for row in rows]


@router.get("/suggestions", response_model=List[CuisineSuggestionResponseSchema])
def list_pending_suggestions(
    current_user: dict = Depends(get_admin_user),
    db: connection = Depends(get_db),
):
    """List all Pending cuisine suggestions awaiting review."""
    rows = cuisine_service.get_pending_suggestions(db)
    return [CuisineSuggestionResponseSchema(**row) for row in rows]


@router.get("/{cuisine_id}", response_model=CuisineDetailResponseSchema)
def get_cuisine(
    cuisine_id: UUID,
    current_user: dict = Depends(get_admin_user),
    db: connection = Depends(get_db),
):
    """Get a single cuisine with full detail."""
    result = cuisine_crud_service.get_by_id(cuisine_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="Cuisine not found")
    return result


@router.put("/{cuisine_id}", response_model=CuisineDetailResponseSchema)
def update_cuisine(
    cuisine_id: UUID,
    data: CuisineUpdateSchema,
    current_user: dict = Depends(get_admin_user),
    db: connection = Depends(get_db),
):
    """Update a cuisine (name, slug, parent, description, i18n, display_order)."""
    update_data = data.model_dump(exclude_unset=True)
    update_data["modified_by"] = current_user["user_id"]
    result = cuisine_crud_service.update(cuisine_id, update_data, db)
    if not result:
        raise HTTPException(status_code=404, detail="Cuisine not found")
    return result


@router.delete("/{cuisine_id}", response_model=CuisineDetailResponseSchema)
def soft_delete_cuisine(
    cuisine_id: UUID,
    current_user: dict = Depends(get_admin_user),
    db: connection = Depends(get_db),
):
    """Soft-delete a cuisine (set is_archived=true, status=Inactive)."""
    update_data = {
        "is_archived": True,
        "status": "Inactive",
        "modified_by": current_user["user_id"],
    }
    result = cuisine_crud_service.update(cuisine_id, update_data, db)
    if not result:
        raise HTTPException(status_code=404, detail="Cuisine not found")
    return result


# ---- Suggestion Review ----

@router.put("/suggestions/{suggestion_id}/approve", response_model=CuisineSuggestionResponseSchema)
def approve_suggestion(
    suggestion_id: UUID,
    data: CuisineSuggestionApproveSchema,
    current_user: dict = Depends(get_admin_user),
    db: connection = Depends(get_db),
):
    """
    Approve a Pending cuisine suggestion.

    If resolved_cuisine_id is provided, maps suggestion to existing cuisine.
    If null, creates a new cuisine from the suggested name.
    Updates the originating restaurant's cuisine_id if present.
    """
    reviewer_id = UUID(current_user["user_id"])
    result = cuisine_service.approve_suggestion(
        suggestion_id=suggestion_id,
        reviewer_id=reviewer_id,
        resolved_cuisine_id=data.resolved_cuisine_id,
        review_notes=data.review_notes,
        db=db,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Suggestion not found or already reviewed")
    return CuisineSuggestionResponseSchema(**result)


@router.put("/suggestions/{suggestion_id}/reject", response_model=CuisineSuggestionResponseSchema)
def reject_suggestion(
    suggestion_id: UUID,
    data: CuisineSuggestionRejectSchema,
    current_user: dict = Depends(get_admin_user),
    db: connection = Depends(get_db),
):
    """Reject a Pending cuisine suggestion with optional review notes."""
    reviewer_id = UUID(current_user["user_id"])
    result = cuisine_service.reject_suggestion(
        suggestion_id=suggestion_id,
        reviewer_id=reviewer_id,
        review_notes=data.review_notes,
        db=db,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Suggestion not found or already reviewed")
    return CuisineSuggestionResponseSchema(**result)
