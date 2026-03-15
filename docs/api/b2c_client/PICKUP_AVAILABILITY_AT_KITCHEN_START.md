# Pickup Availability: "Available at 11:30" vs "Ready for Pickup"

**Audience:** B2C app developers  
**Purpose:** How to show users when their reserved plate is available for pickup, plus charging/refund mechanics

---

## Overview

Plates are **promoted to live** at **kitchen start** (e.g. 11:30 AM local, per market). Until then, the reservation exists but the plate does not appear in the pending-pickup flow. The B2C client should distinguish:

1. **Reserved, not yet available** – "Available for pickup at 11:30 AM"
2. **Ready for pickup** – User can open camera, scan QR, and pick up

---

## Charging and Refund Mechanics

| When | What happens |
|------|--------------|
| **Reservation** | Credits are **validated only** (user must have enough). No deduction yet. |
| **Kitchen start (11:30)** | Credits are **deducted** from subscription balance. Client transaction created. Order is locked. |
| **Cancel before lock** | User can cancel until 1 hour before kitchen day. No charge was made, so nothing to refund. |
| **Cancel after lock** | Not allowed via normal cancel flow. If user no-shows, credits are **forfeited**; no refund. Restaurant keeps credited amount (no-show discount applies). |

**UI guidance:** Before 11:30, show "Available at 11:30 AM" and that cancellation is allowed until 1 hour before. After 11:30, show "Ready for pickup" and that credits have been charged (order is locked).

---

## Cancel Cutoff vs Kitchen Start

| Time (local) | User can… | Credits |
|--------------|-----------|---------|
| Until 10:30 | Cancel or edit reservation | Not charged yet |
| 10:30–11:30 | No edits (locked window) | Not charged yet |
| 11:30 | Order promoted; charged | Deducted |
| After 11:30 | Pick up (no cancel/refund) | Forfeited if no-show |

---

## Timeline (per market, local time)

| Time | State | B2C display |
|------|-------|-------------|
| After reservation, before 11:30 | Reserved | "Available for pickup at 11:30 AM" |
| 11:30 onwards | Ready | "Ready for pickup" / show QR scan |
| After scan | Arrived | Show confirmation + plates to restaurant |

---

## API usage

### 1. Plate selections for today

**Endpoint:** `GET /api/v1/plate-selections/`

Filter items where:
- `pickup_date` = today (in user's market timezone)
- `kitchen_day` = today's kitchen day

For each such selection:
- If `plate_pickup_id` is **null** → not yet promoted → show "Available for pickup at 11:30 AM" (or market-specific `business_hours.open`)
- If `plate_pickup_id` is **present** → promoted → show "Ready for pickup" and enable QR scan

### 2. Pending pickup

**Endpoint:** `GET /api/v1/plate-pickup/pending`

Returns only **live** (promoted) plates. Before 11:30, this may be empty for today's reservations. Use `GET /api/v1/plate-selections/` to show today's reservations with availability state.

### 3. QR scan

**Endpoint:** `POST /api/v1/plate-pickup/scan-qr`

On success, the response includes:
- `confirmation_code` – show to restaurant staff
- `plates` – `[{plate_name, quantity, plate_pickup_id}]` – what the user can pickup, for the "show to restaurant" screen

### 4. Pickup outside intended time range

Once the plate is promoted (kitchen started), the user can pick up **any time** that day, even outside the chosen pickup window (e.g. 11:30–13:30). Availability is gated only by kitchen start, not by time range.

---

## UI flow

1. **My reservations / Today tab**
   - List today's plate selections from `GET /plate-selections/`
   - For each: show `plate_pickup_id ? "Ready for pickup" : "Available at 11:30 AM"` (or market open time)

2. **Ready for pickup**
   - Show "Scan QR at restaurant" button
   - Open camera, call `POST /plate-pickup/scan-qr` with payload from QR

3. **After scan**
   - Show confirmation code and `plates` list
   - User shows this screen to restaurant staff
   - Restaurant marks complete via their flow

---

## Kitchen start time by market

Default: **11:30 AM local** (from `MarketConfiguration.business_hours[day].open`).  
The app can use a fixed "11:30" or fetch market config if available. Future: backend may expose `kitchen_start_time` per market.
