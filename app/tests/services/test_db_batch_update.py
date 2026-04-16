# app/tests/services/test_db_batch_update.py
"""
Unit tests for db_batch_update function.

Tests cover:
- Pattern 1: Same update, different WHERE clauses
- Pattern 2: Different updates per record
- Validation (empty updates, invalid data, pattern ambiguity)
- Transaction atomicity (rollback on error)
- Connection management
- Backward compatibility of db_update
"""

from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from app.utils.db import _build_update_sql, db_batch_update, db_update


class TestBuildUpdateSql:
    """Tests for _build_update_sql helper function"""

    def test_build_update_sql(self):
        """Test building SQL for update"""
        table = "test_table"
        data = {"status": "active", "modified_by": "user1"}
        where = {"id": "uuid1"}

        sql, values = _build_update_sql(table, data, where)

        assert "UPDATE test_table" in sql
        assert "SET status = %s" in sql
        assert "modified_by = %s" in sql
        assert "WHERE id = %s" in sql
        assert len(values) == 3  # 2 data values + 1 where value
        assert values[0] == "active"
        assert values[1] == "user1"
        assert values[2] == "uuid1"

    def test_build_update_sql_with_uuid(self):
        """Test UUID conversion in update"""
        table = "test_table"
        data = {"status": "active"}
        where = {"id": UUID("12345678-1234-5678-1234-567812345678")}

        sql, values = _build_update_sql(table, data, where)

        assert str(values[1]) == "12345678-1234-5678-1234-567812345678"

    def test_build_update_sql_multiple_where_conditions(self):
        """Test building SQL with multiple WHERE conditions"""
        table = "test_table"
        data = {"status": "active"}
        where = {"id": "uuid1", "is_archived": False}

        sql, values = _build_update_sql(table, data, where)

        assert "WHERE id = %s AND is_archived = %s" in sql
        assert len(values) == 3  # 1 data value + 2 where values


class TestDbBatchUpdatePattern1:
    """Tests for db_batch_update Pattern 1: Same update, different WHERE clauses"""

    @patch("app.utils.db.get_db_connection")
    @patch("app.utils.db.close_db_connection")
    def test_pattern1_success(self, mock_close, mock_get_conn):
        """Test successful Pattern 1 batch update"""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1
        mock_get_conn.return_value = mock_conn

        updates = {"status": "archived"}
        where_list = [{"id": "uuid1"}, {"id": "uuid2"}, {"id": "uuid3"}]

        result = db_batch_update("test_table", updates, where_list, connection=mock_conn)

        assert result == 3
        assert mock_cursor.execute.call_count == 3
        mock_conn.commit.assert_called_once()
        mock_conn.rollback.assert_not_called()

    @patch("app.utils.db.get_db_connection")
    @patch("app.utils.db.close_db_connection")
    def test_pattern1_single_record(self, mock_close, mock_get_conn):
        """Test Pattern 1 with single record"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1
        mock_get_conn.return_value = mock_conn

        updates = {"status": "active"}
        where_list = [{"id": "uuid1"}]

        result = db_batch_update("test_table", updates, where_list, connection=mock_conn)

        assert result == 1
        assert mock_cursor.execute.call_count == 1

    def test_pattern1_empty_updates_dict(self):
        """Test that empty updates dict raises ValueError"""
        with pytest.raises(ValueError, match="updates dict cannot be empty"):
            db_batch_update("test_table", {}, [{"id": "uuid1"}], connection=Mock())

    def test_pattern1_missing_where_list(self):
        """Test that missing where_list raises ValueError"""
        with pytest.raises(ValueError, match="where_list is required for Pattern 1"):
            db_batch_update("test_table", {"status": "active"}, None, connection=Mock())

    def test_pattern1_empty_where_list(self):
        """Test that empty where_list raises ValueError"""
        with pytest.raises(ValueError, match="where_list cannot be empty for Pattern 1"):
            db_batch_update("test_table", {"status": "active"}, [], connection=Mock())

    def test_pattern1_invalid_where_list_type(self):
        """Test that invalid where_list type raises ValueError"""
        with pytest.raises(ValueError, match="where_list must be a list for Pattern 1"):
            db_batch_update("test_table", {"status": "active"}, "not_a_list", connection=Mock())

    def test_pattern1_invalid_where_dict(self):
        """Test that invalid where dict raises ValueError"""
        with pytest.raises(ValueError, match="where_list\\[0\\] must be a dictionary"):
            db_batch_update("test_table", {"status": "active"}, ["not_a_dict"], connection=Mock())


class TestDbBatchUpdatePattern2:
    """Tests for db_batch_update Pattern 2: Different updates per record"""

    @patch("app.utils.db.get_db_connection")
    @patch("app.utils.db.close_db_connection")
    def test_pattern2_success(self, mock_close, mock_get_conn):
        """Test successful Pattern 2 batch update"""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1
        mock_get_conn.return_value = mock_conn

        updates = [
            {"id": "uuid1", "status": "active", "modified_by": "user1"},
            {"id": "uuid2", "status": "inactive", "modified_by": "user1"},
            {"id": "uuid3", "status": "pending", "modified_by": "user1"},
        ]

        result = db_batch_update("test_table", updates, connection=mock_conn)

        assert result == 3
        assert mock_cursor.execute.call_count == 3
        mock_conn.commit.assert_called_once()
        mock_conn.rollback.assert_not_called()

    @patch("app.utils.db.get_db_connection")
    @patch("app.utils.db.close_db_connection")
    def test_pattern2_single_record(self, mock_close, mock_get_conn):
        """Test Pattern 2 with single record"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1
        mock_get_conn.return_value = mock_conn

        updates = [{"id": "uuid1", "status": "active"}]

        result = db_batch_update("test_table", updates, connection=mock_conn)

        assert result == 1
        assert mock_cursor.execute.call_count == 1

    def test_pattern2_empty_updates_list(self):
        """Test that empty updates list raises ValueError"""
        with pytest.raises(ValueError, match="updates list cannot be empty for Pattern 2"):
            db_batch_update("test_table", [], connection=Mock())

    def test_pattern2_with_where_list_raises_error(self):
        """Test that providing where_list with Pattern 2 raises ValueError"""
        updates = [{"id": "uuid1", "status": "active"}]
        where_list = [{"id": "uuid1"}]

        with pytest.raises(ValueError, match="where_list must be None for Pattern 2"):
            db_batch_update("test_table", updates, where_list, connection=Mock())

    def test_pattern2_missing_id_field(self):
        """Test that missing id field raises ValueError"""
        updates = [{"status": "active"}]  # Missing 'id'

        with pytest.raises(ValueError, match="updates\\[0\\] must contain 'id' field for Pattern 2"):
            db_batch_update("test_table", updates, connection=Mock())

    def test_pattern2_invalid_update_dict(self):
        """Test that invalid update dict raises ValueError"""
        updates = [{"id": "uuid1"}, "not_a_dict"]

        with pytest.raises(ValueError, match="updates\\[1\\] must be a dictionary"):
            db_batch_update("test_table", updates, connection=Mock())

    def test_pattern2_empty_update_dict(self):
        """Test that empty update dict raises ValueError"""
        updates = [{"id": "uuid1"}, {}]

        with pytest.raises(ValueError, match="updates\\[1\\] cannot be empty"):
            db_batch_update("test_table", updates, connection=Mock())


class TestDbBatchUpdateCommon:
    """Common tests for both patterns"""

    def test_invalid_updates_type(self):
        """Test that invalid updates type raises ValueError"""
        with pytest.raises(ValueError, match="updates must be either a dict"):
            db_batch_update("test_table", "not_dict_or_list", connection=Mock())

    @patch("app.utils.db.get_db_connection")
    @patch("app.utils.db.close_db_connection")
    @patch("app.utils.db.handle_database_exception")
    def test_rollback_on_error(self, mock_handle_exception, mock_close, mock_get_conn):
        """Test that errors trigger rollback"""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_get_conn.return_value = mock_conn

        updates = {"status": "active"}
        where_list = [{"id": "uuid1"}]

        with pytest.raises((Exception, TypeError)):
            db_batch_update("test_table", updates, where_list, connection=mock_conn)

        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()

    @patch("app.utils.db.get_db_connection")
    @patch("app.utils.db.close_db_connection")
    def test_creates_connection_if_none(self, mock_close, mock_get_conn):
        """Test that function creates connection if none provided"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1
        mock_get_conn.return_value = mock_conn

        updates = {"status": "active"}
        where_list = [{"id": "uuid1"}]

        db_batch_update("test_table", updates, where_list, connection=None)

        mock_get_conn.assert_called_once()
        mock_close.assert_called_once_with(mock_conn)

    @patch("app.utils.db.get_db_connection")
    @patch("app.utils.db.close_db_connection")
    def test_uses_provided_connection(self, mock_close, mock_get_conn):
        """Test that function uses provided connection"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1

        updates = {"status": "active"}
        where_list = [{"id": "uuid1"}]

        db_batch_update("test_table", updates, where_list, connection=mock_conn)

        mock_get_conn.assert_not_called()
        mock_close.assert_not_called()


class TestDbUpdate:
    """Tests for db_update function (backward compatibility)"""

    @patch("app.utils.db.get_db_connection")
    @patch("app.utils.db.close_db_connection")
    def test_single_update_backward_compatible(self, mock_close, mock_get_conn):
        """Test that db_update still works as before"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1
        mock_get_conn.return_value = mock_conn

        result = db_update("test_table", {"status": "active"}, {"id": "uuid1"}, connection=mock_conn)

        assert result == 1
        mock_conn.commit.assert_called_once()
