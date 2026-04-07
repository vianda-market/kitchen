"""
Rate limiting for unauthenticated endpoints using slowapi.

Limits are applied per IP (get_remote_address). Use @limiter.limit("20/minute")
on route handlers. The route must include `request: Request` in its signature.

Authenticated users are rate-limited separately by UserRateLimitMiddleware
(app/auth/middleware/rate_limit_middleware.py) based on JWT claims and tier.
The two systems are independent: slowapi handles IP-based limits on public
endpoints; UserRateLimitMiddleware handles per-user limits on authenticated endpoints.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
