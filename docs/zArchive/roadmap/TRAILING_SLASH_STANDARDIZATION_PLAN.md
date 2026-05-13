# Trailing Slash Standardization Plan

**Created**: 2026-03-15  
**Status**: Implemented  
**Goal**: Eliminate 307 redirects on POST/GET by disabling `redirect_slashes` and standardizing all API routes to **no trailing slash** (industry standard for REST).

---

## Problem Summary

- **Symptom**: `POST /api/v1/employers` returns `307 Temporary Redirect` to `/api/v1/employers/`
- **Root cause**: Routes registered with trailing slash; clients calling without slash get redirected
- **Impact**: Mobile HTTP clients often don't follow 307 on POST (risk of sending body twice) → network errors

## Approach: Backend-Only, Single Pattern

1. **Disable redirect_slashes** at the FastAPI app level — one-line change
2. **Register all routes in canonical form without trailing slash** — full API audit
3. **Convention**: `/api/v1/employers`, `/api/v1/employers/enriched`, never `/api/v1/employers/`

Client (mobile) updates are handled in a separate repo; this plan is backend-only.

---

## Phase 1: Disable redirect_slashes

### Change

**File**: [application.py](application.py)

```python
# Before
app = FastAPI(title="Kitchen API", lifespan=lifespan, openapi_tags=OPENAPI_TAGS)

# After
app = FastAPI(title="Kitchen API", lifespan=lifespan, openapi_tags=OPENAPI_TAGS, redirect_slashes=False)
```

**Note**: FastAPI supports `redirect_slashes` (default `True`). Setting to `False` prevents automatic 307 redirects for path mismatches. Routes must then be registered in the exact form we want (no trailing slash).

### Infrastructure endpoint

**File**: [application.py](application.py)

- Change `@app.get("/api/", ...)` → `@app.get("/api", ...)`
- Change `RedirectResponse(url="/api/v1/", ...)` → `RedirectResponse(url="/api/v1", ...)`

---

## Phase 2: Full API Audit – Route Path Changes

All routes below must change from trailing-slash to no-trailing-slash form.

### Change rules

| From | To |
|------|-----|
| `"/"` (collection root) | `""` |
| `"/enriched/"` | `"/enriched"` |
| `"/search/"` | `"/search"` |
| `"/requests/"` | `"/requests"` |
| `"/pending-requests/"` | `"/pending-requests"` |
| `"/institution-types/assignable"` | (already no trailing slash) |
| `"/roles/assignable"` | (already no trailing slash) |

### Files and routes to update

#### 1. [app/routes/employer.py](app/routes/employer.py)
| Line | From | To |
|------|------|-----|
| 189 | `"/enriched/"` | `"/enriched"` |
| 215 | `"/"` | `""` |
| 226 | `"/"` | `""` |

#### 2. [app/routes/address.py](app/routes/address.py)
| From | To |
|------|-----|
| `"/"` (GET list) | `""` |
| `"/"` (POST create) | `""` |
| `"/enriched/"` | `"/enriched"` |
| `"/search/"` | `"/search"` |

#### 3. [app/routes/user.py](app/routes/user.py)
| From | To |
|------|-----|
| `"/"` (GET list) | `""` |
| `"/"` (POST create) | `""` |
| `"/search/"` | `"/search"` |
| `"/enriched/"` | `"/enriched"` |

#### 4. [app/routes/vianda_selection.py](app/routes/vianda_selection.py)
| From | To |
|------|-----|
| `"/"` (POST create) | `""` |
| `"/"` (GET list) | `""` |

#### 5. [app/routes/vianda_review.py](app/routes/vianda_review.py)
| From | To |
|------|-----|
| `"/"` (POST) | `""` |

#### 6. [app/routes/favorite.py](app/routes/favorite.py)
| From | To |
|------|-----|
| `"/"` (POST) | `""` |

#### 7. [app/routes/qr_code.py](app/routes/qr_code.py)
| From | To |
|------|-----|
| `"/"` (POST, GET) | `""` |
| `"/enriched/"` | `"/enriched"` |

#### 8. [app/routes/restaurant.py](app/routes/restaurant.py)
| From | To |
|------|-----|
| `"/"` (POST, GET) | `""` |
| `"/search/"` | `"/search"` |
| `"/enriched/"` | `"/enriched"` |

#### 9. [app/routes/restaurant_balance.py](app/routes/restaurant_balance.py)
| From | To |
|------|-----|
| `"/"` | `""` |
| `"/enriched/"` | `"/enriched"` |

#### 10. [app/routes/restaurant_transaction.py](app/routes/restaurant_transaction.py)
| From | To |
|------|-----|
| `"/"` | `""` |
| `"/enriched/"` | `"/enriched"` |

#### 11. [app/routes/restaurant_holidays.py](app/routes/restaurant_holidays.py)
| From | To |
|------|-----|
| `"/"` (GET, POST) | `""` |
| `"/enriched/"` | `"/enriched"` |

#### 12. [app/routes/vianda_kitchen_days.py](app/routes/vianda_kitchen_days.py)
| From | To |
|------|-----|
| `"/"` (GET, POST) | `""` |
| `"/enriched/"` | `"/enriched"` |

#### 13. [app/routes/national_holidays.py](app/routes/national_holidays.py)
| From | To |
|------|-----|
| `"/"` (GET, POST) | `""` |

#### 14. [app/routes/countries.py](app/routes/countries.py)
| From | To |
|------|-----|
| `"/"` | `""` |

#### 15. [app/routes/currencies.py](app/routes/currencies.py)
| From | To |
|------|-----|
| `"/"` | `""` |

#### 16. [app/routes/cities.py](app/routes/cities.py)
| From | To |
|------|-----|
| `"/"` | `""` |

#### 17. [app/routes/provinces.py](app/routes/provinces.py)
| From | To |
|------|-----|
| `"/"` | `""` |

#### 18. [app/routes/cuisines.py](app/routes/cuisines.py)
| From | To |
|------|-----|
| `"/"` | `""` |

#### 19. [app/routes/enums.py](app/routes/enums.py)
| From | To |
|------|-----|
| `"/"` | `""` |

#### 20. [app/routes/institution_entity.py](app/routes/institution_entity.py)
| From | To |
|------|-----|
| `"/enriched/"` | `"/enriched"` |

#### 21. [app/routes/admin/markets.py](app/routes/admin/markets.py)
| From | To |
|------|-----|
| `"/"` (GET, POST) | `""` |
| `"/enriched/"` | `"/enriched"` |

#### 22. [app/routes/admin/discretionary.py](app/routes/admin/discretionary.py)
| From | To |
|------|-----|
| `"/requests/"` (POST, GET) | `"/requests"` |
| `"/pending-requests/"` | `"/pending-requests"` |

#### 23. [app/routes/admin/archival_config.py](app/routes/admin/archival_config.py)
| From | To |
|------|-----|
| `"/"` (GET, POST) | `""` |

#### 24. [app/routes/super_admin/discretionary.py](app/routes/super_admin/discretionary.py)
| From | To |
|------|-----|
| `"/pending-requests/"` | `"/pending-requests"` |
| `"/requests/"` | `"/requests"` |

#### 25. [app/routes/billing/client_bill.py](app/routes/billing/client_bill.py)
| From | To |
|------|-----|
| `"/"` | `""` |

#### 26. [app/routes/billing/institution_bill.py](app/routes/billing/institution_bill.py)
| From | To |
|------|-----|
| `"/"` | `""` |
| `"/enriched/"` | `"/enriched"` |

#### 27. [app/routes/customer/payment_methods.py](app/routes/customer/payment_methods.py)
| From | To |
|------|-----|
| `"/"` | `""` |

#### 28. [app/services/route_factory.py](app/services/route_factory.py)

**Remove** the `""` aliases (they become the canonical form). **Change** `"/"` to `""` for:
- Generic CRUD: `get_all_entities`, `create_entity` — change `"/"` to `""`, **remove** `get_all_entities_no_trailing_slash` and `create_entity_no_trailing_slash` (they become the primary)
- Products: `"/"` POST, `"/enriched/"` → `""`, `"/enriched"`
- Plans: `"/"` GET/POST, `"/enriched/"` → `""`, `"/enriched"`
- Credit currencies: `"/"` GET/POST → `""`
- Subscriptions: `"/"` GET, `"/enriched/"` → `""`, `"/enriched"`
- Institutions: `"/"` GET/POST — change to `""`, **remove** `get_all_institutions_no_trailing` alias
- Payment methods: `"/"` POST — change to `""`, **remove** `create_payment_method_no_trailing_slash` alias
- Viandas: `"/"` GET, `"/enriched/"` → `""`, `"/enriched"`

#### 29. [app/services/versioned_route_factory.py](app/services/versioned_route_factory.py)
| From | To |
|------|-----|
| `"/"` (GET, POST) | `""` |

#### 30. [app/dependencies/database.py](app/dependencies/database.py)
- Check `@router.post("/")` — if this is a test/dependency router, update to `""`

#### 31. [app/core/versioning.py](app/core/versioning.py)
- Example in docstring: `@router.get("/")` → `@router.get("")` (doc only)

---

## Phase 3: Documentation updates

Update API docs to reflect canonical form (no trailing slash):

- [docs/api/b2c_client/EMPLOYER_MANAGEMENT_B2C.md](docs/api/b2c_client/EMPLOYER_MANAGEMENT_B2C.md)
- [docs/api/b2b_client/API_CLIENT_EMPLOYER_ASSIGNMENT.md](docs/api/b2b_client/API_CLIENT_EMPLOYER_ASSIGNMENT.md)
- Postman collections (if URLs hardcode trailing slashes): `docs/postman/collections/*.json`
- [docs/CLAUDE.md](docs/CLAUDE.md) — add convention: "REST collection endpoints use no trailing slash (e.g. `/api/v1/employers`, not `/api/v1/employers/`)"

---

## Phase 4: Postman collections

Postman collections reference `/api/v1/employers/` and similar. Update to canonical form:

- [docs/postman/collections/010 Permissions Testing - Employee-Only Access.postman_collection.json](docs/postman/collections/010%20Permissions%20Testing%20-%20Employee-Only%20Access.postman_collection.json)
- [docs/postman/collections/000 E2E Vianda Selection.postman_collection.json](docs/postman/collections/000%20E2E%20Plate%20Selection.postman_collection.json)
- Any other collections under `docs/postman/collections/`

---

## Verification

1. Run `GET /api/v1/employers` and `POST /api/v1/employers` — expect 200/201, no 307
2. Run `GET /api/v1/employers/` — expect 404 (no redirect)
3. Run Postman collections — all requests should succeed with updated URLs
4. OpenAPI at `/docs` — paths should show without trailing slash

---

## Summary

| Phase | Scope | Files |
|-------|-------|-------|
| 1 | `redirect_slashes=False` + `/api` redirect | application.py |
| 2 | Route path changes | ~31 files (routes, route_factory, versioned_route_factory) |
| 3 | API docs | docs/api/** |
| 4 | Postman | docs/postman/collections/ |

**Standard**: All resource endpoints use no trailing slash. One app-level change + systematic route audit.
