# Supplier Terms

## Overview

Supplier-specific deal terms are configured in `billing.supplier_terms` — a dedicated table with one row per Supplier institution. This includes no-show discount, payment frequency, and invoice compliance overrides.

Previously, `no_show_discount` lived on `institution_info`. It has been relocated to `supplier_terms` alongside other negotiation terms.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/supplier-terms/{institution_id}` | Supplier Admin (own) / Internal | Get terms for an institution |
| `PUT` | `/api/v1/supplier-terms/{institution_id}` | Internal Manager/Admin/Super Admin | Create or update terms |
| `GET` | `/api/v1/supplier-terms` | Internal only | List all supplier terms |

## Who Can Edit

| User Role | Can edit supplier terms? |
|-----------|-------------------------|
| Internal Manager | Yes |
| Internal Global Manager | Yes |
| Internal Admin | Yes |
| Internal Super Admin | Yes |
| Supplier Admin / Manager | **No** (403) — read-only |
| Customer | No |

Vianda negotiates terms with suppliers; Suppliers can view their terms but cannot change them.

## Response Shape

```json
GET /api/v1/supplier-terms/{institution_id}

{
  "supplier_terms_id": "uuid",
  "institution_id": "uuid",
  "no_show_discount": 15,
  "payment_frequency": "daily",
  "require_invoice": null,
  "invoice_hold_days": null,
  "effective_require_invoice": true,
  "effective_invoice_hold_days": 30,
  "is_archived": false,
  "status": "Active",
  "created_date": "2026-04-05T...",
  "modified_by": "uuid",
  "modified_date": "2026-04-05T..."
}
```

### Effective vs. configured values

- `require_invoice` and `invoice_hold_days` can be `null`, meaning "inherit from market default" (`billing.market_payout_aggregator`).
- `effective_require_invoice` and `effective_invoice_hold_days` are the **resolved values** — supplier override if set, otherwise market default.
- The UI should display effective values as the "active" setting. When the raw field differs from the effective value, show both (e.g., "Inherited from market: 30 days").

## Create / Update (PUT — upsert)

```
PUT /api/v1/supplier-terms/{institution_id}
```

```json
{
  "no_show_discount": 15,
  "payment_frequency": "weekly",
  "require_invoice": true,
  "invoice_hold_days": 45
}
```

All fields are optional on update. If the institution has no `supplier_terms` row yet, PUT creates one.

## Field Reference

| Field | Type | Default | Description | Behavioral effect |
|-------|------|---------|-------------|-------------------|
| `no_show_discount` | int (0-100) | `0` | Percentage deducted from credit when customer does not collect | Applied to `restaurant_transaction.final_amount` at promotion time |
| `payment_frequency` | enum | `"daily"` | `daily`, `weekly`, `biweekly`, `monthly` | **Gates bill creation.** Settlements accumulate daily; bills are only created when the frequency window is due (Monday for weekly, 1st for monthly). Changing this affects when money flows. |
| `require_invoice` | bool \| null | `null` | `null` = inherit from market; `true`/`false` = override | **Gates payout execution.** When `true`, the billing pipeline checks for unmatched bills before releasing payment. |
| `invoice_hold_days` | int \| null | `null` | `null` = inherit from market default (30); positive int = override | **Payout hold threshold.** If unmatched bills are older than this many days, payouts are held until invoices are submitted. Only checked when `effective_require_invoice` is `true`. |

**These are not just display fields** — changing `payment_frequency`, `require_invoice`, or `invoice_hold_days` immediately affects the supplier's billing and payout schedule on the next billing run.

## Where no_show_discount Appears

The `no_show_discount` field still appears on:

- **Enriched vianda responses** (`GET /api/v1/viandas/enriched/`) — sourced from `supplier_terms` via JOIN. Can be `null` if no terms are configured.
- **Restaurant transactions** — recorded at transaction creation time; historical value, not live config.

It does **not** appear on:

- Institution create/update/response (`/api/v1/institutions/`) — removed
- Vianda create/update — never did; still doesn't

## UI Integration Guide

### Supplier Terms Tab (Institution Detail page)

When viewing a **Supplier** institution, show a "Terms" tab or section with:

1. **No-show discount**: percentage slider or input (0-100)
2. **Payment frequency**: dropdown — Daily, Weekly, Biweekly, Monthly
3. **Invoice required**: tri-state — Inherit from market / Yes / No
4. **Invoice hold days**: number input; show market default as placeholder when blank

### Supplier Dashboard (Supplier view)

Read-only display of their terms. The Supplier sees what was agreed but cannot change it.

### Institution Create Flow

When creating a **Supplier** institution, the `no_show_discount` field is no longer on the institution payload. After creating the institution, call `PUT /api/v1/supplier-terms/{institution_id}` to set terms. Consider a two-step wizard: create institution, then configure terms.

### Migration from Previous API

- `no_show_discount` is **removed** from `POST /api/v1/institutions/`, `PUT /api/v1/institutions/{id}`, and institution response schemas.
- `invoice_hold_override_days` is **removed** from institution entity schemas.
- Replace institution `no_show_discount` field with a link to the Supplier Terms section.

## Errors

| Status | Detail | Action |
|--------|--------|--------|
| 403 | "Only Internal users with Manager, Global Manager, Admin, or Super Admin role can edit supplier terms." | Hide edit controls for non-Internal users |
| 404 | "Supplier terms not found for institution {id}" | Show "No terms configured" state with a "Configure Terms" button |
