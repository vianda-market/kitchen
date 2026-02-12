# Bank Account Collection Variable Fix

**Date**: 2026-02-05  
**Issue**: Delete Bank Account call failing with "Bank account not found"  
**Status**: ✅ **FIXED**

---

## 🐛 **Problem**

The "15. Delete Bank Account" request in `INSTITUTION_BANK_ACCOUNT_POSTMAN_COLLECTION.json` was failing with:

```json
{
  "detail": "Bank account not found"
}
```

---

## 🔍 **Root Cause**

The **"5. Create Bank Account (Minimal)"** test script was **not storing** the `bank_account_id` in collection variables after creating a bank account.

### Before (Broken):
```javascript
pm.test('Minimal Bank Account Created Successfully', function () {
    pm.expect(pm.response.code).to.equal(201);
    const response = pm.response.json();
    pm.expect(response).to.have.property('bank_account_id');
    
    // ❌ Only logging, NOT storing the ID
    console.log('Created Minimal Bank Account ID:', response.bank_account_id);
});
```

### Issue:
- If users ran request #5 (Minimal) instead of #1 (Full Details), the `bank_account_id` variable was never set
- Later requests (GET, PUT, DELETE, Validate) that depend on `{{bank_account_id}}` would fail with "not found"

---

## ✅ **Solution**

Added the missing line to store the `bank_account_id` in collection variables:

### After (Fixed):
```javascript
pm.test('Minimal Bank Account Created Successfully', function () {
    pm.expect(pm.response.code).to.equal(201);
    const response = pm.response.json();
    pm.expect(response).to.have.property('bank_account_id');
    
    // ✅ Store the bank_account_id for later use
    pm.collectionVariables.set('bank_account_id', response.bank_account_id);
    
    console.log('Created Minimal Bank Account ID:', response.bank_account_id);
    console.log('Auto-populated Address ID:', response.address_id);
});
```

---

## 📊 **Affected Requests**

The following requests depend on `{{bank_account_id}}` being set correctly:

1. ✅ **1. Create Bank Account (Full Details)** - Already storing ID correctly
2. ✅ **5. Create Bank Account (Minimal)** - **NOW FIXED** to store ID
3. **6. Get Bank Account by ID** - Uses `{{bank_account_id}}`
4. **7. Update Bank Account** - Uses `{{bank_account_id}}`
5. **10. Validate Bank Account** - Uses `{{bank_account_id}}`
6. **15. Delete Bank Account** - Uses `{{bank_account_id}}`
7. **16. Verify Deletion** - Uses `{{bank_account_id}}`

---

## 🧪 **Testing**

Run the collection in order:

1. **Setup** (requests 1-3): Login, Create Institution Entity
2. **Create** (request 5): "Create Bank Account (Minimal)" 
   - ✅ Should now store `bank_account_id` in collection variables
3. **Operations** (requests 6-14): GET, UPDATE, LIST, VALIDATE
   - ✅ Should all work with the stored `bank_account_id`
4. **Delete** (request 15): "Delete Bank Account"
   - ✅ Should now find and delete the account successfully
5. **Verify** (request 16): "Verify Deletion"
   - ✅ Should return 404 (soft delete working)

---

## 📝 **Best Practice**

**Always store entity IDs in collection variables** after CREATE operations:

```javascript
pm.test('Entity Created Successfully', function () {
    pm.expect(pm.response.code).to.equal(201);
    const response = pm.response.json();
    
    // ✅ ALWAYS store the ID for downstream requests
    pm.collectionVariables.set('entity_id', response.entity_id);
    
    console.log('Created Entity ID:', response.entity_id);
});
```

This ensures:
- ✅ Downstream requests can reference the created entity
- ✅ Collection can run end-to-end without manual intervention
- ✅ Tests are reproducible and self-contained

---

## 🎯 **Related Files**

- `docs/postman/INSTITUTION_BANK_ACCOUNT_POSTMAN_COLLECTION.json` - Fixed collection
- `docs/postman/E2E Plate Selection.postman_collection.json` - Uses `entityBankAccountId` (separate variable, working correctly)

---

**Status**: 🎉 **Ready for testing!**
