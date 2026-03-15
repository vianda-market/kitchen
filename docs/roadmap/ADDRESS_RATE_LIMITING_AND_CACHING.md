# Address Autocomplete Rate Limiting and Caching

**Last Updated**: 2026-03-09  
**Purpose**: Abuse prevention, cost control, and fairness for address suggest and create.

---

## Use Cases

| Use Case | Description |
|----------|-------------|
| Abuse prevention | Malicious or buggy clients spamming suggest |
| Cost control | Cap Google API spend during spikes |
| Fairness | Per-user limits so one client cannot starve others |

---

## Rate Limiting

### Suggest

- **Per-user limit**: e.g. 60 requests/minute (adjust for UX: debounce ~300ms, 3–5 suggests per address)
- **Per-IP limit** (unauthenticated if any): Fallback for abuse
- **Implementation**: In-memory (simple) or Redis (distributed)
- **Response**: 429 Too Many Requests with Retry-After

### Create (place_id)

- Typically low volume (1 per address)
- Optional: 10/minute per user for bulk imports
- Less critical than suggest

---

## Caching

### Suggest Results

- **Key**: `(q, country, province, city)` normalized
- **TTL**: 5–15 minutes (addresses rarely change; same query → same suggestions)
- **Storage**: In-memory (single instance) or Redis (multi-instance)
- **Risk**: Stale cache if Google updates; acceptable for address autocomplete
- **Benefit**: Reduce API calls for repeated or popular queries

### Place Details (create)

- **Key**: `place_id`
- **TTL**: Long (days); place data is stable
- **Benefit**: Deduplication when same place_id created multiple times
- **Note**: We already store in geolocation_info; no need to re-fetch for same place_id if we add lookup

---

## Implementation Options

| Option | Pros | Cons |
|--------|------|------|
| In-memory (e.g. slowapi) | Simple, no deps | Per-instance only; lost on restart |
| Redis | Distributed, persistent | Requires Redis |
| API Gateway (Kong, etc.) | Centralized | External infra |

---

## Risks

- **Stale cache**: User gets old suggestions; mitigate with reasonable TTL
- **Per-user vs global**: Per-user fair; global simpler but one user can exhaust
- **Cold start**: No cache → full API cost on first requests
