"""
Message catalog for localized API responses.
Phase 1: scaffold — English strings; es/pt empty dicts fall back via get_message.
"""

from typing import Any, Dict

MESSAGES: Dict[str, Dict[str, str]] = {
    "en": {
        "error.user_not_found": "User not found.",
        "error.duplicate_email": "An account with this email already exists.",
        "error.invalid_credentials": "Invalid username or password.",
        "error.email_change_code_expired": "Verification code has expired. Please request a new one.",
        "error.email_change_code_invalid": "Invalid verification code.",
        "alert.email_verified": "Email verified successfully.",
        "alert.email_change_requested": "A verification code has been sent to {email}.",
    },
    "es": {},
    "pt": {},
}


def get_message(key: str, locale: str = "en", **params: Any) -> str:
    """
    Localized message for key; falls back to English then to key string.
    Supports str.format for params when the template exists.
    """
    msg = MESSAGES.get(locale, {}).get(key) or MESSAGES["en"].get(key, key)
    if params:
        try:
            msg = msg.format(**params)
        except KeyError:
            pass
    return msg
