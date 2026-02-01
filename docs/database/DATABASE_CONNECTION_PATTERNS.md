# Database Connection Patterns

This document outlines the standardized patterns for database connections and function calls throughout the Kitchen application.

## Overview

The application uses two distinct patterns for database operations:

1. **Database Utility Functions** - Low-level database operations
2. **Business Service Functions** - High-level business logic with database access

## Pattern 1: Database Utility Functions

### Function Signatures

```python
# app/utils/db.py
def db_read(query: str, values: tuple = None, connection=None, fetch_one: bool = False)
def db_insert(table: str, data: dict, connection=None)
def db_update(table: str, data: dict, where: dict, connection=None)
```

### Usage Pattern

**Always use keyword argument `connection=db`:**

```python
# ✅ CORRECT
result = db_read(query, (param1, param2), connection=db, fetch_one=True)
record_id = db_insert("user_info", user_data, connection=db)
success = db_update("user_info", update_data, where_clause, connection=db)

# ❌ INCORRECT - Don't use positional argument
result = db_read(query, (param1, param2), db, fetch_one=True)
record_id = db_insert("user_info", user_data, db)
success = db_update("user_info", update_data, where_clause, db)
```

### When to Use

- Direct database queries
- CRUD operations in service layer
- Database utility functions
- Custom queries with complex logic

## Pattern 2: Business Service Functions

### Function Signatures

```python
# app/services/entity_service.py
def create_user_with_validation(user_data: dict, db: psycopg2.extensions.connection) -> UserDTO
def get_user_by_username(username: str, db: psycopg2.extensions.connection) -> Optional[UserDTO]
def get_user_by_id(user_id: UUID, db: psycopg2.extensions.connection) -> Optional[UserDTO]

# app/services/crud_service.py
def get_by_id(self, record_id: UUID, db: psycopg2.extensions.connection) -> Optional[T]
def get_all(self, db: psycopg2.extensions.connection) -> List[T]
def create(self, data: dict, db: psycopg2.extensions.connection) -> Optional[T]
```

### Usage Pattern

**Always use positional argument `db`:**

```python
# ✅ CORRECT
user = create_user_with_validation(user_data, db)
user = get_user_by_username(username, db)
user = crud_service.get_by_id(user_id, db)
users = crud_service.get_all(db)

# ❌ INCORRECT - Don't use keyword argument
user = create_user_with_validation(user_data, connection=db)
user = get_user_by_username(username, connection=db)
user = crud_service.get_by_id(user_id, connection=db)
```

### When to Use

- Business logic functions
- Service layer operations
- CRUD service calls
- Entity-specific operations

## Route Handler Pattern

### Standard Route Handler Template

```python
@router.post("/", response_model=ResponseSchema, status_code=201)
def create_entity(
    entity: CreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a new entity"""
    def _create_entity_with_validation():
        entity_data = entity.dict()
        return entity_service.create_entity_with_validation(entity_data, db)
    
    return handle_business_operation(
        _create_entity_with_validation,
        "entity creation with validation",
        "Entity created successfully"
    )
```

### Key Points

- **Route handlers** receive `db` as a dependency
- **Pass `db` as positional argument** to business service functions
- **Use `connection=db`** when calling database utility functions within business logic

## Examples

### Example 1: Service Function Using Database Utils

```python
def create_user_with_validation(user_data: dict, db: psycopg2.extensions.connection) -> UserDTO:
    """Create user with business validation"""
    
    # Check if username exists - using database utility
    existing_user = db_read(
        "SELECT * FROM user_info WHERE username = %s AND is_archived = FALSE",
        (user_data["username"],),
        connection=db,
        fetch_one=True
    )
    
    if existing_user:
        raise HTTPException(status_code=409, detail="Username already exists")
    
    # Create user - using database utility
    user_id = db_insert("user_info", user_data, connection=db)
    
    # Return user DTO
    return get_user_by_id(user_id, db)  # Using business service function
```

### Example 2: CRUD Service Implementation

```python
class CRUDService:
    def create(self, data: dict, db: psycopg2.extensions.connection) -> Optional[T]:
        """Create a new record"""
        try:
            # Using database utility function
            record_id = db_insert(self.table_name, data, connection=db)
            
            # Using business service function
            return self.get_by_id(record_id, db)
            
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error creating {self.table_name}: {e}")
            return None
```

## Migration Guide

### If You Find Incorrect Usage

1. **Identify the function type:**
   - Database utility function → Use `connection=db`
   - Business service function → Use `db` (positional)

2. **Check function signature:**
   - `def function(..., connection=None)` → Use `connection=db`
   - `def function(..., db: psycopg2.extensions.connection)` → Use `db`

3. **Apply the correct pattern:**
   ```python
   # Database utility
   result = db_read(query, values, connection=db)
   
   # Business service
   result = business_function(data, db)
   ```

## Best Practices

1. **Consistency**: Always use the same pattern for the same function type
2. **Documentation**: Document function signatures clearly
3. **Testing**: Test both patterns to ensure they work correctly
4. **Code Review**: Check for correct parameter usage during code reviews

## Common Mistakes to Avoid

1. **Mixing patterns**: Don't use `connection=db` with business service functions
2. **Inconsistent naming**: Don't change parameter names without updating all callers
3. **Missing parameters**: Don't forget to pass the database connection
4. **Wrong argument type**: Don't pass positional arguments where keyword arguments are expected

## Related Documentation

- [Database Schema](schema.sql)
- [Database Rebuild Guide](DATABASE_REBUILD_PERSISTENCE.md)
- [Performance Monitoring](../performance/PERFORMANCE_MONITORING.md)
