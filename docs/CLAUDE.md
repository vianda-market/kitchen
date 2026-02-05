# Claude.md - PostgreSQL + FastAPI Development Principles

## Mission
Maximize developer velocity while guaranteeing data integrity in PostgreSQL-backed FastAPI applications

## Permission Model and Role-Based Access Control

### Role Type vs Role Name

The permission system uses a two-tier hierarchy:

1. **Role Type** (`role_type`): Determines the user's institutional affiliation
   - **Employee**: Belongs to Vianda Enterprises (our company), has global access to all institutions
   - **Supplier**: Belongs to a restaurant/institution, can only access data for their `institution_id`
   - **Customer**: End users who access iOS/Android apps only (no backoffice access)

2. **Role Name** (`name` in `role_info` table): Determines specific permissions within a role type
   - **Super Admin** (role_type: Employee, name: Super Admin): Can approve discretionary credit requests
   - **Admin** (role_type: Employee, name: Admin): Can request discretionary credits but cannot approve
   - **Admin** (role_type: Supplier, name: Admin): Can adjust supplier's information in the platform
   - **Comensal** (role_type: Customer, name: Comensal): Regular end user (mobile app access only)

### Key Principles

1. **Super Admin is an Employee**: Super Admin users have `role_type='Employee'` and `name='Super Admin'` (NOT `role_type='Super Admin'`)
   - This allows Super Admins to have global access (via Employee role_type) plus special approval permissions (via role_name)
   - All checks for Super Admin must verify BOTH: `role_type == "Employee" AND role_name == "Super Admin"`

2. **Institution Scoping**: 
   - **Employees**: Have global access (can see all institutions) - `InstitutionScope.is_global = True`
   - **Suppliers**: Scoped to their `institution_id` - access is restricted via `InstitutionScope.matches(institution_id)`
   - **Customers**: No backoffice access (mobile apps only)

3. **Permission Checks**:
   - System configuration APIs (Plan, Credit Currency, etc.) require `role_type == "Employee"` (any employee)
   - Super Admin operations (discretionary approval) require `role_type == "Employee" AND role_name == "Super Admin"`
   - Institution-scoped APIs require `InstitutionScope` validation

### Files That Handle Permissions

- **`app/auth/dependencies.py`**: Dependency functions for permission checks
  - `get_current_user()`: Base authentication (returns `user_id`, `role_type`, `institution_id`, `role_name`)
  - `get_super_admin_user()`: Verifies `role_type == "Employee" AND role_name == "Super Admin"` (approve/reject discretionary)
  - `get_employee_user()`: Verifies `role_type == "Employee"` (any employee - system configuration access)
  - `get_admin_user()`: Verifies `role_type == "Employee" AND role_name IN ["Admin", "Super Admin"]` (view discretionary requests)
  - `get_client_user()`: Verifies `role_type == "Customer"` (view plans, fintech links)
  - `get_client_or_employee_user()`: Verifies `role_type IN ["Customer", "Employee"]` (view plans - excludes Suppliers)

- **`app/security/institution_scope.py`**: Institution-based access control
  - `InstitutionScope.is_global`: Returns `True` for `role_type == "Employee"` (not "Super Admin")
  - `InstitutionScope.is_employee`: Returns `True` for `role_type == "Employee"`
  - Used for filtering data based on `institution_id`

- **`app/auth/routes.py`**: JWT token creation
  - Includes both `role_type` and `role_name` in the JWT payload

### Protected APIs and Access Levels

#### Employee-Only APIs (System Configuration)
- **Plans** (`/plans/*`): GET (Employees + Customers), POST/PUT/DELETE (Employees only)
- **Credit Currency** (`/credit-currencies/*`): All operations (Employees only)
- **Discretionary** (`/admin/discretionary/*`): All operations (Employees only)
- **Fintech Link** (`/fintech-link/*`): GET (Customers only), POST/PUT/DELETE (Employees only)

#### Super Admin-Only APIs
- **Discretionary Approval** (`/super-admin/discretionary/requests/{id}/approve`): Super Admin only
- **Discretionary Rejection** (`/super-admin/discretionary/requests/{id}/reject`): Super Admin only

#### Customer-Accessible APIs
- **Plans** (`/plans/*`): GET only (for subscription selection)
- **Fintech Link** (`/fintech-link/*`): GET only (for payment processing)

#### Supplier-Accessible APIs
- Suppliers can manage institution-scoped resources (Products, Plates, Restaurants, QR Codes, etc.)
- Suppliers **cannot** access system configuration APIs (Plans, Credit Currency, Discretionary, Fintech Link)

### Permission Dependency Chain

```
get_current_user() (base authentication)
    ├─> get_employee_user() (Employee role_type)
    │   ├─> get_admin_user() (Employee + Admin/Super Admin role_name)
    │   │   └─> get_super_admin_user() (Employee + Super Admin role_name)
    │   └─> Used for: Plans, Credit Currency, Discretionary, Fintech Link (POST/PUT/DELETE)
    │
    ├─> get_client_user() (Customer role_type)
    │   └─> Used for: Fintech Link (GET)
    │
    └─> get_client_or_employee_user() (Customer OR Employee role_type)
        └─> Used for: Plans (GET)
```

### Testing Permissions

- **Unit Tests**: `app/tests/auth/test_auth_dependencies.py` - Tests all dependency functions
- **Postman Collection**: `docs/postman/Permissions Testing - Employee-Only Access.postman_collection.json`
- **Test Guide**: `docs/postman/PERMISSIONS_TESTING_GUIDE.md`

## Core Engineering Standards

### Working with PostgreSQL Enums

**CRITICAL RULE**: Always check the database schema enum definition before assigning enum values in services.

#### Enum Value Format Rules

1. **Check Schema First**: Before using enum values in queries or service logic, verify the exact format in `app/db/schema.sql`
2. **Never Assume Case**: Enums are case-sensitive. `'Monday'` ≠ `'MONDAY'` ≠ `'monday'`
3. **Use Python Enums**: Reference the corresponding Python enum in `app/config/enums/` for type safety

#### Common PostgreSQL Enums

| Database Enum | Format | Python Enum | Example Values |
|---------------|--------|-------------|----------------|
| `kitchen_day_enum` | **Title Case** | `KitchenDay` | `'Monday'`, `'Tuesday'`, `'Wednesday'` |
| `address_type_enum` | **Title Case** | `AddressType` | `'Restaurant'`, `'Customer Home'` |
| `status_enum` | **Title Case** | `Status` | `'Active'`, `'Inactive'`, `'Pending'` |
| `role_type_enum` | **Title Case** | `RoleType` | `'Employee'`, `'Supplier'`, `'Customer'` |
| `pickup_type_enum` | **lowercase** | `PickupType` | `'self'`, `'for_others'`, `'by_others'` |

#### Correct Pattern

```python
# ✅ GOOD: Check schema, use correct case
def get_daily_orders(order_date: date, db):
    # Kitchen day enum in DB: 'Monday', 'Tuesday', etc. (Title Case)
    kitchen_day = order_date.strftime('%A')  # Returns 'Wednesday'
    kitchen_day = kitchen_day.title()  # Ensure Title Case
    
    query = """
        SELECT * FROM plate_selection
        WHERE kitchen_day = %s  -- Will match 'Wednesday' in DB
    """
    return db_read(query, [kitchen_day], db)

# ✅ GOOD: Use Python enum for type safety
from app.config.enums.kitchen_days import KitchenDay

def validate_kitchen_day(day_str: str) -> bool:
    valid_days = [day.value for day in KitchenDay]
    return day_str in valid_days  # ['Monday', 'Tuesday', ...]
```

#### Incorrect Patterns

```python
# ❌ BAD: Wrong case - will cause SQL error
def get_daily_orders(order_date: date, db):
    kitchen_day = order_date.strftime('%A').upper()  # Returns 'WEDNESDAY'
    # Error: invalid input value for enum kitchen_day_enum: "WEDNESDAY"
    query = """SELECT * FROM plate_selection WHERE kitchen_day = %s"""
    return db_read(query, [kitchen_day], db)

# ❌ BAD: Hardcoded without checking schema
def create_pickup(pickup_type: str):
    # Assumes lowercase, but what if enum is Title Case?
    query = """INSERT INTO pickup_preferences (pickup_type) VALUES (%s)"""
    db_write(query, [pickup_type.lower()])  # May fail if enum is 'Self', not 'self'

# ❌ BAD: Not using Python enum for validation
def validate_status(status: str) -> bool:
    # Hardcoded list may get out of sync with DB
    return status in ['Active', 'Inactive', 'Pending']
```

#### Enum Maintenance Checklist

When adding or modifying enum values:

1. **Update Database**: Modify `app/db/schema.sql` enum definition
2. **Update Python Enum**: Sync `app/config/enums/*.py` file
3. **Update Validators**: Check Pydantic validators in `app/schemas/consolidated_schemas.py`
4. **Update Services**: Search for hardcoded enum values in services
5. **Update Tests**: Verify test fixtures use correct enum values
6. **Migration**: Create ALTER TYPE migration if modifying existing enum

**Reference**: See `docs/database/ENUM_MAINTENANCE.md` for detailed enum management guide.

#### Debugging Enum Errors

**Error**: `invalid input value for enum kitchen_day_enum: "WEDNESDAY"`

**Diagnosis**:
```bash
# 1. Check database enum definition
psql -d kitchen_db_dev -c "SELECT unnest(enum_range(NULL::kitchen_day_enum))"

# Output:
#  Monday
#  Tuesday
#  Wednesday  # ← Title Case, not UPPERCASE

# 2. Check your code
grep -r "WEDNESDAY" app/services/  # Find the uppercase usage
```

**Fix**: Use `.title()` instead of `.upper()` to match database format.

---

### Function-First Design
1. **Functions over classes** - Use classes only for essential state management (e.g., `BaseModelCRUD`)
2. **Explicit dependencies** - Pass `db: psycopg2.connection`, `logger: LoggerAdapter` as parameters
3. **Pure functions**: `input -> Processing -> Output`
4. **Functions < 50 lines**, single responsibility 
5. **Type annotations required**
6. **Try statements as separate functions** - Error handling logic should be extracted into dedicated functions
7. **Data Transfer Objects (DTOs)** - Pure data structures with no functions, separate from business logic

### Testing Standards
1. **Minimize asserts per concept** - Test one concept per test function, use minimal assertions
2. **Fast execution** - Tests should complete in milliseconds, not seconds
3. **Independent tests** - Tests should not set conditions for other tests, no shared state
4. **Repeatable in any environment** - Tests should work consistently across dev/staging/prod
5. **Self-validating** - Tests should produce boolean output (pass/fail) without manual inspection
6. **Test-Driven Development** - Write tests right before the production code that makes them pass
7. **Mock external dependencies** - Database, APIs, file system should be mocked for unit tests
8. **Test business logic, not framework code** - Focus on testing service functions, not FastAPI routes
9. **Use descriptive test names** - Test names should clearly describe what is being tested
10. **Arrange-Act-Assert pattern** - Structure tests with clear setup, execution, and verification phases

### Service vs Utils Architecture
1. **Services contain business logic** - Domain rules, complex operations, orchestration logic
2. **Services require comprehensive testing** - All business logic must be thoroughly tested
3. **Utils contain low-level infrastructure** - Framework helpers, pure functions, configuration
4. **Utils do not require testing** - Infrastructure code is tested by the framework itself
5. **Clear separation of concerns** - Business logic in services, technical utilities in utils

#### Service vs Utils Examples
```python
# ✅ GOOD: Service - Business logic requiring tests
# app/services/date_service.py
def get_effective_current_day(timezone_str: str) -> str:
    """Business rule: Before 1 PM = previous day's service window"""
    if now.time() < time(13, 0):
        return (now - timedelta(days=1)).strftime('%A')
    return now.strftime('%A')

# ✅ GOOD: Service - Business logic requiring tests  
# app/services/geolocation_service.py
def get_timezone_from_location(country: str, city: str) -> str:
    """Business rule: Map country/city to timezone"""
    timezone_mapping = {
        ("Argentina", "Buenos Aires"): "America/Argentina/Buenos_Aires",
        # ... more business rules
    }
    return timezone_mapping.get((country, city), "America/Argentina/Buenos_Aires")

# ❌ BAD: Utils - Simple framework wrapper, no testing needed
# app/utils/log.py
def log_info(message: str):
    """Simple logging wrapper - framework handles this"""
    logger.info(message)

# ❌ BAD: Utils - Framework configuration, no testing needed
# app/utils/query_params.py
def include_archived_query(entity_name: str) -> bool:
    """FastAPI Query parameter - framework handles validation"""
    return Query(False, description=f"Include archived {entity_name}")
```

### Testing Patterns
```python
# Good: Single concept test with minimal assertions
def test_user_signup_processes_password_correctly():
    """Test that password is hashed during signup process"""
    # Arrange
    user_data = {"email": "test@example.com", "password": "plaintext123"}
    mock_db = Mock()
    
    # Act
    result = user_signup_service.process_customer_signup(user_data, mock_db)
    
    # Assert
    assert "hashed_password" in result
    assert "password" not in result

# Good: Fast, independent test with mocked dependencies
def test_currency_resolution_looks_up_currency_code():
    """Test that currency code is resolved from credit currency ID"""
    # Arrange
    bill_data = {"credit_currency_id": "123e4567-e89b-12d3-a456-426614174000"}
    mock_db = Mock()
    mock_currency = Mock(currency_code="USD")
    credit_currency_service.get_by_id = Mock(return_value=mock_currency)
    
    # Act
    client_bill_business_service._resolve_currency_code(bill_data, mock_db)
    
    # Assert
    assert bill_data["currency_code"] == "USD"

# Good: Descriptive test name and self-validating
def test_qr_code_scan_validates_restaurant_match():
    """Test that QR code scan fails when restaurant doesn't match pickup location"""
    # Arrange
    pickup_record = Mock(restaurant_id="restaurant-1")
    qr_code = Mock(restaurant_id="restaurant-2")
    mock_db = Mock()
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        plate_pickup_service._validate_restaurant_match(pickup_record, qr_code, mock_db)
    
    assert "You're at" in str(exc_info.value.detail)

# Avoid: Multiple concepts in one test
def test_user_creation_and_validation_and_email_sending():
    """BAD: Testing multiple concepts"""
    # This tests user creation, validation, AND email sending
    pass

# Avoid: Slow tests with real dependencies
def test_database_operations_with_real_db():
    """BAD: Uses real database, slow and environment-dependent"""
    # This will be slow and may fail in different environments
    pass
```

### Framework Patterns
```python
# Good: Pure DTO - data structure only
class UserDTO(BaseModel):
    """Pure DTO - no functions, just data structure"""
    user_id: UUID
    username: str
    email: Optional[str] = None
    is_archived: bool = False
    created_date: datetime

# Good: Generic CRUD service - eliminates duplication
def get_user_by_id(user_id: UUID, db: psycopg2.connection) -> Optional[UserDTO]:
    """Generic function - no model class needed"""
    return generic_crud.get_by_id("user_info", UserDTO, "user_id", user_id, db)

# Good: FastAPI route with explicit dependencies
async def create_plate_selection(
    payload: PlateSelectionCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
) -> PlateSelectionResponseSchema:
    """Clear input/output, explicit PostgreSQL connection"""
    pass

# Good: Service function with explicit dependencies  
def create_matching_preference(
    plate_selection_id: UUID,
    pickup_type: str,
    target_time: datetime,
    user_id: UUID,
    logger: LoggerAdapter,
    db: psycopg2.connection
) -> PickupPreferencesDTO:
    """Pure function with explicit inputs/outputs"""
    pass

# Good: Error handling as separate function
def create_employer_with_transaction(
    employer_data: dict,
    address_data: dict,
    current_user: dict,
    db: psycopg2.connection
) -> EmployerModel:
    """Main orchestration function"""
    return handle_employer_creation_transaction(
        employer_data, address_data, current_user["user_id"], db
    )

def handle_employer_creation_transaction(
    employer_data: dict,
    address_data: dict,
    user_id: UUID,
    db: psycopg2.connection
) -> EmployerModel:
    """Dedicated function for error handling and transaction management"""
    try:
        db.begin()
        
        # Create address first
        address_record = Address.create(address_data, connection=db)
        
        # Add address_id to employer data
        employer_data["address_id"] = address_record.address_id
        employer_data["modified_by"] = user_id
        
        # Create employer
        employer_record = Employer.create(employer_data, connection=db)
        
        db.commit()
        return employer_record
        
    except Exception as e:
        db.rollback()
        log_error(f"Failed to create employer: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create employer: {e}")
```

## PostgreSQL-Specific Principles

### Database Connection Management
```python
# Good: Explicit connection handling
def update_user_balance(user_id: UUID, credit_amount: int, db: psycopg2.connection) -> bool:
    """Single transaction, explicit connection"""
    try:
        db.begin()
        user = User.get_by_id(user_id, connection=db)
        user.update({"balance": user.balance + credit_amount}, connection=db)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise

# Avoid: Hidden connection management
def update_user_balance(user_id: UUID, credit_amount: int):
    """Connection hidden in model methods - hard to test/track"""
    pass
```

### Query Optimization Practices
```python
# Good: Explicit, optimized queries
def find_coworker_matches(
    user_id: UUID, 
    restaurant_id: UUID,
    pickup_window: tuple[datetime, datetime],
    db: psycopg2.connection
) -> List[PickupPreferencesModel]:
    """Optimized query for pickup matching"""
    query = """
    SELECT pp.preference_id, pp.pickup_type, pp.target_pickup_time
    FROM pickup_preferences pp
    JOIN plate_selection ps ON pp.plate_selection_id = ps.plate_selection_id
    JOIN user_info u ON pp.user_id = u.user_id  
    WHERE ps.restaurant_id = %s 
    AND pp.target_pickup_time BETWEEN %s AND %s
    AND u.employer_id = (
        SELECT employer_id FROM user_info WHERE user_id = %s
    )
    AND pp.is_matched = FALSE
    """
    return db_read(query, (restaurant_id, pickup_window[0], pickup_window[1], user_id), connection=db)
```

### Transactions & Data Integrity
```python
# Good: Explicit transaction boundaries
def create_employer_with_address(
    employer_data: dict,
    address_data: dict, 
    current_user: dict,
    db: psycopg2.connection
) -> EmployerModel:
    """Atomic creation with explicit transaction"""
    try:
        # Create address first
        address_record = Address.create(address_data, connection=db)
        
        # Add address_id to employer data
        employer_data["address_id"] = address_record.address_id
        
        # Create employer
        employer_record = Employer.create(employer_data, connection=db)
        
        return employer_record
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create employer: {e}")
```

## FastAPI-Specific Patterns

### Route Design
```python
# Good: Clear, typed routes
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/pickup-preferences", tags=["Pickup Preferences"])

@router.post("/", response_model=PickupPreferencesResponseSchema, status_code=status.HTTP_201_CREATED)
def create_pickup_preference(
    payload: PickupPreferencesCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
) -> PickupPreferencesResponseSchema:
    """Single responsibility: create pickup preference"""
    
    # Validate permission
    if not can_create_preference(current_user["user_id"], payload.plate_selection_id, db):
        raise HTTPException(status_code=403, detail="Cannot create preference for this plate")
    
    try:
        preference = PickupPreferences.create({
            "plate_selection_id": payload.plate_selection_id,
            "user_id": current_user["user_id"],
            "pickup_type": payload.pickup_type,
            "target_pickup_time": payload.target_pickup_time,
            "modified_by": current_user["user_id"]
        }, connection=db)
        
        # Trigger matching algorithm
        find_and_match_preferences(preference.preference_id, logger, db)
        
        return preference
        
    except Exception as e:
        log_warning(f"Error creating pickup preference: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### Schema Design
```python
# Good: Clear, validated schemas
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID

class PickupPreferencesCreateSchema(BaseModel):
    plate_selection_id: UUID = Field(..., description="Reference to selected plate")
    pickup_type: Literal['self', 'for_others', 'by_others'] = Field(..., description="Pickup method")
    target_pickup_time: Optional[datetime] = Field(None, description="Desired pickup time")
    time_window_minutes: int = Field(30, ge=5, le=120, description="Matching window in minutes")
    
    @validator('target_pickup_time')
    def validate_pickup_time(cls, v):
        if v and v < datetime.now():
            raise ValueError('Pickup time cannot be in the past')
        return v
```

### Schema Field Naming - Reserved Type Names

**CRITICAL RULE**: Never use Python type names as field names in Pydantic schemas. This causes `RuntimeError: error checking inheritance` during schema validation.

**Reserved Names to Avoid**:
```python
# ❌ BAD: Using type names as field names
class BadSchema(BaseModel):
    date: date          # Conflicts with datetime.date type
    time: time          # Conflicts with datetime.time type
    datetime: datetime  # Conflicts with datetime.datetime type
    list: List[str]     # Conflicts with built-in list type
    dict: Dict[str, Any]  # Conflicts with built-in dict type
    set: Set[str]       # Conflicts with built-in set type
    tuple: Tuple[str]   # Conflicts with built-in tuple type
    type: str           # Conflicts with built-in type
    object: Any         # Conflicts with built-in object
    int: int            # Conflicts with built-in int (rare but avoid)
    str: str            # Conflicts with built-in str (rare but avoid)
    bool: bool          # Conflicts with built-in bool (rare but avoid)

# ✅ GOOD: Use descriptive names instead
class GoodSchema(BaseModel):
    order_date: date           # Clear and specific
    pickup_time: time          # Clear and specific
    created_datetime: datetime # Clear and specific
    items_list: List[str]      # Or just "items"
    metadata_dict: Dict[str, Any]  # Or just "metadata"
    tags_set: Set[str]         # Or just "tags"
    coordinates: Tuple[float, float]  # Or "coords"
    entity_type: str           # Clear and specific
    data_object: Any           # Or just "data"
```

**Error Example**:
```python
# This will cause: RuntimeError: error checking inheritance of FieldInfo
class DailyOrdersResponseSchema(BaseModel):
    date: date = Field(..., description="Date of the orders")  # ❌ BREAKS!
    
# Fix:
class DailyOrdersResponseSchema(BaseModel):
    order_date: date = Field(..., description="Date of the orders")  # ✅ WORKS!
```

**Why This Happens**:
- Pydantic's validator system uses `issubclass()` checks during schema creation
- When field name matches type name, Python's namespace resolution gets confused
- The validator tries to check if the field is a subclass of itself
- Results in: `TypeError: issubclass() arg 1 must be a class`

**Best Practices**:
1. **Prefix with context**: `order_date`, `pickup_time`, `created_datetime`
2. **Suffix with type**: `items_list`, `metadata_dict` (or just use plural: `items`, `tags`)
3. **Use descriptive names**: `scheduled_at`, `delivery_window`, `customer_tags`
4. **Be specific**: `start_date` instead of `date`, `access_token` instead of `token`

## Centralization Patterns

### Model Centralization with DTOs
```python
# Single file for all DTOs (app/dto/models.py)
class UserDTO(BaseModel):
    """Pure DTO for user data - no functions, just data structure"""
    user_id: UUID
    institution_id: UUID
    username: str
    # ... other fields
    
    class Config:
        orm_mode = True

# Generic CRUD service (app/services/crud_service.py)
class CRUDService(Generic[T]):
    def __init__(self, table_name: str, dto_class: Type[T], id_column: str):
        self.table_name = table_name
        self.dto_class = dto_class
        self.id_column = id_column
    
    def get_by_id(self, record_id: UUID, db: psycopg2.connection) -> Optional[T]:
        """Generic get_by_id for any entity"""
        query = f"SELECT * FROM {self.table_name} WHERE {self.id_column} = %s"
        result = db_read(query, (str(record_id),), connection=db, fetch_one=True)
        return self.dto_class(**result) if result else None

# Service instances
user_service = CRUDService("user_info", UserDTO, "user_id")
institution_service = CRUDService("institution_info", InstitutionDTO, "institution_id")
```

### Route Centralization with Factory Pattern
```python
# Generic route service (app/services/route_service.py)
class GenericRouteService:
    @staticmethod
    def get_by_id(entity_type: str, entity_id: UUID, include_archived: bool, db):
        service = get_service_for_entity(entity_type)
        if include_archived:
            return service.get_by_id(entity_id, db)
        return service.get_by_id_non_archived(entity_id, db)

# Route factory (app/routes/generic_router.py)
def create_crud_routes(entity_type: str, schemas: dict, service):
    router = APIRouter(prefix=f"/{entity_type}s", tags=[entity_type.title()])
    
    @router.get("/{entity_id}", response_model=schemas['response'])
    def get_entity(entity_id: UUID, include_archived: bool = Query(False), db = Depends(get_db)):
        return GenericRouteService.get_by_id(entity_type, entity_id, include_archived, db)
    
    @router.get("/", response_model=List[schemas['response']])
    def get_all_entities(include_archived: bool = Query(False), db = Depends(get_db)):
        return GenericRouteService.get_all(entity_type, include_archived, db)
    
    return router

# Auto-generate routes for simple entities
role_router = create_crud_routes("role", role_schemas, role_service)
plan_router = create_crud_routes("plan", plan_schemas, plan_service)
```

### Dynamic DTO Generation with Pydantic
```python
# Dynamic DTO creation (app/dto/dynamic_models.py)
from pydantic import create_model, BaseModel

def create_dto_from_schema(schema_class: Type[BaseModel], table_name: str, id_column: str) -> Type[BaseModel]:
    """Dynamically create DTO from existing Pydantic schema"""
    
    # Get field information from schema
    fields = {}
    for field_name, field_info in schema_class.__fields__.items():
        if field_info.default is not None:
            fields[field_name] = (field_info.type_, field_info.default)
        else:
            fields[field_name] = (field_info.type_, ...)
    
    # Create the DTO class
    dto_class = create_model(
        f"{schema_class.__name__}DTO",
        **fields,
        __config__=type('Config', (), {'orm_mode': True})()
    )
    
    return dto_class

# Usage
ProductDTO = create_dto_from_schema(ProductCreateSchema, "product_info", "product_id")
```

### Service Layer Architecture
```python
# Business logic service (app/services/plate_selection_service.py)
def create_plate_selection_with_transactions(
    payload: Dict[str, Any],
    current_user: Dict[str, Any],
    db: psycopg2.extensions.connection
) -> Optional[PlateSelectionDTO]:
    """Create a plate selection with all related transactions"""
    
    # Step 1: Validate and fetch required data
    context = _fetch_plate_selection_context(payload, db)
    
    # Step 2: Determine target kitchen day
    context["target_day"] = determine_target_kitchen_day(
        payload.get("target_kitchen_day"),
        context["plate"],
        get_effective_current_day()
    )
    
    # Step 3: Create the plate selection
    selection = _create_plate_selection_record(context, current_user, db)
    
    # Step 4: Create related records
    _create_related_records(selection, context, current_user, db)
    
    return selection

# Route delegates to service
@router.post("/", response_model=PlateSelectionResponseSchema)
def create_plate_selection(payload: PlateSelectionCreateSchema, current_user = Depends(get_current_user), db = Depends(get_db)):
    payload_dict = payload.dict()
    selection = create_plate_selection_with_transactions(payload_dict, current_user, db)
    if not selection:
        raise HTTPException(status_code=500, detail="Failed to create plate selection")
    return selection
```

## Data Change Logging for PostgreSQL

### Audit Trail Pattern
```python
from app.utils.log import log_info, log_warning
from app.utils.db import db_read

def log_data_change_event(
    table_name: str,
    operation: str,  # 'INSERT', 'UPDATE', 'DELETE'
    record_id: UUID,
    previous_data: Optional[dict],
    new_data: dict,
    modified_by: UUID,
    connection: psycopg2.connection
) -> None:
    """Log data changes for audit trail"""
    
    log_info(f"Data change: {operation} on {table_name}:{record_id} by user:{modified_by}")
    
    # Store in audit_log table
    audit_data = {
        "table_name": table_name,
        "operation": operation,
        "record_id": str(record_id),
        "previous_data": json.dumps(previous_data) if previous_data else None,
        "new_data": json.dumps(new_data),
        "modified_by": str(modified_by),
        "modified_date": datetime.now()
    }
    
    db_insert("audit_log", audit_data, connection=connection)
```

### Best Practice Pattern Template
```python "
@router.put("/{employer_id}", response_model=EmployerResponseSchema)
async def update_employer(
    employer_id: UUID,
    employer_update: EmployerUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
) -> EmployerResponseSchema:
    """Update employer with audit logging"""
    
    # Get current data for audit
    previous_data = Employer.get_by_id(employer_id, connection=db).dict()
    
    # Prepare update
    update_data = {k: v for k, v in employer_update.dict(exclude_unset=True).items()}
    update_data["modified_by"] = current_user["user_id"]
    
    # Log data change before update
log_data_change_event(
        table_name="employer_info",
        operation="UPDATE", 
        record_id=employer_id,
        previous_data=previous_data,
        new_data=update_data,
        modified_by=current_user["user_id"],
        connection=db
    )
    
    # Execute update
    updated_employer = Employer.update(employer_id, update_data, connection=db)
    return updated_employer
```

## Anti-Overengineering Rules

1. **No classes** unless essential state management (stick to `BaseModelCRUD`)
2. **No complex inheritance** - prefer composition over inheritance
3. **No interfaces with single implementations**
4. **Simple SQL queries** - avoid ORM complexity when raw SQL is clearer

## Refactoring Triggers

1. Functions > 50 lines (break into smaller functions)
2. More than 3 levels of nesting (use early returns/guards)
3. Functions with >5 parameters (consider data structures)
4. Mixed abstraction levels in single function
5. Hidden database connections (make them explicit)
6. Try statements within functions (extract error handling into separate functions)
7. Models with both data structures and CRUD logic (separate into DTOs + services)
8. Business logic in utils (move to services and add comprehensive tests)
9. Infrastructure code in services (move to utils, no testing needed)

## Performance Optimization

### PostgreSQL Best Practices
```sql
-- Optimize pickup matching queries
CREATE INDEX CONCURRENTLY idx_pickup_matching 
ON pickup_preferences (restaurant_id, pickup_type, target_pickup_time) 
WHERE is_matched = FALSE;

-- Optimize user searches
CREATE INDEX idx_user_employer ON user_info (employer_id) 
WHERE employer_id IS NOT NULL;

-- Composite indexes for complex queries
CREATE INDEX idx_coworker_matching 
ON pickup_preferences (plate_selection_id, user_id, pickup_type);
```

### Connection Pool Optimization
```python
# app/dependencies/database.py
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

def create_db_pool():
    """Optimized connection pool for PostgreSQL"""
    return QueuePool(
        dialect="postgresql",
        pool_size=10,           # Base connections
        max_overflow=20,        # Additional connections when needed
        pool_pre_ping=True,     # Health check connections
        pool_recycle=300        # Recycle connections every 5 minutes
    )
```

## Test Guidelines

### Database Testing
```python
# Good: Isolated test with explicit connection
def test_create_pickup_preference():
    """Test pickup preference creation"""
    test_db = get_test_db_connection()
    
    # Clean setup
    test_data = create_test_plate_selection(test_db)
    
    # Test function
    result = create_pickup_preference(
        plate_selection_id=test_data.plate_selection_id,
        pickup_type="for_others",
        target_time=datetime.now() + timedelta(hours=1),
        user_id=test_data.user_id,
        logger=mock_logger,
        db=test_db
    )
    
    # Verify
    assert result.pickup_type == "for_others"
    assert not result.is_matched
    
    # Cleanup
    cleanup_test_data(test_db)
```

## Current Architecture Strengths (Keep This!)

✅ **Fast real-time operations** - PostgreSQL <1ms for simple queries  
✅ **ACID transactions** - Perfect for billing/financial operations  
✅ **Simple local development** - One `docker-compose up` command  
✅ **Type safety** - Pydantic models + FastAPI automatic validation  
✅ **Clear error handling** - HTTPException with proper status codes  
✅ **Easy testing** - Unit tests with test database connections

## Error Handling Standards

### **Exception vs None Return Patterns**

**Use HTTPException (Raise Exceptions) for:**
- **API Layer Operations**: All FastAPI route handlers should raise HTTPException
- **CRUD Operations**: Create, Read, Update, Delete operations should raise HTTPException
- **Validation Failures**: Invalid input data should raise HTTPException (400)
- **Resource Not Found**: Missing entities should raise HTTPException (404)
- **Business Rule Violations**: When business logic prevents an operation (400/403)
- **System Errors**: Database failures, external API failures (500)

**Use None Return for:**
- **Optional Operations**: When failure is expected and handled gracefully
- **Background Processing**: Cron jobs, async tasks where failure doesn't affect user
- **Data Lookups**: When "not found" is a normal, expected condition
- **Internal Helper Functions**: Pure utility functions that don't interact with users

### **Standardized Error Handling Functions**

```python
# ✅ GOOD: API operations raise exceptions
def create_user(user_data: dict, db: connection) -> UserDTO:
    if not user_data.get("email"):
        raise HTTPException(status_code=400, detail="Email is required")
    
    user = user_service.create(user_data, db)
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create user")
    return user

# ✅ GOOD: Optional operations return None
def find_user_by_username(username: str, db: connection) -> Optional[UserDTO]:
    try:
        return user_service.get_by_username(username, db)
    except Exception:
        return None  # Username not found is expected

# ❌ BAD: Inconsistent pattern
def create_plate_selection(payload: dict, db: connection) -> Optional[PlateSelectionDTO]:
    # This should raise HTTPException, not return None
    if not payload.get("plate_id"):
        return None  # Should be: raise HTTPException(400, "Plate ID required")
```

### **Error Handling Function Usage**

```python
# ✅ GOOD: Use error handling functions for consistent patterns
def create_product(product_data: dict, current_user: dict, db: connection) -> ProductDTO:
    return handle_create(
        product_service.create, 
        product_data, 
        db, 
        "product"
    )

# ✅ GOOD: Business operations can return None for optional processing
def process_background_task(task_data: dict) -> Optional[TaskResult]:
    return handle_business_operation(
        _process_task_logic,
        "background task processing",
        task_data
    )
```

### **Migration Strategy**

1. **Phase 1**: Update all API route handlers to use HTTPException
2. **Phase 2**: Update business services to use appropriate pattern
3. **Phase 3**: Standardize error handling functions
4. **Phase 4**: Update tests to match new patterns

## Enriched Endpoint Pattern

### Problem
When UI needs to display related entity names (e.g., `role_name`, `institution_name`) but the base endpoint only returns foreign key IDs, the UI would need to make N+1 queries or multiple round trips to fetch related data.

### Solution: Enriched Endpoints
Create dedicated `/enriched/` endpoints that use SQL JOINs to return denormalized data in a single query. This eliminates N+1 queries and provides a better developer experience.

### Implementation Pattern

```python
# 1. Create enriched response schema (app/schemas/consolidated_schemas.py)
class UserEnrichedResponseSchema(BaseModel):
    """Schema for enriched user response data with role and institution names"""
    user_id: UUID
    institution_id: UUID
    institution_name: str  # ← Denormalized from institution_info
    role_id: UUID
    role_name: str         # ← Denormalized from role_info
    role_type: str         # ← Denormalized from role_info
    username: str
    email: str
    # ... other user fields

# 2. Create enriched service methods (app/services/entity_service.py)
def get_enriched_users(
    db: psycopg2.extensions.connection,
    *,
    scope: Optional[InstitutionScope] = None,
    include_archived: bool = False
) -> List[UserEnrichedResponseSchema]:
    """Get all users with enriched data using SQL JOINs"""
    query = """
        SELECT 
            u.user_id,
            u.institution_id,
            i.name as institution_name,  # ← JOIN with institution_info
            u.role_id,
            r.name as role_name,          # ← JOIN with role_info
            r.role_type,                  # ← JOIN with role_info
            u.username,
            u.email,
            # ... other user fields
        FROM user_info u
        JOIN role_info r ON u.role_id = r.role_id
        JOIN institution_info i ON u.institution_id = i.institution_id
        WHERE u.is_archived = FALSE
        ORDER BY u.created_date DESC
    """
    results = db_read(query, None, connection=db)
    return [UserEnrichedResponseSchema(**result) for result in results]

# 3. Create enriched endpoints (app/routes/user.py)
@router.get("/enriched/", response_model=List[UserEnrichedResponseSchema])
def list_enriched_users(
    include_archived: Optional[bool] = include_archived_optional_query("users"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all users with enriched data (role_name, role_type, institution_name)"""
    scope = get_institution_scope(current_user)
    return get_enriched_users(db, scope=scope, include_archived=include_archived or False)

@router.get("/enriched/{user_id}", response_model=UserEnrichedResponseSchema)
def get_enriched_user_by_id_route(
    user_id: UUID,
    include_archived: bool = include_archived_query("users"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a single user by ID with enriched data"""
    scope = get_institution_scope(current_user)
    enriched_user = get_enriched_user_by_id(user_id, db, scope=scope, include_archived=include_archived)
    if not enriched_user:
        raise HTTPException(status_code=404, detail="User not found")
    return enriched_user
```

### Benefits
- **Single Query**: Eliminates N+1 queries by using SQL JOINs
- **Better Performance**: One database round trip instead of multiple
- **Better DX**: UI gets all needed data in one API call
- **Backward Compatible**: Base endpoints remain unchanged
- **Institution Scoping**: Enriched endpoints respect institution scoping rules

### When to Use
- **Use enriched endpoints** when UI needs to display related entity names frequently
- **Use base endpoints** when UI only needs the entity itself or will fetch related data separately
- **Examples**: Users with role/institution names, Products with restaurant names, Bills with institution names

### Naming Convention
- Base endpoints: `/users/`, `/users/{id}`
- Enriched endpoints: `/users/enriched/`, `/users/enriched/{id}`
- Response schemas: `UserResponseSchema` vs `UserEnrichedResponseSchema`

## Focus Areas

1. **Query optimization** - Better indexes for pickup matching
2. **Function simplification** - Break down complex methods
3. **Explicit dependencies** - Make database connections obvious
4. **Performance monitoring** - Add slow query logging
5. **Schema evolution** - Simple migrations with proper rollbacks
6. **Error handling standardization** - Consistent exception vs None patterns
7. **Enriched endpoints** - Use SQL JOINs to eliminate N+1 queries for UI display needs

🎯 **Goal: Simple, fast, maintainable PostgreSQL + FastAPI codebase**

## API Documentation

### Versioning Strategy
- **API Versioning Guide**: [docs/api/API_VERSIONING_GUIDE.md](api/API_VERSIONING_GUIDE.md)
- **Current Version**: v1 (default)
- **Versioning Strategy**: URL Path (`/api/v1/plans/`)
- **Schema Versioning**: Infrastructure ready for version-specific schemas

### Route Architecture
- **User-Dependent Routes Pattern**: [docs/api/USER_DEPENDENT_ROUTES_PATTERN.md](api/USER_DEPENDENT_ROUTES_PATTERN.md)
- **Admin/System Routes**: `crud_routes.py` - Operations by administrators, no user context required
- **User Routes**: `crud_routes_user.py` - Operations by end-users, require user_id extraction
- **Route Separation**: Clear distinction between admin operations vs user-owned entity operations

## Database Documentation

### Connection Patterns
- **Database Connection Patterns**: [docs/database/DATABASE_CONNECTION_PATTERNS.md](database/DATABASE_CONNECTION_PATTERNS.md)
- **Pattern Types**: Database utility functions vs Business service functions
- **Usage Guidelines**: When to use `connection=db` vs positional `db` parameter

### Table Naming Conventions
- **Database Table Naming Patterns**: [docs/database/DATABASE_TABLE_NAMING_PATTERNS.md](database/DATABASE_TABLE_NAMING_PATTERNS.md)
- **Naming Rules**: `_info` suffix for fully editable tables with history tracking
- **Table Categories**: Fully editable, immutable, partially editable, and event/log tables
- **Implementation Guidelines**: CRUD service configuration and route factory patterns

### Database Management
- **Database Rebuild Guide**: [docs/database/DATABASE_REBUILD_PERSISTENCE.md](database/DATABASE_REBUILD_PERSISTENCE.md)
- **Rebuild Process**: Step-by-step database reconstruction and data persistence
## Enriched Endpoint Field Naming Guidelines

### Principle: DO NOT Rename Fields Unless There Is a Collision

**CRITICAL RULE**: Only rename fields when there is an **actual or expected collision** between joined tables. If there is no collision, use the original field name from the source table.

### When to Rename

✅ **Rename ONLY when collision exists or is expected:**
- `plan.status` → `plan_status` (collision with `fintech_link_info.status`)
- `user.name` → `user_name` (if another table in the JOIN has a `name` column)
- `restaurant.name` → `restaurant_name` (collision with `institution_info.name`)

❌ **DO NOT rename when no collision exists:**
- `plan.price` → Keep as `price` (no collision with `fintech_link_info`)
- `plan.credit` → Keep as `credit` (no collision with `fintech_link_info`)
- `user.email` → Keep as `email` (no collision - base table doesn't have `email`)
- `user.username` → Keep as `username` (no collision - base table doesn't have `username`)
- `user.cellphone` → Keep as `cellphone` (no collision - base table doesn't have `cellphone`)
- `CONCAT(first_name, last_name)` → Keep as `full_name` (no collision - base table doesn't have `full_name`)

**Example of incorrect renaming (DO NOT DO THIS):**
```python
# ❌ WRONG: Renaming user fields when fintech_link_transaction table has no collision
"u.username as user_username",  # Base table has no 'username' field - NO RENAME NEEDED
"u.email as user_email",         # Base table has no 'email' field - NO RENAME NEEDED
"u.cellphone as user_cellphone", # Base table has no 'cellphone' field - NO RENAME NEEDED
```

**Correct approach:**
```python
# ✅ CORRECT: Use original field names when no collision
"u.username",      # No collision - use original name
"u.email",          # No collision - use original name
"u.cellphone",      # No collision - use original name
"TRIM(COALESCE(CONCAT_WS(' ', u.first_name, u.last_name), '')) as full_name",  # Computed field, no collision
```

### Implementation Checklist

### Warning System

When renaming fields without a clear collision, add a warning comment:
```python
# ⚠️ WARNING: Field renamed without clear collision - review if prefix needed
"pl.name as plan_name",  # Consider: Is there a future collision risk?
```

This allows the team to:
- Review the naming decision during code review
- Revisit if schema changes introduce collisions
- Document the reasoning for future developers


When creating enriched endpoints:

1. **Identify potential collisions:**
   - Check all tables in JOINs for column name conflicts
   - Consider future schema changes that might introduce collisions

2. **Minimal renaming approach:**
   - Use original column names when safe
   - Only add prefixes/suffixes when collision exists or is highly likely

3. **Documentation:**
   - If renaming without obvious collision, add a comment explaining why
   - Example: `pl.name as plan_name  # Descriptive, no collision but clarifies source`

4. **Warning for review:**
   - If you rename a field without a clear collision, add a `# TODO: Review field naming` comment
   - This allows the team to revisit the decision

### Examples

**Good (collision avoided):**
```python
select_fields=[
    "pl.price",  # No collision - fintech_link_info doesn't have 'price'
    "pl.credit",  # No collision - fintech_link_info doesn't have 'credit'
    "pl.status as plan_status",  # Collision with fl.status - rename required
    "pl.name as plan_name",  # Descriptive, clarifies source table
]
```

**Avoid (unnecessary renaming):**
```python
select_fields=[
    "pl.price as plan_price",  # ❌ Unnecessary - no collision
    "pl.credit as plan_credit",  # ❌ Unnecessary - no collision
]
```

### Benefits

- **Consistency**: Field names match database column names when possible
- **Simplicity**: Less cognitive overhead for developers
- **Maintainability**: Easier to trace fields back to source tables
- **Flexibility**: Can add prefixes later if collisions emerge

---

## Root Cause Resolution Principle

### **CRITICAL RULE: Always Fix Issues at the Root Cause, Not with Downstream Transformations**

When encountering data type mismatches, validation errors, or similar issues, **always investigate and fix the root cause** rather than applying downstream transformations or workarounds.

### **Why Root Cause Resolution Matters**

1. **Type Safety**: Fixing at the root ensures proper type handling throughout the entire stack
2. **Performance**: Root cause fixes are typically more efficient than downstream transformations
3. **Maintainability**: Root cause fixes are easier to understand and maintain
4. **Consistency**: Ensures all code paths use the same correct approach
5. **Future-Proofing**: Prevents similar issues from appearing in other parts of the codebase

### **Example: Enum Array Type Handling**

**Problem**: When inserting `address_type` arrays (e.g., `['Customer Home', 'Customer Billing']`) into PostgreSQL, psycopg2 was sending them as `TEXT[]` instead of `address_type_enum[]`, causing type mismatch errors.

**❌ WRONG Approach (Downstream Transformation):**
```python
# Bad: SQL casting as primary solution
def _build_insert_sql(table: str, data: dict):
    placeholders = []
    for col in data.keys():
        if table == 'address_info' and col == 'address_type':
            placeholders.append('%s::address_type_enum[]')  # SQL casting
        else:
            placeholders.append('%s')
    # ... rest of function
```

**✅ CORRECT Approach (Root Cause Fix):**
```python
# Good: Register enum types with psycopg2 at connection time
def _register_enum_types(conn: psycopg2.extensions.connection):
    """Register PostgreSQL enum types with psycopg2 for proper array handling"""
    cursor.execute("SELECT oid, typarray FROM pg_type WHERE typname = 'address_type_enum'")
    result = cursor.fetchone()
    if result:
        enum_oid, array_oid = result
        ADDRESS_TYPE_ENUM = psycopg2.extensions.new_type((enum_oid,), 'ADDRESS_TYPE_ENUM', ...)
        psycopg2.extensions.register_type(ADDRESS_TYPE_ENUM, conn)
        ADDRESS_TYPE_ENUM_ARRAY = psycopg2.extensions.new_array_type((array_oid,), ...)
        psycopg2.extensions.register_type(ADDRESS_TYPE_ENUM_ARRAY, conn)

# Then use psycopg2.extras.Array() which automatically uses registered types
def _prepare_value_for_db(value: Any, table: str, column: str, connection=None):
    if table == 'address_info' and column == 'address_type' and isinstance(value, list):
        return psycopg2.extras.Array(value)  # Uses registered enum type automatically
```

**Why This is Better:**
- ✅ **Root Cause**: psycopg2 now knows about the enum type at the driver level
- ✅ **Type Safety**: Proper type validation happens automatically
- ✅ **Performance**: No SQL casting overhead in queries
- ✅ **Consistency**: All code paths use the same correct approach
- ✅ **Future-Proof**: Works for all enum arrays, not just address_type

### **Fallback Strategy with Warning Logs**

While root cause fixes are preferred, **defensive programming** requires fallbacks for edge cases (e.g., enum registration fails during connection setup). However, **fallbacks must log warnings** to alert developers that the optimal path isn't being used.

```python
def _prepare_value_for_db(value: Any, table: str, column: str, connection=None):
    if table == 'address_info' and column == 'address_type' and isinstance(value, list):
        if _is_enum_registered(connection):
            return psycopg2.extras.Array(value)  # Root cause fix
        else:
            # Fallback: log warning and use SQL casting
            log_warning(
                f"⚠️ Enum type not registered for connection - using SQL casting fallback "
                f"for {table}.{column}. This indicates enum registration failed. "
                f"Performance may be slightly degraded."
            )
            return value  # Will be cast in SQL

def _build_insert_sql(table: str, data: dict, connection=None):
    placeholders = []
    for col in data.keys():
        if table == 'address_info' and col == 'address_type' and not _is_enum_registered(connection):
            placeholders.append('%s::address_type_enum[]')  # Fallback SQL casting
        else:
            placeholders.append('%s')
    # ... rest of function
```

**Fallback Warning Requirements:**
1. **Must log a warning** when fallback is used
2. **Must explain why** the fallback is being used
3. **Must indicate performance impact** if applicable
4. **Must be actionable** - developers should investigate why root cause fix isn't working

### **Decision Framework: Root Cause vs Fallback**

| Scenario | Approach | Rationale |
|----------|----------|-----------|
| Type mismatch in API layer | Fix at API layer (Pydantic validation, type conversion) | Root cause is API accepting wrong types |
| Type mismatch in database layer | Fix at database layer (enum registration, type adapters) | Root cause is driver not knowing about types |
| Validation error | Fix validation logic, not add workarounds | Root cause is missing/invalid validation |
| Performance issue | Fix query/index, not add caching everywhere | Root cause is inefficient query/index |
| Data transformation needed | Fix data source, not transform in every consumer | Root cause is data source format |

### **When Fallbacks Are Acceptable**

Fallbacks are acceptable **only** when:
1. **Root cause fix is in progress** but not yet complete
2. **Edge cases** that are rare and difficult to prevent (e.g., connection pool edge cases)
3. **Temporary workarounds** with clear TODO comments and timeline for removal
4. **Defensive programming** for external dependencies that may fail

**All fallbacks must:**
- ✅ Log warnings when used
- ✅ Have clear documentation explaining why fallback exists
- ✅ Include TODO comments with timeline for removal (if temporary)
- ✅ Be monitored in production to ensure they're not being used frequently

### **Performance Implications**

**Root Cause Fix (Enum Registration):**
- ✅ **Zero overhead**: Enum types registered once per connection
- ✅ **Type validation**: Happens at driver level (fast)
- ✅ **No SQL casting**: Cleaner SQL queries
- ✅ **Better performance**: psycopg2 handles type conversion efficiently

**Fallback (SQL Casting):**
- ⚠️ **Minimal overhead**: PostgreSQL casting is fast but adds query complexity
- ⚠️ **Warning logs**: Should be monitored - frequent warnings indicate root cause fix isn't working
- ⚠️ **Query complexity**: SQL includes casting syntax, slightly harder to read

**Monitoring Fallback Usage:**
- Monitor warning logs for fallback usage frequency
- If fallbacks are used frequently, investigate why root cause fix isn't working
- Set up alerts if fallback usage exceeds threshold (e.g., >1% of operations)

### **Current Enum Usage in Database**

**PostgreSQL Enum Types:**
- ✅ `address_type_enum`: Used for `address_info.address_type` (array type)
  - Values: `'Restaurant'`, `'Entity Billing'`, `'Entity Address'`, `'Customer Home'`, `'Customer Billing'`, `'Customer Employer'`
  - **API Handling**: Properly registered with psycopg2, uses `psycopg2.extras.Array()` for arrays
  - **Validation**: Pydantic validators in `AddressCreateSchema` and `AddressUpdateSchema` ensure valid enum values

**VARCHAR with CHECK Constraints (Not Enums):**
- `status` fields: VARCHAR(20) with CHECK constraints (e.g., `CHECK (status IN ('Active', 'Inactive', 'Cancelled'))`)
  - **Why not enums**: Status values are managed in `status_info` table, allowing dynamic addition of new statuses
  - **API Handling**: Pydantic validators ensure valid status values
  - **Performance**: CHECK constraints provide similar validation to enums at database level

**Recommendation**: 
- ✅ **Keep `address_type_enum` as enum**: Fixed set of values, used in arrays, benefits from enum type safety
- ✅ **Keep `status` as VARCHAR with CHECK**: Dynamic values managed in `status_info` table, allows runtime status addition

### **Performance Analysis: Enum Registration vs SQL Casting**

**Enum Registration (Root Cause Fix):**
```
Performance Impact: NEGLIGIBLE
- Registration: One-time per connection (pooled connections reuse registration)
- Query Time: 0ms overhead (enum types handled at driver level)
- Memory: ~100 bytes per connection for type registration
- CPU: Negligible (type conversion happens in C layer)
```

**SQL Casting (Fallback):**
```
Performance Impact: MINIMAL
- Query Time: ~0.01-0.05ms per query (PostgreSQL casting is fast)
- Query Complexity: Slightly more complex SQL (still optimized by PostgreSQL)
- Memory: No additional memory overhead
- CPU: Minimal (PostgreSQL type casting is efficient)
```

**Real-World Impact:**
- **Enum Registration**: No measurable performance difference in production
- **SQL Casting Fallback**: <0.1ms per query (negligible for typical workloads)
- **Warning Logs**: Minimal overhead (only logged when fallback is used)

**Conclusion**: Both approaches have negligible performance impact. The root cause fix (enum registration) is preferred for:
1. **Type Safety**: Proper type validation at driver level
2. **Code Clarity**: Cleaner SQL queries without casting syntax
3. **Consistency**: All code paths use the same approach
4. **Future-Proofing**: Works for all enum arrays automatically

**Monitoring Recommendations:**
- Track warning log frequency for enum registration failures
- Alert if fallback usage exceeds 1% of address operations
- Monitor connection pool health (enum registration happens per connection)

---

