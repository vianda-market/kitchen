# app/tests/services/test_db_batch_delete.py
"""
Unit tests for db_batch_delete function.

Tests cover:
- Hard delete (DELETE FROM)
- Soft delete (UPDATE is_archived)
- Soft delete with additional fields (modified_by, modified_date)
- Validation (empty list, invalid data)
- Transaction atomicity (rollback on error)
- Connection management
"""

from datetime import datetime
from unittest.mock import Mock, patch
from uuid import UUID

import psycopg2
import pytest

from app.utils.db import _build_delete_sql, db_batch_delete, db_delete


@pytest.fixture(scope="module")
def db_conn():
    """Real psycopg2 connection used only to render sql.Composed objects via as_string().

    Tests that require this fixture are automatically skipped when no local PostgreSQL
    instance is available (e.g., in the mutation-testing CI job which has no DB service).
    """
    try:
        conn = psycopg2.connect(dbname="kitchen", host="localhost", connect_timeout=2)
    except psycopg2.OperationalError:
        pytest.skip("PostgreSQL not available — skipping sql.Composed rendering tests")
    yield conn
    conn.close()


def render(composed, conn):
    """Render a sql.Composed object to a plain SQL string for assertion."""
    return composed.as_string(conn)


class TestBuildDeleteSql:
    """Tests for _build_delete_sql helper function"""

    def test_build_hard_delete_sql(self, db_conn):
        """Test building SQL for hard delete"""
        table = "test_table"
        where = {"id": "uuid1"}

        composed, values = _build_delete_sql(table, where, soft=False)
        sql_str = render(composed, db_conn)

        assert 'DELETE FROM "test_table"' in sql_str
        assert '"id" = %s' in sql_str
        assert values == ("uuid1",)

    def test_build_soft_delete_sql(self, db_conn):
        """Test building SQL for soft delete"""
        table = "test_table"
        where = {"id": "uuid1"}

        composed, values = _build_delete_sql(table, where, soft=True)
        sql_str = render(composed, db_conn)

        assert 'UPDATE "test_table"' in sql_str
        assert "is_archived = true" in sql_str
        assert '"id" = %s' in sql_str
        assert values == ("uuid1",)

    def test_build_soft_delete_with_additional_fields(self, db_conn):
        """Test building SQL for soft delete with additional fields"""
        table = "test_table"
        where = {"id": "uuid1"}
        soft_update_fields = {"modified_by": "user1", "modified_date": datetime.now()}

        composed, values = _build_delete_sql(table, where, soft=True, soft_update_fields=soft_update_fields)
        sql_str = render(composed, db_conn)

        assert 'UPDATE "test_table"' in sql_str
        assert "is_archived = true" in sql_str
        assert '"modified_by" = %s' in sql_str
        assert '"modified_date" = %s' in sql_str
        assert '"id" = %s' in sql_str
        assert len(values) == 3  # modified_by, modified_date, id

    def test_build_delete_sql_with_uuid(self, db_conn):
        """Test UUID conversion in WHERE clause"""
        table = "test_table"
        where = {"id": UUID("12345678-1234-5678-1234-567812345678")}

        composed, values = _build_delete_sql(table, where, soft=False)

        assert str(values[0]) == "12345678-1234-5678-1234-567812345678"

    def test_build_delete_sql_multiple_where_conditions(self, db_conn):
        """Test building SQL with multiple WHERE conditions"""
        table = "test_table"
        where = {"id": "uuid1", "status": "active"}

        composed, values = _build_delete_sql(table, where, soft=False)
        sql_str = render(composed, db_conn)

        assert '"id" = %s' in sql_str
        assert '"status" = %s' in sql_str
        assert " AND " in sql_str
        assert len(values) == 2


class TestDbBatchDelete:
    """Tests for db_batch_delete function"""

    @patch("app.utils.db.get_db_connection")
    @patch("app.utils.db.close_db_connection")
    def test_batch_hard_delete_success(self, mock_close, mock_get_conn):
        """Test successful batch hard delete"""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1
        mock_get_conn.return_value = mock_conn

        where_list = [{"id": "uuid1"}, {"id": "uuid2"}, {"id": "uuid3"}]

        result = db_batch_delete("test_table", where_list, connection=mock_conn, soft=False)

        assert result == 3
        assert mock_cursor.execute.call_count == 3
        mock_conn.commit.assert_called_once()
        mock_conn.rollback.assert_not_called()

    @patch("app.utils.db.get_db_connection")
    @patch("app.utils.db.close_db_connection")
    def test_batch_soft_delete_success(self, mock_close, mock_get_conn):
        """Test successful batch soft delete"""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1
        mock_get_conn.return_value = mock_conn

        where_list = [{"id": "uuid1"}, {"id": "uuid2"}]

        result = db_batch_delete("test_table", where_list, connection=mock_conn, soft=True)

        assert result == 2
        assert mock_cursor.execute.call_count == 2
        # Verify UPDATE SQL was used (not DELETE) — check the Composed object repr
        first_call_sql = mock_cursor.execute.call_args_list[0][0][0]
        assert "UPDATE" in repr(first_call_sql)
        mock_conn.commit.assert_called_once()

    @patch("app.utils.db.get_db_connection")
    @patch("app.utils.db.close_db_connection")
    def test_batch_soft_delete_with_additional_fields(self, mock_close, mock_get_conn, db_conn):
        """Test batch soft delete with additional fields"""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1
        mock_get_conn.return_value = mock_conn

        where_list = [{"id": "uuid1"}]
        soft_update_fields = {"modified_by": "user1", "modified_date": datetime.now()}

        result = db_batch_delete(
            "test_table", where_list, connection=mock_conn, soft=True, soft_update_fields=soft_update_fields
        )

        assert result == 1
        # Verify SQL includes additional fields via as_string() on the Composed object
        composed = mock_cursor.execute.call_args_list[0][0][0]
        sql_str = render(composed, db_conn)
        assert '"modified_by" = %s' in sql_str
        assert '"modified_date" = %s' in sql_str

    def test_batch_delete_empty_list(self):
        """Test that empty list raises ValueError"""
        with pytest.raises(ValueError, match="where_list cannot be empty"):
            db_batch_delete("test_table", [], connection=Mock())

    def test_batch_delete_invalid_data_type(self):
        """Test that non-dict items raise ValueError"""
        where_list = [{"id": "uuid1"}, "not_a_dict"]

        with pytest.raises(ValueError, match="where_list\\[1\\] must be a dictionary"):
            db_batch_delete("test_table", where_list, connection=Mock())

    def test_batch_delete_empty_dict(self):
        """Test that empty dict items raise ValueError"""
        where_list = [{"id": "uuid1"}, {}]

        with pytest.raises(ValueError, match="where_list\\[1\\] cannot be empty"):
            db_batch_delete("test_table", where_list, connection=Mock())

    @patch("app.utils.db.get_db_connection")
    @patch("app.utils.db.close_db_connection")
    @patch("app.utils.db.handle_database_exception")
    def test_batch_delete_rollback_on_error(self, mock_handle_exception, mock_close, mock_get_conn):
        """Test that errors trigger rollback"""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_get_conn.return_value = mock_conn

        where_list = [{"id": "uuid1"}]

        with pytest.raises((Exception, TypeError)):
            db_batch_delete("test_table", where_list, connection=mock_conn)

        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()

    @patch("app.utils.db.get_db_connection")
    @patch("app.utils.db.close_db_connection")
    def test_batch_delete_creates_connection_if_none(self, mock_close, mock_get_conn):
        """Test that function creates connection if none provided"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1
        mock_get_conn.return_value = mock_conn

        where_list = [{"id": "uuid1"}]

        db_batch_delete("test_table", where_list, connection=None)

        mock_get_conn.assert_called_once()
        mock_close.assert_called_once_with(mock_conn)

    @patch("app.utils.db.get_db_connection")
    @patch("app.utils.db.close_db_connection")
    def test_batch_delete_uses_provided_connection(self, mock_close, mock_get_conn):
        """Test that function uses provided connection"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1

        where_list = [{"id": "uuid1"}]

        db_batch_delete("test_table", where_list, connection=mock_conn)

        mock_get_conn.assert_not_called()
        mock_close.assert_not_called()


class TestDbDelete:
    """Tests for db_delete function (backward compatibility)"""

    @patch("app.utils.db.get_db_connection")
    @patch("app.utils.db.close_db_connection")
    def test_single_delete_backward_compatible(self, mock_close, mock_get_conn):
        """Test that db_delete still works as before"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1
        mock_get_conn.return_value = mock_conn

        result = db_delete("test_table", {"id": "uuid1"}, connection=mock_conn)

        assert result == 1
        mock_conn.commit.assert_called_once()

    @patch("app.utils.db.get_db_connection")
    @patch("app.utils.db.close_db_connection")
    def test_single_soft_delete(self, mock_close, mock_get_conn, db_conn):
        """Test single soft delete"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1
        mock_get_conn.return_value = mock_conn

        result = db_delete("test_table", {"id": "uuid1"}, connection=mock_conn, soft=True)

        assert result == 1
        # Verify UPDATE SQL was used via as_string() on the Composed object
        composed = mock_cursor.execute.call_args_list[0][0][0]
        sql_str = render(composed, db_conn)
        assert "UPDATE" in sql_str
        assert "is_archived = true" in sql_str
