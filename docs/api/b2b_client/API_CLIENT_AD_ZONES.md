# Ad Zone Management (B2B Admin)

Backend API contract for the geographic ad zone management UI in the B2B admin portal. Internal employees use this to create, monitor, and control the flywheel engine that drives market expansion.

**Full design:** `docs/plans/GOOGLE_META_ADS_INTEGRATION_V2.md` sections 14-16.
**Restaurant lead review:** `docs/plans/RESTAURANT_VETTING_SYSTEM.md` section 11.

---

## 1. Zone CRUD Endpoints

All endpoints require Internal employee auth (`get_employee_user`).

### Create Zone

```
POST /api/v1/admin/ad-zones
Authorization: Bearer {token}
```

```json
{
  "name": "BA-Palermo",
  "country_code": "AR",
  "city_name": "Buenos Aires",
  "neighborhood": "Palermo",
  "latitude": -34.5880,
  "longitude": -58.4300,
  "radius_km": 2.0,
  "flywheel_state": "supply_acquisition",
  "daily_budget_cents": 5000,
  "budget_allocation": {
    "b2c_subscriber": 0,
    "b2b_employer": 0,
    "b2b_restaurant": 100
  }
}
```

**Response (201):** Full zone object (see below).

`flywheel_state` can be set on creation for cold start (no prior data needed). Default is `monitoring`.

### List Zones

```
GET /api/v1/admin/ad-zones
GET /api/v1/admin/ad-zones?country_code=AR
GET /api/v1/admin/ad-zones?flywheel_state=supply_acquisition
```

Returns array of zone objects. Supports `country_code` and `flywheel_state` filters.

### Get Zone

```
GET /api/v1/admin/ad-zones/{zone_id}
```

### Update Zone

```
PATCH /api/v1/admin/ad-zones/{zone_id}
```

```json
{
  "name": "BA-Palermo-Extended",
  "radius_km": 2.5,
  "daily_budget_cents": 7500,
  "budget_allocation": {"b2c_subscriber": 60, "b2b_employer": 10, "b2b_restaurant": 30}
}
```

If `flywheel_state` is included in PATCH, the backend routes it to the state transition logic automatically.

### Delete Zone

```
DELETE /api/v1/admin/ad-zones/{zone_id}
```

Returns 204.

---

## 2. Flywheel State Transitions

```
POST /api/v1/admin/ad-zones/{zone_id}/transition?new_state=demand_activation
```

Valid states: `monitoring`, `supply_acquisition`, `demand_activation`, `growth`, `mature`, `paused`.

Operator can force any transition at any time (no automated threshold gates). The system logs who changed the state and when.

### State Machine

```
monitoring -> supply_acquisition -> demand_activation -> growth -> mature
                                                                    |
Any state can transition to: paused (and back to any active state)
```

### State Descriptions

| State | Meaning | Typical Budget |
|-------|---------|---------------|
| `monitoring` | Tracking notify-me leads, no ads | $0 |
| `supply_acquisition` | Running restaurant acquisition ads | $50/day |
| `demand_activation` | Restaurants onboarded, running B2C + restaurant ads | $150/day |
| `growth` | All 3 strategies active | $250/day |
| `mature` | Gemini advisor manages budget dynamically | Variable |
| `paused` | All ads paused for this zone | $0 |

---

## 3. Zone Metrics

### Refresh All Zones (Cron)

```
POST /api/v1/admin/ad-zones/sync-metrics
```

Refreshes `notify_me_lead_count`, `active_restaurant_count`, `active_subscriber_count` for all non-paused zones. Designed to be called daily by Cloud Scheduler.

### Refresh Single Zone

```
POST /api/v1/admin/ad-zones/{zone_id}/sync-metrics
```

Returns updated counts:

```json
{
  "zone_id": "uuid",
  "zone_name": "BA-Palermo",
  "notify_me_lead_count": 42,
  "active_restaurant_count": 7,
  "active_subscriber_count": 156
}
```

---

## 4. Overlap Detection

```
GET /api/v1/admin/ad-zones/{zone_id}/overlaps
```

Returns zones whose radius circles overlap with this zone:

```json
{
  "zone_id": "uuid",
  "overlaps": [
    {
      "zone_id": "uuid",
      "zone_name": "BA-Recoleta",
      "distance_km": 3.4,
      "combined_radii_km": 4.0,
      "overlap_km": 0.6
    }
  ]
}
```

Overlaps are warnings, not errors. The operator decides whether to adjust radii, merge zones, or accept the overlap.

---

## 5. Audience Export

```
GET /api/v1/admin/ad-zones/{zone_id}/audience
```

Returns SHA256-hashed emails of notify-me leads matching this zone's city/country. Ready for Custom Audience upload to Meta or Google.

```json
{
  "zone_id": "uuid",
  "zone_name": "BA-Palermo",
  "audience_size": 42,
  "hashed_emails": [
    {"hashed_email": "a1b2c3..."},
    {"hashed_email": "d4e5f6..."}
  ],
  "usage_guidance": {
    "meta_custom_audience": "Upload hashed_email values to Meta Custom Audience",
    "google_customer_match": "Upload hashed_email values to Google Customer Match",
    "lookalike_viable": false,
    "seed_viable": false
  }
}
```

`lookalike_viable` is true when audience >= 300. `seed_viable` when >= 100.

---

## 6. Zone Response Schema

All GET/POST/PATCH endpoints return this shape:

```json
{
  "id": "uuid",
  "name": "BA-Palermo",
  "country_code": "AR",
  "city_name": "Buenos Aires",
  "neighborhood": "Palermo",
  "latitude": -34.5880,
  "longitude": -58.4300,
  "radius_km": 2.0,
  "flywheel_state": "supply_acquisition",
  "state_changed_at": "2026-04-09T12:00:00Z",
  "notify_me_lead_count": 42,
  "active_restaurant_count": 7,
  "active_subscriber_count": 0,
  "estimated_mau": null,
  "budget_allocation": {"b2c_subscriber": 0, "b2b_employer": 0, "b2b_restaurant": 100},
  "daily_budget_cents": 5000,
  "created_by": "operator",
  "created_date": "2026-04-09T12:00:00Z"
}
```

---

## 7. UI Recommendations

### Zone List View

- Table with columns: name, country, city, state (color-coded badge), restaurants, subscribers, leads, budget
- Filters: country dropdown, state dropdown
- Sort: by state priority (supply_acquisition first) or by name

### Zone Detail / Map View

- Map centered on zone lat/lon with radius circle overlay
- Metrics cards: restaurants, subscribers, notify-me leads, estimated MAU
- State transition buttons (dropdown with all valid states)
- Budget allocation pie chart or slider
- Overlap warnings (if any)

### Zone Creation

- Map click to set lat/lon (or manual coordinate entry)
- Radius slider (1.5km - 10km, default 2km)
- Country + city + neighborhood fields
- Initial state selector (default: monitoring for data-driven, supply_acquisition for cold start)

---

## 8. Meta Pixel on B2B Portal

Install Meta Pixel JS on the B2B portal for tracking employer onboarding events:

| Event | When | Parameters |
|-------|------|-----------|
| `CompleteRegistration` | Employer completes benefits program setup | `registration_type: 'employer_program'` |

This allows Meta to attribute employer onboarding back to B2B employer acquisition campaigns. Pixel ID is the same as the marketing site.
