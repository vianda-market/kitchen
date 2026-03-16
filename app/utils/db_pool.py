"""
Database Connection Pool Manager

Provides efficient connection pooling for database operations,
reducing connection overhead and improving performance.
"""

import psycopg2.pool
import psycopg2.extensions
import psycopg2.extras
import os
import time
from contextlib import contextmanager
from typing import Optional
from app.utils.log import log_info, log_warning, log_error

def _register_enum_types(conn: psycopg2.extensions.connection):
    """
    Register all PostgreSQL enum types with psycopg2 for proper type handling.
    This ensures enum types and arrays are handled correctly without SQL casting.
    
    Args:
        conn: Database connection
        
    Returns:
        True if all enum types registered successfully, False otherwise
    """
    enum_types = [
        'address_type_enum',      # Already implemented
        'status_enum',            # CRITICAL - used by all tables
        'role_type_enum',         # CRITICAL - permission system
        'role_name_enum',         # CRITICAL - permission system
        'institution_type_enum',  # Internal / Customer / Supplier / Employer - must match user role_type (Customer can be in Customer or Employer institution)
        'transaction_type_enum',  # CRITICAL - transaction system
        'kitchen_day_enum',       # New
        'pickup_type_enum',       # New
        'street_type_enum',       # Address street type (St, Ave, Blvd, etc.)
        'audit_operation_enum',   # New
        'discretionary_reason_enum',  # New - discretionary request reasons
        'discretionary_status_enum',  # Discretionary lifecycle: Pending, Cancelled, Approved, Rejected
        'bill_resolution_enum',   # Institution bill resolution: Pending, Paid, Rejected
    ]
    
    registered_count = 0
    for enum_name in enum_types:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT oid, typarray 
                    FROM pg_type 
                    WHERE typname = %s
                """, (enum_name,))
                result = cursor.fetchone()
                
                if result:
                    enum_oid, array_oid = result
                    # Register the enum type
                    ENUM_TYPE = psycopg2.extensions.new_type(
                        (enum_oid,), f'{enum_name.upper()}', lambda value, cursor: value
                    )
                    psycopg2.extensions.register_type(ENUM_TYPE, conn)
                    
                    # Register the array type (if exists)
                    if array_oid:
                        ENUM_ARRAY_TYPE = psycopg2.extensions.new_array_type(
                            (array_oid,), f'{enum_name.upper()}_ARRAY', ENUM_TYPE
                        )
                        psycopg2.extensions.register_type(ENUM_ARRAY_TYPE, conn)
                    
                    registered_count += 1
                    log_info(f"✅ Registered {enum_name} and {enum_name}[] types with psycopg2")
                else:
                    log_warning(f"⚠️ {enum_name} not found in database - enum type registration skipped")
        except Exception as e:
            log_warning(f"⚠️ Failed to register {enum_name}: {e}")
    
    if registered_count == len(enum_types):
        log_info(f"✅ Successfully registered {registered_count}/{len(enum_types)} enum types")
    else:
        log_warning(f"⚠️ Only registered {registered_count}/{len(enum_types)} enum types")
    
    return registered_count == len(enum_types)

class DatabasePool:
    """Manages a pool of database connections for efficient reuse"""
    
    _instance = None
    _pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabasePool, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._pool = None
            self._pool_config = {
                'minconn': int(os.getenv('DB_POOL_MIN_CONNECTIONS', 5)),
                'maxconn': int(os.getenv('DB_POOL_MAX_CONNECTIONS', 20)),
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', 5432)),
                'database': os.getenv('DB_NAME'),
                'user': os.getenv('DB_USER'),
                'password': os.getenv('DB_PASSWORD')
            }
            # Debug logging to see what's being read
            log_info(f"🔍 Database pool config loaded:")
            log_info(f"   DB_NAME: {os.getenv('DB_NAME')}")
            log_info(f"   DB_USER: {os.getenv('DB_USER')}")
            log_info(f"   DB_HOST: {os.getenv('DB_HOST')}")
            log_info(f"   DB_PORT: {os.getenv('DB_PORT')}")
            log_info(f"   Final config: {self._pool_config}")
    
    def get_pool(self):
        """Get or create the connection pool"""
        if self._pool is None:
            try:
                self._pool = psycopg2.pool.SimpleConnectionPool(**self._pool_config)
                log_info(f"🔌 Database pool initialized: {self._pool_config['minconn']}-{self._pool_config['maxconn']} connections")
                log_info(f"📍 Pool config: {self._pool_config['host']}:{self._pool_config['port']}/{self._pool_config['database']}")
            except Exception as e:
                log_error(f"❌ Failed to create database pool: {e}")
                raise
        return self._pool
    
    def get_connection(self):
        """Get a connection from the pool and register enum types"""
        pool = self.get_pool()
        try:
            conn = pool.getconn()
            if conn is None:
                raise Exception("No connections available in pool")
            
            # Register enum types for proper array handling
            _register_enum_types(conn)
            
            return conn
        except Exception as e:
            log_error(f"❌ Failed to get connection from pool: {e}")
            raise
    
    def return_connection(self, conn):
        """Return a connection to the pool"""
        if conn and self._pool:
            try:
                self._pool.putconn(conn)
            except Exception as e:
                log_warning(f"⚠️ Error returning connection to pool: {e}")
    
    @contextmanager
    def get_connection_context(self):
        """Context manager for automatic connection management"""
        conn = None
        try:
            conn = self.get_connection()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.return_connection(conn)
    
    def get_pool_stats(self):
        """Get current pool statistics"""
        if self._pool is None:
            return None
        
        try:
            return {
                'min_connections': self._pool_config['minconn'],
                'max_connections': self._pool_config['maxconn'],
                'pool_initialized': self._pool is not None
            }
        except Exception as e:
            log_warning(f"⚠️ Error getting pool stats: {e}")
            return None
    
    def close_pool(self):
        """Close the connection pool"""
        from app.utils.db import clear_enum_registration_cache
        clear_enum_registration_cache()
        if self._pool:
            try:
                self._pool.closeall()
                log_info("🔌 Database pool closed")
                self._pool = None
            except Exception as e:
                log_warning(f"⚠️ Error closing pool: {e}")

# Global pool instance
db_pool = DatabasePool()

def get_db_pool():
    """Get the global database pool instance"""
    return db_pool

def get_db_connection():
    """Get a connection from the pool (for backward compatibility during transition)"""
    return db_pool.get_connection()

def close_db_connection(conn):
    """Return a connection to the pool (for backward compatibility during transition)"""
    db_pool.return_connection(conn)

@contextmanager
def get_db_connection_context():
    """Context manager for database connections"""
    with db_pool.get_connection_context() as conn:
        yield conn 