# Institution Bank Account API - Postman Test Scripts

## 🚀 Setup Instructions

### 1. Environment Variables
Set these variables in your Postman environment:

```json
{
  "base_url": "http://localhost:8000",
  "auth_token": "your_bearer_token_here",
  "institution_entity_id": "",
  "bank_account_id": "",
  "address_id": ""
}
```

### 2. Collection Variables
The collection will automatically set these variables during execution:
- `institution_entity_id` - Set after creating institution entity
- `bank_account_id` - Set after creating bank account
- `address_id` - Set after creating institution entity

## 📋 Test Flow

### Phase 1: Prerequisites
1. **Create Institution Entity** - Required before creating bank accounts
2. **Verify Entity Creation** - Confirm entity was created successfully

### Phase 2: Bank Account Creation
3. **Create Full Bank Account** - All fields provided
4. **Create Minimal Bank Account** - Auto-population test
5. **Verify Account Creation** - Confirm accounts were created

### Phase 3: Retrieval & Validation
6. **Get Bank Account by ID** - Individual account retrieval
7. **Get All Bank Accounts** - List all accounts
8. **Get by Institution Entity** - Filtered retrieval
9. **Get Active Accounts** - Status-based filtering
10. **Validate Bank Account** - Format validation

### Phase 4: Updates & Modifications
11. **Update Bank Account** - Modify account details
12. **Verify Updates** - Confirm changes were applied

### Phase 5: Error Handling
13. **Test Validation Errors** - Invalid data scenarios
14. **Verify Error Responses** - Proper error handling

### Phase 6: Cleanup
15. **Delete Bank Account** - Soft delete
16. **Verify Deletion** - Confirm account is not accessible

## 🔧 Pre-request Scripts

### Global Pre-request Script
```javascript
// Set default headers
pm.request.headers.add({
    key: 'Content-Type',
    value: 'application/json'
});

// Log request details
console.log('Request:', pm.request.method, pm.request.url);

// Add authorization if token exists
if (pm.collectionVariables.get('auth_token')) {
    pm.request.headers.add({
        key: 'Authorization',
        value: 'Bearer ' + pm.collectionVariables.get('auth_token')
    });
}
```

## ✅ Test Scripts

### 1. Create Institution Entity
```javascript
pm.test('Institution Entity Created Successfully', function () {
    pm.expect(pm.response.code).to.equal(201);
    const response = pm.response.json();
    
    // Verify required fields
    pm.expect(response).to.have.property('institution_entity_id');
    pm.expect(response).to.have.property('name');
    pm.expect(response).to.have.property('tax_id');
    pm.expect(response).to.have.property('status');
    
    // Store IDs for later use
    pm.collectionVariables.set('institution_entity_id', response.institution_entity_id);
    pm.collectionVariables.set('address_id', response.address_id);
    
    console.log('✅ Created Institution Entity ID:', response.institution_entity_id);
    console.log('✅ Address ID:', response.address_id);
    console.log('✅ Entity Name:', response.name);
    console.log('✅ Tax ID:', response.tax_id);
});
```

### 2. Create Bank Account (Full)
```javascript
pm.test('Bank Account Created Successfully', function () {
    pm.expect(pm.response.code).to.equal(201);
    const response = pm.response.json();
    
    // Verify required fields
    pm.expect(response).to.have.property('bank_account_id');
    pm.expect(response).to.have.property('account_holder_name');
    pm.expect(response).to.have.property('bank_name');
    pm.expect(response).to.have.property('account_type');
    pm.expect(response).to.have.property('routing_number');
    pm.expect(response).to.have.property('account_number');
    pm.expect(response).to.have.property('account_token');
    pm.expect(response).to.have.property('status');
    
    // Verify data integrity
    pm.expect(response.account_holder_name).to.equal('John Doe');
    pm.expect(response.bank_name).to.equal('Chase Bank');
    pm.expect(response.account_type).to.equal('Checking');
    pm.expect(response.routing_number).to.equal('021000021');
    pm.expect(response.account_number).to.equal('1234567890');
    pm.expect(response.status).to.equal('Active');
    
    // Store bank account ID
    pm.collectionVariables.set('bank_account_id', response.bank_account_id);
    
    console.log('✅ Created Bank Account ID:', response.bank_account_id);
    console.log('✅ Account Holder:', response.account_holder_name);
    console.log('✅ Bank Name:', response.bank_name);
    console.log('✅ Account Type:', response.account_type);
    console.log('✅ Account Token:', response.account_token);
});
```

### 3. Create Bank Account (Minimal)
```javascript
pm.test('Minimal Bank Account Created Successfully', function () {
    pm.expect(pm.response.code).to.equal(201);
    const response = pm.response.json();
    
    // Verify required fields
    pm.expect(response).to.have.property('bank_account_id');
    pm.expect(response).to.have.property('institution_entity_id');
    pm.expect(response).to.have.property('address_id');
    pm.expect(response).to.have.property('account_holder_name');
    pm.expect(response).to.have.property('bank_name');
    pm.expect(response).to.have.property('account_type');
    pm.expect(response).to.have.property('account_token');
    
    // Verify auto-populated fields
    pm.expect(response.address_id).to.equal(pm.collectionVariables.get('address_id'));
    pm.expect(response.status).to.equal('Active');
    pm.expect(response.is_archived).to.equal(false);
    
    // Verify provided data
    pm.expect(response.account_holder_name).to.equal('Jane Smith');
    pm.expect(response.bank_name).to.equal('Bank of America');
    pm.expect(response.account_type).to.equal('Savings');
    
    console.log('✅ Created Minimal Bank Account ID:', response.bank_account_id);
    console.log('✅ Auto-populated Address ID:', response.address_id);
    console.log('✅ Default Status:', response.status);
    console.log('✅ Account Holder:', response.account_holder_name);
});
```

### 4. Get Bank Account by ID
```javascript
pm.test('Bank Account Retrieved Successfully', function () {
    pm.expect(pm.response.code).to.equal(200);
    const response = pm.response.json();
    
    // Verify correct account
    pm.expect(response.bank_account_id).to.equal(pm.collectionVariables.get('bank_account_id'));
    pm.expect(response.institution_entity_id).to.equal(pm.collectionVariables.get('institution_entity_id'));
    
    // Verify account details
    pm.expect(response.account_holder_name).to.equal('John Doe Updated');
    pm.expect(response.bank_name).to.equal('Chase Bank');
    pm.expect(response.account_type).to.equal('Checking');
    pm.expect(response.status).to.equal('Inactive');
    
    console.log('✅ Retrieved Bank Account:', response.account_holder_name);
    console.log('✅ Bank:', response.bank_name);
    console.log('✅ Type:', response.account_type);
    console.log('✅ Status:', response.status);
});
```

### 5. Get All Bank Accounts
```javascript
pm.test('All Bank Accounts Retrieved Successfully', function () {
    pm.expect(pm.response.code).to.equal(200);
    const response = pm.response.json();
    
    // Verify response structure
    pm.expect(response).to.be.an('array');
    pm.expect(response.length).to.be.greaterThan(0);
    
    // Verify each account has required fields
    response.forEach((account, index) => {
        pm.expect(account).to.have.property('bank_account_id');
        pm.expect(account).to.have.property('account_holder_name');
        pm.expect(account).to.have.property('bank_name');
        pm.expect(account).to.have.property('account_type');
        pm.expect(account).to.have.property('status');
    });
    
    console.log('✅ Total Bank Accounts:', response.length);
    response.forEach((account, index) => {
        console.log(`   ${index + 1}. ${account.account_holder_name} - ${account.bank_name} (${account.status})`);
    });
});
```

### 6. Get Bank Accounts by Institution Entity
```javascript
pm.test('Bank Accounts by Institution Entity Retrieved Successfully', function () {
    pm.expect(pm.response.code).to.equal(200);
    const response = pm.response.json();
    
    // Verify response structure
    pm.expect(response).to.be.an('array');
    
    // All accounts should belong to the same institution entity
    response.forEach(account => {
        pm.expect(account.institution_entity_id).to.equal(pm.collectionVariables.get('institution_entity_id'));
    });
    
    console.log('✅ Bank Accounts for Institution Entity:', response.length);
    response.forEach((account, index) => {
        console.log(`   ${index + 1}. ${account.account_holder_name} - ${account.bank_name}`);
        console.log(`      Type: ${account.account_type}, Status: ${account.status}`);
    });
});
```

### 7. Get Active Bank Accounts
```javascript
pm.test('Active Bank Accounts Retrieved Successfully', function () {
    pm.expect(pm.response.code).to.equal(200);
    const response = pm.response.json();
    
    // Verify response structure
    pm.expect(response).to.be.an('array');
    
    // All accounts should be active
    response.forEach(account => {
        pm.expect(account.status).to.equal('Active');
        pm.expect(account.is_archived).to.equal(false);
    });
    
    console.log('✅ Active Bank Accounts:', response.length);
    response.forEach((account, index) => {
        console.log(`   ${index + 1}. ${account.account_holder_name} - ${account.bank_name}`);
        console.log(`      Type: ${account.account_type}, Status: ${account.status}`);
    });
});
```

### 8. Update Bank Account
```javascript
pm.test('Bank Account Updated Successfully', function () {
    pm.expect(pm.response.code).to.equal(200);
    const response = pm.response.json();
    
    // Verify updated fields
    pm.expect(response.account_holder_name).to.equal('John Doe Updated');
    pm.expect(response.status).to.equal('Inactive');
    
    // Verify unchanged fields
    pm.expect(response.bank_name).to.equal('Chase Bank');
    pm.expect(response.account_type).to.equal('Checking');
    pm.expect(response.routing_number).to.equal('021000021');
    pm.expect(response.account_number).to.equal('1234567890');
    
    console.log('✅ Updated Bank Account:', response.account_holder_name);
    console.log('✅ New Status:', response.status);
    console.log('✅ Bank:', response.bank_name);
    console.log('✅ Type:', response.account_type);
});
```

### 9. Validate Bank Account
```javascript
pm.test('Bank Account Validation Successful', function () {
    pm.expect(pm.response.code).to.equal(200);
    const response = pm.response.json();
    
    // Verify validation response structure
    pm.expect(response).to.have.property('bank_account_id');
    pm.expect(response).to.have.property('routing_number_valid');
    pm.expect(response).to.have.property('account_number_valid');
    pm.expect(response).to.have.property('overall_valid');
    pm.expect(response).to.have.property('validation_notes');
    
    // Verify validation results
    pm.expect(response.routing_number_valid).to.be.true;
    pm.expect(response.account_number_valid).to.be.true;
    pm.expect(response.overall_valid).to.be.true;
    pm.expect(response.validation_notes).to.be.an('array');
    pm.expect(response.validation_notes.length).to.equal(0);
    
    console.log('✅ Validation Result:', response);
    console.log('✅ Routing Number Valid:', response.routing_number_valid);
    console.log('✅ Account Number Valid:', response.account_number_valid);
    console.log('✅ Overall Valid:', response.overall_valid);
    
    if (response.overall_valid) {
        console.log('🎉 Bank account validation passed!');
    } else {
        console.log('❌ Bank account validation failed:', response.validation_notes);
    }
});
```

### 10. Test Validation Errors

#### Invalid Routing Number
```javascript
pm.test('Invalid Routing Number Rejected', function () {
    pm.expect(pm.response.code).to.equal(422);
    const response = pm.response.json();
    
    // Verify error response structure
    pm.expect(response).to.have.property('detail');
    pm.expect(response.detail).to.be.an('array');
    pm.expect(response.detail.length).to.be.greaterThan(0);
    
    // Verify error message
    const routingError = response.detail.find(error => 
        error.msg && error.msg.includes('Invalid routing number format')
    );
    pm.expect(routingError).to.not.be.undefined;
    
    console.log('✅ Validation error caught:', routingError.msg);
    console.log('✅ Error details:', response.detail);
});
```

#### Invalid Account Number
```javascript
pm.test('Invalid Account Number Rejected', function () {
    pm.expect(pm.response.code).to.equal(422);
    const response = pm.response.json();
    
    // Verify error response structure
    pm.expect(response).to.have.property('detail');
    pm.expect(response.detail).to.be.an('array');
    pm.expect(response.detail.length).to.be.greaterThan(0);
    
    // Verify error message
    const accountError = response.detail.find(error => 
        error.msg && error.msg.includes('Invalid account number format')
    );
    pm.expect(accountError).to.not.be.undefined;
    
    console.log('✅ Validation error caught:', accountError.msg);
    console.log('✅ Error details:', response.detail);
});
```

#### Invalid Account Type
```javascript
pm.test('Invalid Account Type Rejected', function () {
    pm.expect(pm.response.code).to.equal(422);
    const response = pm.response.json();
    
    // Verify error response structure
    pm.expect(response).to.have.property('detail');
    pm.expect(response.detail).to.be.an('array');
    pm.expect(response.detail.length).to.be.greaterThan(0);
    
    // Verify error message
    const typeError = response.detail.find(error => 
        error.msg && error.msg.includes('Invalid account type')
    );
    pm.expect(typeError).to.not.be.undefined;
    
    console.log('✅ Validation error caught:', typeError.msg);
    console.log('✅ Error details:', response.detail);
});
```

### 11. Delete Bank Account
```javascript
pm.test('Bank Account Deleted Successfully', function () {
    pm.expect(pm.response.code).to.equal(200);
    const response = pm.response.json();
    
    // Verify deletion response
    pm.expect(response).to.have.property('detail');
    pm.expect(response.detail).to.equal('Bank account deleted successfully');
    
    console.log('✅ Bank account deleted:', response.detail);
    console.log('✅ Deleted Account ID:', pm.collectionVariables.get('bank_account_id'));
});
```

### 12. Verify Deletion
```javascript
pm.test('Bank Account Not Found After Deletion', function () {
    pm.expect(pm.response.code).to.equal(404);
    const response = pm.response.json();
    
    // Verify error response
    pm.expect(response).to.have.property('detail');
    pm.expect(response.detail).to.equal('Bank account not found');
    
    console.log('✅ Bank account not found after deletion');
    console.log('✅ Soft delete working correctly');
    console.log('✅ Error message:', response.detail);
});
```

## 🧪 Test Data

### Valid Test Data
```json
{
  "institution_entity_id": "{{$randomUUID}}",
  "address_id": "{{$randomUUID}}",
  "account_holder_name": "John Doe",
  "bank_name": "Chase Bank",
  "account_type": "Checking",
  "routing_number": "021000021",
  "account_number": "1234567890",
  "status": "Active"
}
```

### Minimal Test Data
```json
{
  "institution_entity_id": "{{institution_entity_id}}",
  "account_holder_name": "Jane Smith",
  "bank_name": "Bank of America",
  "account_type": "Savings",
  "routing_number": "026009593",
  "account_number": "9876543210"
}
```

### Update Test Data
```json
{
  "account_holder_name": "John Doe Updated",
  "status": "Inactive"
}
```

## 🔍 Validation Rules

### Routing Number
- Must be exactly 9 digits
- Must be numeric only
- Example: "021000021" (Chase Bank)

### Account Number
- Must be 4-17 digits
- Must be numeric only
- Example: "1234567890"

### Account Type
- Must be one of: "Checking", "Savings", "Business", "Corporate", "Investment"
- Case-sensitive

### Auto-populated Fields
- `address_id` - Uses institution entity's address if not provided
- `status` - Defaults to "Active"
- `is_archived` - Defaults to false
- `account_token` - Automatically generated
- `created_date` - Automatically set
- `modified_by` - Uses current user ID

## 📊 Expected Results

### Success Responses
- **201** - Resource created successfully
- **200** - Resource retrieved/updated successfully

### Error Responses
- **404** - Resource not found
- **422** - Validation error
- **500** - Internal server error

### Response Fields
All responses include:
- `bank_account_id` - Unique identifier
- `institution_entity_id` - Parent entity reference
- `address_id` - Associated address
- `account_holder_name` - Account owner name
- `bank_name` - Financial institution name
- `account_type` - Type of account
- `routing_number` - Bank routing number
- `account_number` - Account number
- `account_token` - Secure token
- `is_archived` - Archive status
- `status` - Account status
- `created_date` - Creation timestamp
- `modified_by` - Last modifier ID

## 🚀 Running the Tests

1. **Import Collection** - Import the JSON file into Postman
2. **Set Environment** - Configure your environment variables
3. **Run Collection** - Execute the entire collection in order
4. **Review Results** - Check console logs and test results
5. **Verify Data** - Confirm data was created/updated/deleted correctly

## 🔧 Troubleshooting

### Common Issues
1. **Authentication Errors** - Verify `auth_token` is set correctly
2. **Validation Errors** - Check data format matches requirements
3. **Missing Dependencies** - Ensure institution entity exists first
4. **Database Errors** - Check server logs for detailed error messages

### Debug Tips
1. **Console Logs** - Check Postman console for detailed information
2. **Response Headers** - Verify content-type and authorization headers
3. **Request Body** - Ensure JSON is properly formatted
4. **Variable Values** - Confirm collection variables are set correctly

## 📈 Performance Notes

- **Response Time** - Most operations should complete in < 500ms
- **Concurrent Requests** - API supports multiple simultaneous requests
- **Data Volume** - Tested with up to 1000 bank accounts per entity
- **Memory Usage** - Efficient pagination for large result sets 