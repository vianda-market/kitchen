# POSTMAN_INSTITUTION_PAYMENT_ATTEMPT_SCRIPTS.md

## Removed endpoints – supplier payment via pipeline only

The following endpoints have been **removed**. Supplier (institution) payment is now via the **settlement → bill → payout** pipeline only:

**Institution bills:**
- `POST /api/v1/institution-bills/{bill_id}/record-payment` — removed
- `POST /api/v1/institution-bills/{bill_id}/mark-paid` — removed

**Institution payment attempts** (entire API removed; used `bank_account_id`):
- `POST /api/v1/institution-payment-attempts/` — removed
- `POST /api/v1/institution-payment-attempts/minimal` — removed
- All other institution-payment-attempts CRUD endpoints — removed

See **docs/api/internal/SUPPLIER_INSTITUTION_PAYMENT.md** for the atomic flow: Phase 1 settlements → Phase 2 bills → tax doc → payout → mark_paid. The E2E collection verifies bills via **GET /api/v1/institution-bills/{{entityBillId}}**.

---

## Collection Variables (for institution bills and pipeline)

```
baseUrl: http://localhost:8000
authToken: {{authToken}}
institutionEntityId: {{institutionEntityId}}
entityBillId: {{entityBillId}}
planCreditCurrencyId: {{planCreditCurrencyId}}
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

## Run Settlement Pipeline (replaces manual payment attempts)

**Request:** `POST {{baseUrl}}/api/v1/institution-bills/run-settlement-pipeline?bill_date=YYYY-MM-DD&country_code=XX`
**Headers:** `Authorization: Bearer {{authToken}}`

This runs Phase 1 (settlements) → Phase 2 (bills) → tax doc → payout → mark_paid. No manual payment attempts or bank_account_id.

## Institution Bill Generation (legacy – pipeline preferred)

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

## Complete Workflow (pipeline-based)

1. **Run settlement pipeline:** `POST {{baseUrl}}/api/v1/institution-bills/run-settlement-pipeline?bill_date=YYYY-MM-DD`
2. **Get bills (verify):** `GET {{baseUrl}}/institution-bills/?institution_id={{institutionEntityId}}&start_date=...&end_date=...`

### Collection variable requirements
- **institutionEntityId** – valid institution entity ID
- **entityBillId** – from bill generation or GET bills