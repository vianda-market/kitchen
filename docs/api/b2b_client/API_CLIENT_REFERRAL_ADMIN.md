# Referral Program Administration — B2B Integration Guide

**Audience**: vianda-platform (B2B dashboard)
**Status**: Ready for implementation
**Backend**: Fully implemented — all endpoints live

---

## Overview

Internal admins can configure the referral program per market (bonus rates, caps, enable/disable) and monitor referral metrics. The B2B dashboard needs a referral config management section and optional referral activity views.

---

## 1. Referral Configuration Management

### List All Configs

`GET /api/v1/admin/referral-config`

**Auth**: Employee (Internal)

**Response** `200`: Array of configs, one per market.
```json
[
  {
    "referral_config_id": "uuid",
    "market_id": "uuid",
    "is_enabled": true,
    "referrer_bonus_rate": 15,
    "referrer_bonus_cap": null,
    "referrer_monthly_cap": 5,
    "min_plan_price_to_qualify": 0,
    "cooldown_days": 0,
    "held_reward_expiry_hours": 48,
    "pending_expiry_days": 90,
    "is_archived": false,
    "status": "active",
    "created_date": "2026-04-08T00:00:00Z",
    "modified_date": "2026-04-08T00:00:00Z"
  }
]
```

### List All Configs (Enriched)

`GET /api/v1/admin/referral-config/enriched`

**Auth**: Employee (Internal)

**Use this endpoint for the admin table view** — includes `market_name` and `country_code` via JOIN.

**Response** `200`:
```json
[
  {
    "referral_config_id": "uuid",
    "market_id": "uuid",
    "market_name": "Argentina",
    "country_code": "AR",
    "is_enabled": true,
    "referrer_bonus_rate": 15,
    "referrer_bonus_cap": null,
    "referrer_monthly_cap": 5,
    "min_plan_price_to_qualify": 0,
    "cooldown_days": 0,
    "held_reward_expiry_hours": 48,
    "pending_expiry_days": 90,
    "is_archived": false,
    "status": "active",
    "created_date": "2026-04-08T00:00:00Z",
    "modified_date": "2026-04-08T00:00:00Z"
  }
]
```

### Get Config by Market

`GET /api/v1/admin/referral-config/{market_id}`

**Auth**: Employee (Internal)

Returns a single config. `404` if no config exists for that market.

### Update Config

`PUT /api/v1/admin/referral-config/{market_id}`

**Auth**: Employee (Internal)

**Request body** — all fields optional (partial update):
```json
{
  "is_enabled": true,
  "referrer_bonus_rate": 20,
  "referrer_bonus_cap": 500,
  "referrer_monthly_cap": 10,
  "min_plan_price_to_qualify": 1000,
  "cooldown_days": 7,
  "held_reward_expiry_hours": 72,
  "pending_expiry_days": 60
}
```

**Field reference**:

| Field | Type | Description |
|---|---|---|
| `is_enabled` | bool | Master switch for the referral program in this market |
| `referrer_bonus_rate` | int (1-100) | Percentage of referee's plan price awarded as credits |
| `referrer_bonus_cap` | decimal or null | Max credit value per single referral. Null = no cap |
| `referrer_monthly_cap` | int or null | Max referral rewards per referrer per calendar month. Null = unlimited |
| `min_plan_price_to_qualify` | decimal | Minimum plan price for a referral to qualify (blocks gaming with cheap plans) |
| `cooldown_days` | int | Days after a reward before the same referrer can earn another |
| `held_reward_expiry_hours` | int | How long to hold a reward if referrer lacks active subscription |
| `pending_expiry_days` | int | Days after signup before a pending referral expires (referee never subscribed) |

---

## 2. Run Referral Cron (Manual Trigger)

`POST /api/v1/admin/referral-config/run-cron`

**Auth**: Employee (Internal)

Manually triggers the referral cron job that:
- Retries held rewards (referrers who now have active subscriptions)
- Expires stale pending referrals past their market's expiry window

**Response** `200`:
```json
{
  "cron_job": "referral_rewards",
  "success": true,
  "held_retried": 3,
  "pending_expired": 12,
  "errors": []
}
```

---

## 3. Referral Metrics (from existing data)

There are no dedicated admin referral listing endpoints yet (Phase 3). For now, metrics can be derived from the referral config and the database directly. Future endpoints planned:

| Planned endpoint | Description |
|---|---|
| `GET /admin/referrals` | List all referrals with filters (market, status, date range) |
| `GET /admin/referrals/{id}` | Referral detail |
| `PUT /admin/referrals/{id}/cancel` | Cancel a referral (fraud/abuse) |
| `GET /admin/referral-analytics` | Conversion rates, top referrers, revenue attribution |

---

## 4. UI Screens Summary

| Screen | Endpoint | Key elements |
|---|---|---|
| **Referral Config** | `GET /admin/referral-config` | Table: one row per market, showing bonus rate, caps, enabled status |
| **Edit Config** | `PUT /admin/referral-config/{market_id}` | Form with all configurable fields |
| **Manual Cron** | `POST /admin/referral-config/run-cron` | Button + results display |

---

## 5. Enum Reference

The `referral_status` enum is available via `GET /api/v1/enums/referral_status` with localized labels (en/es/pt).

| Value | EN | ES | PT |
|---|---|---|---|
| `pending` | Pending | Pendiente | Pendente |
| `qualified` | Qualified | Calificado | Qualificado |
| `rewarded` | Rewarded | Recompensado | Recompensado |
| `expired` | Expired | Expirado | Expirado |
| `cancelled` | Cancelled | Cancelado | Cancelado |
