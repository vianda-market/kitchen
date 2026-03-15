# Employer Creation Auto-Assign Implementation Checklist

## Quick Reference: Implementation Steps

### Phase 1: Schema Updates ✅
- [ ] Add `assign_employer: bool = True` to `EmployerCreateSchema` in `app/schemas/consolidated_schemas.py`
- [ ] Add `assign_employer: Optional[bool] = Field(True, ...)` to `AddressCreateSchema` in `app/schemas/consolidated_schemas.py`
- [ ] Update schema docstrings to explain parameter behavior

### Phase 2: Service Layer Update ✅
- [ ] Update `create_employer_with_address()` in `app/services/entity_service.py`
  - [ ] Add `assign_to_user: bool = False` parameter
  - [ ] Add user assignment logic after employer creation
  - [ ] Ensure atomic transaction (all-or-nothing)

### Phase 3: Route Updates ✅
- [ ] Update `POST /employers/` in `app/routes/employer.py`
  - [ ] Extract `assign_employer` from request body
  - [ ] Check `role_type` - only Customers can use parameter
  - [ ] Pass `assign_to_user` to service method
- [ ] Update `POST /employers/{employer_id}/addresses` in `app/routes/employer.py`
  - [ ] Extract `assign_employer` from request body (default `True`)
  - [ ] Check `role_type` - only Customers can use parameter
  - [ ] Add user assignment logic after address creation
  - [ ] Ensure atomic transaction

### Phase 4: Transaction Safety ✅
- [ ] Verify database connection `autocommit` setting
- [ ] Test transaction rollback on failure scenarios
- [ ] Ensure all operations (create address, create employer, assign user) are atomic

### Phase 5: Testing ✅
- [ ] Unit tests for service layer
  - [ ] Customer creates employer with `assign_employer=true` → assigned
  - [ ] Customer creates employer with `assign_employer=false` → not assigned
  - [ ] Customer adds address with `assign_employer=true` → assigned
  - [ ] Customer adds address with `assign_employer=false` → not assigned
  - [ ] Employee creates employer → parameter ignored
  - [ ] Transaction rollback scenarios
- [ ] Integration tests (Postman collection)
  - [ ] Update `E2E Plate Selection.postman_collection.json`
  - [ ] Add employer workflow steps after "Update Customer Address"
  - [ ] Test GET employers → none found → POST employer → verify assignment
  - [ ] Test POST employer with `assign_employer=false` → verify no assignment

### Phase 6: Documentation ✅
- [ ] Update `docs/api/client/EMPLOYER_ASSIGNMENT_WORKFLOW.md`
  - [ ] Document `assign_employer` parameter behavior
  - [ ] Document defaults (True for both create employer and add address)
  - [ ] Document role-based behavior (only Customers)
  - [ ] Add UI recommendations section

---

## Implementation Order

1. **Schema Updates** (Phase 1) - Foundation for all changes
2. **Service Layer** (Phase 2) - Core business logic
3. **Route Updates** (Phase 3) - API endpoints
4. **Transaction Safety** (Phase 4) - Verify atomicity
5. **Testing** (Phase 5) - Validate implementation
6. **Documentation** (Phase 6) - Update docs

---

## Key Implementation Details

### Default Behavior
- **Create Employer**: `assign_employer = True` (checked by default)
- **Add Address**: `assign_employer = True` (checked by default)
- **Rationale**: Clients want least steps possible and are adjusting data for themselves

### Role-Based Logic
- **Customers**: `assign_employer` parameter is respected
- **Employees/Suppliers**: Parameter is ignored (always creates without assignment)

### Transaction Safety
- All operations must be atomic (create address, create employer, assign user)
- If any step fails, rollback everything
- Verify `autocommit=False` in database connection

### UI Requirements
- Always show checkbox so users are not surprised
- Checkbox checked by default for both forms
- Clear tooltip explaining behavior
- Allow opt-out by unchecking

---

## Files to Modify

1. `app/schemas/consolidated_schemas.py` - Schema updates
2. `app/services/entity_service.py` - Service layer logic
3. `app/routes/employer.py` - Route handlers
4. `docs/postman/collections/E2E Plate Selection.postman_collection.json` - Postman tests
5. `docs/api/client/EMPLOYER_ASSIGNMENT_WORKFLOW.md` - Documentation

---

## Testing Checklist

### Unit Tests
- [ ] Customer creates employer with `assign_employer=true` → `user.employer_id` set
- [ ] Customer creates employer with `assign_employer=false` → `user.employer_id` not set
- [ ] Customer adds address with `assign_employer=true` → `user.employer_id` set
- [ ] Customer adds address with `assign_employer=false` → `user.employer_id` not set
- [ ] Employee creates employer → `assign_employer` ignored, `user.employer_id` not set
- [ ] Transaction rollback: address creation fails → no employer, no assignment
- [ ] Transaction rollback: employer creation fails → no assignment
- [ ] Transaction rollback: user assignment fails → rollback employer and address

### Integration Tests (Postman)
- [ ] GET `/employers/` → verify empty list or existing employers
- [ ] POST `/employers/` with `assign_employer=true` → verify employer created and assigned
- [ ] POST `/employers/` with `assign_employer=false` → verify employer created but not assigned
- [ ] POST `/employers/{employer_id}/addresses` with `assign_employer=true` → verify address added and employer assigned
- [ ] POST `/employers/{employer_id}/addresses` with `assign_employer=false` → verify address added but employer not assigned
- [ ] GET `/users/me` → verify `employer_id` is set/not set based on `assign_employer` value

