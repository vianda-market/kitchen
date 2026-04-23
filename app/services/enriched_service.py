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

from collections.abc import Callable
from typing import Any, Generic, TypeVar, Union
from uuid import UUID

import psycopg2.extensions
from fastapi import HTTPException
from pydantic import BaseModel

from app.security.institution_scope import InstitutionScope
from app.utils.db import db_read
from app.utils.log import log_error
from app.utils.pagination import PaginatedList

T = TypeVar("T", bound=BaseModel)


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
        institution_column: str | None = None,
        institution_table_alias: str | None = None,
        default_order_by: str | None = None,
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
        scope: InstitutionScope | None = None,
        additional_conditions: list[tuple[str, list]] | None = None,
    ) -> tuple[str, list[Any]]:
        """
        Build WHERE clause and parameters for enriched queries.

        Args:
            include_archived: Whether to include archived records
            scope: Optional institution scope for filtering
            additional_conditions: List of (condition, list_of_params) tuples for custom conditions

        Returns:
            Tuple of (where_clause, params)
        """
        conditions = []
        params: list[Any] = []

        # Filter by archived status
        if not include_archived:
            conditions.append(f"{self.table_alias}.is_archived = FALSE")

        # Apply institution scoping (for Suppliers - filter by institution)
        if scope and not scope.is_global and scope.institution_id and self.institution_column:
            conditions.append(f"{self.institution_table_alias}.{self.institution_column} = %s::uuid")
            params.append(str(scope.institution_id))

        # Add custom conditions
        if additional_conditions:
            for condition, param_list in additional_conditions:
                conditions.append(condition)
                if param_list is not None:
                    # param_list is now a list of parameters for this condition
                    params.extend(param_list)

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
        self, query: str, params: list[Any] | None, db: psycopg2.extensions.connection, fetch_one: bool = False
    ) -> list[dict] | None:
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
            results = db_read(query, tuple(params) if params else None, connection=db, fetch_one=fetch_one)

            if fetch_one:
                return [results] if results else None
            return results if results else []
        except Exception as e:
            log_error(f"Error executing enriched query: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to execute enriched query: {str(e)}") from None

    def get_enriched(
        self,
        db: psycopg2.extensions.connection,
        *,
        select_fields: list[str],
        joins: list[tuple[str, str, str, str]],  # (join_type, table, alias, join_condition)
        scope: InstitutionScope | None = None,
        include_archived: bool = False,
        additional_conditions: list[tuple[str, list]] | None = None,
        order_by: str | None = None,
        row_transform: Callable[[dict], dict] | None = None,
        page: int | None = None,
        page_size: int | None = None,
        distinct: bool = False,
    ) -> Union[list[T], "PaginatedList[T]"]:
        """
        Get all enriched records with JOINs and filtering.

        Args:
            db: Database connection
            select_fields: List of SELECT fields (e.g., ["user_id", "i.name as institution_name"])
            joins: List of JOIN clauses as (table, alias, condition) tuples
            scope: Optional institution scope for filtering
            include_archived: Whether to include archived records
            additional_conditions: List of (condition, list_of_params) tuples for custom WHERE conditions
            order_by: ORDER BY clause (defaults to self.default_order_by)
            page: Optional 1-based page number (activates pagination when both page and page_size are set)
            page_size: Optional rows per page (clamped to 1-100)
            distinct: When True, emits SELECT DISTINCT to eliminate duplicate rows produced by
                1:N filter-only JOINs (e.g. restaurant × kitchen_days). Only set to True when
                the joins list includes a 1:N table that is not represented in select_fields.

        Returns:
            List of enriched schema objects, or PaginatedList with .total_count when paginated
        """
        paginate = page is not None and page_size is not None
        if paginate:
            page_size = max(1, min(page_size, 100))
            page = max(1, page)
            offset = (page - 1) * page_size

        try:
            # Build WHERE clause
            where_clause, params = self._build_where_clause(
                include_archived=include_archived, scope=scope, additional_conditions=additional_conditions
            )

            # Build JOIN clauses
            join_clauses = []
            for join_type, table, alias, condition in joins:
                join_clauses.append(f"{join_type} JOIN {table} {alias} ON {condition}")

            # Build ORDER BY
            order_by_clause = order_by or self.default_order_by

            # Run COUNT query before pagination LIMIT/OFFSET
            select_distinct = "SELECT DISTINCT" if distinct else "SELECT"
            count_expr = f"COUNT(DISTINCT {self.table_alias}.{self.id_column})" if distinct else "COUNT(*)"
            total_count = 0
            if paginate:
                count_query = f"""
                    SELECT {count_expr}
                    FROM {self.base_table} {self.table_alias}
                    {" ".join(join_clauses)}
                    {where_clause}
                """
                count_result = self._execute_query(count_query, list(params), db, fetch_one=True)
                total_count = count_result[0]["count"] if count_result else 0

            # Build complete query
            pagination_clause = ""
            query_params = list(params)
            if paginate:
                pagination_clause = "LIMIT %s OFFSET %s"
                query_params.extend([page_size, offset])

            query = f"""
                {select_distinct}
                    {", ".join(select_fields)}
                FROM {self.base_table} {self.table_alias}
                {" ".join(join_clauses)}
                {where_clause}
                ORDER BY {order_by_clause}
                {pagination_clause}
            """

            # Execute query
            results = self._execute_query(query, query_params, db, fetch_one=False)

            if not results:
                if paginate:
                    return PaginatedList([], total_count=total_count)
                return []

            # Convert UUIDs and validate schemas
            enriched_items = []
            for row in results:
                row_dict = dict(row)
                row_dict = self._convert_uuids_to_strings(row_dict)
                if row_transform:
                    row_dict = row_transform(row_dict)
                enriched_items.append(self.schema_class(**row_dict))

            if paginate:
                return PaginatedList(enriched_items, total_count=total_count)
            return enriched_items

        except HTTPException:
            raise
        except Exception as e:
            import traceback

            error_trace = traceback.format_exc()
            log_error(f"Error getting enriched {self.base_table}: {e}\nTraceback: {error_trace}")
            raise HTTPException(status_code=500, detail=f"Failed to get enriched {self.base_table}: {str(e)}") from None

    def get_enriched_by_id(
        self,
        record_id: UUID,
        db: psycopg2.extensions.connection,
        *,
        select_fields: list[str],
        joins: list[tuple[str, str, str, str]],  # (join_type, table, alias, join_condition)
        scope: InstitutionScope | None = None,
        include_archived: bool = False,
        additional_conditions: list[tuple[str, list]] | None = None,
        row_transform: Callable[[dict], dict] | None = None,
    ) -> T | None:
        """
        Get a single enriched record by ID with JOINs and filtering.

        Args:
            record_id: Record ID to fetch
            db: Database connection
            select_fields: List of SELECT fields
            joins: List of JOIN clauses as (join_type, table, alias, condition) tuples
            scope: Optional institution scope for filtering
            include_archived: Whether to include archived records
            additional_conditions: List of (condition, list_of_params) tuples for custom WHERE conditions

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
                include_archived=include_archived, scope=scope, additional_conditions=conditions
            )

            # Build JOIN clauses
            join_clauses = []
            for join_type, table, alias, condition in joins:
                join_clauses.append(f"{join_type} JOIN {table} {alias} ON {condition}")

            # Build complete query
            query = f"""
                SELECT
                    {", ".join(select_fields)}
                FROM {self.base_table} {self.table_alias}
                {" ".join(join_clauses)}
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
            raise HTTPException(status_code=500, detail=f"Failed to get enriched {self.base_table}: {str(e)}") from None

    def get_distinct_enriched(
        self,
        db: psycopg2.extensions.connection,
        *,
        select_fields: list[str],
        aggregate_fields: list[dict[str, str]],
        joins: list[tuple[str, str, str, str]],
        group_by_fields: list[str] | None = None,
        scope: InstitutionScope | None = None,
        include_archived: bool = False,
        additional_conditions: list[tuple[str, list]] | None = None,
        order_by: str | None = None,
        row_transform: Callable[[dict], dict] | None = None,
        page: int | None = None,
        page_size: int | None = None,
    ) -> Union[list[T], "PaginatedList[T]"]:
        """
        Get enriched records grouped by the base table's primary key, with
        joined rows aggregated into JSON arrays via json_agg(json_build_object(...)).

        Use this instead of get_enriched() when a 1:N JOIN would produce
        duplicate base rows (e.g. one currency used by multiple markets).

        Args:
            db: Database connection
            select_fields: Scalar SELECT fields on the base/1:1 tables
                (e.g. ["cc.currency_metadata_id", "cc.currency_code"]).
                These go into both SELECT and GROUP BY.
            aggregate_fields: List of dicts describing each json_agg column.
                Each dict: {
                    "alias": "markets",           -- output field name
                    "fields": {                    -- keys = JSON keys, values = SQL expressions
                        "market_id": "m.market_id",
                        "market_name": "gc.name",
                        "country_code": "m.country_code",
                    },
                    "filter": "m.market_id IS NOT NULL",  -- optional FILTER (WHERE ...) on the agg
                    "order_by": "gc.name",                -- optional ORDER BY inside json_agg
                }
            joins: JOIN tuples (join_type, table, alias, condition)
            group_by_fields: Explicit GROUP BY list. If None, defaults to select_fields.
            scope, include_archived, additional_conditions, order_by,
            row_transform, page, page_size: same as get_enriched()

        Returns:
            List of schema objects (aggregate columns arrive as Python lists of dicts)
        """
        paginate = page is not None and page_size is not None
        if paginate:
            page_size = max(1, min(page_size, 100))
            page = max(1, page)
            offset = (page - 1) * page_size

        try:
            where_clause, params = self._build_where_clause(
                include_archived=include_archived,
                scope=scope,
                additional_conditions=additional_conditions,
            )

            join_clauses = []
            for join_type, table, alias, condition in joins:
                join_clauses.append(f"{join_type} JOIN {table} {alias} ON {condition}")

            # Build json_agg expressions
            agg_expressions = []
            for agg in aggregate_fields:
                kv_pairs = ", ".join(f"'{k}', {v}" for k, v in agg["fields"].items())
                inner = f"json_build_object({kv_pairs})"
                # Optional ORDER BY inside json_agg
                order = f" ORDER BY {agg['order_by']}" if agg.get("order_by") else ""
                expr = f"json_agg({inner}{order})"
                # Optional FILTER
                if agg.get("filter"):
                    expr += f" FILTER (WHERE {agg['filter']})"
                agg_expressions.append(f"{expr} AS {agg['alias']}")

            all_select = list(select_fields) + agg_expressions
            if group_by_fields:
                gb_fields = group_by_fields
            else:
                # Strip "AS alias" from select_fields for GROUP BY
                # e.g. "ic.name as currency_name" → "ic.name"
                import re

                gb_fields = [re.split(r"\s+[aA][sS]\s+", f)[0].strip() for f in select_fields]
            order_by_clause = order_by or self.default_order_by

            # COUNT for pagination (count distinct base rows)
            total_count = 0
            if paginate:
                count_query = f"""
                    SELECT COUNT(DISTINCT {self.table_alias}.{self.id_column})
                    FROM {self.base_table} {self.table_alias}
                    {" ".join(join_clauses)}
                    {where_clause}
                """
                count_result = self._execute_query(count_query, list(params), db, fetch_one=True)
                total_count = count_result[0]["count"] if count_result else 0

            pagination_clause = ""
            query_params = list(params)
            if paginate:
                pagination_clause = "LIMIT %s OFFSET %s"
                query_params.extend([page_size, offset])

            query = f"""
                SELECT
                    {", ".join(all_select)}
                FROM {self.base_table} {self.table_alias}
                {" ".join(join_clauses)}
                {where_clause}
                GROUP BY {", ".join(gb_fields)}
                ORDER BY {order_by_clause}
                {pagination_clause}
            """

            results = self._execute_query(query, query_params, db, fetch_one=False)

            if not results:
                if paginate:
                    return PaginatedList([], total_count=total_count)
                return []

            enriched_items = []
            for row in results:
                row_dict = dict(row)
                row_dict = self._convert_uuids_to_strings(row_dict)
                # json_agg returns a Python list of dicts via psycopg2 — no extra parsing needed.
                # Coalesce NULL aggregates (from LEFT JOINs with no matches) to empty list.
                for agg in aggregate_fields:
                    if row_dict.get(agg["alias"]) is None:
                        row_dict[agg["alias"]] = []
                if row_transform:
                    row_dict = row_transform(row_dict)
                enriched_items.append(self.schema_class(**row_dict))

            if paginate:
                return PaginatedList(enriched_items, total_count=total_count)
            return enriched_items

        except HTTPException:
            raise
        except Exception as e:
            import traceback

            error_trace = traceback.format_exc()
            log_error(f"Error getting distinct enriched {self.base_table}: {e}\nTraceback: {error_trace}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get distinct enriched {self.base_table}: {str(e)}"
            ) from None
