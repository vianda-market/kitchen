# Enriched Endpoints Guide

## Problem

When UI needs to display related entity names (e.g., `role_name`, `institution_name`) but the base endpoint only returns foreign key IDs, the UI would need N+1 queries or multiple round trips.

## Solution

Create dedicated `/enriched` endpoints that use SQL JOINs to return denormalized data in a single query.

## Implementation Pattern

```python
# 1. Enriched response schema — app/schemas/consolidated_schemas.py
class UserEnrichedResponseSchema(BaseModel):
    user_id: UUID
    institution_id: UUID
    institution_name: str   # ← from JOIN with institution_info
    role_id: UUID
    role_name: str          # ← from JOIN with role_info
    role_type: str
    username: str
    email: str

# 2. Service with JOIN query — app/services/entity_service.py
def get_enriched_users(db, *, scope=None, include_archived=False):
    query = """
        SELECT
            u.user_id, u.institution_id,
            i.name as institution_name,
            u.role_id, r.name as role_name, r.role_type,
            u.username, u.email
        FROM core.user_info u
        JOIN core.role_info r ON u.role_id = r.role_id
        JOIN core.institution_info i ON u.institution_id = i.institution_id
        WHERE u.is_archived = FALSE
        ORDER BY u.created_date DESC
    """
    results = db_read(query, None, connection=db)
    return [UserEnrichedResponseSchema(**row) for row in results]

# 3. Route — app/routes/user.py
@router.get("/enriched", response_model=List[UserEnrichedResponseSchema])
def list_enriched_users(current_user=Depends(get_current_user), db=Depends(get_db)):
    scope = get_institution_scope(current_user)
    return get_enriched_users(db, scope=scope)

@router.get("/enriched/{user_id}", response_model=UserEnrichedResponseSchema)
def get_enriched_user(user_id: UUID, current_user=Depends(get_current_user), db=Depends(get_db)):
    result = get_enriched_user_by_id(user_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return result
```

## Naming Convention

- Base: `/users`, `/users/{id}`
- Enriched: `/users/enriched`, `/users/enriched/{id}`
- Schemas: `UserResponseSchema` vs `UserEnrichedResponseSchema`

## When to Use

- Use enriched when UI frequently needs related entity names alongside IDs
- Use base when UI only needs the entity itself or fetches related data separately

---

## Field Naming Rule: Only Rename on Actual Collision

**CRITICAL:** Only rename or alias a field when there is an actual or expected column name collision between joined tables. If there is no collision, use the original column name.

### When to Rename

✅ **Rename only when collision exists:**
```python
# plan.status collides with another joined table that also has status
"pl.status as plan_status"

# Both restaurant_info and institution_info have a 'name' column
"r.name as restaurant_name",
"i.name as institution_name"
```

### When NOT to Rename

❌ **Do not rename when no collision exists:**
```python
# ❌ WRONG — no collision, unnecessary prefix
"pl.price as plan_price"
"u.email as user_email"
"u.username as user_username"

# ✅ CORRECT — use original name
"pl.price"
"u.email"
"u.username"
```

### Warning Comment for Ambiguous Cases

If you rename without a clear collision, add a comment:
```python
"pl.name as plan_name",  # ⚠️ Descriptive alias — no collision, but clarifies source
```

### Examples

```python
# ✅ Good
select_fields = [
    "pl.price",              # no collision
    "pl.credit",             # no collision
    "pl.status as plan_status",   # collision — another table has 'status'
    "r.name as restaurant_name",  # collision — institution_info also has 'name'
]

# ❌ Bad
select_fields = [
    "pl.price as plan_price",    # no collision, rename is unnecessary
    "pl.credit as plan_credit",  # no collision, rename is unnecessary
]
```

### Benefits of Minimal Renaming
- Field names match DB column names — easier to trace
- Less cognitive overhead
- Prefixes can always be added later if a collision is introduced
