# Kitchen API Documentation

This directory contains all project documentation organized by category for easy navigation and maintenance.

## 📁 Documentation Structure

### 🔄 [Archival](./archival/)
Documentation related to data archival strategies and cron jobs.
- `ARCHIVAL_CRON_STRATEGY.md` - Cron job strategy for archival processes
- `ARCHIVAL_ENHANCEMENT_SUMMARY.md` - Summary of archival system enhancements
- `ARCHIVAL_STRATEGY.md` - Overall archival strategy and approach
- `ARCHIVAL_SYSTEM_IMPLEMENTATION.md` - Implementation details for archival system

### 🧪 [Postman](./postman/)
Postman collection documentation, scripts, and testing guides.
- `POSTMAN_COLLECTION_FIXES.md` - Fixes and updates for Postman collections
- `POSTMAN_E2E_API_CALLS.md` - **Complete E2E API workflow with collection variables**
- `POSTMAN_INSTITUTION_ENTITY_SCRIPTS.md` - Institution entity API testing
- `POSTMAN_INSTITUTION_PAYMENT_ATTEMPT_SCRIPTS.md` - Removed payment-attempt endpoints; settlement pipeline only

### ⏰ [Cron](./cron/)
Cron job setup, configuration, and maintenance documentation.
- `CRON_SETUP_GUIDE.md` - Complete guide for setting up cron jobs

### 💰 [Billing](./billing/)
Billing system architecture, implementation, and business logic documentation.
- `DAILY_BALANCE_MANAGEMENT_SYSTEM.md` - Daily balance management system
- `INSTITUTION_BILLING_EXECUTION_PLAN.md` - Execution plan for institution billing
- `KITCHEN_DAY_BILLING_EXPLANATION.md` - Kitchen day billing logic explanation
- `MARKET_SPECIFIC_KITCHEN_DAY_CONFIGURATION.md` - Market-specific kitchen day configuration
- `MULTI_RESTAURANT_ENTITY_BILLING_ARCHITECTURE.md` - Multi-restaurant billing architecture
- `RESTAURANT_BALANCE_SYSTEM.md` - Restaurant balance system documentation
- `RESTAURANT_BALANCE_TIMING_UPDATE.md` - Balance timing update procedures

### 🗄️ [Database](./database/)
Database-related documentation including rebuild procedures and persistence strategies.
- `DATABASE_REBUILD_PERSISTENCE.md` - Database rebuild and persistence procedures

### 📊 [Performance](./performance/)
Performance monitoring, optimization, and analysis documentation.
- `PERFORMANCE_MONITORING.md` - Performance monitoring strategies and tools

### 🔌 [API](./api/)
API implementation, patterns, and architectural documentation.
- `CENTRALIZED_DELETE_API.md` - Centralized delete API implementation
- `DELETE_API_IMPLEMENTATION_SUMMARY.md` - Summary of delete API implementation
- `LOGGING_STRATEGY.md` - Logging strategy and best practices
- `STATUS_MANAGEMENT_PATTERN.md` - Status management patterns and implementation
- `ROLE_BASED_ACCESS_CONTROL.md` - Role-based access control API guide
- `ROLE_ASSIGNMENT_GUIDE.md` - Guide for assigning roles to users
- `SCOPING_SYSTEM.md` - Scoping and access control system documentation

### 🔒 [Security](./security/)
Security implementation patterns and developer guides.
- `SCOPE_LOGIC_DEVELOPER_GUIDE.md` - Developer guide for implementing scope logic in routes

### 🍽️ [Features](./)
Feature-specific documentation and roadmaps.
- `PLATE_PICKUP_QR_CODE_ROADMAP.md` - **Plate pickup QR code system implementation roadmap**

## 🚀 Quick Navigation

### For Developers
- **API Development**: Start with [API](./api/) folder for implementation patterns
- **Testing**: Check [Postman](./postman/) folder for API testing scripts
- **Database**: Refer to [Database](./database/) for DB-related procedures

### For DevOps
- **Cron Jobs**: See [Cron](./cron/) folder for scheduled task setup
- **Archival**: Check [Archival](./archival/) for data management strategies
- **Performance**: Monitor with [Performance](./performance/) documentation

### For Business Logic
- **Billing**: All billing-related docs in [Billing](./billing/) folder
- **System Architecture**: Review multi-restaurant and kitchen day configurations

## 📝 Documentation Standards

- All documentation files use Markdown format
- Files are organized by functional area
- Each category has a clear purpose and scope
- Cross-references between related documents are maintained

## 🔄 Maintenance

When adding new documentation:
1. Choose the appropriate category folder
2. Use descriptive, consistent naming conventions
3. Update this README if adding new categories
4. Ensure cross-references are maintained

---

*Last updated: September 6, 2025*
