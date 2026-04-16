"""Locale resolution from Accept-Language and supported locales (see app.config.settings)."""

from app.config.settings import settings

SUPPORTED_LOCALES = frozenset(settings.SUPPORTED_LOCALES)
DEFAULT_LOCALE = settings.DEFAULT_LOCALE


def resolve_locale_from_header(accept_language: str | None) -> str:
    """
    Parse Accept-Language header and return best supported locale.
    e.g. 'es-AR,es;q=0.9,en;q=0.8' -> 'es'
    Falls back to DEFAULT_LOCALE if nothing matches.
    """
    if not accept_language:
        return DEFAULT_LOCALE
    for lang in accept_language.replace(" ", "").split(","):
        code = lang.split(";")[0].split("-")[0].lower()
        if code in SUPPORTED_LOCALES:
            return code
    return DEFAULT_LOCALE


def get_user_locale(user_id, db) -> str:
    """Fetch user's locale from DB; fallback to DEFAULT_LOCALE."""
    from app.utils.db import db_read

    row = db_read(
        "SELECT locale FROM user_info WHERE user_id = %s",
        (str(user_id),),
        connection=db,
        fetch_one=True,
    )
    locale = (row.get("locale") if row else None) or DEFAULT_LOCALE
    return locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE


def resolve_user_locale(
    current_user: dict | None,
    accept_language: str | None = None,
) -> str:
    """
    Resolve locale for unauthenticated context: Accept-Language then default.
    For authenticated requests, prefer get_resolved_locale dependency (DB user_info.locale).
    """
    if current_user:
        user_locale = current_user.get("locale")
        if user_locale and user_locale in SUPPORTED_LOCALES:
            return user_locale
    return resolve_locale_from_header(accept_language)
