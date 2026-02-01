# 🏛️ POSTMAN SCRIPTS: INSTITUTION ENTITY API

## 📋 **COLLECTION SETUP**

### **Collection Variables:**
```json
{
  "base_url": "http://localhost:8000",
  "auth_token": "",
  "institution_id": "",
  "address_id": "",
  "institution_entity_id": ""
}
```

---

## 🔐 **1. AUTHENTICATION SETUP**

### **Login Request:**
```
POST {{base_url}}/auth/login
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

### **Pre-request Script (Set Token):**
```javascript
// Extract token from login response
if (pm.response.code === 200) {
    const response = pm.response.json();
    pm.collectionVariables.set("auth_token", response.access_token);
}
```

---

## 🏢 **2. INSTITUTION ENTITY CREATION**

### **Create Institution Entity:**
```
POST {{base_url}}/institution-entities
Authorization: Bearer {{auth_token}}
Content-Type: application/json

{
  "institution_id": "{{institution_id}}",
  "address_id": "{{address_id}}",
  "tax_id": "TAX123456789",
  "name": "Acme Corporation Legal Entity",
  "status": "Active"
}
```

### **Pre-request Script (Auto-populate):**
```javascript
// Auto-generate tax ID if not provided
if (!pm.request.body.raw) {
    const taxId = "TAX" + Math.random().toString(36).substr(2, 9).toUpperCase();
    pm.request.body.raw = pm.request.body.raw.replace('"tax_id": "TAX123456789"', `"tax_id": "${taxId}"`);
}

// Set default status if not provided
if (!pm.request.body.raw.includes('"status"')) {
    pm.request.body.raw = pm.request.body.raw.replace('}', ',\n  "status": "Active"\n}');
}
```

### **Post-request Script (Store Entity ID):**
```javascript
if (pm.response.code === 201) {
    const response = pm.response.json();
    pm.collectionVariables.set("institution_entity_id", response.institution_entity_id);
    
    console.log("✅ Institution Entity created successfully");
    console.log("Entity ID:", response.institution_entity_id);
    console.log("Name:", response.name);
    console.log("Tax ID:", response.tax_id);
}
```

---

## 📋 **3. INSTITUTION ENTITY RETRIEVAL**

### **Get Entity by ID:**
```
GET {{base_url}}/institution-entities/{{institution_entity_id}}
Authorization: Bearer {{auth_token}}
```

### **Get All Entities:**
```
GET {{base_url}}/institution-entities
Authorization: Bearer {{auth_token}}
```

### **Get All Entities (Include Archived):**
```
GET {{base_url}}/institution-entities?include_archived=true
Authorization: Bearer {{auth_token}}
```

### **Post-request Script (Validation):**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    
    if (Array.isArray(response)) {
        console.log(`✅ Retrieved ${response.length} institution entities`);
        response.forEach((entity, index) => {
            console.log(`${index + 1}. ${entity.name} (${entity.institution_entity_id})`);
        });
    } else {
        console.log("✅ Retrieved institution entity:", response.name);
        console.log("Tax ID:", response.tax_id);
        console.log("Status:", response.status);
    }
}
```

---

## ✏️ **4. INSTITUTION ENTITY UPDATE**

### **Update Entity:**
```
PUT {{base_url}}/institution-entities/{{institution_entity_id}}
Authorization: Bearer {{auth_token}}
Content-Type: application/json

{
  "name": "Acme Corporation Legal Entity - Updated",
  "tax_id": "TAX987654321",
  "status": "Active"
}
```

### **Pre-request Script (Smart Updates):**
```javascript
// Only include fields that need updating
const updateData = {};
const body = pm.request.body.raw;

if (body.includes('"name"')) {
    updateData.name = "Acme Corporation Legal Entity - Updated";
}
if (body.includes('"tax_id"')) {
    updateData.tax_id = "TAX" + Math.random().toString(36).substr(2, 9).toUpperCase();
}
if (body.includes('"status"')) {
    updateData.status = "Active";
}

pm.request.body.raw = JSON.stringify(updateData, null, 2);
```

### **Post-request Script (Update Confirmation):**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    console.log("✅ Institution Entity updated successfully");
    console.log("Updated Name:", response.name);
    console.log("Updated Tax ID:", response.tax_id);
    console.log("Modified Date:", response.modified_date);
}
```

---

## 🗑️ **5. INSTITUTION ENTITY DELETION**

### **Delete Entity (Soft Delete):**
```
DELETE {{base_url}}/institution-entities/{{institution_entity_id}}
Authorization: Bearer {{auth_token}}
```

### **Post-request Script (Deletion Confirmation):**
```javascript
if (pm.response.code === 200) {
    console.log("✅ Institution Entity deleted successfully");
    console.log("Note: This is a soft delete - record is archived, not removed");
}
```

---

## 🔍 **6. ADVANCED QUERIES**

### **Get Entity with Related Data:**
```
GET {{base_url}}/institution-entities/{{institution_entity_id}}?include_archived=false
Authorization: Bearer {{auth_token}}
```

### **Get Entities by Institution:**
```
GET {{base_url}}/institution-entities?institution_id={{institution_id}}
Authorization: Bearer {{auth_token}}
```

---

## 📊 **7. TESTING SCENARIOS**

### **Scenario 1: Complete Entity Lifecycle**
```javascript
// Test script for complete entity lifecycle
pm.test("Complete Entity Lifecycle", function () {
    // 1. Create entity
    pm.expect(pm.response.code).to.equal(201);
    
    // 2. Retrieve entity
    pm.expect(pm.response.json()).to.have.property('institution_entity_id');
    pm.expect(pm.response.json()).to.have.property('name');
    pm.expect(pm.response.json()).to.have.property('tax_id');
    
    // 3. Update entity
    pm.expect(pm.response.code).to.equal(200);
    
    // 4. Delete entity
    pm.expect(pm.response.code).to.equal(200);
});
```

### **Scenario 2: Validation Testing**
```javascript
// Test script for validation
pm.test("Validation Rules", function () {
    const response = pm.response.json();
    
    // Check required fields
    pm.expect(response.institution_id).to.not.be.undefined;
    pm.expect(response.address_id).to.not.be.undefined;
    pm.expect(response.tax_id).to.not.be.undefined;
    pm.expect(response.name).to.not.be.undefined;
    
    // Check field lengths
    pm.expect(response.tax_id.length).to.be.at.most(50);
    pm.expect(response.name.length).to.be.at.most(100);
    
    // Check status values
    pm.expect(['Active', 'Inactive', 'Pending']).to.include(response.status);
});
```

---

## 🚀 **8. AUTOMATION SCRIPTS**

### **Pre-request Script (Auto-setup):**
```javascript
// Auto-setup for testing
if (!pm.collectionVariables.get("institution_id")) {
    // Create test institution if needed
    pm.collectionVariables.set("institution_id", "test-institution-id");
}

if (!pm.collectionVariables.get("address_id")) {
    // Create test address if needed
    pm.collectionVariables.set("address_id", "test-address-id");
}
```

### **Post-request Script (Auto-cleanup):**
```javascript
// Auto-cleanup after tests
if (pm.response.code === 201) {
    // Store entity ID for cleanup
    const response = pm.response.json();
    pm.collectionVariables.set("created_entity_id", response.institution_entity_id);
}

// Cleanup after all tests
if (pm.collectionVariables.get("created_entity_id")) {
    // Delete test entity
    pm.sendRequest({
        url: pm.collectionVariables.get("base_url") + "/institution-entities/" + pm.collectionVariables.get("created_entity_id"),
        method: 'DELETE',
        header: {
            'Authorization': 'Bearer ' + pm.collectionVariables.get("auth_token")
        }
    });
}
```

---

## 📝 **9. USAGE EXAMPLES**

### **Create Entity for Restaurant Chain:**
```json
{
  "institution_id": "{{institution_id}}",
  "address_id": "{{address_id}}",
  "tax_id": "RESTAURANT-TAX-001",
  "name": "Kitchen Delights Legal Entity",
  "status": "Active"
}
```

### **Create Entity for Food Supplier:**
```json
{
  "institution_id": "{{institution_id}}",
  "address_id": "{{address_id}}",
  "tax_id": "SUPPLIER-TAX-002",
  "name": "Fresh Ingredients Corp Legal Entity",
  "status": "Active"
}
```

---

## ✅ **10. SUCCESS CRITERIA**

### **API Response Validation:**
- ✅ **201 Created** for successful entity creation
- ✅ **200 OK** for successful retrieval/update
- ✅ **200 OK** for successful deletion (soft delete)
- ✅ **404 Not Found** for non-existent entities
- ✅ **422 Validation Error** for invalid data

### **Data Integrity:**
- ✅ **Required fields** are properly validated
- ✅ **Field lengths** respect database constraints
- ✅ **Foreign key relationships** are maintained
- ✅ **Audit trail** is properly recorded
- ✅ **Soft delete** functionality works correctly

---

## 🎯 **READY FOR TESTING!**

These Postman scripts provide comprehensive testing for the Institution Entity API. The scripts include:

- **Authentication setup** with token management
- **CRUD operations** with proper validation
- **Smart field population** to minimize manual input
- **Automated testing scenarios** for quality assurance
- **Cleanup scripts** for test data management

**Next Step:** Use these scripts to test the Institution Entity API, then proceed to Institution Bank Account API testing! 🚀 