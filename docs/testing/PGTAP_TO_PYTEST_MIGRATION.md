# Migration Plan: pgTAP to Python/pytest Tests

## Overview

This document outlines the plan to migrate from pgTAP SQL-based tests to Python/pytest tests using real database connections. This migration will:

- ✅ Work with PostgreSQL 18+ without external dependencies
- ✅ Integrate with existing pytest infrastructure
- ✅ Use real database connections (not mocks)
- ✅ Keep tests maintainable and data-driven (avoid hardcoded values)
- ✅ Provide better debugging and IDE support

---

## Current State

### Existing pgTAP Tests
1. **`app/db/tests/01_schema_exists.sql`** (50 tests)
   - Tests that all expected tables exist in the schema
   - Covers: base tables, history tables, child tables

2. **`app/db/tests/02_initial_seed.sql`** (6 tests)
   - Tests seed data counts and specific record existence
   - Uses hardcoded UUIDs (e.g., `11111111-1111-1111-1111-111111111111`)

3. **`app/db/tests/03_supplier_onboarding.sql`** (50 tests)
   - Complex integration test for supplier onboarding flow
   - Tests CRUD operations and history table triggers
   - Many hardcoded test values

### Current Issues
- ❌ pgTAP not available for PostgreSQL 18+ (requires compilation)
- ❌ Tests use `prove` (Perl test runner) - separate from pytest
- ❌ Hardcoded UUIDs and test data in SQL files
- ❌ Difficult to debug and maintain
- ❌ No integration with existing pytest test suite

---

## Target State

### New pytest Test Structure

```
app/tests/database/
├── __init__.py
├── conftest.py                    # Database fixtures
├── test_data/
│   ├── __init__.py
│   ├── expected_tables.py        # Data-driven table lists
│   ├── expected_seed_data.py     # Seed data expectations
│   └── test_factories.py         # Test data factories
├── test_schema.py                # Schema existence tests (replaces 01_schema_exists.sql)
├── test_seed.py                  # Seed data tests (replaces 02_initial_seed.sql)
└── test_integration.py           # Integration tests (replaces 03_supplier_onboarding.sql)
```

### Key Principles
1. **Data-Driven**: Table lists, expected counts, etc. in separate data files
2. **Real Connections**: Use actual database connections (not mocks)
3. **Clean Fixtures**: Reusable fixtures for database setup/teardown
4. **Maintainable**: Easy to add new tests as schema evolves
5. **Fast**: Use transactions for test isolation (rollback after each test)

---

## Implementation Plan

### Phase 1: Infrastructure Setup ✅

1. **Create database test fixtures** (`app/tests/database/conftest.py`)
   - Real database connection fixture
   - Transaction-based isolation (rollback after tests)
   - Database connection using environment variables

2. **Create data files** (`app/tests/database/test_data/`)
   - `expected_tables.py`: Lists of expected tables by category
   - `expected_seed_data.py`: Seed data expectations (counts, UUIDs)
   - `test_factories.py`: Factory functions for test data creation

### Phase 2: Schema Tests ✅

3. **Create `test_schema.py`** (replaces `01_schema_exists.sql`)
   - Test all expected tables exist
   - Use data-driven table lists
   - Test critical columns exist (e.g., `payment_method.address_id`)
   - Test indexes exist

### Phase 3: Seed Tests ✅

4. **Create `test_seed.py`** (replaces `02_initial_seed.sql`)
   - Test seed data counts
   - Test specific seed records exist (using data files for UUIDs)
   - Test seed data integrity

### Phase 4: Integration Tests ✅

5. **Create `test_integration.py`** (replaces `03_supplier_onboarding.sql`)
   - Test supplier onboarding flow
   - Use factories for test data (not hardcoded values)
   - Test CRUD operations and history triggers
   - Use transactions for isolation

### Phase 5: Build Script Update ✅

6. **Update `app/db/build_kitchen_db_dev.sh`**
   - Replace `prove` with `pytest`
   - Run database tests after schema rebuild
   - Keep schema rebuild and seed steps

### Phase 6: Cleanup ✅

7. **Remove old pgTAP files**
   - Delete `app/db/tests/*.sql`
   - Update documentation
   - Remove pgTAP extension from schema.sql (if not needed)

---

## Test Data Strategy

### Avoid Hardcoded Values

**❌ Bad (pgTAP style)**:
```sql
SELECT ok(
  EXISTS(SELECT 1 FROM user_info WHERE user_id = '11111111-1111-1111-1111-111111111111'),
  'Admin user seeded'
);
```

**✅ Good (pytest style)**:
```python
# In test_data/expected_seed_data.py
SEED_ADMIN_USER_ID = UUID('11111111-1111-1111-1111-111111111111')

# In test_seed.py
def test_admin_user_seeded(db_transaction, seed_data):
    assert seed_data.admin_user_exists(db_transaction, SEED_ADMIN_USER_ID)
```

### Data-Driven Tables

**✅ Good**:
```python
# test_data/expected_tables.py
BASE_TABLES = [
    'user_info', 'institution_info', 'payment_method',
    'restaurant_info', 'product_info', ...
]

HISTORY_TABLES = [
    'user_history', 'institution_history', ...
]

# test_schema.py
def test_base_tables_exist(db_transaction, expected_tables):
    existing = get_tables(db_transaction)
    for table in expected_tables.BASE_TABLES:
        assert table in existing, f"Table {table} should exist"
```

---

## Database Fixture Design

### Connection Fixture
```python
@pytest.fixture(scope="session")
def db_connection():
    """Real database connection for integration tests"""
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'kitchen_db_dev'),
        user=os.getenv('DB_USER', 'cdeachaval')
    )
    yield conn
    conn.close()
```

### Transaction Fixture (for test isolation)
```python
@pytest.fixture
def db_transaction(db_connection):
    """Database transaction that rolls back after test"""
    db_connection.rollback()  # Start fresh
    yield db_connection
    db_connection.rollback()  # Rollback after test
```

---

## Migration Checklist

- [x] Create migration plan document
- [ ] Create database test fixtures (`conftest.py`)
- [ ] Create test data modules (`test_data/`)
- [ ] Implement `test_schema.py`
- [ ] Implement `test_seed.py`
- [ ] Implement `test_integration.py`
- [ ] Update `build_kitchen_db_dev.sh`
- [ ] Test new pytest suite
- [ ] Remove old pgTAP files
- [ ] Update documentation

---

## Running Tests

### All Database Tests
```bash
pytest app/tests/database/
```

### Specific Test File
```bash
pytest app/tests/database/test_schema.py
```

### With Coverage
```bash
pytest app/tests/database/ --cov=app --cov-report=term-missing
```

### In Build Script
```bash
# In build_kitchen_db_dev.sh
pytest app/tests/database/ -v
```

---

## Benefits of Migration

1. **No External Dependencies**: Works with PostgreSQL 18+ out of the box
2. **Better Integration**: Uses same test framework as application tests
3. **Easier Debugging**: Python debugger, IDE support, better error messages
4. **More Maintainable**: Data-driven, easier to extend
5. **Better Test Organization**: Modular, reusable fixtures and utilities
6. **CI/CD Ready**: Standard pytest output, integrates with test runners


