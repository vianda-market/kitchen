"""
Status Enumeration

Defines the valid status values used across all entities in the system.
Status is a system enum list (static, compile-time constants), not operational data.

Context map: status values vary by use case. Use get_by_context() for API/schemas
so the frontend and validation only see the relevant subset (e.g. user = Active/Inactive only).
"""

from enum import Enum

# Context-scoped status values for API and frontend. DB keeps single status_enum.
# discretionary has its own DiscretionaryStatus enum; status_discretionary from enum_service.
STATUS_CONTEXTS: dict[str, list["Status"]] = {
    "general": [],  # Active, Pending, Inactive
    "user": [],  # Active, Inactive
    "restaurant": [],  # Active, Pending, Inactive
    "plate_pickup": [],  # Pending, Arrived, Handed_Out, Completed, Cancelled
    "bill": [],  # Pending, Processed, Cancelled
    "plate": [],  # Active, Inactive (catalog visibility; no pickup-lifecycle states)
    "plan": [],  # Active, Inactive (plan offering state; never pending/processed)
}


class Status(str, Enum):
    """Valid status values - fixed at compile time"""

    # General statuses (user, institution, product, etc.)
    ACTIVE = "active"
    INACTIVE = "inactive"

    # Order / plate pickup statuses
    PENDING = "pending"
    ARRIVED = "arrived"
    HANDED_OUT = "handed_out"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    # Transaction / bill statuses
    PROCESSED = "processed"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid status values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid status"""
        return value in cls.values()

    @classmethod
    def get_by_context(cls, context: str) -> list[str]:
        """
        Return status values valid for a given context (e.g. user edit, discretionary, bill).
        Use this for enum API and Pydantic schemas so only relevant values are exposed.
        Unknown context returns empty list; caller can fall back to values() if desired.
        """
        _ensure_contexts_filled()
        members = STATUS_CONTEXTS.get(context, [])
        return [s.value for s in members]

    @classmethod
    def get_by_category(cls, category: str) -> list[str]:
        """Get status values by category (for backward compatibility)"""
        category_map = {
            "general": [cls.ACTIVE, cls.PENDING, cls.INACTIVE],
            "order": [cls.PENDING, cls.ARRIVED, cls.COMPLETED, cls.CANCELLED],
            "transaction": [cls.PROCESSED],
        }
        return [s.value for s in category_map.get(category, [])]


def _ensure_contexts_filled() -> None:
    """Fill STATUS_CONTEXTS with Status members (done after Status is defined)."""
    if STATUS_CONTEXTS["user"]:
        return
    STATUS_CONTEXTS["general"] = [Status.ACTIVE, Status.PENDING, Status.INACTIVE]
    STATUS_CONTEXTS["user"] = [Status.ACTIVE, Status.INACTIVE]
    STATUS_CONTEXTS["restaurant"] = [Status.ACTIVE, Status.PENDING, Status.INACTIVE]
    STATUS_CONTEXTS["plate_pickup"] = [
        Status.PENDING,
        Status.ARRIVED,
        Status.HANDED_OUT,
        Status.COMPLETED,
        Status.CANCELLED,
    ]
    STATUS_CONTEXTS["bill"] = [Status.PENDING, Status.PROCESSED, Status.CANCELLED]
    # plate_info: catalog visibility only — admins toggle active/inactive.
    # No pickup-lifecycle states (pending/arrived/completed/cancelled) apply here;
    # those belong to plate_pickup context. processed is billing-only.
    STATUS_CONTEXTS["plate"] = [Status.ACTIVE, Status.INACTIVE]
    # plan_info: offering state only — active (offered) or inactive (withdrawn).
    # Never pending/processed (no approval or billing workflow on plan itself).
    STATUS_CONTEXTS["plan"] = [Status.ACTIVE, Status.INACTIVE]


_ensure_contexts_filled()
