"""
Performance Monitoring Utilities

Provides decorators and utilities for monitoring endpoint performance
and database operation timing.
"""

import functools
import time
from collections.abc import Callable
from typing import Any

from app.utils.log import log_info, log_warning


def monitor_endpoint(threshold: float = 2.0):
    """
    Decorator to monitor endpoint performance

    Args:
        threshold: Time threshold in seconds to log slow endpoints
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time

                # Log endpoint performance
                log_info(f"🌐 {func.__name__} completed in {execution_time:.3f}s")

                if execution_time > threshold:
                    log_warning(f"🐌 Slow endpoint detected: {func.__name__} took {execution_time:.3f}s")

                return result
            except Exception as e:
                execution_time = time.time() - start_time
                log_warning(f"❌ {func.__name__} failed after {execution_time:.3f}s: {e}")
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time

                # Log endpoint performance
                log_info(f"🌐 {func.__name__} completed in {execution_time:.3f}s")

                if execution_time > threshold:
                    log_warning(f"🐌 Slow endpoint detected: {func.__name__} took {execution_time:.3f}s")

                return result
            except Exception as e:
                execution_time = time.time() - start_time
                log_warning(f"❌ {func.__name__} failed after {execution_time:.3f}s: {e}")
                raise

        # Return appropriate wrapper based on function type
        if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        return sync_wrapper

    return decorator


def monitor_database_operation(operation_type: str = "Database"):
    """
    Context manager for monitoring database operations

    Args:
        operation_type: Type of operation being monitored
    """

    class DatabaseOperationMonitor:
        def __init__(self, op_type: str):
            self.op_type = op_type
            self.start_time = None

        def __enter__(self):
            self.start_time = time.time()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.start_time:
                execution_time = time.time() - self.start_time
                log_info(f"📊 {self.op_type} operation completed in {execution_time:.3f}s")

                if execution_time > 1.0:  # Log slow operations
                    log_warning(f"🐌 Slow {self.op_type.lower()} operation: {execution_time:.3f}s")

    return DatabaseOperationMonitor(operation_type)


# Example usage:
# @monitor_endpoint(threshold=1.0)
# async def my_endpoint():
#     with monitor_database_operation("User Lookup"):
#         # ... database operations
#     return result
