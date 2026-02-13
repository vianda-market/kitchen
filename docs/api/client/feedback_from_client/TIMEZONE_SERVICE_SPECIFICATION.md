# **TIMEZONE SERVICE SPECIFICATION**

**Document Version**: 1.0  
**Date**: February 10, 2026  
**For**: Backend Team  
**From**: Frontend Team  

---

## **Executive Summary**

The frontend needs a backend service to intelligently handle timezone assignment for addresses across multiple countries. The service must support both single-timezone countries (current operations) and multi-timezone countries (future expansion like USA, Brazil, Canada).

**Key Principle**: Minimize user friction - users should only provide country and province/state; the backend deduces the timezone.

---

## **Problem Statement**

### **Current State**
- Addresses have optional `timezone` field
- Frontend has no reliable way to populate timezone automatically
- Users must manually enter timezone (error-prone, poor UX)

### **Business Requirements**
1. **Current Markets** (Argentina, Peru, Chile, Colombia, etc.): Single timezone per country
2. **Future Markets** (USA, Brazil, Canada, Australia): Multiple timezones per country
3. **UX Goal**: User selects country + province/state → Backend deduces timezone
4. **Data Integrity**: Ensure all addresses have valid, accurate timezones

---

## **Proposed Solution Architecture**

### **Backend Responsibilities**
1. ✅ Install and maintain timezone data library
2. ✅ Provide country → timezone(s) mapping API
3. ✅ Provide province/state → timezone deduction API
4. ✅ Auto-populate timezone when creating/updating addresses
5. ✅ Validate timezone values against IANA database

### **Frontend Responsibilities**
1. ✅ Display country dropdown (from Markets API)
2. ✅ Display province/state input field
3. ✅ Call backend API to get deduced timezone
4. ✅ Show deduced timezone to user (read-only or hidden)

---

## **Recommended Library**

**Name**: `countries-and-timezones`  
**PyPI Package**: `pytz` + `pycountry` (Python equivalent)  
**NPM Package**: `countries-and-timezones` (if using Node.js)

### **Python Implementation**
```bash
pip install pytz pycountry
```

**Alternative**: Use a timezone database library that provides:
- Country code → timezone(s) mapping
- IANA timezone validation
- Province/state → timezone deduction

### **Data Source**
- **IANA Time Zone Database**: Official, globally maintained
- **Updates**: Library handles DST changes automatically

---

## **API Specification**

### **1. Get Country Timezone Information**

**Purpose**: Return all timezones for a given country

```http
GET /api/v1/countries/{country_code}/timezones
```

**Path Parameters**:
- `country_code` (string, required): ISO 3166-1 alpha-2 code (e.g., "AR", "US")

**Response** (200 OK):
```json
{
  "country_code": "AR",
  "country_name": "Argentina",
  "timezones": [
    {
      "iana_name": "America/Argentina/Buenos_Aires",
      "display_name": "Argentina Time (ART)",
      "utc_offset": "-03:00",
      "is_default": true
    }
  ],
  "has_multiple_timezones": false
}
```

**Response for Multi-TZ Country** (USA):
```json
{
  "country_code": "US",
  "country_name": "United States",
  "timezones": [
    {
      "iana_name": "America/New_York",
      "display_name": "Eastern Time (ET)",
      "utc_offset": "-05:00",
      "is_default": true
    },
    {
      "iana_name": "America/Chicago",
      "display_name": "Central Time (CT)",
      "utc_offset": "-06:00",
      "is_default": false
    },
    {
      "iana_name": "America/Denver",
      "display_name": "Mountain Time (MT)",
      "utc_offset": "-07:00",
      "is_default": false
    },
    {
      "iana_name": "America/Los_Angeles",
      "display_name": "Pacific Time (PT)",
      "utc_offset": "-08:00",
      "is_default": false
    },
    {
      "iana_name": "America/Anchorage",
      "display_name": "Alaska Time (AKT)",
      "utc_offset": "-09:00",
      "is_default": false
    },
    {
      "iana_name": "Pacific/Honolulu",
      "display_name": "Hawaii-Aleutian Time (HAT)",
      "utc_offset": "-10:00",
      "is_default": false
    }
  ],
  "has_multiple_timezones": true
}
```

---

### **2. Get Country Subdivisions (States/Provinces)**

**Purpose**: Return administrative subdivisions with timezone information

```http
GET /api/v1/countries/{country_code}/subdivisions
```

**Path Parameters**:
- `country_code` (string, required): ISO 3166-1 alpha-2 code

**Query Parameters**:
- `include_timezones` (boolean, optional, default: true): Include timezone data

**Response** (200 OK):
```json
{
  "country_code": "US",
  "country_name": "United States",
  "subdivisions": [
    {
      "code": "NY",
      "name": "New York",
      "timezone": "America/New_York",
      "timezone_display": "Eastern Time (ET)"
    },
    {
      "code": "CA",
      "name": "California",
      "timezone": "America/Los_Angeles",
      "timezone_display": "Pacific Time (PT)"
    },
    {
      "code": "TX",
      "name": "Texas",
      "timezone": "America/Chicago",
      "timezone_display": "Central Time (CT)"
    },
    {
      "code": "FL",
      "name": "Florida",
      "timezone": "America/New_York",
      "timezone_display": "Eastern Time (ET)"
    }
    // ... all 50 states
  ]
}
```

**For Single-TZ Countries** (Argentina):
```json
{
  "country_code": "AR",
  "country_name": "Argentina",
  "subdivisions": [
    {
      "code": "B",
      "name": "Buenos Aires",
      "timezone": "America/Argentina/Buenos_Aires",
      "timezone_display": "Argentina Time (ART)"
    },
    {
      "code": "C",
      "name": "Córdoba",
      "timezone": "America/Argentina/Buenos_Aires",
      "timezone_display": "Argentina Time (ART)"
    }
    // All provinces have same timezone
  ]
}
```

---

### **3. Deduce Timezone from Location**

**Purpose**: Intelligently deduce timezone based on country and optional province/state

```http
POST /api/v1/locations/deduce-timezone
```

**Request Body**:
```json
{
  "country_code": "US",
  "subdivision_name": "California"  // Optional: state, province, or region
}
```

**Response** (200 OK):
```json
{
  "timezone": "America/Los_Angeles",
  "timezone_display": "Pacific Time (PT)",
  "confidence": "high",
  "deduction_method": "subdivision_mapping",
  "message": "Timezone deduced from subdivision: California"
}
```

**Response when no subdivision provided (single-TZ country)**:
```json
{
  "timezone": "America/Argentina/Buenos_Aires",
  "timezone_display": "Argentina Time (ART)",
  "confidence": "high",
  "deduction_method": "country_single_timezone",
  "message": "Country has single timezone"
}
```

**Response when no subdivision provided (multi-TZ country)**:
```json
{
  "timezone": "America/New_York",
  "timezone_display": "Eastern Time (ET)",
  "confidence": "low",
  "deduction_method": "country_default",
  "message": "Multiple timezones exist; returning default. Provide subdivision for accurate deduction.",
  "requires_user_selection": true
}
```

**Response when subdivision not found**:
```json
{
  "timezone": null,
  "confidence": "none",
  "deduction_method": "failed",
  "message": "Could not deduce timezone. Subdivision 'InvalidProvince' not found for country US.",
  "requires_user_selection": true,
  "available_timezones": [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu"
  ]
}
```

---

### **4. Enhanced Address Endpoints**

#### **Create Address (Modified)**

```http
POST /api/v1/addresses/
```

**Request Body** (timezone now OPTIONAL):
```json
{
  "institution_id": "uuid",
  "name": "Main Office",
  "country": "US",
  "province": "California",
  "city": "San Francisco",
  "address_line_1": "123 Market St",
  "postal_code": "94103"
  // timezone is OPTIONAL - backend will deduce
}
```

**Backend Logic**:
```python
def create_address(address_data: AddressCreateRequest):
    # If timezone not provided, deduce it
    if not address_data.timezone:
        deduced = deduce_timezone(
            country_code=address_data.country,
            subdivision=address_data.province
        )
        address_data.timezone = deduced.timezone
    
    # Validate timezone
    if not is_valid_timezone(address_data.timezone):
        raise ValidationError("Invalid timezone")
    
    # Create address
    return create_address_record(address_data)
```

**Response** (201 Created):
```json
{
  "address_id": "uuid",
  "institution_id": "uuid",
  "name": "Main Office",
  "country": "US",
  "province": "California",
  "city": "San Francisco",
  "address_line_1": "123 Market St",
  "postal_code": "94103",
  "timezone": "America/Los_Angeles",  // Auto-deduced
  "timezone_display": "Pacific Time (PT)",
  "is_active": true
}
```

---

#### **Update Address (Modified)**

```http
PUT /api/v1/addresses/{address_id}
```

**Backend Logic**:
```python
def update_address(address_id: UUID, update_data: AddressUpdateRequest):
    existing = get_address(address_id)
    
    # If country or province changed, re-deduce timezone
    if (update_data.country != existing.country or 
        update_data.province != existing.province):
        
        if not update_data.timezone:  # User didn't explicitly set timezone
            deduced = deduce_timezone(
                country_code=update_data.country,
                subdivision=update_data.province
            )
            update_data.timezone = deduced.timezone
    
    return update_address_record(address_id, update_data)
```

---

### **5. Validation Endpoint**

**Purpose**: Validate if a timezone is valid for a given country/subdivision

```http
POST /api/v1/locations/validate-timezone
```

**Request Body**:
```json
{
  "country_code": "US",
  "subdivision_name": "California",
  "timezone": "America/Los_Angeles"
}
```

**Response** (200 OK):
```json
{
  "is_valid": true,
  "message": "Timezone is valid for this location"
}
```

**Response** (Invalid):
```json
{
  "is_valid": false,
  "message": "Timezone 'America/New_York' is not valid for California, US. Expected: 'America/Los_Angeles'",
  "expected_timezone": "America/Los_Angeles"
}
```

---

## **Database Schema Updates**

### **Option 1: Add Subdivisions Table (Recommended)**

```sql
CREATE TABLE country_subdivisions (
    subdivision_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    country_code VARCHAR(2) NOT NULL,  -- ISO 3166-1 alpha-2
    subdivision_code VARCHAR(10),       -- ISO 3166-2 code
    subdivision_name VARCHAR(255) NOT NULL,
    timezone VARCHAR(100) NOT NULL,     -- IANA timezone
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(country_code, subdivision_code),
    FOREIGN KEY (country_code) REFERENCES markets(country_code)
);

-- Index for fast lookups
CREATE INDEX idx_subdivisions_country ON country_subdivisions(country_code);
CREATE INDEX idx_subdivisions_name ON country_subdivisions(subdivision_name);
```

**Seed Data Example**:
```sql
-- Argentina (single timezone)
INSERT INTO country_subdivisions (country_code, subdivision_code, subdivision_name, timezone) VALUES
('AR', 'B', 'Buenos Aires', 'America/Argentina/Buenos_Aires'),
('AR', 'C', 'Córdoba', 'America/Argentina/Buenos_Aires'),
('AR', 'X', 'Mendoza', 'America/Argentina/Buenos_Aires');

-- USA (multiple timezones)
INSERT INTO country_subdivisions (country_code, subdivision_code, subdivision_name, timezone) VALUES
('US', 'NY', 'New York', 'America/New_York'),
('US', 'CA', 'California', 'America/Los_Angeles'),
('US', 'TX', 'Texas', 'America/Chicago'),
('US', 'FL', 'Florida', 'America/New_York'),
('US', 'AK', 'Alaska', 'America/Anchorage'),
('US', 'HI', 'Hawaii', 'Pacific/Honolulu');
```

### **Option 2: Use Library for Deduction (No DB)**

If you install `countries-and-timezones` or similar library:
- No database changes needed
- Library provides country→timezone mapping
- Manual province→timezone mapping in code
- Trade-off: Less flexible, harder to override

---

## **Implementation Requirements**

### **Phase 1: Core Infrastructure (Week 1)**
- [ ] Install timezone library (`pytz`, `pycountry`)
- [ ] Create timezone utility functions
- [ ] Implement `/countries/{code}/timezones` endpoint
- [ ] Implement `/locations/deduce-timezone` endpoint
- [ ] Add timezone validation logic
- [ ] Unit tests for deduction logic

### **Phase 2: Subdivisions Support (Week 2)**
- [ ] Create `country_subdivisions` table
- [ ] Seed data for current markets (AR, PE, CL, CO)
- [ ] Implement `/countries/{code}/subdivisions` endpoint
- [ ] Update Address create/update to auto-deduce timezone
- [ ] Integration tests for address creation

### **Phase 3: US Market Preparation (Future)**
- [ ] Seed US subdivisions data (50 states)
- [ ] Test timezone deduction for all US states
- [ ] Update frontend integration
- [ ] Document edge cases (e.g., Arizona no DST)

---

## **Business Logic Rules**

### **Timezone Deduction Priority**

```
1. If user explicitly provides timezone → Use it (validate only)
2. Else if country has 1 timezone → Auto-assign country's timezone
3. Else if subdivision provided → Lookup subdivision→timezone mapping
4. Else if subdivision not found → Return country default + warning
5. Else → Require user to select from available timezones
```

### **Validation Rules**

- ✅ Timezone must be valid IANA timezone string
- ✅ Timezone must be one of the country's valid timezones
- ✅ If subdivision provided, timezone should match subdivision's timezone
- ✅ Warn (don't block) if timezone doesn't match expected for subdivision

---

## **Edge Cases to Handle**

### **1. Subdivision Name Variations**
**Problem**: User enters "New York" vs "NY" vs "New York State"

**Solution**:
```python
# Fuzzy matching for subdivision names
def normalize_subdivision_name(name: str) -> str:
    # Remove common suffixes
    name = name.replace(" State", "").replace(" Province", "")
    # Titlecase
    return name.strip().title()

# Support both codes and names
def find_subdivision(country_code: str, query: str):
    query_normalized = normalize_subdivision_name(query)
    
    # Try exact match on code
    result = db.query(Subdivision).filter(
        Subdivision.country_code == country_code,
        Subdivision.subdivision_code == query.upper()
    ).first()
    
    if result:
        return result
    
    # Try exact match on name
    result = db.query(Subdivision).filter(
        Subdivision.country_code == country_code,
        Subdivision.subdivision_name == query_normalized
    ).first()
    
    return result
```

### **2. Multi-Timezone Subdivisions**
**Problem**: Some US states span multiple timezones (e.g., Kentucky, Tennessee)

**Solution**:
```sql
-- Allow multiple timezones per subdivision
CREATE TABLE subdivision_timezones (
    subdivision_id UUID REFERENCES country_subdivisions(subdivision_id),
    timezone VARCHAR(100),
    is_default BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (subdivision_id, timezone)
);
```

Return primary timezone by default, but expose others:
```json
{
  "subdivision": "Kentucky",
  "primary_timezone": "America/New_York",
  "secondary_timezones": ["America/Chicago"],
  "message": "This state spans multiple timezones. Using primary timezone."
}
```

### **3. No DST Zones**
**Problem**: Arizona (except Navajo Nation) doesn't observe DST

**Solution**: Use correct IANA timezone
- ✅ `America/Phoenix` (no DST)
- ❌ Not `America/Denver` (has DST)

### **4. Territories and Dependencies**
**Problem**: US territories (Puerto Rico, Guam) have different timezones

**Solution**: Treat as subdivisions
```sql
INSERT INTO country_subdivisions (country_code, subdivision_code, subdivision_name, timezone) VALUES
('US', 'PR', 'Puerto Rico', 'America/Puerto_Rico'),
('US', 'GU', 'Guam', 'Pacific/Guam');
```

---

## **API Error Responses**

### **Invalid Country Code**
```json
{
  "detail": "Country code 'XY' not found or not supported"
}
```
**HTTP**: 404 Not Found

### **Invalid Timezone**
```json
{
  "detail": "Timezone 'America/Invalid' is not a valid IANA timezone"
}
```
**HTTP**: 400 Bad Request

### **Timezone Mismatch Warning**
```json
{
  "warning": "Timezone 'America/New_York' does not match expected timezone for California ('America/Los_Angeles'). Using provided timezone.",
  "expected_timezone": "America/Los_Angeles",
  "provided_timezone": "America/New_York"
}
```
**HTTP**: 201 Created (with warning in response body)

---

## **Frontend Integration Changes**

### **Before (Current)**
```typescript
// User manually enters timezone (error-prone)
<TextField name="timezone" label="Timezone" />
```

### **After (Proposed)**
```typescript
// 1. User selects country
<SelectField name="country" options={markets} />

// 2. User enters province (text or dropdown)
<TextField name="province" label="Province/State" />

// 3. Backend auto-deduces timezone
// Display deduced timezone (read-only)
<TextField 
  name="timezone" 
  label="Timezone" 
  value={deducedTimezone}
  disabled 
  helperText="Auto-detected from location"
/>
```

### **Frontend API Call**
```typescript
// After user enters country + province
const response = await apiClient.post('/api/v1/locations/deduce-timezone', {
  country_code: formData.country,
  subdivision_name: formData.province
});

setFormData(prev => ({
  ...prev,
  timezone: response.data.timezone
}));

// Show confidence to user
if (response.data.confidence === 'low') {
  showWarning('Please verify timezone is correct');
}
```

---

## **Testing Requirements**

### **Unit Tests**
- [ ] Test timezone deduction for single-TZ countries
- [ ] Test timezone deduction for multi-TZ countries with subdivision
- [ ] Test timezone deduction for multi-TZ countries without subdivision
- [ ] Test invalid country codes
- [ ] Test invalid subdivision names
- [ ] Test timezone validation
- [ ] Test fuzzy matching for subdivision names

### **Integration Tests**
- [ ] Test address creation with auto-deduced timezone
- [ ] Test address creation with explicit timezone
- [ ] Test address update changing country (should update timezone)
- [ ] Test address update changing province (should update timezone)
- [ ] Test all markets currently in production

### **Data Validation**
- [ ] Verify all subdivisions in DB have valid IANA timezones
- [ ] Verify all markets have correct default timezones
- [ ] Test DST transitions (spring forward, fall back)

---

## **Documentation Requirements**

- [ ] API documentation (Swagger/OpenAPI)
- [ ] Database schema documentation
- [ ] Timezone deduction logic flowchart
- [ ] List of supported countries and subdivisions
- [ ] Edge case handling guide
- [ ] Migration guide for existing addresses

---

## **Migration Strategy for Existing Data**

### **Step 1: Backfill Missing Timezones**
```sql
-- Find addresses without timezone
SELECT address_id, country, province 
FROM addresses 
WHERE timezone IS NULL;

-- Deduce and update
UPDATE addresses 
SET timezone = (
    SELECT timezone 
    FROM country_subdivisions 
    WHERE country_code = addresses.country 
    LIMIT 1
)
WHERE timezone IS NULL;
```

### **Step 2: Validate Existing Timezones**
```python
# Script to validate and correct existing timezones
addresses = db.query(Address).all()
for address in addresses:
    deduced = deduce_timezone(address.country, address.province)
    if address.timezone != deduced.timezone:
        print(f"Mismatch: {address.address_id} has {address.timezone}, expected {deduced.timezone}")
        # Option: Auto-correct or flag for review
```

---

## **Performance Considerations**

### **Caching Strategy**
```python
from functools import lru_cache

@lru_cache(maxsize=500)
def get_country_timezones(country_code: str):
    # Cache country timezone lookups
    return db.query(Subdivision).filter_by(country_code=country_code).all()

@lru_cache(maxsize=2000)
def deduce_timezone_cached(country_code: str, subdivision: str):
    # Cache deduction results
    return deduce_timezone(country_code, subdivision)
```

### **Database Indexing**
```sql
-- Fast lookups by country
CREATE INDEX idx_subdivisions_country ON country_subdivisions(country_code);

-- Fast lookups by name (for fuzzy matching)
CREATE INDEX idx_subdivisions_name ON country_subdivisions(subdivision_name);

-- Composite index for exact lookups
CREATE INDEX idx_subdivisions_country_name ON country_subdivisions(country_code, subdivision_name);
```

---

## **Security Considerations**

- [ ] Validate all user inputs (country, subdivision, timezone)
- [ ] Prevent timezone injection attacks
- [ ] Rate limit timezone deduction API
- [ ] Log suspicious timezone validation failures
- [ ] Sanitize subdivision name inputs

---

## **Success Criteria**

✅ **For Single-TZ Countries**: User selects country → timezone auto-populated → 0 user input required  
✅ **For Multi-TZ Countries**: User selects country + province → timezone auto-populated → 0 user input required  
✅ **For Edge Cases**: User can manually override if deduction fails  
✅ **For Data Integrity**: 100% of addresses have valid IANA timezones  
✅ **For Performance**: Timezone deduction < 50ms (P95)  
✅ **For Maintenance**: Adding new country requires only DB seed data, no code changes  

---

## **Questions for Backend Team**

1. **Library preference**: Do you prefer `pytz` + `pycountry` or another library?
2. **Database approach**: Should we create `country_subdivisions` table or use library-only?
3. **Validation strictness**: Should we block or warn on timezone mismatches?
4. **Migration timeline**: When can existing addresses be backfilled?
5. **API versioning**: Should this be `/api/v1/` or `/api/v2/`?

---

## **Frontend Dependencies**

**Blocked on**:
- ✅ `/api/v1/countries/{code}/timezones` endpoint
- ✅ `/api/v1/locations/deduce-timezone` endpoint
- ✅ Updated `POST /api/v1/addresses/` (auto-deduce timezone)

**Optional (Nice-to-have)**:
- `/api/v1/countries/{code}/subdivisions` endpoint (enables province dropdown)
- `/api/v1/locations/validate-timezone` endpoint (enables client-side validation)

---

## **Timeline Estimate**

| Phase | Tasks | Effort | Dependencies |
|-------|-------|--------|--------------|
| **Phase 1** | Core API endpoints, deduction logic | 3-5 days | Library installation |
| **Phase 2** | Subdivisions table, seed data | 2-3 days | Phase 1 complete |
| **Phase 3** | Address auto-deduction, migration | 2-3 days | Phase 2 complete |
| **Testing** | Unit + integration tests | 2 days | All phases |
| **Documentation** | API docs, guides | 1 day | All phases |

**Total**: 10-14 days

---

## **Contact**

For questions or clarifications, contact the Frontend Team.

**Document Status**: Ready for Backend Implementation  
**Next Steps**: Backend team reviews → estimates timeline → begins Phase 1

---

**END OF SPECIFICATION**
