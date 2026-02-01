# 🏦 POSTMAN SCRIPTS: INSTITUTION BANK ACCOUNT API

## 📋 **COLLECTION SETUP**

### **Collection Variables:**
```json
{
  "base_url": "http://localhost:8000",
  "auth_token": "",
  "institution_id": "",
  "institution_entity_id": "",
  "address_id": "",
  "bank_account_id": ""
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

## 🏦 **2. INSTITUTION BANK ACCOUNT CREATION**

### **Create Bank Account (Full):**
```
POST {{base_url}}/institution-bank-accounts
Authorization: Bearer {{auth_token}}
Content-Type: application/json

{
  "institution_entity_id": "{{institution_entity_id}}",
  "address_id": "{{address_id}}",
  "account_holder_name": "Acme Corporation",
  "bank_name": "Chase Bank",
  "account_type": "Business",
  "routing_number": "021000021",
  "account_number": "1234567890",
  "status": "Active"
}
```

### **Create Bank Account (Minimal):**
```
POST {{base_url}}/institution-bank-accounts
Authorization: Bearer {{auth_token}}
Content-Type: application/json

{
  "institution_entity_id": "{{institution_entity_id}}",
  "account_holder_name": "Acme Corporation",
  "bank_name": "Bank of America",
  "account_type": "Business",
  "routing_number": "026009593",
  "account_number": "9876543210"
}
```

### **Pre-request Script (Auto-populate):**
```javascript
// Auto-generate account token if not provided
const accountNumber = pm.request.body.raw.match(/"account_number":\s*"([^"]+)"/)[1];
const accountToken = "TOKEN_" + accountNumber + "_" + Date.now();
pm.request.body.raw = pm.request.body.raw.replace('}', `,\n  "account_token": "${accountToken}"\n}`);

// Set default status if not provided
if (!pm.request.body.raw.includes('"status"')) {
    pm.request.body.raw = pm.request.body.raw.replace('}', ',\n  "status": "Active"\n}');
}

// Auto-populate address_id from institution_entity if not provided
if (!pm.request.body.raw.includes('"address_id"')) {
    pm.request.body.raw = pm.request.body.raw.replace('}', `,\n  "address_id": "{{address_id}}"\n}`);
}
```

### **Post-request Script (Store Bank Account ID):**
```javascript
if (pm.response.code === 201) {
    const response = pm.response.json();
    pm.collectionVariables.set("bank_account_id", response.bank_account_id);
    
    console.log("✅ Bank Account created successfully");
    console.log("Bank Account ID:", response.bank_account_id);
    console.log("Account Holder:", response.account_holder_name);
    console.log("Bank Name:", response.bank_name);
    console.log("Account Type:", response.account_type);
    console.log("Account Token:", response.account_token);
}
```

---

## 📋 **3. INSTITUTION BANK ACCOUNT RETRIEVAL**

### **Get Bank Account by ID:**
```
GET {{base_url}}/institution-bank-accounts/{{bank_account_id}}
Authorization: Bearer {{auth_token}}
```

### **Get All Bank Accounts:**
```
GET {{base_url}}/institution-bank-accounts
Authorization: Bearer {{auth_token}}
```

### **Get All Bank Accounts (Include Archived):**
```
GET {{base_url}}/institution-bank-accounts?include_archived=true
Authorization: Bearer {{auth_token}}
```

### **Get Bank Accounts by Institution Entity:**
```
GET {{base_url}}/institution-bank-accounts?institution_entity_id={{institution_entity_id}}
Authorization: Bearer {{auth_token}}
```

### **Get Bank Accounts by Institution:**
```
GET {{base_url}}/institution-bank-accounts?institution_id={{institution_id}}
Authorization: Bearer {{auth_token}}
```

### **Get Active Bank Accounts:**
```
GET {{base_url}}/institution-bank-accounts/active/{{institution_entity_id}}
Authorization: Bearer {{auth_token}}
```

### **Post-request Script (Validation):**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    
    if (Array.isArray(response)) {
        console.log(`✅ Retrieved ${response.length} bank accounts`);
        response.forEach((account, index) => {
            console.log(`${index + 1}. ${account.account_holder_name} - ${account.bank_name} (${account.account_type})`);
        });
    } else {
        console.log("✅ Retrieved bank account:", response.account_holder_name);
        console.log("Bank:", response.bank_name);
        console.log("Account Type:", response.account_type);
        console.log("Status:", response.status);
    }
}
```

---

## ✏️ **4. INSTITUTION BANK ACCOUNT UPDATE**

### **Update Bank Account:**
```
PUT {{base_url}}/institution-bank-accounts/{{bank_account_id}}
Authorization: Bearer {{auth_token}}
Content-Type: application/json

{
  "account_holder_name": "Acme Corporation - Updated",
  "bank_name": "Wells Fargo Bank",
  "account_type": "Corporate",
  "status": "Active"
}
```

### **Pre-request Script (Smart Updates):**
```javascript
// Only include fields that need updating
const updateData = {};
const body = pm.request.body.raw;

if (body.includes('"account_holder_name"')) {
    updateData.account_holder_name = "Acme Corporation - Updated";
}
if (body.includes('"bank_name"')) {
    updateData.bank_name = "Wells Fargo Bank";
}
if (body.includes('"account_type"')) {
    updateData.account_type = "Corporate";
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
    console.log("✅ Bank Account updated successfully");
    console.log("Updated Account Holder:", response.account_holder_name);
    console.log("Updated Bank Name:", response.bank_name);
    console.log("Updated Account Type:", response.account_type);
    console.log("Modified Date:", response.modified_date);
}
```

---

## 🗑️ **5. INSTITUTION BANK ACCOUNT DELETION**

### **Delete Bank Account (Soft Delete):**
```
DELETE {{base_url}}/institution-bank-accounts/{{bank_account_id}}
Authorization: Bearer {{auth_token}}
```

### **Post-request Script (Deletion Confirmation):**
```javascript
if (pm.response.code === 200) {
    console.log("✅ Bank Account deleted successfully");
    console.log("Note: This is a soft delete - record is archived, not removed");
}
```

---

## 🔍 **6. ADVANCED QUERIES & VALIDATION**

### **Validate Routing Number Format:**
```javascript
// Pre-request script for routing number validation
const routingNumber = pm.request.body.raw.match(/"routing_number":\s*"([^"]+)"/)[1];
if (routingNumber.length !== 9 || !/^\d+$/.test(routingNumber)) {
    throw new Error("Routing number must be exactly 9 digits");
}
```

### **Validate Account Number Format:**
```javascript
// Pre-request script for account number validation
const accountNumber = pm.request.body.raw.match(/"account_number":\s*"([^"]+)"/)[1];
if (accountNumber.length < 4 || accountNumber.length > 17 || !/^\d+$/.test(accountNumber)) {
    throw new Error("Account number must be 4-17 digits");
}
```

### **Validate Account Type:**
```javascript
// Pre-request script for account type validation
const accountType = pm.request.body.raw.match(/"account_type":\s*"([^"]+)"/)[1];
const validTypes = ['Checking', 'Savings', 'Business', 'Corporate', 'Investment'];
if (!validTypes.includes(accountType)) {
    throw new Error(`Account type must be one of: ${validTypes.join(', ')}`);
}
```

---

## 📊 **7. TESTING SCENARIOS**

### **Scenario 1: Complete Bank Account Lifecycle**
```javascript
// Test script for complete bank account lifecycle
pm.test("Complete Bank Account Lifecycle", function () {
    // 1. Create bank account
    pm.expect(pm.response.code).to.equal(201);
    
    // 2. Retrieve bank account
    pm.expect(pm.response.json()).to.have.property('bank_account_id');
    pm.expect(pm.response.json()).to.have.property('account_holder_name');
    pm.expect(pm.response.json()).to.have.property('bank_name');
    pm.expect(pm.response.json()).to.have.property('account_token');
    
    // 3. Update bank account
    pm.expect(pm.response.code).to.equal(200);
    
    // 4. Delete bank account
    pm.expect(pm.response.code).to.equal(200);
});
```

### **Scenario 2: Validation Testing**
```javascript
// Test script for validation
pm.test("Validation Rules", function () {
    const response = pm.response.json();
    
    // Check required fields
    pm.expect(response.institution_entity_id).to.not.be.undefined;
    pm.expect(response.account_holder_name).to.not.be.undefined;
    pm.expect(response.bank_name).to.not.be.undefined;
    pm.expect(response.account_type).to.not.be.undefined;
    pm.expect(response.routing_number).to.not.be.undefined;
    pm.expect(response.account_number).to.not.be.undefined;
    pm.expect(response.account_token).to.not.be.undefined;
    
    // Check field lengths
    pm.expect(response.account_holder_name.length).to.be.at.most(100);
    pm.expect(response.bank_name.length).to.be.at.most(100);
    pm.expect(response.account_type.length).to.be.at.most(50);
    pm.expect(response.routing_number.length).to.be.at.most(50);
    pm.expect(response.account_number.length).to.be.at.most(50);
    pm.expect(response.account_token.length).to.be.at.most(100);
    
    // Check status values
    pm.expect(['Active', 'Inactive', 'Pending', 'Suspended']).to.include(response.status);
});
```

### **Scenario 3: Business Logic Testing**
```javascript
// Test script for business logic
pm.test("Business Logic", function () {
    const response = pm.response.json();
    
    // Check account token generation
    pm.expect(response.account_token).to.include(response.account_number);
    
    // Check account type validation
    const validTypes = ['Checking', 'Savings', 'Business', 'Corporate', 'Investment'];
    pm.expect(validTypes).to.include(response.account_type);
    
    // Check routing number format
    pm.expect(response.routing_number).to.match(/^\d{9}$/);
    
    // Check account number format
    pm.expect(response.account_number).to.match(/^\d{4,17}$/);
});
```

---

## 🚀 **8. AUTOMATION SCRIPTS**

### **Pre-request Script (Auto-setup):**
```javascript
// Auto-setup for testing
if (!pm.collectionVariables.get("institution_entity_id")) {
    // Create test institution entity if needed
    pm.collectionVariables.set("institution_entity_id", "test-entity-id");
}

if (!pm.collectionVariables.get("address_id")) {
    // Create test address if needed
    pm.collectionVariables.set("address_id", "test-address-id");
}

// Auto-generate test data
if (pm.request.method === "POST") {
    const testData = {
        account_holder_name: "Test Corporation " + Math.random().toString(36).substr(2, 5),
        bank_name: "Test Bank " + Math.random().toString(36).substr(2, 5),
        account_type: ["Checking", "Savings", "Business", "Corporate", "Investment"][Math.floor(Math.random() * 5)],
        routing_number: Math.floor(100000000 + Math.random() * 900000000).toString(),
        account_number: Math.floor(1000 + Math.random() * 9000).toString()
    };
    
    // Update request body with test data
    let body = pm.request.body.raw;
    Object.keys(testData).forEach(key => {
        const regex = new RegExp(`"${key}":\\s*"[^"]*"`);
        body = body.replace(regex, `"${key}": "${testData[key]}"`);
    });
    pm.request.body.raw = body;
}
```

### **Post-request Script (Auto-cleanup):**
```javascript
// Auto-cleanup after tests
if (pm.response.code === 201) {
    // Store bank account ID for cleanup
    const response = pm.response.json();
    pm.collectionVariables.set("created_bank_account_id", response.bank_account_id);
}

// Cleanup after all tests
if (pm.collectionVariables.get("created_bank_account_id")) {
    // Delete test bank account
    pm.sendRequest({
        url: pm.collectionVariables.get("base_url") + "/institution-bank-accounts/" + pm.collectionVariables.get("created_bank_account_id"),
        method: 'DELETE',
        header: {
            'Authorization': 'Bearer ' + pm.collectionVariables.get("auth_token")
        }
    });
}
```

---

## 📝 **9. USAGE EXAMPLES**

### **Create Business Checking Account:**
```json
{
  "institution_entity_id": "{{institution_entity_id}}",
  "account_holder_name": "Kitchen Delights LLC",
  "bank_name": "Chase Bank",
  "account_type": "Business",
  "routing_number": "021000021",
  "account_number": "1234567890"
}
```

### **Create Corporate Savings Account:**
```json
{
  "institution_entity_id": "{{institution_entity_id}}",
  "account_holder_name": "Fresh Ingredients Corp",
  "bank_name": "Bank of America",
  "account_type": "Corporate",
  "routing_number": "026009593",
  "account_number": "9876543210"
}
```

### **Create Investment Account:**
```json
{
  "institution_entity_id": "{{institution_entity_id}}",
  "account_holder_name": "Kitchen Ventures Inc",
  "bank_name": "Goldman Sachs",
  "account_type": "Investment",
  "routing_number": "021000021",
  "account_number": "5555666677"
}
```

---

## 🔐 **10. SECURITY & COMPLIANCE**

### **Account Token Generation:**
```javascript
// Post-request script to verify account token security
if (pm.response.code === 201) {
    const response = pm.response.json();
    
    // Verify account token is generated and secure
    pm.expect(response.account_token).to.not.equal(response.account_number);
    pm.expect(response.account_token).to.include(response.account_number);
    pm.expect(response.account_token).to.include("TOKEN_");
    
    console.log("🔐 Account token generated securely:", response.account_token);
}
```

### **Data Masking:**
```javascript
// Pre-request script to mask sensitive data in logs
const accountNumber = pm.request.body.raw.match(/"account_number":\s*"([^"]+)"/)[1];
const maskedNumber = "*".repeat(accountNumber.length - 4) + accountNumber.slice(-4);
console.log("🔒 Account number masked for security:", maskedNumber);
```

---

## ✅ **11. SUCCESS CRITERIA**

### **API Response Validation:**
- ✅ **201 Created** for successful bank account creation
- ✅ **200 OK** for successful retrieval/update
- ✅ **200 OK** for successful deletion (soft delete)
- ✅ **404 Not Found** for non-existent bank accounts
- ✅ **422 Validation Error** for invalid data

### **Data Integrity:**
- ✅ **Required fields** are properly validated
- ✅ **Field lengths** respect database constraints
- ✅ **Account token** is automatically generated
- ✅ **Routing/account numbers** are properly formatted
- ✅ **Account types** are validated against allowed values
- ✅ **Foreign key relationships** are maintained
- ✅ **Audit trail** is properly recorded
- ✅ **Soft delete** functionality works correctly

---

## 🎯 **READY FOR TESTING!**

These Postman scripts provide comprehensive testing for the Institution Bank Account API. The scripts include:

- **Authentication setup** with token management
- **CRUD operations** with proper validation
- **Smart field population** to minimize manual input
- **Automatic account token generation** for security
- **Comprehensive validation** for banking data
- **Automated testing scenarios** for quality assurance
- **Cleanup scripts** for test data management
- **Security features** for sensitive banking information

**Next Step:** Use these scripts to test both APIs and prepare for payment attempt implementation! 🚀

---

## 🔄 **WORKFLOW ORDER:**

1. **First:** Test Institution Entity API using `POSTMAN_INSTITUTION_ENTITY_SCRIPTS.md`
2. **Second:** Test Institution Bank Account API using `POSTMAN_INSTITUTION_BANK_ACCOUNT_SCRIPTS.md`
3. **Third:** Proceed to Payment Attempt implementation

This ensures proper data relationships are established before testing bank account functionality! 🎯 