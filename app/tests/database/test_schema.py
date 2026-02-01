"""
Schema validation tests.

Tests that all expected tables, columns, and indexes exist in the database schema.
Replaces: app/db/tests/01_schema_exists.sql
"""

import pytest
from app.tests.database.conftest import (
    db_transaction, get_tables, get_table_columns, get_indexes
)
from app.tests.database.test_data.expected_tables import (
    BASE_TABLES, HISTORY_TABLES, CHILD_TABLES, ALL_EXPECTED_TABLES,
    TABLES_WITH_CRITICAL_COLUMNS
)


class TestSchemaTables:
    """Test that all expected tables exist in the schema."""
    
    def test_all_expected_tables_exist(self, db_transaction):
        """Test that all expected tables exist in the database."""
        existing_tables = get_tables(db_transaction)
        
        missing_tables = set(ALL_EXPECTED_TABLES) - existing_tables
        
        assert not missing_tables, (
            f"Missing tables: {', '.join(sorted(missing_tables))}\n"
            f"Total expected: {len(ALL_EXPECTED_TABLES)}, "
            f"Found: {len(existing_tables)}"
        )
    
    def test_base_tables_exist(self, db_transaction):
        """Test that all base/parent tables exist."""
        existing_tables = get_tables(db_transaction)
        
        for table in BASE_TABLES:
            assert table in existing_tables, f"Base table {table} should exist"
    
    def test_history_tables_exist(self, db_transaction):
        """Test that all history tables exist."""
        existing_tables = get_tables(db_transaction)
        
        for table in HISTORY_TABLES:
            assert table in existing_tables, f"History table {table} should exist"
    
    def test_child_tables_exist(self, db_transaction):
        """Test that all child tables exist."""
        existing_tables = get_tables(db_transaction)
        
        for table in CHILD_TABLES:
            assert table in existing_tables, f"Child table {table} should exist"
    
    @pytest.mark.parametrize("table_name", BASE_TABLES + HISTORY_TABLES + CHILD_TABLES)
    def test_table_exists(self, db_transaction, table_name):
        """Parametrized test for individual table existence."""
        existing_tables = get_tables(db_transaction)
        assert table_name in existing_tables, f"Table {table_name} should exist"


class TestSchemaColumns:
    """Test that critical columns exist in tables."""
    
    def test_payment_method_has_address_id(self, db_transaction):
        """Test that payment_method table has address_id column."""
        columns = get_table_columns(db_transaction, 'payment_method')
        assert 'address_id' in columns, "payment_method table should have address_id column"
    
    def test_critical_columns_exist(self, db_transaction):
        """Test that all critical columns exist in their respective tables."""
        for table_name, required_columns in TABLES_WITH_CRITICAL_COLUMNS.items():
            columns = get_table_columns(db_transaction, table_name)
            for column in required_columns:
                assert column in columns, (
                    f"Table {table_name} should have column {column}"
                )


class TestSchemaIndexes:
    """Test that critical indexes exist."""
    
    def test_payment_method_address_id_index_exists(self, db_transaction):
        """Test that payment_method.address_id has an index."""
        indexes = get_indexes(db_transaction, 'payment_method')
        index_names = ' '.join(indexes).lower()
        # Check for index on address_id (could be named differently)
        assert any('address_id' in idx.lower() for idx in indexes) or any(
            'payment_method_address' in idx.lower() for idx in indexes
        ), f"Expected index on payment_method.address_id, found indexes: {indexes}"


