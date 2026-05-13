# Vianda Kitchen Days API - Implementation Roadmap

## Overview
Create a dedicated API for managing `vianda_kitchen_days` records, allowing Suppliers to assign which viandas are available on which days of the week (Monday-Friday). This API will replace the nested endpoints currently under `/vianda-selections/kitchen-days/{vianda_id}`.

## Business Requirements

### Access Control
- **Suppliers**: Can view and manage kitchen days for viandas in their own institution only
- **Employees**: Can view and manage kitchen days for all institutions (global access)
- **Customers**: No access (403 Forbidden)

### Data Model
- Each `vianda_kitchen_days` record represents a combination of:
  - `vianda_id`: The vianda that is available
  - `kitchen_day`: Day of the week (Monday, Tuesday, Wednesday, Thursday, Friday)
- Unique constraint: `(vianda_id, kitchen_day)` - a vianda can only be available once per day
- Institution scoping path: `vianda_kitchen_days` → `vianda_info` → `restaurant_info` → `institution_id`

## API Endpoints

### Standard CRUD Endpoints

1. **GET `/vianda-kitchen-days/`**
   - List all kitchen day assignments
   - Supports `include_archived` query parameter
   - Institution scoped for Suppliers
   - Returns: `List[ViandaKitchenDayResponseSchema]`

2. **GET `/vianda-kitchen-days/{kitchen_day_id}`**
   - Get a single kitchen day assignment by ID
   - Supports `include_archived` query parameter
   - Institution scoped for Suppliers
   - Returns: `ViandaKitchenDayResponseSchema`

3. **POST `/vianda-kitchen-days/`**
   - Create a new kitchen day assignment
   - Validates:
     - Vianda exists
     - Vianda belongs to Supplier's institution (if Supplier)
     - `kitchen_day` is valid (Monday-Friday)
     - Unique constraint: `(vianda_id, kitchen_day)` doesn't already exist
   - Returns: `ViandaKitchenDayResponseSchema`

4. **PUT `/vianda-kitchen-days/{kitchen_day_id}`**
   - Update an existing kitchen day assignment
   - Validates same as POST
   - Institution scoped for Suppliers
   - Returns: `ViandaKitchenDayResponseSchema`

5. **DELETE `/vianda-kitchen-days/{kitchen_day_id}`**
   - Soft delete (archive) a kitchen day assignment
   - Institution scoped for Suppliers
   - Returns: Success message

### Enriched Endpoints

6. **GET `/vianda-kitchen-days/enriched/`**
   - List all kitchen day assignments with enriched data
   - Includes:
     - Institution Name
     - Restaurant Name
     - Vianda Name
     - Dietary (from product)
   - Supports `include_archived` query parameter
   - Institution scoped for Suppliers
   - Returns: `List[ViandaKitchenDayEnrichedResponseSchema]`

7. **GET `/vianda-kitchen-days/enriched/{kitchen_day_id}`**
   - Get a single kitchen day assignment with enriched data
   - Same enriched fields as list endpoint
   - Supports `include_archived` query parameter
   - Institution scoped for Suppliers
   - Returns: `ViandaKitchenDayEnrichedResponseSchema`

## Implementation Plan

### Phase 1: Schemas
- [ ] Create `ViandaKitchenDayCreateSchema`
  - Required: `vianda_id`, `kitchen_day`
  - Validation: `kitchen_day` must be one of: Monday, Tuesday, Wednesday, Thursday, Friday
- [ ] Create `ViandaKitchenDayUpdateSchema`
  - Optional: `vianda_id`, `kitchen_day`, `is_archived`
  - Same validation as Create
- [ ] Create `ViandaKitchenDayResponseSchema`
  - All fields from `ViandaKitchenDaysDTO`
- [ ] Create `ViandaKitchenDayEnrichedResponseSchema`
  - Base fields from `ViandaKitchenDayResponseSchema`
  - Additional: `institution_name`, `restaurant_name`, `vianda_name`, `dietary`

### Phase 2: Service Functions
- [ ] Create `get_enriched_vianda_kitchen_days()` in `entity_service.py`
  - Uses `EnrichedService` with JOINs:
    - `vianda_kitchen_days` (base table)
    - `vianda_info` (for vianda_id)
    - `restaurant_info` (for restaurant_id and institution_id)
    - `institution_info` (for institution_name)
    - `product_info` (for vianda_name and dietary)
  - Institution scoping via `restaurant.institution_id`
- [ ] Create `get_enriched_vianda_kitchen_day_by_id()` in `entity_service.py`
  - Similar to above but for single record

### Phase 3: Routes
- [ ] Create `app/routes/vianda_kitchen_days.py`
  - Import dependencies: `get_employee_user`, `get_supplier_user` (or create combined)
  - Implement all 7 endpoints
  - Add institution scoping logic:
    - Suppliers: Filter by `restaurant.institution_id = current_user.institution_id`
    - Employees: No filtering (global access)
    - Customers: 403 Forbidden
  - Validation:
    - Check vianda exists before create/update
    - Check unique constraint `(vianda_id, kitchen_day)`
    - Validate `kitchen_day` is valid weekday

### Phase 4: Registration
- [ ] Register router in `application.py`
- [ ] Add route prefix: `/vianda-kitchen-days`

### Phase 5: Testing & Documentation
- [ ] Update `API_PERMISSIONS_BY_ROLE.md` with new endpoints
- [ ] Test with Postman:
  - Supplier can only see/manage their institution's kitchen days
  - Employee can see/manage all kitchen days
  - Customer gets 403 Forbidden
  - Unique constraint prevents duplicates
  - Validation rejects invalid kitchen days

## Technical Details

### Institution Scoping Implementation
Since `vianda_kitchen_days` doesn't have `institution_id` directly, scoping must be done via JOIN:
```sql
SELECT pkd.* 
FROM vianda_kitchen_days pkd
INNER JOIN vianda_info p ON pkd.vianda_id = p.vianda_id
INNER JOIN restaurant_info r ON p.restaurant_id = r.restaurant_id
WHERE r.institution_id = %s  -- For Suppliers
```

### Enriched Query Structure
```sql
SELECT 
    pkd.vianda_kitchen_day_id,
    pkd.vianda_id,
    pkd.kitchen_day,
    pkd.is_archived,
    pkd.created_date,
    pkd.modified_by,
    pkd.modified_date,
    i.name as institution_name,
    r.name as restaurant_name,
    p.name as vianda_name,  -- Actually from product_info
    pr.dietary
FROM vianda_kitchen_days pkd
INNER JOIN vianda_info p ON pkd.vianda_id = p.vianda_id
INNER JOIN restaurant_info r ON p.restaurant_id = r.restaurant_id
INNER JOIN institution_info i ON r.institution_id = i.institution_id
INNER JOIN product_info pr ON p.product_id = pr.product_id
WHERE pkd.is_archived = FALSE
  AND r.institution_id = %s  -- For Suppliers only
```

### Unique Constraint Handling
The database has a unique constraint on `(vianda_id, kitchen_day)`. The API should:
1. Check for existing record before create
2. Return clear error message if duplicate
3. Allow updates to same record (no duplicate check needed)

## Migration Notes

### Deprecation Strategy
The existing endpoints under `/vianda-selections/kitchen-days/{vianda_id}` can remain for backward compatibility but should be documented as deprecated. The new dedicated API provides:
- Better REST semantics
- Proper institution scoping
- Enriched data support
- Standard CRUD operations

### Backward Compatibility
- Keep existing `/vianda-selections/kitchen-days/{vianda_id}` endpoints
- Add deprecation notice in docstrings
- Recommend migration to new API in documentation

## Success Criteria
- ✅ Suppliers can only see/manage kitchen days for their institution's viandas
- ✅ Employees can see/manage all kitchen days
- ✅ Customers get 403 Forbidden
- ✅ Unique constraint prevents duplicate `(vianda_id, kitchen_day)` combinations
- ✅ Enriched endpoint returns Institution Name, Restaurant Name, Vianda Name, Dietary
- ✅ All CRUD operations work correctly with institution scoping
- ✅ Validation rejects invalid kitchen days (weekends, invalid strings)

