"""Locales route — public, cacheable endpoint exposing supported locales."""

from fastapi import APIRouter, Response

from app.config.settings import settings

router = APIRouter(prefix="/locales", tags=["Locales"])


@router.get("")
async def list_locales(response: Response):
    """
    Public list of supported locales and the platform default.

    **No authentication required.** Cached for 24 hours.

    Used by all clients for:
    - Language picker / locale toggle rendering
    - Multi-locale content authoring (B2B admin forms)
    - Determining which locale inputs to render
    """
    response.headers["Cache-Control"] = "public, max-age=86400"
    return {
        "supported": settings.SUPPORTED_LOCALES,
        "default": settings.DEFAULT_LOCALE,
    }
