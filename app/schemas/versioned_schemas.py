# app/schemas/versioned_schemas.py
"""
Versioned Schema Management

This module provides a system for managing schema versions and ensuring
backward compatibility as the API evolves.

Current Implementation:
- All schemas default to v1
- Infrastructure ready for version-specific schemas
- Backward compatibility maintained
"""

from typing import Dict, Type, Any, Optional
from pydantic import BaseModel
from app.core.versioning import APIVersion
from app.schemas.consolidated_schemas import *


class VersionedSchemaRegistry:
    """Registry for managing schema versions"""
    
    def __init__(self):
        self._schemas: Dict[str, Dict[APIVersion, Type[BaseModel]]] = {}
        self._register_default_schemas()
    
    def _register_default_schemas(self):
        """Register all current schemas as v1 schemas"""
        # Core Entity Schemas
        self.register_schema("UserCreate", APIVersion.V1, UserCreateSchema)
        self.register_schema("UserUpdate", APIVersion.V1, UserUpdateSchema)
        self.register_schema("UserResponse", APIVersion.V1, UserResponseSchema)
        self.register_schema("CustomerSignup", APIVersion.V1, CustomerSignupSchema)
        
        self.register_schema("InstitutionCreate", APIVersion.V1, InstitutionCreateSchema)
        self.register_schema("InstitutionUpdate", APIVersion.V1, InstitutionUpdateSchema)
        self.register_schema("InstitutionResponse", APIVersion.V1, InstitutionResponseSchema)
        
        # Role schemas removed - role_info table deprecated, roles stored directly on user_info as enums
        
        # Restaurant & Food Schemas
        self.register_schema("RestaurantCreate", APIVersion.V1, RestaurantCreateSchema)
        self.register_schema("RestaurantUpdate", APIVersion.V1, RestaurantUpdateSchema)
        self.register_schema("RestaurantResponse", APIVersion.V1, RestaurantResponseSchema)
        
        self.register_schema("ProductCreate", APIVersion.V1, ProductCreateSchema)
        self.register_schema("ProductUpdate", APIVersion.V1, ProductUpdateSchema)
        self.register_schema("ProductResponse", APIVersion.V1, ProductResponseSchema)
        
        self.register_schema("PlateCreate", APIVersion.V1, PlateCreateSchema)
        self.register_schema("PlateUpdate", APIVersion.V1, PlateUpdateSchema)
        self.register_schema("PlateResponse", APIVersion.V1, PlateResponseSchema)
        
        self.register_schema("QRCodeCreate", APIVersion.V1, QRCodeCreateSchema)
        self.register_schema("QRCodeUpdate", APIVersion.V1, QRCodeUpdateSchema)
        self.register_schema("QRCodeResponse", APIVersion.V1, QRCodeResponseSchema)
        
        # Billing & Payments Schemas
        self.register_schema("CreditCurrencyCreate", APIVersion.V1, CreditCurrencyCreateSchema)
        self.register_schema("CreditCurrencyUpdate", APIVersion.V1, CreditCurrencyUpdateSchema)
        self.register_schema("CreditCurrencyResponse", APIVersion.V1, CreditCurrencyResponseSchema)
        
        self.register_schema("PlanCreate", APIVersion.V1, PlanCreateSchema)
        self.register_schema("PlanUpdate", APIVersion.V1, PlanUpdateSchema)
        self.register_schema("PlanResponse", APIVersion.V1, PlanResponseSchema)
        
        # Location & Address Schemas
        self.register_schema("AddressCreate", APIVersion.V1, AddressCreateSchema)
        self.register_schema("AddressUpdate", APIVersion.V1, AddressUpdateSchema)
        self.register_schema("AddressResponse", APIVersion.V1, AddressResponseSchema)
        
        self.register_schema("EmployerCreate", APIVersion.V1, EmployerCreateSchema)
        self.register_schema("EmployerUpdate", APIVersion.V1, EmployerUpdateSchema)
        self.register_schema("EmployerResponse", APIVersion.V1, EmployerResponseSchema)
        self.register_schema("EmployerSearch", APIVersion.V1, EmployerSearchSchema)
        
        # Plate Selection & Pickup Schemas
        self.register_schema("PlateSelectionCreate", APIVersion.V1, PlateSelectionCreateSchema)
        self.register_schema("PlateSelectionUpdate", APIVersion.V1, PlateSelectionUpdateSchema)
        self.register_schema("PlateSelectionResponse", APIVersion.V1, PlateSelectionResponseSchema)
        
        # Admin & Discretionary Schemas
        self.register_schema("DiscretionaryCreate", APIVersion.V1, DiscretionaryCreateSchema)
        self.register_schema("DiscretionaryUpdate", APIVersion.V1, DiscretionaryUpdateSchema)
        self.register_schema("DiscretionaryResponse", APIVersion.V1, DiscretionaryResponseSchema)
        self.register_schema("DiscretionaryResolutionCreate", APIVersion.V1, DiscretionaryResolutionCreateSchema)
        self.register_schema("DiscretionaryResolutionResponse", APIVersion.V1, DiscretionaryResolutionResponseSchema)
        self.register_schema("DiscretionaryApproval", APIVersion.V1, DiscretionaryApprovalSchema)
        self.register_schema("DiscretionaryRejection", APIVersion.V1, DiscretionaryRejectionSchema)
        self.register_schema("DiscretionarySummary", APIVersion.V1, DiscretionarySummarySchema)
    
    def register_schema(self, name: str, version: APIVersion, schema_class: Type[BaseModel]):
        """Register a schema for a specific version"""
        if name not in self._schemas:
            self._schemas[name] = {}
        self._schemas[name][version] = schema_class
    
    def get_schema(self, name: str, version: APIVersion) -> Optional[Type[BaseModel]]:
        """Get a schema for a specific version"""
        if name in self._schemas and version in self._schemas[name]:
            return self._schemas[name][version]
        return None
    
    def get_latest_schema(self, name: str) -> Optional[Type[BaseModel]]:
        """Get the latest version of a schema"""
        if name not in self._schemas:
            return None
        
        # Return the highest version available
        versions = list(self._schemas[name].keys())
        if not versions:
            return None
        
        # Sort versions and return the latest
        latest_version = max(versions, key=lambda v: int(v.value[1:]))
        return self._schemas[name][latest_version]
    
    def list_schemas_for_version(self, version: APIVersion) -> Dict[str, Type[BaseModel]]:
        """List all schemas available for a specific version"""
        schemas = {}
        for name, version_schemas in self._schemas.items():
            if version in version_schemas:
                schemas[name] = version_schemas[version]
        return schemas


# Global schema registry
schema_registry = VersionedSchemaRegistry()


def get_schema_for_version(schema_name: str, version: APIVersion) -> Type[BaseModel]:
    """
    Get a schema class for a specific API version
    
    Args:
        schema_name: Name of the schema (e.g., "UserCreate")
        version: API version
        
    Returns:
        Schema class for the specified version
        
    Raises:
        ValueError: If schema is not found for the version
    """
    schema_class = schema_registry.get_schema(schema_name, version)
    if schema_class is None:
        raise ValueError(f"Schema '{schema_name}' not found for version {version}")
    return schema_class


def get_latest_schema(schema_name: str) -> Type[BaseModel]:
    """
    Get the latest version of a schema
    
    Args:
        schema_name: Name of the schema
        
    Returns:
        Latest schema class
        
    Raises:
        ValueError: If schema is not found
    """
    schema_class = schema_registry.get_latest_schema(schema_name)
    if schema_class is None:
        raise ValueError(f"Schema '{schema_name}' not found")
    return schema_class


# Convenience functions for common schemas
def get_user_create_schema(version: APIVersion = APIVersion.V1) -> Type[BaseModel]:
    """Get UserCreate schema for specified version"""
    return get_schema_for_version("UserCreate", version)


def get_plan_create_schema(version: APIVersion = APIVersion.V1) -> Type[BaseModel]:
    """Get PlanCreate schema for specified version"""
    return get_schema_for_version("PlanCreate", version)


def get_plan_response_schema(version: APIVersion = APIVersion.V1) -> Type[BaseModel]:
    """Get PlanResponse schema for specified version"""
    return get_schema_for_version("PlanResponse", version)


# Example of how to add version-specific schemas in the future:
"""
# Example: Adding a v2 schema with breaking changes
# class UserCreateSchemaV2(BaseModel):
#     email_verified: bool = False
#     # ... register with schema_registry.register_schema("UserCreate", APIVersion.V2, UserCreateSchemaV2)
# v1 user payloads use mobile_number (E.164) from consolidated_schemas.UserCreateSchema.
"""
