import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Simple in-memory cache to store permission decisions.
# In production, consider using Redis or similar.
permission_cache = {}

class PermissionCacheMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, cache_ttl: int = 300):  # TTL in seconds (default 5 minutes)
        super().__init__(app)
        self.cache_ttl = cache_ttl

    async def dispatch(self, request: Request, call_next):
        # Assume that once the token is verified and user info is in the request state,
        # we can use user_id as key for permission cache.
        token = request.headers.get("Authorization")
        if token:
            # Extract user_id from token. In a real app, you might have already stored user data 
            # in the request state using your authentication middleware.
            # Here, we simulate extraction from an Authorization header "Bearer <token>".
            parts = token.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                from app.auth.security import verify_token
                user_data = verify_token(parts[1])
                if user_data:
                    user_id = user_data.get("sub")
                    # Check if permissions for this user_id are in cache and not expired.
                    cached = permission_cache.get(user_id)
                    if cached:
                        entry, timestamp = cached
                        if time.time() - timestamp < self.cache_ttl:
                            # Attach cached permissions to the request.
                            request.state.permissions = entry
                        else:
                            # Cache expired, remove entry.
                            permission_cache.pop(user_id, None)
                    else:
                        # Optionally initialize an empty permissions structure.
                        request.state.permissions = None

        # Process request
        response: Response = await call_next(request)

        # After the request, if permissions were computed during the request (e.g., by a middleware
        # or an endpoint), cache them for this user_id.
        if token:
            if len(parts) == 2 and parts[0].lower() == "bearer" and user_data:
                user_id = user_data.get("sub")
                # Assume that during processing, your endpoint or other middleware sets:
                # request.state.permissions = <computed permission dict>
                if hasattr(request.state, "permissions") and request.state.permissions is not None:
                    permission_cache[user_id] = (request.state.permissions, time.time())

        # Prune expired entries when cache is large to prevent unbounded growth
        if len(permission_cache) > 1000:
            now = time.time()
            expired = [uid for uid, (_, ts) in permission_cache.items() if now - ts >= self.cache_ttl]
            for uid in expired:
                permission_cache.pop(uid, None)

        return response
