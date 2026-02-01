# Postman E2E API Calls Documentation

This document provides complete details for all API calls used in the end-to-end testing workflow, including URLs, request bodies with collection variables, and post-request scripts for data extraction.

## 🔧 Complete Collection Variables Reference

This E2E collection uses the following collection variables. All values are dynamically populated from API responses or set in pre-request scripts:

### Core System Variables
```javascript
{{baseUrl}} = http://localhost:8000
{{adminUsername}} = admin
{{adminPassword}} = admin123
{{billDate}} = [Auto-set to current date]
{{systemUserId}} = 11111111-1111-1111-1111-111111111111
```

### Entity & Institution Variables
```javascript
{{institutionEntityId}} = [Auto-populated from institution entity creation]
{{institutionId}} = [Auto-populated from institution creation]
{{entityBankAccountId}} = [Auto-populated from bank account creation]
{{entityBillId}} = [Auto-populated from bill generation]
```

### Restaurant & Product Variables
```javascript
{{restaurantId}} = 004db831-2699-480a-9718-4c55d76e998d
{{restaurantQrCodeId}} = [Auto-populated from QR code creation]
{{plateRestaurantId}} = [Auto-populated from plate creation]
{{plateId}} = [Auto-populated from plate creation]
{{plateProductId}} = [Auto-populated from plate creation]
{{plateSelectionId}} = [Auto-populated from plate selection]
{{productId}} = [Auto-populated from product creation]
{{qrQodeId}} = [Auto-populated from QR code creation]
```

### Credit & Currency Variables
```javascript
{{planCreditCurrencyId}} = [Auto-populated from credit currency creation]
{{planCreditCurrencyCode}} = [Auto-populated from credit currency creation]
{{planCredit}} = [Auto-populated from plan creation]
{{planId}} = [Auto-populated from plan creation]
{{planPrice}} = [Auto-populated from plan creation]
{{plateCreditCost}} = [Auto-populated from plate creation]
{{plateNoShowDiscount}} = [Auto-populated from plate creation]
```

### Payment & Transaction Variables
```javascript
{{paymentId}} = [Auto-populated from payment creation]
{{paymentMethodId}} = [Auto-populated from payment method creation]
{{clientBillId}} = [Auto-populated from client bill creation]
{{subscriptionId}} = [Auto-populated from subscription creation]
```

### User & Authentication Variables
```javascript
{{customerUserId}} = [Auto-populated from customer creation]
{{customerUsername}} = [Auto-populated from customer creation]
{{customerPassword}} = [Auto-populated from customer creation]
{{customerEmail}} = [Auto-populated from customer creation]
{{supplierUserId}} = [Auto-populated from supplier creation]
{{supplierUsername}} = [Auto-populated from supplier creation]
{{supplierPassword}} = [Auto-populated from supplier creation]
{{supplierEmail}} = [Auto-populated from supplier creation]
{{roleId}} = [Auto-populated from role creation]
```

### Address Variables
```javascript
{{customerAddressId}} = [Auto-populated from customer address creation]
{{supplierAddressId}} = [Auto-populated from supplier address creation]
```

### Fintech Integration Variables
```javascript
{{fintechLink}} = [Auto-populated from fintech link creation]
{{fintechLinkId}} = [Auto-populated from fintech link creation]
{{fintechLinkProvider}} = [Auto-populated from fintech link creation]
```

### Pickup & Order Variables
```javascript
{{pendingPickupId}} = [Auto-populated from pickup creation]
{{pendingRestaurantId}} = [Auto-populated from pickup creation]
```

### Authentication Token
```javascript
{{authToken}} = [Auto-populated from authentication response]
```

## 📋 Complete E2E API Call Sequence

### Phase 1: Admin Setup & System Configuration

### 1. POST Login Admin
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 2. POST Create Credit Currency
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 3. POST Create Subscription Plans
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 4. POST Create Plan Fintech Link
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 5. POST Register Supplier Institution
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 6. POST Register Supplier User
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 7. GET Logout Admin
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### Phase 2: Supplier Setup & Restaurant Registration

### 8. POST Login Supplier User
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 9. POST Register Supplier Address
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 10. POST Register Supplier Entity
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 11. POST Register Supplier Bank Account
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 12. POST Register Supplier Restaurant
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 13. POST Register Supplier Restaurant QR Code
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 14. POST Register Supplier Product
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 15. PUT Update Supplier Product
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 16. POST Register Supplier Plate
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 17. GET Logout Supplier User
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### Phase 3: Customer Registration & Setup

### 18. POST Register Customer User
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 19. POST Login Customer User
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 20. POST Register Customer Address
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 21. PUT Update Customer Address
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 22. POST Create Customer Subscription
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### Phase 4: Payment & Transaction Processing

### 23. POST Register Payment Method as Link
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 24. POST Fintech Link Transaction
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 25. POST Register Client Payment Attempt
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 26. PATCH Update Payment Attempt Status
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 27. GET Fetch Currency Country Code
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 28. POST Register Client Bill
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 29. POST Update Subscription Balance and Renewal
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### Phase 5: Plate Selection & Order Processing

### 30. GET List Plates for Customer
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 31. POST Register Plate Selection
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 32. GET List Active QR Codes
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 33. POST Post QR Code Scan
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 34. POST Confirm Delivery
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 35. GET Logout Customer User
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### Phase 6: Admin Billing & Payment Processing

### 36. POST Login Admin
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 37. POST Issue Bills
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 38. GET Get Bills
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 39. POST Institution Payment Attempt
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Body:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

### 40. GET Logout Admin
**URL:** `[TO BE FILLED]`
**Headers:** `[TO BE FILLED]`
**Pre-Request Script:** `[TO BE FILLED]`
**Post-Request Script:** `[TO BE FILLED]`

---

## 🔄 Complete E2E Workflow

### Pre-Request Script (Collection Level)
```javascript
// Set current date for bill generation
const today = new Date();
const billDate = today.toISOString().split('T')[0];
pm.collectionVariables.set("billDate", billDate);

// Set system user ID
pm.collectionVariables.set("systemUserId", "11111111-1111-1111-1111-111111111111");

// Set restaurant ID (update this if you have a different test restaurant)
pm.collectionVariables.set("restaurantId", "004db831-2699-480a-9718-4c55d76e998d");

console.log("🚀 Starting E2E test for date:", billDate);
console.log("🏪 Using restaurant ID:", pm.collectionVariables.get("restaurantId"));
```

### Post-Request Script (Collection Level)
```javascript
// Log completion status
if (pm.info.requestName === "Logout Admin") {
    console.log("🎉 E2E test completed!");
    console.log("Final bill ID:", pm.collectionVariables.get("entityBillId"));
}
```

## 🛠️ Troubleshooting

### Common Issues:

1. **"NO_BILLS_FOUND" Error**
   - Check if restaurant has positive balance
   - Verify bill date matches restaurant balance date
   - Ensure `DEV_OVERRIDE_DAY` is set if testing on weekends

2. **"Invalid protocol" Error**
   - Check URL format in Postman (should be `http://` not `post http:`)

3. **"422 Unprocessable Entity"**
   - Verify all collection variables are populated
   - Check JSON syntax in request body
   - Ensure UUIDs are properly quoted

4. **Authentication Issues**
   - Verify auth token is set in collection variables
   - Check if token has expired

### Debug Collection Variables:
```javascript
// Add this to any request's Pre-Request Script to debug
console.log("=== CURRENT COLLECTION VARIABLES ===");
console.log("Core System:");
console.log("  baseUrl:", pm.collectionVariables.get("baseUrl"));
console.log("  adminUsername:", pm.collectionVariables.get("adminUsername"));
console.log("  adminPassword:", pm.collectionVariables.get("adminPassword"));
console.log("  billDate:", pm.collectionVariables.get("billDate"));
console.log("  restaurantId:", pm.collectionVariables.get("restaurantId"));

console.log("Entity Variables:");
console.log("  institutionEntityId:", pm.collectionVariables.get("institutionEntityId"));
console.log("  institutionId:", pm.collectionVariables.get("institutionId"));
console.log("  entityBankAccountId:", pm.collectionVariables.get("entityBankAccountId"));
console.log("  planCreditCurrencyId:", pm.collectionVariables.get("planCreditCurrencyId"));
console.log("  planCreditCurrencyCode:", pm.collectionVariables.get("planCreditCurrencyCode"));
console.log("  entityBillId:", pm.collectionVariables.get("entityBillId"));

console.log("Authentication:");
console.log("  authToken:", pm.collectionVariables.get("authToken") ? "SET" : "NOT SET");
```

## 📝 Notes

- **All values use collection variables** - No hardcoded values in request bodies
- All IDs are dynamically populated from previous API calls
- The system automatically derives `currency_code` from `credit_currency_id`
- Bill generation uses the current date unless `DEV_OVERRIDE_DAY` is set
- Restaurant balance must exist before bill generation
- Payment attempts require a valid bill ID
- Collection variables are automatically set in pre-request scripts and post-request scripts
- Database rebuilds are safe - all dynamic data is re-populated from API responses

---

## 🔄 Batch Job Testing (Alternative Approach)

For testing the cron job functionality and batch processing, use these API calls instead of the one-off bill creation:

### Batch Job: Generate Daily Bills (Cron Simulation)
**POST** `{{baseUrl}}/institution-bills/generate-daily-bills?bill_date={{billDate}}`

**Headers:**
```
Authorization: Bearer {{authToken}}
```

**Body:** (Empty)

**Post-Request Script:**
```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    console.log("✅ Daily bills generated successfully");
    console.log("Statistics:", response.statistics);
    
    // Extract bill ID if bills were created
    if (response.statistics.bills_created > 0) {
        // Get the first bill ID from the response or make a separate call
        pm.collectionVariables.set("entityBillId", "BILL_GENERATED");
        console.log("✅ Bill ID set for payment attempt");
    } else {
        pm.collectionVariables.set("entityBillId", "NO_BILLS_FOUND");
        console.log("⚠️ No bills generated - check restaurant balances");
    }
} else {
    console.log("❌ Bill generation failed");
    pm.collectionVariables.set("entityBillId", "GENERATION_FAILED");
}
```

### When to Use Batch Jobs vs One-off:

**Use One-off Bill Creation (Steps 1-8 above) when:**
- Testing individual restaurant billing
- Debugging specific billing scenarios
- Manual bill creation for testing
- E2E testing with controlled data

**Use Batch Job Generation when:**
- Testing cron job functionality
- Simulating daily batch processing
- Testing multi-restaurant billing
- Validating weekend/holiday logic
- Performance testing with multiple restaurants

### Batch Job Testing Workflow:
1. Follow steps 1-5 (Authentication through Restaurant Balance)
2. **Replace step 6** with the batch job API call above
3. Continue with steps 7-8 (Get Bills and Payment Attempt)

---

*This documentation ensures your e2e tests can run consistently after database rebuilds by using collection variables for all dynamic data.*
