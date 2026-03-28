"""Tests for Accept-Language parsing (app.utils.locale)."""

from app.config.settings import settings
from app.utils.locale import DEFAULT_LOCALE, resolve_locale_from_header


def test_resolve_locale_prefers_first_supported_tag():
    assert resolve_locale_from_header("es-AR,en;q=0.8") == "es"


def test_resolve_locale_falls_back_when_no_supported_tag():
    assert resolve_locale_from_header("fr-CH,de;q=0.9") == DEFAULT_LOCALE
    assert DEFAULT_LOCALE == settings.DEFAULT_LOCALE


def test_resolve_locale_empty_header_uses_default():
    assert resolve_locale_from_header(None) == DEFAULT_LOCALE
    assert resolve_locale_from_header("") == DEFAULT_LOCALE
