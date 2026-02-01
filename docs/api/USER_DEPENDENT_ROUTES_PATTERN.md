# User-Dependent Routes Pattern

## Overview

This document describes the architectural pattern for handling CRUD routes that require user context (user_id extraction from authenticated users).

## Problem

Some entities require the `user_id` field to be automatically set from the authenticated user context, while others are managed by administrators and don't need user context.

## Solution

We separate routes into two categories:

### 1. Admin/System Routes (`crud_routes.py`)
- **Purpose**: Operations performed by administrators or system processes
- **User Context**: Not required
- **Examples**: Role, Product, Plan, Restaurant, CreditCurrency, Institution, etc.
- **Pattern**: Use generic route factory

### 2. User-Dependent Routes (`crud_routes_user.py`)
- **Purpose**: Operations performed by end-users who log into the app
- **User Context**: Required - `user_id` extracted from authenticated user
- **Examples**: Subscription, PaymentMethod, ClientBill, PlateSelection, ClientPaymentAttempt, etc.
- **Pattern**: Enhanced route factory with user context extraction

### 3. Immutable Entity Routes
- **Purpose**: Entities that cannot be modified after creation (payment attempts, bank accounts)
- **User Context**: Depends on entity type (admin vs user)
- **Modification**: Not allowed - only CREATE, READ, DELETE operations
- **Examples**: InstitutionPaymentAttempt, ClientPaymentAttempt, InstitutionBankAccount
- **Pattern**: Enhanced route factory with `allows_modification=False`

## Implementation Pattern

### For User-Dependent Entities

1. **Add route function** in route factory with `requires_user_context=True`
2. **Include in user routes**: Add to `crud_routes_user.py`

### For Immutable Entities

1. **Add route function** in route factory with `allows_modification=False`
2. **Determine user context**: Set `requires_user_context=True/False` based on entity type
3. **Include in appropriate routes**: Admin routes or user routes

### Example Templates

#### For User-Dependent Entities:
```python
# app/services/route_factory.py
def create_{entity}_routes() -> APIRouter:
    """Create routes for {Entity} entity (user-dependent)"""
    from app.services.crud_service import {entity}_service
    from app.schemas.{entity} import {Entity}CreateSchema, {Entity}UpdateSchema, {Entity}ResponseSchema
    
    config = RouteConfig(
        prefix="/{entities}",
        tags=["{Entity}s"],
        entity_name="{entity}",
        entity_name_plural="{entities}"
    )
    
    return create_crud_routes(
        config=config,
        service={entity}_service,
        create_schema={Entity}CreateSchema,
        update_schema={Entity}UpdateSchema,
        response_schema={Entity}ResponseSchema,
        requires_user_context=True  # ← KEY: Auto-extracts user_id
    )
```

#### For Immutable Entities:
```python
# app/services/route_factory.py
def create_{entity}_routes() -> APIRouter:
    """Create routes for {Entity} entity (immutable - no modification allowed)"""
    from app.services.crud_service import {entity}_service
    from app.schemas.{entity} import {Entity}CreateSchema, {Entity}ResponseSchema
    
    config = RouteConfig(
        prefix="/{entities}",
        tags=["{Entity}s"],
        entity_name="{entity}",
        entity_name_plural="{entities}"
    )
    
    return create_crud_routes(
        config=config,
        service={entity}_service,
        create_schema={Entity}CreateSchema,
        update_schema={Entity}CreateSchema,  # Not used for immutable entities
        response_schema={Entity}ResponseSchema,
        requires_user_context=False,  # Admin/system entity
        allows_modification=False  # ← KEY: Immutable entity - no PUT/update routes
    )
```

## Route Registration

### In `crud_routes_user.py`:
```python
from app.routes.{entity}_user import router as {entity}_router
crud_router_user.include_router({entity}_router)
```

### In `application.py`:
```python
# User-dependent CRUD routes (require user_id context)
app.include_router(crud_router_user)

# Versioned user CRUD router
v1_crud_router_user = create_versioned_router("api", ["User CRUD"], APIVersion.V1)
v1_crud_router_user.include_router(crud_router_user)
app.include_router(v1_crud_router_user)
```

## Identifying User-Dependent Entities

An entity should use user-dependent routes if:

1. **Ownership**: The entity "belongs" to a user (e.g., user's subscriptions, user's payment methods)
2. **User Context**: Operations require knowing which user is performing them
3. **Data Isolation**: Users should only see/modify their own data
4. **Business Logic**: User-specific business rules apply

### Examples:

**User-Dependent** ✅:
- `Subscription` - belongs to a user
- `PaymentMethod` - user's payment methods
- `ClientBill` - user's bills
- `PlateSelection` - user's food orders
- `UserProfile` - user's profile data

**Admin/System** ✅:
- `Role` - system roles
- `Product` - restaurant products
- `Plan` - subscription plans
- `Institution` - organizations
- `CreditCurrency` - system currencies

## Benefits

1. **Clear Separation**: Easy to understand which routes need user context
2. **Consistent Pattern**: Standardized approach for user-dependent entities
3. **Security**: Automatic user_id extraction prevents context confusion
4. **Maintainability**: Centralized user context handling
5. **Scalability**: Easy to add new user-dependent entities

## Migration Guide

To migrate an existing entity to user-dependent routes:

1. Move the entity from `crud_routes.py` to `crud_routes_user.py`
2. Create custom route file following the template
3. Update route registration
4. Test user context extraction
5. Update documentation

## Current Implementation

- ✅ `Subscription` - migrated to user-dependent routes
- 🔄 `PaymentMethod` - candidate for migration
- 🔄 `ClientBill` - candidate for migration
- 🔄 `PlateSelection` - candidate for migration
