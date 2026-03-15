# Archival Cron Strategy - Hybrid Configuration Approach

## 🎯 **PROBLEM SOLVED**

You correctly identified that **critical business configurations shouldn't require code deployments**. Our solution provides a **hybrid approach** that supports both:

- **Code-based configuration** (for dev environments)
- **Database-based configuration** (for production business agility)

## 🏗️ **ARCHITECTURE OVERVIEW**

### **Configuration Sources (Priority Order)**
1. **Database Configuration** - Business users can modify via API/UI
2. **Code Fallback** - Developer-defined defaults when DB unavailable
3. **Graceful Degradation** - System continues running if config source fails

### **Category-Based SLA Management**
Instead of individual table configurations, we use **business-logical categories**:

| Category | Retention | Grace Period | Priority | Business Reason |
|----------|-----------|--------------|----------|-----------------|
| `FINANCIAL_CRITICAL` | 7 years | 30 days | 1 | Legal compliance |
| `FINANCIAL_OPERATIONAL` | 1 year | 14 days | 2 | Dispute resolution |
| `CUSTOMER_SERVICE` | 3 months | 7 days | 3 | Support window |
| `OPERATIONAL_DATA` | 6 months | 14 days | 4 | Business analytics |
| `REFERENCE_DATA` | 2 years | 30 days | 5 | Product catalogs |
| `SECURITY_COMPLIANCE` | 7 years | 30 days | 1 | Security requirements |
| `SYSTEM_CONFIGURATION` | Never | 0 days | 99 | Core system data |

## 📁 **FILES CREATED/MODIFIED**

### **Core Configuration**
- `app/config/archival_config.py` - Hybrid configuration manager
- `app/db/archival_config_table.sql` - Database schema for config storage

### **Admin API**
- `app/routes/admin/archival_config.py` - Business user configuration endpoints

### **Table Categorization (Your Review Needed)**
```python
# FINANCIAL CRITICAL (7 years - legal compliance)
"user_info": ArchivalCategory.FINANCIAL_CRITICAL,
"client_bill_info": ArchivalCategory.FINANCIAL_CRITICAL,

# FINANCIAL OPERATIONAL (1 year - financial operations)  
"client_transaction": ArchivalCategory.FINANCIAL_OPERATIONAL,
"restaurant_transaction": ArchivalCategory.FINANCIAL_OPERATIONAL,
"subscription_info": ArchivalCategory.FINANCIAL_OPERATIONAL,

# CUSTOMER SERVICE (3 months - support window)
"plate_pickup_live": ArchivalCategory.CUSTOMER_SERVICE,
"client_payment_attempt": ArchivalCategory.CUSTOMER_SERVICE,
"plate_selection": ArchivalCategory.CUSTOMER_SERVICE,

# OPERATIONAL DATA (6 months - business operations)
"restaurant_info": ArchivalCategory.OPERATIONAL_DATA,
"institution_info": ArchivalCategory.OPERATIONAL_DATA,
"address_info": ArchivalCategory.OPERATIONAL_DATA,

# REFERENCE DATA (2 years - product/catalog data)
"product_info": ArchivalCategory.REFERENCE_DATA,  # + blob cleanup: delete image files when archived
"plate_info": ArchivalCategory.REFERENCE_DATA,
"plan_info": ArchivalCategory.REFERENCE_DATA,
"qr_code_info": ArchivalCategory.REFERENCE_DATA,

# SYSTEM CONFIGURATION (never archived)
"role_info": ArchivalCategory.SYSTEM_CONFIGURATION,
"status_info": ArchivalCategory.SYSTEM_CONFIGURATION,
# All *_history tables
```

## 🚀 **IMPLEMENTATION PHASES**

### **Phase 1: Dev Environment (Current)**
```bash
# Uses code-based configuration by default
# No environment variable needed
python -m uvicorn application:app --reload
```

### **Phase 2: Production Database Configuration**
```bash
# Enable database configuration
export USE_DATABASE_ARCHIVAL_CONFIG=true

# Apply database schema
psql -d kitchen_db_prod -f app/db/archival_config_table.sql

# Populate initial configuration via API
curl -X POST /admin/archival-config/ -d '{...}'
```

### **Phase 3: Business User Interface**
- Web UI for configuration management
- Approval workflows for critical changes
- Impact analysis before changes

## 🛠️ **ADMIN API ENDPOINTS**

### **Configuration Management**
- `GET /admin/archival-config/` - List all configurations
- `POST /admin/archival-config/` - Create new configuration
- `PUT /admin/archival-config/{id}` - Update configuration
- `DELETE /admin/archival-config/{id}` - Deactivate configuration

### **Operational Endpoints**
- `GET /admin/archival-config/table/{table_name}` - Get table-specific config
- `POST /admin/archival-config/refresh-cache` - Force refresh cache
- `GET /admin/archival-config/priority-order` - Get archival priority
- `GET /admin/archival-config/categories` - List available categories
- `GET /admin/archival-config/history/{id}` - Configuration change history

## 📊 **CRON CONFIGURATION**

### **Recommended Cron Schedule**
```bash
# Daily archival (runs high-priority tables first)
0 2 * * * cd /app && python -c "from app.services.cron.archival_job import daily_cron_entry; daily_cron_entry()"

# Weekly validation
0 3 * * 0 cd /app && python -c "from app.services.cron.archival_job import weekly_validation_entry; weekly_validation_entry()"

# Real-time config refresh (if needed)
*/15 * * * * cd /app && curl -X POST http://localhost:8000/admin/archival-config/refresh-cache
```

### **Priority-Based Processing**
The cron processes tables in **business priority order**:
1. **Financial Critical** (user_info, client_bill_info) - Priority 1
2. **Financial Operational** (transactions, subscriptions) - Priority 2  
3. **Customer Service** (orders, payment attempts) - Priority 3
4. **Operational Data** (restaurants, addresses) - Priority 4
5. **Reference Data** (products, plans) - Priority 5

### Product Image Blob Cleanup

When **`product_info`** records are archived, their image blobs must be deleted from storage:

- **Local dev:** Delete files at `image_storage_path` and `image_thumbnail_storage_path` (skip placeholder)
- **Prod (S3):** Delete the corresponding objects in the product-image bucket

Use `ProductImageService.delete_image(storage_path, thumbnail_storage_path)` before or after setting `is_archived = true`. The archival pipeline should invoke this for each archived product (excluding those still using the placeholder path).

Likewise, when **`qr_code`** records are archived, delete their image files from `static/qr_codes/` (or S3 when using cloud storage).

## ⚡ **BUSINESS AGILITY BENEFITS**

### **Before (Code-Based)**
- Configuration change requires code deployment
- Engineering bottleneck for business decisions
- Risk of bundling config with unrelated changes
- Slow response to regulatory changes

### **After (Hybrid Database)**
- Business users modify retention policies via API/UI
- No deployment needed for config changes
- Audit trail for all configuration changes
- Real-time cache refresh
- Rollback capability through history tables

## 🔄 **CACHE STRATEGY**

### **Configuration Loading**
1. **First Request**: Load from database (if enabled), fallback to code
2. **Subsequent Requests**: Use cached configuration
3. **Manual Refresh**: Force reload via admin API
4. **Error Handling**: Graceful fallback to code-based config

### **Performance Optimization**
- Configuration cached in memory after first load
- Database queries only on cache miss or manual refresh
- Fallback ensures system never fails due to config issues

## 🎛️ **ENVIRONMENT CONTROL**

### **Development**
```bash
# Uses code-based configuration (default)
# Fast iteration, no database dependency
```

### **Staging**
```bash
export USE_DATABASE_ARCHIVAL_CONFIG=true
# Test database configuration before production
```

### **Production**
```bash
export USE_DATABASE_ARCHIVAL_CONFIG=true
# Business users control retention policies
# Full audit trail and approval workflows
```

## 📋 **NEXT STEPS FOR YOU**

### **1. Review Table Categorization**
Please review the table categorization I provided and let me know:
- Any tables that should move between categories?
- Any missing tables from your schema?
- Any retention periods that need adjustment?

### **2. Test in Development**
```bash
# Test current code-based configuration
python -c "from app.config.archival_config import get_table_archival_config; print(get_table_archival_config('user_info'))"

# Test cron job
python -c "from app.services.cron.archival_job import get_archival_dashboard; print(get_archival_dashboard())"
```

### **3. Future Production Migration**
When ready for database configuration:
1. Apply `app/db/archival_config_table.sql`
2. Populate initial data via admin API
3. Set `USE_DATABASE_ARCHIVAL_CONFIG=true`
4. Build business user interface

## 🔒 **AUDIT & COMPLIANCE**

### **Change Tracking**
- All configuration changes logged in `archival_config_history`
- Who made changes, when, and what changed
- Rollback capability through history

### **Business Justification**
- Each category has clear business reasoning
- Retention periods align with legal/operational needs
- Priority system ensures critical data processed first

This approach gives you the **best of both worlds**: developer productivity in dev environments and business agility in production! 