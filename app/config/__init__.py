"""
Configuration Module

Central location for all system configuration, including enum definitions.
All enum classes are defined in the enums/ subfolder and re-exported here for convenience.

This module provides a unified import point for both enum definitions and runtime configuration.
"""

# Re-export all enums from the enums subfolder for backward compatibility
from app.config.enums import (
    AddressType,
    Status,
    RoleType,
    RoleName,
    TransactionType,
    KitchenDay,
    PickupType,
    AuditOperation,
    DiscretionaryReason,
    BillPayoutStatus,
)

__all__ = [
    "AddressType",
    "Status",
    "RoleType",
    "RoleName",
    "TransactionType",
    "KitchenDay",
    "PickupType",
    "AuditOperation",
    "DiscretionaryReason",
    "BillPayoutStatus",
]

