"""
Address autocomplete configuration.

Tuning for UX (too low = noisy suggestions; too high = poor UX) and cost
(fewer chars = more API calls).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AddressAutocompleteConfig(BaseSettings):
    """Config for address autocomplete. Reads from env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Minimum characters before calling suggest. Client typically checks; backend can enforce.
    ADDRESS_AUTOCOMPLETE_MIN_CHARS: int = 3


_address_autocomplete_config: AddressAutocompleteConfig | None = None


def get_address_autocomplete_config() -> AddressAutocompleteConfig:
    global _address_autocomplete_config
    if _address_autocomplete_config is None:
        _address_autocomplete_config = AddressAutocompleteConfig()
    return _address_autocomplete_config
