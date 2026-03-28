"""
Database test fixtures for pytest.

Provides real database connections for integration tests.
Tests use transactions for isolation - changes are rolled back after each test.

Session-scoped cleanup archives test-created records when tests use commit=True,
preventing pollution of the dev database (e.g. plans, users, subscriptions).
"""

import os

# Ensure DB env vars for tests that use app services (e.g. market_service via pool).
# db_pool uses os.getenv('DB_NAME') without default; None causes "database cdeachaval" error.
# Same database name as Cloud SQL (kitchen); environment is isolated by instance / GCP project.
os.environ.setdefault("DB_NAME", "kitchen")
os.environ.setdefault("DB_USER", "cdeachaval")
import pytest
import psycopg2
from app.utils.db_pool import build_psycopg2_dsn
from app.tests.database.test_data.expected_seed_data import (
    SEED_SUPERADMIN_USER_ID,
    SEED_SYSTEM_BOT_USER_ID,
)
import psycopg2.extensions
from typing import Generator
from contextlib import contextmanager


def _cleanup_allowed_for_session() -> bool:
    """
    Run destructive-ish archive cleanup only for local dev against database `kitchen`.
    Remote hosts need PYTEST_DB_CLEANUP=1 (e.g. CI with DB_HOST=postgres).
    """
    if os.getenv("DB_NAME", "kitchen") != "kitchen":
        return False
    if os.getenv("PYTEST_DB_CLEANUP", "").lower() in ("1", "true", "yes"):
        return True
    host = (os.getenv("DB_HOST") or "localhost").strip().lower()
    return host in ("localhost", "127.0.0.1", "::1", "")


def _run_cleanup_test_data(conn: psycopg2.extensions.connection) -> None:
    """
    Archive test-created records when cleanup is allowed (see _cleanup_allowed_for_session).
    Uses soft-delete (is_archived, status) to preserve FK integrity.
    """
    if not _cleanup_allowed_for_session():
        return

    seed_user_ids = (str(SEED_SUPERADMIN_USER_ID), str(SEED_SYSTEM_BOT_USER_ID))

    with conn.cursor() as cur:
        # 1. Archive client_bill_info for non-seed users
        cur.execute("""
            UPDATE client_bill_info SET is_archived = TRUE, status = 'Inactive'::status_enum
            WHERE user_id NOT IN %s
        """, (seed_user_ids,))
        # 2. Archive subscription_info for non-seed users
        cur.execute("""
            UPDATE subscription_info SET is_archived = TRUE, status = 'Inactive'::status_enum
            WHERE user_id NOT IN %s
        """, (seed_user_ids,))
        # 3. Archive plan_info by test plan names
        cur.execute("""
            UPDATE plan_info SET is_archived = TRUE, status = 'Inactive'::status_enum
            WHERE name IN ('Test Plan', 'Cron Plan', 'Plan With Cap', 'Entry Level', 'Plan', 'Zero Credit Plan')
        """)
        # 4. Archive address_info for non-seed users (future-proofing)
        cur.execute("""
            UPDATE address_info SET is_archived = TRUE, status = 'Inactive'::status_enum
            WHERE user_id IS NOT NULL AND user_id NOT IN %s
        """, (seed_user_ids,))
        # 5. Archive payment_method for non-seed users
        cur.execute("""
            UPDATE payment_method SET is_archived = TRUE, status = 'Inactive'::status_enum
            WHERE user_id NOT IN %s
        """, (seed_user_ids,))
        # 6. Archive all users except seed (superadmin, system bot)
        cur.execute("""
            UPDATE user_info SET is_archived = TRUE, status = 'Inactive'::status_enum
            WHERE user_id NOT IN %s
        """, (seed_user_ids,))
        # 7. Archive test institutions (per plan: name LIKE 'Test %')
        cur.execute("""
            UPDATE institution_info SET is_archived = TRUE, status = 'Inactive'::status_enum
            WHERE name LIKE 'Test %%'
        """)
        # 8. Archive non-seed credit currencies (seed has USD, ARS, PEN, CLP, MXN, BRL)
        seed_credit_currency_ids = (
            '55555555-5555-5555-5555-555555555555',  # USD
            '66666666-6666-6666-6666-666666666601',  # ARS
            '66666666-6666-6666-6666-666666666602',  # PEN
            '66666666-6666-6666-6666-666666666603',  # CLP
            '66666666-6666-6666-6666-666666666604',  # MXN
            '66666666-6666-6666-6666-666666666605',  # BRL
        )
        cur.execute("""
            UPDATE credit_currency_info SET is_archived = TRUE, status = 'Inactive'::status_enum
            WHERE credit_currency_id NOT IN %s
        """, (seed_credit_currency_ids,))
    conn.commit()


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data(db_connection: psycopg2.extensions.connection) -> Generator[None, None, None]:
    """
    Session-scoped fixture that archives test-created records before and after database tests.
    Runs only when cleanup is allowed (local `kitchen` or PYTEST_DB_CLEANUP=1). Prevents dev DB pollution from tests that use commit=True.
    - Start: cleans leftover data from previous runs so test_seed and others see a clean DB.
    - End: cleans data from this run for the next session.
    """
    try:
        _run_cleanup_test_data(db_connection)
    except Exception:
        pass  # Non-blocking; avoid masking test failures
    yield
    try:
        _run_cleanup_test_data(db_connection)
    except Exception:
        pass  # Non-blocking; avoid masking test failures


@pytest.fixture(scope="session")
def db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Real database connection for integration tests.
    
    This fixture creates a session-scoped database connection that is reused
    across all tests in the session. The connection is closed after all tests complete.
    
    Uses environment variables for connection parameters:
    - DB_HOST (default: localhost)
    - DB_NAME (default: kitchen)
    - DB_USER (default: cdeachaval)
    - DB_PASSWORD (optional)
    - DB_PORT (default: 5432)
    - DB_SSLMODE (optional; non-local hosts default to require for Cloud SQL TLS)
    """
    # libpq URI with sslmode= in query (reliable for Cloud SQL); see build_psycopg2_dsn().
    conn = psycopg2.connect(build_psycopg2_dsn())
    
    # Enable autocommit for DDL operations, but we'll use transactions in tests
    conn.autocommit = False

    # Set search_path so bare table names resolve across app schemas
    with conn.cursor() as _cur:
        _cur.execute("SET search_path = core, ops, customer, billing, audit, public")

    yield conn

    conn.close()


@pytest.fixture
def db_transaction(db_connection: psycopg2.extensions.connection):
    """
    Database transaction that rolls back after test.
    
    This fixture ensures test isolation by rolling back any changes made
    during the test. Each test gets a fresh transaction state.
    
    Usage:
        def test_something(db_transaction):
            with db_transaction.cursor() as cur:
                cur.execute("SELECT * FROM user_info")
                # ... test code ...
            # Transaction is automatically rolled back after test
    """
    # Start fresh - rollback any pending changes
    db_connection.rollback()
    
    yield db_connection
    
    # Rollback after test to ensure isolation
    db_connection.rollback()


APP_SCHEMAS = ('core', 'ops', 'customer', 'billing', 'audit')


def get_tables(conn: psycopg2.extensions.connection, schema: str = None) -> set:
    """
    Get all table names across all app schemas (or a specific schema if provided).

    Args:
        conn: Database connection
        schema: Optional schema name; defaults to all app schemas

    Returns:
        Set of table names
    """
    with conn.cursor() as cur:
        if schema:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """, (schema,))
        else:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = ANY(%s)
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """, (list(APP_SCHEMAS),))
        return {row[0] for row in cur.fetchall()}


def get_table_columns(conn: psycopg2.extensions.connection, table_name: str, schema: str = None) -> set:
    """
    Get all column names for a specific table across all app schemas (or a specific schema).

    Args:
        conn: Database connection
        table_name: Name of the table
        schema: Optional schema name; defaults to all app schemas

    Returns:
        Set of column names
    """
    with conn.cursor() as cur:
        if schema:
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = %s
                ORDER BY column_name
            """, (schema, table_name))
        else:
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = ANY(%s)
                  AND table_name = %s
                ORDER BY column_name
            """, (list(APP_SCHEMAS), table_name))
        return {row[0] for row in cur.fetchall()}


def get_indexes(conn: psycopg2.extensions.connection, table_name: str = None, schema: str = None) -> list:
    """
    Get all indexes across app schemas, optionally filtered by table (or a specific schema).

    Args:
        conn: Database connection
        table_name: Optional table name to filter indexes
        schema: Optional schema name; defaults to all app schemas

    Returns:
        List of index names
    """
    with conn.cursor() as cur:
        if schema:
            if table_name:
                cur.execute("""
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname = %s AND tablename = %s
                    ORDER BY indexname
                """, (schema, table_name))
            else:
                cur.execute("""
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname = %s
                    ORDER BY indexname
                """, (schema,))
        else:
            if table_name:
                cur.execute("""
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname = ANY(%s) AND tablename = %s
                    ORDER BY indexname
                """, (list(APP_SCHEMAS), table_name))
            else:
                cur.execute("""
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname = ANY(%s)
                    ORDER BY indexname
                """, (list(APP_SCHEMAS),))
        return [row[0] for row in cur.fetchall()]


def count_rows(conn: psycopg2.extensions.connection, table_name: str, schema: str = None) -> int:
    """
    Count rows in a table. Bare name resolves via search_path across app schemas.

    Args:
        conn: Database connection
        table_name: Name of the table
        schema: Optional explicit schema; omit to rely on search_path

    Returns:
        Number of rows
    """
    with conn.cursor() as cur:
        if schema:
            cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{table_name}"')
        else:
            cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        return cur.fetchone()[0]


def count_non_archived_rows(
    conn: psycopg2.extensions.connection, table_name: str, schema: str = None
) -> int:
    """
    Count rows in a table where is_archived = FALSE.

    Args:
        conn: Database connection
        table_name: Name of the table (must have is_archived column)
        schema: Optional explicit schema; omit to rely on search_path

    Returns:
        Number of non-archived rows
    """
    with conn.cursor() as cur:
        if schema:
            cur.execute(
                f'SELECT COUNT(*) FROM "{schema}"."{table_name}" WHERE is_archived = FALSE'
            )
        else:
            cur.execute(f'SELECT COUNT(*) FROM "{table_name}" WHERE is_archived = FALSE')
        return cur.fetchone()[0]


def record_exists(conn: psycopg2.extensions.connection, table_name: str,
                  column_name: str, value, schema: str = None) -> bool:
    """
    Check if a record exists in a table. Bare name resolves via search_path.

    Args:
        conn: Database connection
        table_name: Name of the table
        column_name: Name of the column to check
        value: Value to search for
        schema: Optional explicit schema; omit to rely on search_path

    Returns:
        True if record exists, False otherwise
    """
    with conn.cursor() as cur:
        if schema:
            cur.execute(f'''
                SELECT EXISTS(
                    SELECT 1 FROM "{schema}"."{table_name}"
                    WHERE "{column_name}" = %s
                )
            ''', (value,))
        else:
            cur.execute(f'''
                SELECT EXISTS(
                    SELECT 1 FROM "{table_name}"
                    WHERE "{column_name}" = %s
                )
            ''', (value,))
        return cur.fetchone()[0]


