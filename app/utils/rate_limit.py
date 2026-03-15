"""
Rate limiting for unauthenticated endpoints using slowapi.

Limits are applied per IP (get_remote_address). Use @limiter.limit("20/minute")
on route handlers. The route must include `request: Request` in its signature.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
