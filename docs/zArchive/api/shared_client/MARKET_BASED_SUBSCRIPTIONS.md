# Market-Based Subscriptions

## Overview

The multi-market subscription architecture allows users to maintain multiple subscriptions across different markets (countries). Each subscription is independent and can be managed separately, including the ability to put subscriptions on hold.

**Key Concept**: A user can have multiple active subscriptions, one per market, each with its own balance, renewal date, and hold status.

---

## Multi-Market Subscriptions

### Core Principles

1. **One Subscription Per Market**: A user can have one active subscription per market
2. **Independent Management**: Each subscription is managed independently
3. **Market-Specific Plans**: Plans are market-specific and use the market's currency
4. **Hold Functionality**: Users can put subscriptions on hold without canceling

### Database Constraint

The system enforces a unique constraint to prevent users from having multiple active subscriptions in the same market:

```sql
-- Unique constraint: One active subscription per user per market
CREATE UNIQUE INDEX idx_user_market_active 
ON subscription_info (user_id, market_id) 
WHERE is_archived = FALSE AND status = 'Active'::status_enum;
```

**Note**: Archived or inactive subscriptions do not count toward this constraint.

---

## Market Selection Flow

### New User Registration

1. **User Registers** → Account created
2. **Select Country (Market)** → User selects their primary market
3. **View Plans** → System shows plans for selected market
4. **Subscribe to Plan** → Subscription created in that market
5. **Can Add More Markets** → User can later subscribe to additional markets

### Adding Additional Markets

1. **Navigate to Subscriptions** → View current subscriptions
2. **Add New Market** → Select a different country
3. **Choose Plan** → View and select plan in new market
4. **Subscribe** → New subscription created for that market

---

## API Patterns

### Get User's Subscriptions (with Market Info)

```http
GET /api/v1/subscriptions/me
```

**Response** (Enriched):
```json
[
  {
    "subscription_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "plan_id": "11111111-1111-1111-1111-111111111111",
    "plan_name": "Argentina Basic",
    "market_id": "11111111-1111-1111-1111-111111111111",
    "market_name": "Argentina",
    "country_code": "AR",
    "balance": 15.50,
    "renewal_date": "2026-03-01T00:00:00Z",
    "subscription_status": "Active",
    "hold_start_date": null,
    "hold_end_date": null,
    "status": "Active"
  },
  {
    "subscription_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "plan_id": "22222222-2222-2222-2222-222222222222",
    "plan_name": "Peru Premium",
    "market_id": "22222222-2222-2222-2222-222222222222",
    "market_name": "Peru",
    "country_code": "PE",
    "balance": 20.00,
    "renewal_date": "2026-02-28T00:00:00Z",
    "subscription_status": "On Hold",
    "hold_start_date": "2026-01-15T00:00:00Z",
    "hold_end_date": "2026-02-15T00:00:00Z",
    "status": "Active"
  }
]
```

---

### Filter Plans by Market

```http
GET /api/v1/plans/enriched/?market_id={market_id}
```

**Example**:
```http
GET /api/v1/plans/enriched/?market_id=11111111-1111-1111-1111-111111111111
```

**Response**:
```json
[
  {
    "plan_id": "11111111-aaaa-aaaa-aaaa-111111111111",
    "market_id": "11111111-1111-1111-1111-111111111111",
    "market_name": "Argentina",
    "country_code": "AR",
    "currency_name": "Argentine Peso",
    "currency_code": "ARS",
    "name": "Argentina Basic",
    "credit": 20,
    "price": 5000.00,
    "rollover": true,
    "rollover_cap": null,
    "status": "Active"
  }
]
```

---

### Create Subscription

```http
POST /api/v1/subscriptions/
```

**Request Body**:
```json
{
  "user_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  "plan_id": "11111111-aaaa-aaaa-aaaa-111111111111"
}
```

**Note**: The `market_id` is automatically determined from the selected `plan_id` (plans are market-specific).

**Response**: Created subscription with enriched data

**Error Cases**:
- `409 Conflict`: User already has an active subscription in this market
- `404 Not Found`: Plan not found or is archived
- `400 Bad Request`: Invalid user_id or plan_id

---

## Hold Functionality

### Subscription Hold States

| Status | Description | Billing | Plate Selection |
|--------|-------------|---------|-----------------|
| **Active** | Subscription is active | ✅ Billed | ✅ Allowed |
| **On Hold** | Subscription temporarily paused | ❌ Not billed | ❌ Not allowed |
| **Cancelled** | Subscription terminated | ❌ Not billed | ❌ Not allowed |

### Put Subscription on Hold

```http
POST /api/v1/subscriptions/{subscription_id}/hold
```

**Request Body**:
```json
{
  "hold_start_date": "2026-02-01T00:00:00Z",
  "hold_end_date": "2026-02-28T00:00:00Z"
}
```

**Response**: Updated subscription with `subscription_status = "On Hold"`

**Business Rules**:
- Hold period must be in the future
- Hold end date must be after hold start date
- User is not billed during hold period
- User cannot select plates during hold period
- Subscription automatically reactivates after hold end date

### Resume Subscription from Hold

```http
POST /api/v1/subscriptions/{subscription_id}/resume
```

**Response**: Updated subscription with `subscription_status = "Active"`

---

## TypeScript Interfaces

```typescript
interface Subscription {
  subscription_id: string;
  user_id: string;
  plan_id: string;
  plan_name: string;
  market_id: string;
  market_name: string;
  country_code: string;
  balance: number;
  renewal_date: string;  // ISO 8601
  subscription_status: 'Active' | 'On Hold' | 'Cancelled';
  hold_start_date?: string;  // ISO 8601 (optional)
  hold_end_date?: string;    // ISO 8601 (optional)
  status: string;  // Database status (usually 'Active')
  created_date: string;
  modified_by: string;
  modified_date: string;
}

interface SubscriptionCreateRequest {
  user_id: string;
  plan_id: string;  // Market is determined from plan
}

interface SubscriptionHoldRequest {
  hold_start_date: string;  // ISO 8601
  hold_end_date: string;    // ISO 8601
}
```

---

## React Examples

### Display User's Subscriptions (Multiple Markets)

```typescript
import React, { useEffect, useState } from 'react';
import { Subscription } from '../types';

const MySubscriptionsPage = () => {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSubscriptions = async () => {
      try {
        const response = await fetch('/api/v1/subscriptions/me');
        const data = await response.json();
        setSubscriptions(data);
      } catch (error) {
        console.error('Failed to fetch subscriptions:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchSubscriptions();
  }, []);

  if (loading) return <div>Loading subscriptions...</div>;

  return (
    <div className="subscriptions-container">
      <h1>My Subscriptions</h1>
      {subscriptions.map(sub => (
        <div key={sub.subscription_id} className="subscription-card">
          <h3>{sub.plan_name}</h3>
          <p><strong>Market:</strong> {sub.market_name} ({sub.country_code})</p>
          <p><strong>Balance:</strong> {sub.balance} credits</p>
          <p><strong>Renewal Date:</strong> {new Date(sub.renewal_date).toLocaleDateString()}</p>
          
          {sub.subscription_status === 'On Hold' && (
            <div className="hold-banner">
              <p>⏸️ On Hold</p>
              <p>From: {new Date(sub.hold_start_date!).toLocaleDateString()}</p>
              <p>Until: {new Date(sub.hold_end_date!).toLocaleDateString()}</p>
              <button onClick={() => resumeSubscription(sub.subscription_id)}>
                Resume Subscription
              </button>
            </div>
          )}

          {sub.subscription_status === 'Active' && (
            <button onClick={() => showHoldModal(sub.subscription_id)}>
              Put on Hold
            </button>
          )}
        </div>
      ))}
    </div>
  );
};
```

---

### Market Switcher (for users with multiple subscriptions)

```typescript
import React, { useState, useEffect } from 'react';
import { Subscription } from '../types';

const MarketSwitcher = () => {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [selectedMarket, setSelectedMarket] = useState<string | null>(null);

  useEffect(() => {
    fetchSubscriptions();
  }, []);

  const fetchSubscriptions = async () => {
    const response = await fetch('/api/v1/subscriptions/me');
    const data = await response.json();
    setSubscriptions(data);

    // Default to first active subscription
    const activeSubscription = data.find(s => s.subscription_status === 'Active');
    if (activeSubscription) {
      setSelectedMarket(activeSubscription.market_id);
    }
  };

  const handleMarketChange = (marketId: string) => {
    setSelectedMarket(marketId);
    // Store in localStorage for persistent selection
    localStorage.setItem('selectedMarket', marketId);
    // Trigger app-wide market change (e.g., via context/redux)
  };

  return (
    <div className="market-switcher">
      <label>Country:</label>
      <select 
        value={selectedMarket || ''} 
        onChange={(e) => handleMarketChange(e.target.value)}
      >
        {subscriptions.map(sub => (
          <option key={sub.market_id} value={sub.market_id}>
            {sub.market_name} ({sub.country_code})
            {sub.subscription_status === 'On Hold' && ' - On Hold'}
          </option>
        ))}
      </select>
    </div>
  );
};
```

---

### Subscribe to New Market

```typescript
import React, { useState, useEffect } from 'react';
import { Market, Plan } from '../types';

const AddMarketSubscriptionPage = () => {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [selectedMarket, setSelectedMarket] = useState<string>('');
  const [plans, setPlans] = useState<Plan[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<string>('');

  useEffect(() => {
    // Fetch available markets
    const fetchMarkets = async () => {
      const response = await fetch('/api/v1/markets/enriched/');
      const data = await response.json();
      setMarkets(data);
    };
    fetchMarkets();
  }, []);

  useEffect(() => {
    if (selectedMarket) {
      // Fetch plans for selected market
      const fetchPlans = async () => {
        const response = await fetch(`/api/v1/plans/enriched/?market_id=${selectedMarket}`);
        const data = await response.json();
        setPlans(data);
      };
      fetchPlans();
    }
  }, [selectedMarket]);

  const handleSubscribe = async () => {
    try {
      const response = await fetch('/api/v1/subscriptions/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: localStorage.getItem('user_id'),
          plan_id: selectedPlan
        })
      });

      if (response.ok) {
        alert('Subscription created successfully!');
        // Navigate to subscriptions page
      } else if (response.status === 409) {
        alert('You already have an active subscription in this market.');
      } else {
        alert('Failed to create subscription');
      }
    } catch (error) {
      console.error('Error creating subscription:', error);
    }
  };

  return (
    <div>
      <h1>Add New Market Subscription</h1>
      
      <div>
        <label>Select Country:</label>
        <select value={selectedMarket} onChange={(e) => setSelectedMarket(e.target.value)}>
          <option value="">Choose a market...</option>
          {markets.map(market => (
            <option key={market.market_id} value={market.market_id}>
              {market.country_name} ({market.currency_code})
            </option>
          ))}
        </select>
      </div>

      {plans.length > 0 && (
        <div>
          <label>Select Plan:</label>
          <select value={selectedPlan} onChange={(e) => setSelectedPlan(e.target.value)}>
            <option value="">Choose a plan...</option>
            {plans.map(plan => (
              <option key={plan.plan_id} value={plan.plan_id}>
                {plan.name} - {plan.price} {plan.currency_code} ({plan.credit} credits)
              </option>
            ))}
          </select>
        </div>
      )}

      <button onClick={handleSubscribe} disabled={!selectedPlan}>
        Subscribe
      </button>
    </div>
  );
};
```

---

## Best Practices

1. **Display Active Subscriptions**: Always show subscription status (Active/On Hold) prominently
2. **Market Context**: Include market name and currency code in all subscription displays
3. **Hold Period Validation**: Validate hold dates on the frontend before submitting
4. **Error Handling**: Handle 409 Conflict errors gracefully (user already has subscription in market)
5. **Market Switcher**: For multi-market users, provide an easy way to switch between markets in the navigation
6. **Billing Clarity**: Clearly communicate that hold periods are not billed
7. **Auto-Resume**: Inform users that subscriptions auto-resume after hold end date

---

## Related Documentation

- [Markets and market scope](./MARKET_SCOPE_FOR_CLIENTS.md)
- [Enriched Endpoint Pattern](./ENRICHED_ENDPOINT_PATTERN.md)
- [API Permissions by Role](./API_PERMISSIONS_BY_ROLE.md)
