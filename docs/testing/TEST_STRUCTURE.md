# Test Structure and Organization

## Overview

This document describes the test folder structure and testing logic for the FastAPI application. Tests are organized by layer and responsibility to ensure maintainability and clear separation of concerns.

## Test Directory Structure

```
app/tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # Shared pytest fixtures and configuration
├── services/                   # Service-layer unit tests
│   ├── __init__.py
│   ├── test_address_service.py
│   ├── test_discretionary_service.py
│   └── ...
├── auth/                       # Authentication and authorization tests
│   ├── __init__.py
│   ├── test_auth_dependencies.py
│   └── test_permissions.py
└── routes/                     # Route-level integration tests (if needed)
    ├── __init__.py
    └── test_route_permissions.py
```

## Testing Layers

### 1. Unit Tests (`app/tests/services/`)

**Purpose**: Test individual service functions in isolation with mocked dependencies.

**Scope**:
- Business logic in service modules
- Data transformation and validation
- Error handling and edge cases
- Pure functions and calculations

**Characteristics**:
- Fast execution (milliseconds)
- No database connections (mocked)
- No external API calls (mocked)
- Independent and repeatable
- Test one concept per test function

**Example**:
```python
# app/tests/services/test_discretionary_service.py
def test_create_discretionary_request_success(discretionary_service, mock_db, sample_admin_user):
    """Test successful discretionary request creation"""
    # Arrange
    request_data = {"user_id": uuid4(), "amount": Decimal("10.00")}
    
    # Act
    result = discretionary_service.create_discretionary_request(request_data, sample_admin_user, mock_db)
    
    # Assert
    assert result is not None
    assert result.status == "Pending"
```

### 2. Authentication & Authorization Tests (`app/tests/auth/`)

**Purpose**: Test permission checks, role validation, and access control logic.

**Scope**:
- Dependency functions (`get_employee_user()`, `get_super_admin_user()`, etc.)
- Permission validation logic
- Role-based access control (RBAC)
- Institution scoping

**Characteristics**:
- Test dependency functions directly
- Mock JWT payloads and user data
- Verify 403 errors for unauthorized access
- Test positive and negative cases

**Example**:
```python
# app/tests/auth/test_auth_dependencies.py
def test_get_employee_user_allows_employee(mock_employee_user):
    """Test that get_employee_user() allows Employee role_type"""
    # Act
    result = get_employee_user(mock_employee_user)
    
    # Assert
    assert result == mock_employee_user

def test_get_employee_user_rejects_supplier(mock_supplier_user):
    """Test that get_employee_user() rejects Supplier role_type"""
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        get_employee_user(mock_supplier_user)
    assert exc_info.value.status_code == 403
```

### 3. Route-Level Integration Tests (`app/tests/routes/` - Optional)

**Purpose**: Test API endpoints with full request/response cycle.

**Scope**:
- End-to-end permission enforcement
- HTTP status codes and error responses
- Request/response schema validation
- Route-level business logic

**Characteristics**:
- Use FastAPI TestClient
- May use in-memory database or test database
- Slower than unit tests
- Test complete request/response flow

**Note**: Route-level integration tests are optional. Most permission testing can be done at the dependency level (unit tests) and via Postman (manual/integration testing).

## Test File Naming Conventions

1. **Service Tests**: `test_<service_name>_service.py`
   - Example: `test_discretionary_service.py`

2. **Auth Tests**: `test_<auth_component>_<specificity>.py`
   - Example: `test_auth_dependencies.py`, `test_permissions.py`

3. **Route Tests**: `test_<route_group>_<specificity>.py`
   - Example: `test_route_permissions.py`

## Test Organization Principles

### 1. Group by Responsibility

Tests are organized by **what they test** (services, auth, routes), not by what modules they import.

- ✅ **Good**: `app/tests/auth/test_auth_dependencies.py` (tests auth dependencies)
- ❌ **Bad**: `app/tests/auth/test_auth_routes.py` (routes aren't auth logic)

### 2. Shared Fixtures in `conftest.py`

Common fixtures used across multiple test files should be in `app/tests/conftest.py`:
- Database mocks
- Sample user data (Employee, Supplier, Customer, Super Admin)
- Service instances

### 3. File-Specific Fixtures

Fixtures used only in one test file should be defined in that file using `@pytest.fixture`.

### 4. Test Class Organization

Use test classes to group related tests when it makes sense:

```python
class TestEmployeeUserAccess:
    """Test cases for get_employee_user() dependency"""
    
    def test_allows_employee(self):
        ...
    
    def test_rejects_supplier(self):
        ...
    
    def test_rejects_customer(self):
        ...
```

## Testing Strategy by Layer

### Services (`app/services/*`)
- ✅ **Unit tests required** - Test business logic in isolation
- ✅ **Mock dependencies** - Database, external APIs, other services
- ✅ **Fast execution** - Should complete in milliseconds

### Auth Dependencies (`app/auth/dependencies.py`)
- ✅ **Unit tests required** - Test permission checks directly
- ✅ **Mock JWT payloads** - Test with different role types and names
- ✅ **Verify error responses** - Test 403 errors for unauthorized access

### Routes (`app/routes/*`)
- ⚠️ **Integration tests optional** - Most testing via Postman
- ⚠️ **Use TestClient if needed** - For complex route logic
- ✅ **Postman collections** - Primary method for route testing

### Security (`app/security/*`)
- ✅ **Unit tests recommended** - Test scoping logic
- ✅ **Mock InstitutionScope** - Test with different user contexts

## Fixture Conventions

### User Fixtures

Standard user fixtures should be available in `conftest.py`:

```python
@pytest.fixture
def sample_employee_user():
    """Employee user (role_type='Employee')"""
    return {
        "user_id": uuid4(),
        "role_type": "Employee",
        "role_name": "Admin",
        "institution_id": uuid4()
    }

@pytest.fixture
def sample_super_admin_user():
    """Super Admin user (role_type='Employee', role_name='Super Admin')"""
    return {
        "user_id": uuid4(),
        "role_type": "Employee",
        "role_name": "Super Admin",
        "institution_id": uuid4()
    }

@pytest.fixture
def sample_supplier_user():
    """Supplier user (role_type='Supplier')"""
    return {
        "user_id": uuid4(),
        "role_type": "Supplier",
        "role_name": "Admin",
        "institution_id": uuid4()
    }

@pytest.fixture
def sample_customer_user():
    """Customer user (role_type='Customer')"""
    return {
        "user_id": uuid4(),
        "role_type": "Customer",
        "role_name": "Comensal",
        "institution_id": uuid4()
    }
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test File
```bash
pytest app/tests/auth/test_auth_dependencies.py
```

### Run Specific Test Class
```bash
pytest app/tests/auth/test_auth_dependencies.py::TestEmployeeUserAccess
```

### Run Specific Test Function
```bash
pytest app/tests/auth/test_auth_dependencies.py::TestEmployeeUserAccess::test_allows_employee
```

### Run with Coverage
```bash
pytest --cov=app --cov-report=html
```

## Best Practices

1. **One concept per test**: Each test should verify a single behavior
2. **Descriptive names**: Test names should clearly describe what is being tested
3. **Arrange-Act-Assert**: Structure tests with clear setup, execution, and verification
4. **Mock external dependencies**: Don't rely on real database or external APIs
5. **Test both positive and negative cases**: Verify success and failure paths
6. **Keep tests fast**: Unit tests should complete quickly
7. **Independent tests**: Tests should not depend on each other
8. **Repeatable**: Tests should work consistently across environments

## Future Considerations

- **E2E Tests**: May add `app/tests/e2e/` for full-stack integration tests if needed
- **Performance Tests**: May add `app/tests/performance/` for load testing
- **Contract Tests**: May add API contract tests for external integrations

