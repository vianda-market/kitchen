# Plans Filter – Client Integration Guide

## Overview

The Plans enriched list endpoint (`GET /api/v1/plans/enriched/`) supports optional query filters so clients (Web, iOS, Android) can narrow results by market, status, and currency code. Filters are combined with AND logic. The response shape is identical whether filters are used or not.

---

## Endpoint

```http
GET /api/v1/plans/enriched/
```

**Authorization**: Clients and Employees (Customers and Employees can view; Suppliers cannot).

---

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `include_archived` | boolean | No (default: false) | Include archived plans |
| `market_id` | UUID | No | Filter plans to a single market |
| `status` | string | No | Filter by plan status (`Active`, `Inactive`) |
| `currency_code` | string | No | Filter by currency code (e.g. `ARS`, `USD`, `PEN`, `CLP`) |

All filter parameters are optional. When omitted, all plans (subject to auth and `include_archived`) are returned. When present, filters are applied with AND logic.

---

## Request Examples

**No filters (all plans)**:
```http
GET /api/v1/plans/enriched/
```

**Filter by market**:
```http
GET /api/v1/plans/enriched/?market_id=11111111-1111-1111-1111-111111111111
```

**Filter by status**:
```http
GET /api/v1/plans/enriched/?status=Active
```

**Filter by currency**:
```http
GET /api/v1/plans/enriched/?currency_code=ARS
```

**Combined filters**:
```http
GET /api/v1/plans/enriched/?market_id=11111111-1111-1111-1111-111111111111&status=Active&currency_code=USD
```

---

## Response Shape

The response is always a JSON array of plan objects (or empty array `[]`), regardless of filters. Each plan has:

```json
[
  {
    "plan_id": "11111111-aaaa-aaaa-aaaa-111111111111",
    "market_id": "11111111-1111-1111-1111-111111111111",
    "market_name": "Argentina",
    "country_code": "AR",
    "credit_currency_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "currency_name": "Argentine Peso",
    "currency_code": "ARS",
    "name": "Argentina Basic",
    "credit": 20,
    "price": 5000.00,
    "rollover": true,
    "rollover_cap": null,
    "is_archived": false,
    "status": "Active",
    "created_date": "2026-01-15T10:00:00Z",
    "modified_date": "2026-01-15T10:00:00Z"
  }
]
```

**Rollover fields:** All plans currently have `rollover: true` and `rollover_cap: null` (unlimited). B2B clients should hide these fields from plan create/edit UI. B2C clients may use them for display (rollover badge, "no cap" messaging). See [../b2b_client/PLAN_ROLLOVER_UI_HIDDEN.md](../b2b_client/PLAN_ROLLOVER_UI_HIDDEN.md) and [../b2c_client/CREDIT_ROLLOVER_DISPLAY_B2C.md](../b2c_client/CREDIT_ROLLOVER_DISPLAY_B2C.md).

---

## Behavior

| Scenario | Result |
|----------|--------|
| No filters | All plans (per auth and `include_archived`) |
| Valid filter(s) | Plans matching all filters; empty array if none |
| Unknown `market_id` (valid UUID, no plans) | Empty array `[]` |
| Invalid `market_id` (malformed UUID) | 422 Unprocessable Entity (FastAPI validation) |
| Unknown `status` or `currency_code` | Empty array `[]` |
| `currency_code` | Case-insensitive (e.g. `ars` and `ARS` both match) |

---

## Web (React / TypeScript)

### TypeScript interface

```typescript
interface PlanEnriched {
  plan_id: string;
  market_id: string;
  market_name: string;
  country_code: string;
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

interface PlansFilterParams {
  market_id?: string;
  status?: string;
  currency_code?: string;
  include_archived?: boolean;
}
```

### Fetch with filters

```typescript
const fetchPlans = async (filters: PlansFilterParams = {}) => {
  const params = new URLSearchParams();
  if (filters.market_id) params.set('market_id', filters.market_id);
  if (filters.status) params.set('status', filters.status);
  if (filters.currency_code) params.set('currency_code', filters.currency_code);
  if (filters.include_archived) params.set('include_archived', 'true');

  const url = `/api/v1/plans/enriched/${params.toString() ? '?' + params.toString() : ''}`;
  const response = await fetch(url, {
    headers: { Authorization: `Bearer ${getAuthToken()}` },
  });

  if (!response.ok) throw new Error('Failed to fetch plans');
  return response.json() as Promise<PlanEnriched[]>;
};
```

### Plans table with filter dropdowns

```typescript
const PlansPage = () => {
  const [plans, setPlans] = useState<PlanEnriched[]>([]);
  const [markets, setMarkets] = useState<Market[]>([]);
  const [marketId, setMarketId] = useState<string>('');
  const [status, setStatus] = useState<string>('');
  const [currencyCode, setCurrencyCode] = useState<string>('');

  useEffect(() => {
    fetchMarkets().then(setMarkets);
  }, []);

  useEffect(() => {
    fetchPlans({
      market_id: marketId || undefined,
      status: status || undefined,
      currency_code: currencyCode || undefined,
    }).then(setPlans);
  }, [marketId, status, currencyCode]);

  return (
    <div>
      <h1>Plans</h1>
      <div className="filters">
        <select
          value={marketId}
          onChange={(e) => setMarketId(e.target.value)}
        >
          <option value="">All Markets</option>
          {markets.map((m) => (
            <option key={m.market_id} value={m.market_id}>
              {m.country_name} ({m.currency_code})
            </option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">All Statuses</option>
          <option value="Active">Active</option>
          <option value="Inactive">Inactive</option>
        </select>
        <select
          value={currencyCode}
          onChange={(e) => setCurrencyCode(e.target.value)}
        >
          <option value="">All Currencies</option>
          <option value="ARS">ARS</option>
          <option value="PEN">PEN</option>
          <option value="CLP">CLP</option>
          <option value="USD">USD</option>
        </select>
      </div>
      <table>
        <thead>
          <tr>
            <th>Plan</th>
            <th>Market</th>
            <th>Currency</th>
            <th>Price</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {plans.map((p) => (
            <tr key={p.plan_id}>
              <td>{p.name}</td>
              <td>{p.market_name}</td>
              <td>{p.currency_code}</td>
              <td>{p.price}</td>
              <td>{p.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
```

---

## iOS (Swift)

```swift
struct PlanEnriched: Codable {
    let planId: UUID
    let marketId: UUID
    let marketName: String
    let countryCode: String
    let currencyName: String
    let currencyCode: String
    let name: String
    let credit: Int
    let price: Double
    let status: String
    // ... other fields; use CodingKeys if needed for snake_case
}

func fetchPlans(
    marketId: UUID? = nil,
    status: String? = nil,
    currencyCode: String? = nil
) async throws -> [PlanEnriched] {
    var components = URLComponents(string: baseURL + "/api/v1/plans/enriched/")!
    var queryItems: [URLQueryItem] = []
    if let id = marketId { queryItems.append(URLQueryItem(name: "market_id", value: id.uuidString)) }
    if let s = status { queryItems.append(URLQueryItem(name: "status", value: s)) }
    if let c = currencyCode { queryItems.append(URLQueryItem(name: "currency_code", value: c)) }
    if !queryItems.isEmpty { components.queryItems = queryItems }

    var request = URLRequest(url: components.url!)
    request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")

    let (data, _) = try await URLSession.shared.data(for: request)
    return try JSONDecoder().decode([PlanEnriched].self, from: data)
}
```

---

## Android (Kotlin)

```kotlin
data class PlanEnriched(
    val plan_id: String,
    val market_id: String,
    val market_name: String,
    val country_code: String,
    val currency_code: String,
    val name: String,
    val price: Double,
    val status: String,
    // ... other fields
)

suspend fun fetchPlans(
    marketId: String? = null,
    status: String? = null,
    currencyCode: String? = null
): List<PlanEnriched> {
    val url = buildString {
        append("$baseUrl/api/v1/plans/enriched/")
        val params = listOfNotNull(
            marketId?.let { "market_id=$it" },
            status?.let { "status=$it" },
            currencyCode?.let { "currency_code=$it" }
        )
        if (params.isNotEmpty()) append("?").append(params.joinToString("&"))
    }

    return httpClient.get(url) {
        header("Authorization", "Bearer $authToken")
    }.body()
}
```

---

## Best Practices

1. **Same response handling**: Parse the response as `PlanEnriched[]` regardless of filters; no special handling.
2. **Empty list**: Treat `[]` as “no matching plans”, not an error.
3. **Filter persistence**: Store selected filters (e.g. in URL or local state) so users see consistent results.
4. **Market dropdown**: Populate from `GET /api/v1/markets/enriched/` and use `market_id` for the filter.
5. **Currency codes**: Use values from markets/plans (e.g. ARS, PEN, CLP, USD).

---

## Related Documentation

- [Market scope for clients](./MARKET_SCOPE_FOR_CLIENTS.md) – Market dropdown data (use GET /markets/enriched/; exclude Global for plan)
- [Market-Based Subscriptions](./MARKET_BASED_SUBSCRIPTIONS.md) – Plans and subscriptions flow
- [Enriched Endpoint Pattern](./ENRICHED_ENDPOINT_PATTERN.md) – Enriched API conventions
