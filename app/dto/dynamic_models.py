# app/dto/dynamic_models.py
"""
Example of using Pydantic's create_model for dynamic DTO generation.

This demonstrates how to leverage Pydantic's create_model functionality
to reduce boilerplate and keep DTOs in sync with schemas.
"""

from pydantic import create_model, BaseModel
from typing import Any, Dict, Type
from app.schemas.consolidated_schemas import ProductCreateSchema


def create_dto_from_schema(schema_class: Type[BaseModel], table_name: str, id_column: str) -> Type[BaseModel]:
    """
    Dynamically create DTO from existing Pydantic schema.
    
    Args:
        schema_class: The Pydantic schema class to base the DTO on
        table_name: Database table name (for documentation)
        id_column: Primary key column name
        
    Returns:
        New DTO class with orm_mode enabled
    """
    
    # Get field information from schema
    fields = {}
    for field_name, field_info in schema_class.__fields__.items():
        # Handle optional fields
        if field_info.default is not None:
            fields[field_name] = (field_info.type_, field_info.default)
        elif field_info.default_factory is not None:
            fields[field_name] = (field_info.type_, field_info.default_factory())
        else:
            fields[field_name] = (field_info.type_, ...)
    
    # Create the DTO class
    dto_class = create_model(
        f"{schema_class.__name__}DTO",
        **fields,
        __config__=type('Config', (), {'orm_mode': True})()
    )
    
    # Add documentation
    dto_class.__doc__ = f"DTO for {table_name} table (dynamically generated from {schema_class.__name__})"
    
    return dto_class


# Example usage:
# ProductDTO = create_dto_from_schema(ProductCreateSchema, "product_info", "product_id")

def create_extended_dto(base_dto: Type[BaseModel], **additional_fields) -> Type[BaseModel]:
    """
    Create extended DTO with additional fields (for lazy loading scenarios).
    
    Args:
        base_dto: Base DTO class to extend
        **additional_fields: Additional fields to add
        
    Returns:
        Extended DTO class
    """
    
    # Get existing fields
    fields = {}
    for field_name, field_info in base_dto.__fields__.items():
        fields[field_name] = (field_info.type_, field_info.default)
    
    # Add additional fields
    fields.update(additional_fields)
    
    # Create extended DTO
    extended_dto = create_model(
        f"Extended{base_dto.__name__}",
        **fields,
        __config__=type('Config', (), {'orm_mode': True})()
    )
    
    return extended_dto


# Example usage for lazy loading:
# ProductWithInstitutionDTO = create_extended_dto(
#     ProductDTO,
#     institution_name=(str, None)
# )
