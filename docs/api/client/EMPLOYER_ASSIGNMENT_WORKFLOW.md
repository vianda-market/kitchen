# Employer Assignment Workflow - Backoffice Implementation Guide

## Overview

This document provides implementation guidance for the React web backoffice application to manage employers and their addresses. This is for **Employee Operators, Admins, and Super Admins** to maintain the employer catalog (not for assigning employers to users - that's a separate client-facing workflow).

### Access Control Summary

- **Employees (Admin, Super Admin, Management, Operator)**: Full access (GET, POST, PUT, DELETE)
- **Customers**: 
  - ✅ GET all employers (including enriched endpoints)
  - ✅ POST new employers
  - ✅ POST addresses to existing employers
  - ❌ Cannot PUT/DELETE employers (403 Forbidden)
  - ❌ Cannot PUT/DELETE addresses (403 Forbidden)

### Enriched Endpoints

**Use enriched endpoints** (`/employers/enriched/`) to get address data in a single query, eliminating the need for separate address API calls. The enriched response includes all address fields prefixed with `address_`.

---

## API Endpoints Reference

### Employer Endpoints

| Endpoint | Method | Purpose | Response | Access Control |
|----------|--------|---------|----------|----------------|
| `GET /api/v1/employers/` | GET | List all employers | `List[EmployerResponseSchema]` | All authenticated users |
| `GET /api/v1/employers/enriched/` | GET | List all employers with address data | `List[EmployerEnrichedResponseSchema]` | All authenticated users |
| `GET /api/v1/employers/{employer_id}` | GET | Get single employer | `EmployerResponseSchema` | All authenticated users |
| `GET /api/v1/employers/enriched/{employer_id}` | GET | Get single employer with address data | `EmployerEnrichedResponseSchema` | All authenticated users |
| `GET /api/v1/employers/search?search_term=...` | GET | Search employers by name | `List[EmployerResponseSchema]` | All authenticated users |
| `POST /api/v1/employers/` | POST | Create employer with address (atomic) | `EmployerResponseSchema` | All authenticated users |
| `PUT /api/v1/employers/{employer_id}` | PUT | Update employer | `EmployerResponseSchema` | **Employees only** |
| `DELETE /api/v1/employers/{employer_id}` | DELETE | Archive employer (soft delete) | `{message: string}` | **Employees only** |

### Employer Address Endpoints

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `GET /api/v1/employers/{employer_id}/addresses` | GET | Get all addresses for employer | `List[AddressResponseSchema]` |
| `POST /api/v1/employers/{employer_id}/addresses` | POST | Add address to existing employer | `AddressResponseSchema` |

### Address Endpoints (Standalone)

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `GET /api/v1/addresses/{address_id}` | GET | Get single address | `AddressResponseSchema` |
| `PUT /api/v1/addresses/{address_id}` | PUT | Update address | `AddressResponseSchema` |
| `DELETE /api/v1/addresses/{address_id}` | DELETE | Archive address | `{detail: string}` |

---

## 1. Backoffice Employer Management Page

### Purpose
Display all registered employers and their addresses. Allow admins to add new employers and addresses to expand the catalog available to clients.

### Access Control
- ✅ **Employee Admin**: Full access (GET, POST, PUT, DELETE)
- ✅ **Employee Super Admin**: Full access (GET, POST, PUT, DELETE)
- ✅ **Employee Management**: Full access (GET, POST, PUT, DELETE)
- ✅ **Employee Operator**: Full access (GET, POST, PUT, DELETE)
- ✅ **Customer**: GET all, POST new employers, POST addresses to employers
- ❌ **Customer**: Cannot PUT/DELETE employers or addresses (403 Forbidden)

### Page Structure

```
┌─────────────────────────────────────────────────────────┐
│ Employers Management                                    │
├─────────────────────────────────────────────────────────┤
│ [Search: ___________] [Create New Employer] [Refresh]   │
├─────────────────────────────────────────────────────────┤
│ Employer Name    | Primary Address    | Actions         │
├─────────────────────────────────────────────────────────┤
│ Acme Corp        | 123 Main St, BA    | [Edit] [View]   │
│ Tech Solutions   | 456 Tech Ave, BA   | [Edit] [View]    │
│ Global Inc       | 789 Global St, BA  | [Edit] [View]   │
└─────────────────────────────────────────────────────────┘
```

### Implementation Steps

#### Step 1: Fetch All Employers with Enriched Address Data

```typescript
// API Call - Use enriched endpoint to get address data in single query
GET /api/v1/employers/enriched/?include_archived=false

// Response
[
  {
    "employer_id": "uuid",
    "name": "Acme Corporation",
    "address_id": "uuid",  // Primary address (first created)
    "address_country": "Argentina",
    "address_province": "Buenos Aires",
    "address_city": "Buenos Aires",
    "address_postal_code": "1000",
    "address_street_type": "Street",
    "address_street_name": "Main Street",
    "address_building_number": "123",
    "address_floor": null,
    "address_apartment_unit": null,
    "is_archived": false,
    "status": "Active",
    "created_date": "2024-01-15T10:30:00Z",
    "modified_date": "2024-01-20T14:45:00Z"
  },
  // ... more employers
]
```

**Note**: The enriched endpoint includes all address fields prefixed with `address_`, eliminating the need for separate address API calls.

#### Step 3: Display Employers Table

```typescript
interface EmployerTableRow {
  employer_id: string;
  name: string;
  primaryAddress: {
    street_name: string;
    building_number: string;
    city: string;
    province: string;
    country: string;
    postal_code: string;
  };
  addressCount: number;  // Total addresses for this employer (fetch separately via GET /api/v1/employers/{employer_id}/addresses)
  status: "Active" | "Archived";
  created_date: string;
}

// Table Actions
- [Edit] → Navigate to Edit Page
- [View] → Expand row to show all addresses
- [Archive] → Soft delete employer
```

#### Step 4: Search Functionality

```typescript
// Search employers by name
GET /api/v1/employers/search?search_term=acme&limit=50

// Response: Filtered list of employers matching search term
```

#### Step 5: Add New Employer Button

- Clicking "Create New Employer" navigates to **Create Page** (see Section 3)

---

## 2. Edit Employer Page

### Purpose
Edit an existing employer record and manage its addresses.

### Access Control
- ✅ **Employee Admin**: Full access (GET, POST, PUT, DELETE)
- ✅ **Employee Super Admin**: Full access (GET, POST, PUT, DELETE)
- ✅ **Employee Management**: Full access (GET, POST, PUT, DELETE)
- ✅ **Employee Operator**: Full access (GET, POST, PUT, DELETE)
- ✅ **Customer**: GET all, POST new employers, POST addresses to employers
- ❌ **Customer**: Cannot PUT/DELETE employers or addresses (403 Forbidden)

### Page Structure

```
┌─────────────────────────────────────────────────────────┐
│ Edit Employer: Acme Corporation                         │
├─────────────────────────────────────────────────────────┤
│ Employer Information                                    │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Name: [Acme Corporation________________]           │ │
│ │ Status: [Active ▼]                                  │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ Addresses (2)                                            │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Primary Address (Address ID: abc-123)                │ │
│ │ Country: [Argentina ▼]                              │ │
│ │ Province: [Buenos Aires ▼]                          │ │
│ │ City: [Buenos Aires ▼]                              │ │
│ │ Postal Code: [1000_____]                            │ │
│ │ Street Type: [Street ▼]                             │ │
│ │ Street Name: [Main Street________]                  │ │
│ │ Building Number: [123_____]                         │ │
│ │ Floor: [___] (optional)                              │ │
│ │ Apartment Unit: [___] (optional)                    │ │
│ │ [Update Address] [Delete Address]                   │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Secondary Address (Address ID: def-456)             │ │
│ │ [Same fields as above]                              │ │
│ │ [Update Address] [Delete Address]                   │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ [Add New Address] [Save Changes] [Cancel]               │
└─────────────────────────────────────────────────────────┘
```

### Implementation Steps

#### Step 1: Load Employer Data

```typescript
// Fetch employer
GET /api/v1/employers/{employer_id}

// Fetch all addresses for this employer
GET /api/v1/employers/{employer_id}/addresses

// Response: Array of addresses
[
  {
    "address_id": "uuid",
    "employer_id": "uuid",
    "country": "Argentina",
    "province": "Buenos Aires",
    "city": "Buenos Aires",
    "postal_code": "1000",
    "street_type": "Street",
    "street_name": "Main Street",
    "building_number": "123",
    "floor": null,
    "apartment_unit": null,
    // ... other fields
  },
  // ... more addresses
]
```

#### Step 2: Update Employer Name

```typescript
// Update employer
PUT /api/v1/employers/{employer_id}

// Request Body
{
  "name": "Updated Company Name"
}

// Response: Updated employer
{
  "employer_id": "uuid",
  "name": "Updated Company Name",
  "address_id": "uuid",
  // ... other fields
}
```

#### Step 3: Update Individual Address

```typescript
// Update address
PUT /api/v1/addresses/{address_id}

// Request Body
{
  "country": "Argentina",
  "province": "Cordoba",
  "city": "Cordoba",
  "postal_code": "5000",
  "street_type": "Avenue",
  "street_name": "New Avenue",
  "building_number": "456",
  "floor": "2",
  "apartment_unit": "A"
}

// Response: Updated address
```

#### Step 4: Add New Address to Employer

```typescript
// Add address to existing employer
POST /api/v1/employers/{employer_id}/addresses

// Request Body
{
  "institution_id": "uuid",  // Required
  "user_id": "uuid",  // Required (can use current admin user_id)
  "address_type": ["Customer Employer"],  // Will be auto-added if missing
  "country": "Argentina",
  "province": "Mendoza",
  "city": "Mendoza",
  "postal_code": "5500",
  "street_type": "Street",
  "street_name": "Mendoza Street",
  "building_number": "789"
}

// Response: Created address with employer_id set
{
  "address_id": "uuid",
  "employer_id": "uuid",  // Automatically linked
  // ... other fields
}
```

#### Step 5: Delete Address

```typescript
// Archive address (soft delete)
DELETE /api/v1/addresses/{address_id}

// Response
{
  "detail": "Address deleted successfully"
}
```

---

## 3. Create Employer Page

### Purpose
Create a new employer with its initial address in a single atomic operation.

### Access Control
- ✅ **Employee Admin**: Full access (GET, POST, PUT, DELETE)
- ✅ **Employee Super Admin**: Full access (GET, POST, PUT, DELETE)
- ✅ **Employee Management**: Full access (GET, POST, PUT, DELETE)
- ✅ **Employee Operator**: Full access (GET, POST, PUT, DELETE)
- ✅ **Customer**: GET all, POST new employers, POST addresses to employers
- ❌ **Customer**: Cannot PUT/DELETE employers or addresses (403 Forbidden)

### Recommended Approach: Single Form with Two Sections

**Key Insight**: The API supports creating employer and address atomically via `POST /api/v1/employers/`. This is the recommended approach for a single-page form.

### Page Structure

```
┌─────────────────────────────────────────────────────────┐
│ Create New Employer                                     │
├─────────────────────────────────────────────────────────┤
│ Employer Information                                    │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Company Name: [________________________] *         │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ Initial Address Information                             │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Institution: [Select Institution ▼] *              │ │
│ │ Country: [Argentina ▼] *                           │ │
│ │ Province: [Buenos Aires ▼] *                       │ │
│ │ City: [Buenos Aires ▼] *                           │ │
│ │ Postal Code: [1000_____] *                         │ │
│ │ Street Type: [Street ▼] *                          │ │
│ │ Street Name: [________________] *                  │ │
│ │ Building Number: [_____] *                         │ │
│ │ Floor: [___] (optional)                            │ │
│ │ Apartment Unit: [___] (optional)                   │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ [Create Employer] [Cancel]                              │
└─────────────────────────────────────────────────────────┘
```

### Implementation: Atomic Creation

#### Option A: Single API Call (Recommended) ✅

**Use `POST /api/v1/employers/` which creates both employer and address atomically:**

```typescript
// Single API call creates both employer and address
POST /api/v1/employers/

// Request Body
{
  "name": "New Company Inc.",
  "address": {
    "institution_id": "uuid",  // Required - get from current user's JWT or institution selector
    "user_id": "uuid",  // Required - can use current admin user_id from JWT
    "address_type": ["Customer Employer"],  // Optional - will be auto-added
    "country": "Argentina",
    "province": "Buenos Aires",
    "city": "Buenos Aires",
    "postal_code": "1000",
    "street_type": "Street",
    "street_name": "New Street",
    "building_number": "123",
    "floor": null,  // Optional
    "apartment_unit": null  // Optional
  }
}

// Response: Created employer with address_id
{
  "employer_id": "uuid",
  "name": "New Company Inc.",
  "address_id": "uuid",  // Primary address created
  "is_archived": false,
  "status": "Active",
  "created_date": "2024-12-06T15:30:00Z",
  "modified_date": "2024-12-06T15:30:00Z"
}
```

**Benefits**:
- ✅ Atomic operation (all or nothing)
- ✅ Single API call (simpler error handling)
- ✅ Address automatically linked to employer (`employer_id` set)
- ✅ Address type automatically set to "Customer Employer"

**TypeScript Example**:

```typescript
interface CreateEmployerFormData {
  // Employer fields
  name: string;
  
  // Address fields
  institution_id: string;
  user_id: string;  // From current user JWT
  country: string;
  province: string;
  city: string;
  postal_code: string;
  street_type: string;
  street_name: string;
  building_number: string;
  floor?: string | null;
  apartment_unit?: string | null;
}

async function createEmployerWithAddress(
  formData: CreateEmployerFormData,
  authToken: string
): Promise<EmployerResponse> {
  const response = await fetch('/api/v1/employers/', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${authToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      name: formData.name,
      address: {
        institution_id: formData.institution_id,
        user_id: formData.user_id,
        address_type: ["Customer Employer"],  // Auto-added by backend if missing
        country: formData.country,
        province: formData.province,
        city: formData.city,
        postal_code: formData.postal_code,
        street_type: formData.street_type,
        street_name: formData.street_name,
        building_number: formData.building_number,
        floor: formData.floor || null,
        apartment_unit: formData.apartment_unit || null
      }
    })
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create employer');
  }
  
  return response.json();
}
```

#### Option B: Two-Step Creation (Not Recommended)

**Alternative approach** (if you need more control, but not recommended):

```typescript
// Step 1: Create employer (without address)
POST /api/v1/employers/  // This won't work - address is required!

// Step 2: Create address and link to employer
POST /api/v1/employers/{employer_id}/addresses
```

**Why Not Recommended**:
- ❌ `POST /api/v1/employers/` requires address in the request body
- ❌ Two API calls = potential inconsistency
- ❌ More complex error handling
- ❌ Not atomic

---

## Form Field Requirements

### Employer Fields

| Field | Type | Required | Max Length | Notes |
|-------|------|----------|------------|-------|
| `name` | string | ✅ Yes | 100 | Company name |

### Address Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `institution_id` | UUID | ✅ Yes | Get from current user's JWT or institution selector |
| `user_id` | UUID | ✅ Yes | Can use current admin user_id from JWT |
| `address_type` | string[] | ⚠️ Optional | Will be auto-set to `["Customer Employer"]` if missing |
| `country` | string | ✅ Yes | Dropdown or text input |
| `province` | string | ✅ Yes | Dropdown or text input |
| `city` | string | ✅ Yes | Dropdown or text input |
| `postal_code` | string | ✅ Yes | Text input |
| `street_type` | string | ✅ Yes | Dropdown (Street, Avenue, Boulevard, etc.) |
| `street_name` | string | ✅ Yes | Text input |
| `building_number` | string | ✅ Yes | Text input |
| `floor` | string | ❌ No | Text input (optional) |
| `apartment_unit` | string | ❌ No | Text input (optional) |

**Note**: `employer_id` is **NOT** included in the create form - it's set automatically by the backend when creating via `POST /api/v1/employers/`.

---

## Error Handling

### Common Errors

```typescript
// 422 Unprocessable Entity - Validation errors
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}

// 404 Not Found - Employer not found
{
  "detail": "Employer with ID {employer_id} not found"
}

// 500 Internal Server Error - Creation/update failed
{
  "detail": "Failed to create employer with address"
}
```

### Error Handling Pattern

```typescript
try {
  const employer = await createEmployerWithAddress(formData, token);
  // Success - navigate to employer list or edit page
  navigate(`/employers/${employer.employer_id}`);
} catch (error) {
  if (error.response?.status === 422) {
    // Validation errors - display field-level errors
    const errors = error.response.data.detail;
    setFieldErrors(parseValidationErrors(errors));
  } else if (error.response?.status === 401) {
    // Unauthorized - redirect to login
    navigate('/login');
  } else {
    // Generic error
    showErrorToast('Failed to create employer. Please try again.');
  }
}
```

---

## UI/UX Recommendations

### 1. Employer Management Page

- **Table View**: Display employers in a sortable, filterable table
- **Search**: Real-time search as user types (debounced)
- **Pagination**: If many employers, paginate results
- **Status Indicators**: Visual indicators for Active/Archived status
- **Address Count Badge**: Show number of addresses per employer
- **Actions Column**: Edit, View, Archive buttons

### 2. Edit Page

- **Vertical Form Layout**: Long form with sections
- **Address Cards**: Display each address as a card with edit/delete actions
- **Add Address Button**: Opens inline form or modal to add new address
- **Save Changes**: Single save button that updates employer name (addresses updated individually)
- **Cancel**: Navigate back without saving

### 3. Create Page

- **Single Form**: All fields on one page (employer + address)
- **Clear Sections**: Visual separation between employer and address fields
- **Required Field Indicators**: Mark required fields with asterisk (*)
- **Validation**: Client-side validation before submission
- **Loading State**: Show loading spinner during API call
- **Success Feedback**: Toast notification + navigate to edit page

### 4. Address Management

- **Expandable Rows**: Click "View" to expand and see all addresses
- **Address Cards**: In edit page, display addresses as cards
- **Primary Address Indicator**: Mark the first address (address_id matches employer.address_id) as "Primary"
- **Add Address Flow**: 
  - Option A: Inline form in edit page
  - Option B: Modal dialog
  - Option C: Separate "Add Address" page

---

## Data Flow Diagrams

### Create Employer Flow

```
User fills form
    ↓
Click "Create Employer"
    ↓
Validate form (client-side)
    ↓
POST /api/v1/employers/ (with embedded address)
    ↓
Backend creates employer + address atomically
    ↓
Response: Employer with address_id
    ↓
Navigate to Edit Page or Employer List
```

### Edit Employer Flow

```
User clicks "Edit" on employer row
    ↓
Navigate to Edit Page
    ↓
GET /api/v1/employers/{employer_id}
GET /api/v1/employers/{employer_id}/addresses
    ↓
Display form with current data
    ↓
User modifies fields
    ↓
Click "Save Changes"
    ↓
PUT /api/v1/employers/{employer_id} (for name)
PUT /api/v1/addresses/{address_id} (for each address)
    ↓
Show success message
```

### Add Address to Employer Flow

```
User clicks "Add New Address" in Edit Page
    ↓
Display address form (inline or modal)
    ↓
User fills address fields
    ↓
Click "Add Address"
    ↓
POST /api/v1/employers/{employer_id}/addresses
    ↓
Address created with employer_id linked
    ↓
Refresh address list
```

---

## TypeScript Interfaces

```typescript
// Employer Response (basic)
interface EmployerResponse {
  employer_id: string;
  name: string;
  address_id: string;  // Primary address
  is_archived: boolean;
  status: "Active" | "Archived";
  created_date: string;
  modified_date: string;
}

// Employer Enriched Response (includes address data)
interface EmployerEnrichedResponse {
  employer_id: string;
  name: string;
  address_id: string;  // Primary address
  address_country: string | null;
  address_province: string | null;
  address_city: string | null;
  address_postal_code: string | null;
  address_street_type: string | null;
  address_street_name: string | null;
  address_building_number: string | null;
  address_floor: string | null;
  address_apartment_unit: string | null;
  is_archived: boolean;
  status: "Active" | "Archived";
  created_date: string;
  modified_date: string;
}

// Address Response
interface AddressResponse {
  address_id: string;
  institution_id: string;
  user_id: string;
  employer_id: string | null;
  address_type: string[];  // ["Customer Employer"]
  country: string;
  province: string;
  city: string;
  postal_code: string;
  street_type: string;
  street_name: string;
  building_number: string;
  floor: string | null;
  apartment_unit: string | null;
  is_archived: boolean;
  status: "Active" | "Archived";
  created_date: string;
  modified_date: string;
}

// Create Employer Request
interface CreateEmployerRequest {
  name: string;
  address: {
    institution_id: string;
    user_id: string;
    address_type?: string[];  // Optional - auto-set to ["Customer Employer"]
    country: string;
    province: string;
    city: string;
    postal_code: string;
    street_type: string;
    street_name: string;
    building_number: string;
    floor?: string | null;
    apartment_unit?: string | null;
  };
}

// Update Employer Request
interface UpdateEmployerRequest {
  name?: string;
  address_id?: string;  // Change primary address
}

// Create Address Request (for adding to existing employer)
interface CreateAddressRequest {
  institution_id: string;
  user_id: string;
  address_type?: string[];  // Optional - auto-set to ["Customer Employer"]
  country: string;
  province: string;
  city: string;
  postal_code: string;
  street_type: string;
  street_name: string;
  building_number: string;
  floor?: string | null;
  apartment_unit?: string | null;
  // employer_id is set automatically by backend
}
```

---

## Best Practices

### 1. Atomic Operations

✅ **DO**: Use `POST /api/v1/employers/` for creating employer with address (atomic)
❌ **DON'T**: Create employer and address separately (risk of inconsistency)

### 2. Error Handling

✅ **DO**: Handle 422 validation errors and display field-level errors
✅ **DO**: Show user-friendly error messages
❌ **DON'T**: Show raw API error responses to users

### 3. Loading States

✅ **DO**: Show loading spinners during API calls
✅ **DO**: Disable form submission while loading
❌ **DON'T**: Allow multiple simultaneous submissions

### 4. Data Refresh

✅ **DO**: Refresh employer list after create/update
✅ **DO**: Refresh address list after adding address
❌ **DON'T**: Assume data is up-to-date without refresh

### 5. User Experience

✅ **DO**: Provide clear success/error feedback
✅ **DO**: Navigate to edit page after successful creation
✅ **DO**: Allow cancel/back navigation
❌ **DON'T**: Lose user data on navigation errors

---

## Testing Checklist

### Create Employer Page

- [ ] Form validation (required fields)
- [ ] Successful creation with all fields
- [ ] Successful creation with optional fields (floor, apartment_unit)
- [ ] Error handling (422, 401, 500)
- [ ] Loading state during API call
- [ ] Success navigation

### Edit Employer Page

- [ ] Load employer data correctly
- [ ] Load all addresses for employer
- [ ] Update employer name
- [ ] Update individual address
- [ ] Add new address to employer
- [ ] Delete address
- [ ] Error handling
- [ ] Cancel navigation

### Employer Management Page

- [ ] Display all employers
- [ ] Search functionality
- [ ] Filter by status (Active/Archived)
- [ ] Pagination (if many employers)
- [ ] Navigate to edit page
- [ ] Refresh data

---

## Related Documentation

- `API_PERMISSIONS_BY_ROLE.md` - Role-based access control
- `SCOPING_BEHAVIOR_FOR_UI.md` - Scoping behavior
- `USER_SELF_UPDATE_PATTERN.md` - User self-update patterns (different use case)

---

**Last Updated**: December 2024

 