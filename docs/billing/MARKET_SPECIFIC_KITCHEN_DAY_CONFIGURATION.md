# 🌍 Market-Specific Kitchen Day Configuration

## 🎯 **Your Requirements Implemented**

### **Argentina (UTC-3):**
- ✅ **Kitchen closes**: 2:30 PM local = 5:30 PM UTC
- ✅ **Billing runs**: 4:00 PM local = 7:00 PM UTC  
- ✅ **Reservations open**: 5:00 PM local = 8:00 PM UTC

### **Peru (UTC-5):**
- ✅ **Kitchen closes**: 2:30 PM local = 7:30 PM UTC
- ✅ **Billing runs**: 4:00 PM local = 9:00 PM UTC
- ✅ **Reservations open**: 5:00 PM local = 10:00 PM UTC

---

## 🔧 **Where Kitchen Day Configuration Lives**

### **File Location:**
```
app/config/market_config.py
```

### **Configuration Structure:**
```python
MARKETS = {
    "AR": MarketKitchenConfig(
        market_id="AR",
        market_name="Argentina",
        country_code="AR",
        timezone="America/Argentina/Buenos_Aires",
        kitchen_day_config={
            "Monday": {
                "kitchen_close": time(14, 30),      # 2:30 PM local
                "billing_run": time(16, 0),         # 4:00 PM local
                "reservations_open": time(17, 0),   # 5:00 PM local
                "enabled": True
            },
            # ... other days
        }
    ),
    "PE": MarketKitchenConfig(...)
}
```

---

## ⏰ **Timing Configuration (Local Time)**

### **Argentina (UTC-3):**
| Day | Kitchen Close | Billing Run | Reservations Open | Status |
|-----|---------------|-------------|-------------------|---------|
| Monday | 2:30 PM | 4:00 PM | 5:00 PM | ✅ Enabled |
| Tuesday | 2:30 PM | 4:00 PM | 5:00 PM | ✅ Enabled |
| Wednesday | 2:30 PM | 4:00 PM | 5:00 PM | ✅ Enabled |
| Thursday | 2:30 PM | 4:00 PM | 5:00 PM | ✅ Enabled |
| Friday | 2:30 PM | 4:00 PM | 5:00 PM | ✅ Enabled |
| Saturday | 2:30 PM | 4:00 PM | 5:00 PM | ✅ Enabled |
| Sunday | 2:30 PM | 4:00 PM | 5:00 PM | ❌ Disabled |

### **Peru (UTC-5):**
| Day | Kitchen Close | Billing Run | Reservations Open | Status |
|-----|---------------|-------------|-------------------|---------|
| Monday | 2:30 PM | 4:00 PM | 5:00 PM | ✅ Enabled |
| Tuesday | 2:30 PM | 4:00 PM | 5:00 PM | ✅ Enabled |
| Wednesday | 2:30 PM | 4:00 PM | 5:00 PM | ✅ Enabled |
| Thursday | 2:30 PM | 4:00 PM | 5:00 PM | ✅ Enabled |
| Friday | 2:30 PM | 4:00 PM | 5:00 PM | ✅ Enabled |
| Saturday | 2:30 PM | 4:00 PM | 5:00 PM | ✅ Enabled |
| Sunday | 2:30 PM | 4:00 PM | 5:00 PM | ❌ Disabled |

---

## 🌐 **Timezone Conversion Examples**

### **Argentina (UTC-3) - Saturday, August 16, 2025:**
```
Local Time (Argentina): 2:30 PM
UTC Time: 5:30 PM
Billing Period: 00:00 UTC to 17:30 UTC
```

### **Peru (UTC-5) - Saturday, August 16, 2025:**
```
Local Time (Peru): 2:30 PM  
UTC Time: 7:30 PM
Billing Period: 00:00 UTC to 19:30 UTC
```

---

## 🚀 **How to Use Location-Based Billing**

Billing and kitchen start promotion use **location_id** (timezone-region), not country_code. Single-timezone markets (AR, PE) use country as location; US is split by timezone (US-Eastern, US-Central, US-Mountain, US-Pacific).

### **1. Single Location Billing:**
```python
# Argentina (single location)
from app.services.cron.billing_events import multi_market_billing_entry
result = multi_market_billing_entry(location_id="AR")

# US-Pacific (LA, etc.)
result = multi_market_billing_entry(location_id="US-Pacific")
```

### **2. Multi-Location Billing (Recommended):**
```python
from app.services.cron.billing_events import multi_market_billing_entry
result = multi_market_billing_entry()
# Automatically processes all locations: AR, PE, US-Eastern, US-Central, US-Mountain, US-Pacific
```

### **3. Command Line:**
```bash
# All locations
python app/services/cron/billing_events.py multi_market

# Single location
python app/services/cron/billing_events.py multi_market AR
python app/services/cron/billing_events.py multi_market US-Pacific
```

---

## 🔧 **Cron Job Setup for Multiple Markets**

### **Option 1: Multi-Location Cron (Recommended)**
```bash
# Add to crontab (crontab -e)
# Run every 5 minutes - automatically handles all locations (AR, PE, US-Eastern, US-Central, US-Mountain, US-Pacific)
*/5 * * * * cd /path/to/kitchen && /path/to/venv/bin/python -c "from app.services.cron.billing_events import multi_market_billing_entry; multi_market_billing_entry()" >> /var/log/kitchen/multi_market_billing.log 2>&1
```

### **Option 2: Location-Specific Crons (GCP Cloud Scheduler)**
```bash
# Argentina billing - every 5 minutes
*/5 * * * * cd /path/to/kitchen && /path/to/venv/bin/python -c "from app.services.cron.billing_events import multi_market_billing_entry; multi_market_billing_entry('AR')" >> /var/log/kitchen/billing_ar.log 2>&1

# Peru billing - every 5 minutes
*/5 * * * * cd /path/to/kitchen && /path/to/venv/bin/python -c "from app.services.cron.billing_events import multi_market_billing_entry; multi_market_billing_entry('PE')" >> /var/log/kitchen/billing_pe.log 2>&1

# US-Pacific (LA, Seattle, etc.) - every 5 minutes
*/5 * * * * cd /path/to/kitchen && /path/to/venv/bin/python -c "from app.services.cron.billing_events import multi_market_billing_entry; multi_market_billing_entry('US-Pacific')" >> /var/log/kitchen/billing_us_pacific.log 2>&1

# US-Eastern (NYC, etc.) - every 5 minutes
*/5 * * * * cd /path/to/kitchen && /path/to/venv/bin/python -c "from app.services.cron.billing_events import multi_market_billing_entry; multi_market_billing_entry('US-Eastern')" >> /var/log/kitchen/billing_us_eastern.log 2>&1
```

### **Kitchen Start Promotion (Lock-at-Kitchen-Start)**

Promotes locked plate selections to live (creates plate_pickup_live + restaurant_transaction) at kitchen start (11:30 AM local). Run every 5–15 minutes during business hours. Uses **location_id** (filters by address.timezone):

```bash
# All locations
*/5 * * * * cd /path/to/kitchen && /path/to/venv/bin/python -c "from app.services.cron.billing_events import kitchen_start_promotion_entry; kitchen_start_promotion_entry()" >> /var/log/kitchen/kitchen_start_promotion.log 2>&1

# Single location (e.g. AR or US-Pacific)
*/5 * * * * cd /path/to/kitchen && /path/to/venv/bin/python -c "from app.services.cron.billing_events import kitchen_start_promotion_entry; kitchen_start_promotion_entry('AR')" >> /var/log/kitchen/kitchen_start_ar.log 2>&1
*/5 * * * * cd /path/to/kitchen && /path/to/venv/bin/python -c "from app.services.cron.billing_events import kitchen_start_promotion_entry; kitchen_start_promotion_entry('US-Pacific')" >> /var/log/kitchen/kitchen_start_us_pacific.log 2>&1
```

Or via billing_events CLI: `python app/services/cron/billing_events.py kitchen_start [location_id]`

---

## 🎯 **Business Logic Flow**

### **Daily Timeline (Argentina Example):**
```
8:00 AM - Kitchen opens
2:30 PM - Kitchen closes (no more pickups)
4:00 PM - Billing runs (cron job)
5:00 PM - Reservations open for next day
```

### **Daily Timeline (Peru Example):**
```
8:00 AM - Kitchen opens  
2:30 PM - Kitchen closes (no more pickups)
4:00 PM - Billing runs (cron job)
5:00 PM - Reservations open for next day
```

---

## 🔍 **System Status Methods**

### **Check Market Configuration:**
```python
from app.config.market_config import MarketConfiguration

# Get market config
ar_config = MarketConfiguration.get_market_config("AR")
pe_config = MarketConfiguration.get_market_config("PE")

# Check if kitchen day is enabled
is_monday_enabled = MarketConfiguration.is_kitchen_day_enabled("AR", "Monday")

# Get kitchen close time in UTC
kitchen_close_utc = MarketConfiguration.get_kitchen_close_utc("AR", datetime.now(), "Monday")
```

### **Timezone Conversions:**
```python
# Convert local time to UTC
utc_time = MarketConfiguration.convert_local_to_utc("AR", time(14, 30), datetime.now())

# Convert UTC to local time
local_time = MarketConfiguration.convert_utc_to_local("AR", datetime.now())
```

---

## 📊 **Real Example from Your System**

### **Argentina Billing (Saturday, August 16, 2025):**
```
Kitchen Day: Saturday
Local Close Time: 2:30 PM (Argentina)
UTC Close Time: 5:30 PM
Billing Period: 00:00 UTC to 17:30 UTC
Result: Institution bill created with proper period
```

**Notice the difference:**
- **Old system**: 00:00 to 23:59 UTC (full day)
- **New system**: 00:00 to 17:30 UTC (kitchen day closure)

---

## 🎉 **Benefits of Market-Specific Configuration**

### **For Operations:**
- ✅ **Accurate timing** per market/country
- ✅ **Timezone awareness** (no manual UTC calculations)
- ✅ **Flexible configuration** (easy to add new markets)
- ✅ **Centralized management** (all configs in one place)

### **For Business:**
- ✅ **Local business hours** respected
- ✅ **Accurate billing periods** aligned with kitchen closure
- ✅ **Market-specific rules** (e.g., Sunday closed in some markets)
- ✅ **Scalable** to new countries/markets

---

## 🔧 **Adding New Markets**

### **1. Add Market Configuration:**
```python
# In app/config/market_config.py
"MX": MarketKitchenConfig(
    market_id="MX",
    market_name="Mexico",
    country_code="MX", 
    timezone="America/Mexico_City",
    kitchen_day_config={
        "Monday": {
            "kitchen_close": time(15, 0),      # 3:00 PM local
            "billing_run": time(16, 30),       # 4:30 PM local
            "reservations_open": time(18, 0),  # 6:00 PM local
            "enabled": True
        },
        # ... other days
    }
)
```

### **2. System Automatically:**
- ✅ **Detects new market**
- ✅ **Applies timezone conversions**
- ✅ **Includes in multi-market billing**
- ✅ **Respects market-specific rules**

---

## 🧪 **Testing the System**

### **Test Market Configurations:**
```bash
python -c "from app.config.market_config import MarketConfiguration; from datetime import datetime; print('AR Monday close:', MarketConfiguration.get_kitchen_close_utc('AR', datetime.now(), 'Monday')); print('PE Monday close:', MarketConfiguration.get_kitchen_close_utc('PE', datetime.now(), 'Monday'))"
```

### **Test Location-Specific Billing:**
```bash
# Argentina
python app/services/cron/billing_events.py multi_market AR

# US-Pacific
python app/services/cron/billing_events.py multi_market US-Pacific
```

### **Test Multi-Location Billing:**
```bash
python app/services/cron/billing_events.py multi_market
```

---

## 🎯 **Summary**

**Your kitchen day configuration now:**
1. **✅ Lives in `app/config/market_config.py`**
2. **✅ Supports Argentina (UTC-3) and Peru (UTC-5)**
3. **✅ Kitchen closes at 2:30 PM local time**
4. **✅ Billing runs at 4:00 PM local time**
5. **✅ Reservations open at 5:00 PM local time**
6. **✅ Automatically converts to UTC for system operations**
7. **✅ Supports multi-market billing with single cron job**

**The system automatically handles timezone conversions and creates bills with proper periods based on each market's kitchen day closure! 🚀** 