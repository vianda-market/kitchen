# Database Table Naming Patterns

## Overview

This document outlines the database table naming conventions and patterns used in the Kitchen application. Understanding these patterns is crucial for developers working with the database schema and CRUD operations.

## Naming Convention Rules

### Tables with `_info` Suffix
Tables ending with `_info` are **fully editable records** that:
- Allow complete CRUD operations (Create, Read, Update, Delete)
- Include a trigger function for audit trails
- Have corresponding `_history` tables for change tracking
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
| `role_info` | User roles and permissions | `role_history` |
| `institution_info` | Institution/company data | `institution_history` |
| `address_info` | Address information | `address_history` |
| `user_info` | User account data | `user_history` |
| `institution_entity_info` | Institution entity details | `institution_entity_history` |
| `geolocation_info` | Geographic location data | `geolocation_history` |
| `restaurant_info` | Restaurant details | `restaurant_history` |
| `qr_code_info` | QR code configurations | `qr_code_history` |
| `product_info` | Product catalog | `product_history` |
| `plate_info` | Plate/menu item details | `plate_history` |
| `plan_info` | Subscription plans | `plan_history` |
| `subscription_info` | User subscriptions | `subscription_history` |
| `client_bill_info` | Client billing records | `client_bill_history` |
| `restaurant_balance_info` | Restaurant balance tracking | `restaurant_balance_history` |
| `institution_bill_info` | Institution billing records | `institution_bill_history` |
| `credit_currency_info` | Credit currency definitions | `credit_currency_history` |
| `fintech_link_info` | Fintech integration data | `fintech_link_history` |
| `status_info` | Status definitions | `status_history` |
| `transaction_type_info` | Transaction type definitions | `transaction_type_history` |

### 2. Tables without `_info` Suffix

#### 2.1. Immutable Tables (No Modifications)
These tables are created once and never modified:

| Table Name | Description | Notes |
|------------|-------------|-------|
| `national_holidays` | National holiday calendar | Read-only reference data |
| `discretionary_info` | Discretionary credit requests | Created once, archived when resolved |
| `discretionary_history` | Discretionary credit request history | Immutable audit trail |
| `discretionary_resolution_info` | Discretionary resolution records | Created once per resolution |
| `discretionary_resolution_history` | Discretionary resolution history | Immutable audit trail |
| `credential_recovery` | Password recovery tokens | Temporary, auto-expire |
| `pickup_preferences` | Customer pickup preferences | User preferences, rarely modified |
| `fintech_link_transaction` | Fintech transaction logs | Immutable transaction records |
| `fintech_wallet` | Fintech wallet data | External system integration |
| `fintech_wallet_auth` | Fintech authentication | Authentication tokens |
| `institution_bank_account` | Bank account information | Created once, rarely modified |

#### 2.2. Partially Editable Tables (Limited Field Updates)
These tables allow updates to specific fields only:

| Table Name | Description | Editable Fields | Notes |
|------------|-------------|-----------------|-------|
| `plate_selection` | Customer plate selections | `status`, `modified_date` | Status changes only |
| `plate_pickup_live` | Live pickup tracking | `status`, `arrival_time`, `completion_time`, `was_collected` | Real-time status updates |
| `client_transaction` | Client transaction records | `status`, `collected_timestamp`, `was_collected` | Transaction status updates |
| `restaurant_transaction` | Restaurant transaction records | `status`, `arrival_time`, `completion_time`, `was_collected` | Transaction status updates |
| `client_payment_attempt` | Payment attempt records | `status`, `resolution_date` | Payment status updates |
| `institution_payment_attempt` | Institution payment attempts | `status`, `resolution_date` | Payment status updates |
| `payment_method` | User payment methods | `status`, `modified_date` | Payment method status |
| `credit_card` | Credit card details | `status`, `modified_date` | Card status updates |
| `bank_account` | Bank account details | `status`, `modified_date` | Account status updates |
| `appstore_account` | App store account info | `status`, `modified_date` | Account status updates |
| `plate_kitchen_days` | Plate availability days | `is_archived`, `modified_by` | Availability management |
| `restaurant_holidays` | Restaurant holiday schedule | `is_archived`, `modified_by` | Holiday management |

#### 2.3. Event/Log Tables (Append-Only)
These tables are primarily for logging and tracking:

| Table Name | Description | Notes |
|------------|-------------|-------|
| `fintech_link_transaction` | Fintech transaction logs | Immutable transaction records |

## Implementation Guidelines

### For `_info` Tables
- Use full CRUD operations
- Always include `modified_date` and `modified_by` in updates
- Leverage history tables for audit trails
- Support soft deletion with `is_archived` flag

### For Non-`_info` Tables
- **Immutable Tables**: Create only, no updates
- **Partially Editable**: Update only specific fields (typically `status`, `modified_date`)
- **Event Tables**: Append-only, no modifications

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

All `_info` tables have corresponding `_history` tables that automatically track changes via triggers. History tables are not directly accessible via API but provide audit trails for compliance and debugging.

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
