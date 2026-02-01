"""
Database test fixtures for pytest.

Provides real database connections for integration tests.
Tests use transactions for isolation - changes are rolled back after each test.
"""

import os
import pytest
import psycopg2
import psycopg2.extensions
from typing import Generator
from contextlib import contextmanager


@pytest.fixture(scope="session")
def db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Real database connection for integration tests.
    
    This fixture creates a session-scoped database connection that is reused
    across all tests in the session. The connection is closed after all tests complete.
    
    Uses environment variables for connection parameters:
    - DB_HOST (default: localhost)
    - DB_NAME (default: kitchen_db_dev)
    - DB_USER (default: cdeachaval)
    - DB_PASSWORD (optional)
    - DB_PORT (default: 5432)
    """
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'kitchen_db_dev'),
        user=os.getenv('DB_USER', 'cdeachaval'),
        password=os.getenv('DB_PASSWORD', ''),
        port=int(os.getenv('DB_PORT', '5432'))
    )
    
    # Enable autocommit for DDL operations, but we'll use transactions in tests
    conn.autocommit = False
    
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


def get_tables(conn: psycopg2.extensions.connection, schema: str = 'public') -> set:
    """
    Get all table names in the specified schema.
    
    Args:
        conn: Database connection
        schema: Schema name (default: 'public')
        
    Returns:
        Set of table names
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """, (schema,))
        return {row[0] for row in cur.fetchall()}


def get_table_columns(conn: psycopg2.extensions.connection, table_name: str, schema: str = 'public') -> set:
    """
    Get all column names for a specific table.
    
    Args:
        conn: Database connection
        table_name: Name of the table
        schema: Schema name (default: 'public')
        
    Returns:
        Set of column names
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = %s
              AND table_name = %s
            ORDER BY column_name
        """, (schema, table_name))
        return {row[0] for row in cur.fetchall()}


def get_indexes(conn: psycopg2.extensions.connection, table_name: str = None, schema: str = 'public') -> list:
    """
    Get all indexes in the schema, optionally filtered by table.
    
    Args:
        conn: Database connection
        table_name: Optional table name to filter indexes
        schema: Schema name (default: 'public')
        
    Returns:
        List of index names
    """
    with conn.cursor() as cur:
        if table_name:
            cur.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE schemaname = %s
                  AND tablename = %s
                ORDER BY indexname
            """, (schema, table_name))
        else:
            cur.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE schemaname = %s
                ORDER BY indexname
            """, (schema,))
        return [row[0] for row in cur.fetchall()]


def count_rows(conn: psycopg2.extensions.connection, table_name: str, schema: str = 'public') -> int:
    """
    Count rows in a table.
    
    Args:
        conn: Database connection
        table_name: Name of the table
        schema: Schema name (default: 'public')
        
    Returns:
        Number of rows
    """
    with conn.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{table_name}"')
        return cur.fetchone()[0]


def record_exists(conn: psycopg2.extensions.connection, table_name: str, 
                  column_name: str, value, schema: str = 'public') -> bool:
    """
    Check if a record exists in a table.
    
    Args:
        conn: Database connection
        table_name: Name of the table
        column_name: Name of the column to check
        value: Value to search for
        schema: Schema name (default: 'public')
        
    Returns:
        True if record exists, False otherwise
    """
    with conn.cursor() as cur:
        cur.execute(f'''
            SELECT EXISTS(
                SELECT 1 FROM "{schema}"."{table_name}" 
                WHERE "{column_name}" = %s
            )
        ''', (value,))
        return cur.fetchone()[0]


