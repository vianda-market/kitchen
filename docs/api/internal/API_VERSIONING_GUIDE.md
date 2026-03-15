# API Versioning Implementation Guide

## Overview

This guide outlines the API versioning infrastructure implemented for the Kitchen API. The system is designed to support multiple API versions while maintaining backward compatibility.

## Current Status

- **Current Version**: v1 (default)
- **Supported Versions**: v1
- **Versioning Strategy**: URL Path (`/api/v1/plans/`)
- **Schema Versioning**: Infrastructure ready, currently all schemas use v1

## Architecture

### 1. Versioning Infrastructure

```python
# app/core/versioning.py
- VersionConfig: Global versioning configuration
- get_version_from_request(): Extract version from requests
- create_versioned_router(): Create versioned routers
- Versioning strategies: URL path, header, query parameter
```

### 2. Schema Versioning

```python
# app/schemas/versioned_schemas.py
- VersionedSchemaRegistry: Manage schema versions
- get_schema_for_version(): Get version-specific schemas
- Backward compatibility maintained
```

### 3. Route Versioning

```python
# app/services/versioned_route_factory.py
- VersionedRouteConfig: Extended route configuration
- create_versioned_crud_routes(): Create versioned CRUD routes
- Automatic version info in responses
```

## Implementation Strategy

### Phase 1: Infrastructure Setup (Current)

All APIs use v1 by default with versioning infrastructure ready:

```python
# Current URLs (all work the same)
/api/v1/plans/     # Explicit v1
/api/plans/        # Defaults to v1 (backward compatibility)
```

### Phase 2: Static Versioning (Development)

- All APIs explicitly use `/v1/` prefix
- Versioning infrastructure is active but unused
- No breaking changes to current behavior

### Phase 3: Dynamic Versioning (Release)

When breaking changes are needed:

```python
# Future URLs
/api/v1/plans/     # Existing API (maintained)
/api/v2/plans/     # New API with breaking changes
```

## Usage Examples

### 1. Creating Versioned Routes

```python
from app.services.versioned_route_factory import create_versioned_plan_routes
from app.core.versioning import APIVersion

# Create v1 routes (current)
v1_router = create_versioned_plan_routes(APIVersion.V1)

# Create v2 routes (future)
v2_router = create_versioned_plan_routes(APIVersion.V2)
```

### 2. Using Version-Specific Schemas

```python
from app.schemas.versioned_schemas import get_schema_for_version
from app.core.versioning import APIVersion

# Get v1 schema
v1_schema = get_schema_for_version("PlanCreate", APIVersion.V1)

# Get v2 schema (when available)
v2_schema = get_schema_for_version("PlanCreate", APIVersion.V2)
```

### 3. Version-Aware Endpoints

```python
from app.core.versioning import get_current_version, APIVersion

@router.get("/")
def get_plans(version: APIVersion = Depends(get_current_version)):
    # Handle version-specific logic
    if version == APIVersion.V1:
        # v1 logic
        pass
    elif version == APIVersion.V2:
        # v2 logic
        pass
```

## Adding New Versions

### 1. Update Version Configuration

```python
# app/core/versioning.py
VERSION_CONFIG = VersionConfig(
    default_version=APIVersion.V1,
    supported_versions=[APIVersion.V1, APIVersion.V2],  # Add v2
    strategy=VersioningStrategy.URL_PATH,
    deprecated_versions=[]  # Mark v1 as deprecated when ready
)
```

### 2. Create Version-Specific Schemas

```python
# app/schemas/versioned_schemas.py
class PlanCreateSchemaV2(BaseModel):
    # New required field
    metadata: Optional[dict] = None
    # Changed field
    price: Decimal = Field(..., gt=0)  # Changed from float
    
    # All other fields remain the same
    credit_currency_id: UUID
    name: str = Field(..., max_length=100)
    credit: int = Field(..., gt=0)
    rollover: Optional[bool] = True
    rollover_cap: Optional[Decimal] = None

# Register v2 schema
schema_registry.register_schema("PlanCreate", APIVersion.V2, PlanCreateSchemaV2)
```

### 3. Create Version-Specific Routes

```python
# app/services/versioned_route_factory.py
def create_versioned_plan_routes_v2() -> APIRouter:
    # Custom v2 logic
    router = create_versioned_router("plans", ["Plans"], APIVersion.V2)
    
    @router.post("/")
    def create_plan_v2(plan_data: PlanCreateSchemaV2):
        # v2-specific creation logic
        pass
    
    return router
```

## Migration Strategy

### Backward Compatibility

- **v1 APIs**: Maintained indefinitely during transition
- **Deprecation**: Gradual with advance notice
- **Migration**: Client-driven with support

### Breaking Changes

When introducing breaking changes:

1. **Create v2 endpoints** with new schema
2. **Maintain v1 endpoints** for existing clients
3. **Communicate deprecation** timeline
4. **Provide migration guides**
5. **Monitor usage** and sunset v1 when ready

## Testing

### Version-Specific Testing

```python
def test_v1_plan_creation():
    response = client.post("/v1/plans/", json=plan_data_v1)
    assert response.status_code == 200
    assert "_api_version" in response.json()

def test_v2_plan_creation():
    response = client.post("/v2/plans/", json=plan_data_v2)
    assert response.status_code == 200
    assert response.json()["_api_version"] == "v2"
```

### Backward Compatibility Testing

```python
def test_backward_compatibility():
    # Test that v1 clients still work
    response = client.post("/plans/", json=plan_data_v1)
    assert response.status_code == 200
    assert response.json()["_api_version"] == "v1"
```

## Benefits

### Development Phase
- **Future-Proof**: Ready for versioning when needed
- **No Disruption**: Current development unaffected
- **Consistent Patterns**: Standardized versioning approach

### Release Phase
- **Smooth Transitions**: Gradual migration possible
- **Backward Compatibility**: Existing clients protected
- **Flexible Evolution**: API can evolve without breaking changes

## Next Steps

1. **Phase 1**: Infrastructure ready (✅ Complete)
2. **Phase 2**: Static versioning (✅ Ready to implement)
3. **Phase 3**: Dynamic versioning (🔄 When breaking changes needed)

The versioning infrastructure is now ready for use. All current APIs work exactly as before, but the system is prepared for future API evolution.
