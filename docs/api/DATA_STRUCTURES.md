# Data Structures — Enum Convention

## Enum Pattern (all enums)

Every enum in the system follows this structure:

| Concern | Where | Format | Example |
|---------|-------|--------|---------|
| **Member name** | Python class | UPPER_SNAKE_CASE | `Status.HANDED_OUT` |
| **Value** | DB column, API response, API request | lowercase slug | `"handed_out"` |
| **Display label** | `GET /api/v1/enums` response | Title Case (locale-dependent) | `"Handed Out"` (en), `"Entregado"` (es) |

## Enum API Endpoint

`GET /api/v1/enums?language={locale}`

Returns all system enums. Each enum key contains:

```json
{
  "status": {
    "values": ["active", "inactive", "pending", "arrived", "handed_out", "completed", "cancelled", "processed"],
    "labels": {
      "active": "Active",
      "inactive": "Inactive",
      "pending": "Pending",
      "arrived": "Arrived",
      "handed_out": "Handed Out",
      "completed": "Completed",
      "cancelled": "Cancelled",
      "processed": "Processed"
    }
  }
}
```

### Usage Rules

- **`value`** (lowercase slug) — use for logic, comparisons, API payloads, URL params
- **`label`** (display string) — use for UI rendering only
- **`Accept-Language`** header or `?language=` param controls locale for labels (en, es, pt)

### JWT Token Values

Role values in JWT tokens (`role_type`, `role_name`) are lowercase slugs:
- `role_type`: `"internal"`, `"supplier"`, `"customer"`, `"employer"`
- `role_name`: `"admin"`, `"super_admin"`, `"manager"`, `"operator"`, `"comensal"`, `"global_manager"`

### All Enum Types

| Enum | Sample values |
|------|-------------|
| `status` | `active`, `inactive`, `pending`, `arrived`, `handed_out`, `completed`, `cancelled`, `processed` |
| `role_type` | `internal`, `supplier`, `customer`, `employer` |
| `role_name` | `admin`, `super_admin`, `manager`, `operator`, `comensal`, `global_manager` |
| `subscription_status` | `active`, `on_hold`, `pending`, `cancelled` |
| `address_type` | `restaurant`, `entity_billing`, `entity_address`, `customer_home`, `customer_billing`, `customer_employer`, `customer_other` |
| `transaction_type` | `order`, `credit`, `debit`, `refund`, `discretionary`, `payment` |
| `kitchen_day` | `monday`, `tuesday`, `wednesday`, `thursday`, `friday` |
| `pickup_type` | `offer`, `request`, `self` |
| `street_type` | `st`, `ave`, `blvd`, `rd`, `dr`, `ln`, `way`, `ct`, `pl`, `cir` |
| `bill_resolution` | `pending`, `paid`, `rejected`, `failed` |
| `bill_payout_status` | `pending`, `completed`, `failed` |
| `discretionary_status` | `pending`, `cancelled`, `approved`, `rejected` |
| `discretionary_reason` | `marketing_campaign`, `credit_refund`, `order_incorrectly_marked`, `full_order_refund` |
| `supplier_invoice_status` | `pending_review`, `approved`, `rejected` |
| `supplier_invoice_type` | `factura_electronica`, `cpe`, `1099_nec` |
| `employer_bill_payment_status` | `pending`, `paid`, `failed`, `overdue` |
| `payment_method_provider` | `stripe`, `mercado_pago`, `payu` |
| `audit_operation` | `create`, `update`, `archive`, `delete` |
| `favorite_entity_type` | `plate`, `restaurant` |
| `dietary_flag` | `vegan`, `vegetarian`, `gluten_free`, `dairy_free`, `nut_free`, `halal`, `kosher` |
| `portion_size_display` | `light`, `standard`, `large`, `insufficient_reviews` |
| `billing_cycle` | `daily`, `weekly`, `monthly` |
| `payment_frequency` | `daily`, `weekly`, `biweekly`, `monthly` |
| `benefit_cap_period` | `per_renewal`, `monthly` |
| `enrollment_mode` | `managed`, `domain_gated` |
| `tax_classification` | `individual`, `c_corp`, `s_corp`, `partnership`, `llc`, `other` |
| `interest_type` | `customer`, `employer`, `supplier` |
| `lead_interest_status` | `active`, `notified`, `unsubscribed` |
| `lead_interest_source` | `marketing_site`, `b2c_app` |
