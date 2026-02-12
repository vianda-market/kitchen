# Markets API Documentation

## Overview

Markets represent the countries where the platform operates. Each market has its own currency, timezone, and subscription plans. Markets are fundamental to the multi-market subscription architecture, enabling users to subscribe to plans in different countries.

**Key Concept**: A **Market** is a country-level subscription region with its own credit currency, timezone, and regulatory requirements.

---

## Why Markets Matter

1. **Multi-Currency Support**: Each market uses a specific credit currency for transactions
2. **Localized Plans**: Subscription plans are market-specific
3. **Timezone Management**: Each market has its own timezone for time-based operations
4. **Regulatory Compliance**: Markets enable country-specific business rules

---

## API Endpoints

### Base vs Enriched Endpoints

- **Base Endpoints** (`/api/v1/markets/`): Returns basic market data
- **Enriched Endpoints** (`/api/v1/markets/enriched/`): Returns market data with currency details (currency_name, currency_code)

**Recommendation**: Always use enriched endpoints in the frontend for complete market information.

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
    "country_code": "ARG",
    "credit_currency_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "currency_name": "Argentine Peso",
    "currency_code": "ARS",
    "timezone": "America/Argentina/Buenos_Aires",
    "is_archived": false,
    "status": "Active",
    "created_date": "2026-01-15T10:00:00Z",
    "modified_date": "2026-01-15T10:00:00Z"
  }
]
```

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

**Authorization**: Super Admin only

**Request Body**:
```json
{
  "country_name": "Brazil",
  "country_code": "BRA",
  "credit_currency_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
  "timezone": "America/Sao_Paulo",
  "status": "Active"
}
```

**Response**: Created market with enriched currency info (status code 201)

---

### Update Market

```http
PUT /api/v1/markets/{market_id}
```

**Authorization**: Super Admin only

**Request Body** (all fields optional):
```json
{
  "country_name": "Brazil Updated",
  "credit_currency_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
  "timezone": "America/Sao_Paulo",
  "status": "Active",
  "is_archived": false
}
```

**Response**: Updated market with enriched currency info

---

### Archive Market (Soft Delete)

```http
DELETE /api/v1/markets/{market_id}
```

**Authorization**: Super Admin only

**Response**: 204 No Content

**Note**: This is a soft delete. The market is marked as archived but not removed from the database.

---

## Authorization & Permissions

### Super Admin vs Admin Permissions

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| **Super Admin Employee** | ✅ | ✅ | ✅ | ✅ |
| **Admin Employee** | ✅ | ❌ | ❌ | ❌ |
| **Supplier** | ✅ | ❌ | ❌ | ❌ |
| **Customer** | ❌ | ❌ | ❌ | ❌ |

**Key Points**:
- **Super Admin** (`role_name === "Super Admin"`): Full CRUD access for system configuration
- **Admin** (`role_name === "Admin"`): Read-only access for reference data
- **Supplier**: Read-only access for dropdown when creating plans
- **Customer**: No direct access (market determined by subscription)

---

## TypeScript Interfaces

```typescript
interface Market {
  market_id: string;
  country_name: string;
  country_code: string;
  credit_currency_id: string;
  currency_name: string;  // Enriched field
  currency_code: string;  // Enriched field
  timezone: string;
  is_archived: boolean;
  status: string;
  created_date: string;
  modified_date: string;
}

interface MarketCreateRequest {
  country_name: string;
  country_code: string;
  credit_currency_id: string;
  timezone: string;
  status?: string;
}

interface MarketUpdateRequest {
  country_name?: string;
  country_code?: string;
  credit_currency_id?: string;
  timezone?: string;
  status?: string;
  is_archived?: boolean;
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
    // Check if current user is Super Admin
    const userRole = localStorage.getItem('role_name');
    setIsSuperAdmin(userRole === 'Super Admin');

    // Fetch markets
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
    
    fetchMarkets(); // Refresh list
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
            <th>Timezone</th>
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
              <td>{market.timezone}</td>
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

### Displaying Market Info in Subscription Views

```typescript
import React from 'react';
import { SubscriptionEnriched } from '../types';

interface Props {
  subscription: SubscriptionEnriched;
}

const SubscriptionCard = ({ subscription }: Props) => {
  return (
    <div className="subscription-card">
      <h3>{subscription.plan_name}</h3>
      <p>Market: {subscription.market_name} ({subscription.country_code})</p>
      <p>Balance: {subscription.balance} {subscription.currency_code}</p>
      <p>Renewal Date: {new Date(subscription.renewal_date).toLocaleDateString()}</p>
    </div>
  );
};
```

---

## Future Enhancements (Roadmap)

The Markets enriched endpoint will eventually include:

### National Holidays
- JOIN with `national_holidays` table
- Display market-specific holidays for restaurant planning
- Support frontend holiday calendars

### Marketing Campaigns
- Future table `market_campaigns` for promotional activities
- Campaign start/end dates
- Target demographics
- Special offers per market

### Market Headcount Metrics
- Total registered users per market
- Active subscriptions per market
- Growth trends
- Revenue by market

**Note**: These fields will be added after UAT when the market structure is stable.

---

## Best Practices

1. **Always Use Enriched Endpoints**: Use `/enriched/` endpoints in the frontend to get complete market data with currency details
2. **Check User Role**: Verify Super Admin status before showing edit/delete buttons
3. **Cache Market Data**: Markets change infrequently - consider caching market data with a reasonable TTL
4. **Display Full Context**: Always show both market name and currency code in UI (e.g., "Argentina (ARS)")
5. **Handle Archived Markets**: Filter out archived markets in dropdowns unless explicitly needed

---

## Related Documentation

- [Enriched Endpoint Pattern](./ENRICHED_ENDPOINT_PATTERN.md)
- [API Permissions by Role](./API_PERMISSIONS_BY_ROLE.md)
- [Market-Based Subscriptions](./MARKET_BASED_SUBSCRIPTIONS.md)
