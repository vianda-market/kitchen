# Enriched Endpoints Migration Example

This document shows how to migrate an existing enriched endpoint to use `EnrichedService`.

## Example: `get_enriched_institution_bank_accounts`

### Before (90+ lines)

```python
def get_enriched_institution_bank_accounts(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[InstitutionBankAccountEnrichedResponseSchema]:
    try:
        conditions = []
        params: List[Any] = []
        
        # Apply institution scoping (for Suppliers - filter by institution_entity's institution)
        if scope and not scope.is_global and scope.institution_id:
            conditions.append("ie.institution_id = %s::uuid")
            params.append(str(scope.institution_id))
        
        # Filter by archived status
        if not include_archived:
            conditions.append("iba.is_archived = FALSE")
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        query = f"""
            SELECT 
                iba.bank_account_id,
                iba.institution_entity_id,
                ie.institution_id,
                COALESCE(i.name, '') as institution_name,
                COALESCE(ie.name, '') as institution_entity_name,
                iba.address_id,
                COALESCE(a.country, '') as country,
                iba.account_holder_name,
                iba.bank_name,
                iba.account_type,
                iba.routing_number,
                iba.account_number,
                iba.is_archived,
                iba.status,
                iba.created_date,
                iba.modified_by
            FROM institution_bank_account iba
            INNER JOIN institution_entity_info ie ON iba.institution_entity_id = ie.institution_entity_id
            LEFT JOIN institution_info i ON ie.institution_id = i.institution_id
            LEFT JOIN address_info a ON iba.address_id = a.address_id
            {where_clause}
            ORDER BY iba.created_date DESC
        """
        
        results = db_read(query, tuple(params) if params else None, connection=db, fetch_one=False)
        
        if not results:
            return []
        
        # Convert UUID objects to strings for Pydantic validation
        enriched_accounts = []
        for row in results:
            row_dict = dict(row)
            for key, value in row_dict.items():
                if isinstance(value, UUID):
                    row_dict[key] = str(value)
            enriched_accounts.append(InstitutionBankAccountEnrichedResponseSchema(**row_dict))
        
        return enriched_accounts
    
    except Exception as e:
        log_error(f"Error getting enriched institution bank accounts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve enriched institution bank accounts: {str(e)}")
```

### After (15-20 lines)

```python
from app.services.enriched_service import EnrichedService

# Initialize service instance (can be module-level or class-level)
_bank_account_enriched_service = EnrichedService(
    base_table="institution_bank_account",
    table_alias="iba",
    id_column="bank_account_id",
    schema_class=InstitutionBankAccountEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="ie"  # institution_id is on the joined table
)

def get_enriched_institution_bank_accounts(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[InstitutionBankAccountEnrichedResponseSchema]:
    """
    Get all institution bank accounts with enriched data (institution name, entity name, country).
    """
    return _bank_account_enriched_service.get_enriched(
        db,
        select_fields=[
            "iba.bank_account_id",
            "iba.institution_entity_id",
            "ie.institution_id",
            "COALESCE(i.name, '') as institution_name",
            "COALESCE(ie.name, '') as institution_entity_name",
            "iba.address_id",
            "COALESCE(a.country, '') as country",
            "iba.account_holder_name",
            "iba.bank_name",
            "iba.account_type",
            "iba.routing_number",
            "iba.account_number",
            "iba.is_archived",
            "iba.status",
            "iba.created_date",
            "iba.modified_by"
        ],
        joins=[
            ("INNER", "institution_entity_info", "ie", "iba.institution_entity_id = ie.institution_entity_id"),
            ("LEFT", "institution_info", "i", "ie.institution_id = i.institution_id"),
            ("LEFT", "address_info", "a", "iba.address_id = a.address_id")
        ],
        scope=scope,
        include_archived=include_archived
    )
```

## Key Migration Steps

1. **Create service instance** (module-level, outside function)
   ```python
   _service = EnrichedService(
       base_table="table_name",
       table_alias="alias",
       id_column="id_column_name",
       schema_class=YourSchemaClass,
       institution_column="institution_id",  # if applicable
       institution_table_alias="alias"  # if institution_id is on joined table
   )
   ```

2. **Extract SELECT fields** - List all fields from the original query
3. **Extract JOINs** - Convert to `(join_type, table, alias, condition)` tuples
4. **Replace function body** - Call `service.get_enriched()` with extracted config
5. **Test** - Verify response matches original

## Benefits

- **90% code reduction** - From 90+ lines to 15-20 lines
- **Consistent error handling** - Handled by service
- **UUID conversion** - Handled by service
- **Scoping logic** - Handled by service
- **Maintainability** - Changes to enriched logic only need to be made once

## Migration Checklist

- [ ] Create `EnrichedService` instance
- [ ] Extract SELECT fields list
- [ ] Extract JOINs list (with join types)
- [ ] Replace function body
- [ ] Test endpoint manually
- [ ] Verify response matches original
- [ ] Check code reduction
- [ ] Update any route handlers if needed

