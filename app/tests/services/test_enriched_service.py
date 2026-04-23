"""
Unit tests for EnrichedService

Tests the generic enriched service functionality including:
- WHERE clause building (archived, institution scoping)
- Query building with JOINs
- UUID conversion
- Error handling
- Schema validation
"""

from unittest.mock import MagicMock, Mock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from app.security.institution_scope import InstitutionScope
from app.services.enriched_service import EnrichedService


# Test schemas
class MockEnrichedSchema(BaseModel):
    """Test schema for enriched service tests"""

    id: str
    name: str
    institution_id: str
    is_archived: bool

    model_config = ConfigDict(extra="forbid")


class MockEnrichedSchemaOptional(BaseModel):
    """Test schema with optional fields"""

    id: str
    name: str
    institution_id: str | None = None
    is_archived: bool = False

    model_config = ConfigDict(extra="forbid")


@pytest.fixture
def mock_db():
    """Mock database connection"""
    return Mock()


@pytest.fixture
def enriched_service():
    """Create a test EnrichedService instance"""
    return EnrichedService(
        base_table="test_table",
        table_alias="tt",
        id_column="test_id",
        schema_class=MockEnrichedSchema,
        institution_column="institution_id",
        institution_table_alias="tt",
    )


@pytest.fixture
def enriched_service_no_institution():
    """Create a test EnrichedService instance without institution scoping"""
    return EnrichedService(
        base_table="test_table", table_alias="tt", id_column="test_id", schema_class=MockEnrichedSchemaOptional
    )


class TestBuildWhereClause:
    """Test WHERE clause building"""

    def test_build_where_clause_no_archived(self, enriched_service):
        """Test WHERE clause with archived filter"""
        where_clause, params = enriched_service._build_where_clause(include_archived=False)
        assert "tt.is_archived = FALSE" in where_clause
        assert len(params) == 0

    def test_build_where_clause_include_archived(self, enriched_service):
        """Test WHERE clause without archived filter"""
        where_clause, params = enriched_service._build_where_clause(include_archived=True)
        assert "tt.is_archived = FALSE" not in where_clause
        assert len(params) == 0

    def test_build_where_clause_institution_scoped(self, enriched_service):
        """Test WHERE clause with institution scoping"""
        institution_id = str(uuid4())
        scope = InstitutionScope(institution_id=institution_id, role_type="supplier")
        where_clause, params = enriched_service._build_where_clause(scope=scope)
        assert "tt.institution_id = %s::uuid" in where_clause
        assert len(params) == 1
        assert params[0] == institution_id

    def test_build_where_clause_global_scope(self, enriched_service):
        """Test WHERE clause with global scope (Internal Admin)"""
        scope = InstitutionScope(
            institution_id=str(uuid4()),
            role_type="internal",
            role_name="admin",  # Internal Admin has global access
        )
        where_clause, params = enriched_service._build_where_clause(scope=scope)
        # Global scope should not add institution filter
        assert "tt.institution_id" not in where_clause
        assert len(params) == 0

    def test_build_where_clause_additional_conditions(self, enriched_service):
        """Test WHERE clause with additional conditions"""
        where_clause, params = enriched_service._build_where_clause(
            additional_conditions=[("tt.status = %s", ["active"]), ("tt.created_date > %s", ["2024-01-01"])]
        )
        assert "tt.status = %s" in where_clause
        assert "tt.created_date > %s" in where_clause
        assert len(params) == 2
        assert params[0] == "active"
        assert params[1] == "2024-01-01"

    def test_build_where_clause_no_institution_column(self, enriched_service_no_institution):
        """Test WHERE clause when no institution column is configured"""
        scope = InstitutionScope(institution_id=str(uuid4()), role_type="supplier")
        where_clause, params = enriched_service_no_institution._build_where_clause(scope=scope)
        # Should not add institution filter if no institution_column configured
        assert "institution_id" not in where_clause
        assert len(params) == 0


class TestConvertUuidsToStrings:
    """Test UUID to string conversion"""

    def test_convert_uuids_simple(self, enriched_service):
        """Test converting UUID objects to strings"""
        row_dict = {
            "id": UUID("11111111-1111-1111-1111-111111111111"),
            "name": "Test",
            "institution_id": UUID("22222222-2222-2222-2222-222222222222"),
            "is_archived": False,
        }
        converted = enriched_service._convert_uuids_to_strings(row_dict)
        assert converted["id"] == "11111111-1111-1111-1111-111111111111"
        assert converted["institution_id"] == "22222222-2222-2222-2222-222222222222"
        assert converted["name"] == "Test"
        assert converted["is_archived"] is False

    def test_convert_uuids_mixed_types(self, enriched_service):
        """Test converting mixed types (UUIDs and strings)"""
        row_dict = {"id": UUID("11111111-1111-1111-1111-111111111111"), "name": "Test", "count": 5, "is_active": True}
        converted = enriched_service._convert_uuids_to_strings(row_dict)
        assert isinstance(converted["id"], str)
        assert isinstance(converted["name"], str)
        assert isinstance(converted["count"], int)
        assert isinstance(converted["is_active"], bool)

    def test_convert_uuids_no_uuids(self, enriched_service):
        """Test conversion when no UUIDs are present"""
        row_dict = {"id": "11111111-1111-1111-1111-111111111111", "name": "Test", "count": 5}
        converted = enriched_service._convert_uuids_to_strings(row_dict)
        assert converted == row_dict


class TestGetEnriched:
    """Test get_enriched method"""

    @patch("app.services.enriched_service.db_read")
    def test_get_enriched_success(self, mock_db_read, enriched_service, mock_db):
        """Test successful enriched query"""
        # Mock database results - db_read returns list of dict-like objects
        # Use MagicMock with __iter__ to make it dict-like
        row1 = MagicMock()
        row1.__iter__ = lambda self: iter(
            [("id", str(uuid4())), ("name", "Test 1"), ("institution_id", str(uuid4())), ("is_archived", False)]
        )
        row1.items = lambda: [
            ("id", str(uuid4())),
            ("name", "Test 1"),
            ("institution_id", str(uuid4())),
            ("is_archived", False),
        ]
        row1.keys = lambda: ["id", "name", "institution_id", "is_archived"]
        row1.values = lambda: [str(uuid4()), "Test 1", str(uuid4()), False]

        row2 = MagicMock()
        row2.__iter__ = lambda self: iter(
            [("id", str(uuid4())), ("name", "Test 2"), ("institution_id", str(uuid4())), ("is_archived", False)]
        )
        row2.items = lambda: [
            ("id", str(uuid4())),
            ("name", "Test 2"),
            ("institution_id", str(uuid4())),
            ("is_archived", False),
        ]
        row2.keys = lambda: ["id", "name", "institution_id", "is_archived"]
        row2.values = lambda: [str(uuid4()), "Test 2", str(uuid4()), False]

        # Simpler approach: use actual dicts
        mock_results = [
            {"id": str(uuid4()), "name": "Test 1", "institution_id": str(uuid4()), "is_archived": False},
            {"id": str(uuid4()), "name": "Test 2", "institution_id": str(uuid4()), "is_archived": False},
        ]
        mock_db_read.return_value = mock_results

        results = enriched_service.get_enriched(
            mock_db,
            select_fields=["tt.id", "tt.name", "tt.institution_id", "tt.is_archived"],
            joins=[("LEFT", "institution_info", "i", "tt.institution_id = i.institution_id")],
        )

        assert len(results) == 2
        assert all(isinstance(r, MockEnrichedSchema) for r in results)
        mock_db_read.assert_called_once()

    @patch("app.services.enriched_service.db_read")
    def test_get_enriched_empty_results(self, mock_db_read, enriched_service, mock_db):
        """Test enriched query with no results"""
        mock_db_read.return_value = []

        results = enriched_service.get_enriched(mock_db, select_fields=["tt.id", "tt.name"], joins=[])

        assert len(results) == 0
        assert results == []

    @patch("app.services.enriched_service.db_read")
    def test_get_enriched_with_scope(self, mock_db_read, enriched_service, mock_db):
        """Test enriched query with institution scoping"""
        institution_id = str(uuid4())
        scope = InstitutionScope(institution_id=institution_id, role_type="supplier")
        mock_db_read.return_value = []

        enriched_service.get_enriched(mock_db, select_fields=["tt.id", "tt.name"], joins=[], scope=scope)

        # Verify query includes institution filter
        call_args = mock_db_read.call_args
        query = call_args[0][0]
        assert "tt.institution_id = %s::uuid" in query

    @patch("app.services.enriched_service.db_read")
    def test_get_enriched_with_joins(self, mock_db_read, enriched_service, mock_db):
        """Test enriched query with JOINs"""
        mock_db_read.return_value = []

        enriched_service.get_enriched(
            mock_db,
            select_fields=["tt.id", "i.name as institution_name"],
            joins=[
                ("LEFT", "institution_info", "i", "tt.institution_id = i.institution_id"),
                ("INNER", "address_info", "a", "tt.address_id = a.address_id"),
            ],
        )

        # Verify JOINs are in query
        call_args = mock_db_read.call_args
        query = call_args[0][0]
        assert "LEFT JOIN institution_info i" in query
        assert "INNER JOIN address_info a" in query

    @patch("app.services.enriched_service.db_read")
    def test_get_enriched_custom_order_by(self, mock_db_read, enriched_service, mock_db):
        """Test enriched query with custom ORDER BY"""
        mock_db_read.return_value = []

        enriched_service.get_enriched(mock_db, select_fields=["tt.id", "tt.name"], joins=[], order_by="tt.name ASC")

        call_args = mock_db_read.call_args
        query = call_args[0][0]
        assert "ORDER BY tt.name ASC" in query

    @patch("app.services.enriched_service.db_read")
    def test_get_enriched_database_error(self, mock_db_read, enriched_service, mock_db):
        """Test enriched query with database error"""
        mock_db_read.side_effect = Exception("Database connection failed")

        with pytest.raises(HTTPException) as exc_info:
            enriched_service.get_enriched(mock_db, select_fields=["tt.id", "tt.name"], joins=[])

        assert exc_info.value.status_code == 500
        assert (
            "Failed to execute enriched query" in exc_info.value.detail
            or "Failed to get enriched" in exc_info.value.detail
        )


class TestGetEnrichedById:
    """Test get_enriched_by_id method"""

    @patch("app.services.enriched_service.db_read")
    def test_get_enriched_by_id_success(self, mock_db_read, enriched_service, mock_db):
        """Test successful enriched query by ID"""
        record_id = uuid4()
        mock_results = {"id": str(record_id), "name": "Test", "institution_id": str(uuid4()), "is_archived": False}
        mock_db_read.return_value = mock_results

        result = enriched_service.get_enriched_by_id(
            record_id, mock_db, select_fields=["tt.id", "tt.name", "tt.institution_id", "tt.is_archived"], joins=[]
        )

        assert result is not None
        assert isinstance(result, MockEnrichedSchema)
        assert result.id == str(record_id)
        mock_db_read.assert_called_once()

    @patch("app.services.enriched_service.db_read")
    def test_get_enriched_by_id_not_found(self, mock_db_read, enriched_service, mock_db):
        """Test enriched query by ID when record not found"""
        record_id = uuid4()
        mock_db_read.return_value = None

        result = enriched_service.get_enriched_by_id(record_id, mock_db, select_fields=["tt.id", "tt.name"], joins=[])

        assert result is None

    @patch("app.services.enriched_service.db_read")
    def test_get_enriched_by_id_with_scope(self, mock_db_read, enriched_service, mock_db):
        """Test enriched query by ID with institution scoping"""
        record_id = uuid4()
        institution_id = str(uuid4())
        scope = InstitutionScope(institution_id=institution_id, role_type="supplier")
        mock_db_read.return_value = None

        enriched_service.get_enriched_by_id(
            record_id, mock_db, select_fields=["tt.id", "tt.name"], joins=[], scope=scope
        )

        # Verify query includes both ID and institution filter
        call_args = mock_db_read.call_args
        query = call_args[0][0]
        assert "tt.test_id = %s" in query
        assert "tt.institution_id = %s::uuid" in query


class TestExecuteQuery:
    """Test _execute_query method"""

    @patch("app.services.enriched_service.db_read")
    def test_execute_query_success(self, mock_db_read, enriched_service, mock_db):
        """Test successful query execution"""
        mock_results = [{"id": "1", "name": "Test"}]
        mock_db_read.return_value = mock_results

        results = enriched_service._execute_query("SELECT * FROM test", None, mock_db, fetch_one=False)
        assert results == mock_results

    @patch("app.services.enriched_service.db_read")
    def test_execute_query_fetch_one(self, mock_db_read, enriched_service, mock_db):
        """Test query execution with fetch_one=True"""
        mock_result = {"id": "1", "name": "Test"}
        mock_db_read.return_value = mock_result

        results = enriched_service._execute_query("SELECT * FROM test WHERE id = %s", ["1"], mock_db, fetch_one=True)
        assert results == [mock_result]

    @patch("app.services.enriched_service.db_read")
    def test_execute_query_fetch_one_none(self, mock_db_read, enriched_service, mock_db):
        """Test query execution with fetch_one=True but no result"""
        mock_db_read.return_value = None

        results = enriched_service._execute_query("SELECT * FROM test WHERE id = %s", ["999"], mock_db, fetch_one=True)
        assert results is None

    @patch("app.services.enriched_service.db_read")
    def test_execute_query_error(self, mock_db_read, enriched_service, mock_db):
        """Test query execution with error"""
        mock_db_read.side_effect = Exception("DB Error")

        with pytest.raises(HTTPException) as exc_info:
            enriched_service._execute_query("SELECT * FROM test", None, mock_db, fetch_one=False)
        assert exc_info.value.status_code == 500
