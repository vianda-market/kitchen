# app/utils/referral_code.py
"""
Referral code generation utility.

Generates static, human-readable referral codes in the format NAME-XXXX
(e.g., MARIA-V7X2). Caller handles uniqueness retry on DB constraint violation.
"""
import secrets
import string

# Exclude ambiguous characters: 0/O, 1/I/L
_SAFE_CHARS = "".join(
    c for c in string.ascii_uppercase + string.digits
    if c not in "0OIL1"
)


def generate_referral_code(first_name: str | None) -> str:
    """Generate a referral code like MARIA-V7X2.

    Uses first 5 chars of uppercased first_name (or VIAND if none)
    plus a hyphen plus 4 random alphanumeric characters.
    """
    prefix = (first_name or "").strip().upper()[:5]
    if not prefix:
        prefix = "VIAND"
    suffix = "".join(secrets.choice(_SAFE_CHARS) for _ in range(4))
    return f"{prefix}-{suffix}"
