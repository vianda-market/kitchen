# Fintech Link Transaction Enriched API

## Overview

The Fintech Link Transaction API provides both base and enriched endpoints for managing fintech link transactions. The enriched endpoints include provider and plan information to eliminate N+1 queries.

## Access Control

- **Employees**: Full access to all transactions
- **Customers**: Self-scoped access (only their own transactions via `payment_method.user_id`)
- **Suppliers**: Not allowed (blocked)

## Base Endpoints

### `GET /fintech-link-transaction/`
List all fintech link transactions.

**Access**: Employees (all), Customers (own only)

**Query Parameters**:
- `include_archived` (optional, bool): Include archived records

**Response**: `List[FintechLinkTransactionResponseSchema]`

### `GET /fintech-link-transaction/{fintech_link_transaction_id}`
Get a single fintech link transaction by ID.

**Access**: Employees (any), Customers (own only)

**Query Parameters**:
- `include_archived` (bool, default: false): Include archived records

**Response**: `FintechLinkTransactionResponseSchema`

### `POST /fintech-link-transaction/`
Create a new fintech link transaction.

**Access**: Employees (any user), Customers (own payment methods only)

**Request Body**: `FintechLinkTransactionCreateSchema`
```json
{
  "payment_method_id": "uuid",
  "fintech_link_id": "uuid"
}
```

**Response**: `FintechLinkTransactionDTO`

### `DELETE /fintech-link-transaction/{fintech_link_transaction_id}`
Soft-delete a fintech link transaction.

**Access**: Employees (any), Customers (own only)

**Response**: `{"detail": "Fintech link transaction deleted successfully"}`

## Enriched Endpoints

### `GET /fintech-link-transaction/enriched/`
List all fintech link transactions with enriched data.

**Enriched Fields**:
- `provider` (from `fintech_link_info`)
- `plan_name` (from `plan_info` via `fintech_link_info`)
- `credit` (from `plan_info` via `fintech_link_info`)
- `price` (from `plan_info` via `fintech_link_info`)

**Access**: Employees (all), Customers (own only)

**Query Parameters**:
- `include_archived` (optional, bool): Include archived records

**Response**: `List[FintechLinkTransactionEnrichedResponseSchema]`

### `GET /fintech-link-transaction/enriched/{fintech_link_transaction_id}`
Get a single fintech link transaction by ID with enriched data.

**Enriched Fields**: Same as list endpoint

**Access**: Employees (any), Customers (own only)

**Query Parameters**:
- `include_archived` (bool, default: false): Include archived records

**Response**: `FintechLinkTransactionEnrichedResponseSchema`

## Response Schemas

### `FintechLinkTransactionResponseSchema` (Base)
```python
{
    "fintech_link_transaction_id": "uuid",
    "payment_method_id": "uuid",
    "fintech_link_id": "uuid",
    "is_archived": bool,
    "status": str,
    "created_date": "datetime"
}
```

### `FintechLinkTransactionEnrichedResponseSchema` (Enriched)
```python
{
    "fintech_link_transaction_id": "uuid",
    "payment_method_id": "uuid",
    "fintech_link_id": "uuid",
    "provider": str,  # From fintech_link_info
    "plan_name": str,  # From plan_info
    "credit": int,  # From plan_info
    "price": float,  # From plan_info
    "is_archived": bool,
    "status": str,
    "created_date": "datetime"
}
```

## Implementation Details

### Scoping Logic

**For Customers**:
- Transactions are filtered by `payment_method.user_id = current_user.user_id`
- This is enforced at both the base and enriched endpoint levels

**For Employees**:
- No filtering applied (see all transactions)

### Database Joins

The enriched endpoints use the following JOIN structure:
```sql
SELECT 
    flt.*,
    fl.provider,
    pl.name as plan_name,
    pl.credit,
    pl.price
FROM fintech_link_transaction flt
INNER JOIN fintech_link_info fl ON flt.fintech_link_id = fl.fintech_link_id
INNER JOIN plan_info pl ON fl.plan_id = pl.plan_id
INNER JOIN payment_method pm ON flt.payment_method_id = pm.payment_method_id
WHERE pm.user_id = %s  -- For customer scoping
```

### Relationship Chain

```
fintech_link_transaction
  → payment_method_id → payment_method (for user scoping)
  → fintech_link_id → fintech_link_info
    → plan_id → plan_info (for plan details)
```

## Notes

- The `plan_id` is **NOT** stored directly in `fintech_link_transaction` table
- Plan information is accessed through the `fintech_link_info` table
- This maintains data integrity and follows normalization principles
- See `FINTECH_LINK_TRANSACTION_PLAN_ID_ANALYSIS.md` for detailed analysis

---

*Last Updated: 2025-11-24*
