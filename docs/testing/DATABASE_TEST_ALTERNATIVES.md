# Database Testing Alternatives to pgTAP for PostgreSQL 18

## Current Situation

- **Current Setup**: pgTAP extension for SQL-based database tests
- **Issue**: pgTAP not available for PostgreSQL 18 (requires compilation/installation)
- **Existing Tests**: 3 SQL test files in `app/db/tests/` using pgTAP
- **Python Tests**: Already have pytest setup with mocked database connections

---

## Alternative Options

### Option 1: Convert to Python/pytest Tests (Recommended) ⭐

**Pros**:
- ✅ No external dependencies (uses psycopg2, already installed)
- ✅ Works with PostgreSQL 18+ out of the box
- ✅ Integrates with existing pytest infrastructure
- ✅ More flexible than SQL tests (can use Python libraries, better error messages)
- ✅ Easier to debug (Python debugger, better IDE support)
- ✅ Can reuse existing test patterns from `app/tests/`

**Cons**:
- ⚠️ Need to rewrite SQL tests in Python
- ⚠️ Requires real database connection (not just mocks)

**Implementation**:
- Create real database connection fixtures in `conftest.py`
- Convert SQL pgTAP tests to Python pytest tests
- Use psycopg2 to execute queries and assert results

**Example**:
```python
# app/tests/database/test_schema.py
import pytest
import psycopg2
from app.dependencies.database import get_db

@pytest.fixture
def db_connection():
    """Real database connection for schema tests"""
    conn = psycopg2.connect(
        host="localhost",
        database="kitchen",
        user="cdeachaval"
    )
    yield conn
    conn.close()

def test_all_tables_exist(db_connection):
    """Test that all expected tables exist"""
    with db_connection.cursor() as cur:
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = [row[0] for row in cur.fetchall()]
        
        expected_tables = [
            'user_info', 'institution_info', 'payment_method',
            ...
        ]
        
        for table in expected_tables:
            assert table in tables, f"Table {table} should exist"
```

---

### Option 2: Plain SQL with DO Blocks (Simple, No Dependencies)

**Pros**:
- ✅ No external dependencies
- ✅ Works with any PostgreSQL version
- ✅ Minimal changes to existing SQL test structure
- ✅ Can use RAISE EXCEPTION for assertions

**Cons**:
- ⚠️ Less structured than pgTAP (no test counts, no TAP output)
- ⚠️ Manual test organization required
- ⚠️ Harder to integrate with CI/CD

**Implementation**:
- Replace pgTAP functions with DO blocks
- Use RAISE EXCEPTION for test failures
- Use RAISE NOTICE for test results

**Example**:
```sql
-- app/db/tests/01_schema_exists_simple.sql
DO $$
DECLARE
    table_count INTEGER;
    expected_count INTEGER := 50;
BEGIN
    -- Count tables
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_type = 'BASE TABLE';
    
    -- Assert table count
    IF table_count < expected_count THEN
        RAISE EXCEPTION 'Expected at least % tables, found %', expected_count, table_count;
    END IF;
    
    -- Check specific tables exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'payment_method'
    ) THEN
        RAISE EXCEPTION 'Table payment_method does not exist';
    END IF;
    
    RAISE NOTICE '✅ Schema tests passed: % tables found', table_count;
END $$;
```

---

### Option 3: Install pgTAP for PostgreSQL 18

**Pros**:
- ✅ No code changes needed
- ✅ Keep existing test structure

**Cons**:
- ⚠️ Requires compilation from source (not in Homebrew)
- ⚠️ More complex installation process
- ⚠️ Maintenance burden (need to recompile for PostgreSQL updates)

**Installation** (if you want to go this route):
```bash
# pgTAP needs to be compiled from source for PostgreSQL 18
git clone https://github.com/theory/pgtap.git
cd pgtap
make
make install PG_CONFIG=/opt/homebrew/opt/postgresql@18/bin/pg_config
```

---

### Option 4: PGUnit (xUnit-style for PostgreSQL)

**Pros**:
- ✅ xUnit-style testing (familiar pattern)
- ✅ No external dependencies (SQL-only)

**Cons**:
- ⚠️ Still requires extension installation
- ⚠️ Less popular than pgTAP (smaller community)
- ⚠️ Need to learn new framework

**Installation**: Similar to pgTAP (compile from source)

---

### Option 5: Skip SQL Tests, Use Python Tests Only

**Pros**:
- ✅ Simplest approach
- ✅ Already have pytest infrastructure
- ✅ No SQL test maintenance

**Cons**:
- ⚠️ Lose schema-level SQL tests
- ⚠️ Different testing approach (application-level vs schema-level)

**Note**: This might be acceptable if you have good Python integration tests that cover schema functionality.

---

## Recommendation: Option 1 (Python/pytest Tests)

**Why**: 
1. Already have pytest infrastructure
2. No external dependencies
3. More maintainable long-term
4. Better developer experience
5. Works with PostgreSQL 18+ out of the box

---

## Migration Plan (if choosing Option 1)

### Step 1: Create Database Connection Fixtures

**File**: `app/tests/conftest.py`

```python
import pytest
import psycopg2
from typing import Generator

@pytest.fixture(scope="session")
def test_db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Real database connection for integration tests"""
    conn = psycopg2.connect(
        host="localhost",
        database="kitchen",
        user="cdeachaval",
        autocommit=False
    )
    yield conn
    conn.close()

@pytest.fixture
def db_transaction(test_db_connection):
    """Database transaction that rolls back after test"""
    test_db_connection.rollback()  # Start fresh
    yield test_db_connection
    test_db_connection.rollback()  # Rollback after test
```

### Step 2: Convert Schema Tests

**File**: `app/tests/database/test_schema_exists.py`

```python
import pytest
from app.tests.conftest import db_transaction

class TestSchemaExists:
    """Test that all expected tables exist in the schema"""
    
    EXPECTED_TABLES = [
        # Base tables
        'user_info', 'institution_info', 'payment_method',
        'restaurant_info', 'product_info', 'plan_info',
        # History tables
        'user_history', 'institution_history', 'restaurant_history',
        # Child tables
        'vianda_selection',
        # ... etc
    ]
    
    def test_all_base_tables_exist(self, db_transaction):
        """Test that all base tables exist"""
        with db_transaction.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            existing_tables = {row[0] for row in cur.fetchall()}
            
            for table in self.EXPECTED_TABLES:
                assert table in existing_tables, f"Table {table} should exist"
    
    def test_payment_method_has_address_id(self, db_transaction):
        """Test that payment_method table has address_id column"""
        with db_transaction.cursor() as cur:
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public'
                  AND table_name = 'payment_method'
                  AND column_name = 'address_id'
            """)
            result = cur.fetchone()
            assert result is not None, "payment_method should have address_id column"
```

### Step 3: Convert Seed Tests

**File**: `app/tests/database/test_initial_seed.py`

```python
import pytest
from app.tests.conftest import db_transaction
from uuid import UUID

class TestInitialSeed:
    """Test initial seed data"""
    
    def test_admin_user_seeded(self, db_transaction):
        """Test that admin user is seeded"""
        with db_transaction.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) 
                FROM user_info 
                WHERE user_id = '11111111-1111-1111-1111-111111111111'
            """)
            count = cur.fetchone()[0]
            assert count == 1, "Admin user should be seeded"
    
    def test_institution_count(self, db_transaction):
        """Test that correct number of institutions are seeded"""
        with db_transaction.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM institution_info")
            count = cur.fetchone()[0]
            assert count >= 2, "Should have at least 2 seeded institutions"
```

### Step 4: Update Test Runner

**File**: `pytest.ini` (already exists)

Add database test marker:
```ini
markers =
    database: Tests that require database
    database_schema: Schema-level database tests
```

Run database tests separately:
```bash
# Run all tests
pytest

# Run only database schema tests
pytest -m database_schema

# Run all database tests
pytest -m database
```

---

## Quick Start: Option 2 (Simple SQL DO Blocks)

If you want a quick solution with minimal changes:

1. Replace pgTAP functions with DO blocks
2. Use RAISE EXCEPTION for failures
3. Keep existing SQL test structure

**Example conversion**:
```sql
-- Before (pgTAP):
SELECT has_table('public', 'payment_method', 'payment_method exists');

-- After (DO block):
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'payment_method'
    ) THEN
        RAISE EXCEPTION 'Table payment_method does not exist';
    END IF;
END $$;
```

---

## Comparison Table

| Option | Setup Complexity | Maintenance | Flexibility | PostgreSQL 18 Support |
|--------|-----------------|-------------|-------------|---------------------|
| **Python/pytest** | Medium | Low | High | ✅ Yes |
| **SQL DO Blocks** | Low | Medium | Medium | ✅ Yes |
| **Install pgTAP** | High | High | Low | ⚠️ Manual compile |
| **PGUnit** | High | High | Medium | ⚠️ Manual compile |
| **Skip SQL tests** | None | Low | N/A | ✅ Yes |

---

## Recommendation Summary

**Best Choice**: **Option 1 (Python/pytest tests)**
- Most maintainable long-term
- No external dependencies
- Better developer experience
- Aligns with existing test infrastructure

**Quick Fix**: **Option 2 (SQL DO blocks)**
- Minimal code changes
- Works immediately
- Good for temporary solution

**If you really need pgTAP**: **Option 3**
- Compile from source
- More maintenance overhead
- But keeps existing test structure


