"""
Database Dependencies for FastAPI

Provides request-scoped database connections using the connection pool.
"""

from fastapi import Depends
import psycopg2.extensions
from app.utils.db_pool import get_db_connection_context

async def get_db():
    """
    FastAPI dependency that provides a database connection for the request.
    
    This dependency ensures that:
    1. Each request gets a connection from the pool
    2. The connection is automatically returned to the pool
    3. Transactions are properly managed
    4. Connections are reused efficiently
    
    Usage:
        @router.post("/")
        async def my_endpoint(db: psycopg2.extensions.connection = Depends(get_db)):
            # Use db connection for all database operations
            result = db_read("SELECT * FROM table", connection=db)
            return result
    """
    with get_db_connection_context() as conn:
        yield conn 