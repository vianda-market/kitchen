# Market Migration Guide

## Overview

This guide helps frontend developers migrate existing code to support the new multi-market subscription architecture. It covers API endpoint changes, schema updates, and component modifications.

---

## Breaking Changes

### API Endpoint Changes

#### No Breaking Changes to Existing Endpoints

Good news! The backend maintains backwards compatibility. Existing endpoints continue to work, but now return additional market-related fields.

**Updated Enriched Endpoints** (new fields added):
- `GET /api/v1/plans/enriched/` - Now includes `market_id`, `market_name`, `country_code`
- `GET /api/v1/subscriptions/enriched/` - Now includes `market_id`, `market_name`, `country_code`  
- `GET /api/v1/institution-bills/enriched/` - Now includes `market_id`, `market_name`, `country_code`
- `GET /api/v1/institution-bank-accounts/enriched/` - Now includes `market_id`, `market_name`, `country_code`
- `GET /api/v1/institution-entities/enriched/` - Now includes `market_id`, `market_name`, `country_code`

**New Endpoints**:
- `GET /api/v1/markets/enriched/` - List markets with currency details
- `GET /api/v1/markets/enriched/{market_id}` - Get specific market
- `GET /api/v1/credit-currencies/enriched/` - List credit currencies with market details
- `GET /api/v1/discretionary/enriched/` - List discretionary requests with market details

---

## Migration Steps

### Step 1: Update TypeScript Interfaces

#### Plans

**Before**:
```typescript
interface PlanEnriched {
  plan_id: string;
  credit_currency_id: string;
  currency_name: string;
  currency_code: string;
  name: string;
  credit: number;
  price: number;
  rollover: boolean;
  rollover_cap: number | null;
  is_archived: boolean;
  status: string;
  created_date: string;
  modified_date: string;
}
```

**After**:
```typescript
interface PlanEnriched {
  plan_id: string;
  market_id: string;          // NEW
  market_name: string;         // NEW (e.g., "Argentina")
  country_code: string;        // NEW (e.g., "ARG")
  credit_currency_id: string;
  currency_name: string;
  currency_code: string;
  name: string;
  credit: number;
  price: number;
  rollover: boolean;
  rollover_cap: number | null;
  is_archived: boolean;
  status: string;
  created_date: string;
  modified_date: string;
}
```

#### Subscriptions

**Before**:
```typescript
interface SubscriptionEnriched {
  subscription_id: string;
  user_id: string;
  user_full_name: string;
  user_username: string;
  user_email: string;
  plan_id: string;
  plan_name: string;
  plan_credit: number;
  plan_price: number;
  renewal_date: string;
  balance: number;
  is_archived: boolean;
  status: string;
}
```

**After**:
```typescript
interface SubscriptionEnriched {
  subscription_id: string;
  user_id: string;
  user_full_name: string;
  user_username: string;
  user_email: string;
  plan_id: string;
  plan_name: string;
  plan_credit: number;
  plan_price: number;
  market_id: string;           // NEW
  market_name: string;          // NEW
  country_code: string;         // NEW
  renewal_date: string;
  balance: number;
  is_archived: boolean;
  status: string;
}
```

**New Interfaces**:
```typescript
interface Market {
  market_id: string;
  country_name: string;
  country_code: string;
  credit_currency_id: string;
  currency_name: string;
  currency_code: string;
  timezone: string;
  is_archived: boolean;
  status: string;
  created_date: string;
  modified_date: string;
}

interface CreditCurrencyEnriched {
  credit_currency_id: string;
  currency_name: string;
  currency_code: string;
  credit_value: number;
  market_id: string;
  market_name: string;
  country_code: string;
  is_archived: boolean;
  status: string;
  created_date: string;
  modified_date: string;
}

interface DiscretionaryEnriched {
  discretionary_id: string;
  user_id: string | null;
  user_full_name: string | null;
  restaurant_id: string | null;
  restaurant_name: string | null;
  institution_id: string;
  institution_name: string;
  credit_currency_id: string;
  currency_name: string;
  currency_code: string;
  market_id: string;
  market_name: string;
  country_code: string;
  category: string;
  reason: string;
  amount: number;
  comment: string | null;
  status: string;
}
```

---

### Step 2: Update Component Displays

#### Add Market Column to Tables

**Plans Table**:
```typescript
// Before
<Table>
  <TableHead>
    <TableRow>
      <TableCell>Plan Name</TableCell>
      <TableCell>Credits</TableCell>
      <TableCell>Price</TableCell>
      <TableCell>Currency</TableCell>
    </TableRow>
  </TableHead>
  <TableBody>
    {plans.map(plan => (
      <TableRow key={plan.plan_id}>
        <TableCell>{plan.name}</TableCell>
        <TableCell>{plan.credit}</TableCell>
        <TableCell>{plan.price}</TableCell>
        <TableCell>{plan.currency_code}</TableCell>
      </TableRow>
    ))}
  </TableBody>
</Table>

// After
<Table>
  <TableHead>
    <TableRow>
      <TableCell>Plan Name</TableCell>
      <TableCell>Market</TableCell>        {/* NEW */}
      <TableCell>Credits</TableCell>
      <TableCell>Price</TableCell>
      <TableCell>Currency</TableCell>
    </TableRow>
  </TableHead>
  <TableBody>
    {plans.map(plan => (
      <TableRow key={plan.plan_id}>
        <TableCell>{plan.name}</TableCell>
        <TableCell>{plan.market_name}</TableCell>  {/* NEW */}
        <TableCell>{plan.credit}</TableCell>
        <TableCell>{plan.price}</TableCell>
        <TableCell>{plan.currency_code}</TableCell>
      </TableRow>
    ))}
  </TableBody>
</Table>
```

**Subscriptions Display**:
```typescript
// Before
<div className="subscription-card">
  <h3>{subscription.plan_name}</h3>
  <p>Balance: {subscription.balance} credits</p>
  <p>Renewal: {new Date(subscription.renewal_date).toLocaleDateString()}</p>
</div>

// After
<div className="subscription-card">
  <h3>{subscription.plan_name}</h3>
  <p>Market: {subscription.market_name} ({subscription.country_code})</p>  {/* NEW */}
  <p>Balance: {subscription.balance} credits</p>
  <p>Renewal: {new Date(subscription.renewal_date).toLocaleDateString()}</p>
</div>
```

---

### Step 3: Add Market Filtering

#### Plans Page with Market Filter

```typescript
import React, { useState, useEffect } from 'react';
import { Market, PlanEnriched } from '../types';

const PlansPage = () => {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [selectedMarket, setSelectedMarket] = useState<string>('');
  const [plans, setPlans] = useState<PlanEnriched[]>([]);

  // Fetch available markets
  useEffect(() => {
    const fetchMarkets = async () => {
      const response = await fetch('/api/v1/markets/enriched/');
      const data = await response.json();
      setMarkets(data);
    };
    fetchMarkets();
  }, []);

  // Fetch plans (filtered by market if selected)
  useEffect(() => {
    const fetchPlans = async () => {
      const url = selectedMarket 
        ? `/api/v1/plans/enriched/?market_id=${selectedMarket}`
        : `/api/v1/plans/enriched/`;
      
      const response = await fetch(url);
      const data = await response.json();
      setPlans(data);
    };
    fetchPlans();
  }, [selectedMarket]);

  return (
    <div>
      <h1>Subscription Plans</h1>
      
      {/* Market Filter */}
      <div className="filter-section">
        <label>Filter by Market:</label>
        <select value={selectedMarket} onChange={(e) => setSelectedMarket(e.target.value)}>
          <option value="">All Markets</option>
          {markets.map(market => (
            <option key={market.market_id} value={market.market_id}>
              {market.country_name} ({market.currency_code})
            </option>
          ))}
        </select>
      </div>

      {/* Plans Table */}
      <table>
        <thead>
          <tr>
            <th>Plan Name</th>
            <th>Market</th>
            <th>Credits</th>
            <th>Price</th>
          </tr>
        </thead>
        <tbody>
          {plans.map(plan => (
            <tr key={plan.plan_id}>
              <td>{plan.name}</td>
              <td>{plan.market_name}</td>
              <td>{plan.credit}</td>
              <td>{plan.price} {plan.currency_code}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
```

---

### Step 4: Update Form Components

#### Plan Creation Form (Suppliers)

**Before**:
```typescript
const PlanCreateForm = () => {
  const [currencyId, setCurrencyId] = useState<string>('');

  const handleSubmit = async () => {
    const payload = {
      name: planName,
      credit: planCredit,
      price: planPrice,
      credit_currency_id: currencyId,
      rollover: rollover
    };
    
    await fetch('/api/v1/plans/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  };

  return (
    <form>
      <select value={currencyId} onChange={(e) => setCurrencyId(e.target.value)}>
        {/* Currency options */}
      </select>
    </form>
  );
};
```

**After**:
```typescript
const PlanCreateForm = () => {
  const [marketId, setMarketId] = useState<string>('');         // NEW
  const [currencyId, setCurrencyId] = useState<string>('');
  const [markets, setMarkets] = useState<Market[]>([]);

  useEffect(() => {
    // Fetch markets for dropdown
    const fetchMarkets = async () => {
      const response = await fetch('/api/v1/markets/enriched/');
      const data = await response.json();
      setMarkets(data);
    };
    fetchMarkets();
  }, []);

  const handleSubmit = async () => {
    const payload = {
      name: planName,
      market_id: marketId,           // NEW - Required field
      credit: planCredit,
      price: planPrice,
      credit_currency_id: currencyId,
      rollover: rollover
    };
    
    await fetch('/api/v1/plans/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  };

  return (
    <form>
      {/* Market Selection - NEW */}
      <div>
        <label>Market:</label>
        <select value={marketId} onChange={(e) => setMarketId(e.target.value)} required>
          <option value="">Select Market</option>
          {markets.map(market => (
            <option key={market.market_id} value={market.market_id}>
              {market.country_name} ({market.currency_code})
            </option>
          ))}
        </select>
      </div>

      {/* Currency Selection */}
      <select value={currencyId} onChange={(e) => setCurrencyId(e.target.value)}>
        {/* Currency options */}
      </select>
    </form>
  );
};
```

---

### Step 5: Add Super Admin Checks

#### Markets Management Page (Super Admin Only)

```typescript
import React, { useState, useEffect } from 'react';

const MarketsManagementPage = () => {
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [markets, setMarkets] = useState<Market[]>([]);

  useEffect(() => {
    // Check if current user is Super Admin
    // Option 1: From JWT
    const token = localStorage.getItem('authToken');
    if (token) {
      const decoded = JSON.parse(atob(token.split('.')[1]));
      setIsSuperAdmin(decoded.role_name === 'Super Admin');
    }

    // Option 2: From /users/me endpoint
    const fetchUserRole = async () => {
      const response = await fetch('/api/v1/users/me');
      const user = await response.json();
      setIsSuperAdmin(user.role_name === 'Super Admin');
    };
    // fetchUserRole();

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

    await fetch(`/api/v1/markets/${marketId}`, { method: 'DELETE' });
    fetchMarkets();
  };

  return (
    <div>
      <h1>Markets Management</h1>
      {!isSuperAdmin && <p className="warning">Read-only view (Admin)</p>}
      
      {isSuperAdmin && (
        <button onClick={() => navigateToCreateMarket()}>
          Create New Market
        </button>
      )}

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

## Testing Checklist

### Unit Tests

- [ ] Market dropdown renders correctly
- [ ] Plan creation includes `market_id`
- [ ] Subscription display shows market name
- [ ] Super Admin checks work correctly
- [ ] Market filter updates plan list

### Integration Tests

- [ ] Market selection filters plans correctly
- [ ] User can subscribe to multiple markets
- [ ] Subscription on hold displays correctly
- [ ] Super Admin can create/edit markets
- [ ] Regular Admin cannot edit markets
- [ ] Suppliers can view markets for dropdown

### Manual Testing

- [ ] All tables display market column correctly
- [ ] Market filter works on Plans page
- [ ] Subscription cards show market info
- [ ] Multi-market subscriptions display correctly
- [ ] Market switcher (if implemented) works
- [ ] Super Admin vs Admin permissions work correctly

---

## Rollback Plan

If issues arise, the frontend can safely ignore new fields without breaking:

1. **New Fields are Optional**: All new market fields are added to existing responses, but not required for requests
2. **Backwards Compatible**: Existing API calls continue to work
3. **Gradual Migration**: You can update components one at a time
4. **Feature Flags**: Consider using feature flags to gradually roll out market-related UI

**Rollback Steps**:
1. Remove market-related UI components
2. Revert TypeScript interfaces to pre-migration versions
3. Backend continues to send market fields (harmless if ignored)
4. No backend changes needed for rollback

---

## Common Issues & Solutions

### Issue: `market_id` required error when creating plans

**Solution**: Ensure all plan creation forms include `market_id` field:
```typescript
const payload = {
  name: planName,
  market_id: selectedMarket,  // REQUIRED
  credit_currency_id: currencyId,
  // ... other fields
};
```

### Issue: TypeScript errors for missing market fields

**Solution**: Update interfaces to include new fields:
```typescript
interface PlanEnriched {
  // ... existing fields
  market_id: string;
  market_name: string;
  country_code: string;
}
```

### Issue: 404 on `/api/v1/markets/enriched/`

**Solution**: Verify backend is running the latest version. Check server logs for routing errors.

### Issue: Market filter not working

**Solution**: Ensure query parameter is correct:
```typescript
// Correct
`/api/v1/plans/enriched/?market_id=${marketId}`

// Incorrect
`/api/v1/plans/enriched/?market=${marketId}`
```

---

## Performance Considerations

1. **Cache Market Data**: Markets change infrequently - cache market list with 1-hour TTL
2. **Lazy Load Plans**: Only load plans for selected market to reduce initial load time
3. **Index Market Fields**: Backend has indexed market_id for fast filtering
4. **Batch Requests**: If fetching multiple markets, use enriched endpoint once instead of multiple calls

---

## Related Documentation

- [Markets API](./MARKETS_API_CLIENT.md)
- [Market-Based Subscriptions](./MARKET_BASED_SUBSCRIPTIONS.md)
- [Enriched Endpoint Pattern](./ENRICHED_ENDPOINT_PATTERN.md)
- [API Permissions by Role](./API_PERMISSIONS_BY_ROLE.md)
