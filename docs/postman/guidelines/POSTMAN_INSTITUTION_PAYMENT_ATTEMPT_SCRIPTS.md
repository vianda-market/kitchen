# POSTMAN_INSTITUTION_PAYMENT_ATTEMPT_SCRIPTS.md

## Collection Variables

Set these variables in your Postman collection:

```
baseUrl: http://localhost:8000
authToken: {{authToken}}
institutionEntityId: {{institutionEntityId}}
entityBankAccountId: {{entityBankAccountId}}
entityBillId: {{entityBillId}}
planCreditCurrencyId: {{planCreditCurrencyId}}
paymentAttemptId: {{paymentAttemptId}}
```

## Authentication Setup

### 1. Login to Get Auth Token
**Request:** `POST {{baseUrl}}/auth/token`
**Headers:** `Content-Type: application/x-www-form-urlencoded`
**Body (x-www-form-urlencoded):**
```
username: admin
password: admin_password
```

**Post-request Script:**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    pm.collectionVariables.set("authToken", response.access_token);
    console.log("Auth token set:", response.access_token);
} else {
    console.error("Failed to get auth token:", pm.response.text());
}
```

## Institution Bill Generation

### 1. Generate Daily Bills
**Request:** `POST {{baseUrl}}/institution-bills/generate-daily-bills?bill_date=2025-08-16`
**Headers:** 
```
Content-Type: application/json
Authorization: Bearer {{authToken}}
```

**Post-request Script:**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    console.log("Daily bills generated successfully:", response.message);
    console.log("Date:", response.date);
    console.log("Statistics:", response.statistics);
    
    // Store the bill date for the follow-up request
    pm.collectionVariables.set("billDate", response.date);
    console.log("Bill date stored:", response.date);
    
} else {
    console.error("Failed to generate daily bills:", pm.response.text());
}
```

### 2. Get Bills by Institution (Follow-up to get bill IDs)
**Request:** `GET {{baseUrl}}/institution-bills/?institution_id={{institutionEntityId}}&start_date={{billDate}}&end_date={{billDate}}`
**Headers:** `Authorization: Bearer {{authToken}}`

**Post-request Script:**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    console.log(`Retrieved ${response.length} bills for date ${pm.collectionVariables.get("billDate")}`);
    
    if (response.length > 0) {
        // Get the first bill ID (you can modify this logic if you need a specific bill)
        const firstBill = response[0];
        pm.collectionVariables.set("entityBillId", firstBill.institution_bill_id);
        console.log("✅ Bill ID set:", firstBill.institution_bill_id);
        console.log("Bill details:", {
            amount: firstBill.amount,
            currency: firstBill.currency_code,
            status: firstBill.status,
            period: `${firstBill.period_start} to ${firstBill.period_end}`
        });
    } else {
        console.log("⚠️ No bills found for the specified date");
        pm.collectionVariables.set("entityBillId", "NO_BILLS_FOUND");
    }
} else {
    console.error("Failed to retrieve bills:", pm.response.text());
}
```

## Institution Payment Attempt API Endpoints

### 1. Create Payment Attempt (Full)
**Request:** `POST {{baseUrl}}/institution-payment-attempts/`
**Headers:** 
```
Content-Type: application/json
Authorization: Bearer {{authToken}}
```
**Body (raw JSON):**
```json
{
    "institution_entity_id": "{{institutionEntityId}}",
    "bank_account_id": "{{entityBankAccountId}}",
    "institution_bill_id": "{{entityBillId}}",
    "credit_currency_id": "{{planCreditCurrencyId}}",
    "amount": 150.75,
    "currency_code": null,
    "transaction_result": null,
    "external_transaction_id": null
}
```

**Post-request Script:**
```javascript
if (pm.response.code === 201) {
    const response = pm.response.json();
    pm.collectionVariables.set("paymentAttemptId", response.payment_id);
    console.log("Payment attempt created:", response.payment_id);
    console.log("Status:", response.status);
} else {
    console.error("Failed to create payment attempt:", pm.response.text());
}
```

### 2. Create Payment Attempt (Minimal) - FIXED
**Request:** `POST {{baseUrl}}/institution-payment-attempts/minimal`
**Headers:** 
```
Content-Type: application/json
Authorization: Bearer {{authToken}}
```
**Body (raw JSON):**
```json
{
    "institution_entity_id": "{{institutionEntityId}}",
    "bank_account_id": "{{entityBankAccountId}}",
    "institution_bill_id": "{{entityBillId}}",
    "credit_currency_id": "{{planCreditCurrencyId}}",
    "amount": 200.00
}
```

**Post-request Script:**
```javascript
if (pm.response.code === 201) {
    const response = pm.response.json();
    pm.collectionVariables.set("paymentAttemptId", response.payment_id);
    console.log("Minimal payment attempt created:", response.payment_id);
    console.log("Status:", response.status);
    console.log("Amount:", response.amount, response.currency_code);
} else {
    console.error("Failed to create minimal payment attempt:", pm.response.text());
}
```

### 3. Get Payment Attempt by ID
**Request:** `GET {{baseUrl}}/institution-payment-attempts/{{paymentAttemptId}}`
**Headers:** `Authorization: Bearer {{authToken}}`

**Post-request Script:**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    console.log("Payment attempt retrieved:", response.payment_id);
    console.log("Amount:", response.amount, response.currency_code);
    console.log("Status:", response.status);
} else {
    console.error("Failed to retrieve payment attempt:", pm.response.text());
}
```

### 4. Get All Payment Attempts
**Request:** `GET {{baseUrl}}/institution-payment-attempts/`
**Headers:** `Authorization: Bearer {{authToken}}`

**Query Parameters (optional):**
- `include_archived=true` - Include archived attempts
- `institution_entity_id={{institutionEntityId}}` - Filter by institution entity
- `institution_bill_id={{entityBillId}}` - Filter by institution bill

**Post-request Script:**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    console.log(`Retrieved ${response.length} payment attempts`);
    response.forEach((attempt, index) => {
        console.log(`${index + 1}. ID: ${attempt.payment_id}, Amount: ${attempt.amount} ${attempt.currency_code}, Status: ${attempt.status}`);
    });
} else {
    console.error("Failed to retrieve payment attempts:", pm.response.text());
}
```

### 5. Get Pending Payment Attempts
**Request:** `GET {{baseUrl}}/institution-payment-attempts/pending/{{institutionEntityId}}`
**Headers:** `Authorization: Bearer {{authToken}}`

**Post-request Script:**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    console.log(`Retrieved ${response.length} pending payment attempts`);
    response.forEach((attempt, index) => {
        console.log(`${index + 1}. ID: ${attempt.payment_id}, Amount: ${attempt.amount} ${attempt.currency_code}`);
    });
} else {
    console.error("Failed to retrieve pending payment attempts:", pm.response.text());
}
```

### 6. Mark Payment Attempt as Complete
**Request:** `POST {{baseUrl}}/institution-payment-attempts/{{paymentAttemptId}}/complete`
**Headers:** 
```
Content-Type: application/json
Authorization: Bearer {{authToken}}
```
**Body (raw JSON):**
```json
{
    "transaction_result": "Payment Successful",
    "external_transaction_id": "ext_txn_12345"
}
```

**Post-request Script:**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    console.log("Payment attempt marked as complete:", response.payment_id);
    console.log("New status:", response.status);
    console.log("Transaction result:", response.transaction_result);
    console.log("Resolution date:", response.resolution_date);
} else {
    console.error("Failed to mark payment attempt as complete:", pm.response.text());
}
```

### 7. Mark Payment Attempt as Failed
**Request:** `POST {{baseUrl}}/institution-payment-attempts/{{paymentAttemptId}}/failed`
**Headers:** 
```
Content-Type: application/json
Authorization: Bearer {{authToken}}
```
**Body (raw JSON):**
```json
{
    "transaction_result": "Insufficient Funds",
    "external_transaction_id": "ext_txn_12345"
}
```

**Post-request Script:**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    console.log("Payment attempt marked as failed:", response.payment_id);
    console.log("New status:", response.status);
    console.log("Transaction result:", response.transaction_result);
    console.log("Resolution date:", response.resolution_date);
} else {
    console.error("Failed to mark payment attempt as failed:", pm.response.text());
}
```

### 8. Update Payment Attempt
**Request:** `PUT {{baseUrl}}/institution-payment-attempts/{{paymentAttemptId}}`
**Headers:** 
```
Content-Type: application/json
Authorization: Bearer {{authToken}}
```
**Body (raw JSON):**
```json
{
    "transaction_result": "Updated Result",
    "external_transaction_id": "ext_txn_updated"
}
```

**Post-request Script:**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    console.log("Payment attempt updated:", response.payment_id);
    console.log("Transaction result:", response.transaction_result);
    console.log("External transaction ID:", response.external_transaction_id);
} else {
    console.error("Failed to update payment attempt:", pm.response.text());
}
```

### 9. Get Payment Attempt Summary
**Request:** `GET {{baseUrl}}/institution-payment-attempts/summary/{{institutionEntityId}}`
**Headers:** `Authorization: Bearer {{authToken}}`

**Post-request Script:**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    console.log("Payment attempt summary retrieved");
    response.forEach((attempt, index) => {
        console.log(`${index + 1}. ID: ${attempt.payment_id}, Amount: ${attempt.amount} ${attempt.currency_code}, Status: ${attempt.status}`);
    });
} else {
    console.error("Failed to retrieve payment attempt summary:", pm.response.text());
}
```

### 10. Delete Payment Attempt
**Request:** `DELETE {{baseUrl}}/institution-payment-attempts/{{paymentAttemptId}}`
**Headers:** `Authorization: Bearer {{authToken}}`

**Post-request Script:**
```javascript
if (pm.response.code === 200) {
    console.log("Payment attempt deleted successfully");
} else {
    console.error("Failed to delete payment attempt:", pm.response.text());
}
```

### 11. Undelete Payment Attempt
**Request:** `POST {{baseUrl}}/institution-payment-attempts/{{paymentAttemptId}}/undelete`
**Headers:** `Authorization: Bearer {{authToken}}`

**Post-request Script:**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    console.log("Payment attempt undeleted:", response.payment_id);
    console.log("Status:", response.status);
} else {
    console.error("Failed to undelete payment attempt:", pm.response.text());
}
```

## Complete Workflow Example

### Step 1: Generate Daily Bills
```bash
POST {{baseUrl}}/institution-bills/generate-daily-bills?bill_date=2025-08-16
```

### Step 2: Get Bill IDs (Automated)
```bash
GET {{baseUrl}}/institution-bills/?institution_id={{institutionEntityId}}&start_date={{billDate}}&end_date={{billDate}}
```

### Step 3: Create Payment Attempt
```bash
POST {{baseUrl}}/institution-payment-attempts/minimal
```

## Important Notes

### Collection Variable Requirements:
1. **institutionEntityId** - Must be set to a valid institution entity ID
2. **entityBankAccountId** - Must be set to a valid bank account ID for the institution entity
3. **entityBillId** - Automatically populated from bill generation workflow
4. **planCreditCurrencyId** - Must be set to a valid credit currency ID
5. **currency_code** - Removed from request body (system will pull from credit currency ID)

### Workflow:
1. **Generate Daily Bills** - Creates institution bills for a specific date
2. **Get Bill IDs** - Automatically retrieves the created bill IDs
3. **Create Payment Attempts** - Uses the retrieved bill IDs to create payment attempts

### Troubleshooting:
- If you get 422 errors, check that all collection variables are properly set
- Ensure the referenced entities (institution entity, bank account, bill, credit currency) exist in the database
- The system will automatically pull the currency code from the credit currency ID
- Make sure to run the bill generation and bill retrieval steps before creating payment attempts 