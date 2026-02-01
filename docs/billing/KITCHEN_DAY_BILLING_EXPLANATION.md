# 🍽️ Kitchen Day-Aware Billing System

## 🔍 **How Restaurant Balances → Institution Bills Works**

### **1. Data Flow Architecture:**
```
restaurant_balance_info → daily billing cron → institution_bill_info
```

### **2. Data Source: `restaurant_balance_info` Table**
The system scans this table to find restaurants with positive balances:
- **`restaurant_id`** - Which restaurant has money to collect
- **`balance`** - Current balance amount (e.g., $11,200.00)
- **`transaction_count`** - Number of transactions for the day
- **`currency_code`** - Currency (ARS, USD, etc.)
- **`institution_id`** - Which institution owns the restaurant

### **3. Billing Logic:**
1. **Scans ALL restaurants** with positive balances
2. **Creates bills for the specified date**
3. **Links to institution entities** for proper billing
4. **Tracks billing periods** based on kitchen day closure

---

## 🎯 **Kitchen Day-Aware Billing (NEW!)**

### **Problem with Old System:**
- ❌ Bills generated at **midnight UTC** (00:00)
- ❌ **Ignores kitchen day closure timing**
- ❌ Restaurant might still be serving customers

### **Solution: Kitchen Day Closure Timing**
- ✅ Bills generated when **kitchen day closes**
- ✅ **Configurable closure hours** per day
- ✅ **Real-time billing triggers** available

---

## ⏰ **Kitchen Day Configuration**

### **Default Closure Hours:**
```python
KITCHEN_DAY_CLOSURE_HOURS = {
    'Monday': 22,    # 10:00 PM
    'Tuesday': 22,   # 10:00 PM  
    'Wednesday': 22, # 10:00 PM
    'Thursday': 22,  # 10:00 PM
    'Friday': 22,    # 10:00 PM
    'Saturday': 18,  # 6:00 PM (weekend)
    'Sunday': 18     # 6:00 PM (weekend)
}
```

### **Billing Periods:**
- **Start**: Beginning of the day (00:00)
- **End**: Kitchen closure time (e.g., 18:00 for Saturday)
- **Example**: Saturday 2025-08-16: 00:00 to 18:00 UTC

---

## 🚀 **Two Billing Modes**

### **1. Daily Billing (Traditional)**
```bash
# Run daily billing for a specific date
python -c "from app.services.cron.billing_events import run_daily_billing; from datetime import date; result = run_daily_billing(date.today())"
```

**Use Case**: Manual billing, historical billing, batch processing

### **2. Kitchen Day Closure Billing (NEW!)**
```bash
# Real-time billing when kitchen closes
python -c "from app.services.cron.billing_events import run_kitchen_day_closure_billing"
```

**Use Case**: Automated real-time billing, immediate collection

---

## 📊 **Real-World Example**

### **Scenario: Saturday, August 16, 2025**
1. **Kitchen Day**: Saturday
2. **Closure Time**: 6:00 PM UTC
3. **Billing Period**: 00:00 to 18:00 UTC
4. **Restaurant Balance**: $11,200.00 ARS
5. **Result**: Institution bill created for $11,200.00

### **What Happens:**
```
08:36 AM - Daily billing runs
├── Detects Saturday kitchen day
├── Sets period: 00:00 to 18:00 UTC
├── Finds restaurant with $11,200.00 balance
├── Creates institution bill
└── Bill period: 2025-08-16 00:00 to 18:00 UTC
```

---

## 🔧 **Cron Job Setup**

### **Option 1: Daily Billing (Traditional)**
```bash
# Add to crontab (crontab -e)
# Daily billing at 1:00 AM UTC
0 1 * * * cd /path/to/kitchen && /path/to/venv/bin/python -c "from app.services.cron.billing_events import daily_billing_entry; daily_billing_entry()" >> /var/log/kitchen/billing.log 2>&1
```

### **Option 2: Kitchen Day Closure Billing (Recommended)**
```bash
# Add to crontab (crontab -e)
# Kitchen closure billing - every 5 minutes
*/5 * * * * cd /path/to/kitchen && /path/to/venv/bin/python -c "from app.services.cron.billing_events import kitchen_day_closure_billing_entry; kitchen_day_closure_billing_entry()" >> /var/log/kitchen/kitchen_closure_billing.log 2>&1
```

---

## 🎯 **When Bills Are Generated**

### **Automatic Triggers:**
1. **✅ Kitchen Day Closure** - When kitchen closes (e.g., 6 PM Saturday)
2. **✅ Daily Cron Job** - At specified time (e.g., 1 AM daily)
3. **✅ Manual API Call** - When you call the endpoint

### **Smart Timing:**
- **Not before closure**: System checks if it's time to bill
- **Within 5 minutes after closure**: Billing window opens
- **Prevents duplicate bills**: Checks existing bills for the period

---

## 🔍 **System Status Methods**

### **Check Current Kitchen Day:**
```python
from app.services.billing.institution_billing import InstitutionBillingService

# Get current kitchen day
current_day = InstitutionBillingService.get_current_kitchen_day()
print(f"Today is: {current_day}")

# Check if kitchen is active
is_active = InstitutionBillingService.is_kitchen_day_active("Saturday")
print(f"Saturday kitchen active: {is_active}")

# Check if it's time to bill
should_bill = InstitutionBillingService.should_generate_bills_now()
print(f"Should bill now: {should_bill}")
```

---

## 📈 **Benefits of New System**

### **For Restaurants:**
- ✅ **Accurate billing periods** aligned with business hours
- ✅ **No premature billing** before kitchen closes
- ✅ **Real-time collection** when day ends

### **For Institutions:**
- ✅ **Timely revenue collection** at kitchen closure
- ✅ **Accurate daily reporting** based on actual business hours
- ✅ **Flexible timing** per day of week

### **For Operations:**
- ✅ **Automated billing** without manual intervention
- ✅ **Configurable closure times** per day
- ✅ **Audit trail** of billing periods and amounts

---

## 🧪 **Testing the System**

### **Test Daily Billing:**
```bash
python -c "from app.services.cron.billing_events import run_daily_billing; from datetime import date; result = run_daily_billing(date.today()); print('Daily billing:', result['bills_created'], 'bills, Kitchen day:', result['kitchen_day'])"
```

### **Test Kitchen Closure Billing:**
```bash
python -c "from app.services.cron.billing_events import run_kitchen_day_closure_billing; result = run_kitchen_day_closure_billing(); print('Kitchen closure billing:', result['bills_created'], 'bills')"
```

### **Test Commands:**
```bash
# Available commands
python app/services/cron/billing_events.py daily
python app/services/cron/billing_events.py kitchen_closure
python app/services/cron/billing_events.py dashboard
```

---

## 🎉 **Summary**

**Your billing system now:**
1. **✅ Scans restaurant balances** from `institution_balance_info`
2. **✅ Bills when kitchen days close** (not at midnight)
3. **✅ Supports real-time billing** triggers
4. **✅ Configurable closure times** per day
5. **✅ Prevents duplicate billing** for same periods
6. **✅ Uses bot_chef user** for automated operations

**The system automatically creates `institution_bill_info` records when kitchen days close, ensuring accurate and timely billing based on actual business hours! 🚀** 