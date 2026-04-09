"""
Audit Operation Enumeration

Defines the valid audit operations tracked in history tables.
Audit operations are fixed at compile time and represent CRUD operations.
"""
from enum import Enum


class AuditOperation(str, Enum):
    """Valid audit operations - fixed at compile time"""
    CREATE = "create"
    UPDATE = "update"
    ARCHIVE = "archive"
    DELETE = "delete"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid audit operation values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid audit operation"""
        return value in cls.values()

