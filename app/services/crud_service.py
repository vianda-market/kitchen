# app/services/crud_service.py
"""
Generic CRUD Service - Eliminates code duplication across all entities.

This service provides generic CRUD operations that can be used for any DTO type,
eliminating the need for duplicate CRUD logic across 20+ model classes.

Benefits:
- Single implementation for all CRUD operations
- No code duplication across entities
- Consistent error handling
- Type-safe operations with generics
- Easy to extend with new operations
"""

from datetime import datetime
from typing import Any, Generic, TypeVar, Union
from uuid import UUID

import psycopg2
from fastapi import HTTPException
from pydantic import BaseModel

from app.config import Status
from app.config.restricted_institutions import (
    RESTRICTED_INSTITUTION_TABLES,
    TABLE_CONTEXT_FOR_MESSAGE,
    validate_institution_assignable,
)
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.security.institution_scope import InstitutionScope
from app.utils.db import db_delete, db_insert, db_read, db_update
from app.utils.log import log_error, log_info, log_warning
from app.utils.pagination import PaginatedList

# Tables that use resolved_by/resolved_date instead of modified_by/modified_date (no created_by)
TABLES_WITHOUT_MODIFIED_BY = ("discretionary_resolution_info",)
TABLES_WITHOUT_MODIFIED_DATE = ("discretionary_resolution_info",)

T = TypeVar("T", bound=BaseModel)


class CRUDService(Generic[T]):
    """
    Generic CRUD service that provides common database operations
    for any DTO type, eliminating code duplication.
    """

    def __init__(
        self,
        table_name: str,
        dto_class: type[T],
        id_column: str,
        *,
        institution_column: str | None = None,
        institution_join_path: list[tuple[str, str, str]] | None = None,
        institution_table_alias: str | None = None,
    ):
        """
        Initialize the CRUD service for a specific table and DTO type.

        Args:
            table_name: Name of the database table
            dto_class: The DTO class to use for serialization
            id_column: Name of the primary key column
            institution_column: Name of the institution_id column (for direct scoping)
            institution_join_path: List of JOIN tuples (join_type, table, alias, join_condition)
                                  to reach the table containing institution_id
            institution_table_alias: Alias of the table containing institution_id (for JOIN-based scoping)

        Examples:
            # Direct column scoping (institution_id on base table)
            service = CRUDService("restaurant_info", RestaurantDTO, "restaurant_id",
                                  institution_column="institution_id")

            # JOIN-based scoping (institution_id on joined table)
            service = CRUDService("plate_kitchen_days", PlateKitchenDaysDTO, "kitchen_day_id",
                                  institution_join_path=[
                                      ("INNER", "plate_info", "p", "pkd.plate_id = p.plate_id"),
                                      ("INNER", "restaurant_info", "r", "p.restaurant_id = r.restaurant_id")
                                  ],
                                  institution_table_alias="r")
        """
        self.table_name = table_name
        self.dto_class = dto_class
        self.id_column = id_column
        self.institution_column = institution_column
        self.institution_join_path = institution_join_path
        self.institution_table_alias = institution_table_alias

        # Validate configuration
        if institution_join_path and not institution_table_alias:
            raise ValueError("institution_table_alias is required when institution_join_path is provided")
        if institution_join_path and institution_column:
            raise ValueError("Cannot use both institution_column and institution_join_path")

    def _build_join_query_with_scope(
        self,
        scope: InstitutionScope | None,
        include_archived: bool = False,
        additional_conditions: list[tuple[str, list]] | None = None,
        select_fields: str | None = None,
        order_by: str | None = None,
    ) -> tuple[str, list[Any]]:
        """
        Build a JOIN query with institution scoping for tables that require JOINs.

        Args:
            scope: Optional institution scope for filtering
            include_archived: Whether to include archived records
            additional_conditions: List of (condition, list_of_params) tuples for custom conditions
            select_fields: Custom SELECT fields (defaults to base table.*)
            order_by: Custom ORDER BY clause (defaults to primary key DESC for newest first)

        Returns:
            Tuple of (query, params)
        """
        if not self.institution_join_path:
            raise ValueError("_build_join_query_with_scope requires institution_join_path")

        # Build SELECT clause
        if select_fields:
            select_clause = select_fields
        else:
            select_clause = f"{self.table_name}.*"

        # Build FROM and JOINs
        from_clause = f"FROM {self.table_name}"
        join_clauses = []
        for join_type, table, alias, condition in self.institution_join_path:
            join_clauses.append(f"{join_type} JOIN {table} {alias} ON {condition}")

        # Build WHERE clause
        conditions = []
        params: list[Any] = []

        # Filter by archived status
        if not include_archived:
            conditions.append(f"{self.table_name}.is_archived = FALSE")

        # Apply institution scoping
        if scope and not scope.is_global and scope.institution_id and self.institution_table_alias:
            conditions.append(f"{self.institution_table_alias}.institution_id = %s::uuid")
            params.append(str(scope.institution_id))

        # Add custom conditions
        if additional_conditions:
            for condition, param_list in additional_conditions:
                conditions.append(condition)
                if param_list is not None:
                    params.extend(param_list)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Build ORDER BY (UUID7 PK gives newest-first when DESC)
        if order_by:
            order_clause = f"ORDER BY {order_by}"
        else:
            order_clause = f"ORDER BY {self.table_name}.{self.id_column} DESC"

        # Combine query
        query = f"""
            SELECT {select_clause}
            {from_clause}
            {" ".join(join_clauses)}
            {where_clause}
            {order_clause}
        """

        return query, params

    def _filter_control_parameters(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Filter out control parameters that are not database fields.

        Uses DTO fields as whitelist - only fields that exist in the DTO are kept.
        This prevents control parameters (like assign_employer) from reaching the database.

        Control parameters are fields that exist in request schemas (e.g., AddressCreateSchema)
        but not in DTOs (e.g., AddressDTO), indicating they are business logic flags,
        not database columns.

        IMPORTANT: This method assumes DTOs match database schemas. If a DTO is missing
        required database fields (like modified_by, modified_date), those fields should be
        added to the DTO rather than bypassing this filter.

        Args:
            data: Data dictionary that may contain control parameters

        Returns:
            Filtered data dictionary with only valid database fields (fields that exist in DTO)
        """
        # Get all field names from DTO class
        # Pydantic v2 uses model_fields; v1 used __fields__ (deprecated)
        if hasattr(self.dto_class, "model_fields"):
            dto_fields = set(self.dto_class.model_fields.keys())
        elif hasattr(self.dto_class, "__fields__"):
            dto_fields = set(self.dto_class.__fields__.keys())
        else:
            # Fallback: if we can't determine fields, log warning and return data as-is
            log_warning(
                f"Could not determine DTO fields for {self.dto_class.__name__}, skipping control parameter filtering"
            )
            return data

        # Filter data to only include fields that exist in DTO
        filtered_data = {k: v for k, v in data.items() if k in dto_fields}

        # Log filtered fields for debugging (only if fields were actually filtered)
        filtered_out = set(data.keys()) - set(filtered_data.keys())
        if filtered_out:
            # Check if any filtered fields are system-added fields (modified_by, modified_date, created_date)
            # These should be in the DTO - if they're being filtered, it indicates a DTO mismatch
            system_fields = {"modified_by", "modified_date", "created_date", "created_by"}
            filtered_system_fields = filtered_out & system_fields
            if filtered_system_fields:
                log_warning(
                    f"[CRUDService] WARNING: Filtered out system fields {filtered_system_fields} from {self.table_name}. "
                    f"This indicates {self.dto_class.__name__} DTO is missing required database fields. "
                    f"DTO should be updated to include these fields."
                )
            # Log control parameters separately
            filtered_control_params = filtered_out - system_fields
            if filtered_control_params:
                log_info(
                    f"[CRUDService] Filtered out control parameters: {filtered_control_params} (not in {self.dto_class.__name__} DTO)"
                )

        return filtered_data

    def _enforce_scope_on_dto(self, dto: T | None, scope: InstitutionScope | None) -> T | None:
        if dto is None or scope is None or scope.is_global:
            return dto

        # For direct column scoping
        if self.institution_column:
            institution_value = getattr(dto, self.institution_column, None)
            scope.enforce(institution_value)
        # For JOIN-based scoping, validation happens at query level
        # but we can still enforce if institution_id is present in DTO
        elif hasattr(dto, "institution_id"):
            institution_value = getattr(dto, "institution_id", None)
            scope.enforce(institution_value)

        return dto

    def _validate_join_based_scope(
        self,
        db: psycopg2.extensions.connection,
        scope: InstitutionScope | None,
        foreign_key_field: str,
        foreign_key_value: Any,
    ) -> None:
        """
        Validate that a foreign key relationship leads to an institution that matches the scope.

        This is used for JOIN-based scoping where we need to validate that a foreign key
        (e.g., plate_id) points to a resource (e.g., plate) that belongs to the correct institution.

        Args:
            db: Database connection
            scope: Institution scope to validate against
            foreign_key_field: Name of the foreign key field (e.g., "plate_id")
            foreign_key_value: Value of the foreign key

        Raises:
            HTTPException: If the foreign key doesn't lead to a resource in the correct institution
        """
        if not self.institution_join_path or not scope or scope.is_global:
            return

        if not foreign_key_value:
            return

        # Build a query to check if the foreign key leads to the correct institution
        # We'll use the first JOIN in the path to validate
        # For plate_kitchen_days: plate_id -> plate_info -> restaurant_info -> institution_id
        from app.utils.db import db_read

        # Find the first JOIN that connects to the foreign key
        # For plate_kitchen_days: plate_id connects to plate_info
        # We need to trace through the JOINs to find institution_id
        if len(self.institution_join_path) >= 1:
            # Build a validation query
            # Example: SELECT r.institution_id FROM plate_info p INNER JOIN restaurant_info r ON p.restaurant_id = r.restaurant_id WHERE p.plate_id = %s
            first_join = self.institution_join_path[0]
            join_table = first_join[1]  # e.g., "plate_info"
            join_alias = first_join[2]  # e.g., "p"
            first_join[3]  # e.g., "pkd.plate_id = p.plate_id"

            # Extract the foreign key field from join_condition (e.g., "pkd.plate_id" -> "plate_id")
            fk_field = foreign_key_field

            # Build query to check institution_id
            validation_query = f"""
                SELECT {self.institution_table_alias}.institution_id
                FROM {join_table} {join_alias}
            """

            # Add remaining JOINs
            for join_type, table, alias, condition in self.institution_join_path[1:]:
                validation_query += f" {join_type} JOIN {table} {alias} ON {condition}"

            # Add WHERE clause
            validation_query += f" WHERE {join_alias}.{fk_field} = %s::uuid"

            result = db_read(validation_query, (str(foreign_key_value),), connection=db, fetch_one=True)

            if not result:
                raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale="en", entity=foreign_key_field)

            institution_id = result.get("institution_id")
            if not scope.matches(institution_id):
                raise envelope_exception(ErrorCode.SECURITY_INSTITUTION_MISMATCH, status=403, locale="en")

    def _apply_scope_to_create_data(
        self, data: dict[str, Any], scope: InstitutionScope | None, db: psycopg2.extensions.connection | None = None
    ) -> None:
        """
        Apply institution scoping to create data.

        For direct column scoping: Sets or validates institution_id.
        For JOIN-based scoping: Validates foreign key relationships.
        """
        if scope is None or scope.is_global:
            return

        # Direct column scoping
        if self.institution_column:
            existing_value = data.get(self.institution_column)
            if existing_value is None:
                if scope.institution_id is None:
                    raise envelope_exception(ErrorCode.SECURITY_FORBIDDEN, status=403, locale="en")
                data[self.institution_column] = scope.institution_id
            elif not scope.matches(existing_value):
                raise envelope_exception(ErrorCode.SECURITY_INSTITUTION_MISMATCH, status=403, locale="en")
        # JOIN-based scoping: validate foreign key relationships
        elif self.institution_join_path and db:
            # Determine which foreign key to validate based on entity type
            # This is entity-specific, so we'll check common patterns
            if "plate_id" in data:
                self._validate_join_based_scope(db, scope, "plate_id", data.get("plate_id"))
            elif "restaurant_id" in data:
                # For restaurant_holidays: restaurant_id -> restaurant_info -> institution_id
                self._validate_join_based_scope(db, scope, "restaurant_id", data.get("restaurant_id"))
            # Add more foreign key validations as needed for other entities

        # Vianda Customers and Vianda Enterprises must not be assigned to products, institution entities, or restaurants
        if self.institution_column and self.table_name in RESTRICTED_INSTITUTION_TABLES:
            inst_id = data.get(self.institution_column)
            if inst_id is not None:
                validate_institution_assignable(
                    inst_id,
                    context=TABLE_CONTEXT_FOR_MESSAGE.get(self.table_name, "record"),
                )

    def get_by_id(
        self, record_id: UUID, db: psycopg2.extensions.connection, *, scope: InstitutionScope | None = None
    ) -> T | None:
        """
        Get a single record by ID.

        Args:
            record_id: The ID of the record to retrieve
            db: Database connection
            scope: Optional institution scope for filtering

        Returns:
            The DTO instance if found, None otherwise
        """
        try:
            # Use JOIN-based query if institution_join_path is configured
            if self.institution_join_path:
                additional_conditions = [(f"{self.table_name}.{self.id_column} = %s", [str(record_id)])]
                query, params = self._build_join_query_with_scope(
                    scope=scope,
                    include_archived=False,
                    additional_conditions=additional_conditions,
                    select_fields=f"{self.table_name}.*",
                )
                result = db_read(query, tuple(params), connection=db, fetch_one=True)
            else:
                # address_info: resolve country_name via market_info (column not stored on address)
                if self.table_name == "address_info":
                    conditions = [f"a.{self.id_column} = %s", "a.is_archived = FALSE"]
                    values: list[Any] = [str(record_id)]
                    if scope and not scope.is_global and self.institution_column and scope.institution_id:
                        conditions.append(f"a.{self.institution_column} = %s")
                        values.append(scope.institution_id)
                    query = f"""
                        SELECT a.*, gc.name AS country_name, g.latitude, g.longitude
                        FROM address_info a
                        LEFT JOIN market_info m ON a.country_code = m.country_code
                        LEFT JOIN external.geonames_country gc ON gc.iso_alpha2 = m.country_code
                        LEFT JOIN geolocation_info g ON g.address_id = a.address_id AND g.is_archived = FALSE
                        WHERE {" AND ".join(conditions)}
                    """
                    result = db_read(query, tuple(values), connection=db, fetch_one=True)
                else:
                    # Direct column scoping
                    conditions = [f"{self.id_column} = %s", "is_archived = FALSE"]
                    values = [str(record_id)]
                    if scope and not scope.is_global and self.institution_column and scope.institution_id:
                        conditions.append(f"{self.institution_column} = %s")
                        values.append(scope.institution_id)
                    query = f"""
                        SELECT * FROM {self.table_name}
                        WHERE {" AND ".join(conditions)}
                    """
                    result = db_read(query, tuple(values), connection=db, fetch_one=True)

            dto = self.dto_class(**result) if result else None
            return self._enforce_scope_on_dto(dto, scope)
        except Exception as e:
            log_error(f"Error getting {self.table_name} by {self.id_column}: {e}")
            return None

    def _build_scope_clauses(
        self, scope: InstitutionScope | None, include_archived: bool, alias: str = ""
    ) -> tuple[list[str], list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        prefix = f"{alias}." if alias else ""
        if not include_archived:
            clauses.append(f"{prefix}is_archived = FALSE")
        if scope and not scope.is_global and self.institution_column and scope.institution_id:
            clauses.append(f"{prefix}{self.institution_column} = %s")
            params.append(scope.institution_id)
        return clauses, params

    def _apply_pagination_or_limit(
        self, query: str, params: list[Any], paginate: bool, page_size: int, offset: int, limit: int | None
    ) -> str:
        if paginate:
            query += " LIMIT %s OFFSET %s"
            params.extend([page_size, offset])
        elif limit:
            query += " LIMIT %s"
            params.append(limit)
        return query

    def _get_count(self, count_query: str, params: list[Any], db: psycopg2.extensions.connection) -> int:
        count_result = db_read(count_query, tuple(params) if params else None, connection=db, fetch_one=True)
        return count_result["count"] if count_result else 0

    def _get_all_via_join(
        self,
        db: psycopg2.extensions.connection,
        scope: InstitutionScope | None,
        include_archived: bool,
        paginate: bool,
        page_size: int,
        offset: int,
        limit: int | None,
    ) -> tuple[Any, int]:
        query, params = self._build_join_query_with_scope(
            scope=scope, include_archived=include_archived, select_fields=f"{self.table_name}.*"
        )
        total_count = 0
        if paginate:
            count_query = query.replace(f"SELECT {self.table_name}.*", "SELECT COUNT(*)", 1)
            total_count = self._get_count(count_query, params, db)
        query = self._apply_pagination_or_limit(query, params, paginate, page_size, offset, limit)
        return db_read(query, tuple(params) if params else None, connection=db), total_count

    def _get_all_address_info(
        self,
        db: psycopg2.extensions.connection,
        scope: InstitutionScope | None,
        include_archived: bool,
        paginate: bool,
        page_size: int,
        offset: int,
        limit: int | None,
    ) -> tuple[Any, int]:
        clauses, params = self._build_scope_clauses(scope, include_archived, alias="a")
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        from_clause = (
            "FROM address_info a"
            " LEFT JOIN market_info m ON a.country_code = m.country_code"
            " LEFT JOIN external.geonames_country gc ON gc.iso_alpha2 = m.country_code"
            " LEFT JOIN geolocation_info g ON g.address_id = a.address_id AND g.is_archived = FALSE"
        )
        total_count = 0
        if paginate:
            total_count = self._get_count(f"SELECT COUNT(*) {from_clause} {where_clause}", list(params), db)
        query = f"SELECT a.*, gc.name AS country_name, g.latitude, g.longitude {from_clause} {where_clause} ORDER BY a.{self.id_column} DESC"
        query = self._apply_pagination_or_limit(query, params, paginate, page_size, offset, limit)
        return db_read(query, tuple(params) if params else None, connection=db), total_count

    def _get_all_direct(
        self,
        db: psycopg2.extensions.connection,
        scope: InstitutionScope | None,
        include_archived: bool,
        paginate: bool,
        page_size: int,
        offset: int,
        limit: int | None,
    ) -> tuple[Any, int]:
        clauses, params = self._build_scope_clauses(scope, include_archived)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total_count = 0
        if paginate:
            total_count = self._get_count(f"SELECT COUNT(*) FROM {self.table_name} {where_clause}", list(params), db)
        query = f"SELECT * FROM {self.table_name} {where_clause} ORDER BY {self.id_column} DESC"
        query = self._apply_pagination_or_limit(query, params, paginate, page_size, offset, limit)
        return db_read(query, tuple(params) if params else None, connection=db), total_count

    def get_all(
        self,
        db: psycopg2.extensions.connection,
        limit: int | None = None,
        *,
        scope: InstitutionScope | None = None,
        include_archived: bool = False,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Union[list[T], "PaginatedList[T]"]:
        """
        Get all records (optionally including archived).

        Args:
            db: Database connection
            limit: Optional limit on number of records
            scope: Optional institution scope for filtering
            include_archived: Whether to include archived records (default: False)
            page: Optional 1-based page number (activates pagination when both page and page_size are set)
            page_size: Optional rows per page (clamped to 1-100)

        Returns:
            List of DTO instances, or PaginatedList with .total_count when paginated
        """
        paginate = page is not None and page_size is not None
        if paginate:
            page_size = max(1, min(page_size, 100))
            page = max(1, page)
            offset = (page - 1) * page_size
        else:
            page_size, offset = 0, 0

        try:
            if self.institution_join_path:
                results, total_count = self._get_all_via_join(
                    db, scope, include_archived, paginate, page_size, offset, limit
                )
            elif self.table_name == "address_info":
                results, total_count = self._get_all_address_info(
                    db, scope, include_archived, paginate, page_size, offset, limit
                )
            else:
                results, total_count = self._get_all_direct(
                    db, scope, include_archived, paginate, page_size, offset, limit
                )

            dtos = [self.dto_class(**result) for result in results] if results else []
            if scope and not scope.is_global and self.institution_column:
                dtos = [dto for dto in dtos if scope.matches(getattr(dto, self.institution_column, None))]
            if paginate:
                return PaginatedList(dtos, total_count=total_count)
            return dtos
        except Exception as e:
            log_error(f"Error getting all {self.table_name}: {e}")
            return []

    def get_by_id_non_archived(
        self, record_id: UUID, db: psycopg2.extensions.connection, *, scope: InstitutionScope | None = None
    ) -> T | None:
        """
        Get a single non-archived record by ID.
        This is an alias for get_by_id() for clarity.

        Args:
            record_id: The ID of the record to retrieve
            db: Database connection

        Returns:
            The DTO instance if found, None otherwise
        """
        return self.get_by_id(record_id, db, scope=scope)

    def get_all_non_archived(
        self,
        db: psycopg2.extensions.connection,
        limit: int | None = None,
        *,
        scope: InstitutionScope | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Union[list[T], "PaginatedList[T]"]:
        """
        Get all non-archived records.
        This is an alias for get_all() for clarity.

        Args:
            db: Database connection
            limit: Optional limit on number of records
            page: Optional 1-based page number (activates pagination when both page and page_size are set)
            page_size: Optional rows per page (clamped to 1-100)

        Returns:
            List of DTO instances, or PaginatedList with .total_count when paginated
        """
        return self.get_all(db, limit, scope=scope, page=page, page_size=page_size)

    def get_by_field(
        self,
        field_name: str,
        field_value: Any,
        db: psycopg2.extensions.connection,
        *,
        scope: InstitutionScope | None = None,
    ) -> T | None:
        """
        Get a single record by a specific field value.

        Args:
            field_name: Name of the field to search by
            field_value: Value to search for
            db: Database connection

        Returns:
            The DTO instance if found, None otherwise
        """
        try:
            if self.table_name == "address_info":
                params: list[Any] = [str(field_value)]
                conditions = [f"a.{field_name} = %s", "a.is_archived = FALSE"]
                if scope and not scope.is_global and self.institution_column and scope.institution_id:
                    conditions.append(f"a.{self.institution_column} = %s")
                    params.append(str(scope.institution_id))
                query = f"""
                    SELECT a.*, gc.name AS country_name
                    FROM address_info a
                    LEFT JOIN market_info m ON a.country_code = m.country_code
                    LEFT JOIN external.geonames_country gc ON gc.iso_alpha2 = m.country_code
                    WHERE {" AND ".join(conditions)}
                """
                result = db_read(query, tuple(params), connection=db, fetch_one=True)
            else:
                query = f"""
                    SELECT * FROM {self.table_name}
                    WHERE {field_name} = %s AND is_archived = FALSE
                """
                params = [str(field_value)]
                if scope and not scope.is_global and self.institution_column:
                    query += f" AND {self.institution_column} = %s"
                    params.append(str(scope.institution_id))
                result = db_read(query, tuple(params), connection=db, fetch_one=True)
            return self.dto_class(**result) if result else None
        except Exception as e:
            log_error(f"Error getting {self.table_name} by {field_name}: {e}")
            return None

    def get_all_by_field(
        self,
        field_name: str,
        field_value: Any,
        db: psycopg2.extensions.connection,
        *,
        scope: InstitutionScope | None = None,
    ) -> list[T]:
        """
        Get all records matching a specific field value.

        Args:
            field_name: Name of the field to search by
            field_value: Value to search for
            db: Database connection

        Returns:
            List of DTO instances
        """
        try:
            if self.table_name == "address_info":
                params: list[Any] = [str(field_value)]
                conditions = [f"a.{field_name} = %s", "a.is_archived = FALSE"]
                if scope and not scope.is_global and self.institution_column and scope.institution_id:
                    conditions.append(f"a.{self.institution_column} = %s")
                    params.append(str(scope.institution_id))
                query = f"""
                    SELECT a.*, gc.name AS country_name
                    FROM address_info a
                    LEFT JOIN market_info m ON a.country_code = m.country_code
                    LEFT JOIN external.geonames_country gc ON gc.iso_alpha2 = m.country_code
                    WHERE {" AND ".join(conditions)}
                    ORDER BY a.{self.id_column} DESC
                """
                results = db_read(query, tuple(params), connection=db)
            else:
                query = f"""
                    SELECT * FROM {self.table_name}
                    WHERE {field_name} = %s AND is_archived = FALSE
                """
                params = [str(field_value)]
                if scope and not scope.is_global and self.institution_column:
                    query += f" AND {self.institution_column} = %s"
                    params.append(str(scope.institution_id))
                query += f" ORDER BY {self.id_column} DESC"
                results = db_read(query, tuple(params), connection=db)
            return [self.dto_class(**result) for result in results] if results else []
        except Exception as e:
            log_error(f"Error getting {self.table_name} by {field_name}: {e}")
            return []

    def create(
        self,
        data: dict[str, Any],
        db: psycopg2.extensions.connection,
        *,
        scope: InstitutionScope | None = None,
        commit: bool = True,
    ) -> T | None:
        """
        Create a new record.

        Args:
            data: Dictionary of data to insert
            db: Database connection
            scope: Optional institution scope for access control
            commit: Whether to commit immediately after insert (default: True).
                    Set to False for atomic multi-operation transactions.

        Returns:
            The created DTO instance if successful, None otherwise

        NOTE: For address_service specifically, this method should NOT be called directly.
        Use address_business_service.create_address_with_geocoding() instead, which:
        - Automatically sets timezone (required field)
        - Handles geocoding for Restaurant, Customer Employer, and Customer Home addresses
        - Creates geolocation records in geolocation_info table
        NOTE: For address_service specifically, this method should NOT be called directly.
        Use address_business_service.create_address_with_geocoding() instead, which:
        - Automatically sets timezone (required field)
        - Handles geocoding for Restaurant, Customer Employer, and Customer Home addresses
        - Creates geolocation records in geolocation_info table
        """
        # Runtime check: Warn if address_service.create() is called directly (outside business service)
        if self.table_name == "address_info":
            import inspect

            caller_frame = inspect.currentframe().f_back
            caller_file = caller_frame.f_code.co_filename if caller_frame else ""
            caller_name = caller_frame.f_code.co_name if caller_frame else ""
            # Check if caller is NOT from address_service.py (business service)
            if "address_service.py" not in caller_file or "create_address_with_geocoding" not in caller_name:
                log_warning(
                    f"[CRUDService] WARNING: address_service.create() called directly from {caller_file}:{caller_name}. "
                    f"This should use address_business_service.create_address_with_geocoding() instead. "
                    f"Direct calls bypass timezone setting and geocoding."
                )

        try:
            log_info(f"[CRUDService.create] Table: {self.table_name}, Data keys before scope: {list(data.keys())}")
            self._apply_scope_to_create_data(data, scope, db)
            # Subscription create: resolve market_id from plan_id (subscription_info requires market_id, plan has it)
            if self.table_name == "subscription_info" and "market_id" not in data and data.get("plan_id"):
                from app.services.crud_service import plan_service

                plan = plan_service.get_by_id(data["plan_id"], db)
                if plan:
                    data["market_id"] = plan.market_id
                else:
                    log_error(f"Plan not found for plan_id={data['plan_id']}, cannot create subscription")
                    raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale="en", entity="Plan")
            log_info(f"[CRUDService.create] Data keys after scope: {list(data.keys())}")
            # Add timestamps
            data["created_date"] = datetime.now()

            # Only add modified_date if the table supports it
            if self.table_name not in TABLES_WITHOUT_MODIFIED_DATE:
                data["modified_date"] = datetime.now()

            # Set created_by from modified_by when DTO supports it (all mutable tables except discretionary_resolution_info)
            dto_fields = getattr(self.dto_class, "model_fields", None)
            if dto_fields is None:
                dto_fields = getattr(self.dto_class, "__fields__", {})
            if dto_fields and "created_by" in dto_fields and "created_by" not in data and "modified_by" in data:
                if self.table_name not in TABLES_WITHOUT_MODIFIED_BY:
                    data["created_by"] = data["modified_by"]

            # Assign default status when the entity has a status column and none was provided (clients may omit status on create)
            dto_annotations = getattr(self.dto_class, "__annotations__", {})
            if "status" in dto_annotations and data.get("status") is None:
                if self.table_name == "payment_method":
                    data["status"] = (
                        Status.PENDING
                    )  # Payment methods start Pending until linked (external_payment_method, etc.)
                else:
                    data["status"] = Status.ACTIVE

            # Remove modified_by if the table doesn't support it
            if self.table_name in TABLES_WITHOUT_MODIFIED_BY and "modified_by" in data:
                del data["modified_by"]

            log_info(f"[CRUDService.create] Data keys before db_insert: {list(data.keys())}")
            log_info(f"[CRUDService.create] currency_code value: {data.get('currency_code')}")
            log_info(f"[CRUDService.create] status value: {data.get('status')}")

            # Filter out control parameters using DTO fields as whitelist
            filtered_data = self._filter_control_parameters(data)

            # Insert record with filtered data (only database fields)
            record_id = db_insert(self.table_name, filtered_data, connection=db, commit=commit)
            if record_id:
                # When creating an institution entity, update the address's address_type from linkages
                # so the address is correctly marked as Entity Address/Entity Billing (used for country detection in settlement pipeline).
                if self.table_name == "institution_entity_info" and filtered_data.get("address_id"):
                    from app.services.address_service import update_address_type_from_linkages

                    addr_id = filtered_data["address_id"]
                    update_address_type_from_linkages(
                        addr_id if isinstance(addr_id, UUID) else UUID(str(addr_id)),
                        db,
                        commit=commit,
                    )
                return self.get_by_id(record_id, db, scope=scope)
            return None
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error creating {self.table_name}: {e}")
            return None

    def update(
        self,
        record_id: UUID,
        data: dict[str, Any],
        db: psycopg2.extensions.connection,
        *,
        scope: InstitutionScope | None = None,
        commit: bool = True,
    ) -> T | None:
        """
        Update an existing record.

        Args:
            record_id: ID of the record to update
            data: Dictionary of data to update
            db: Database connection
            scope: Optional institution scope for access control
            commit: Whether to commit immediately after update (default: True).
                    Set to False for atomic multi-operation transactions.

        Returns:
            The updated DTO instance if successful, None otherwise
        """
        try:
            existing = self.get_by_id(record_id, db, scope=scope)
            if existing is None:
                return None

            # Validate institution scoping for updates
            if self.institution_column and self.institution_column in data:
                # Vianda Customers and Vianda Enterprises must not be assigned to products, institution entities, or restaurants
                if self.table_name in RESTRICTED_INSTITUTION_TABLES:
                    validate_institution_assignable(
                        data[self.institution_column],
                        context=TABLE_CONTEXT_FOR_MESSAGE.get(self.table_name, "record"),
                    )
                if scope and not scope.is_global:
                    if not scope.matches(data[self.institution_column]):
                        raise envelope_exception(ErrorCode.SECURITY_INSTITUTION_MISMATCH, status=403, locale="en")
            elif scope and not scope.is_global and self.institution_join_path:
                # JOIN-based scoping: validate foreign key changes
                if "plate_id" in data:
                    self._validate_join_based_scope(db, scope, "plate_id", data.get("plate_id"))
                # Add more foreign key validations as needed

            # Add modification timestamp only if table supports it
            if self.table_name not in TABLES_WITHOUT_MODIFIED_DATE:
                data["modified_date"] = datetime.now()

            # Remove modified_by if the table doesn't support it
            if self.table_name in TABLES_WITHOUT_MODIFIED_BY and "modified_by" in data:
                del data["modified_by"]

            # Filter out control parameters using DTO fields as whitelist
            filtered_data = self._filter_control_parameters(data)

            # Update record with filtered data (only database fields)
            row_count = db_update(
                self.table_name, filtered_data, {self.id_column: str(record_id)}, connection=db, commit=commit
            )

            if row_count > 0:
                return self.get_by_id(record_id, db, scope=scope)
            return None
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Error updating {self.table_name}: {e}")
            return None

    def soft_delete(
        self,
        record_id: UUID,
        modified_by: UUID,
        db: psycopg2.extensions.connection,
        *,
        scope: InstitutionScope | None = None,
    ) -> bool:
        """
        Soft delete a record (set is_archived = True).

        Args:
            record_id: ID of the record to delete
            modified_by: ID of the user performing the deletion
            db: Database connection

        Returns:
            True if successful, False otherwise
        """
        try:
            existing = self.get_by_id(record_id, db, scope=scope)
            if existing is None:
                return False

            update_data = {"is_archived": True, "modified_by": modified_by, "modified_date": datetime.now()}
            if self.table_name in TABLES_WITHOUT_MODIFIED_BY:
                update_data.pop("modified_by", None)
            if self.table_name in TABLES_WITHOUT_MODIFIED_DATE:
                update_data.pop("modified_date", None)

            row_count = db_update(self.table_name, update_data, {self.id_column: str(record_id)}, connection=db)

            if row_count > 0:
                # Check if this archive caused an onboarding regression for a Supplier
                from app.services.onboarding_service import check_onboarding_regression

                check_onboarding_regression(self.table_name, record_id, db)

            return row_count > 0
        except Exception as e:
            log_error(f"Error soft deleting {self.table_name}: {e}")
            return False

    def hard_delete(self, record_id: UUID, db: psycopg2.extensions.connection) -> bool:
        """
        Permanently delete a record from the database.

        Args:
            record_id: ID of the record to delete
            db: Database connection

        Returns:
            True if successful, False otherwise
        """
        try:
            row_count = db_delete(self.table_name, {self.id_column: str(record_id)}, connection=db)

            return row_count > 0
        except Exception as e:
            log_error(f"Error hard deleting {self.table_name}: {e}")
            return False

    def exists(self, record_id: UUID, db: psycopg2.extensions.connection) -> bool:
        """
        Check if a record exists.

        Args:
            record_id: ID of the record to check
            db: Database connection

        Returns:
            True if record exists, False otherwise
        """
        try:
            query = f"""
                SELECT 1 FROM {self.table_name}
                WHERE {self.id_column} = %s AND is_archived = FALSE
            """
            result = db_read(query, (str(record_id),), connection=db, fetch_one=True)
            return result is not None
        except Exception as e:
            log_error(f"Error checking existence of {self.table_name}: {e}")
            return False

    def count(self, db: psycopg2.extensions.connection) -> int:
        """
        Count total non-archived records.

        Args:
            db: Database connection

        Returns:
            Number of non-archived records
        """
        try:
            query = f"SELECT COUNT(*) FROM {self.table_name} WHERE is_archived = FALSE"
            result = db_read(query, connection=db, fetch_one=True)
            return result[0] if result else 0
        except Exception as e:
            log_error(f"Error counting {self.table_name}: {e}")
            return 0

    # =========================================================================
    # SPECIALIZED METHODS FOR INSTITUTION_BILL_SERVICE
    # =========================================================================
    # These methods are specific to institution bills and extend the generic
    # CRUD operations. They are only used when this service is instantiated
    # for the institution_bill_info table.

    def get_by_entity_and_period(
        self, entity_id: UUID, period_start: datetime, period_end: datetime, db: psycopg2.extensions.connection
    ) -> T | None:
        """Get bill for specific entity and billing period.

        This method is specific to institution_bill_service.

        Args:
            entity_id: Institution entity UUID
            period_start: Start of billing period
            period_end: End of billing period
            db: Database connection

        Returns:
            Bill DTO if found, None otherwise
        """
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE institution_entity_id = %s
            AND period_start = %s
            AND period_end = %s
        """
        result = db_read(query, (str(entity_id), period_start, period_end), connection=db, fetch_one=True)
        return self.dto_class(**result) if result else None

    def get_pending(self, db: psycopg2.extensions.connection) -> list[T]:
        """Get all pending bills.

        This method is specific to institution_bill_service.

        Returns:
            List of bills with status 'Pending'
        """
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE status = 'pending'
            AND is_archived = FALSE
            ORDER BY period_end ASC
        """
        results = db_read(query, connection=db)
        return [self.dto_class(**row) for row in results]

    def mark_paid(self, bill_id: UUID, modified_by: UUID, db: psycopg2.extensions.connection) -> bool:
        """Mark bill as paid (resolution only; no payment_attempt link).

        This method is specific to institution_bill_service.
        institution_bill_info no longer has payment_id; payments are atomic elsewhere.
        """
        try:
            with db.cursor() as cursor:
                from app.config.enums import BillResolution

                query = f"""
                    UPDATE {self.table_name}
                    SET status = 'processed', resolution = %s,
                        modified_by = %s, modified_date = CURRENT_TIMESTAMP
                    WHERE {self.id_column} = %s AND is_archived = FALSE
                """
                cursor.execute(query, (BillResolution.PAID.value, str(modified_by), str(bill_id)))
                db.commit()
                return cursor.rowcount > 0
        except Exception as e:
            db.rollback()
            log_error(f"Error marking bill {bill_id} as paid: {e}")
            raise

    def get_by_institution_and_period(
        self, institution_id: UUID, period_start: datetime, period_end: datetime, db: psycopg2.extensions.connection
    ) -> list[T]:
        """Get bills by institution and period.

        This method is specific to institution_bill_service.
        Joins through institution_entity to get all bills for institution.

        Args:
            institution_id: Institution UUID
            period_start: Start of billing period
            period_end: End of billing period
            db: Database connection

        Returns:
            List of bills for institution in period
        """
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE institution_id = %s
            AND period_start >= %s
            AND period_end <= %s
            AND is_archived = FALSE
        """
        results = db_read(query, (str(institution_id), period_start, period_end), connection=db)
        return [self.dto_class(**row) for row in results]

    # =========================================================================
    # SPECIALIZED METHODS FOR RESTAURANT_BALANCE_SERVICE
    # =========================================================================
    # These methods are specific to restaurant balance and extend the generic
    # CRUD operations. CRITICAL: These handle money and financial transactions.

    def update_with_monetary_amount(
        self, restaurant_id: UUID, amount: float, currency_code: str, db: psycopg2.extensions.connection
    ) -> bool:
        """Update balance with monetary amount.

        This method is specific to restaurant_balance_service.
        CRITICAL: This updates financial balances.

        Args:
            restaurant_id: Restaurant UUID
            amount: Amount to add to balance (can be negative)
            currency_code: Currency code (e.g., 'ARS', 'USD')
            db: Database connection

        Returns:
            True if successful, False otherwise
        """
        try:
            with db.cursor() as cursor:
                query = f"""
                    UPDATE {self.table_name}
                    SET balance = balance + %s,
                        modified_date = CURRENT_TIMESTAMP
                    WHERE restaurant_id = %s AND is_archived = FALSE
                """
                cursor.execute(query, (amount, str(restaurant_id)))
                db.commit()
                return cursor.rowcount > 0
        except Exception as e:
            db.rollback()
            log_error(f"Error updating balance for restaurant {restaurant_id}: {e}")
            return False

    def get_current_event_id(self, restaurant_id: UUID, db: psycopg2.extensions.connection) -> UUID | None:
        """Get the current balance event_id before reset.

        This method is specific to restaurant_balance_service.
        Used for tracking balance history.

        Args:
            restaurant_id: Restaurant UUID
            db: Database connection

        Returns:
            Event ID if found, None otherwise
        """
        query = """
            SELECT event_id
            FROM restaurant_balance_history
            WHERE restaurant_id = %s AND is_current = TRUE
            ORDER BY event_id DESC
            LIMIT 1
        """
        result = db_read(query, (str(restaurant_id),), connection=db, fetch_one=True)
        return result.get("event_id") if result else None

    def reset_balance(self, restaurant_id: UUID, db: psycopg2.extensions.connection, *, commit: bool = True) -> bool:
        """Reset restaurant balance to 0 (used during bill creation).

        This method is specific to restaurant_balance_service.
        CRITICAL: This resets financial balances.

        Args:
            restaurant_id: Restaurant UUID
            db: Database connection
            commit: Whether to commit immediately (default: True).
                   Set to False for atomic multi-operation transactions.

        Returns:
            True if successful, False otherwise
        """
        try:
            with db.cursor() as cursor:
                query = f"""
                    UPDATE {self.table_name}
                    SET balance = 0,
                        transaction_count = 0,
                        modified_date = CURRENT_TIMESTAMP
                    WHERE restaurant_id = %s AND is_archived = FALSE
                """
                cursor.execute(query, (str(restaurant_id),))

                if commit:
                    db.commit()

                return cursor.rowcount > 0
        except Exception as e:
            if commit:
                db.rollback()
            log_error(f"Error resetting balance for restaurant {restaurant_id}: {e}")
            return False

    def create_balance_record(
        self,
        restaurant_id: UUID,
        currency_metadata_id: UUID,
        currency_code: str,
        modified_by: UUID,
        db: psycopg2.extensions.connection,
        *,
        commit: bool = True,
    ) -> bool:
        """Create initial balance record for a new restaurant.

        This method is specific to restaurant_balance_service.
        CRITICAL: This initializes financial records.

        Args:
            restaurant_id: Restaurant UUID
            currency_metadata_id: Credit currency UUID
            currency_code: Currency code (e.g., 'ARS', 'USD')
            modified_by: User UUID who is creating the record
            db: Database connection
            commit: Whether to commit immediately (default: True).
                   Set to False for atomic multi-operation transactions.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if balance record already exists
            existing_balance = self.get_by_restaurant(restaurant_id, db)
            if existing_balance:
                log_info(f"Restaurant balance record already exists for restaurant {restaurant_id}")
                return True

            with db.cursor() as cursor:
                query = f"""
                    INSERT INTO {self.table_name}
                    (restaurant_id, currency_metadata_id, transaction_count, balance,
                     currency_code, status, is_archived, created_date, modified_date, modified_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)
                """
                cursor.execute(
                    query,
                    (
                        str(restaurant_id),
                        str(currency_metadata_id),
                        0,  # Initial transaction count
                        0.00,  # Initial balance
                        currency_code,
                        "active",  # Initial status
                        False,  # Not archived
                        str(modified_by),
                    ),
                )

                if commit:
                    db.commit()

                return cursor.rowcount > 0
        except Exception as e:
            if commit:
                db.rollback()
            log_error(f"Error creating restaurant balance record for restaurant {restaurant_id}: {e}")
            return False

    # =========================================================================
    # SPECIALIZED METHODS FOR RESTAURANT_TRANSACTION_SERVICE
    # =========================================================================
    # These methods are specific to restaurant transactions and extend the
    # generic CRUD operations.

    def get_by_plate_selection(self, plate_selection_id: UUID, db: psycopg2.extensions.connection) -> T | None:
        """Get transaction by plate selection ID.

        This method is specific to restaurant_transaction_service.

        Args:
            plate_selection_id: Plate selection UUID
            db: Database connection

        Returns:
            Transaction DTO if found, None otherwise
        """
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE plate_selection_id = %s AND is_archived = FALSE
        """
        result = db_read(query, (str(plate_selection_id),), connection=db, fetch_one=True)
        return self.dto_class(**result) if result else None

    def mark_collected(
        self, transaction_id: UUID, collected_timestamp: datetime, modified_by: UUID, db: psycopg2.extensions.connection
    ) -> bool:
        """Mark transaction as collected.

        This method is specific to restaurant_transaction_service.

        Args:
            transaction_id: Transaction UUID
            collected_timestamp: When customer collected the order
            modified_by: User UUID making the change
            db: Database connection

        Returns:
            True if successful, False otherwise
        """
        try:
            with db.cursor() as cursor:
                # Note: Check for both table names (restaurant_transaction_info and restaurant_transaction)
                query = f"""
                    UPDATE {self.table_name}
                    SET was_collected = TRUE,
                        collected_timestamp = %s,
                        modified_date = CURRENT_TIMESTAMP,
                        modified_by = %s
                    WHERE transaction_id = %s AND is_archived = FALSE
                """
                cursor.execute(query, (collected_timestamp, str(modified_by), str(transaction_id)))
                db.commit()
                return cursor.rowcount > 0
        except Exception as e:
            db.rollback()
            log_error(f"Error marking transaction {transaction_id} as collected: {e}")
            return False

    def update_final_amount(
        self, transaction_id: UUID, final_amount: float, modified_by: UUID, db: psycopg2.extensions.connection
    ) -> bool:
        """Update the final amount for a transaction.

        This method is specific to restaurant_transaction_service.

        Args:
            transaction_id: Transaction UUID
            final_amount: Final transaction amount
            modified_by: User UUID making the change
            db: Database connection

        Returns:
            True if successful, False otherwise
        """
        try:
            with db.cursor() as cursor:
                query = f"""
                    UPDATE {self.table_name}
                    SET final_amount = %s,
                        modified_date = CURRENT_TIMESTAMP,
                        modified_by = %s
                    WHERE transaction_id = %s AND is_archived = FALSE
                """
                cursor.execute(query, (final_amount, str(modified_by), str(transaction_id)))
                db.commit()
                return cursor.rowcount > 0
        except Exception as e:
            db.rollback()
            log_error(f"Error updating final amount for transaction {transaction_id}: {e}")
            return False

    def update_arrival_time(
        self, transaction_id: UUID, arrival_time: datetime, modified_by: UUID, db: psycopg2.extensions.connection
    ) -> bool:
        """Update customer arrival time for transaction.

        This method is specific to restaurant_transaction_service.

        Args:
            transaction_id: Transaction UUID
            arrival_time: When customer arrived
            modified_by: User UUID making the change
            db: Database connection

        Returns:
            True if successful, False otherwise
        """
        try:
            with db.cursor() as cursor:
                query = f"""
                    UPDATE {self.table_name}
                    SET arrival_time = %s,
                        modified_date = CURRENT_TIMESTAMP,
                        modified_by = %s
                    WHERE transaction_id = %s AND is_archived = FALSE
                """
                cursor.execute(query, (arrival_time, str(modified_by), str(transaction_id)))
                db.commit()
                return cursor.rowcount > 0
        except Exception as e:
            db.rollback()
            log_error(f"Error updating arrival time for transaction {transaction_id}: {e}")
            return False

    # =========================================================================
    # SPECIALIZED METHODS FOR VARIOUS SERVICES
    # =========================================================================
    # These methods are service-specific lookups (Phase 3 - Miscellaneous)

    def get_by_code(self, code: str, db: psycopg2.extensions.connection) -> T | None:
        """Get record by code (e.g., currency_code).

        Used by credit_currency_service.

        Args:
            code: Code to search for (e.g., 'ARS', 'USD')
            db: Database connection

        Returns:
            DTO if found, None otherwise
        """
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE currency_code = %s AND is_archived = FALSE
        """
        result = db_read(query, (code,), connection=db, fetch_one=True)
        return self.dto_class(**result) if result else None

    def get_by_restaurant(self, restaurant_id: UUID, db: psycopg2.extensions.connection) -> T | None:
        """Get record by restaurant ID.

        Used by qr_code_service and other restaurant-related services.

        Args:
            restaurant_id: Restaurant UUID
            db: Database connection

        Returns:
            DTO if found, None otherwise
        """
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE restaurant_id = %s AND is_archived = FALSE
        """
        result = db_read(query, (str(restaurant_id),), connection=db, fetch_one=True)
        return self.dto_class(**result) if result else None

    def get_by_user(self, user_id: UUID, db: psycopg2.extensions.connection) -> T | None:
        """Get record by user ID.

        Used by subscription_service and other user-related services.

        Args:
            user_id: User UUID
            db: Database connection

        Returns:
            DTO if found, None otherwise
        """
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE user_id = %s AND is_archived = FALSE
        """
        result = db_read(query, (str(user_id),), connection=db, fetch_one=True)
        return self.dto_class(**result) if result else None

    def get_by_address(self, address_id: UUID, db: psycopg2.extensions.connection) -> T | None:
        """Get record by address ID.

        Used by geolocation_service.

        Args:
            address_id: Address UUID
            db: Database connection

        Returns:
            DTO if found, None otherwise
        """
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE address_id = %s AND is_archived = FALSE
        """
        result = db_read(query, (str(address_id),), connection=db, fetch_one=True)
        return self.dto_class(**result) if result else None


# =============================================================================
# SERVICE INSTANCES
# =============================================================================
# Pre-configured service instances for all entities
# This eliminates the need for individual model classes

from app.dto.models import (
    AddressDTO,
    BillInvoiceMatchDTO,
    CityDTO,
    ClientBillDTO,
    ClientTransactionDTO,
    CreditCurrencyDTO,
    CuisineDTO,
    CuisineSuggestionDTO,
    DiscretionaryDTO,
    DiscretionaryResolutionDTO,
    EmployerBenefitsProgramDTO,
    EmployerBillDTO,
    EmployerBillLineDTO,
    GeolocationDTO,
    IngredientCatalogDTO,
    InstitutionBillDTO,
    InstitutionDTO,
    InstitutionEntityDTO,
    InstitutionSettlementDTO,
    NationalHolidayDTO,
    PaymentMethodDTO,
    PickupPreferencesDTO,
    PlanDTO,
    PlateDTO,
    PlateKitchenDaysDTO,
    PlatePickupLiveDTO,
    PlateSelectionDTO,
    ProductDTO,
    QRCodeDTO,
    ReferralConfigDTO,
    ReferralInfoDTO,
    RestaurantBalanceDTO,
    RestaurantDTO,
    RestaurantHolidaysDTO,
    RestaurantTransactionDTO,
    SubscriptionDTO,
    SupplierInvoiceARDTO,
    SupplierInvoiceDTO,
    SupplierInvoicePEDTO,
    SupplierInvoiceUSDTO,
    SupplierTermsDTO,
    SupplierW9DTO,
    UserDTO,
    WorkplaceGroupDTO,
)

# Core entity services
user_service = CRUDService("user_info", UserDTO, "user_id", institution_column="institution_id")
institution_service = CRUDService(
    "institution_info", InstitutionDTO, "institution_id", institution_column="institution_id"
)
# role_service removed - role_info table deprecated, roles stored directly on user_info as enums
product_service = CRUDService("product_info", ProductDTO, "product_id", institution_column="institution_id")
plate_service = CRUDService("plate_info", PlateDTO, "plate_id")
restaurant_service = CRUDService("restaurant_info", RestaurantDTO, "restaurant_id", institution_column="institution_id")

# Billing services
institution_bill_service = CRUDService("institution_bill_info", InstitutionBillDTO, "institution_bill_id")
institution_settlement_service = CRUDService("institution_settlement", InstitutionSettlementDTO, "settlement_id")
client_bill_service = CRUDService("client_bill_info", ClientBillDTO, "client_bill_id")
credit_currency_service = CRUDService("currency_metadata", CreditCurrencyDTO, "currency_metadata_id")
supplier_invoice_service = CRUDService(
    "supplier_invoice",
    SupplierInvoiceDTO,
    "supplier_invoice_id",
    institution_join_path=[
        ("INNER", "institution_entity_info", "ie", "supplier_invoice.institution_entity_id = ie.institution_entity_id")
    ],
    institution_table_alias="ie",
)
bill_invoice_match_service = CRUDService("bill_invoice_match", BillInvoiceMatchDTO, "match_id")
supplier_terms_service = CRUDService(
    "supplier_terms", SupplierTermsDTO, "supplier_terms_id", institution_column="institution_id"
)
supplier_invoice_ar_service = CRUDService("supplier_invoice_ar", SupplierInvoiceARDTO, "supplier_invoice_id")
supplier_invoice_pe_service = CRUDService("supplier_invoice_pe", SupplierInvoicePEDTO, "supplier_invoice_id")
supplier_invoice_us_service = CRUDService("supplier_invoice_us", SupplierInvoiceUSDTO, "supplier_invoice_id")
supplier_w9_service = CRUDService(
    "supplier_w9",
    SupplierW9DTO,
    "w9_id",
    institution_join_path=[
        ("INNER", "institution_entity_info", "ie", "supplier_w9.institution_entity_id = ie.institution_entity_id")
    ],
    institution_table_alias="ie",
)

# Address and location services
address_service = CRUDService("address_info", AddressDTO, "address_id", institution_column="institution_id")
workplace_group_service = CRUDService("workplace_group", WorkplaceGroupDTO, "workplace_group_id")
# employer_service REMOVED — employer identity is institution_info + institution_entity_info
# employer_domain_service REMOVED — email_domain is a column on institution_entity_info
employer_benefits_program_service = CRUDService("employer_benefits_program", EmployerBenefitsProgramDTO, "program_id")
employer_bill_service = CRUDService("employer_bill", EmployerBillDTO, "employer_bill_id")
employer_bill_line_service = CRUDService("employer_bill_line", EmployerBillLineDTO, "line_id")
city_service = CRUDService("city_metadata", CityDTO, "city_metadata_id")
geolocation_service = CRUDService("geolocation_info", GeolocationDTO, "geolocation_id")

# Cuisine services
cuisine_crud_service = CRUDService("cuisine", CuisineDTO, "cuisine_id")
cuisine_suggestion_crud_service = CRUDService("cuisine_suggestion", CuisineSuggestionDTO, "suggestion_id")

# Transaction services
restaurant_transaction_service = CRUDService(
    "restaurant_transaction",
    RestaurantTransactionDTO,
    "transaction_id",
    institution_join_path=[("INNER", "restaurant_info", "r", "restaurant_transaction.restaurant_id = r.restaurant_id")],
    institution_table_alias="r",
)
client_transaction_service = CRUDService("client_transaction", ClientTransactionDTO, "transaction_id")


def get_client_charge_by_plate_selection(
    plate_selection_id: UUID, db: psycopg2.extensions.connection
) -> ClientTransactionDTO | None:
    """Get the charge transaction (source='plate_selection') for a plate selection, if promoted. Returns None if not yet charged."""
    result = db_read(
        """SELECT * FROM client_transaction
           WHERE plate_selection_id = %s AND source = 'plate_selection' AND is_archived = FALSE""",
        (str(plate_selection_id),),
        connection=db,
        fetch_one=True,
    )
    return ClientTransactionDTO(**result) if result else None


# Plate selection and pickup services
plate_selection_service = CRUDService("plate_selection_info", PlateSelectionDTO, "plate_selection_id")
pickup_preferences_service = CRUDService("pickup_preferences_info", PickupPreferencesDTO, "preference_id")

# Subscription and plan services
subscription_service = CRUDService("subscription_info", SubscriptionDTO, "subscription_id")
plan_service = CRUDService("plan_info", PlanDTO, "plan_id")

# Institution entity services
institution_entity_service = CRUDService(
    "institution_entity_info", InstitutionEntityDTO, "institution_entity_id", institution_column="institution_id"
)

# Additional core services
# status_service removed - status_info table deprecated, status stored directly on entities as enum
# transaction_type_service removed - transaction_type_info table deprecated, transaction_type stored directly on transaction tables as enum
payment_method_service = CRUDService("payment_method", PaymentMethodDTO, "payment_method_id")
qr_code_service = CRUDService("qr_code", QRCodeDTO, "qr_code_id")

# Restaurant and plate services
restaurant_balance_service = CRUDService(
    "restaurant_balance_info",
    RestaurantBalanceDTO,
    "restaurant_id",
    institution_join_path=[
        ("INNER", "restaurant_info", "r", "restaurant_balance_info.restaurant_id = r.restaurant_id")
    ],
    institution_table_alias="r",
)
restaurant_holidays_service = CRUDService(
    "restaurant_holidays",
    RestaurantHolidaysDTO,
    "holiday_id",
    institution_join_path=[("INNER", "restaurant_info", "r", "restaurant_holidays.restaurant_id = r.restaurant_id")],
    institution_table_alias="r",
)
national_holiday_service = CRUDService("national_holidays", NationalHolidayDTO, "holiday_id")
plate_kitchen_days_service = CRUDService(
    "plate_kitchen_days",
    PlateKitchenDaysDTO,
    "plate_kitchen_day_id",
    institution_join_path=[
        ("INNER", "plate_info", "p", "plate_kitchen_days.plate_id = p.plate_id"),
        ("INNER", "restaurant_info", "r", "p.restaurant_id = r.restaurant_id"),
    ],
    institution_table_alias="r",
)
plate_pickup_live_service = CRUDService("plate_pickup_live", PlatePickupLiveDTO, "plate_pickup_id")


def get_plate_pickup_id_for_selection(plate_selection_id: UUID, db: psycopg2.extensions.connection) -> UUID | None:
    """Get plate_pickup_id for a plate selection if it has been promoted to live. Returns None if not yet promoted."""
    row = db_read(
        "SELECT plate_pickup_id FROM plate_pickup_live WHERE plate_selection_id = %s AND is_archived = FALSE",
        (str(plate_selection_id),),
        connection=db,
        fetch_one=True,
    )
    return UUID(str(row["plate_pickup_id"])) if row else None


def soft_delete_plate_pickups_by_plate_selection(
    plate_selection_id: UUID, modified_by: UUID, db: psycopg2.extensions.connection
) -> int:
    """Soft-delete all plate_pickup_live records for the given plate_selection_id. Returns count deleted."""
    rows = db_read(
        "SELECT plate_pickup_id FROM plate_pickup_live WHERE plate_selection_id = %s AND is_archived = FALSE",
        (str(plate_selection_id),),
        connection=db,
    )
    count = 0
    for row in rows or []:
        plate_pickup_live_service.soft_delete(row["plate_pickup_id"], modified_by, db)
        count += 1
    return count


# Additional methods for institution_settlement_service
def get_settlement_by_restaurant_and_period(
    restaurant_id: UUID, period_start: datetime, period_end: datetime, connection=None
) -> InstitutionSettlementDTO | None:
    """Get settlement for a restaurant and period (idempotency: skip if exists)."""
    query = """
        SELECT * FROM institution_settlement
        WHERE restaurant_id = %s AND period_start = %s AND period_end = %s
    """
    result = db_read(query, (str(restaurant_id), period_start, period_end), connection=connection, fetch_one=True)
    return InstitutionSettlementDTO(**result) if result else None


def get_settlements_by_entity_and_period(
    institution_entity_id: UUID, period_start: datetime, period_end: datetime, connection=None
) -> list[InstitutionSettlementDTO]:
    """Get all settlements for an entity and period (for aggregating into one bill)."""
    query = """
        SELECT * FROM institution_settlement
        WHERE institution_entity_id = %s AND period_start = %s AND period_end = %s
        ORDER BY restaurant_id
    """
    results = db_read(query, (str(institution_entity_id), period_start, period_end), connection=connection)
    return [InstitutionSettlementDTO(**row) for row in results] if results else []


def get_settlements_by_run_id(settlement_run_id: UUID, connection=None) -> list[InstitutionSettlementDTO]:
    """Get all settlements for a run (Phase 2: aggregate by entity and create bills)."""
    query = """
        SELECT * FROM institution_settlement
        WHERE settlement_run_id = %s
        ORDER BY institution_entity_id, restaurant_id
    """
    results = db_read(query, (str(settlement_run_id),), connection=connection)
    return [InstitutionSettlementDTO(**row) for row in results] if results else []


def get_settlements_by_bill_id(institution_bill_id: UUID, connection=None) -> list[InstitutionSettlementDTO]:
    """Get all settlements linked to a bill (for dashboard: restaurant count per bill)."""
    query = """
        SELECT s.* FROM institution_settlement s
        WHERE s.institution_bill_id = %s AND s.is_archived = FALSE
        ORDER BY s.restaurant_id
    """
    results = db_read(query, (str(institution_bill_id),), connection=connection)
    return [InstitutionSettlementDTO(**row) for row in results] if results else []


def get_bills_by_restaurant_and_period(
    restaurant_id: UUID, period_start: datetime, period_end: datetime, connection=None
) -> list[InstitutionBillDTO]:
    """Get bills that have a settlement for this restaurant in the given period (bills no longer have restaurant_id)."""
    query = """
        SELECT ibi.* FROM institution_bill_info ibi
        INNER JOIN institution_settlement s ON s.institution_bill_id = ibi.institution_bill_id
        WHERE s.restaurant_id = %s AND s.is_archived = FALSE
          AND ibi.is_archived = FALSE
          AND s.period_start < %s AND s.period_end > %s
    """
    results = db_read(query, (str(restaurant_id), period_end, period_start), connection=connection)
    return [InstitutionBillDTO(**row) for row in results] if results else []


# Additional methods for institution_bill_service
def get_institution_id_by_restaurant(restaurant_id: UUID, connection=None) -> UUID | None:
    """Get institution ID for a restaurant"""
    query = "SELECT institution_id FROM restaurant_info WHERE restaurant_id = %s AND is_archived = FALSE"
    result = db_read(query, (str(restaurant_id),), connection=connection, fetch_one=True)
    return UUID(result["institution_id"]) if result and result.get("institution_id") else None


def get_institution_id_by_entity(institution_entity_id: UUID, connection=None) -> UUID | None:
    """Get institution ID for an institution entity"""
    query = (
        "SELECT institution_id FROM institution_entity_info WHERE institution_entity_id = %s AND is_archived = FALSE"
    )
    result = db_read(query, (str(institution_entity_id),), connection=connection, fetch_one=True)
    return UUID(result["institution_id"]) if result and result.get("institution_id") else None


def get_institution_entity_by_institution(institution_id: UUID, connection=None) -> UUID | None:
    """Get institution entity ID for an institution"""
    query = (
        "SELECT institution_entity_id FROM institution_entity_info WHERE institution_id = %s AND is_archived = FALSE"
    )
    result = db_read(query, (str(institution_id),), connection=connection)
    return result[0]["institution_entity_id"] if result else None


def get_credit_cost_local_currency_of_most_expensive_plan_for_market(market_id: UUID, connection=None) -> float | None:
    """Return credit_cost_local_currency of the highest-price active plan in the market, or None. Used for explore fallback when user has no subscription in that market."""
    query = """
        SELECT credit_cost_local_currency FROM plan_info
        WHERE market_id = %s AND is_archived = FALSE AND status = 'active'
        ORDER BY price DESC
        LIMIT 1
    """
    row = db_read(query, (str(market_id),), connection=connection, fetch_one=True)
    return (
        float(row["credit_cost_local_currency"]) if row and row.get("credit_cost_local_currency") is not None else None
    )


def get_by_entity_and_period(
    entity_id: UUID, period_start: datetime, period_end: datetime, connection=None
) -> InstitutionBillDTO | None:
    """DEPRECATED: Use institution_bill_service.get_by_entity_and_period() instead.

    This function will be removed in a future version.
    Please update your code to use the service method:
        from app.services.crud_service import institution_bill_service
        institution_bill_service.get_by_entity_and_period(entity_id, period_start, period_end, db)
    """
    from app.utils.db import close_db_connection, get_db_connection

    if connection is None:
        connection = get_db_connection()
        try:
            return institution_bill_service.get_by_entity_and_period(entity_id, period_start, period_end, connection)
        finally:
            close_db_connection(connection)
    return institution_bill_service.get_by_entity_and_period(entity_id, period_start, period_end, connection)


def get_pending_bills(connection=None) -> list[InstitutionBillDTO]:
    """DEPRECATED: Use institution_bill_service.get_pending() instead.

    This function will be removed in a future version.
    Please update your code to use the service method:
        from app.services.crud_service import institution_bill_service
        institution_bill_service.get_pending(db)
    """
    from app.utils.db import close_db_connection, get_db_connection

    if connection is None:
        connection = get_db_connection()
        try:
            return institution_bill_service.get_pending(connection)
        finally:
            close_db_connection(connection)
    return institution_bill_service.get_pending(connection)


def mark_paid(bill_id: UUID, modified_by: UUID, connection=None) -> bool:
    """DEPRECATED: Use institution_bill_service.mark_paid() instead.

    Marks institution bill as paid (resolution only; no payment_id).
    """
    from app.utils.db import close_db_connection, get_db_connection

    if connection is None:
        connection = get_db_connection()
        try:
            return institution_bill_service.mark_paid(bill_id, modified_by, connection)
        finally:
            close_db_connection(connection)
    return institution_bill_service.mark_paid(bill_id, modified_by, connection)


def get_by_institution_and_period(
    institution_id: UUID, period_start: datetime, period_end: datetime, connection=None
) -> list[InstitutionBillDTO]:
    """DEPRECATED: Use institution_bill_service.get_by_institution_and_period() instead.

    This function will be removed in a future version.
    Please update your code to use the service method:
        from app.services.crud_service import institution_bill_service
        institution_bill_service.get_by_institution_and_period(institution_id, period_start, period_end, db)
    """
    from app.utils.db import close_db_connection, get_db_connection

    if connection is None:
        connection = get_db_connection()
        try:
            return institution_bill_service.get_by_institution_and_period(
                institution_id, period_start, period_end, connection
            )
        finally:
            close_db_connection(connection)
    return institution_bill_service.get_by_institution_and_period(institution_id, period_start, period_end, connection)


# Additional methods for plate_service
def get_plates_by_restaurant_address(address_id: UUID, db: psycopg2.extensions.connection) -> list[PlateDTO]:
    """Get all plates for restaurants at this address"""
    query = """
        SELECT p.* FROM plate_info p
        JOIN restaurant_info r ON p.restaurant_id = r.restaurant_id
        JOIN address_info a ON r.address_id = a.address_id
        WHERE a.address_id = %s AND p.is_archived = FALSE
        ORDER BY p.name
    """
    results = db_read(query, (str(address_id),), connection=db)
    return [PlateDTO(**row) for row in results]


def get_active_plates_today_by_restaurant_address(
    address_id: UUID, db: psycopg2.extensions.connection
) -> list[PlateDTO]:
    """Get active plates for today at restaurant address"""
    query = """
        SELECT DISTINCT p.* FROM plate_info p
        JOIN restaurant_info r ON p.restaurant_id = r.restaurant_id
        JOIN address_info a ON r.address_id = a.address_id
        JOIN plate_kitchen_days pkd ON p.plate_id = pkd.plate_id
        WHERE a.address_id = %s
        AND p.is_archived = FALSE
        AND p.status = 'active'
        AND pkd.is_archived = FALSE
        AND pkd.kitchen_day = UPPER(TO_CHAR(CURRENT_DATE, 'DAY'))
        ORDER BY p.name
    """
    results = db_read(query, (str(address_id),), connection=db)
    return [PlateDTO(**row) for row in results]


# Additional methods for credit_currency_service
def get_by_code(currency_code: str, db: psycopg2.extensions.connection) -> CreditCurrencyDTO | None:
    """DEPRECATED: Use credit_currency_service.get_by_code() instead.

    This function will be removed in a future version.
    Please update your code to use the service method:
        from app.services.crud_service import credit_currency_service
        credit_currency_service.get_by_code(currency_code, db)
    """
    return credit_currency_service.get_by_code(currency_code, db)


# Additional methods for QR code service
def get_by_restaurant_id(restaurant_id: UUID, db: psycopg2.extensions.connection) -> QRCodeDTO | None:
    """DEPRECATED: Use qr_code_service.get_by_restaurant() instead.

    This function will be removed in a future version.
    Please update your code to use the service method:
        from app.services.crud_service import qr_code_service
        qr_code_service.get_by_restaurant(restaurant_id, db)
    """
    return qr_code_service.get_by_restaurant(restaurant_id, db)


# Additional methods for plate selection service
def get_all_by_user(user_id: UUID, db: psycopg2.extensions.connection) -> list[PlateSelectionDTO]:
    """Get all plate selections by user"""
    query = (
        "SELECT * FROM plate_selection_info WHERE user_id = %s AND is_archived = FALSE ORDER BY plate_selection_id DESC"
    )
    results = db_read(query, (str(user_id),), connection=db)
    return [PlateSelectionDTO(**row) for row in results]


# Additional methods for subscription service
def get_subscription_by_user_and_market(
    user_id: UUID,
    market_id: UUID,
    db: psycopg2.extensions.connection,
) -> SubscriptionDTO | None:
    """
    Get the non-archived subscription for a user in a given market, if any.
    At most one exists per (user_id, market_id) due to unique index.
    """
    query = """
        SELECT * FROM subscription_info
        WHERE user_id = %s AND market_id = %s AND is_archived = FALSE
        LIMIT 1
    """
    result = db_read(query, (str(user_id), str(market_id)), connection=db, fetch_one=True)
    return SubscriptionDTO(**result) if result else None


def get_by_user_id(user_id: UUID, db: psycopg2.extensions.connection) -> SubscriptionDTO | None:
    """DEPRECATED: Use subscription_service.get_by_user() instead.

    This function will be removed in a future version.
    Please update your code to use the service method:
        from app.services.crud_service import subscription_service
        subscription_service.get_by_user(user_id, db)
    """
    return subscription_service.get_by_user(user_id, db)


def update_balance(
    subscription_id: UUID, balance_change: float, db: psycopg2.extensions.connection, *, commit: bool = True
) -> bool:
    """
    Update subscription balance.

    Args:
        subscription_id: Subscription ID
        balance_change: Amount to change balance by (can be negative for deductions)
        db: Database connection
        commit: Whether to commit immediately after update (default: True).
                Set to False for atomic multi-operation transactions.

    Returns:
        True if balance updated successfully, False otherwise
    """
    with db.cursor() as cursor:
        cursor.execute(
            """
            UPDATE subscription_info
            SET balance = balance + %s,
                modified_date = CURRENT_TIMESTAMP
            WHERE subscription_id = %s AND is_archived = FALSE
        """,
            (balance_change, str(subscription_id)),
        )

        # Only commit if requested (default True for backward compatibility)
        if commit:
            db.commit()

        return cursor.rowcount > 0


# Additional methods for client transaction service
def mark_plate_selection_complete(
    transaction_id: UUID, modified_by: UUID, db: psycopg2.extensions.connection, *, commit: bool = True
) -> bool:
    """
    Mark the client transaction created during plate selection as complete.

    Args:
        transaction_id: Client transaction ID
        modified_by: User ID making the change
        db: Database connection
        commit: Whether to commit immediately after update (default: True).
                Set to False for atomic multi-operation transactions.

    Returns:
        True if transaction marked complete successfully, False otherwise
    """
    with db.cursor() as cursor:
        cursor.execute(
            """
            UPDATE client_transaction
            SET status = 'completed',
                modified_by = %s,
                modified_date = CURRENT_TIMESTAMP
            WHERE transaction_id = %s AND is_archived = FALSE
            """,
            (str(modified_by), str(transaction_id)),
        )

        # Only commit if requested (default True for backward compatibility)
        if commit:
            db.commit()

        return cursor.rowcount > 0


# Additional methods for restaurant transaction service
def create_with_conservative_balance_update(
    data: dict, db: psycopg2.extensions.connection, *, commit: bool = True
) -> RestaurantTransactionDTO:
    """
    Create restaurant transaction with conservative balance update (discounted amount).

    Both operations (transaction creation and balance update) are performed atomically
    when commit=False - either both succeed or both are rolled back.

    Args:
        data: Restaurant transaction data dictionary
        db: Database connection
        commit: Whether to commit immediately after operations (default: True).
                Set to False for atomic multi-operation transactions.

    Returns:
        Created RestaurantTransactionDTO or None if creation fails

    Raises:
        HTTPException: If transaction creation or balance update fails (when commit=False)
    """
    try:
        # Create the transaction first (commit=False for atomic transaction)
        transaction = restaurant_transaction_service.create(data, db, commit=False)

        if not transaction:
            if not commit:
                db.rollback()
            return None

        # Update restaurant balance with the discounted amount (conservative estimate)
        # commit=False for atomic transaction
        balance_updated = update_balance_on_transaction_creation(
            transaction.restaurant_id, float(transaction.final_amount), db, commit=False
        )

        if not balance_updated:
            if not commit:
                db.rollback()
            log_warning(f"Failed to update restaurant balance for transaction {transaction.transaction_id}")
            return None

        # Commit both operations atomically if requested
        if commit:
            db.commit()
            log_info(
                f"Restaurant balance updated with conservative amount {transaction.final_amount} for transaction {transaction.transaction_id}"
            )
        else:
            log_info("Restaurant transaction created and balance update prepared (commit deferred)")

        return transaction
    except Exception as e:
        if not commit:
            db.rollback()
        log_error(f"Error creating restaurant transaction with balance update: {e}")
        raise


# Additional methods for restaurant transaction service
def get_by_plate_selection_id(
    plate_selection_id: UUID, db: psycopg2.extensions.connection
) -> RestaurantTransactionDTO | None:
    """DEPRECATED: Use restaurant_transaction_service.get_by_plate_selection() instead.

    This function will be removed in a future version.
    Please update your code to use the service method:
        from app.services.crud_service import restaurant_transaction_service
        restaurant_transaction_service.get_by_plate_selection(plate_selection_id, db)
    """
    return restaurant_transaction_service.get_by_plate_selection(plate_selection_id, db)


def update_balance_on_transaction_creation(
    restaurant_id: UUID, amount: float, db: psycopg2.extensions.connection, *, commit: bool = True
) -> bool:
    """
    Update restaurant balance when transaction is created (with discounted amount).

    Args:
        restaurant_id: Restaurant ID
        amount: Amount to add to balance (discounted amount)
        db: Database connection
        commit: Whether to commit immediately after update (default: True).
                Set to False for atomic multi-operation transactions.

    Returns:
        True if balance updated successfully, False otherwise
    """
    with db.cursor() as cursor:
        cursor.execute(
            """
            UPDATE restaurant_balance_info
            SET balance = balance + %s,
                transaction_count = transaction_count + 1,
                modified_date = CURRENT_TIMESTAMP
            WHERE restaurant_id = %s AND is_archived = FALSE
        """,
            (amount, str(restaurant_id)),
        )

        # Only commit if requested (default True for backward compatibility)
        if commit:
            db.commit()

        return cursor.rowcount > 0


def update_balance_on_arrival(
    restaurant_id: UUID, amount: float, db: psycopg2.extensions.connection, *, commit: bool = True
) -> bool:
    """
    Update restaurant balance on customer arrival (add difference to reach full amount).

    Args:
        restaurant_id: Restaurant ID
        amount: Amount to add to balance (difference between full and discounted amount)
        db: Database connection
        commit: Whether to commit immediately after update (default: True).
                Set to False for atomic multi-operation transactions.

    Returns:
        True if balance updated successfully, False otherwise
    """
    with db.cursor() as cursor:
        cursor.execute(
            """
            UPDATE restaurant_balance_info
            SET balance = balance + %s,
                modified_date = CURRENT_TIMESTAMP
            WHERE restaurant_id = %s AND is_archived = FALSE
        """,
            (amount, str(restaurant_id)),
        )

        # Only commit if requested (default True for backward compatibility)
        if commit:
            db.commit()

        return cursor.rowcount > 0


def mark_collected_with_balance_update(
    transaction_id: UUID,
    restaurant_id: UUID,
    additional_amount: float,
    db: psycopg2.extensions.connection,
    *,
    commit: bool = True,
) -> bool:
    """
    Mark transaction as collected and update balance.

    Args:
        transaction_id: Restaurant transaction ID
        restaurant_id: Restaurant ID
        additional_amount: Additional amount to add to balance (if any)
        db: Database connection
        commit: Whether to commit immediately after update (default: True).
                Set to False for atomic multi-operation transactions.

    Returns:
        True if transaction marked and balance updated successfully, False otherwise
    """

    # First update the transaction
    with db.cursor() as cursor:
        cursor.execute(
            """
            UPDATE restaurant_transaction
            SET was_collected = TRUE,
                modified_date = CURRENT_TIMESTAMP
            WHERE transaction_id = %s AND is_archived = FALSE
        """,
            (str(transaction_id),),
        )

        # Only commit if requested (default True for backward compatibility)
        if commit:
            db.commit()

        transaction_updated = cursor.rowcount > 0

    # Then update the balance with the additional amount (difference between discounted and full amount)
    if additional_amount > 0:
        balance_updated = update_balance_on_arrival(restaurant_id, additional_amount, db, commit=commit)
        return transaction_updated and balance_updated

    return transaction_updated


def get_client_bill_by_subscription_payment(
    subscription_payment_id: UUID,
    db: psycopg2.extensions.connection,
) -> ClientBillDTO | None:
    """Get client bill by subscription_payment_id (for idempotency in confirm-payment/webhook)."""
    result = db_read(
        "SELECT * FROM client_bill_info WHERE subscription_payment_id = %s AND is_archived = FALSE",
        (str(subscription_payment_id),),
        connection=db,
        fetch_one=True,
    )
    return ClientBillDTO(**result) if result else None


# Additional methods for restaurant balance service
def get_by_restaurant(restaurant_id: UUID, db: psycopg2.extensions.connection) -> RestaurantBalanceDTO | None:
    """DEPRECATED: Use restaurant_balance_service.get_by_restaurant() instead.

    This function will be removed in a future version.
    Please update your code to use the service method:
        from app.services.crud_service import restaurant_balance_service
        restaurant_balance_service.get_by_restaurant(restaurant_id, db)
    """
    return restaurant_balance_service.get_by_restaurant(restaurant_id, db)


def update_balance_with_monetary_amount(
    restaurant_id: UUID, amount: float, currency_code: str, db: psycopg2.extensions.connection
) -> bool:
    """DEPRECATED: Use restaurant_balance_service.update_with_monetary_amount() instead.

    This function will be removed in a future version.
    Please update your code to use the service method:
        from app.services.crud_service import restaurant_balance_service
        restaurant_balance_service.update_with_monetary_amount(restaurant_id, amount, currency_code, db)
    """
    return restaurant_balance_service.update_with_monetary_amount(restaurant_id, amount, currency_code, db)


def get_current_balance_event_id(restaurant_id: UUID, db: psycopg2.extensions.connection) -> UUID | None:
    """DEPRECATED: Use restaurant_balance_service.get_current_event_id() instead.

    This function will be removed in a future version.
    Please update your code to use the service method:
        from app.services.crud_service import restaurant_balance_service
        restaurant_balance_service.get_current_event_id(restaurant_id, db)
    """
    return restaurant_balance_service.get_current_event_id(restaurant_id, db)


def reset_restaurant_balance(restaurant_id: UUID, db: psycopg2.extensions.connection, *, commit: bool = True) -> bool:
    """DEPRECATED: Use restaurant_balance_service.reset_balance() instead.

    This function will be removed in a future version.
    Please update your code to use the service method:
        from app.services.crud_service import restaurant_balance_service
        restaurant_balance_service.reset_balance(restaurant_id, db, commit=commit)
    """
    return restaurant_balance_service.reset_balance(restaurant_id, db, commit=commit)


def create_restaurant_balance_record(
    restaurant_id: UUID,
    currency_metadata_id: UUID,
    currency_code: str,
    modified_by: UUID,
    db: psycopg2.extensions.connection,
    *,
    commit: bool = True,
) -> bool:
    """
    Create initial restaurant balance record for a new restaurant.

    Args:
        restaurant_id: Restaurant ID
        currency_metadata_id: Credit currency ID
        currency_code: Currency code
        modified_by: User ID who is creating the record
        db: Database connection
        commit: Whether to commit immediately after insert (default: True).
                Set to False for atomic multi-operation transactions.

    Returns:
        True if balance record created successfully, False otherwise
    """

    """DEPRECATED: Use restaurant_balance_service.create_balance_record() instead.

    This function will be removed in a future version.
    Please update your code to use the service method:
        from app.services.crud_service import restaurant_balance_service
        restaurant_balance_service.create_balance_record(restaurant_id, currency_metadata_id,
                                                         currency_code, modified_by, db, commit=commit)
    """
    return restaurant_balance_service.create_balance_record(
        restaurant_id, currency_metadata_id, currency_code, modified_by, db, commit=commit
    )


# Additional methods for institution entity service
def get_institution_entities_by_institution(
    institution_id: UUID, db: psycopg2.extensions.connection
) -> list[InstitutionEntityDTO]:
    """Get institution entities by institution ID"""
    query = "SELECT * FROM institution_entity_info WHERE institution_id = %s AND is_archived = FALSE"
    results = db_read(query, (str(institution_id),), connection=db)
    return [InstitutionEntityDTO(**row) for row in results]


# Additional methods for national holiday service
def is_holiday(country: str, date, db: psycopg2.extensions.connection) -> bool:
    """Check if date is a national holiday for country (uses national_holidays.country_code)."""
    query = "SELECT 1 FROM national_holidays WHERE country_code = %s AND holiday_date = %s AND is_archived = FALSE"
    result = db_read(query, (country, date), connection=db, fetch_one=True)
    return result is not None


# Additional methods for plate kitchen days service
def get_by_restaurant_and_day(
    restaurant_id: UUID, day: str, db: psycopg2.extensions.connection
) -> PlateKitchenDaysDTO | None:
    """Get plate kitchen day by restaurant and day"""
    query = "SELECT pkd.* FROM plate_kitchen_days_info pkd JOIN plate_info p ON pkd.plate_id = p.plate_id WHERE p.restaurant_id = %s AND pkd.kitchen_day = %s AND pkd.is_archived = FALSE AND p.is_archived = FALSE"
    result = db_read(query, (restaurant_id, day), connection=db, fetch_one=True)
    return PlateKitchenDaysDTO(**result) if result else None


# Additional methods for plate service
def get_plates_by_user_city(user_address_id: UUID, db: psycopg2.extensions.connection) -> list[PlateDTO]:
    """Get all plates in same city as user's address"""
    # Get the city for the user's address
    address_query = "SELECT city FROM address_info WHERE address_id = %s AND is_archived = FALSE"
    address_result = db_read(address_query, (user_address_id,), connection=db, fetch_one=True)
    if not address_result:
        return []
    city = address_result["city"]

    # Query plates for restaurants in that city
    query = """
        SELECT p.plate_id, p.product_id, p.restaurant_id, p.price, p.credit, p.delivery_time_minutes, p.is_archived, p.status, p.created_date, p.modified_by, p.modified_date
        FROM plate_info p
        JOIN restaurant_info r ON p.restaurant_id = r.restaurant_id
        JOIN address_info a ON r.address_id = a.address_id
        WHERE a.city = %s AND p.is_archived = %s
    """
    results = db_read(query, (city, False), connection=db)
    return [PlateDTO(**row) for row in results] if results else []


def get_active_plates_today_by_user_city(address_id: UUID, db: psycopg2.extensions.connection) -> list[PlateDTO]:
    """Get active plates for today in user's city (with holiday logic)"""

    from app.services.date_service import get_effective_current_date, get_effective_current_day

    # Get the user's address to get city and timezone
    address_query = "SELECT city, timezone FROM address_info WHERE address_id = %s AND is_archived = FALSE"
    address_result = db_read(address_query, (address_id,), connection=db, fetch_one=True)
    if not address_result:
        return []
    city = address_result["city"]
    timezone_str = address_result["timezone"]

    # Calculate the effective current day
    current_day = get_effective_current_day(timezone_str)
    get_effective_current_date(timezone_str).date()

    # Get all plates for the current day
    query = """
        SELECT DISTINCT p.plate_id, p.product_id, p.restaurant_id, p.price, p.credit, p.delivery_time_minutes, p.is_archived, p.status, p.created_date, p.modified_by, p.modified_date
        FROM plate_info p
        JOIN restaurant_info r ON p.restaurant_id = r.restaurant_id
        JOIN address_info a ON r.address_id = a.address_id
        JOIN plate_kitchen_days pkd ON p.plate_id = pkd.plate_id
        WHERE a.city = %s
          AND p.is_archived = %s
          AND p.status = %s
          AND pkd.kitchen_day = %s
          AND pkd.is_archived = %s
    """
    results = db_read(query, (city, False, "active", current_day, False), connection=db)
    if not results:
        return []

    # Filter out plates from restaurants that are closed for holidays
    available_plates = []
    for row in results:
        plate = PlateDTO(**row)
        row[2]  # restaurant_id is at index 2 in the query
        # TODO: Check if restaurant is closed for holiday today
        available_plates.append(plate)
    return available_plates


# Additional methods for restaurant transaction service
def mark_collected(
    transaction_id: UUID, collected_timestamp: datetime, modified_by: UUID, db: psycopg2.extensions.connection
) -> bool:
    """DEPRECATED: Use restaurant_transaction_service.mark_collected() instead.

    This function will be removed in a future version.
    Please update your code to use the service method:
        from app.services.crud_service import restaurant_transaction_service
        restaurant_transaction_service.mark_collected(transaction_id, collected_timestamp, modified_by, db)
    """
    return restaurant_transaction_service.mark_collected(transaction_id, collected_timestamp, modified_by, db)


def update_final_amount(
    transaction_id: UUID, final_amount: float, modified_by: UUID, db: psycopg2.extensions.connection
) -> bool:
    """DEPRECATED: Use restaurant_transaction_service.update_final_amount() instead.

    This function will be removed in a future version.
    Please update your code to use the service method:
        from app.services.crud_service import restaurant_transaction_service
        restaurant_transaction_service.update_final_amount(transaction_id, final_amount, modified_by, db)
    """
    return restaurant_transaction_service.update_final_amount(transaction_id, final_amount, modified_by, db)


def update_transaction_arrival_time(
    transaction_id: UUID, arrival_time: datetime, modified_by: UUID, db: psycopg2.extensions.connection
) -> bool:
    """DEPRECATED: Use restaurant_transaction_service.update_arrival_time() instead.

    This function will be removed in a future version.
    Please update your code to use the service method:
        from app.services.crud_service import restaurant_transaction_service
        restaurant_transaction_service.update_arrival_time(transaction_id, arrival_time, modified_by, db)
    """
    return restaurant_transaction_service.update_arrival_time(transaction_id, arrival_time, modified_by, db)


def mark_transaction_as_collected(
    transaction_id: UUID, collected_timestamp: datetime, modified_by: UUID, db: psycopg2.extensions.connection
) -> bool:
    """Mark transaction as collected"""
    with db.cursor() as cursor:
        cursor.execute(
            """
            UPDATE restaurant_transaction
            SET was_collected = TRUE,
                collected_timestamp = %s,
                modified_date = CURRENT_TIMESTAMP,
                modified_by = %s
            WHERE transaction_id = %s AND is_archived = FALSE
        """,
            (collected_timestamp, modified_by, str(transaction_id)),
        )
        db.commit()
        return cursor.rowcount > 0


# Additional methods for pickup preferences service
def find_matching_preferences(preference_id: UUID, db: psycopg2.extensions.connection) -> list[PickupPreferencesDTO]:
    """Find preferences that can be matched with the given preference"""
    # TODO: Implement pickup preferences matching logic
    return []


# Additional methods for geolocation service
def get_by_address_id(address_id: UUID, db: psycopg2.extensions.connection) -> GeolocationDTO | None:
    """DEPRECATED: Use geolocation_service.get_by_address() instead.

    This function will be removed in a future version.
    Please update your code to use the service method:
        from app.services.crud_service import geolocation_service
        geolocation_service.get_by_address(address_id, db)
    """
    return geolocation_service.get_by_address(address_id, db)


# Additional methods for plate service
def get_plates_by_currency_metadata_id(
    currency_metadata_id: UUID, db: psycopg2.extensions.connection
) -> list[PlateDTO]:
    """Get all non-archived plates for a specific credit currency"""
    query = """
        SELECT * FROM plate_info
        WHERE currency_metadata_id = %s AND is_archived = FALSE
    """
    results = db_read(query, (str(currency_metadata_id),), connection=db)
    return [PlateDTO(**row) for row in results] if results else []


# =============================================================================
# DISCRETIONARY CREDIT SERVICES
# =============================================================================

# Discretionary credit services
discretionary_service = CRUDService("discretionary_info", DiscretionaryDTO, "discretionary_id")
discretionary_resolution_service = CRUDService(
    "discretionary_resolution_info", DiscretionaryResolutionDTO, "approval_id"
)

# Ingredient catalog — global, no institution scoping
ingredient_catalog_service = CRUDService("ingredient_catalog", IngredientCatalogDTO, "ingredient_id")

# Referral services
referral_config_service = CRUDService("referral_config", ReferralConfigDTO, "referral_config_id")
referral_info_service = CRUDService("referral_info", ReferralInfoDTO, "referral_id")

# Workplace group services
workplace_group_service = CRUDService("workplace_group", WorkplaceGroupDTO, "workplace_group_id")
