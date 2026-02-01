# Database Rebuild Persistence Guide

## **🎯 Key Principle: All Changes Must Be in Repository Files**

Since the database is frequently torn down and rebuilt, **ALL** changes must be made to repository files, never to the live database directly.

## **✅ Files Modified for Archival System Persistence**

### **1. Database Structure Files**
```
app/db/
├── schema.sql              ✅ Updated (status/transaction_type tables)
├── index.sql               ✅ Updated (history table indexes)
├── trigger.sql             ✅ Updated (new triggers added)
├── archival_indexes.sql    ✅ NEW (17 performance indexes)
├── seed.sql                ✅ Updated (new reference data)
└── build_kitchen_db_dev.sh ✅ Updated (includes archival_indexes.sql)
```

### **2. Application Code Files**
```
app/
├── services/
│   ├── archival.py             ✅ Enhanced (8 new entity types)
│   └── cron/archival_job.py    ✅ NEW (scheduled jobs)
├── routes/admin/archival.py    ✅ NEW (admin endpoints)
├── models/user.py              ✅ Fixed (BaseModelCRUD inheritance)
├── config/settings.py          ✅ Updated (retention periods)
└── utils/log.py               ✅ Enhanced (new log levels)
```

### **3. Documentation Files**
```
├── ARCHIVAL_STRATEGY.md                ✅ NEW (strategic framework)
├── ARCHIVAL_SYSTEM_IMPLEMENTATION.md   ✅ NEW (technical details)
├── ARCHIVAL_ENHANCEMENT_SUMMARY.md     ✅ NEW (completion summary)
├── LOGGING_STRATEGY.md                 ✅ NEW (logging analysis)
└── DATABASE_REBUILD_PERSISTENCE.md    ✅ NEW (this file)
```

## **🔧 Build Process Integration**

### **Updated Build Script**
The `app/db/build_kitchen_db_dev.sh` now includes:
```bash
\i app/db/schema.sql
\i app/db/index.sql
\i app/db/trigger.sql
\i app/db/archival_indexes.sql  # ← NEW: Archival performance indexes
\i app/db/seed.sql
```

### **What Happens on Rebuild**
1. ✅ **Schema**: Status/transaction_type tables created
2. ✅ **Indexes**: Standard indexes + 17 archival performance indexes
3. ✅ **Triggers**: History logging triggers for new tables
4. ✅ **Data**: Reference data for statuses and transaction types
5. ✅ **Tests**: Validation that all tables exist

## **🚨 Critical Changes Made Persistent**

### **1. Archival Performance Indexes (17 total)**
```sql
-- Orders
idx_plate_pickup_archival
idx_plate_pickup_archival_eligible

-- Transactions  
idx_restaurant_transaction_archival
idx_restaurant_transaction_archival_eligible

-- Financial Records
idx_client_transaction_archival
idx_client_payment_attempt_archival

-- Statistics
idx_plate_pickup_stats
idx_restaurant_transaction_stats
idx_client_transaction_stats
```

### **2. Enhanced Entity Coverage**
```python
# New entities in archival system:
"client_bills": 365 days retention
"client_transactions": 90 days retention  
"fintech_transactions": 180 days retention
"plate_selections": 60 days retention
"payment_methods": 365 days retention
"plans": 730 days retention
"qr_codes": 180 days retention
"products": 365 days retention
```

### **3. Reference Data Management**
```sql
-- Status types (7 total)
'Pending', 'Arrived', 'Complete', 'Cancelled', 'Active', 'Inactive', 'Processed'

-- Transaction types (5 total)
'Order', 'Credit', 'Debit', 'Refund', 'Payment'
```

## **🔍 Validation After Rebuild**

### **Quick Verification Commands**
```bash
# 1. Verify archival indexes exist
psql -d kitchen_db_dev -c "
SELECT count(*) FROM pg_indexes 
WHERE indexname LIKE '%archival%' OR indexname LIKE '%stats%';"
# Expected: 17

# 2. Verify new tables exist
psql -d kitchen_db_dev -c "
SELECT table_name FROM information_schema.tables 
WHERE table_name IN ('status_info', 'transaction_type_info', 'status_history', 'transaction_type_history');"
# Expected: 4 tables

# 3. Verify reference data loaded
psql -d kitchen_db_dev -c "
SELECT count(*) FROM status_info; 
SELECT count(*) FROM transaction_type_info;"
# Expected: 7 statuses, 5 transaction types
```

### **Application Verification**
```python
# Test archival system functionality
from app.services.archival import ArchivalService

# Should return 14 entity types
entities = len(ArchivalService.get_retention_periods())
print(f"Coverage: {entities} entity types")

# Should import all models successfully  
for entity in settings.RETENTION_PERIODS.keys():
    model = ArchivalService._get_model_class(entity)
    assert model is not None, f"{entity} model import failed"
```

## **⚠️ Things to Never Do**

### **❌ Direct Database Changes**
```bash
# NEVER do this - changes will be lost on rebuild
psql -d kitchen_db_dev -c "CREATE INDEX some_index ON some_table(column);"
```

### **❌ Manual Data Updates**
```bash
# NEVER do this - data will be lost on rebuild  
psql -d kitchen_db_dev -c "INSERT INTO status_info VALUES (...);"
```

### **✅ Always Do This Instead**
```bash
# Add to app/db/archival_indexes.sql
echo "CREATE INDEX some_index ON some_table(column);" >> app/db/archival_indexes.sql

# Add to app/db/seed.sql
echo "INSERT INTO status_info VALUES (...);" >> app/db/seed.sql

# Then rebuild
./app/db/build_kitchen_db_dev.sh
```

## **🎯 Rebuild Test Checklist**

After any database rebuild, verify:

- [ ] **17 archival indexes** created
- [ ] **4 new tables** (status_info, status_history, transaction_type_info, transaction_type_history)  
- [ ] **Reference data** loaded (7 statuses, 5 transaction types)
- [ ] **14 entity types** covered in archival system
- [ ] **User model** inherits from BaseModelCRUD
- [ ] **Admin endpoints** accessible at `/admin/archival/*`
- [ ] **Dashboard** generates without errors
- [ ] **Validation** passes integrity checks

## **🚀 Future Additions**

When adding new features that require database changes:

1. **Schema changes** → Add to `app/db/schema.sql`
2. **New indexes** → Add to `app/db/index.sql` or `app/db/archival_indexes.sql`
3. **New triggers** → Add to `app/db/trigger.sql`
4. **Reference data** → Add to `app/db/seed.sql`
5. **New entity archival** → Update `app/services/archival.py` and `app/config/settings.py`

**Remember: Every change must survive `./app/db/build_kitchen_db_dev.sh`**

---

## **✅ Current Status: FULLY PERSISTENT**

All archival system enhancements are now properly integrated into the repository structure and will persist across database rebuilds. The enhanced system provides:

- **133% increase** in archival coverage (6 → 14 entity types)
- **17 performance indexes** for optimal query performance  
- **Complete financial compliance** with proper retention periods
- **Comprehensive documentation** for maintenance and future development

**Next rebuild will automatically include all enhancements!** 🎉 