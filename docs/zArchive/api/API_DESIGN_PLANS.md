# API Design Plans: User Profile Updates and Employer Assignment

## Security Analysis: JWT Path Parameter vs `/me` Endpoint

### Current Approach: `PUT /users/{user_id}`

**How it works:**
- Client extracts `user_id` from JWT token payload
- Client sends `PUT /users/{user_id}` with `user_id` in URL path
- Server validates JWT via `get_current_user` dependency
- Server enforces access control:
  - **Customers**: `user_scope.enforce_user(user_id)` ensures they can only update themselves
  - **Employees/Suppliers**: Institution scope filtering

**Security Risks:**
1. **Path Parameter Manipulation**: Client can send any `user_id` in the URL path
2. **Enforcement Logic Dependency**: Security relies on correct implementation of `enforce_user()` check
3. **Error-Prone**: If enforcement logic is missing or buggy, user could update wrong user
4. **Attack Vector**: Malicious client could attempt to update other users' profiles if enforcement fails

**Example Attack Scenario:**
```http
PUT /users/victim-user-id
Authorization: Bearer attacker-token
{
  "employer_id": "attacker-controlled-employer"
}
```
If `enforce_user()` check is missing or fails, attacker could update victim's profile.

### Recommended Approach: `PUT /users/me`

**How it works:**
- Client sends `PUT /users/me` (no `user_id` in path)
- Server extracts `user_id` directly from JWT token via `current_user` dependency
- Server uses `current_user["user_id"]` as source of truth
- No path parameter to manipulate

**Security Benefits:**
1. **No Path Parameter**: Eliminates possibility of updating wrong user
2. **Single Source of Truth**: `current_user["user_id"]` from JWT is authoritative
3. **Simpler Logic**: No need for `enforce_user()` checks for self-updates
4. **Industry Best Practice**: Follows RESTful conventions (`/me` pattern)
5. **Principle of Least Privilege**: User can only update themselves, period

**Security Comparison:**

| Aspect | JWT Path Parameter | `/me` Endpoint |
|--------|-------------------|----------------|
| Path manipulation risk | ⚠️ High | ✅ None |
| Enforcement complexity | ⚠️ Requires checks | ✅ Automatic |
| Error-prone | ⚠️ Yes | ✅ No |
| Industry standard | ⚠️ Less common | ✅ Common pattern |
| Attack surface | ⚠️ Larger | ✅ Minimal |

**Conclusion:** `/me` endpoint is **more secure** and **better practice** because:
- Eliminates entire class of path parameter manipulation attacks
- Simpler, less error-prone implementation
- Follows industry best practices
- Reduces attack surface

---

## Plan 1: Generalized `/me` Endpoint for Profile Updates

### Overview
Create a comprehensive `/users/me` endpoint pattern that handles all self-update operations, including employer assignment.

### Endpoints

#### 1. `GET /users/me` - Get Current User Profile
**Purpose**: Retrieve current user's profile information

**Implementation:**
```python
@router.get("/me", response_model=UserEnrichedResponseSchema)
def get_my_profile(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get current user's profile with enriched data"""
    def _get_my_profile():
        enriched_user = get_enriched_user_by_id(
            current_user["user_id"],
            db,
            scope=None,
            include_archived=False
        )
        if not enriched_user:
            raise HTTPException(status_code=404, detail="User not found")
        return enriched_user
    
    return handle_business_operation(_get_my_profile, "profile retrieval")
```

#### 2. `PUT /users/me` - Update Current User Profile
**Purpose**: Update any profile field (including employer assignment)

**Access**: All users (Customers, Supplier Admins, Employee Admins, etc.) use this for self-updates

**Request Schema:**
```python
class UserProfileUpdateSchema(BaseModel):
    """Schema for updating current user's profile"""
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    cellphone: Optional[str] = Field(None, max_length=20)
    employer_id: Optional[UUID] = None
    
    @validator('employer_id')
    def validate_employer_exists(cls, v):
        # Validation happens in endpoint, not schema
        return v
```

**Implementation:**
```python
@router.put("/me", response_model=UserResponseSchema)
def update_my_profile(
    profile_update: UserProfileUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Update current user's profile (self-update only)"""
    def _update_my_profile():
        # Validate employer exists if employer_id is being updated
        if profile_update.employer_id is not None:
            employer = employer_service.get_by_id(profile_update.employer_id, db)
            if not employer:
                raise HTTPException(
                    status_code=404,
                    detail="Employer not found"
                )
        
        # Prepare update data
        update_data = profile_update.dict(exclude_unset=True)
        update_data["modified_by"] = current_user["user_id"]
        
        # Update user profile
        updated = user_service.update(
            current_user["user_id"],
            update_data,
            db,
            scope=None  # No scope needed - self-update only
        )
        
        if not updated:
            raise HTTPException(
                status_code=500,
                detail="Failed to update profile"
            )
        return updated
    
    return handle_business_operation(_update_my_profile, "profile update")
```

**Usage Example:**
```http
PUT /users/me
Authorization: Bearer <token>
{
  "employer_id": "existing-employer-uuid"
}
```

**Access Pattern**:
- ✅ **All users** should use this endpoint for self-updates (prevents `user_id` ingestion errors)
- ✅ **Supplier Admins** use this in vianda-platform client for their own profile
- ✅ **Employee Admins/Super Admins** use this for self-updates
- ❌ **Not for** updating other users (admins use `PUT /users/{user_id}` for that)
- ✅ **All users** should use this endpoint for self-updates (prevents `user_id` ingestion errors)
- ✅ **Supplier Admins** use this in vianda-platform client for their own profile
- ✅ **Employee Admins/Super Admins** use this for self-updates
- ❌ **Not for** updating other users (admins use `PUT /users/{user_id}` for that)

#### 3. `PUT /users/me/terminate` - Terminate Account
**Purpose**: Archive/terminate current user's account (soft delete)

**Implementation:**
```python
@router.put("/me/terminate", response_model=dict)
def terminate_my_account(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Terminate current user's account (archive/soft delete)
    
    This is a destructive operation that archives the user's account.
    Users cannot delete themselves - only archive/terminate.
    Separate endpoint from regular profile updates for safety.
    """
    def _terminate_account():
        # Archive user (soft delete via is_archived = TRUE)
        success = user_service.soft_delete(
            current_user["user_id"],
            current_user["user_id"],  # Self-termination
            db,
            scope=None
        )
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to terminate account"
            )
        return {"detail": "Account terminated successfully"}
    
    return handle_business_operation(_terminate_account, "account termination")
```

**Usage:**
```http
PUT /users/me/terminate
Authorization: Bearer <token>
```

**Rationale**:
- More destructive than regular profile updates
- Separate endpoint for clarity and safety
- Allows for additional validation/confirmation if needed
- Clear separation from admin deletion operations

### Benefits
- ✅ Single endpoint for all profile updates
- ✅ Secure (no path parameter manipulation)
- ✅ Validates employer existence
- ✅ Reusable for future profile fields
- ✅ Follows RESTful best practices

### Limitations
- Generic endpoint (less semantic than dedicated employer endpoint)
- All profile updates go through same endpoint

---

## Plan 2: Employer Assignment Workflow

### Overview
Dedicated endpoints for the complete employer assignment workflow, supporting:
1. Get all employers (for selection)
2. Get addresses for a selected employer
3. Assign existing employer to user
4. Create new employer and assign
5. Add address to existing employer

### Endpoints

#### 1. `GET /employers/` - Get All Employers
**Status**: ✅ Already exists (`app/routes/employer.py:45`)

**Usage:**
```http
GET /employers/?include_archived=false
Authorization: Bearer <token>
```

**Response:**
```json
[
  {
    "employer_id": "uuid",
    "name": "Acme Corp",
    "address_id": "uuid",
    "status": "Active",
    "created_date": "..."
  }
]
```

#### 2. `GET /employers/{employer_id}/addresses` - Get Addresses for Employer
**Purpose**: Retrieve all addresses associated with an employer

**Implementation:**
```python
@router.get("/{employer_id}/addresses", response_model=List[AddressResponseSchema])
def get_employer_addresses(
    employer_id: UUID,
    include_archived: bool = include_archived_query("addresses"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all addresses for a specific employer"""
    def _get_employer_addresses():
        # Validate employer exists
        employer = employer_service.get_by_id(employer_id, db)
        if not employer:
            raise employer_not_found()
        
        # Query all addresses for this employer using employer_id FK
        # This is efficient with the partial index on employer_id
        addresses = address_service.get_by_field(
            "employer_id",
            employer_id,
            db,
            scope=None
        )
        
        # If multiple addresses, return as list; if single, wrap in list
        if not addresses:
            return []
        if isinstance(addresses, list):
            return addresses
        return [addresses]
    
    return handle_business_operation(_get_employer_addresses, "employer addresses retrieval")
```

**Schema Change**: `address_info` table now includes `employer_id` foreign key (see Schema Updates section below).

#### 3. `PUT /users/me/employer` - Assign Existing Employer
**Purpose**: Assign an existing employer to current user

**Implementation:**
```python
@router.put("/me/employer", response_model=UserResponseSchema)
def assign_my_employer(
    employer_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Assign an existing employer to current user"""
    def _assign_employer():
        # Validate employer exists
        employer = employer_service.get_by_id(employer_id, db)
        if not employer:
            raise HTTPException(
                status_code=404,
                detail="Employer not found"
            )
        
        # Update user's employer_id
        update_data = {
            "employer_id": employer_id,
            "modified_by": current_user["user_id"]
        }
        
        updated = user_service.update(
            current_user["user_id"],
            update_data,
            db,
            scope=None
        )
        
        if not updated:
            raise HTTPException(
                status_code=500,
                detail="Failed to assign employer"
            )
        return updated
    
    return handle_business_operation(_assign_employer, "employer assignment")
```

**Usage:**
```http
PUT /users/me/employer?employer_id=uuid
Authorization: Bearer <token>
```

#### 4. `POST /employers/` - Create New Employer
**Status**: ✅ Already exists (`app/routes/employer.py:54`)

**Usage:**
```http
POST /employers/
Authorization: Bearer <token>
{
  "name": "New Company",
  "address": {
    "address_type": ["Customer Employer"],
    "country": "US",
    "province": "CA",
    "city": "San Francisco",
    "postal_code": "94102",
    "street_type": "St",
    "street_name": "Market",
    "building_number": "123"
  }
}
```

**Response:**
```json
{
  "employer_id": "new-uuid",
  "name": "New Company",
  "address_id": "address-uuid",
  "status": "Active"
}
```

**Workflow after creation:**
```http
PUT /users/me/employer?employer_id=new-uuid
```

#### 5. `POST /employers/{employer_id}/addresses` - Add Address to Employer
**Purpose**: Add an additional address to an existing employer

**Implementation:**
```python
@router.post("/{employer_id}/addresses", response_model=AddressResponseSchema, status_code=status.HTTP_201_CREATED)
def add_employer_address(
    employer_id: UUID,
    address_create: AddressCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Add an additional address to an existing employer"""
    def _add_employer_address():
        # Validate employer exists
        employer = employer_service.get_by_id(employer_id, db)
        if not employer:
            raise employer_not_found()
        
        # Prepare address data
        address_data = address_create.dict()
        
        # Ensure address_type includes "Customer Employer"
        from app.config import AddressType
        address_types = address_data.get("address_type", [])
        if AddressType.CUSTOMER_EMPLOYER not in address_types:
            if isinstance(address_types, list):
                address_types.append(AddressType.CUSTOMER_EMPLOYER)
            else:
                address_data["address_type"] = [AddressType.CUSTOMER_EMPLOYER]
        
        # Link address to employer
        address_data["employer_id"] = employer_id
        address_data["modified_by"] = current_user["user_id"]
        
        # Create address with employer_id
        new_address = address_service.create(address_data, db)
        if not new_address:
            raise HTTPException(
                status_code=500,
                detail="Failed to create address"
            )
        
        return new_address
    
    return handle_business_operation(_add_employer_address, "employer address creation")
```

**Schema Change**: `address_info` table now includes `employer_id` foreign key (see Schema Updates section below).

### Complete User Workflow

#### Scenario A: Employer Exists
1. **Get all employers**: `GET /employers/`
2. **User selects employer**: `employer_id = "selected-uuid"`
3. **Get employer addresses**: `GET /employers/{employer_id}/addresses`
4. **If address visible**: User proceeds
5. **If address not visible**: `POST /employers/{employer_id}/addresses` to add new address
6. **Assign employer to user**: `PUT /users/me/employer?employer_id={employer_id}`

#### Scenario B: Employer Doesn't Exist
1. **Get all employers**: `GET /employers/` (returns empty or no match)
2. **Create new employer**: `POST /employers/` with name and initial address
3. **Get created employer ID**: From response `employer_id`
4. **Assign employer to user**: `PUT /users/me/employer?employer_id={new_employer_id}`
5. **Add additional address (optional)**: `POST /employers/{employer_id}/addresses`

### Schema Updates

**Decision**: Add `employer_id` to `address_info` table to support efficient employer address queries.

**Schema Change:**
```sql
-- In app/db/schema.sql, update address_info table:
CREATE TABLE address_info (
    address_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    institution_id UUID NOT NULL,
    user_id UUID NOT NULL,
    employer_id UUID NULL,  -- NEW: Links address to employer (nullable)
    address_type address_type_enum[] NOT NULL,
    -- ... rest of columns ...
    FOREIGN KEY (institution_id) REFERENCES institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (employer_id) REFERENCES employer_info(employer_id) ON DELETE SET NULL  -- NEW FK
);
```

**Also update `address_history` table:**
```sql
CREATE TABLE address_history (
    -- ... existing columns ...
    employer_id UUID NULL,  -- NEW: Track employer_id in history
    -- ... rest of columns ...
);
```

**Index for Performance:**
```sql
-- In app/db/index.sql, add partial index for employer_id queries:
CREATE INDEX IF NOT EXISTS idx_address_info_employer_id 
ON address_info(employer_id) 
WHERE employer_id IS NOT NULL AND NOT is_archived;
```

**Why NULL Values Are Not Detrimental:**

1. **Standard Pattern**: NULL foreign keys are a common and accepted database pattern for optional relationships
2. **PostgreSQL Efficiency**: 
   - NULL values are stored efficiently (NULL bitmap, minimal space)
   - Partial indexes (`WHERE employer_id IS NOT NULL`) exclude NULLs from the index
   - Queries on `employer_id` are fast even with many NULLs
3. **Query Performance**: 
   - `WHERE employer_id = ?` queries use the partial index (only non-NULL rows indexed)
   - `WHERE employer_id IS NULL` queries can use a separate index or table scan
   - No performance degradation expected
4. **Data Integrity**: 
   - Foreign key constraint ensures referential integrity when `employer_id` is set
   - `ON DELETE SET NULL` prevents orphaned addresses if employer is deleted
5. **Real-World Usage**:
   - Many addresses won't have `employer_id` (restaurant, institution_entity, bank_account, user home)
   - Only addresses with `address_type` containing "Customer Employer" will have `employer_id`
   - This is expected and correct behavior

**Benefits:**
- ✅ Direct query: `SELECT * FROM address_info WHERE employer_id = ?` (fast with index)
- ✅ Proper relationship between employers and multiple addresses
- ✅ Better data integrity (FK constraint)
- ✅ Efficient queries (partial index on non-NULL values)
- ✅ No performance impact from NULL values

### Benefits
- ✅ Dedicated, semantic endpoints for employer workflow
- ✅ Clear separation of concerns
- ✅ Supports complete workflow (list → select → assign/create → add addresses)
- ✅ Secure (uses `/me` pattern for user updates)

### Limitations
- Requires multiple API calls for complete workflow
- Schema update required: `employer_id` must be added to `address_info` table (see Schema Updates section above)

---

## Recommendation

**Use Plan 1 (Generalized `/me` endpoint) for profile updates** because:
- More secure
- Simpler to maintain
- Reusable for all profile fields
- Industry best practice

**Use Plan 2 endpoints for employer workflow** because:
- Semantic and clear
- Supports complete user journey
- Better UX (dedicated endpoints)

**Combined Approach:**
- **Schema Update**: Add `employer_id` to `address_info` table (see Schema Updates section above)
- Implement `PUT /users/me` for general profile updates (Plan 1)
- Implement `PUT /users/me/employer` for employer assignment (Plan 2)
- Keep existing `GET /employers/` and `POST /employers/`
- Add `GET /employers/{employer_id}/addresses` and `POST /employers/{employer_id}/addresses`

This gives you:
- ✅ Secure profile updates via `/me`
- ✅ Semantic employer assignment endpoint
- ✅ Complete employer workflow support
- ✅ Efficient address queries via `employer_id` FK
- ✅ Proper data relationships and integrity

---

## Deprecation Plan

**⚠️ Important**: Before implementing new endpoints, review the [API Deprecation Plan](./API_DEPRECATION_PLAN.md) to understand which legacy endpoints should be deprecated.

**Summary**:
- `PUT /users/{user_id}` - **DEPRECATE for self-updates** (all users use `PUT /users/me`), **KEEP for admin operations** (updating other users)
- `GET /users/{user_id}` - **DEPRECATE for self-reads** (all users use `GET /users/me`), **KEEP for admin operations** (reading other users)
- `GET /users/enriched/{user_id}` - **DEPRECATE for self-reads** (all users use `GET /users/me`), **KEEP for admin operations**

**Access Pattern Matrix**:
| Role | Self-Updates | Manage Others | Scope |
|------|--------------|---------------|-------|
| Customer | `/me` only | ❌ None | N/A |
| Supplier Admin | `/me` (prevent user_id errors) | `/{user_id}` (institution scope) | Institution |
| Supplier Operator | `/me` only | ❌ None | N/A |
| Employee Admin | `/me` (prevent user_id errors) | `/{user_id}` (global scope) | Global |
| Employee Management | `/me` (prevent user_id errors) | `/{user_id}` (institution scope) | Institution |
| Employee Operator | `/me` only | ❌ None | N/A |

**Key Principle**: All users should use `/me` endpoints for self-updates to prevent `user_id` ingestion errors. Only admins use `/{user_id}` endpoints for managing OTHER users.

**Employee Role Structure**:
- **Employee Admin**: Global scope - can manage any user across all institutions
- **Employee Management**: Institution scope - can manage users within their institution only
- **Employee Operator**: Self-updates only - no management capabilities, uses `/me` endpoints exclusively

**Note**: This structure requires adding `OPERATOR` and `MANAGEMENT` role names to the `RoleName` enum. See implementation checklist for enum updates.

The deprecation plan includes:
- Security rationale
- Role-based access patterns
- Migration strategy
- Implementation timeline
- Testing updates
- Postman collection updates

---

## Implementation Checklist

### Phase 0: Review Deprecation Plan & Role Structure
- [ ] Review `docs/API_DEPRECATION_PLAN.md`
- [ ] Decide on deprecation timeline
- [ ] Plan migration strategy for existing clients
- [ ] **Add new role names to `RoleName` enum**: `OPERATOR` and `MANAGEMENT`
- [ ] **Update role validation**: Add `OPERATOR` and `MANAGEMENT` to valid Employee role combinations
- [ ] **Update schema**: Ensure database supports new role names
- [ ] **Map existing roles**: Decide if `SUPER_ADMIN` → Employee Admin (global) or create new mapping

### Phase 1: Schema Updates
- [ ] Add `employer_id UUID NULL` to `address_info` table in `app/db/schema.sql`
- [ ] Add `FOREIGN KEY (employer_id) REFERENCES employer_info(employer_id) ON DELETE SET NULL` to `address_info`
- [ ] Add `employer_id UUID NULL` to `address_history` table
- [ ] Add partial index `idx_address_info_employer_id` in `app/db/index.sql`
- [ ] Update `AddressDTO` to include `employer_id: Optional[UUID]`
- [ ] Update `AddressCreateSchema` and `AddressUpdateSchema` to include optional `employer_id`
- [ ] Update `AddressResponseSchema` to include `employer_id`

### Phase 2: API Endpoints
- [ ] Implement `GET /users/me` endpoint
- [ ] Implement `PUT /users/me` endpoint
- [ ] Implement `PUT /users/me/terminate` endpoint (account termination)
- [ ] Implement `PUT /users/me/employer` endpoint
- [ ] Implement `GET /employers/{employer_id}/addresses` endpoint
- [ ] Implement `POST /employers/{employer_id}/addresses` endpoint
- [ ] Add deprecation warnings to `PUT /users/{user_id}` for self-updates (see deprecation plan)
- [ ] Add deprecation warnings to `GET /users/{user_id}` for self-reads (see deprecation plan)
- [ ] Update `PUT /users/{user_id}` to detect and warn on self-updates (all user types)

### Phase 3: Service Layer Updates
- [ ] Update `address_service.create()` to handle `employer_id`
- [ ] Update `address_service.get_by_field()` to support `employer_id` queries
- [ ] Update `create_employer_with_address()` to set `employer_id` on address creation
- [ ] Update any address queries to include `employer_id` where applicable

### Phase 4: Testing
- [ ] Test `GET /users/me` returns current user profile
- [ ] Test `PUT /users/me` updates profile fields
- [ ] Test `PUT /users/me/terminate` archives user account
- [ ] Test `PUT /users/me/employer` assigns employer to user
- [ ] Test `GET /employers/{employer_id}/addresses` returns all addresses for employer
- [ ] Test `POST /employers/{employer_id}/addresses` creates address linked to employer
- [ ] Test workflow: create employer → add addresses → assign to user
- [ ] Test NULL `employer_id` handling (addresses without employers)
- [ ] Test Employee Operator can only use `/me` endpoints (no access to `/{user_id}` for others)
- [ ] Test Employee Management can use `/{user_id}` for institution users only
- [ ] Test Employee Admin can use `/{user_id}` for any user (global scope)

