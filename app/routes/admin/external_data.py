"""
Admin External Data API — GeoNames picker endpoints.

Read-only endpoints for the superadmin city/country promotion UI.
Queries raw GeoNames tables in the `external` schema.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from psycopg2.extensions import connection
from pydantic import BaseModel

from app.auth.dependencies import get_super_admin_user
from app.dependencies.database import get_db
from app.utils.db import db_read

router = APIRouter(prefix="/admin/external", tags=["Admin: External Data"])


# ---------------------------------------------------------------------------
# Response schemas (admin-only, not in consolidated_schemas.py)
# ---------------------------------------------------------------------------


class GeonamesCountryResponse(BaseModel):
    iso_alpha2: str
    name: str
    population: int | None = None
    continent: str | None = None


class GeonamesProvinceResponse(BaseModel):
    admin1_full_code: str
    country_iso: str
    name: str
    ascii_name: str | None = None
    geonames_id: int | None = None


class GeonamesCityResponse(BaseModel):
    geonames_id: int
    name: str
    ascii_name: str | None = None
    country_iso: str
    admin1_code: str | None = None
    population: int | None = None
    timezone: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/countries", response_model=list[GeonamesCountryResponse])
async def list_geonames_countries(
    current_user: dict[str, Any] = Depends(get_super_admin_user),
    db: connection = Depends(get_db),
) -> Any:
    """
    List all countries from external.geonames_country.

    **Authorization:** Super Admin only.
    """
    rows = db_read(
        """
        SELECT iso_alpha2, name, population, continent
        FROM external.geonames_country
        ORDER BY name ASC
        """,
        connection=db,
    )
    return rows


@router.get("/provinces", response_model=list[GeonamesProvinceResponse])
async def list_geonames_provinces(
    country_iso: str = Query(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code"),
    current_user: dict[str, Any] = Depends(get_super_admin_user),
    db: connection = Depends(get_db),
) -> Any:
    """
    List admin1 provinces for a given country from external.geonames_admin1.

    **Authorization:** Super Admin only.
    """
    rows = db_read(
        """
        SELECT admin1_full_code, country_iso, name, ascii_name, geonames_id
        FROM external.geonames_admin1
        WHERE country_iso = %s
        ORDER BY name ASC
        """,
        values=(country_iso.upper(),),
        connection=db,
    )
    return rows


@router.get("/cities", response_model=list[GeonamesCityResponse])
async def list_geonames_cities(
    country_iso: str = Query(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code"),
    admin1_code: str | None = Query(None, description="Admin1 code to filter provinces"),
    q: str | None = Query(None, description="Search string (matches ascii_name, case-insensitive)"),
    current_user: dict[str, Any] = Depends(get_super_admin_user),
    db: connection = Depends(get_db),
) -> Any:
    """
    List cities for a given country from external.geonames_city.

    Supports optional province filter and name search. Capped at 200 rows.

    **Authorization:** Super Admin only.
    """
    clauses = ["country_iso = %s"]
    params: list = [country_iso.upper()]

    if admin1_code is not None:
        clauses.append("admin1_code = %s")
        params.append(admin1_code)

    if q is not None:
        clauses.append("LOWER(ascii_name) LIKE LOWER(%s)")
        params.append(f"%{q}%")

    where = " AND ".join(clauses)

    rows = db_read(
        f"""
        SELECT geonames_id, name, ascii_name, country_iso, admin1_code, population, timezone
        FROM external.geonames_city
        WHERE {where}
        ORDER BY population DESC NULLS LAST, name ASC
        LIMIT 200
        """,
        values=tuple(params),
        connection=db,
    )
    return rows
