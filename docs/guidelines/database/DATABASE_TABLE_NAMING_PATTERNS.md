# Database Table Naming Patterns

## Overview

This document outlines the database table naming conventions and patterns used in the Kitchen application. Understanding these patterns is crucial for developers working with the database schema and CRUD operations.

## Naming Convention Rules

### Tables with `_info` Suffix
Tables ending with `_info` are **fully editable records** that:
- Allow complete CRUD operations (Create, Read, Update, Delete)
- Include a trigger function for audit trails
- Typically have corresponding `_history` tables for change tracking (some exceptions)
- Support full field modifications including `modified_date` and `modified_by`

### Tables without `_info` Suffix
Tables without the `_info` suffix are **specialized tables** that:
- May be immutable (no modifications after creation)
- May allow only partial field updates (e.g., status changes)
- May be transaction/event logs
- May be lookup/reference tables

## Table Categories

### 1. Tables with `_info` Suffix (Fully Editable)

These tables support full CRUD operations and have history tracking:

| Table Name | Description | History Table |
|------------|-------------|---------------|
| `institution_info` | Institution/company data | `institution_history` |
| `address_info` | Address information | `address_history` |
| `user_info` | User account data | `user_history` |
| `employer_info` | Employer data | `employer_history` |
| `institution_entity_info` | Institution entity details | `institution_entity_history` |
| `geolocation_info` | Geographic location data | `geolocation_history` |
| `restaurant_info` | Restaurant details | `restaurant_history` |
| `product_info` | Product catalog | `product_history` |
| `plate_info` | Plate/menu item details | `plate_history` |
| `plan_info` | Subscription plans | `plan_history` |
| `subscription_info` | User subscriptions | `subscription_history` |
| `client_bill_info` | Client billing records | `client_bill_history` |
| `restaurant_balance_info` | Restaurant balance tracking | `restaurant_balance_history` |
| `institution_bill_info` | Institution billing records | `institution_bill_history` |
| `credit_currency_info` | Credit currency definitions | `credit_currency_history` |
| `market_info` | Market definitions | `market_history` |
| `plate_selection_info` | Customer plate selections | `plate_selection_history` |
| `discretionary_info` | Discretionary credit requests | `discretionary_history` |
| `discretionary_resolution_info` | Discretionary resolution records | `discretionary_resolution_history` |

**`_info` tables without history tables** (no triggers): `city_info`, `plate_review_info`, `user_favorite_info`

**Note:** `discretionary_info` and `discretionary_resolution_info` are `_info` tables with history but are **immutable** (created once, archived when resolved — no field updates).

### 2. Tables without `_info` Suffix

#### 2.1. Reference / Lookup Tables (No or Minimal History)
| Table Name | Description | History Table | Notes |
|------------|-------------|---------------|-------|
| `national_holidays` | National holiday calendar | `national_holidays_history` | Read-only reference data |
| `qr_code` | QR code configurations | *(none)* | No `_info` suffix; no history table |
| `address_subpremise` | Address sub-premise details | *(none)* | Lookup/reference |
| `user_market_assignment` | User-to-market assignments | *(none)* | Junction table |
| `user_messaging_preferences` | User messaging preferences | *(none)* | Preferences |

#### 2.2. Immutable or Append-Only
These tables are created once and never modified, or are append-only:

| Table Name | Description | History Table | Notes |
|------------|-------------|---------------|-------|
| `credential_recovery` | Password recovery tokens | *(none)* | Temporary, auto-expire |
| `pending_customer_signup` | Pending signup records | *(none)* | Temporary |
| `pickup_preferences` | Customer pickup preferences | *(none)* | User preferences |
| `subscription_payment` | Subscription payment records | *(none)* | Payment log |
| `coworker_pickup_notification` | Coworker pickup notifications | *(none)* | Notification log |

#### 2.3. Partially Editable Tables (Limited Field Updates)
These tables allow updates to specific fields only:

| Table Name | Description | Editable Fields | History Table |
|------------|-------------|-----------------|---------------|
| `plate_pickup_live` | Live pickup tracking | `status`, `arrival_time`, `completion_time`, `was_collected` | *(none)* |
| `client_transaction` | Client transaction records | `status`, `collected_timestamp`, `was_collected` | *(none)* |
| `restaurant_transaction` | Restaurant transaction records | `status`, `arrival_time`, `completion_time`, `was_collected` | *(none)* |
| `payment_method` | User payment methods | `status`, `modified_date` | *(none)* |
| `external_payment_method` | External/linked payment methods | `status`, `modified_date` | *(none)* |
| `plate_kitchen_days` | Plate availability days | `is_archived`, `modified_by` | `plate_kitchen_days_history` |
| `restaurant_holidays` | Restaurant holiday schedule | `is_archived`, `modified_by` | `restaurant_holidays_history` |
| `institution_settlement` | Institution settlement records | Various | `institution_settlement_history` |

#### 2.4. History Tables (Immutable Audit Trails)
`*_history` tables track changes via triggers. Not directly accessible via API.

## Implementation Guidelines

### For `_info` Tables
- Use full CRUD operations
- Always include `modified_date` and `modified_by` in updates
- Leverage history tables for audit trails
- Support soft deletion with `is_archived` flag

### For Non-`_info` Tables
- **Immutable / Append-Only**: Create only, no updates
- **Partially Editable**: Update only specific fields (typically `status`, `modified_date`)

### CRUD Service Configuration
When configuring CRUD services for non-`_info` tables:

```python
# For immutable tables
service = CRUDService("table_name", DTOClass, "primary_key", allows_modification=False)

# For partially editable tables
service = CRUDService("table_name", DTOClass, "primary_key", allows_modification=True)
# Use custom update schemas that only allow specific fields
```

### Route Factory Configuration
```python
# For immutable tables
create_crud_routes(
    service=service,
    create_schema=CreateSchema,
    response_schema=ResponseSchema,
    allows_modification=False
)

# For partially editable tables
create_crud_routes(
    service=service,
    create_schema=CreateSchema,
    update_schema=PartialUpdateSchema,  # Limited fields
    response_schema=ResponseSchema,
    allows_modification=True
)
```

## History Tables

Most `_info` tables have corresponding `_history` tables that automatically track changes via triggers. Exceptions: `city_info`, `plate_review_info`, `user_favorite_info` have no history tables. Some non-`_info` tables (e.g. `plate_kitchen_days`, `restaurant_holidays`, `institution_settlement`) also have history tables. History tables are not directly accessible via API but provide audit trails for compliance and debugging.

## Best Practices

1. **Always check table naming patterns** before implementing CRUD operations
2. **Use appropriate update schemas** for partially editable tables
3. **Respect immutability** for transaction and log tables
4. **Leverage history tables** for audit requirements
5. **Document any deviations** from these patterns

## Migration Considerations

When adding new tables:
- Use `_info` suffix for fully editable business entities
- Use descriptive names without `_info` for specialized tables
- Implement appropriate triggers for history tracking
- Configure CRUD services with correct modification permissions
- Update this documentation when adding new table categories
