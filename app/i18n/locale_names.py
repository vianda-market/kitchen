"""Locale-aware name resolution: countries, currencies, and cuisine i18n."""

import gettext

import pycountry

from app.config.settings import settings

# Eagerly load gettext translation objects for each supported locale.
# pycountry ships .mo files for iso3166-1 (countries) and iso4217 (currencies).
_country_translators: dict[str, gettext.GNUTranslations] = {}
_currency_translators: dict[str, gettext.GNUTranslations] = {}

for _locale in settings.SUPPORTED_LOCALES:
    if _locale == "en":
        continue
    try:
        _country_translators[_locale] = gettext.translation("iso3166-1", pycountry.LOCALES_DIR, languages=[_locale])
    except FileNotFoundError:
        pass
    try:
        _currency_translators[_locale] = gettext.translation("iso4217", pycountry.LOCALES_DIR, languages=[_locale])
    except FileNotFoundError:
        pass


def localize_country_name(country_code: str, locale: str) -> str:
    """Translate country name for the given locale using pycountry gettext.

    Falls back to the English name if no translation is available.
    """
    country = pycountry.countries.get(alpha_2=country_code.upper())
    if country is None:
        return country_code
    english_name = country.name
    if locale == "en":
        return english_name
    translator = _country_translators.get(locale)
    if translator is None:
        return english_name
    return translator.gettext(english_name)


def localize_currency_name(currency_code: str, locale: str) -> str:
    """Translate currency name for the given locale using pycountry gettext.

    Falls back to the English name if no translation is available.
    """
    currency = pycountry.currencies.get(alpha_3=currency_code.upper())
    if currency is None:
        return currency_code
    english_name = currency.name
    if locale == "en":
        return english_name
    translator = _currency_translators.get(locale)
    if translator is None:
        return english_name
    return translator.gettext(english_name)


def resolve_i18n_field(obj, field_name: str, locale: str):
    """Resolve obj.field_name from obj.field_name_i18n if locale translation exists."""
    if locale == "en":
        return
    i18n = getattr(obj, f"{field_name}_i18n", None)
    if i18n and locale in i18n:
        setattr(obj, field_name, i18n[locale])


def resolve_i18n_list_field(obj, field_name: str, locale: str):
    """Resolve array field from field_name_i18n JSONB if locale exists."""
    if locale == "en":
        return
    i18n = getattr(obj, f"{field_name}_i18n", None)
    if i18n and locale in i18n:
        setattr(obj, field_name, i18n[locale])


def resolve_i18n_field_aliased(obj, display_field: str, i18n_field: str, locale: str):
    """Resolve obj.display_field from obj.i18n_field when field names differ (e.g. product_name vs name_i18n)."""
    if locale == "en":
        return
    i18n = getattr(obj, i18n_field, None)
    if i18n and locale in i18n:
        setattr(obj, display_field, i18n[locale])


def resolve_i18n_field_dict(row: dict, field_name: str, locale: str):
    """Resolve row[field_name] from row[field_name_i18n] for dict rows."""
    if locale == "en":
        return
    i18n = row.get(f"{field_name}_i18n") or {}
    if locale in i18n:
        row[field_name] = i18n[locale]


# Legacy aliases for cuisine-specific callers (Phase 3)
def resolve_cuisine_name(obj, locale: str):
    """Override obj.cuisine_name from cuisine_name_i18n if locale translation exists."""
    resolve_i18n_field(obj, "cuisine_name", locale)


def resolve_cuisine_name_dict(row: dict, locale: str):
    """Override row['cuisine_name'] from row['cuisine_name_i18n'] if locale translation exists."""
    resolve_i18n_field_dict(row, "cuisine_name", locale)
