# Markets API Documentation

## Overview

Markets represent the countries where the platform operates. Each market has its own currency and subscription plans. Markets are fundamental to the multi-market subscription architecture, enabling users to subscribe to plans in different countries.

**Key Concept**: A **Market** is a country-level subscription region with its own credit currency, locale, and regulatory requirements. Kitchen hours and operational timezone live elsewhere (see notes below).

**What does NOT live on market_info:**
- **Timezone** — lives on `address_info.timezone` per-restaurant. Deprecated on market response (returns `null`).
- **Kitchen hours** (`kitchen_open_time`, `kitchen_close_time`) — moved to market billing config (`market_payout_aggregator`) as market-level defaults, with per-supplier overrides on `supplier_terms`. See [Billing Config](#market-billing-configuration) and [API_CLIENT_SUPPLIER_TERMS.md](API_CLIENT_SUPPLIER_TERMS.md).

---

## Why Markets Matter

1. **Multi-Currency Support**: Each market uses a specific credit currency for transactions
2. **Localized Plans**: Subscription plans are market-specific
3. **Locale & Phone**: Each market has a default UI language (`en`, `es`, `pt`), computed BCP 47 `locale` (e.g. `es-AR`), and phone formatting hints (`phone_dial_code`, `phone_local_digits`)
4. **Tax ID Hints**: Each market provides `tax_id_label`, `tax_id_regex`, and `tax_id_example` so entity forms can display the correct field label (e.g. "CUIT" in AR, "RUC" in PE, "EIN" in US), validate input client-side, and show a placeholder
4. **Regulatory Compliance**: Markets enable country-specific business rules

---

## API Endpoints

### Public Endpoint (No Auth) -- Leads

- **GET /api/v1/leads/markets**: Returns the list of **active, non-archived** markets. **No authentication required.** Returns **`country_code`** and **`country_name`** only (no `market_id`). Use for B2C signup country dropdown and pre-auth country selector.
- **Rate-limited** (60 req/min per IP). **Cached** (10 min). See [LEADS_API_SCOPE.md](../shared_client/LEADS_API_SCOPE.md).

### Authenticated Endpoints -- Full Data

- **Base Endpoints** (`/api/v1/markets/`): Returns basic market data (any authenticated user)
- **Enriched Endpoints** (`/api/v1/markets/enriched/`): Returns full market data with `market_id`, currency details (any authenticated user)

**Recommendation**:
- **Pre-auth / B2C signup**: Use **GET /api/v1/leads/markets** (country_code, country_name only). Send `country_code` in signup request.
- **Authenticated / B2B forms** (institution create, plan create, admin dropdowns): Use **GET /api/v1/markets/enriched/** (includes `market_id`).

---

## Enriched Endpoints

### List Markets (Enriched)

```http
GET /api/v1/markets/enriched/
```

**Query Parameters**:
- `include_archived` (boolean, default: false) - Include archived markets

**Response**:
```json
[
  {
    "market_id": "11111111-1111-1111-1111-111111111111",
    "country_name": "Argentina",
    "country_code": "AR",
    "currency_metadata_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "currency_name": "Argentine Peso",
    "currency_code": "ARS",
    "credit_value_local_currency": "100.00",
    "currency_conversion_usd": "950.00",
    "timezone": null,
    "language": "es",
    "locale": "es-AR",
    "phone_dial_code": "+54",
    "phone_local_digits": 10,
    "tax_id_label": "CUIT",
    "tax_id_mask": "##-########-#",
    "tax_id_regex": "^\\d{11}$",
    "tax_id_example": "30123456789",
    "is_archived": false,
    "status": "active",
    "created_date": "2026-01-15T10:00:00Z",
    "modified_date": "2026-01-15T10:00:00Z"
  }
]
```

**Notes**:
- `timezone` is always `null` (deprecated). Use the restaurant's `address_info.timezone` for operational time.
- `locale` is a computed field (`{language}-{country_code}`, e.g. `es-AR`). Use for i18n.
- `credit_value_local_currency` and `currency_conversion_usd` come from `currency_metadata` JOIN. Use for plan form previews.
- `tax_id_label`, `tax_id_mask`, `tax_id_regex`, `tax_id_example` are derived from config (not stored in DB). Use to label, mask, validate, and placeholder the tax ID field on entity creation forms. `null` for countries without configured rules. **Convention:** the backend stores and validates **raw digits only** (no dashes or separators). `tax_id_mask` tells the frontend how to display the value (`#` = digit slot, literal characters are auto-inserted). The frontend must strip non-digit characters before sending the API payload.

**Use Case**: Display markets in dropdowns for plan creation, subscription selection, or market filtering.

---

### Get Market by ID (Enriched)

```http
GET /api/v1/markets/enriched/{market_id}
```

**Path Parameters**:
- `market_id` (UUID) - Market ID

**Query Parameters**:
- `include_archived` (boolean, default: false) - Include archived markets

**Response**: Single market object (same structure as list endpoint)

**Use Case**: Display detailed market information in market management views.

---

## Base Endpoints (CRUD Operations)

### Create Market

```http
POST /api/v1/markets/
```

**Authorization**: Employee (Admin/Super Admin) only

**Request Body**: Send only **country_code** (ISO 3166-1 alpha-2). The backend derives **country_name** from the code. Optionally embed `billing_config` to set market-level billing defaults atomically (see [Billing Config](#market-billing-configuration) below).
```json
{
  "country_code": "BR",
  "currency_metadata_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
  "timezone": "America/Sao_Paulo",
  "status": "active",
  "language": "pt",
  "phone_dial_code": "+55",
  "phone_local_digits": 11,
  "billing_config": {
    "aggregator": "stripe",
    "is_active": true,
    "require_invoice": false,
    "max_unmatched_bill_days": 30,
    "kitchen_open_time": "09:00",
    "kitchen_close_time": "13:30",
    "notes": "Stripe Connect supported"
  }
}
```

- `billing_config` is **optional**. If omitted, the backend creates a billing config row with defaults (`aggregator="stripe"`, `is_active=true`, `require_invoice=false`, `max_unmatched_bill_days=30`, `kitchen_open_time="09:00"`, `kitchen_close_time="13:30"`).
- `language` is optional; derived from country_code if omitted (AR/PE/CL/MX -> es, BR -> pt, else en).
- `timezone` is accepted but ignored (backward compat). Operational timezone lives on `address_info`.
- The Global Marketplace sentinel does not get a billing config row.

**Response**: Created market with enriched currency info (includes `country_name` and `country_code`). Status code 201.

**Validation**: Invalid or unsupported `country_code` returns **400 Bad Request**.

---

### Update Market

```http
PUT /api/v1/markets/{market_id}
```

**Authorization**: Employee (Admin/Super Admin) only. **Global Marketplace** (`country_code = "XG"`) is editable **only by Super Admin** — all other roles receive **403 Forbidden**. The frontend should hide or disable the Edit action for XG when the user is not Super Admin.

**Request Body** (all fields optional). When **country_code** is provided, the backend derives **country_name** from it.
```json
{
  "country_code": "BR",
  "currency_metadata_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
  "status": "active",
  "is_archived": false,
  "language": "pt",
  "phone_dial_code": "+55",
  "phone_local_digits": 11
}
```

**Note**: Kitchen hours are NOT on this endpoint. To change market-level kitchen hours defaults, use `PUT /markets/{id}/billing-config`.

**Response**: Updated market with enriched currency info.

**Validation**: Invalid `country_code` returns **400 Bad Request**.

---

### Archive Market (Soft Delete)

```http
DELETE /api/v1/markets/{market_id}
```

**Authorization**: Super Admin only

**Response**: 204 No Content

**Note**: This is a soft delete. The market is marked as archived but not removed from the database.

**Global Marketplace protection**: The API **unconditionally rejects** archiving the Global Marketplace (`country_code = "XG"`) with **400 Bad Request** `"The Global Marketplace cannot be archived."` — even for Super Admin. The Global Marketplace is the sentinel market that gives Internal users their global query scope; archiving it would lock out every Internal user. The frontend should **hide the Archive button** (or disable it) when `country_code === "XG"` to avoid showing an action that will always fail.

---

## Market Billing Configuration

Each market has a billing configuration (`market_payout_aggregator`) that controls payout behavior and operational defaults for all suppliers in that market. This table holds:

- **Payout settings**: `aggregator`, `is_active`
- **Invoice compliance defaults**: `require_invoice`, `max_unmatched_bill_days`
- **Kitchen hours defaults**: `kitchen_open_time`, `kitchen_close_time`

Supplier terms with `NULL` values for these fields inherit from their market's billing config at runtime. See [API_CLIENT_SUPPLIER_TERMS.md](API_CLIENT_SUPPLIER_TERMS.md) for the per-supplier override pattern.

### Get Billing Config

```http
GET /api/v1/markets/{market_id}/billing-config
```

**Authorization**: Internal Employee only

**Response**:
```json
{
  "market_id": "11111111-1111-1111-1111-111111111111",
  "aggregator": "stripe",
  "is_active": true,
  "require_invoice": false,
  "max_unmatched_bill_days": 30,
  "kitchen_open_time": "09:00",
  "kitchen_close_time": "13:30",
  "notes": "Stripe Connect supported",
  "is_archived": false,
  "status": "active",
  "created_date": "2026-04-12T10:00:00Z",
  "modified_by": "dddddddd-dddd-dddd-dddd-dddddddddddd",
  "modified_date": "2026-04-12T10:00:00Z"
}
```

---

### Update Billing Config

```http
PUT /api/v1/markets/{market_id}/billing-config
```

**Authorization**: Internal Employee only

**Request Body** (all fields optional):
```json
{
  "require_invoice": true,
  "max_unmatched_bill_days": 45,
  "kitchen_open_time": "08:00",
  "kitchen_close_time": "14:00"
}
```

**Response**: Updated billing config (same shape as GET).

**Audit**: Every update is tracked in `audit.market_payout_aggregator_history`. The previous config is preserved with `is_current=false` and `valid_until` set to the update timestamp.

**Impact**: Changing any field immediately affects all suppliers in this market whose `supplier_terms` have `NULL` for that field (i.e., suppliers inheriting from market defaults). Use the propagation preview endpoint below to see who will be affected before making changes.

---

### Propagation Preview

```http
GET /api/v1/markets/{market_id}/billing-config/propagation-preview
```

**Authorization**: Internal Employee only

**Response**:
```json
{
  "market_id": "11111111-1111-1111-1111-111111111111",
  "market_config": {
    "market_id": "11111111-1111-1111-1111-111111111111",
    "aggregator": "stripe",
    "is_active": true,
    "require_invoice": false,
    "max_unmatched_bill_days": 30,
    "kitchen_open_time": "09:00",
    "kitchen_close_time": "13:30",
    "notes": "Stripe Connect supported"
  },
  "affected_suppliers": [
    {
      "institution_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      "institution_name": "Cocina del Sur",
      "supplier_require_invoice": null,
      "supplier_invoice_hold_days": null,
      "effective_require_invoice": false,
      "effective_invoice_hold_days": 30,
      "effective_kitchen_open_time": "09:00",
      "effective_kitchen_close_time": "13:30"
    }
  ],
  "total_affected": 1
}
```

**Use case**: Before changing billing config, call this endpoint to see which suppliers inherit from market defaults and what their effective values will be. Suppliers with explicit (non-NULL) values in their own `supplier_terms` are NOT affected and NOT listed.

---

## Authorization & Permissions

| Role | GET markets | POST market | PUT market | DELETE market | Billing config (GET/PUT/preview) |
|------|-------------|-------------|------------|--------------|----------------------------------|
| **Super Admin Employee** | Yes | Yes | Yes | Yes | Yes |
| **Admin Employee** | Yes | No | No | No | Yes |
| **Supplier** | Yes | No | No | No | No |
| **Customer** | Yes | No | No | No | No |

**Key Points**:
- **Super Admin** (`role_name === "super_admin"`): Full CRUD access for system configuration
- **Admin** (`role_name === "admin"`): Read-only market access; can manage billing config
- **Supplier**: Read-only access for country dropdown when creating addresses
- **Customer**: Read-only access for country dropdown when creating addresses

---

## TypeScript Interfaces

```typescript
interface Market {
  market_id: string;
  country_name: string;
  country_code: string;           // ISO 3166-1 alpha-2
  currency_metadata_id: string;
  currency_name: string | null;   // Enriched from JOIN
  currency_code: string | null;   // Enriched from JOIN
  credit_value_local_currency: string | null;  // Decimal as string
  currency_conversion_usd: string | null;      // Decimal as string
  timezone: string | null;        // DEPRECATED — always null
  language: string;               // "en" | "es" | "pt"
  locale: string;                 // Computed: "{language}-{country_code}" (e.g. "es-AR")
  phone_dial_code: string | null; // E.164 prefix (e.g. "+54")
  phone_local_digits: number | null;
  tax_id_label: string | null;   // Country-specific label (e.g. "CUIT", "RUC", "EIN")
  tax_id_mask: string | null;    // Display mask ('#' = digit, literals auto-inserted). Strip before sending.
  tax_id_regex: string | null;   // Regex for raw-digit validation (e.g. "^\\d{9}$")
  tax_id_example: string | null; // Raw-digit placeholder (e.g. "123456789")
  is_archived: boolean;
  status: string;
  created_date: string;
  modified_date: string;
}

/** Create: send only country_code (alpha-2); backend derives country_name */
interface MarketCreateRequest {
  country_code: string;           // ISO 3166-1 alpha-2 (e.g. "AR", "BR")
  currency_metadata_id: string;
  timezone: string;               // Accepted but ignored (backward compat)
  status?: string;
  language?: string;              // Derived from country_code if omitted
  phone_dial_code?: string;
  phone_local_digits?: number;
  billing_config?: MarketBillingConfigRequest;
}

/** Update: when country_code is provided, backend derives country_name */
interface MarketUpdateRequest {
  country_code?: string;
  currency_metadata_id?: string;
  status?: string;
  is_archived?: boolean;
  language?: string;
  phone_dial_code?: string;
  phone_local_digits?: number;
}

interface MarketBillingConfigRequest {
  aggregator?: string;               // "stripe" | "none"
  is_active?: boolean;
  require_invoice?: boolean;
  max_unmatched_bill_days?: number;
  kitchen_open_time?: string;        // HH:MM (e.g. "09:00")
  kitchen_close_time?: string;       // HH:MM (e.g. "13:30")
  notes?: string;
}

interface MarketBillingConfigResponse {
  market_id: string;
  aggregator: string;
  is_active: boolean;
  require_invoice: boolean;
  max_unmatched_bill_days: number;
  kitchen_open_time: string;         // HH:MM
  kitchen_close_time: string;        // HH:MM
  notes: string | null;
  is_archived: boolean;
  status: string;
  created_date: string;
  modified_by: string;
  modified_date: string;
}

interface PropagationPreviewResponse {
  market_id: string;
  market_config: MarketBillingConfigResponse;
  affected_suppliers: AffectedSupplier[];
  total_affected: number;
}

interface AffectedSupplier {
  institution_id: string;
  institution_name: string;
  supplier_require_invoice: boolean | null;
  supplier_invoice_hold_days: number | null;
  effective_require_invoice: boolean;
  effective_invoice_hold_days: number;
  effective_kitchen_open_time: string;   // HH:MM
  effective_kitchen_close_time: string;  // HH:MM
}
```

---

## React Examples

### Fetching Markets for Dropdown (Admin/Supplier)

```typescript
import React, { useEffect, useState } from 'react';
import { Market } from '../types';

const MarketDropdown = () => {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMarkets = async () => {
      try {
        const response = await fetch('/api/v1/markets/enriched/');
        const data = await response.json();
        setMarkets(data);
      } catch (error) {
        console.error('Failed to fetch markets:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchMarkets();
  }, []);

  if (loading) return <div>Loading markets...</div>;

  return (
    <select>
      <option value="">Select Market</option>
      {markets.map(market => (
        <option key={market.market_id} value={market.market_id}>
          {market.country_name} ({market.currency_code})
        </option>
      ))}
    </select>
  );
};
```

---

### Market Management UI (Super Admin Only)

```typescript
import React, { useState, useEffect } from 'react';
import { Market } from '../types';

const MarketsManagementPage = () => {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);

  useEffect(() => {
    const userRole = localStorage.getItem('role_name');
    setIsSuperAdmin(userRole === 'super_admin');
    fetchMarkets();
  }, []);

  const fetchMarkets = async () => {
    const response = await fetch('/api/v1/markets/enriched/');
    const data = await response.json();
    setMarkets(data);
  };

  const handleArchive = async (marketId: string) => {
    if (!isSuperAdmin) {
      alert('Only Super Admins can archive markets');
      return;
    }

    await fetch(`/api/v1/markets/${marketId}`, {
      method: 'DELETE',
    });

    fetchMarkets();
  };

  return (
    <div>
      <h1>Markets Management</h1>
      {!isSuperAdmin && <p>Read-only view (Admin)</p>}

      <table>
        <thead>
          <tr>
            <th>Country</th>
            <th>Code</th>
            <th>Currency</th>
            <th>Language</th>
            <th>Status</th>
            {isSuperAdmin && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {markets.map(market => (
            <tr key={market.market_id}>
              <td>{market.country_name}</td>
              <td>{market.country_code}</td>
              <td>{market.currency_code}</td>
              <td>{market.locale}</td>
              <td>{market.status}</td>
              {isSuperAdmin && (
                <td>
                  <button onClick={() => handleArchive(market.market_id)}>
                    Archive
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
```

---

## Best Practices

1. **Always Use Enriched Endpoints**: Use `/enriched/` endpoints in the frontend to get complete market data with currency details
2. **Check User Role**: Verify Super Admin status before showing edit/delete buttons
3. **Cache Market Data**: Markets change infrequently - consider caching market data with a reasonable TTL
4. **Display Full Context**: Always show both market name and currency code in UI (e.g., "Argentina (ARS)")
5. **Handle Archived Markets**: Filter out archived markets in dropdowns unless explicitly needed
6. **Kitchen hours are on billing config, not market**: To display or edit kitchen hours defaults for a market, use the billing-config endpoints. Per-supplier overrides go through the supplier terms API.

---

## Related Documentation

- [Institution market_id (B2B client)](API_CLIENT_INSTITUTIONS.md) -- How institution `market_id` is used for scoping
- [Supplier Terms (B2B client)](API_CLIENT_SUPPLIER_TERMS.md) -- Per-supplier overrides including kitchen hours
- [Enriched Endpoint Pattern](../shared_client/ENRICHED_ENDPOINT_PATTERN.md)
