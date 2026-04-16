# app/dto/dynamic_models.py
"""
Example of using Pydantic's create_model for dynamic DTO generation.

This demonstrates how to leverage Pydantic's create_model functionality
to reduce boilerplate and keep DTOs in sync with schemas.
"""

from pydantic import BaseModel, ConfigDict, Field, create_model


def create_dto_from_schema(schema_class: type[BaseModel], table_name: str, id_column: str) -> type[BaseModel]:
    """
    Dynamically create DTO from existing Pydantic schema.

    Args:
        schema_class: The Pydantic schema class to base the DTO on
        table_name: Database table name (for documentation)
        id_column: Primary key column name

    Returns:
        New DTO class with orm_mode enabled
    """

    # Get field information from schema (model_fields in Pydantic v2)
    from pydantic_core import PydanticUndefined

    fields = {}
    for field_name, field_info in schema_class.model_fields.items():
        ann = field_info.annotation
        # Handle optional fields
        if field_info.default is not PydanticUndefined and field_info.default is not None:
            fields[field_name] = (ann, field_info.default)
        elif field_info.default_factory is not None:
            fields[field_name] = (ann, Field(default_factory=field_info.default_factory))
        else:
            fields[field_name] = (ann, ...)

    # Create the DTO class
    dto_class = create_model(f"{schema_class.__name__}DTO", **fields, __config__=ConfigDict(from_attributes=True))

    # Add documentation
    dto_class.__doc__ = f"DTO for {table_name} table (dynamically generated from {schema_class.__name__})"

    return dto_class


# Example usage:
# ProductDTO = create_dto_from_schema(ProductCreateSchema, "product_info", "product_id")


def create_extended_dto(base_dto: type[BaseModel], **additional_fields) -> type[BaseModel]:
    """
    Create extended DTO with additional fields (for lazy loading scenarios).

    Args:
        base_dto: Base DTO class to extend
        **additional_fields: Additional fields to add

    Returns:
        Extended DTO class
    """

    # Get existing fields
    from pydantic_core import PydanticUndefined

    fields = {}
    for field_name, field_info in base_dto.model_fields.items():
        ann = field_info.annotation
        if field_info.default is not PydanticUndefined and field_info.default is not None:
            fields[field_name] = (ann, field_info.default)
        elif field_info.default_factory is not None:
            fields[field_name] = (ann, Field(default_factory=field_info.default_factory))
        else:
            fields[field_name] = (ann, ...)

    # Add additional fields
    fields.update(additional_fields)

    # Create extended DTO
    extended_dto = create_model(f"Extended{base_dto.__name__}", **fields, __config__=ConfigDict(from_attributes=True))

    return extended_dto


# Example usage for lazy loading:
# ProductWithInstitutionDTO = create_extended_dto(
#     ProductDTO,
#     institution_name=(str, None)
# )
