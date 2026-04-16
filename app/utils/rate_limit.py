"""
Rate limiting for unauthenticated endpoints using slowapi.

Limits are applied per IP (get_remote_address). Use @limiter.limit("20/minute")
on route handlers. The route must include `request: Request` in its signature.

Authenticated users are rate-limited separately by UserRateLimitMiddleware
(app/auth/middleware/rate_limit_middleware.py) based on JWT claims and tier.
The two systems are independent: slowapi handles IP-based limits on public
endpoints; UserRateLimitMiddleware handles per-user limits on authenticated endpoints.

In DEV_MODE, slowapi rate limiting is disabled so Postman collection runs
(which hit the same localhost IP for dozens of requests) don't get blocked.
Production (DEV_MODE=False) always enforces limits.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config.settings import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=not settings.DEV_MODE,
)
