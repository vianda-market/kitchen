# app/services/enriched_service.py
"""
Generic Enriched Service - Eliminates code duplication across enriched endpoints.

This service provides generic enriched query operations that can be used for any
enriched endpoint type, eliminating the need for duplicate enriched query logic
across 13+ enriched endpoint functions.

Benefits:
- Single implementation for all enriched query operations
- No code duplication across enriched endpoints
- Consistent error handling
- Type-safe operations with generics
- Easy to extend with new enriched endpoints
"""

from typing import TypeVar, Generic, Optional, List, Any, Tuple, Dict, Callable
from uuid import UUID
from datetime import datetime
import psycopg2.extensions
from fastapi import HTTPException
from pydantic import BaseModel
from app.utils.db import db_read
from app.utils.log import log_info, log_error
from app.security.institution_scope import InstitutionScope

T = TypeVar('T', bound=BaseModel)


class EnrichedService(Generic[T]):
    """
    Generic enriched service that provides common enriched query operations
    for any enriched endpoint type, eliminating code duplication.
    
    Similar to CRUDService but specialized for enriched queries with JOINs,
    computed fields, and complex filtering.
    """
    
    def __init__(
        self,
        base_table: str,
        table_alias: str,
        id_column: str,
        schema_class: type[T],
        *,
        institution_column: Optional[str] = None,
        institution_table_alias: Optional[str] = None,
        default_order_by: Optional[str] = None
    ):
        """
        Initialize the enriched service for a specific entity.
        
        Args:
            base_table: Name of the main database table (e.g., "institution_entity_info")
            table_alias: Alias for the main table in queries (e.g., "ie")
            id_column: Name of the primary key column (e.g., "institution_entity_id")
            schema_class: The Pydantic schema class for responses
            institution_column: Column name for institution_id filtering (e.g., "institution_id").
                Used for WHERE clause filtering (institution scoping), NOT for selecting columns.
                Set to None if no institution scoping is needed.
            institution_table_alias: Table alias where institution_column exists.
                - If institution_id is on the base table: use table_alias (e.g., "u" for user_info)
                - If institution_id is on a joined table: use the joined table alias (e.g., "ie" for institution_entity_info)
                - If institution_column is None: this is ignored
            default_order_by: Default ORDER BY clause (defaults to table_alias.id_column DESC for newest first)
        """
        self.base_table = base_table
        self.table_alias = table_alias
        self.id_column = id_column
        self.schema_class = schema_class
        self.institution_column = institution_column
        self.institution_table_alias = institution_table_alias or table_alias
        self.default_order_by = default_order_by if default_order_by is not None else f"{table_alias}.{id_column} DESC"
    
    def _build_where_clause(
        self,
        include_archived: bool = False,
        scope: Optional[InstitutionScope] = None,
        additional_conditions: Optional[List[Tuple[str, Any]]] = None
    ) -> Tuple[str, List[Any]]:
        """
        Build WHERE clause and parameters for enriched queries.
        
        Args:
            include_archived: Whether to include archived records
            scope: Optional institution scope for filtering
            additional_conditions: List of (condition, param) tuples for custom conditions
            
        Returns:
            Tuple of (where_clause, params)
        """
        conditions = []
        params: List[Any] = []
        
        # Filter by archived status
        if not include_archived:
            conditions.append(f"{self.table_alias}.is_archived = FALSE")
        
        # Apply institution scoping (for Suppliers - filter by institution)
        if scope and not scope.is_global and scope.institution_id and self.institution_column:
            conditions.append(f"{self.institution_table_alias}.{self.institution_column} = %s::uuid")
            params.append(str(scope.institution_id))
        
        # Add custom conditions
        if additional_conditions:
            for condition, param in additional_conditions:
                conditions.append(condition)
                if param is not None:
                    # psycopg2 can't adapt uuid.UUID; convert to str for query params
                    params.append(str(param) if isinstance(param, UUID) else param)
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return where_clause, params
    
    def _convert_uuids_to_strings(self, row_dict: dict) -> dict:
        """
        Convert UUID objects to strings in a row dictionary for Pydantic validation.
        
        Args:
            row_dict: Dictionary from database query
            
        Returns:
            Dictionary with UUIDs converted to strings
        """
        converted = {}
        for key, value in row_dict.items():
            if isinstance(value, UUID):
                converted[key] = str(value)
            else:
                converted[key] = value
        return converted
    
    def _execute_query(
        self,
        query: str,
        params: Optional[List[Any]],
        db: psycopg2.extensions.connection,
        fetch_one: bool = False
    ) -> Optional[List[dict]]:
        """
        Execute enriched query with standard error handling.
        
        Args:
            query: SQL query string
            params: Query parameters
            db: Database connection
            fetch_one: Whether to fetch single result
            
        Returns:
            List of dictionaries or None if fetch_one and no result
        """
        try:
            results = db_read(
                query,
                tuple(params) if params else None,
                connection=db,
                fetch_one=fetch_one
            )
            
            if fetch_one:
                return [results] if results else None
            return results if results else []
        except Exception as e:
            log_error(f"Error executing enriched query: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to execute enriched query: {str(e)}"
            )
    
    def get_enriched(
        self,
        db: psycopg2.extensions.connection,
        *,
        select_fields: List[str],
        joins: List[Tuple[str, str, str, str]],  # (join_type, table, alias, join_condition)
        scope: Optional[InstitutionScope] = None,
        include_archived: bool = False,
        additional_conditions: Optional[List[Tuple[str, Any]]] = None,
        order_by: Optional[str] = None,
        row_transform: Optional[Callable[[dict], dict]] = None,
    ) -> List[T]:
        """
        Get all enriched records with JOINs and filtering.
        
        Args:
            db: Database connection
            select_fields: List of SELECT fields (e.g., ["user_id", "i.name as institution_name"])
            joins: List of JOIN clauses as (table, alias, condition) tuples
            scope: Optional institution scope for filtering
            include_archived: Whether to include archived records
            additional_conditions: List of (condition, param) tuples for custom WHERE conditions
            order_by: ORDER BY clause (defaults to self.default_order_by)
            
        Returns:
            List of enriched schema objects
        """
        try:
            # Build WHERE clause
            where_clause, params = self._build_where_clause(
                include_archived=include_archived,
                scope=scope,
                additional_conditions=additional_conditions
            )
            
            # Build JOIN clauses
            join_clauses = []
            for join_type, table, alias, condition in joins:
                join_clauses.append(f"{join_type} JOIN {table} {alias} ON {condition}")
            
            # Build ORDER BY
            order_by_clause = order_by or self.default_order_by
            
            # Build complete query
            query = f"""
                SELECT 
                    {', '.join(select_fields)}
                FROM {self.base_table} {self.table_alias}
                {' '.join(join_clauses)}
                {where_clause}
                ORDER BY {order_by_clause}
            """
            
            # Execute query
            results = self._execute_query(query, params, db, fetch_one=False)
            
            if not results:
                return []
            
            # Convert UUIDs and validate schemas
            enriched_items = []
            for row in results:
                row_dict = dict(row)
                row_dict = self._convert_uuids_to_strings(row_dict)
                if row_transform:
                    row_dict = row_transform(row_dict)
                enriched_items.append(self.schema_class(**row_dict))
            
            return enriched_items
            
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            log_error(f"Error getting enriched {self.base_table}: {e}\nTraceback: {error_trace}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get enriched {self.base_table}: {str(e)}"
            )
    
    def get_enriched_by_id(
        self,
        record_id: UUID,
        db: psycopg2.extensions.connection,
        *,
        select_fields: List[str],
        joins: List[Tuple[str, str, str, str]],  # (join_type, table, alias, join_condition)
        scope: Optional[InstitutionScope] = None,
        include_archived: bool = False,
        additional_conditions: Optional[List[Tuple[str, Any]]] = None,
        row_transform: Optional[Callable[[dict], dict]] = None,
    ) -> Optional[T]:
        """
        Get a single enriched record by ID with JOINs and filtering.
        
        Args:
            record_id: Record ID to fetch
            db: Database connection
            select_fields: List of SELECT fields
            joins: List of JOIN clauses as (join_type, table, alias, condition) tuples
            scope: Optional institution scope for filtering
            include_archived: Whether to include archived records
            additional_conditions: List of (condition, param) tuples for custom WHERE conditions
            
        Returns:
            Enriched schema object or None if not found
        """
        try:
            # Add ID condition
            id_condition = (f"{self.table_alias}.{self.id_column} = %s", str(record_id))
            conditions = [id_condition]
            if additional_conditions:
                conditions.extend(additional_conditions)
            
            # Build WHERE clause
            where_clause, params = self._build_where_clause(
                include_archived=include_archived,
                scope=scope,
                additional_conditions=conditions
            )
            
            # Build JOIN clauses
            join_clauses = []
            for join_type, table, alias, condition in joins:
                join_clauses.append(f"{join_type} JOIN {table} {alias} ON {condition}")
            
            # Build complete query
            query = f"""
                SELECT 
                    {', '.join(select_fields)}
                FROM {self.base_table} {self.table_alias}
                {' '.join(join_clauses)}
                {where_clause}
            """
            
            # Execute query
            results = self._execute_query(query, params, db, fetch_one=True)
            
            if not results:
                return None
            
            # Convert UUIDs and validate schema
            row_dict = dict(results[0])
            row_dict = self._convert_uuids_to_strings(row_dict)
            if row_transform:
                row_dict = row_transform(row_dict)
            return self.schema_class(**row_dict)
            
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            log_error(f"Error getting enriched {self.base_table} by ID {record_id}: {e}\nTraceback: {error_trace}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get enriched {self.base_table}: {str(e)}"
            )

