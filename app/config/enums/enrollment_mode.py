"""Enrollment Mode Enumeration for employer benefits program."""
from enum import Enum


class EnrollmentMode(str, Enum):
    """How employees join the benefits program."""
    MANAGED = "managed"
    DOMAIN_GATED = "domain_gated"
