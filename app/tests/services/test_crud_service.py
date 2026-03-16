"""
Unit tests for CRUDService JOIN-based scoping

Tests the generic CRUD service functionality including:
- JOIN-based query building with institution scoping
- Direct column scoping (backward compatibility)
- Edge cases (no scope, global scope, supplier scope)
- Multiple JOIN paths
- Validation for create/update operations
- All CRUD operations with JOIN scoping
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from fastapi import HTTPException

from app.services.crud_service import CRUDService
from app.security.institution_scope import InstitutionScope
from app.dto.models import PlateKitchenDaysDTO
from app.config import Status


# Test DTO for direct column scoping
class MockDirectScopingDTO(BaseModel):
    """Test DTO with direct institution_id column"""
    id: UUID
    name: str
    institution_id: UUID
    is_archived: bool
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")


# Test DTO for JOIN-based scoping
class MockJoinScopingDTO(BaseModel):
    """Test DTO requiring JOIN-based scoping"""
    id: UUID
    foreign_key_id: UUID
    is_archived: bool
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")


@pytest.fixture
def mock_db():
    """Mock database connection"""
    mock_conn = Mock()
    mock_conn.cursor.return_value = Mock()
    return mock_conn


@pytest.fixture
def direct_scoping_service():
    """CRUDService with direct column scoping"""
    return CRUDService(
        table_name="test_table",
        dto_class=MockDirectScopingDTO,
        id_column="id",
        institution_column="institution_id"
    )


@pytest.fixture
def join_scoping_service():
    """CRUDService with JOIN-based scoping (single JOIN)"""
    return CRUDService(
        table_name="test_table",
        dto_class=MockJoinScopingDTO,
        id_column="id",
        institution_join_path=[
            ("INNER", "related_table", "rt", "test_table.foreign_key_id = rt.related_id")
        ],
        institution_table_alias="rt"
    )


@pytest.fixture
def multi_join_scoping_service():
    """CRUDService with JOIN-based scoping (multiple JOINs)"""
    return CRUDService(
        table_name="plate_kitchen_days",
        dto_class=PlateKitchenDaysDTO,
        id_column="plate_kitchen_day_id",
        institution_join_path=[
            ("INNER", "plate_info", "p", "plate_kitchen_days.plate_id = p.plate_id"),
            ("INNER", "restaurant_info", "r", "p.restaurant_id = r.restaurant_id")
        ],
        institution_table_alias="r"
    )


@pytest.fixture
def global_scope():
    """InstitutionScope with global access (Internal Admin)"""
    return InstitutionScope(
        institution_id=uuid4(),
        role_type="Internal",
        role_name="Admin"  # Internal Admin has global access
    )


@pytest.fixture
def supplier_scope():
    """InstitutionScope with supplier access (scoped)"""
    institution_id = uuid4()
    return InstitutionScope(
        institution_id=institution_id,
        role_type="Supplier"
    )


class TestBuildJoinQueryWithScope:
    """Test _build_join_query_with_scope() method"""
    
    def test_build_join_query_no_scope(self, multi_join_scoping_service):
        """Test query building without scope"""
        query, params = multi_join_scoping_service._build_join_query_with_scope(
            scope=None,
            include_archived=False
        )
        
        assert "SELECT plate_kitchen_days.*" in query
        assert "FROM plate_kitchen_days" in query
        assert "INNER JOIN plate_info p" in query
        assert "INNER JOIN restaurant_info r" in query
        assert "plate_kitchen_days.is_archived = FALSE" in query
        assert "r.institution_id" not in query  # No scoping
        assert len(params) == 0
    
    def test_build_join_query_global_scope(self, multi_join_scoping_service, global_scope):
        """Test query building with global scope (Internal)"""
        query, params = multi_join_scoping_service._build_join_query_with_scope(
            scope=global_scope,
            include_archived=False
        )
        
        assert "SELECT plate_kitchen_days.*" in query
        assert "INNER JOIN plate_info p" in query
        assert "INNER JOIN restaurant_info r" in query
        assert "plate_kitchen_days.is_archived = FALSE" in query
        assert "r.institution_id" not in query  # Global scope doesn't filter
        assert len(params) == 0
    
    def test_build_join_query_supplier_scope(self, multi_join_scoping_service, supplier_scope):
        """Test query building with supplier scope"""
        query, params = multi_join_scoping_service._build_join_query_with_scope(
            scope=supplier_scope,
            include_archived=False
        )
        
        assert "SELECT plate_kitchen_days.*" in query
        assert "INNER JOIN plate_info p" in query
        assert "INNER JOIN restaurant_info r" in query
        assert "r.institution_id = %s::uuid" in query
        assert "plate_kitchen_days.is_archived = FALSE" in query
        assert len(params) == 1
        assert params[0] == str(supplier_scope.institution_id)
    
    def test_build_join_query_include_archived(self, multi_join_scoping_service, supplier_scope):
        """Test query building with include_archived=True"""
        query, params = multi_join_scoping_service._build_join_query_with_scope(
            scope=supplier_scope,
            include_archived=True
        )
        
        assert "plate_kitchen_days.is_archived = FALSE" not in query
        assert "r.institution_id = %s::uuid" in query
        assert len(params) == 1
    
    def test_build_join_query_custom_select_fields(self, multi_join_scoping_service, supplier_scope):
        """Test query building with custom SELECT fields"""
        query, params = multi_join_scoping_service._build_join_query_with_scope(
            scope=supplier_scope,
            include_archived=False,
            select_fields="plate_kitchen_days.plate_kitchen_day_id, plate_kitchen_days.kitchen_day"
        )
        
        assert "SELECT plate_kitchen_days.plate_kitchen_day_id, plate_kitchen_days.kitchen_day" in query
        assert "plate_kitchen_days.*" not in query
    
    def test_build_join_query_custom_order_by(self, multi_join_scoping_service, supplier_scope):
        """Test query building with custom ORDER BY"""
        query, params = multi_join_scoping_service._build_join_query_with_scope(
            scope=supplier_scope,
            include_archived=False,
            order_by="kitchen_day ASC"
        )
        
        assert "ORDER BY kitchen_day ASC" in query
        assert "ORDER BY created_date DESC" not in query
    
    def test_build_join_query_additional_conditions(self, multi_join_scoping_service, supplier_scope):
        """Test query building with additional WHERE conditions"""
        query, params = multi_join_scoping_service._build_join_query_with_scope(
            scope=supplier_scope,
            include_archived=False,
            additional_conditions=[
                ("plate_kitchen_days.kitchen_day = %s", "Monday"),
                ("p.plate_id = %s::uuid", str(uuid4()))
            ]
        )
        
        assert "plate_kitchen_days.kitchen_day = %s" in query
        assert "p.plate_id = %s::uuid" in query
        assert len(params) == 3  # institution_id + 2 additional conditions
    
    def test_build_join_query_requires_join_path(self, direct_scoping_service, supplier_scope):
        """Test that _build_join_query_with_scope raises error without join_path"""
        with pytest.raises(ValueError, match="institution_join_path"):
            direct_scoping_service._build_join_query_with_scope(
                scope=supplier_scope,
                include_archived=False
            )


class TestGetAllWithJoinScoping:
    """Test get_all() with JOIN-based scoping"""
    
    @patch('app.services.crud_service.db_read')
    def test_get_all_no_scope(self, mock_db_read, multi_join_scoping_service, mock_db):
        """Test get_all() without scope"""
        mock_db_read.return_value = [
            {
                'plate_kitchen_day_id': uuid4(),
                'plate_id': uuid4(),
                'kitchen_day': 'Monday',
                'status': Status.ACTIVE,
                'is_archived': False,
                'created_date': datetime.now(timezone.utc),
                'modified_by': uuid4(),
                'modified_date': datetime.now(timezone.utc)
            }
        ]
        
        results = multi_join_scoping_service.get_all(mock_db, scope=None)
        
        assert len(results) == 1
        assert isinstance(results[0], PlateKitchenDaysDTO)
        # Verify query includes JOINs but no institution filter
        call_args = mock_db_read.call_args
        assert "INNER JOIN plate_info p" in call_args[0][0]
        assert "INNER JOIN restaurant_info r" in call_args[0][0]
        assert "r.institution_id" not in call_args[0][0]
    
    @patch('app.services.crud_service.db_read')
    def test_get_all_global_scope(self, mock_db_read, multi_join_scoping_service, mock_db, global_scope):
        """Test get_all() with global scope (Internal)"""
        mock_db_read.return_value = [
            {
                'plate_kitchen_day_id': uuid4(),
                'plate_id': uuid4(),
                'kitchen_day': 'Monday',
                'status': Status.ACTIVE,
                'is_archived': False,
                'created_date': datetime.now(timezone.utc),
                'modified_by': uuid4(),
                'modified_date': datetime.now(timezone.utc)
            }
        ]
        
        results = multi_join_scoping_service.get_all(mock_db, scope=global_scope)
        
        assert len(results) == 1
        # Verify no institution filter for global scope
        call_args = mock_db_read.call_args
        assert "r.institution_id" not in call_args[0][0]
    
    @patch('app.services.crud_service.db_read')
    def test_get_all_supplier_scope(self, mock_db_read, multi_join_scoping_service, mock_db, supplier_scope):
        """Test get_all() with supplier scope"""
        institution_id = supplier_scope.institution_id
        mock_db_read.return_value = [
            {
                'plate_kitchen_day_id': uuid4(),
                'plate_id': uuid4(),
                'kitchen_day': 'Monday',
                'status': Status.ACTIVE,
                'is_archived': False,
                'created_date': datetime.now(timezone.utc),
                'modified_by': uuid4(),
                'modified_date': datetime.now(timezone.utc)
            }
        ]
        
        results = multi_join_scoping_service.get_all(mock_db, scope=supplier_scope)
        
        assert len(results) == 1
        # Verify institution filter is applied
        call_args = mock_db_read.call_args
        assert "r.institution_id = %s::uuid" in call_args[0][0]
        assert str(institution_id) in call_args[0][1]
    
    @patch('app.services.crud_service.db_read')
    def test_get_all_include_archived(self, mock_db_read, multi_join_scoping_service, mock_db, supplier_scope):
        """Test get_all() with include_archived=True"""
        mock_db_read.return_value = []
        
        multi_join_scoping_service.get_all(mock_db, scope=supplier_scope, include_archived=True)
        
        call_args = mock_db_read.call_args
        assert "is_archived = FALSE" not in call_args[0][0]
    
    @patch('app.services.crud_service.db_read')
    def test_get_all_with_limit(self, mock_db_read, multi_join_scoping_service, mock_db, supplier_scope):
        """Test get_all() with limit"""
        mock_db_read.return_value = []
        
        multi_join_scoping_service.get_all(mock_db, limit=10, scope=supplier_scope)
        
        call_args = mock_db_read.call_args
        assert "LIMIT %s" in call_args[0][0]
        assert 10 in call_args[0][1]


class TestGetByIdWithJoinScoping:
    """Test get_by_id() with JOIN-based scoping"""
    
    @patch('app.services.crud_service.db_read')
    def test_get_by_id_no_scope(self, mock_db_read, multi_join_scoping_service, mock_db):
        """Test get_by_id() without scope"""
        record_id = uuid4()
        mock_db_read.return_value = {
            'plate_kitchen_day_id': record_id,
            'plate_id': uuid4(),
            'kitchen_day': 'Monday',
            'status': Status.ACTIVE,
            'is_archived': False,
            'created_date': datetime.now(timezone.utc),
            'modified_by': uuid4(),
            'modified_date': datetime.now(timezone.utc)
        }
        
        result = multi_join_scoping_service.get_by_id(record_id, mock_db, scope=None)
        
        assert result is not None
        assert isinstance(result, PlateKitchenDaysDTO)
        assert result.plate_kitchen_day_id == record_id
        # Verify query includes JOINs but no institution filter
        call_args = mock_db_read.call_args
        assert "INNER JOIN plate_info p" in call_args[0][0]
        assert "r.institution_id" not in call_args[0][0]
    
    @patch('app.services.crud_service.db_read')
    def test_get_by_id_supplier_scope(self, mock_db_read, multi_join_scoping_service, mock_db, supplier_scope):
        """Test get_by_id() with supplier scope"""
        record_id = uuid4()
        institution_id = supplier_scope.institution_id
        mock_db_read.return_value = {
            'plate_kitchen_day_id': record_id,
            'plate_id': uuid4(),
            'kitchen_day': 'Monday',
            'status': Status.ACTIVE,
            'is_archived': False,
            'created_date': datetime.now(timezone.utc),
            'modified_by': uuid4(),
            'modified_date': datetime.now(timezone.utc)
        }
        
        result = multi_join_scoping_service.get_by_id(record_id, mock_db, scope=supplier_scope)
        
        assert result is not None
        # Verify institution filter is applied
        call_args = mock_db_read.call_args
        assert "r.institution_id = %s::uuid" in call_args[0][0]
        assert str(institution_id) in call_args[0][1]
        assert str(record_id) in call_args[0][1]
    
    @patch('app.services.crud_service.db_read')
    def test_get_by_id_not_found(self, mock_db_read, multi_join_scoping_service, mock_db, supplier_scope):
        """Test get_by_id() when record not found"""
        record_id = uuid4()
        mock_db_read.return_value = None
        
        result = multi_join_scoping_service.get_by_id(record_id, mock_db, scope=supplier_scope)
        
        assert result is None


class TestBackwardCompatibility:
    """Test backward compatibility with direct column scoping"""
    
    @patch('app.services.crud_service.db_read')
    def test_get_all_direct_column_scoping(self, mock_db_read, direct_scoping_service, mock_db, supplier_scope):
        """Test get_all() with direct column scoping (backward compatibility)"""
        mock_db_read.return_value = [
            {
                'id': uuid4(),
                'name': 'Test',
                'institution_id': supplier_scope.institution_id,
                'is_archived': False,
                'created_date': datetime.now(timezone.utc),
                'modified_date': datetime.now(timezone.utc)
            }
        ]
        
        results = direct_scoping_service.get_all(mock_db, scope=supplier_scope)
        
        assert len(results) == 1
        # Verify direct column filter is used (no JOINs)
        call_args = mock_db_read.call_args
        assert "INNER JOIN" not in call_args[0][0]
        assert "institution_id = %s" in call_args[0][0]
    
    @patch('app.services.crud_service.db_read')
    def test_get_by_id_direct_column_scoping(self, mock_db_read, direct_scoping_service, mock_db, supplier_scope):
        """Test get_by_id() with direct column scoping"""
        record_id = uuid4()
        mock_db_read.return_value = {
            'id': record_id,
            'name': 'Test',
            'institution_id': supplier_scope.institution_id,
            'is_archived': False,
            'created_date': datetime.now(timezone.utc),
            'modified_date': datetime.now(timezone.utc)
        }
        
        result = direct_scoping_service.get_by_id(record_id, mock_db, scope=supplier_scope)
        
        assert result is not None
        # Verify direct column filter is used
        call_args = mock_db_read.call_args
        assert "INNER JOIN" not in call_args[0][0]
        assert "institution_id = %s" in call_args[0][0]


class TestValidateJoinBasedScope:
    """Test _validate_join_based_scope() method"""
    
    @patch('app.utils.db.db_read')
    def test_validate_join_based_scope_success(self, mock_db_read, multi_join_scoping_service, mock_db, supplier_scope):
        """Test validation succeeds when foreign key belongs to scoped institution"""
        foreign_key_value = uuid4()
        institution_id = supplier_scope.institution_id
        
        # Mock validation query returning the correct institution_id (as dict for fetch_one=True)
        mock_db_read.return_value = {'institution_id': institution_id}
        
        # Should not raise an exception
        multi_join_scoping_service._validate_join_based_scope(
            mock_db,
            supplier_scope,
            "plate_id",
            foreign_key_value
        )
        
        # Verify validation query was executed
        call_args = mock_db_read.call_args
        assert "SELECT r.institution_id" in call_args[0][0]
        assert "FROM plate_info p" in call_args[0][0]
        assert "INNER JOIN restaurant_info r" in call_args[0][0]
    
    @patch('app.utils.db.db_read')
    def test_validate_join_based_scope_failure(self, mock_db_read, multi_join_scoping_service, mock_db, supplier_scope):
        """Test validation fails when foreign key belongs to different institution"""
        foreign_key_value = uuid4()
        different_institution_id = uuid4()
        
        # Mock validation query returning a different institution_id (as dict for fetch_one=True)
        mock_db_read.return_value = {'institution_id': different_institution_id}
        
        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            multi_join_scoping_service._validate_join_based_scope(
                mock_db,
                supplier_scope,
                "plate_id",
                foreign_key_value
            )
        
        assert exc_info.value.status_code == 403
        assert "institution" in str(exc_info.value.detail).lower()
    
    @patch('app.utils.db.db_read')
    def test_validate_join_based_scope_not_found(self, mock_db_read, multi_join_scoping_service, mock_db, supplier_scope):
        """Test validation fails when foreign key doesn't exist"""
        foreign_key_value = uuid4()
        
        # Mock validation query returning no results (None for fetch_one=True)
        mock_db_read.return_value = None
        
        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            multi_join_scoping_service._validate_join_based_scope(
                mock_db,
                supplier_scope,
                "plate_id",
                foreign_key_value
            )
        
        assert exc_info.value.status_code == 404
    
    @patch('app.services.crud_service.db_read')
    def test_validate_join_based_scope_global_scope(self, mock_db_read, multi_join_scoping_service, mock_db, global_scope):
        """Test validation skipped for global scope"""
        foreign_key_value = uuid4()
        
        # Should not execute validation query for global scope
        multi_join_scoping_service._validate_join_based_scope(
            mock_db,
            global_scope,
            "plate_id",
            foreign_key_value
        )
        
        # No database call should be made for global scope
        mock_db_read.assert_not_called()


class TestCreateWithJoinScoping:
    """Test create() with JOIN-based scoping"""
    
    @patch('app.services.crud_service.db_insert')
    @patch('app.utils.db.db_read')
    @patch('app.services.crud_service.db_read')
    def test_create_with_foreign_key_validation(self, mock_crud_db_read, mock_utils_db_read, mock_db_insert, multi_join_scoping_service, mock_db, supplier_scope):
        """Test create() validates foreign key belongs to scoped institution"""
        institution_id = supplier_scope.institution_id
        plate_id = uuid4()
        
        # Mock validation query (as dict for fetch_one=True) - from utils.db
        mock_utils_db_read.return_value = {'institution_id': institution_id}
        
        # Mock insert
        new_id = uuid4()
        mock_db_insert.return_value = new_id
        
        # Mock get_by_id after insert - from crud_service
        mock_crud_db_read.return_value = {
            'plate_kitchen_day_id': new_id,
            'plate_id': plate_id,
            'kitchen_day': 'Monday',
            'status': Status.ACTIVE,
            'is_archived': False,
            'created_date': datetime.now(timezone.utc),
            'modified_by': uuid4(),
            'modified_date': datetime.now(timezone.utc)
        }
        
        data = {
            'plate_id': plate_id,
            'kitchen_day': 'Monday',
            'modified_by': uuid4()
        }
        
        result = multi_join_scoping_service.create(data, mock_db, scope=supplier_scope)
        
        assert result is not None
        # Verify validation was called
        assert mock_utils_db_read.called
        # Verify insert was called
        assert mock_db_insert.called
    
    @patch('app.utils.db.db_read')
    def test_create_fails_foreign_key_validation(self, mock_db_read, multi_join_scoping_service, mock_db, supplier_scope):
        """Test create() fails when foreign key belongs to different institution"""
        different_institution_id = uuid4()
        plate_id = uuid4()
        
        # Mock validation query returning different institution (as dict for fetch_one=True)
        mock_db_read.return_value = {'institution_id': different_institution_id}
        
        data = {
            'plate_id': plate_id,
            'kitchen_day': 'Monday',
            'modified_by': uuid4()
        }
        
        with pytest.raises(HTTPException) as exc_info:
            multi_join_scoping_service.create(data, mock_db, scope=supplier_scope)
        
        assert exc_info.value.status_code == 403


class TestUpdateWithJoinScoping:
    """Test update() with JOIN-based scoping"""
    
    @patch('app.services.crud_service.db_update')
    @patch('app.utils.db.db_read')
    @patch('app.services.crud_service.db_read')
    def test_update_with_foreign_key_validation(self, mock_crud_db_read, mock_utils_db_read, mock_db_update, multi_join_scoping_service, mock_db, supplier_scope):
        """Test update() validates foreign key when updating"""
        record_id = uuid4()
        institution_id = supplier_scope.institution_id
        new_plate_id = uuid4()
        
        # Mock validation query (from utils.db)
        mock_utils_db_read.return_value = {'institution_id': institution_id}
        
        # Mock get_by_id (existing record) and after update (from crud_service)
        mock_crud_db_read.side_effect = [
            {  # First call: get_by_id
                'plate_kitchen_day_id': record_id,
                'plate_id': uuid4(),
                'kitchen_day': 'Monday',
                'status': Status.ACTIVE,
                'is_archived': False,
                'created_date': datetime.now(timezone.utc),
                'modified_by': uuid4(),
                'modified_date': datetime.now(timezone.utc)
            },
            {  # Second call: get_by_id after update
                'plate_kitchen_day_id': record_id,
                'plate_id': new_plate_id,
                'kitchen_day': 'Tuesday',
                'status': Status.ACTIVE,
                'is_archived': False,
                'created_date': datetime.now(timezone.utc),
                'modified_by': uuid4(),
                'modified_date': datetime.now(timezone.utc)
            }
        ]
        
        mock_db_update.return_value = 1
        
        data = {
            'plate_id': new_plate_id,
            'kitchen_day': 'Tuesday'
        }
        
        result = multi_join_scoping_service.update(record_id, data, mock_db, scope=supplier_scope)
        
        assert result is not None
        # Verify validation was called for the new plate_id
        assert mock_utils_db_read.called
        # Verify get_by_id was called
        assert mock_crud_db_read.call_count >= 2
    
    @patch('app.utils.db.db_read')
    @patch('app.services.crud_service.db_read')
    def test_update_fails_foreign_key_validation(self, mock_crud_db_read, mock_utils_db_read, multi_join_scoping_service, mock_db, supplier_scope):
        """Test update() fails when new foreign key belongs to different institution"""
        record_id = uuid4()
        different_institution_id = uuid4()
        new_plate_id = uuid4()
        
        # Mock validation query (from utils.db) - returns different institution
        mock_utils_db_read.return_value = {'institution_id': different_institution_id}
        
        # Mock get_by_id (existing record) - from crud_service
        mock_crud_db_read.return_value = {
            'plate_kitchen_day_id': record_id,
            'plate_id': uuid4(),
            'kitchen_day': 'Monday',
            'status': Status.ACTIVE,
            'is_archived': False,
            'created_date': datetime.now(timezone.utc),
            'modified_by': uuid4(),
            'modified_date': datetime.now(timezone.utc)
        }
        
        data = {
            'plate_id': new_plate_id,
            'kitchen_day': 'Tuesday'
        }
        
        with pytest.raises(HTTPException) as exc_info:
            multi_join_scoping_service.update(record_id, data, mock_db, scope=supplier_scope)
        
        assert exc_info.value.status_code == 403


class TestSoftDeleteWithJoinScoping:
    """Test soft_delete() with JOIN-based scoping"""
    
    @patch('app.services.crud_service.db_update')
    @patch('app.services.crud_service.db_read')
    def test_soft_delete_with_join_scoping(self, mock_db_read, mock_db_update, multi_join_scoping_service, mock_db, supplier_scope):
        """Test soft_delete() uses JOIN-based scoping"""
        record_id = uuid4()
        modified_by = uuid4()
        
        # Mock get_by_id (existing record)
        mock_db_read.return_value = {
            'plate_kitchen_day_id': record_id,
            'plate_id': uuid4(),
            'kitchen_day': 'Monday',
            'status': Status.ACTIVE,
            'is_archived': False,
            'created_date': datetime.now(timezone.utc),
            'modified_by': uuid4(),
            'modified_date': datetime.now(timezone.utc)
        }
        
        mock_db_update.return_value = 1
        
        result = multi_join_scoping_service.soft_delete(record_id, modified_by, mock_db, scope=supplier_scope)
        
        assert result is True
        # Verify get_by_id was called (which uses JOIN scoping)
        assert mock_db_read.called


class TestServiceInitialization:
    """Test service initialization validation"""
    
    def test_init_requires_table_alias_with_join_path(self):
        """Test that institution_table_alias is required when join_path is provided"""
        with pytest.raises(ValueError, match="institution_table_alias"):
            CRUDService(
                table_name="test_table",
                dto_class=MockJoinScopingDTO,
                id_column="id",
                institution_join_path=[
                    ("INNER", "related_table", "rt", "test_table.foreign_key_id = rt.related_id")
                ]
                # Missing institution_table_alias
            )
    
    def test_init_cannot_use_both_column_and_join_path(self):
        """Test that both institution_column and join_path cannot be used"""
        with pytest.raises(ValueError, match="Cannot use both"):
            CRUDService(
                table_name="test_table",
                dto_class=MockDirectScopingDTO,
                id_column="id",
                institution_column="institution_id",
                institution_join_path=[
                    ("INNER", "related_table", "rt", "test_table.foreign_key_id = rt.related_id")
                ],
                institution_table_alias="rt"
            )
    
    def test_init_direct_column_scoping(self, direct_scoping_service):
        """Test initialization with direct column scoping"""
        assert direct_scoping_service.institution_column == "institution_id"
        assert direct_scoping_service.institution_join_path is None
        assert direct_scoping_service.institution_table_alias is None
    
    def test_init_join_based_scoping(self, multi_join_scoping_service):
        """Test initialization with JOIN-based scoping"""
        assert multi_join_scoping_service.institution_column is None
        assert multi_join_scoping_service.institution_join_path is not None
        assert len(multi_join_scoping_service.institution_join_path) == 2
        assert multi_join_scoping_service.institution_table_alias == "r"

