# Institution no_show_discount

## Overview

`no_show_discount` is configured at the **institution** level, not per plate. For Supplier institutions (restaurants), every plate served by that institution uses the institution’s negotiated no-show discount rate. This allows a single rate per institution instead of per plate.

## Where to Edit

- **Endpoint:** `PUT /api/v1/institutions/{id}`
- **Request body:** `{"no_show_discount": 0}` to `100` (percentage)
- **Create:** `POST /api/v1/institutions/` — when `institution_type` is `Supplier`, `no_show_discount` is **required** (0–100)

## Who Can Edit

| User Role                         | Can edit no_show_discount? |
|-----------------------------------|----------------------------|
| Employee Manager                  | Yes (no_show_discount only)|
| Employee Global Manager          | Yes (no_show_discount only)|
| Employee Admin                   | Yes (all fields)           |
| Employee Super Admin             | Yes (all fields)           |
| Supplier Admin / Manager         | **No** (403)              |
| Customer                         | No                        |

Only Employees with Manager, Global Manager, Admin, or Super Admin can edit `no_show_discount`. Vianda negotiates rates with institutions; Suppliers manage plates and operations but cannot change the discount.

## Institution Type Scoping

**Only Supplier institutions carry `no_show_discount`.** Employee, Customer, and Employer institutions do not carry this value; it is always `null` (not applicable) for them.

| `institution_type` | Carries `no_show_discount`? |
|-------------------|---------------------------|
| Supplier          | Yes (required 0–100)      |
| Employee          | No (always null)          |
| Customer          | No (always null)          |
| Employer          | No (always null)          |

When creating or updating a non-Supplier institution, the backend ignores `no_show_discount` if sent in the payload and stores `NULL` regardless.

## Nullability

- **Supplier institutions:** `no_show_discount` is **required** (NOT NULL). Must be 0–100.
- **Employee / Customer / Employer institutions:** `no_show_discount` is always NULL (not applicable; field is ignored if sent).

## Scope

The value applies to **all plates** of restaurants belonging to that institution. The promotion and billing logic resolve it via `restaurant.institution_id -> institution.no_show_discount`.
