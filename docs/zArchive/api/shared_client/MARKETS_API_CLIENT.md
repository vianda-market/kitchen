**ARCHIVED — Merged into [MARKET_SCOPE_FOR_CLIENTS.md](../../../api/shared_client/MARKET_SCOPE_FOR_CLIENTS.md). Content below kept for history.**

---

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

### Public Endpoint (No Auth) – Market Selector Source of Truth

- **GET /api/v1/markets/available**: Returns the list of **active, non-archived** markets. **No authentication required.** Use this as the single source of truth for the market dropdown (e.g. default by browser country, fallback to US; user can override).
- **Rate-limited** (e.g. 60 requests per minute per IP). **Cached** on the server (e.g. 10 minutes).
- **Write operations** (POST/PUT/DELETE) remain employee-only; this endpoint is read-only.

### Base vs Enriched Endpoints (Authenticated)

- **Base Endpoints** (`/api/v1/markets/`): Returns basic market data (any authenticated user)
- **Enriched Endpoints** (`/api/v1/markets/enriched/`): Returns market data with currency details (any authenticated user)

**Recommendation**: For the **market selector** (including pre-login or first load), use **GET /api/v1/markets/available**. For authenticated flows that need full details, use the enriched endpoints.

---

(Full original content omitted for brevity; see git history or MARKET_SCOPE_FOR_CLIENTS.md for API details, TypeScript interfaces, and React examples.)
