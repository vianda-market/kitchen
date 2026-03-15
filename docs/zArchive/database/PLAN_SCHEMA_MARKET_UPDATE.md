# Plan Schema Market Update

**Date**: 2026-02-04  
**Status**: ✅ Complete

---

## 🎯 **Issue**

When creating a subscription plan via Postman, the API returned:
```json
{
    "detail": "Database error during insert into plan_info: null value in column \"market_id\" of relation \"plan_info\" violates not-null constraint"
}
```

**Root Cause**: The Pydantic schemas for plans (`PlanCreateSchema`, `PlanUpdateSchema`, `PlanResponseSchema`, `PlanEnrichedResponseSchema`) were missing the `market_id` field, even though the database table `plan_info` requires it.

---

## 🔧 **Fix Applied**

Updated all plan-related schemas in `app/schemas/consolidated_schemas.py` to include `market_id`:

### **1. PlanCreateSchema** (Required field)
```python
class PlanCreateSchema(BaseModel):
    """Schema for creating a new plan"""
    market_id: UUID = Field(..., description="Market (country) this plan belongs to")
    credit_currency_id: UUID
    name: str = Field(..., max_length=100)
    credit: int = Field(..., gt=0)
    price: float = Field(..., ge=0)
    rollover: Optional[bool] = True
    rollover_cap: Optional[Decimal] = None
```

### **2. PlanUpdateSchema** (Optional field)
```python
class PlanUpdateSchema(BaseModel):
    """Schema for updating plan information"""
    market_id: Optional[UUID] = Field(None, description="Market (country) this plan belongs to")
    credit_currency_id: Optional[UUID] = None
    # ... other fields
```

### **3. PlanResponseSchema** (Return field)
```python
class PlanResponseSchema(BaseModel):
    """Schema for plan response data"""
    plan_id: UUID
    market_id: UUID  # Added
    credit_currency_id: UUID
    name: str
    # ... other fields
```

### **4. PlanEnrichedResponseSchema** (Return field)
```python
class PlanEnrichedResponseSchema(BaseModel):
    """Schema for enriched plan response data with currency name and code"""
    plan_id: UUID
    market_id: UUID  # Added
    credit_currency_id: UUID
    currency_name: str
    currency_code: str
    # ... other fields
```

---

## ✅ **Verification**

- ✅ Application imports successfully
- ✅ Schemas now match the database table structure
- ✅ `market_id` is required when creating plans
- ✅ `market_id` is returned in plan responses

---

## 🚀 **Next Steps**

1. **Restart your server**:
   ```bash
   cd /Users/cdeachaval/Desktop/local/kitchen
   source venv/bin/activate
   python3 application.py
   ```

2. **Test in Postman**:
   - Run "List Markets" to fetch available markets
   - Run "Create Subscription Plans" - should now work correctly!

---

## 📊 **Expected Postman Flow**

1. **List Markets**: `GET /api/v1/markets/`
   - Returns list of markets
   - Stores `planMarketId` (e.g., Argentina's UUID)

2. **Create Credit Currency**: `POST /api/v1/credit-currencies/`
   - Creates or fetches currency
   - Stores `planCreditCurrencyId`

3. **Create Subscription Plans**: `POST /api/v1/plans/`
   ```json
   {
     "market_id": "11111111-1111-1111-1111-111111111111",  // From step 1
     "credit_currency_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",  // From step 2
     "name": "Entry Level",
     "credit": 5,
     "price": 160000.00
   }
   ```
   - ✅ Should now create successfully!

---

## 📝 **Files Modified**

- `app/schemas/consolidated_schemas.py` - Added `market_id` to plan schemas

---

**Status**: Ready to test! 🎉
