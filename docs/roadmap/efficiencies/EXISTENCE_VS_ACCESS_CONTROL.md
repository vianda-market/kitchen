# Existence vs. Access Control: Security Analysis

## Current Implementation Pattern

### Pattern: Check Existence First, Then Scope

```python
# Current pattern in app/routes/user.py
scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)

# Step 1: Check if user exists (without scope)
user_exists = user_service.get_by_id(user_id, db, scope=None)
if not user_exists:
    raise user_not_found()  # 404

# Step 2: Check if user has access (with scope)
if scope and not scope.is_global:
    user_with_scope = user_service.get_by_id(user_id, db, scope=scope)
    if not user_with_scope:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this user")
```

### Where This Pattern Is Used

1. **User Routes** (`app/routes/user.py`):
   - `GET /users/{user_id}` - Lines 160-171
   - `PUT /users/{user_id}` - Lines 236-247

2. **Address Routes** (`app/routes/address.py`):
   - Multiple endpoints check existence before scope validation

## Security Risks

### 1. **Information Disclosure (Enumeration Attack)**

**Risk**: An attacker can determine whether a resource exists, even if they don't have access to it.

**Example Attack**:
```python
# Attacker tries to enumerate user IDs
for user_id in potential_user_ids:
    response = GET /users/{user_id}
    if response.status == 404:
        print(f"User {user_id} does NOT exist")
    elif response.status == 403:
        print(f"User {user_id} EXISTS but I don't have access")
```

**Impact**:
- **Low to Medium**: For user IDs (UUIDs are hard to guess)
- **High**: For predictable IDs (sequential IDs, email-based lookups)
- **Critical**: For sensitive resources (admin accounts, system users)

### 2. **Timing Attacks**

**Risk**: Different code paths may have different execution times, revealing information.

**Example**:
- `scope=None` query: Simple SELECT (fast)
- `scope=institution` query: JOIN with institution filtering (slower)

**Mitigation**: Use consistent query patterns and add artificial delays if needed.

### 3. **Human Error / Misconfiguration**

**Risk**: Developers might accidentally expose existence checks without proper authorization.

**Example**:
```python
# BAD: Existence check without proper authorization
def check_user_exists(user_id: UUID):
    return user_service.get_by_id(user_id, db, scope=None)  # No auth check!
```

## Best Practices & Alternatives

### Option 1: Return 404 for Both (Security-First)

**Approach**: Always return 404 if the resource doesn't exist OR if the user doesn't have access.

**Pros**:
- ✅ Prevents information disclosure
- ✅ Prevents enumeration attacks
- ✅ Consistent error messages
- ✅ Simpler implementation

**Cons**:
- ❌ Less helpful error messages for legitimate users
- ❌ Harder to debug authorization issues
- ❌ May confuse users who expect 403 for access denied

**Implementation**:
```python
# Security-first approach
scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
user = user_service.get_by_id(user_id, db, scope=scope)

if not user:
    # Could be "not found" OR "forbidden" - don't reveal which
    raise HTTPException(status_code=404, detail="User not found")
```

**When to Use**:
- High-security environments
- Public-facing APIs
- Resources with predictable IDs
- Sensitive data (admin accounts, system users)

### Option 2: Separate Existence Check Endpoint (Current Pattern Refined)

**Approach**: Provide a separate, authorized endpoint for existence checks.

**Pros**:
- ✅ Clear separation of concerns
- ✅ Can apply different authorization rules
- ✅ Allows existence checks without full data access
- ✅ Better for UI/UX (e.g., "check if username is available")

**Cons**:
- ❌ Additional endpoint to maintain
- ❌ More API surface area
- ❌ Still requires proper authorization

**Implementation**:
```python
# Separate existence check endpoint
@router.get("/users/{user_id}/exists", response_model=dict)
def check_user_exists(
    user_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Check if a user exists (authorized existence check)"""
    # Apply same scope rules as GET /users/{user_id}
    scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)
    user = user_service.get_by_id(user_id, db, scope=scope)
    
    return {"exists": user is not None}
```

**When to Use**:
- When existence checks are a legitimate use case
- For public resources (e.g., "is username available?")
- When you need to distinguish between "not found" and "forbidden" for legitimate reasons

### Option 3: Context-Aware Error Messages (Current Pattern Enhanced)

**Approach**: Return 404 for "not found", 403 for "forbidden", but add rate limiting and logging.

**Pros**:
- ✅ Better user experience (clear error messages)
- ✅ Easier debugging
- ✅ Follows HTTP status code semantics

**Cons**:
- ❌ Information disclosure risk
- ❌ Requires additional security measures

**Enhanced Implementation**:
```python
# Enhanced current pattern with security measures
scope = EntityScopingService.get_scope_for_entity(ENTITY_USER, current_user)

# Rate limit existence checks
@rate_limit(max_requests=10, window_seconds=60)
def get_user_by_id(user_id: UUID, ...):
    # Check existence (with logging for security monitoring)
    user_exists = user_service.get_by_id(user_id, db, scope=None)
    if not user_exists:
        log_security_event("user_lookup_not_found", user_id, current_user)
        raise user_not_found()  # 404
    
    # Check access
    if scope and not scope.is_global:
        user_with_scope = user_service.get_by_id(user_id, db, scope=scope)
        if not user_with_scope:
            log_security_event("user_lookup_forbidden", user_id, current_user)
            raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this user")
    
    log_security_event("user_lookup_success", user_id, current_user)
    return user
```

**Security Measures to Add**:
1. **Rate Limiting**: Prevent enumeration attacks
2. **Security Logging**: Monitor suspicious patterns
3. **IP Blocking**: Block IPs with excessive 404/403 requests
4. **Consistent Timing**: Add artificial delays to prevent timing attacks

**When to Use**:
- Internal/admin APIs
- When user experience is prioritized
- When you can implement proper security measures

### Option 4: Hybrid Approach (Recommended)

**Approach**: Use different strategies based on resource sensitivity and context.

**Implementation**:
```python
# Resource-specific security levels
SECURITY_LEVELS = {
    "user": "medium",  # UUIDs are hard to guess, but still sensitive
    "admin_user": "high",  # Admin accounts are sensitive
    "email": "high",  # Email enumeration is a real risk
    "username": "low",  # Usernames are often public
}

def get_user_by_id(user_id: UUID, ...):
    security_level = SECURITY_LEVELS.get("user", "medium")
    
    if security_level == "high":
        # Security-first: Return 404 for both
        user = user_service.get_by_id(user_id, db, scope=scope)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    else:
        # Context-aware: Distinguish 404 vs 403
        # ... current implementation with rate limiting ...
```

## Recommendations for This Codebase

### Current Assessment

**Current Pattern**: Option 3 (Context-Aware) - Returns 404 for "not found", 403 for "forbidden"

**Risk Level**: **Medium**

**Reasons**:
1. ✅ UUIDs are hard to enumerate (128-bit randomness)
2. ✅ Most resources require authentication
3. ⚠️ No rate limiting currently implemented
4. ⚠️ No security logging for enumeration attempts
5. ⚠️ Email/username lookups could be vulnerable

### Recommended Enhancements

1. **Add Rate Limiting** (High Priority)
   ```python
   from slowapi import Limiter
   from slowapi.util import get_remote_address
   
   limiter = Limiter(key_func=get_remote_address)
   
   @router.get("/users/{user_id}")
   @limiter.limit("10/minute")  # Prevent enumeration
   def get_user_by_id(...):
       ...
   ```

2. **Add Security Logging** (High Priority)
   ```python
   def log_security_event(event_type: str, resource_id: UUID, current_user: dict):
       """Log security events for monitoring"""
       log_warning(f"SECURITY: {event_type} - resource_id={resource_id}, user_id={current_user['user_id']}")
   ```

3. **Consider Hybrid Approach** (Medium Priority)
   - Use security-first (404 for both) for sensitive resources
   - Use context-aware (404 vs 403) for less sensitive resources

4. **Add Timing Attack Protection** (Low Priority)
   ```python
   import time
   
   # Add consistent delay to prevent timing attacks
   start_time = time.time()
   user = user_service.get_by_id(user_id, db, scope=scope)
   elapsed = time.time() - start_time
   
   # Ensure minimum response time
   if elapsed < 0.1:
       time.sleep(0.1 - elapsed)
   ```

## Conclusion

The current pattern (check existence, then scope) is **acceptable for this codebase** given:
- UUIDs are hard to enumerate
- Most endpoints require authentication
- Better user experience with clear error messages

However, **enhancements are recommended**:
1. Add rate limiting to prevent enumeration attacks
2. Add security logging to monitor suspicious patterns
3. Consider hybrid approach for sensitive resources

The pattern should be **documented** and **consistently applied** across all endpoints to avoid confusion and security gaps.

