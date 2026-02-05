# Database Repository Structure - kitchen-database

**Purpose**: Separate repository for database schema, migrations, and PL/pgSQL code  
**Owner**: Data Engineer  
**Related Repos**: `kitchen-backend` (API), `kitchen-frontend` (UI)

---

## 🎯 Why Separate Repository?

### Benefits
1. **Clear Ownership**: Data engineer owns database, backend engineer owns Python code
2. **Independent Versioning**: Database changes versioned separately from application code
3. **Specialization**: Database expert focuses on schema optimization, not API logic
4. **CI/CD Separation**: Database migrations deployed independently
5. **Reusability**: Multiple applications can reference same database
6. **Review Process**: Database changes reviewed by DB team, not backend team

### Team Structure
- **Data Engineer**: Schema design, migrations, performance tuning, PL/pgSQL
- **Backend Engineer**: Python code, API endpoints, business logic
- **DevOps Engineer**: AWS infrastructure, deployment pipelines

---

## 📁 Repository Structure

```
kitchen-database/
├── README.md
├── .gitignore
├── .github/
│   └── workflows/
│       ├── validate-schema.yml      # CI: Validate SQL syntax
│       ├── test-migrations.yml      # CI: Test migrations on temp DB
│       └── deploy-schema.yml        # CD: Deploy to RDS
│
├── schema/
│   ├── 00-extensions.sql            # PostgreSQL extensions (uuid-ossp, etc.)
│   ├── 01-enums.sql                 # ENUM types
│   ├── 02-tables/
│   │   ├── core/
│   │   │   ├── user_info.sql
│   │   │   ├── institution_info.sql
│   │   │   └── address_info.sql
│   │   ├── restaurant/
│   │   │   ├── restaurant_info.sql
│   │   │   ├── product_info.sql
│   │   │   └── plate_info.sql
│   │   └── billing/
│   │       ├── subscription_info.sql
│   │       └── client_bill_info.sql
│   ├── 03-indexes.sql               # Performance indexes
│   ├── 04-constraints.sql           # Foreign keys, unique constraints
│   ├── 05-functions/
│   │   ├── uuid7_function.sql       # UUIDv7 generator
│   │   ├── audit_triggers.sql       # Audit logging
│   │   └── business_logic.sql       # PL/pgSQL business functions
│   └── 06-views.sql                 # Materialized views, regular views
│
├── migrations/
│   ├── v1.0.0_initial_schema.sql
│   ├── v1.1.0_add_credential_recovery.sql
│   ├── v1.2.0_add_geolocation_indexes.sql
│   ├── v1.3.0_add_user_preferences_table.sql
│   └── rollback/
│       ├── v1.3.0_rollback.sql
│       └── v1.2.0_rollback.sql
│
├── seeds/
│   ├── 00-reference-data.sql        # Required reference data (all envs)
│   ├── dev/
│   │   ├── 01-dev-users.sql
│   │   ├── 02-dev-restaurants.sql
│   │   └── 03-dev-test-data.sql
│   ├── staging/
│   │   └── 01-staging-minimal.sql
│   └── prod/
│       └── 01-prod-reference-only.sql
│
├── tests/
│   ├── schema_tests.sql             # pgTAP or custom SQL tests
│   ├── constraint_tests.sql         # Test foreign keys, constraints
│   ├── function_tests.sql           # Test PL/pgSQL functions
│   └── performance_tests.sql        # Query performance benchmarks
│
├── scripts/
│   ├── apply-schema.sh              # Apply full schema (fresh install)
│   ├── migrate.sh                   # Run migrations
│   ├── rollback.sh                  # Rollback last migration
│   ├── backup.sh                    # Create database backup
│   ├── restore.sh                   # Restore from backup
│   ├── validate-sql.sh              # Validate SQL syntax
│   └── utils/
│       ├── connect-db.sh            # Helper to connect to DB
│       └── generate-migration.sh    # Template for new migration
│
├── docs/
│   ├── SCHEMA_DESIGN.md             # Database design documentation
│   ├── MIGRATION_GUIDE.md           # How to create/apply migrations
│   ├── PERFORMANCE_TUNING.md        # Index optimization guide
│   └── ERD.png                      # Entity Relationship Diagram
│
└── config/
    ├── database.yml                 # Database connection configs
    └── migration-config.yml         # Migration tool settings
```

---

## 🚀 Usage Workflows

### 1. Fresh Database Setup (New Environment)

```bash
# Clone repository
git clone https://github.com/cdeachaval/kitchen-database.git
cd kitchen-database

# Set database connection (from AWS Secrets Manager)
export DB_HOST=$(aws secretsmanager get-secret-value --secret-id kitchen/prod/database/credentials --query 'SecretString' | jq -r '.host')
export DB_PORT=5432
export DB_NAME=kitchen_db_prod
export DB_USER=$(aws secretsmanager get-secret-value --secret-id kitchen/prod/database/credentials --query 'SecretString' | jq -r '.username')
export DB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id kitchen/prod/database/credentials --query 'SecretString' | jq -r '.password')

# Apply full schema
./scripts/apply-schema.sh

# Apply reference data seeds
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f seeds/00-reference-data.sql

# For dev environment, also apply dev seeds
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f seeds/dev/01-dev-users.sql
```

### 2. Create New Migration

```bash
# Generate migration template
./scripts/utils/generate-migration.sh "add_user_preferences_table"
# Creates: migrations/v1.x.x_add_user_preferences_table.sql

# Edit migration file with SQL changes
vim migrations/v1.3.0_add_user_preferences_table.sql

# Test migration on local/dev database
./scripts/migrate.sh $DB_HOST $DB_NAME $DB_USER

# Create rollback script
vim migrations/rollback/v1.3.0_rollback.sql
```

### 3. Apply Migration to Production

```bash
# Via CI/CD pipeline (recommended)
git tag v1.3.0
git push origin v1.3.0
# GitHub Actions automatically deploys to staging, waits for approval, then prod

# Or manually (emergency only)
./scripts/migrate.sh $PROD_DB_HOST $PROD_DB_NAME $PROD_DB_USER
```

### 4. Rollback Migration

```bash
# Rollback last migration
./scripts/rollback.sh $DB_HOST $DB_NAME $DB_USER

# Or manually
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f migrations/rollback/v1.3.0_rollback.sql
```

---

## 🔄 Integration with kitchen-backend

### Backend Application Deployment

```yaml
# kitchen-backend/.github/workflows/deploy.yml

- name: Clone Database Repository
  run: |
    git clone https://github.com/cdeachaval/kitchen-database.git
    cd kitchen-database
    git checkout ${{ env.DB_VERSION }}  # Pin to specific version

- name: Apply Database Migrations
  run: |
    cd kitchen-database
    ./scripts/migrate.sh $DB_HOST $DB_NAME $DB_USER
  env:
    DB_HOST: ${{ secrets.DB_HOST }}
    DB_NAME: ${{ secrets.DB_NAME }}
    DB_USER: ${{ secrets.DB_USER }}
    DB_PASSWORD: ${{ secrets.DB_PASSWORD }}

- name: Deploy Backend Application
  run: |
    # Deploy Python app after DB is ready
    ./scripts/deploy-backend.sh
```

### Version Compatibility

**kitchen-backend** `requirements.txt`:
```text
# Database schema version compatibility
# This app requires kitchen-database >= v1.3.0
# See: https://github.com/cdeachaval/kitchen-database/releases
```

**kitchen-database** `CHANGELOG.md`:
```markdown
## v1.3.0 (2026-02-15)
### Added
- user_preferences table for recommendation engine
- indexes on plate_selection(user_id, created_date)

### Changed
- None

### Breaking Changes
- None

### Compatible With
- kitchen-backend: >= v2.1.0
```

---

## 📝 Migration Best Practices

### 1. Backwards Compatible Changes
Always write migrations that are backwards compatible:

✅ **Good** (Backwards Compatible):
```sql
-- Add new optional column
ALTER TABLE user_info ADD COLUMN phone_verified BOOLEAN DEFAULT FALSE;

-- Add new table (doesn't affect existing code)
CREATE TABLE user_preferences (...);

-- Add index (improves performance, doesn't break code)
CREATE INDEX idx_user_email ON user_info(email);
```

❌ **Bad** (Breaking Changes):
```sql
-- Rename column (breaks existing queries)
ALTER TABLE user_info RENAME COLUMN email TO email_address;

-- Drop column (breaks existing code)
ALTER TABLE user_info DROP COLUMN cellphone;

-- Change column type (may break constraints)
ALTER TABLE user_info ALTER COLUMN age TYPE INTEGER;
```

### 2. Two-Phase Deployments for Breaking Changes

**Phase 1: Add New, Keep Old**
```sql
-- Add new column
ALTER TABLE user_info ADD COLUMN email_address VARCHAR(100);

-- Copy data
UPDATE user_info SET email_address = email;

-- Update application to use email_address
-- Deploy backend v2.0.0
```

**Phase 2: Remove Old**
```sql
-- After backend deployment is stable
ALTER TABLE user_info DROP COLUMN email;
```

### 3. Migration Testing

```bash
# Always test migrations on dev/staging first
./scripts/migrate.sh $DEV_DB_HOST $DEV_DB_NAME $DEV_DB_USER

# Run backend tests against migrated database
cd ../kitchen-backend
pytest app/tests/

# If tests pass, proceed to staging
./scripts/migrate.sh $STAGING_DB_HOST $STAGING_DB_NAME $STAGING_DB_USER
```

---

## 🔒 Security Considerations

### 1. Sensitive Data
**Never commit**:
- Database passwords
- Connection strings
- Production data
- Real user information

### 2. Seed Data
**Development seeds**:
- Use fake names (John Doe, Jane Smith)
- Use fake emails (test@example.com)
- Use non-real phone numbers

**Production seeds**:
- Only reference data (countries, currencies)
- No user data

### 3. Access Control
```sql
-- Create read-only role for analytics
CREATE ROLE kitchen_readonly;
GRANT CONNECT ON DATABASE kitchen_db_prod TO kitchen_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO kitchen_readonly;

-- Application role (read/write)
CREATE ROLE kitchen_app;
GRANT CONNECT ON DATABASE kitchen_db_prod TO kitchen_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO kitchen_app;
```

---

## 🎯 Data Engineer Responsibilities

### Daily Tasks
1. Review schema change requests from backend team
2. Write and test migrations
3. Monitor database performance (CloudWatch)
4. Optimize slow queries

### Weekly Tasks
1. Review database metrics (query performance, index usage)
2. Plan index optimizations
3. Update documentation

### Monthly Tasks
1. Database backup verification
2. Performance tuning review
3. Capacity planning

---

## 📚 Related Documentation

- `AWS_INFRASTRUCTURE_SETUP.md` - AWS RDS setup
- `BACKEND_ROADMAP.md` - Backend development roadmap
- `MIGRATION_GUIDE.md` - Detailed migration procedures

---

## ❓ FAQs

**Q: Should I create a migration for every schema change?**  
A: Yes. Even small changes should have migrations for traceability.

**Q: Can I edit old migrations?**  
A: No. Once a migration is applied to any environment, it's immutable. Create a new migration to fix issues.

**Q: How do I handle data migrations (not just schema)?**  
A: Create a migration with both DDL (schema) and DML (data) changes, but test extensively on dev first.

**Q: Should PL/pgSQL functions go in migrations or schema/?**  
A: Schema changes go in `schema/05-functions/`. Modifications to existing functions go in migrations.

---

**Repository**: https://github.com/cdeachaval/kitchen-database  
**Owner**: Data Engineering Team  
**Last Updated**: 2026-02-04
