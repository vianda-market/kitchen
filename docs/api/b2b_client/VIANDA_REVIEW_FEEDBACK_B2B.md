# Vianda Review Feedback — B2B Integration

**From:** kitchen backend
**To:** vianda-platform (B2B supplier dashboard)
**Date:** 2026-04-04

Customers can now leave text comments and a "would order again" flag when reviewing viandas. This data is intended for restaurant/supplier consumption via the B2B platform.

---

## What Changed

The `vianda_review_info` table now includes two optional fields:

| Field | Type | Description |
|-------|------|-------------|
| `would_order_again` | boolean (nullable) | Whether the customer would order this vianda again |
| `comment` | varchar(500) (nullable) | Free-text feedback from the customer |

These fields appear in the existing review response schemas (`ViandaReviewResponseSchema`).

---

## Where to Surface This

The B2B platform should build a **Customer Feedback** section accessible to Supplier users (Admin, Manager, Operator) where they can:

1. View reviews for their restaurant's viandas (scoped by institution)
2. See star rating, portion size rating, "would order again" flag, and comment text
3. Optionally aggregate/filter by vianda, date range, or rating

---

## API Endpoints

Reviews are currently created by customers via `POST /api/v1/vianda-reviews` (B2C only, Customer auth).

For the B2B dashboard to read reviews, a new supplier-scoped endpoint may be needed. Currently available:

- **`GET /api/v1/vianda-reviews/me`** — Customer-only (returns user's own reviews)
- **Vianda review aggregates** — Used internally via `get_vianda_review_aggregates()` in `app/services/vianda_review_service.py`

**Action needed:** If the B2B agent needs a supplier-scoped endpoint like `GET /api/v1/vianda-reviews/by-restaurant/{restaurant_id}`, request it from the kitchen backend team. The data and service layer exist; only a new route with institution scoping is needed.

---

## Moderation

No content moderation is applied. Comments are stored as raw text (trimmed, max 500 chars). If moderation becomes necessary, the backend can add a `needs_review` column later.

---

## Notes

- Comments are NOT surfaced in the B2C mobile app
- Reviews are immutable — one per pickup, cannot be edited after creation
- `would_order_again` and `comment` are both optional; older reviews will have `null` for both
