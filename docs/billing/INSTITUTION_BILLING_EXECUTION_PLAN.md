# 🏦 INSTITUTION BILLING SYSTEM - EXECUTION PLAN

## 📋 **REQUIREMENTS SUMMARY**

### **Updated Business Logic:**
1. **Order Placement** → Restaurant balance updated with **conservative estimate** (no-show discount applied)
2. **QR Scan (Customer Arrival)** → Balance adjusted **upward** to full amount (add back discount)
3. **End of Day** → Generate **institution bills** from final restaurant balances

### **Key Relationships:**
- `restaurant_info.institution_id` → `institution_info.institution_id`
- `institution_entity_info.institution_id` → `institution_info.institution_id`
- Daily bills aggregate restaurant balances per institution

---

## 🏗️ **IMPLEMENTATION STATUS**

### ✅ **COMPLETED FILES:**

#### **1. Models**
- ✅ `app/models/billing/institution_bill.py`
  - Complete CRUD model with institution relationship queries
  - Methods: `get_by_restaurant_and_period`, `get_by_institution_and_period`, `mark_paid`
  - Institution/entity ID lookup methods

#### **2. Schemas**  
- ✅ `app/schemas/billing/institution_bill.py`
  - Create, Update, Response schemas for API operations

#### **3. Services**
- ✅ `app/services/billing/__init__.py`
- ✅ `app/services/billing/institution_billing.py`
  - Complete billing service with daily bill generation
  - Methods: `generate_daily_bills`, `get_bills_by_institution`, `get_bill_summary`

#### **4. Routes**
- ✅ `app/routes/billing/institution_bill.py`
  - Complete REST API for institution bill management
  - Endpoints: CRUD operations, mark paid, generate daily bills, billing summary

#### **5. Updated Models**
- ✅ `app/models/restaurant_balance.py` - Enhanced with no-show discount support
- ✅ `app/models/restaurant_transaction.py` - New conservative balance update methods
- ✅ `app/routes/plate_selection.py` - Updated to use conservative balance updates

---

## 🔧 **REMAINING TASKS**

### **Critical Fixes Needed:**

#### **1. Fix Linter Errors** 
```bash
# app/models/restaurant_balance.py (Line 68)
# Fix indentation error in exception handling

# application.py (Lines 79-82) 
# Fix router registration indentation
```

#### **2. Complete Restaurant Transaction Updates**
```python
# app/models/restaurant_transaction.py
# Complete the update_balance_on_arrival method to calculate proper adjustment
```

#### **3. Register Institution Bill Routes**
```python
# application.py
# Properly register institution_bill_router with correct indentation
```

---

## 💰 **NEW FINANCIAL FLOW**

### **Order Placement:**
```python
# Conservative estimate (80% of full amount if 20% no-show discount)
conservative_amount = credits × credit_value × (1 - no_show_discount_rate)
RestaurantBalance.update_balance_for_transaction(..., no_show_discount=0.20)
```

### **Customer Arrival (QR Scan):**
```python
# Add back the discount amount
discount_amount = credits × credit_value × no_show_discount_rate
RestaurantBalance.update_balance_for_transaction(discount_amount, no_show_discount=None)
```

### **End of Day Bill Generation:**
```python
# Generate bills from final restaurant balances
InstitutionBillingService.generate_daily_bills(date.today(), system_user_id)
```

---

## 🚀 **API ENDPOINTS AVAILABLE**

### **Institution Bills:**
- `POST /institution-bills/` - Create bill
- `GET /institution-bills/` - List bills (with filters)
- `GET /institution-bills/{bill_id}` - Get specific bill
- `PUT /institution-bills/{bill_id}` - Update bill
- `POST /institution-bills/{bill_id}/mark-paid` - Mark as paid
- `POST /institution-bills/generate-daily-bills` - Generate daily bills
- `GET /institution-bills/summary/{institution_id}` - Get billing summary

---

## 📊 **EXAMPLE WORKFLOW**

### **Day 1 - Order Processing:**
```
8:00 AM - Customer places order (10 credits × $3.00 = $30.00)
        → Restaurant balance: +$24.00 (20% discount applied)
        
10:30 AM - Customer scans QR at restaurant  
         → Restaurant balance: +$6.00 (remaining 20%)
         → Total balance: $30.00 ✅
         
12:00 PM - Customer completes pickup
         → Status updated to "Complete"
```

### **End of Day - Bill Generation:**
```
11:59 PM - Daily bill generation runs
         → Query all restaurant balances
         → Group by institution_id
         → Create institution_bill_info records
         → Status: "Pending"
```

### **Day 2 - Payment Processing:**
```
9:00 AM - Institution pays bill
        → POST /institution-bills/{bill_id}/mark-paid
        → Status: "Paid"
        → Payment tracking complete
```

---

## 🔄 **TESTING STRATEGY**

### **Integration Tests:**
1. **Order → Balance Update** - Verify conservative amount
2. **QR Scan → Balance Adjustment** - Verify discount addition
3. **Bill Generation** - Verify end-of-day aggregation
4. **Institution Queries** - Verify restaurant→institution lookups

### **API Tests:**
1. **CRUD Operations** - All institution bill endpoints
2. **Filter Operations** - By institution, restaurant, date range
3. **Payment Workflow** - Mark paid functionality
4. **Daily Generation** - Automated bill creation

---

## 📈 **BUSINESS IMPACT**

### **For Restaurants:**
- ✅ **Immediate payment** - Conservative estimate on order placement
- ✅ **Full payment guarantee** - When customers actually show up
- ✅ **Fair no-show handling** - Reduced payment for no-shows

### **For Institutions:**
- ✅ **Automated billing** - Daily bill generation from restaurant balances
- ✅ **Transparent accounting** - Complete audit trail per restaurant
- ✅ **Flexible payment tracking** - Mark bills paid with payment references

### **For Platform:**
- ✅ **Accurate financials** - Real-time balance tracking
- ✅ **Automated operations** - End-of-day bill generation
- ✅ **Scalable architecture** - Handles multiple institutions/restaurants

---

## 🎯 **FINAL IMPLEMENTATION STEPS**

1. **Fix linter errors** in restaurant_balance.py and application.py
2. **Complete arrival balance adjustment** in restaurant_transaction.py  
3. **Test conservative balance updates** on order placement
4. **Test QR scan balance adjustments** on customer arrival
5. **Test end-of-day bill generation** with sample data
6. **Verify institution→restaurant relationships** in database
7. **Run integration tests** for full workflow

---

## 🏆 **MVP COMPLETION**

With this implementation, your MVP will have:

- ✅ **Real-time restaurant balance tracking** with conservative estimates
- ✅ **Fair payment model** based on actual customer behavior  
- ✅ **Automated institution billing** from restaurant balances
- ✅ **Complete audit trail** for all financial transactions
- ✅ **Scalable architecture** for multiple institutions and restaurants

The system now provides **sophisticated financial management** that protects all parties while ensuring accurate, automated billing! 🎉 