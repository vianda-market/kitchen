# Referral System – Plan

**Status**: Plan
**Last Updated**: 2026-04
**Purpose**: Allow registered users to refer new users to Vianda. When a referred user becomes a paid subscriber, the referrer earns bonus credits proportional to the plan price. Configurable per market, abuse-resistant, and built on existing credit infrastructure.

---

## 1. Context and goals

### 1.1 What this system is

A growth mechanism where existing Vianda users share a personal referral link. When a non-user registers through that link and completes their first paid subscription, the referrer receives bonus credits added to their subscription balance. The bonus scales with the plan price — higher-value plans yield more referral credits.

### 1.2 Terminology

| Term | Definition |
|---|---|
| **Referrer** | An existing registered user who shares their referral link. Must have an active subscription to receive credits. If the referrer's subscription is not active when the qualifying event occurs, the reward is held for up to 48 hours — if the referrer activates within that window, credits are issued; otherwise the reward is forfeited. |
| **Referee** | A new user who registers via the referral link. |
| **Referral code** | A unique, permanent, human-readable code assigned to each user (e.g., `MARIA-V7X2`). |
| **Referral link** | A URL containing the referral code: `https://vianda.app/r/{referral_code}` |
| **Qualifying event** | The referee's first paid subscription payment is confirmed (status = `active`, balance > 0). |
| **Referral bonus** | Credits awarded to the referrer upon qualifying event. Computed as a percentage of the referee's plan price. |
| **Referral config** | Per-market configuration that controls bonus rates, caps, and program status. |

### 1.3 Design principles

1. **Static referral code per user**: Each user gets one permanent code (not a new link per share). This is industry best practice — simpler for users to remember and share verbally, easier to track, and prevents link sprawl. The code is generated at user creation time.
2. **Reward on first payment only**: The referral bonus triggers once — when the referee's first subscription payment succeeds. Subsequent renewals do not trigger additional referral rewards. This prevents gaming via repeated cancel/resubscribe cycles.
3. **Proportional bonus**: The referral credit is a configurable percentage of the referee's plan price. Higher-value plans generate more bonus credits, aligning incentives with revenue.
4. **Reuse existing credit infrastructure, distinct transaction type**: Referral bonuses flow through `billing.client_transaction` for balance updates, but use a dedicated `source = 'referral_program'` to distinguish them from discretionary promotions, refunds, and orders. This keeps the credit pipeline unified while giving clear attribution in reporting and audit.
5. **Per-market configuration**: Referral program settings (enabled/disabled, bonus percentage, caps) are stored in a DB table and configurable per market. No hardcoded values.
6. **Double-sided rewards** (future-ready): The schema supports optional referee rewards (e.g., "you also get 10% off your first plan"), but MVP launches with referrer-only rewards to keep scope tight.

---

## 2. Referral link design — static code

### 2.1 Why static over dynamic

| Approach | Pros | Cons |
|---|---|---|
| **Static code** (one per user, permanent) | Simple sharing (verbal, social, print); no link management UI; easy support lookup; works across channels | Less per-campaign attribution granularity |
| **Dynamic links** (new link per share) | Per-share tracking; can expire individual links | Users confused by multiple links; link management overhead; harder to share verbally |

**Decision**: Static code. Industry leaders (Dropbox, Uber, Revolut) all converged on static codes. For a food subscription platform, simplicity wins — users share codes at the office, over WhatsApp, on social media. A single memorable code maximizes sharing.

### 2.2 Code format

- **Pattern**: `{FIRST_NAME_UPPER}-{4_ALPHANUM}` → e.g., `MARIA-V7X2`, `CARLOS-9KTP`
- **Uniqueness**: Enforced at DB level (UNIQUE constraint on `referral_code`).
- **Generation**: On user creation. Collision retry with different random suffix (4-char alphanumeric gives 1.6M combinations per name — collisions are negligible).
- **Characters**: Uppercase letters + digits, no ambiguous chars (0/O, 1/I/L excluded from random suffix).
- **Immutable**: Once assigned, the code never changes. Users can share it confidently.

### 2.3 Referral link

The frontend constructs the link: `https://vianda.app/r/{referral_code}` (or market-specific domain).

The registration flow reads the `ref` query param or path segment and attaches it to the new user record as `referred_by_code`.

---

## 3. Referral configuration — per-market settings

### 3.1 Table: `customer.referral_config`

Stores referral program configuration per market. One row per market.

| Column | Type | Description |
|---|---|---|
| `referral_config_id` | UUID PK | |
| `market_id` | UUID FK UNIQUE | One config per market |
| `is_enabled` | BOOLEAN | Whether the referral program is active in this market |
| `referrer_bonus_rate` | INTEGER | Percentage of referee's plan price awarded as credits (e.g., 15 → 15%) |
| `referrer_bonus_cap` | NUMERIC NULL | Max credits a referrer can earn per single referral. NULL = no cap |
| `referrer_monthly_cap` | INTEGER NULL | Max referral rewards a user can earn per calendar month. NULL = unlimited |
| `referee_bonus_credits` | INTEGER DEFAULT 0 | Bonus credits the referee gets on their first subscription (future use, MVP = 0) |
| `min_plan_price_to_qualify` | NUMERIC DEFAULT 0 | Minimum plan price for the referral to qualify (prevents gaming with free/trial plans) |
| `cooldown_days` | INTEGER DEFAULT 0 | Days after reward before same referrer can earn another reward (anti-abuse) |
| `is_archived` | BOOLEAN DEFAULT FALSE | |
| `status` | status_enum DEFAULT 'active' | |
| Audit columns | | `created_date`, `created_by`, `modified_by`, `modified_date` |

### 3.2 Default configuration (MVP)

```
referrer_bonus_rate = 15          -- 15% of referee's plan price as credits
referrer_bonus_cap = NULL         -- no per-referral cap
referrer_monthly_cap = 5          -- max 5 referral rewards per month
referee_bonus_credits = 0         -- no referee bonus (MVP)
min_plan_price_to_qualify = 0     -- any paid plan qualifies
cooldown_days = 0                 -- no cooldown
```

**Example**: Referee subscribes to a plan costing 20 credits at $90. Referrer gets `90 × 0.15 = 13.5` → 13 credits (rounded down) added to their balance.

---

## 4. Referral tracking — per-referral record

### 4.1 Table: `customer.referral_info`

Tracks each individual referral relationship and its lifecycle.

| Column | Type | Description |
|---|---|---|
| `referral_id` | UUID PK | |
| `referrer_user_id` | UUID FK | The user who shared the code |
| `referee_user_id` | UUID FK UNIQUE | The user who registered with the code (one referral per user) |
| `referral_code_used` | VARCHAR | The code used at registration (denormalized for audit) |
| `market_id` | UUID FK | Market where referral occurred |
| `referral_status` | referral_status_enum | `pending` → `qualified` → `rewarded` or `expired` or `cancelled` |
| `bonus_credits_awarded` | NUMERIC NULL | Credits awarded to referrer (set when status = rewarded) |
| `bonus_plan_price` | NUMERIC NULL | The referee's plan price used for calculation (audit trail) |
| `bonus_rate_applied` | INTEGER NULL | The bonus rate at time of reward (audit trail — rate may change later) |
| `qualified_date` | TIMESTAMPTZ NULL | When the referee's first payment was confirmed |
| `rewarded_date` | TIMESTAMPTZ NULL | When credits were issued to the referrer |
| `transaction_id` | UUID FK NULL | Links to the `client_transaction` that issued the credits |
| `reward_held_until` | TIMESTAMPTZ NULL | Deadline for held rewards (set when referrer lacks active subscription at qualification time) |
| `is_archived` | BOOLEAN DEFAULT FALSE | |
| `status` | status_enum DEFAULT 'active' | |
| Audit columns | | `created_date`, `created_by`, `modified_by`, `modified_date` |

### 4.2 Referral status lifecycle

```
PENDING     → User registered with referral code, has not yet subscribed
QUALIFIED   → Referee's first subscription payment confirmed. If referrer has active subscription,
              transitions immediately to REWARDED. If not, reward is held for up to 48 hours.
REWARDED    → Referrer credits have been issued
EXPIRED     → Referee did not subscribe within 90 days, OR referrer did not activate within
              the 48-hour hold window after qualification
CANCELLED   → Referral voided (e.g., referee refunded, fraud detected)
```

### 4.3 Enum: `referral_status_enum`

```python
class ReferralStatus(str, Enum):
    PENDING = "pending"
    QUALIFIED = "qualified"
    REWARDED = "rewarded"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
```

---

## 5. User model changes

### 5.1 New column on `core.user_info`

| Column | Type | Description |
|---|---|---|
| `referral_code` | VARCHAR(20) UNIQUE | The user's personal referral code, generated at creation |
| `referred_by_code` | VARCHAR(20) NULL | The referral code used during registration (NULL if organic) |

**Why on user_info and not a separate table**: The referral code is a 1:1 attribute of the user, queried on every registration and profile view. A JOIN for this would be unnecessary overhead.

---

## 6. Bonus calculation

### 6.1 Formula

```
plan_price        = referee's selected plan price (local currency)
bonus_rate        = referral_config.referrer_bonus_rate / 100
raw_bonus         = plan_price × bonus_rate
capped_bonus      = MIN(raw_bonus, referrer_bonus_cap)      -- if cap is set
credit_value      = credit_currency.credit_value_local_currency
bonus_credits     = FLOOR(capped_bonus / credit_value)       -- convert to credits, round down
```

### 6.2 Examples (AR market, 1 credit = 500 ARS)

| Plan | Price (ARS) | Bonus rate | Raw bonus | Credits awarded |
|---|---|---|---|---|
| Basic (10 credits) | 5,000 | 15% | 750 | 1 credit |
| Standard (20 credits) | 9,000 | 15% | 1,350 | 2 credits |
| Premium (30 credits) | 12,000 | 15% | 1,800 | 3 credits |

The proportional model naturally incentivizes referrers to attract higher-value subscribers.

---

## 7. Integration with existing systems

### 7.1 Credit issuance — via client transaction with `referral_program` source

When a referral reaches `QUALIFIED`:
1. Check referrer has an active subscription:
   - **Active**: Issue credits immediately (step 2)
   - **Not active**: Set referral status to `QUALIFIED` and hold. A cron job retries every 12 hours for up to 48 hours. If the referrer activates within that window, credits are issued. After 48 hours without activation, the reward is forfeited and referral status → `EXPIRED`.
2. Create `billing.client_transaction` with `source = 'referral_program'` and `referral_id` FK to link back to the referral record
3. Update referrer's subscription balance
4. Update `customer.referral_info.referral_status` → `REWARDED`, set `rewarded_date`, `transaction_id`

This reuses the existing credit transaction pipeline but with a dedicated source for clear attribution in reports, distinct from discretionary promotions and refunds.

### 7.2 New transaction source

Add `'referral_program'` as a valid `source` value in `billing.client_transaction`. This is the key differentiator — referral credits are **not** discretionary credits. They have their own source, enabling:
- Filtered reporting (referral spend vs. marketing spend vs. refunds)
- Separate audit trail per program
- Independent policy controls (e.g., referral credits don't count toward discretionary budgets)

### 7.4 Subscription payment hook

The qualifying event is detected in the subscription payment flow (`subscription_payment.py`):
- After `confirm-payment` succeeds for a user with a non-NULL `referred_by_code`
- Check if this is the user's first successful subscription payment
- If yes, trigger the referral qualification + reward flow

---

## 8. API endpoints

### 8.1 User-facing

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/v1/referrals/my-code` | Customer | Returns current user's referral code and shareable link |
| `GET` | `/api/v1/referrals/my-referrals` | Customer | Lists referrals made by current user (status, referee name, credits earned) |
| `GET` | `/api/v1/referrals/stats` | Customer | Summary: total referrals, total credits earned, pending referrals |

### 8.2 Admin-facing

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/v1/admin/referrals` | Internal | List all referrals (filterable by market, status, date range) |
| `GET` | `/api/v1/admin/referrals/{referral_id}` | Internal | Referral detail |
| `PUT` | `/api/v1/admin/referrals/{referral_id}/cancel` | Internal | Cancel a referral (fraud, abuse) |
| `GET` | `/api/v1/admin/referral-config` | Internal | List referral configs per market |
| `GET` | `/api/v1/admin/referral-config/enriched` | Internal | List referral configs with `market_name` and `country_code` (B2B table view) |
| `PUT` | `/api/v1/admin/referral-config/{market_id}` | Internal | Update referral config for a market |

### 8.3 Registration integration

`POST /api/v1/customers/signup/request` — accepts optional `referral_code` field. The registration flow:
1. Validate the code exists (lookup by `referral_code` on `core.user_info`)
2. Store `referred_by_code` on the new user
3. Create `customer.referral_info` record with status = `PENDING`

Alternatively, the referral code can arrive via device-based pre-assignment (see 8.4).

### 8.4 Pre-auth referral code assignment (deep link lifecycle)

The B2C app uses deep links (`https://vianda.app/r/{CODE}`) to drive referral signups. When a user taps the link but doesn't complete signup immediately (closes app, restarts phone), the referral code is lost unless persisted server-side. This flow solves that:

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/referrals/assign-code` | None (public) | Associate a referral code with a device fingerprint |
| `GET` | `/api/v1/referrals/assigned-code` | None (public) | Check if a device has an assigned code |

**`POST /api/v1/referrals/assign-code`**

```json
{
  "referral_code": "CARLOS-V7X2",
  "device_id": "<device fingerprint>"
}
```

- Validates the referral code exists
- Stores `(device_id, referral_code, created_at)` in `customer.referral_code_assignment`
- If the device already has an assignment, the new code **replaces** it (last link wins)
- Returns `200` with `{ "success": true, "referral_code": "CARLOS-V7X2" }`
- Invalid code returns `400`
- Rate-limited: 10/minute per IP

**`GET /api/v1/referrals/assigned-code?device_id={device_id}`**

- Returns `{ "referral_code": "CARLOS-V7X2" }` if an active (non-expired) assignment exists
- Returns `404` if no assignment or expired

**Lifecycle**:
- Assignments auto-expire after **48 hours** (enforced by query filter, cleaned by cron)
- When `POST /customers/signup/request` is called, if no `referral_code` in the body, the backend checks for an active assignment matching the `device_id` header (`X-Device-Id`)
- On successful signup, the assignment is marked as `used`

**Table: `customer.referral_code_assignment`**

| Column | Type | Description |
|---|---|---|
| `assignment_id` | UUID PK | |
| `device_id` | VARCHAR(255) NOT NULL | Device fingerprint from client |
| `referral_code` | VARCHAR(20) NOT NULL | The referral code assigned |
| `used` | BOOLEAN DEFAULT FALSE | Marked true when signup consumes the code |
| `created_at` | TIMESTAMPTZ DEFAULT NOW | Auto-expires after 48h |

Index: `UNIQUE ON (device_id) WHERE used = FALSE` — one active assignment per device.

**Anti-abuse**: Rate-limited, no PII stored (device_id is an opaque fingerprint), short TTL, unauthenticated but low-value target.

---

## 9. Anti-abuse measures

### 9.1 Built-in protections

| Protection | Mechanism |
|---|---|
| **Self-referral** | Cannot use own referral code at registration (backend validation) |
| **Duplicate referral** | `referee_user_id` is UNIQUE — one referral per user, ever |
| **Monthly cap** | `referrer_monthly_cap` limits rewards per calendar month per referrer |
| **Cooldown** | `cooldown_days` prevents rapid-fire reward collection |
| **Payment required** | Reward only triggers on confirmed payment — free/trial signups don't qualify |
| **Min plan price** | `min_plan_price_to_qualify` blocks gaming with throwaway low-price plans |
| **Refund clawback** | If referee's payment is refunded within 30 days, referral status → `CANCELLED` and credits are debited |

### 9.2 Future anti-abuse (not MVP)

- **IP/device fingerprint matching**: Flag referrals from same IP or device as referrer
- **Email domain clustering**: Detect bulk signups from disposable email domains
- **Velocity alerts**: Admin notification when a user exceeds N referrals in a short window
- **Tiered rewards**: Decreasing bonus rate after N referrals per month (diminishing returns)

---

## 10. Notification touchpoints

| Event | Recipient | Channel |
|---|---|---|
| Referee registers | Referrer | Push + in-app: "Your friend {name} just joined Vianda!" |
| Referee subscribes (reward issued) | Referrer | Push + in-app: "You earned {N} credits from referring {name}!" |
| Referee subscribes | Referee | In-app: "Welcome! You were referred by {referrer_name}" |
| Referral expired | Referrer | In-app: "Your referral to {email} expired (they didn't subscribe)" |
| Monthly cap reached | Referrer | In-app: "You've hit your monthly referral cap. Resets next month!" |

---

## 11. DB changes summary

### 11.1 New tables

1. `customer.referral_config` — per-market program settings
2. `customer.referral_info` — individual referral tracking
3. `customer.referral_code_assignment` — pre-auth device-to-code mapping for deep link lifecycle

### 11.2 Modified tables

1. `core.user_info` — add `referral_code` (VARCHAR UNIQUE), `referred_by_code` (VARCHAR NULL)

### 11.3 New enums

1. `referral_status_enum` — `pending`, `qualified`, `rewarded`, `expired`, `cancelled`

### 11.4 Modified tables/columns

1. `billing.client_transaction.source` — add `'referral_program'` as valid value

### 11.5 History tables

- `audit.user_info_history` — add `referral_code`, `referred_by_code`
- Create `audit.referral_info_history`, `audit.referral_config_history`

### 11.6 Triggers

- `core.user_info` trigger — include `referral_code`, `referred_by_code` in audit INSERT
- New triggers for `customer.referral_info` and `customer.referral_config`

---

## 12. Implementation phases

### Phase 1 — Foundation (MVP) `DONE`

1. DB: Add `referral_code` and `referred_by_code` to `core.user_info`
2. DB: Create `customer.referral_config` and `customer.referral_info` tables
3. DB: Create enums, history tables, triggers
4. Generate referral codes for all existing users (backfill migration in seed.sql)
5. Generate referral code at user creation time
6. Registration: Accept `referral_code` param, validate, store, create referral record
7. Service: `referral_service.py` — code validation, referral creation, reward calculation
8. Admin API: CRUD for `referral_config`
9. User API: `GET /my-code`, `GET /my-referrals`, `GET /stats`

### Phase 2 — Reward flow `DONE`

1. Hook into subscription payment confirmation to detect qualifying events
2. Implement reward calculation (proportional to plan price)
3. Issue credits via `client_transaction` with `source = 'referral_program'`
4. Update referral status lifecycle (pending → qualified → rewarded)
5. Held-reward cron job: retry every 12h for `QUALIFIED` referrals where referrer lacks active subscription, expire after 48h
6. Expiration cron job (mark stale pending referrals as expired after market's `pending_expiry_days`)
7. Admin API: cron trigger endpoint

### Phase 2.5 — Cross-repo integration support (B2B enriched + B2C deep link lifecycle)

**Driven by**: B2B agent (`vianda-platform/docs/plans/REFERRAL_CONFIG_ADMIN_PLAN.md`) and B2C agent (`vianda-app/docs/plans/referral_system.md`).

#### B2B: Enriched referral config endpoint

1. Add `GET /api/v1/admin/referral-config/enriched` — JOIN `referral_config` with `market_info` to include `market_name` and `country_code` in the response
2. New schema: `ReferralConfigEnrichedResponseSchema` — extends `ReferralConfigResponseSchema` with `market_name: str` and `country_code: str`
3. SQL: `SELECT rc.*, m.country_name AS market_name, m.country_code FROM referral_config rc JOIN market_info m ON rc.market_id = m.market_id WHERE rc.is_archived = FALSE`
4. Add to `app/routes/admin/referral_config.py`

#### B2C: Pre-auth referral code assignment (deep link lifecycle)

1. DB: Create `customer.referral_code_assignment` table (see 8.4 for schema)
2. Public endpoints (no auth, rate-limited):
   - `POST /api/v1/referrals/assign-code` — associate referral code with device_id
   - `GET /api/v1/referrals/assigned-code?device_id=` — check active assignment
3. Signup integration: If `POST /customers/signup/request` has no `referral_code` in body, check for active assignment via `X-Device-Id` header
4. Assignment cleanup: Extend referral cron to expire assignments older than 48h
5. Add to `app/routes/customer/referral.py` (the assign/check endpoints are public, not behind auth)

#### Infra: Universal link support

- `vianda-home` must serve `/.well-known/apple-app-site-association` and `/.well-known/assetlinks.json` for `vianda.app/r/{CODE}` deep links to open the B2C app directly. Flag for **infra-kitchen-gcp** agent.

### Phase 3 — Polish & growth

1. Notification integration (push + in-app for referral events)
2. Anti-abuse: cooldown enforcement
3. Admin analytics: referral conversion rates, top referrers, revenue attribution
4. Admin API: List/detail/cancel individual referrals
5. Implement refund clawback (cancel referral if payment refunded within 30 days)

### Phase 4 — Double-sided rewards (future)

1. Enable `referee_bonus_credits` in referral config
2. Apply referee bonus at first subscription
3. Welcome notification for referee with bonus info

---

## 13. Cross-repo impact

| Repo | Impact | Status |
|---|---|---|
| **vianda-app** (B2C) | Deep link handling (`vianda.app/r/{CODE}`), referral tab (code sharing, activity list, stats), signup pass-through. Needs: `POST /referrals/assign-code` + `GET /referrals/assigned-code` for device-based code persistence (Phase 2.5). | Plan ready: `vianda-app/docs/plans/referral_system.md` |
| **vianda-platform** (B2B) | Referral config admin page with market name display. Needs: `GET /admin/referral-config/enriched` with `market_name` and `country_code` (Phase 2.5). | Plan ready: `vianda-platform/docs/plans/REFERRAL_CONFIG_ADMIN_PLAN.md` |
| **vianda-home** (marketing) | Referral landing page at `/r/{code}`. Redirect to app store / registration with code pre-filled. Must serve AASA + assetlinks for universal links. | Not started |
| **infra-kitchen-gcp** | Cron job for referral rewards + expiration. Universal link config (AASA, assetlinks) on `vianda.app` domain. | Not started |

---

## 14. Best practices applied

| Practice | Source | How applied |
|---|---|---|
| **Static referral code** | Dropbox, Uber, Revolut | One permanent code per user, not per-share links |
| **Reward on payment, not signup** | Industry standard | Prevents fake-account gaming; only real paying customers count |
| **Proportional rewards** | Airbnb, fintech apps | Higher plan price = more credits, aligns referrer incentive with revenue |
| **Monthly reward caps** | Uber, DoorDash | Prevents abuse from power-referrers or bot farms |
| **Refund clawback** | Stripe referral programs | If payment is reversed, so is the reward |
| **Qualification window** | Standard SaaS | Referrals expire after 90 days if referee doesn't convert |
| **Denormalized audit fields** | Internal convention | `bonus_rate_applied`, `bonus_plan_price` frozen at reward time for accurate audit |
| **Reuse existing credit pipeline** | Internal principle | Discretionary credits + client transactions, no parallel system |
