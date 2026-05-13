import time
from enum import Enum
from typing import Any
from uuid import UUID

import psycopg2
import psycopg2.extensions
import psycopg2.extras
from dotenv import load_dotenv
from fastapi.exceptions import HTTPException
from psycopg2 import sql

from app.utils.error_messages import handle_database_exception
from app.utils.log import log_error, log_info, log_warning

load_dotenv()  # This loads environment variables from .env file

# Track enum registration status per connection
_enum_registration_cache: dict[int, dict[str, bool]] = {}  # connection_id -> {enum_name -> registered}


def clear_enum_registration_cache() -> None:
    """Clear the enum registration cache. Call when the connection pool is closed."""
    global _enum_registration_cache
    _enum_registration_cache.clear()


class EnumArrayAdapter:
    """
    Custom adapter for PostgreSQL enum arrays.

    This adapter explicitly casts Python lists to PostgreSQL enum arrays,
    ensuring proper type handling when psycopg2's automatic array type
    registration doesn't work as expected.

    The adapter implements the ISQLQuote protocol that psycopg2 expects.
    """

    def __init__(self, enum_list: list[str], enum_type_name: str):
        """
        Initialize the adapter.

        Args:
            enum_list: List of enum values (strings or Enum objects)
            enum_type_name: Name of the PostgreSQL enum type (e.g., 'address_type_enum')
        """
        # Convert Enum objects to strings if needed
        self.enum_list = [v.value if isinstance(v, Enum) else v for v in enum_list]
        self.enum_type_name = enum_type_name

    def getquoted(self) -> str:
        """
        Return a properly quoted and casted PostgreSQL array literal.

        This method is called by psycopg2 when adapting the value for SQL.
        The returned string should be ready to be inserted into SQL without
        additional quoting (psycopg2 will handle that).

        Returns:
            String representation of the array with explicit enum type cast
        """
        # Escape single quotes in enum values (PostgreSQL escaping)
        escaped_values = [v.replace("'", "''") for v in self.enum_list]
        # Format as PostgreSQL array literal with explicit enum type cast
        quoted_values = [f"'{v}'" for v in escaped_values]
        array_literal = "{" + ",".join(quoted_values) + "}"
        # Return the array literal with explicit cast (no additional quoting needed)
        return f"{array_literal}::{self.enum_type_name}[]"

    def __conform__(self, protocol: Any) -> "EnumArrayAdapter | None":
        """
        Allow psycopg2 to adapt this object.

        This method is part of the Python DB-API adaptation protocol.
        Returns self if the protocol is ISQLQuote, allowing psycopg2 to call getquoted().
        """
        if protocol is psycopg2.extensions.ISQLQuote:
            return self
        return None

    def prepare(self, conn: Any) -> None:
        """Required by ISQLQuote protocol - called before getquoted()"""


def _is_enum_registered(connection: Any, enum_name: str) -> bool:
    """
    Check if a specific enum type is registered for this connection.
    Uses a cache to avoid repeated queries.

    Args:
        connection: Database connection
        enum_name: Name of the enum type to check (e.g., 'status_enum', 'role_type_enum')

    Returns:
        True if enum type is registered, False otherwise
    """
    if connection is None:
        return False

    conn_id = id(connection)
    if conn_id not in _enum_registration_cache:
        _enum_registration_cache[conn_id] = {}

    if enum_name in _enum_registration_cache[conn_id]:
        return _enum_registration_cache[conn_id][enum_name]

    # Check if enum type exists in database
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_type
                    WHERE typname = %s
                )
            """,
                (enum_name,),
            )
            result = cursor.fetchone()
            enum_exists: bool = result[0] if result else False

            # Cache the result
            _enum_registration_cache[conn_id][enum_name] = enum_exists
            return enum_exists
    except Exception:
        _enum_registration_cache[conn_id][enum_name] = False
        return False


def _prepare_value_for_db(value: Any, table: str, column: str, connection: Any = None) -> Any:
    """
    Prepare a value for database insertion, handling special types like enums and enum arrays.

    When enum types are registered with psycopg2, Python Enum objects and lists are automatically
    converted to the correct enum type. If not registered, we fall back to SQL casting.

    Args:
        value: The value to prepare
        table: Table name
        column: Column name
        connection: Optional database connection (for type registration check)

    Returns:
        Prepared value ready for psycopg2
    """
    # Handle enum types
    enum_mappings = {
        ("address_info", "address_type"): "address_type_enum",
        # Status enum - used by ALL _info and _history tables
        ("user_info", "status"): "status_enum",
        ("user_history", "status"): "status_enum",
        ("product_info", "status"): "status_enum",
        ("product_history", "status"): "status_enum",
        ("vianda_info", "status"): "status_enum",
        ("vianda_history", "status"): "status_enum",
        ("restaurant_info", "status"): "status_enum",
        ("restaurant_history", "status"): "status_enum",
        ("institution_info", "status"): "status_enum",
        ("institution_history", "status"): "status_enum",
        ("plan_info", "status"): "status_enum",
        ("plan_history", "status"): "status_enum",
        ("national_holidays", "status"): "status_enum",
        ("national_holidays_history", "status"): "status_enum",
        ("restaurant_holidays", "status"): "status_enum",
        ("restaurant_holidays_history", "status"): "status_enum",
        ("client_transaction", "status"): "status_enum",
        ("restaurant_transaction", "status"): "status_enum",
        ("discretionary_info", "status"): "discretionary_status_enum",
        ("discretionary_history", "status"): "discretionary_status_enum",
        ("discretionary_resolution_info", "status"): "status_enum",
        ("discretionary_resolution_info", "resolution"): "discretionary_status_enum",
        ("discretionary_resolution_history", "status"): "status_enum",
        ("discretionary_resolution_history", "resolution"): "discretionary_status_enum",
        ("subscription_info", "status"): "status_enum",
        ("subscription_history", "status"): "status_enum",
        ("client_bill_info", "status"): "status_enum",
        ("client_bill_history", "status"): "status_enum",
        ("geolocation_info", "status"): "status_enum",
        ("geolocation_history", "status"): "status_enum",
        # employer_info/employer_history REMOVED
        ("currency_metadata", "status"): "status_enum",
        ("credit_currency_history", "status"): "status_enum",
        ("institution_entity_info", "status"): "status_enum",
        ("institution_entity_history", "status"): "status_enum",
        ("address_info", "status"): "status_enum",
        ("address_history", "status"): "status_enum",
        ("payment_method", "status"): "status_enum",
        # Role enums - stored directly on user_info (no role_info table)
        ("user_info", "role_type"): "role_type_enum",
        ("user_info", "role_name"): "role_name_enum",
        ("user_history", "role_type"): "role_type_enum",
        ("user_history", "role_name"): "role_name_enum",
        ("institution_info", "institution_type"): "institution_type_enum",
        ("institution_history", "institution_type"): "institution_type_enum",
        # Transaction type enum - stored directly on transaction tables
        ("restaurant_transaction", "transaction_type"): "transaction_type_enum",
        # Kitchen day enum
        ("vianda_kitchen_days", "kitchen_day"): "kitchen_day_enum",
        ("vianda_kitchen_days_history", "kitchen_day"): "kitchen_day_enum",
        ("vianda_selection_info", "kitchen_day"): "kitchen_day_enum",
        # Pickup type enum
        ("pickup_preferences", "pickup_type"): "pickup_type_enum",
        # Street type enum
        ("address_info", "street_type"): "street_type_enum",
        ("address_history", "street_type"): "street_type_enum",
        # Audit operation enum
        ("restaurant_holidays_history", "operation"): "audit_operation_enum",
        ("vianda_kitchen_days_history", "operation"): "audit_operation_enum",
        ("discretionary_history", "operation"): "audit_operation_enum",
        ("discretionary_resolution_history", "operation"): "audit_operation_enum",
        # Bill resolution enum (institution_bill_info, institution_bill_history)
        ("institution_bill_info", "resolution"): "bill_resolution_enum",
        ("institution_bill_history", "resolution"): "bill_resolution_enum",
        # Favorite entity type enum
        ("user_favorite_info", "entity_type"): "favorite_entity_type_enum",
        # Notification banner enums
        ("notification_banner", "notification_type"): "notification_banner_type_enum",
        ("notification_banner", "priority"): "notification_banner_priority_enum",
        ("notification_banner", "action_status"): "notification_banner_action_status_enum",
        ("workplace_group", "status"): "status_enum",
    }

    # Handle enum arrays for address_type (special case - must come before scalar enum handling)
    # Note: For address_type, the SQL query itself includes the cast (::address_type_enum[])
    # So we just need to pass the list directly - the cast in SQL will handle conversion
    if table == "address_info" and column == "address_type" and isinstance(value, list):
        # Convert Enum objects to strings if needed, then pass list directly
        # The SQL cast in _build_insert_sql will handle the enum array conversion
        return [v.value if isinstance(v, Enum) else v for v in value]

    enum_type = enum_mappings.get((table, column))
    if enum_type and isinstance(value, (str, Enum)):
        # Convert Enum to string if needed
        enum_value = value.value if isinstance(value, Enum) else value

        if _is_enum_registered(connection, enum_type):
            # When enum type is registered, psycopg2 handles conversion automatically
            return enum_value
        log_warning(
            f"⚠️ Enum type {enum_type} not registered for connection - using SQL casting fallback for {table}.{column}"
        )
        return enum_value  # Will be cast in SQL

    # Convert UUID to string
    if isinstance(value, UUID):
        return str(value)

    # JSONB columns: psycopg2 cannot adapt Python dict natively.
    # Wrap with Json() so it serialises to JSONB. Lists are left as-is
    # because psycopg2 adapts them natively to Postgres arrays (TEXT[], etc.).
    if isinstance(value, dict):
        return psycopg2.extras.Json(value)

    return value


def get_db_connection() -> Any:
    """Get a connection from the pool"""
    from app.utils.db_pool import get_db_connection as pool_get_connection

    return pool_get_connection()


def close_db_connection(conn: Any) -> None:
    """Return a connection to the pool"""
    from app.utils.db_pool import close_db_connection as pool_close_connection

    pool_close_connection(conn)


PRIMARY_KEY_MAPPING = {
    "institution_info": "institution_id",
    "user_info": "user_id",
    "user_messaging_preferences": "user_id",
    "credential_recovery": "credential_recovery_id",
    "email_change_request": "email_change_request_id",
    "address_info": "address_id",
    "address_subpremise": "subpremise_id",
    # "employer_info" REMOVED
    "institution_entity_info": "institution_entity_id",
    "supplier_terms": "supplier_terms_id",
    "supplier_invoice": "supplier_invoice_id",
    "supplier_invoice_ar": "supplier_invoice_id",
    "supplier_invoice_pe": "supplier_invoice_id",
    "supplier_invoice_us": "supplier_invoice_id",
    "supplier_w9": "w9_id",
    "employer_benefits_program": "program_id",
    "employer_domain": "domain_id",
    "employer_bill": "employer_bill_id",
    "employer_bill_line": "line_id",
    "bill_invoice_match": "match_id",
    "city_metadata": "city_metadata_id",
    "cuisine": "cuisine_id",
    "cuisine_suggestion": "suggestion_id",
    "pickup_preferences_info": "preference_id",
    "national_holidays": "holiday_id",
    "ingredient_catalog": "ingredient_id",
    "referral_config": "referral_config_id",
    "referral_info": "referral_id",
    "referral_transaction": "referral_transaction_id",
    "restaurant_info": "restaurant_id",
    "qr_code": "qr_code_id",
    "discretionary_info": "discretionary_id",
    "discretionary_history": "history_id",
    "discretionary_resolution_info": "approval_id",
    "discretionary_resolution_history": "history_id",
    "product_info": "product_id",
    "vianda_info": "vianda_id",
    "vianda_selection_info": "vianda_selection_id",
    "vianda_pickup_live": "vianda_pickup_id",
    "vianda_review_info": "vianda_review_id",
    "user_favorite_info": "favorite_id",
    "plan_info": "plan_id",
    "client_transaction": "transaction_id",
    "subscription_info": "subscription_id",
    "subscription_payment": "subscription_payment_id",
    "client_bill_info": "client_bill_id",
    "payment_method": "payment_method_id",
    "external_payment_method": "external_payment_method_id",
    "user_payment_provider": "user_payment_provider_id",
    "currency_metadata": "currency_metadata_id",
    "currency_rate_raw": "currency_rate_raw_id",
    "restaurant_transaction": "transaction_id",
    "restaurant_balance_info": "restaurant_id",
    "institution_bill_info": "institution_bill_id",
    "institution_settlement": "settlement_id",
    "geolocation_info": "geolocation_id",
    "vianda_kitchen_days": "vianda_kitchen_day_id",
    "restaurant_holidays": "holiday_id",
    "notification_banner": "notification_id",
    "workplace_group": "workplace_group_id",
    # role_info, status_info, transaction_type_info removed
}


def _build_insert_sql(
    table: str, data: dict[str, Any], connection: Any = None
) -> tuple["sql.Composed", tuple[Any, ...], str]:
    """
    Build SQL statement, values tuple, and primary key for insert.

    This is a shared helper function used by both db_insert and db_batch_insert
    to avoid code duplication while maintaining clear separation of concerns.

    Table and column names are quoted via psycopg2.sql.Identifier, which
    eliminates string interpolation of identifiers and silences CodeQL
    py/sql-injection findings.  Values continue to use parameterised %s
    placeholders — no change in safety semantics.

    Args:
        table: Table name
        data: Dictionary of column names to values
        connection: Optional database connection (for enum registration check)

    Returns:
        Tuple of (sql.Composed, values, primary_key)
    """
    # Build column identifier list and placeholder list
    col_identifiers = []
    placeholder_parts = []
    for col in data:
        col_identifiers.append(sql.Identifier(col))
        if table == "address_info" and col == "address_type":
            # Explicit cast in SQL for the enum array column
            placeholder_parts.append(sql.SQL("%s::address_type_enum[]"))
        else:
            placeholder_parts.append(sql.Placeholder())

    # Get the primary key column for the given table (default to 'id' if not defined)
    primary_key = PRIMARY_KEY_MAPPING.get(table, "id")

    composed = sql.SQL("INSERT INTO {table} ({columns}) VALUES ({values}) RETURNING {pk}").format(
        table=sql.Identifier(table),
        columns=sql.SQL(", ").join(col_identifiers),
        values=sql.SQL(", ").join(placeholder_parts),
        pk=sql.Identifier(primary_key),
    )

    # Prepare values: handle enum arrays and UUIDs properly
    # For address_type, we'll pass the list directly and let SQL cast handle it
    values = []
    for col, v in data.items():
        if table == "address_info" and col == "address_type":
            # Pass the list directly - SQL cast will handle conversion
            # Convert Enum objects to strings if needed
            if isinstance(v, list):
                values.append([item.value if isinstance(item, Enum) else item for item in v])
            else:
                values.append(v)
        else:
            values.append(_prepare_value_for_db(v, table, col, connection))

    return composed, tuple(values), primary_key


def db_insert(table: str, data: dict[str, Any], connection: Any = None, *, commit: bool = True) -> Any:
    """
    Insert a single record into the database.

    This function can commit immediately after the insert (default) or defer
    committing for use in atomic multi-operation transactions.

    Args:
        table: Table name
        data: Dictionary of column names to values
        connection: Optional database connection (if None, creates new connection)
        commit: Whether to commit immediately after insert (default: True).
                Set to False for atomic multi-operation transactions.

    Returns:
        The primary key ID of the inserted record
    """
    # If no connection is provided, get one from the pool
    new_connection = False
    if connection is None:
        connection = get_db_connection()
        new_connection = True

    sql, values, primary_key = _build_insert_sql(table, data, connection)

    start_time = time.time()
    try:
        cursor = connection.cursor()
        log_info(f"Executing SQL: {sql} with values {values}")
        cursor.execute(sql, values)
        inserted_id = cursor.fetchone()[0]

        # Only commit if requested (default True for backward compatibility)
        if commit:
            connection.commit()
            log_info(f"Successfully inserted record into '{table}' with ID {inserted_id}")
        else:
            log_info(f"Inserted record into '{table}' with ID {inserted_id} (commit deferred)")

        execution_time = time.time() - start_time
        log_info(f"📊 INSERT executed in {execution_time:.3f}s")

        if execution_time > 1.0:  # Log slow operations
            log_warning(f"🐌 Slow INSERT detected: {execution_time:.3f}s - {table}")

        return inserted_id
    except Exception as e:
        connection.rollback()
        raise handle_database_exception(e, f"insert into {table}") from e
    finally:
        if new_connection:
            close_db_connection(connection)
            log_info("Database connection returned to pool after INSERT execution.")


def db_batch_insert(table: str, data_list: list[dict[str, Any]], connection: Any = None) -> list[Any]:
    """
    Insert multiple records into a table in a single atomic transaction.

    This function is designed for batch operations where all inserts must
    succeed or all must fail (atomicity). It validates all data before
    executing any inserts, then executes all inserts in a single transaction.

    Args:
        table: Table name
        data_list: List of dictionaries, each representing one row to insert
        connection: Optional database connection (if None, creates and manages connection)

    Returns:
        List of inserted primary key IDs in the same order as data_list

    Raises:
        ValueError: If data_list is empty or contains invalid data
        Exception: If any insert fails, all operations are rolled back

    Example:
        data_list = [
            {"vianda_id": "uuid1", "kitchen_day": "Monday"},
            {"vianda_id": "uuid1", "kitchen_day": "Tuesday"}
        ]
        ids = db_batch_insert("vianda_kitchen_days", data_list, connection)
        # Returns: [uuid1, uuid2] (primary key IDs)
    """
    if not data_list:
        raise ValueError("data_list cannot be empty")

    # If no connection is provided, get one from the pool
    new_connection = False
    if connection is None:
        connection = get_db_connection()
        new_connection = True

    start_time = time.time()
    inserted_ids = []

    try:
        cursor = connection.cursor()

        # Validate all data first (before any inserts)
        for i, data in enumerate(data_list):
            if not isinstance(data, dict):
                raise ValueError(f"data_list[{i}] must be a dictionary")
            if not data:
                raise ValueError(f"data_list[{i}] cannot be empty")

        # Execute all inserts using shared helper
        for i, data in enumerate(data_list):
            sql, values, primary_key = _build_insert_sql(table, data, connection)
            log_info(f"Executing batch INSERT {i + 1}/{len(data_list)}: {sql} with values {values}")
            cursor.execute(sql, values)
            inserted_id = cursor.fetchone()[0]
            inserted_ids.append(inserted_id)

        # Commit all inserts atomically
        connection.commit()
        execution_time = time.time() - start_time

        log_info(f"Successfully batch inserted {len(inserted_ids)} records into '{table}'")
        log_info(f"📊 BATCH INSERT executed in {execution_time:.3f}s")

        if execution_time > 1.0:
            log_warning(f"🐌 Slow BATCH INSERT detected: {execution_time:.3f}s - {table}")

        return inserted_ids

    except Exception as e:
        # Rollback all inserts on any error
        connection.rollback()
        log_error(f"Batch insert failed for '{table}': {e}. All operations rolled back.")
        raise handle_database_exception(e, f"batch insert into {table}") from e
    finally:
        if new_connection:
            close_db_connection(connection)
            log_info("Database connection returned to pool after BATCH INSERT execution.")


def _build_update_sql(
    table: str, data: dict[str, Any], where: dict[str, Any], connection: Any = None
) -> tuple["sql.Composed", tuple[Any, ...]]:
    """
    Build SQL statement and values tuple for update operation.

    This is a shared helper function used by both db_update and db_batch_update
    to avoid code duplication while maintaining clear separation of concerns.

    Table and column names are quoted via psycopg2.sql.Identifier, which
    eliminates string interpolation of identifiers and silences CodeQL
    py/sql-injection findings.  Values continue to use parameterised %s
    placeholders — no change in safety semantics.

    Args:
        table: Table name
        data: Dictionary of column names to values for SET clause
        where: Dictionary of column names to values for WHERE clause
        connection: Optional database connection (for enum registration check)

    Returns:
        Tuple of (sql.Composed, values)
    """
    # Build the SET clause - use explicit cast for address_info.address_type (enum array)
    set_parts = []
    for column in data:
        if table == "address_info" and column == "address_type":
            set_parts.append(sql.SQL("{col} = %s::address_type_enum[]").format(col=sql.Identifier(column)))
        else:
            set_parts.append(sql.SQL("{col} = %s").format(col=sql.Identifier(column)))

    # Build the WHERE clause
    where_parts = [sql.SQL("{col} = %s").format(col=sql.Identifier(column)) for column in where]

    composed = sql.SQL("UPDATE {table} SET {set_clause} WHERE {where_clause}").format(
        table=sql.Identifier(table),
        set_clause=sql.SQL(", ").join(set_parts),
        where_clause=sql.SQL(" AND ").join(where_parts),
    )

    # Prepare values: handle enum arrays (address_type) and other types
    data_values = []
    for col, v in data.items():
        if table == "address_info" and col == "address_type":
            if isinstance(v, list):
                data_values.append([item.value if isinstance(item, Enum) else item for item in v])
            else:
                data_values.append(v)
        else:
            data_values.append(_prepare_value_for_db(v, table, col, connection))
    data_values_tuple = tuple(data_values)
    where_values = tuple(_prepare_value_for_db(v, table, col, connection) for col, v in where.items())
    values = data_values_tuple + where_values

    return composed, values


def db_update(
    table: str, data: dict[str, Any], where: dict[str, Any], connection: Any = None, *, commit: bool = True
) -> int:
    """
    Update records in the database matching the WHERE clause.

    This function can commit immediately after the update (default) or defer
    committing for use in atomic multi-operation transactions.

    Args:
        table: Table name
        data: Dictionary of column names to values for SET clause
        where: Dictionary of column names to values for WHERE clause
        connection: Optional database connection (if None, creates new connection)
        commit: Whether to commit immediately after update (default: True).
                Set to False for atomic multi-operation transactions.

    Returns:
        Number of rows affected
    """
    # If no connection is provided, get one from the pool
    new_connection = False
    if connection is None:
        connection = get_db_connection()
        new_connection = True

    sql, values = _build_update_sql(table, data, where, connection)

    start_time = time.time()
    try:
        cursor = connection.cursor()
        log_info(f"🚀 Executing SQL: {sql}")
        log_info(f"📊 Data values: {values[: len(data)]}")
        log_info(f"🔍 Where values: {values[len(data) :]}")
        log_info(f"📋 All values: {values}")

        cursor.execute(sql, values)
        row_count: int = cursor.rowcount

        # Only commit if requested (default True for backward compatibility)
        if commit:
            connection.commit()
            log_info(f"📊 UPDATE result: {row_count} row(s) affected")
        else:
            log_info(f"📊 UPDATE result: {row_count} row(s) affected (commit deferred)")

        execution_time = time.time() - start_time
        log_info(f"📊 UPDATE executed in {execution_time:.3f}s")

        if execution_time > 1.0:  # Log slow operations
            log_warning(f"🐌 Slow UPDATE detected: {execution_time:.3f}s - {table}")

        return row_count
    except Exception as e:
        connection.rollback()
        raise handle_database_exception(e, f"update {table}") from e
    finally:
        if new_connection:
            close_db_connection(connection)
            log_info("Database connection returned to pool after UPDATE execution.")


def _validate_batch_update_pattern1(
    updates: dict[str, Any], where_list: list[dict[str, Any]] | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not updates:
        raise ValueError("updates dict cannot be empty for Pattern 1")
    if where_list is None:
        raise ValueError("where_list is required for Pattern 1 (same update, different WHERE clauses)")
    if not isinstance(where_list, list):
        raise ValueError("where_list must be a list for Pattern 1")
    if not where_list:
        raise ValueError("where_list cannot be empty for Pattern 1")
    for i, where_clause in enumerate(where_list):
        if not isinstance(where_clause, dict):
            raise ValueError(f"where_list[{i}] must be a dictionary")
        if not where_clause:
            raise ValueError(f"where_list[{i}] cannot be empty")
    return [updates] * len(where_list), where_list


def _validate_batch_update_pattern2(
    updates: list[dict[str, Any]], where_list: list[dict[str, Any]] | None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not updates:
        raise ValueError("updates list cannot be empty for Pattern 2")
    if where_list is not None:
        raise ValueError("where_list must be None for Pattern 2 (id should be in each update dict)")
    update_list: list[dict[str, Any]] = []
    where_clause_list: list[dict[str, Any]] = []
    for i, update_dict in enumerate(updates):
        if not isinstance(update_dict, dict):
            raise ValueError(f"updates[{i}] must be a dictionary")
        if not update_dict:
            raise ValueError(f"updates[{i}] cannot be empty")
        if "id" not in update_dict:
            raise ValueError(f"updates[{i}] must contain 'id' field for Pattern 2")
        update_list.append({k: v for k, v in update_dict.items() if k != "id"})
        where_clause_list.append({"id": update_dict["id"]})
    return update_list, where_clause_list


def db_batch_update(
    table: str,
    updates: dict[str, Any] | list[dict[str, Any]],
    where_list: list[dict[str, Any]] | None = None,
    connection: Any = None,
) -> int:
    """
    Update multiple records in a table in a single atomic transaction.

    This function supports two patterns:

    Pattern 1: Same update, different WHERE clauses
        updates = {"status": "archived"}
        where_list = [{"id": "uuid1"}, {"id": "uuid2"}]

    Pattern 2: Different updates per record (id must be in each update dict)
        updates = [
            {"id": "uuid1", "status": "active", "modified_by": "user1"},
            {"id": "uuid2", "status": "inactive", "modified_by": "user1"}
        ]
        where_list = None (id is extracted from each update dict)
    """
    if isinstance(updates, dict):
        update_list, where_clause_list = _validate_batch_update_pattern1(updates, where_list)
    elif isinstance(updates, list):
        update_list, where_clause_list = _validate_batch_update_pattern2(updates, where_list)
    else:
        raise ValueError("updates must be either a dict (Pattern 1) or list of dicts (Pattern 2)")

    # If no connection is provided, get one from the pool
    new_connection = False
    if connection is None:
        connection = get_db_connection()
        new_connection = True

    start_time = time.time()
    total_rows_affected = 0

    try:
        cursor = connection.cursor()

        # Execute all updates using shared helper
        for i, (update_data, where_clause) in enumerate(zip(update_list, where_clause_list, strict=False)):
            sql, values = _build_update_sql(table, update_data, where_clause, connection)
            log_info(f"Executing batch UPDATE {i + 1}/{len(update_list)}: {sql} with values {values}")
            cursor.execute(sql, values)
            total_rows_affected += cursor.rowcount

        # Commit all updates atomically
        connection.commit()
        execution_time = time.time() - start_time

        log_info(f"Successfully batch updated {total_rows_affected} record(s) in '{table}'")
        log_info(f"📊 BATCH UPDATE executed in {execution_time:.3f}s")

        if execution_time > 1.0:
            log_warning(f"🐌 Slow BATCH UPDATE detected: {execution_time:.3f}s - {table}")

        return total_rows_affected

    except ValueError:
        # Re-raise validation errors (these happen before any database operations)
        raise
    except Exception as e:
        # Rollback all updates on any error
        connection.rollback()
        log_error(f"Batch update failed for '{table}': {e}. All operations rolled back.")
        raise handle_database_exception(e, f"batch update {table}") from e
    finally:
        if new_connection:
            close_db_connection(connection)
            log_info("Database connection returned to pool after BATCH UPDATE execution.")


def db_read(
    query: str, values: tuple[Any, ...] | None = None, connection: Any = None, fetch_one: bool = False
) -> dict[str, Any] | list[dict[str, Any]] | None:
    """Execute a read query using a connection from the pool"""
    # If no connection is provided, get one from the pool
    new_connection = False
    if connection is None:
        connection = get_db_connection()
        new_connection = True

    cursor = connection.cursor()
    start_time = time.time()
    try:
        log_info(f"Executing query: {query} with values: {values}")
        if values is not None:
            cursor.execute(
                query, values
            )  # codeql[py/sql-injection] query is always a full SQL literal from internal service callers; values are parameterised via psycopg2 %s
        else:
            cursor.execute(
                query
            )  # codeql[py/sql-injection] query is always a full SQL literal from internal service callers; no user-controlled input reaches this path
        columns = [desc[0] for desc in cursor.description]

        # Fetch either a single record or all records
        raw_results = cursor.fetchone() if fetch_one else cursor.fetchall()
        execution_time = time.time() - start_time

        # Convert results to dictionaries
        results: dict[str, Any] | list[dict[str, Any]] | None
        if raw_results is None:
            results = None
        elif fetch_one:
            # Single record - return dictionary or None
            results = dict(zip(columns, raw_results, strict=False)) if raw_results else None
        else:
            # Multiple records - return list of dictionaries
            results = [dict(zip(columns, row, strict=False)) for row in raw_results] if raw_results else []

        log_info(f"Query results: {results}")
        log_info(f"📊 Query executed in {execution_time:.3f}s: {query[:100]}...")

        if execution_time > 1.0:  # Log slow queries
            log_warning(f"🐌 Slow query detected: {execution_time:.3f}s - {query}")

        return results
    except Exception as e:
        log_warning(f"Error executing query: {e}")
        raise HTTPException(status_code=500, detail=f"Error executing query: {e}") from None
    finally:
        cursor.close()
        if new_connection:
            close_db_connection(connection)
            log_info("Database connection returned to pool after query execution.")


def _build_delete_sql(
    table: str, where: dict[str, Any], soft: bool = False, soft_update_fields: dict[str, Any] | None = None
) -> tuple["sql.Composed", tuple[Any, ...]]:
    """
    Build SQL statement and values tuple for delete operation.

    This is a shared helper function used by both db_delete and db_batch_delete
    to avoid code duplication while maintaining clear separation of concerns.

    Table and column names are quoted via psycopg2.sql.Identifier, which
    eliminates string interpolation of identifiers and silences CodeQL
    py/sql-injection findings.  Values continue to use parameterised %s
    placeholders — no change in safety semantics.

    Args:
        table: Table name
        where: Dictionary of column names to values for WHERE clause
        soft: If True, perform soft delete (UPDATE is_archived) instead of hard delete
        soft_update_fields: Optional dictionary of additional fields to update during soft delete
                          (e.g., {"modified_by": uuid, "modified_date": datetime})

    Returns:
        Tuple of (sql.Composed, values)
    """
    where_parts = [sql.SQL("{col} = %s").format(col=sql.Identifier(column)) for column in where]
    where_clause = sql.SQL(" AND ").join(where_parts)

    if soft:
        # Soft delete: UPDATE is_archived = true
        set_parts: list[sql.Composable] = [sql.SQL("is_archived = true")]
        set_values = []

        # Add additional fields if provided (e.g., modified_by, modified_date)
        if soft_update_fields:
            for field, value in soft_update_fields.items():
                set_parts.append(sql.SQL("{col} = %s").format(col=sql.Identifier(field)))
                set_values.append(value if not isinstance(value, UUID) else str(value))

        composed = sql.SQL("UPDATE {table} SET {set_clause} WHERE {where_clause}").format(
            table=sql.Identifier(table),
            set_clause=sql.SQL(", ").join(set_parts),
            where_clause=where_clause,
        )
        # Values: set_values first, then where values
        values = tuple(set_values + [v if not isinstance(v, UUID) else str(v) for v in where.values()])
    else:
        # Hard delete: DELETE FROM table
        composed = sql.SQL("DELETE FROM {table} WHERE {where_clause}").format(
            table=sql.Identifier(table),
            where_clause=where_clause,
        )
        # Convert UUID objects to their string representation
        values = tuple(v if not isinstance(v, UUID) else str(v) for v in where.values())

    return composed, values


def db_delete(
    table: str,
    where: dict[str, Any],
    connection: Any = None,
    soft: bool = False,
    soft_update_fields: dict[str, Any] | None = None,
) -> int:
    """
    Delete a single record from the database.

    This function commits immediately after the delete, making it suitable
    for single-record operations that should be atomic on their own.

    Args:
        table: Table name
        where: Dictionary of column names to values for WHERE clause
        connection: Optional database connection (if None, creates new connection)
        soft: If True, perform soft delete (UPDATE is_archived) instead of hard delete
        soft_update_fields: Optional dictionary of additional fields to update during soft delete
                          (e.g., {"modified_by": uuid, "modified_date": datetime})

    Returns:
        Number of rows affected
    """
    sql, values = _build_delete_sql(table, where, soft=soft, soft_update_fields=soft_update_fields)

    # If no connection is provided, get one from the pool
    new_connection = False
    if connection is None:
        connection = get_db_connection()
        new_connection = True

    cursor = connection.cursor()
    start_time = time.time()
    try:
        log_info(f"Executing DELETE SQL: {sql} with values: {values}")
        cursor.execute(sql, values)
        connection.commit()
        row_count: int = cursor.rowcount
        execution_time = time.time() - start_time

        delete_type = "soft delete" if soft else "hard delete"
        log_info(f"Successfully {delete_type} {row_count} row(s) from '{table}'.")
        log_info(f"📊 DELETE executed in {execution_time:.3f}s")

        if execution_time > 1.0:  # Log slow operations
            log_warning(f"🐌 Slow DELETE detected: {execution_time:.3f}s - {table}")

        return row_count
    except Exception as e:
        connection.rollback()
        log_warning(f"Error deleting record from '{table}': {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting record: {e}") from None
    finally:
        cursor.close()
        if new_connection:
            close_db_connection(connection)
            log_info("Database connection returned to pool after DELETE execution.")


def db_batch_delete(
    table: str,
    where_list: list[dict[str, Any]],
    connection: Any = None,
    soft: bool = False,
    soft_update_fields: dict[str, Any] | None = None,
) -> int:
    """
    Delete multiple records from a table in a single atomic transaction.

    This function is designed for batch operations where all deletes must
    succeed or all must fail (atomicity). It validates all WHERE clauses before
    executing any deletes, then executes all deletes in a single transaction.

    Args:
        table: Table name
        where_list: List of dictionaries, each representing a WHERE clause
        connection: Optional database connection (if None, creates and manages connection)
        soft: If True, perform soft delete (UPDATE is_archived) instead of hard delete
        soft_update_fields: Optional dictionary of additional fields to update during soft delete
                          (e.g., {"modified_by": uuid, "modified_date": datetime})
                          Applied to all records in the batch

    Returns:
        Total number of rows affected

    Raises:
        ValueError: If where_list is empty or contains invalid data
        Exception: If any delete fails, all operations are rolled back

    Example:
        where_list = [
            {"id": "uuid1"},
            {"id": "uuid2"},
            {"id": "uuid3"}
        ]
        count = db_batch_delete("table", where_list, connection, soft=True,
                                soft_update_fields={"modified_by": user_id})
        # Returns: 3 (number of records soft-deleted)
    """
    if not where_list:
        raise ValueError("where_list cannot be empty")

    # If no connection is provided, get one from the pool
    new_connection = False
    if connection is None:
        connection = get_db_connection()
        new_connection = True

    start_time = time.time()
    total_rows_affected = 0

    try:
        cursor = connection.cursor()

        # Validate all WHERE clauses first (before any deletes)
        for i, where_clause in enumerate(where_list):
            if not isinstance(where_clause, dict):
                raise ValueError(f"where_list[{i}] must be a dictionary")
            if not where_clause:
                raise ValueError(f"where_list[{i}] cannot be empty")

        # Execute all deletes using shared helper
        for i, where_clause in enumerate(where_list):
            sql, values = _build_delete_sql(table, where_clause, soft=soft, soft_update_fields=soft_update_fields)
            delete_type = "soft delete" if soft else "hard delete"
            log_info(f"Executing batch {delete_type} {i + 1}/{len(where_list)}: {sql} with values {values}")
            cursor.execute(sql, values)
            total_rows_affected += cursor.rowcount

        # Commit all deletes atomically
        connection.commit()
        execution_time = time.time() - start_time

        delete_type = "soft delete" if soft else "hard delete"
        log_info(f"Successfully batch {delete_type} {total_rows_affected} record(s) from '{table}'")
        log_info(f"📊 BATCH DELETE executed in {execution_time:.3f}s")

        if execution_time > 1.0:
            log_warning(f"🐌 Slow BATCH DELETE detected: {execution_time:.3f}s - {table}")

        return total_rows_affected

    except ValueError:
        # Re-raise validation errors (these happen before any database operations)
        raise
    except Exception as e:
        # Rollback all deletes on any error
        connection.rollback()
        delete_type = "soft delete" if soft else "hard delete"
        log_error(f"Batch {delete_type} failed for '{table}': {e}. All operations rolled back.")
        raise handle_database_exception(e, f"batch delete from {table}") from e
    finally:
        if new_connection:
            close_db_connection(connection)
            log_info("Database connection returned to pool after BATCH DELETE execution.")
