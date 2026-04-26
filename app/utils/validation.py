# app/utils/validation.py
"""
Validation utilities.
"""

import uuid

from pydantic import UUID4


def validate_uuid(uuid_to_test, uuid_type=UUID4):
    """Validate that the given string is a valid UUID."""
    try:
        uuid_obj = uuid_type(uuid_to_test)
    except ValueError:
        raise ValueError(f"{uuid_to_test} is not a valid UUID.")


def validate_positive_integer(value, field_name):
    """Validate that the given value is a positive integer."""
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")