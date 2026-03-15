# Institution Scoping & RBAC Audit

**Date:** 2025-11-11  
**Author:** GPT-5 Codex  
**Goal:** Catalogue FastAPI endpoints that expose institution-scoped resources and document their current behaviour. This is Task 1 of the “Institution Scoping & RBAC Enforcement” roadmap item.

## Legend
- **Scope** column describes who can access the data today.
  - `Global` → returns all rows regardless of institution.
  - `Filtered (manual)` → optional filters exist, but enforcement is caller-driven.
  - `Scoped` → server-side restriction already in place (none observed).
- **Notes** call out where additional backend work is required.

## Users (`app/routes/user.py`)
| Endpoint | Scope | Notes |
| --- | --- | --- |
| `GET /users/` | Global | Uses `user_service.get_all` → no institution filter. |
| `GET /users/lookup` | Global | Lookup by username/email; no institution validation. |
| `GET /users/{user_id}` | Global | Returns any user by ID. |
| `POST /users/` | Global | `process_admin_user_creation` accepts institution IDs in payload; no RBAC gate. |
| `PUT /users/{user_id}` | Global | No institution ownership check. |
| `DELETE /users/{user_id}` | Global | Soft delete without institution validation. |

## Institution Entities (`create_institution_entity_routes`, Route Factory)
| Endpoint | Scope | Notes |
| --- | --- | --- |
| `GET /institution-entities/` | Global | Generic CRUD route → returns all entities. |
| `GET /institution-entities/{entity_id}` | Global | No institution check. |
| `POST /institution-entities/` | Global | Allows creating entity for any institution id. |
| `PUT/PATCH /institution-entities/{entity_id}` | Global | Updates unchecked. |
| `DELETE /institution-entities/{entity_id}` | Global | Soft delete without scoping. |

## Addresses (`app/routes/address.py`)
| Endpoint | Scope | Notes |
| --- | --- | --- |
| `GET /addresses/` | Global | Returns all addresses; includes non-institution types as well. |
| `GET /addresses/{address_id}` | Global | No scoping. |
| `POST /addresses/` | Global | Allows linking address to any institution/user. |
| `PUT /addresses/{address_id}` | Global | Updates allowed for any address. |
| `DELETE /addresses/{address_id}` | Global | Soft delete without scoping. |

## Restaurants (`app/routes/restaurant.py`)
| Endpoint | Scope | Notes |
| --- | --- | --- |
| `GET /restaurants/` | Global | Returns all restaurants via `restaurant_service.get_all`. |
| `GET /restaurants/{restaurant_id}` | Global | No institution check. |
| `POST /restaurants/` | Global | Caller provides `institution_id`/`institution_entity_id`; no validation. |
| `PUT /restaurants/{restaurant_id}` | Global | Updates any restaurant. |
| `DELETE /restaurants/{restaurant_id}` | Global | Soft delete any restaurant. |
| `POST /restaurants/{restaurant_id}/create-balance` | Global | Manual balance creation; no institution check. |

## Products (`create_product_routes`, Route Factory)
| Endpoint | Scope | Notes |
| --- | --- | --- |
| `GET /products/` | Global | Generic CRUD route → returns all products. |
| `GET /products/{product_id}` | Global | No scoping. |
| `POST /products/` | Global | Allows creating product for any institution. |
| `PUT/PATCH /products/{product_id}` | Global | Updates allowed without institution validation. |
| `DELETE /products/{product_id}` | Global | Soft delete without scoping. |
| `POST /products/{product_id}/image` | Global | Fetches by ID then updates; no institution check beyond existence. |

## Plates (`create_plate_routes`, Route Factory)
| Endpoint | Scope | Notes |
| --- | --- | --- |
| `GET /plates/` | Global | Returns all plates regardless of restaurant/institution. |
| `GET /plates/{plate_id}` | Global | No scoping. |
| `POST /plates/` | Global | Accepts `restaurant_id`/`product_id`; no institution enforcement. |
| `PUT/PATCH /plates/{plate_id}` | Global | Updates allowed for any plate. |
| `DELETE /plates/{plate_id}` | Global | Soft delete without scoping. |

## QR Codes (`app/routes/qr_code.py`)
| Endpoint | Scope | Notes |
| --- | --- | --- |
| `GET /qr-codes/` | Global | Uses `qr_code_service.get_all`; no institution filter. |
| `GET /qr-codes/{qr_code_id}` | Global | No scoping. |
| `POST /qr-codes/` | Global | Atomic creation for any `restaurant_id`. |
| `PUT /qr-codes/{qr_code_id}` | Global | Status/update for any code. |
| `DELETE /qr-codes/{qr_code_id}` | Global | Deletes code without institution check. |
| `GET /qr-codes/restaurant/{restaurant_id}` | Global | Returns QR by restaurant – caller can query any restaurant. |

## Related Supporting Endpoints (Manual Filters Only)
| Module | Endpoint | Current Behaviour |
| --- | --- | --- |
| `app/routes/institution_bank_account.py` | `GET /institution-bank-accounts/?institution_entity_id=...` | Optional query param filters by entity, but API returns all accounts if omitted. No role-based enforcement. |
| `app/routes/payment_methods/institution_payment_attempt.py` | Multiple `GET` endpoints filtered by `institution_entity_id`, but only when caller supplies param; otherwise global. |
| `app/services/entity_service.py` | Helper functions `get_pending_bills_by_institution`, etc. | Load all bills then filter in Python; no enforcement at SQL level. |

## Observations
1. **No endpoint currently performs server-side institution scoping** for non-employee roles. All “list/detail” operations fetch global datasets.
2. **Mutations rely on client-provided IDs** (institution, restaurant, etc.) without validating ownership.
3. Some modules provide optional filters (e.g., `institution_bank_account`), but they are advisory rather than enforced.
4. Employees (role_type `Employee`/`Super Admin`) legitimately need global access; implementation must respect this exception.

## Next Steps (Feeds Task 2+)
- Define shared helper(s) that accept `institution_id` from JWT and append `WHERE` clauses / validation.
- Triage endpoints requiring deeper refactors (e.g., `restaurant_service.get_all` should accept filters, or new service method).
- Update DTO/route layers to call scoped variants by default.
- Coordinate with Vianda Platform frontend so non-employee users pass institution context where needed (until backend fully enforces).

