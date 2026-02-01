# EnrichedService Institution Scoping Parameters

## Purpose

The `institution_column` and `institution_table_alias` parameters in `EnrichedService.__init__()` are **NOT** for selecting columns to return. They are for **WHERE clause filtering** to implement institution scoping.

## The Problem

When a Supplier (non-global scope) queries enriched endpoints, we need to filter results by their `institution_id`. However, the `institution_id` column is **not always on the base table** - it's often on a **joined table**.

### Examples from Existing Code

**Example 1: `institution_bank_account`**
- Base table: `institution_bank_account` (alias `iba`)
- The `institution_id` is on the **joined table** `institution_entity_info` (alias `ie`)
- Filter needed: `ie.institution_id = %s::uuid`

**Example 2: `institution_bill_info`**
- Base table: `institution_bill_info` (alias `ibi`)
- The `institution_id` is on the **joined table** `restaurant_info` (alias `r`)
- Filter needed: `r.institution_id = %s::uuid`

**Example 3: `user_info` (hypothetical)**
- Base table: `user_info` (alias `u`)
- The `institution_id` is on the **base table** itself
- Filter needed: `u.institution_id = %s::uuid`

## Solution

The `EnrichedService` needs to know:
1. **What column** to filter on (`institution_column` - usually `"institution_id"`)
2. **Which table/alias** has that column (`institution_table_alias` - could be base table or joined table)

## Usage in Code

```python
# Institution bank account - institution_id is on joined table
_bank_account_service = EnrichedService(
    base_table="institution_bank_account",
    table_alias="iba",
    id_column="bank_account_id",
    schema_class=InstitutionBankAccountEnrichedResponseSchema,
    institution_column="institution_id",  # Column name
    institution_table_alias="ie"  # It's on the joined institution_entity_info table
)
# This generates: WHERE ie.institution_id = %s::uuid

# Institution bill - institution_id is on joined table
_bill_service = EnrichedService(
    base_table="institution_bill_info",
    table_alias="ibi",
    id_column="institution_bill_id",
    schema_class=InstitutionBillEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="r"  # It's on the joined restaurant_info table
)
# This generates: WHERE r.institution_id = %s::uuid

# User info - institution_id is on base table
_user_service = EnrichedService(
    base_table="user_info",
    table_alias="u",
    id_column="user_id",
    schema_class=UserEnrichedResponseSchema,
    institution_column="institution_id",
    institution_table_alias="u"  # It's on the base table itself
)
# This generates: WHERE u.institution_id = %s::uuid
```

## Implementation

In `_build_where_clause()`, the service uses these parameters to build the filter:

```python
# Apply institution scoping (for Suppliers - filter by institution)
if scope and not scope.is_global and scope.institution_id and self.institution_column:
    conditions.append(f"{self.institution_table_alias}.{self.institution_column} = %s::uuid")
    params.append(str(scope.institution_id))
```

## Why Not Just Use Base Table?

Because the `institution_id` is often on a joined table, not the base table. We need flexibility to specify where the column actually exists.

## When to Set These Parameters

- **Set `institution_column`**: If the endpoint needs institution scoping (most do)
- **Set `institution_table_alias`**: 
  - If `institution_id` is on the base table → use the base table alias
  - If `institution_id` is on a joined table → use the joined table alias
  - If no institution scoping needed → leave both as `None`

## Summary

- **Purpose**: WHERE clause filtering for institution scoping, NOT column selection
- **Why needed**: `institution_id` location varies (base table vs. joined table)
- **Common pattern**: Most enriched endpoints need institution scoping
- **Flexibility**: Allows scoping to work regardless of where `institution_id` exists

