# E2E Plate Selection - Testing Strategy & Improvements

## Current State Analysis
- **Total Requests**: ~45+ requests
- **Test Listeners**: 49
- **Actual Test Assertions (`pm.test`)**: 37
- **Requests Without Tests**: ~12
- **Tests Passing**: 36

## Testing Gaps Identified

### Requests Missing Proper Test Assertions

Based on analysis, the following request types are missing comprehensive tests:

1. **Login Endpoints** (multiple)
   - No status code validation
   - No token format validation
   - No expiry validation

2. **Logout Endpoints** (multiple)
   - No test assertions at all
   - Should verify token is cleared

3. **Update Endpoints** (e.g., Update Customer Address, Update Supplier Product)
   - Minimal or no test coverage
   - Should verify fields were actually updated

4. **Fetch/List Endpoints** 
   - Some have no assertions
   - Should validate response structure and data types

5. **Delete/Archive Operations**
   - No validation that resources are actually archived/deleted

---

## Recommended Testing Improvements

### 1. **Universal Tests for ALL Requests**

Every request should have at minimum:

```javascript
// Status Code Validation
pm.test("Response status is successful", function () {
    pm.expect(pm.response.code).to.be.oneOf([200, 201, 204]);
});

// Response Time SLA
pm.test("Response time is acceptable (< 2000ms)", function () {
    pm.expect(pm.response.responseTime).to.be.below(2000);
});

// Content-Type Header
pm.test("Content-Type is JSON", function () {
    pm.expect(pm.response.headers.get("Content-Type")).to.include("application/json");
});
```

---

### 2. **Login Endpoints - Enhanced Testing**

```javascript
pm.test("Login successful", function () {
    pm.response.to.have.status(200);
});

pm.test("Response contains access_token", function () {
    const body = pm.response.json();
    pm.expect(body).to.have.property("access_token");
    pm.expect(body.access_token).to.be.a("string");
    pm.expect(body.access_token.length).to.be.above(20);
});

pm.test("Token is valid JWT format", function () {
    const { access_token } = pm.response.json();
    const parts = access_token.split('.');
    pm.expect(parts.length).to.equal(3); // header.payload.signature
});

pm.test("Token expiry is set", function () {
    const { access_token } = pm.response.json();
    const payload = JSON.parse(atob(access_token.split('.')[1]));
    pm.expect(payload).to.have.property("exp");
    pm.expect(payload.exp).to.be.a("number");
});

// Set token for subsequent requests
const { access_token } = pm.response.json();
pm.environment.set("authToken", access_token);
```

---

### 3. **Logout Endpoints - Add Tests**

```javascript
pm.test("Logout successful", function () {
    pm.response.to.have.status(200);
});

pm.test("Auth token removed from environment", function () {
    pm.environment.unset("authToken");
    pm.expect(pm.environment.get("authToken")).to.be.undefined;
});
```

---

### 4. **POST/Create Endpoints - Comprehensive Validation**

```javascript
pm.test("Resource created successfully", function () {
    pm.response.to.have.status(201);
});

pm.test("Response contains resource ID", function () {
    const body = pm.response.json();
    // Adjust property name based on resource type
    pm.expect(body).to.have.property("institution_id");
    pm.expect(body.institution_id).to.match(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
});

pm.test("Response includes all required fields", function () {
    const body = pm.response.json();
    pm.expect(body).to.have.property("name");
    pm.expect(body).to.have.property("status");
    pm.expect(body).to.have.property("created_date");
    pm.expect(body).to.have.property("modified_date");
});

pm.test("Created resource has correct values", function () {
    const body = pm.response.json();
    const requestBody = JSON.parse(pm.request.body.raw);
    pm.expect(body.name).to.equal(requestBody.name);
});

pm.test("Timestamps are valid ISO 8601 format", function () {
    const body = pm.response.json();
    pm.expect(body.created_date).to.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
    pm.expect(new Date(body.created_date).toString()).to.not.equal("Invalid Date");
});

pm.test("Default status is Active", function () {
    const body = pm.response.json();
    pm.expect(body.status).to.equal("Active");
});

pm.test("is_archived is false by default", function () {
    const body = pm.response.json();
    pm.expect(body.is_archived).to.be.false;
});
```

---

### 5. **PUT/PATCH/Update Endpoints - Verify Changes**

```javascript
pm.test("Update successful", function () {
    pm.response.to.have.status(200);
});

pm.test("Updated fields reflect changes", function () {
    const body = pm.response.json();
    const requestBody = JSON.parse(pm.request.body.raw);
    
    // Verify each updated field
    Object.keys(requestBody).forEach(key => {
        pm.expect(body[key]).to.equal(requestBody[key]);
    });
});

pm.test("modified_date is updated", function () {
    const body = pm.response.json();
    pm.expect(body.modified_date).to.exist;
    
    // Optional: Verify modified_date is recent (within last 5 seconds)
    const modifiedDate = new Date(body.modified_date);
    const now = new Date();
    const diffSeconds = (now - modifiedDate) / 1000;
    pm.expect(diffSeconds).to.be.below(5);
});

pm.test("Unchanged fields remain the same", function () {
    const body = pm.response.json();
    // Verify critical fields weren't accidentally changed
    pm.expect(body.created_date).to.exist;
    pm.expect(body.id).to.exist;
});
```

---

### 6. **GET/List Endpoints - Structure & Data Validation**

```javascript
pm.test("List retrieved successfully", function () {
    pm.response.to.have.status(200);
});

pm.test("Response is an array", function () {
    const body = pm.response.json();
    pm.expect(body).to.be.an("array");
});

pm.test("Array contains valid items", function () {
    const body = pm.response.json();
    
    if (body.length > 0) {
        body.forEach((item, index) => {
            pm.expect(item, `Item ${index} has ID`).to.have.property("id");
            pm.expect(item, `Item ${index} has name`).to.have.property("name");
            pm.expect(item, `Item ${index} has status`).to.have.property("status");
        });
    }
});

pm.test("Archived items are excluded (when include_archived=false)", function () {
    const body = pm.response.json();
    body.forEach((item, index) => {
        pm.expect(item.is_archived, `Item ${index} should not be archived`).to.be.false;
    });
});

pm.test("Items are sorted correctly", function () {
    const body = pm.response.json();
    
    // Verify sorting (e.g., by created_date desc)
    for (let i = 1; i < body.length; i++) {
        const prev = new Date(body[i-1].created_date);
        const curr = new Date(body[i].created_date);
        pm.expect(prev.getTime()).to.be.at.least(curr.getTime());
    }
});
```

---

### 7. **GET/Single Resource - Detailed Validation**

```javascript
pm.test("Resource found", function () {
    pm.response.to.have.status(200);
});

pm.test("Response contains complete resource", function () {
    const body = pm.response.json();
    
    // Core fields
    pm.expect(body).to.have.property("id");
    pm.expect(body).to.have.property("name");
    pm.expect(body).to.have.property("status");
    pm.expect(body).to.have.property("created_date");
    pm.expect(body).to.have.property("modified_date");
    pm.expect(body).to.have.property("is_archived");
    
    // Relationships
    pm.expect(body).to.have.property("institution_id");
    pm.expect(body).to.have.property("address_id");
});

pm.test("ID matches requested ID", function () {
    const body = pm.response.json();
    const requestedId = pm.collectionVariables.get("resourceId");
    pm.expect(body.id).to.equal(requestedId);
});
```

---

### 8. **Relationship Validation Tests**

```javascript
pm.test("Foreign key relationships are valid UUIDs", function () {
    const body = pm.response.json();
    
    const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    
    if (body.institution_id) {
        pm.expect(body.institution_id).to.match(uuidPattern);
    }
    if (body.address_id) {
        pm.expect(body.address_id).to.match(uuidPattern);
    }
    if (body.user_id) {
        pm.expect(body.user_id).to.match(uuidPattern);
    }
});

pm.test("Enriched data includes related entities", function () {
    const body = pm.response.json();
    
    // For enriched endpoints
    pm.expect(body).to.have.property("address_country");
    pm.expect(body).to.have.property("address_city");
    pm.expect(body).to.have.property("institution_name");
});
```

---

### 9. **Business Logic Validation**

```javascript
// Example: Plate Selection
pm.test("Plate selection validates credit availability", function () {
    const body = pm.response.json();
    const userCredit = pm.collectionVariables.get("userCreditBalance");
    const plateCost = pm.collectionVariables.get("plateCreditCost");
    
    pm.expect(userCredit).to.be.at.least(plateCost);
});

pm.test("No-show discount is within valid range", function () {
    const body = pm.response.json();
    pm.expect(body.no_show_discount).to.be.at.least(0);
    pm.expect(body.no_show_discount).to.be.at.most(100);
});

pm.test("Price and credit values are positive", function () {
    const body = pm.response.json();
    pm.expect(body.price).to.be.above(0);
    pm.expect(body.credit).to.be.above(0);
});
```

---

### 10. **Error Handling Tests (Negative Tests)**

Add these as separate requests in a "❌ Negative Tests" folder:

```javascript
// Test: Create without required field
pm.test("Returns 422 for missing required field", function () {
    pm.response.to.have.status(422);
});

pm.test("Error message is descriptive", function () {
    const body = pm.response.json();
    pm.expect(body).to.have.property("detail");
    pm.expect(body.detail).to.be.an("array");
    pm.expect(body.detail[0]).to.have.property("msg");
});

// Test: Invalid UUID format
pm.test("Returns 422 for invalid UUID", function () {
    pm.response.to.have.status(422);
    const body = pm.response.json();
    pm.expect(body.detail[0].type).to.include("uuid");
});

// Test: Unauthorized access
pm.test("Returns 401 without auth token", function () {
    pm.response.to.have.status(401);
});

// Test: Forbidden access
pm.test("Returns 403 for insufficient permissions", function () {
    pm.response.to.have.status(403);
});

// Test: Resource not found
pm.test("Returns 404 for non-existent resource", function () {
    pm.response.to.have.status(404);
});

// Test: Duplicate resource
pm.test("Returns 409 for duplicate resource", function () {
    pm.response.to.have.status(409);
});
```

---

### 11. **Data Integrity Tests (Cross-Request Validation)**

```javascript
// After creating a resource, verify it appears in list
pm.test("Created resource appears in list", function () {
    const createdId = pm.collectionVariables.get("createdResourceId");
    
    pm.sendRequest({
        url: pm.environment.get("baseUrl") + "/api/v1/resources/",
        method: 'GET',
        header: {
            'Authorization': 'Bearer ' + pm.environment.get("authToken")
        }
    }, function (err, res) {
        const resources = res.json();
        const found = resources.find(r => r.id === createdId);
        pm.expect(found).to.exist;
    });
});

// Verify cascading updates
pm.test("Child resources reflect parent updates", function () {
    // Verify related data is consistent
});
```

---

### 12. **Performance & Monitoring Tests**

```javascript
pm.test("Response time is within SLA (critical endpoints < 500ms)", function () {
    pm.expect(pm.response.responseTime).to.be.below(500);
});

pm.test("Response time is within SLA (standard endpoints < 2000ms)", function () {
    pm.expect(pm.response.responseTime).to.be.below(2000);
});

pm.test("Response size is reasonable (< 1MB)", function () {
    const responseSize = pm.response.size().body;
    pm.expect(responseSize).to.be.below(1048576); // 1MB
});

pm.test("Database query is efficient (check response headers)", function () {
    // If your API returns query time in headers
    const queryTime = pm.response.headers.get("X-Query-Time");
    if (queryTime) {
        pm.expect(parseInt(queryTime)).to.be.below(100); // 100ms
    }
});
```

---

## Specific Improvements for Your Collection

### Immediate Actions (High Priority)

1. **Add tests to all Login endpoints**:
   - Login Admin (3 instances)
   - Login Supplier User (2 instances)
   - Login Customer User

2. **Add tests to all Logout endpoints**:
   - Logout Admin (3 instances)
   - Logout Supplier
   - Logout Customer User

3. **Add comprehensive tests to Update endpoints**:
   - Update Supplier Product
   - Update Customer Address
   - Update Payment Attempt Status

4. **Add tests to Fetch/Read endpoints**:
   - Fetch Currency Country Code (currently deprecated but should have tests if kept)
   - Get Bills

5. **Add validation tests to business-critical operations**:
   - Register plate selection
   - Post QR Code Scan
   - Generate Daily Bills
   - Issue bills
   - Record Manual Payment

---

## Test Organization Strategy

### Folder Structure
```
E2E Plate Selection/
├── 🔐 Authentication & Setup/
│   └── (Add status + token validation to all)
├── 🏢 Supplier Setup/
│   └── (Add creation validation to all)
├── 🍽️ Supplier Menu Setup/
│   └── (Add product/plate validation)
├── 👤 Client Setup/
│   └── (Add user + subscription validation)
├── 💳 Payment Flow/
│   └── (Add payment validation)
├── 🍽️ Plate Selection & Pickup/
│   └── (Add selection + pickup validation)
├── 💰 Billing & Settlement/
│   └── (Add billing validation)
└── ❌ Negative Tests/ (NEW)
    ├── Invalid UUIDs
    ├── Missing Required Fields
    ├── Unauthorized Access
    ├── Insufficient Permissions
    └── Not Found Scenarios
```

---

## Implementation Priority

### Phase 1: Core Coverage (Week 1)
- [ ] Add status code tests to ALL requests
- [ ] Add response structure validation to all POST/PUT
- [ ] Add authentication tests to all login/logout
- [ ] Fix existing tests that don't assert (only console.log)

### Phase 2: Business Logic (Week 2)
- [ ] Add value validation for all create/update operations
- [ ] Add relationship validation (foreign keys)
- [ ] Add data consistency checks (cross-request)
- [ ] Add timestamp and audit field validation

### Phase 3: Advanced (Week 3)
- [ ] Add performance/SLA tests
- [ ] Add negative test scenarios (separate folder)
- [ ] Add data integrity tests
- [ ] Add idempotency tests

### Phase 4: Monitoring (Week 4)
- [ ] Add response time tracking
- [ ] Add data quality checks
- [ ] Add test reporting/dashboards
- [ ] Document all test scenarios

---

## Test Metrics to Track

1. **Coverage Metrics**
   - Requests with tests: Target 100% (currently ~75%)
   - Assertions per request: Target 5+ (currently ~1-2)
   - Status codes tested: Target all (200, 201, 400, 401, 403, 404, 409, 422)

2. **Quality Metrics**
   - Tests passing: Target 100% (currently 36 passing)
   - Test failures investigated: Target < 24 hours
   - Flaky tests: Target 0%

3. **Performance Metrics**
   - Response time SLA compliance: Target 95%+
   - Test suite execution time: Target < 5 minutes

---

## Next Steps

1. **Review this strategy** with your team
2. **Prioritize** which improvements to tackle first
3. **Create a template** for common test patterns
4. **Assign ownership** for different test categories
5. **Set up CI/CD** to run tests automatically
6. **Monitor results** and iterate

Would you like me to implement any specific section of these improvements into your collection?
