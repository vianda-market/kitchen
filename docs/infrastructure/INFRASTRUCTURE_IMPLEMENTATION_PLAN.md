# Infrastructure Implementation Plan

**Purpose**: Strategic plan for separating infrastructure (AWS), database (PostgreSQL), and backend (Python)  
**Target**: Enable parallel development by DevOps Agent, Database Agent, and Backend Agent  
**Date**: 2026-02-04

---

## 🎯 Overall Strategy

### Current State (Monorepo)
```
kitchen/
├── app/                    # Python backend code
│   ├── services/
│   ├── routes/
│   └── ...
├── app/db/                 # SQL files mixed with Python
│   ├── schema.sql
│   ├── trigger.sql
│   ├── uuid7_function.sql
│   └── seed.sql
├── docs/
└── static/
```

### Target State (3 Repositories)
```
1. kitchen-backend          # Python API only (Backend Agent)
   ├── app/
   ├── tests/
   ├── requirements.txt
   └── application.py

2. kitchen-database         # All SQL code (Database Agent)
   ├── schema/
   ├── migrations/
   ├── functions/
   └── seeds/

3. infrastructure           # AWS CloudFormation (DevOps Agent)
   ├── cloudformation/
   │   ├── 01-network.yml
   │   ├── 02-rds.yml
   │   ├── 03-ec2.yml
   │   ├── 04-secrets.yml
   │   └── 05-alb.yml
   └── scripts/
```

---

## 📋 PART 1: AWS Infrastructure Setup

### Goal
Create clean, modular CloudFormation YAML files that DevOps Agent can deploy to AWS without needing to understand Python or SQL code.

### CloudFormation Stack Architecture

```
┌─────────────────────────────────────────────────────┐
│  Stack 1: Network (01-network.yml)                  │
│  - VPC, Subnets, Internet Gateway                   │
│  - Security Groups                                  │
│  Outputs: VPC ID, Subnet IDs, SG IDs              │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│  Stack 2: Database (02-rds.yml)                     │
│  - RDS PostgreSQL instance                          │
│  - DB Subnet Group                                  │
│  - CloudWatch alarms                                │
│  Outputs: DB Endpoint, Port                        │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│  Stack 3: Secrets (03-secrets.yml)                  │
│  - AWS Secrets Manager                              │
│  - IAM policies for secrets access                  │
│  Outputs: Secret ARNs                              │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│  Stack 4: Compute (04-ec2.yml)                      │
│  - EC2 instances                                    │
│  - IAM roles for EC2                                │
│  - User data script (bootstrap)                     │
│  Outputs: Instance IDs, Public IPs                 │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│  Stack 5: Load Balancer (05-alb.yml)                │
│  - Application Load Balancer                        │
│  - Target Groups                                    │
│  - Listener Rules                                   │
│  Outputs: ALB DNS Name                             │
└─────────────────────────────────────────────────────┘
```

### YAML Files to Create

#### 1.1 Network Infrastructure (`01-network.yml`)
**Purpose**: VPC, subnets, security groups  
**Parameters**:
- `Environment` (dev/staging/prod)
- `VpcCIDR` (default: 10.0.0.0/16)
- `PublicSubnet1CIDR`, `PublicSubnet2CIDR`
- `PrivateSubnet1CIDR`, `PrivateSubnet2CIDR`

**Resources**:
- VPC with DNS support
- Internet Gateway
- 2 Public Subnets (for EC2, ALB) across 2 AZs
- 2 Private Subnets (for RDS) across 2 AZs
- Route Tables
- Security Groups:
  - ALB Security Group (80, 443 from 0.0.0.0/0)
  - EC2 Security Group (8000 from ALB, 22 from admin IP)
  - RDS Security Group (5432 from EC2 only)

**Outputs**:
- VPC ID
- All Subnet IDs
- All Security Group IDs

---

#### 1.2 Database Infrastructure (`02-rds.yml`)
**Purpose**: RDS PostgreSQL instance  
**Parameters**:
- `Environment`
- `NetworkStackName` (to import VPC/subnet references)
- `DBInstanceClass` (db.t3.micro for free tier)
- `DBAllocatedStorage` (20 GB for free tier)
- `DBName` (kitchen_db_prod)
- `DBMasterUsername` (kitchen_admin)
- `DBMasterPassword` (secure parameter)
- `BackupRetentionPeriod` (7 days default)
- `MultiAZ` (false for dev, true for prod)

**Resources**:
- RDS DB Instance (PostgreSQL 13+)
- DB Subnet Group
- CloudWatch Alarms:
  - High CPU (> 80%)
  - Low storage (< 2 GB)
  - High connections
- Automated backups

**Outputs**:
- DB Endpoint Address
- DB Port
- DB Name

**Special Notes**:
- Schema is NOT applied here
- Schema comes from `kitchen-database` repo
- RDS only provides empty PostgreSQL instance
- Application/pipeline applies schema from separate repo

---

#### 1.3 Compute Infrastructure (`03-ec2.yml`)
**Purpose**: EC2 instances for backend API  
**Parameters**:
- `Environment`
- `NetworkStackName`
- `SecretsStackName`
- `InstanceType` (t2.micro for free tier)
- `KeyPairName` (for SSH access)
- `LatestAmiId` (Amazon Linux 2023)

**Resources**:
- EC2 Instance with:
  - Python 3.11
  - Nginx reverse proxy
  - Supervisor for process management
- IAM Instance Profile with:
  - Secrets Manager read access
  - CloudWatch Logs write access
  - S3 read access (for static assets)
- User Data script:
  ```bash
  #!/bin/bash
  # Install dependencies
  yum update -y
  yum install -y python3.11 nginx git postgresql15-client
  
  # Clone backend repo
  git clone https://github.com/cdeachaval/kitchen-backend.git /opt/kitchen-backend
  
  # Install Python dependencies
  cd /opt/kitchen-backend
  pip3.11 install -r requirements.txt
  
  # Fetch secrets from AWS Secrets Manager
  # Configure application
  # Start services
  ```

**Outputs**:
- Instance ID
- Public IP
- Private IP

---

#### 1.4 Secrets Management (`04-secrets.yml`)
**Purpose**: Store credentials and API keys  
**Parameters**:
- `Environment`
- `DatabaseStackName` (to reference DB endpoint)

**Resources**:
- Secrets:
  - `kitchen/{env}/database/credentials`
    ```json
    {
      "host": "kitchen-db-prod.xxx.rds.amazonaws.com",
      "port": 5432,
      "username": "kitchen_admin",
      "password": "CHANGEME",
      "database": "kitchen_db_prod"
    }
    ```
  - `kitchen/{env}/backend/api-keys`
    ```json
    {
      "jwt_secret": "GENERATE_RANDOM",
      "google_maps_api_key": "FROM_GOOGLE_CONSOLE",
      "mercadopago_client_id": "FROM_MERCADOPAGO",
      "mercadopago_client_secret": "FROM_MERCADOPAGO"
    }
    ```
  - `kitchen/{env}/email/config`
    ```json
    {
      "smtp_host": "smtp.gmail.com",
      "smtp_port": 587,
      "smtp_username": "kitchen@gmail.com",
      "smtp_password": "GMAIL_APP_PASSWORD",
      "from_email": "kitchen@gmail.com"
    }
    ```
- IAM Policy: EC2 read access to all kitchen/* secrets

**Outputs**:
- Secret ARNs
- IAM Policy ARN

---

#### 1.5 Load Balancer (`05-alb.yml`)
**Purpose**: Application Load Balancer for multi-app routing  
**Parameters**:
- `Environment`
- `NetworkStackName`
- `ComputeStackName`

**Resources**:
- Application Load Balancer
- Target Groups:
  - Backend API (port 8000, path `/api/*`)
  - Frontend (port 3000, path `/*`) - future
- Listener Rules:
  - HTTP → HTTPS redirect
  - HTTPS routing
- Health Checks:
  - Backend: `GET /health`
  - Frontend: `GET /`

**Outputs**:
- ALB DNS Name
- Target Group ARNs

---

### 1.6 Deployment Order

```bash
# Step 1: Deploy Network
aws cloudformation create-stack \
  --stack-name kitchen-network-prod \
  --template-body file://01-network.yml \
  --parameters ParameterKey=Environment,ParameterValue=prod

# Step 2: Deploy Database
aws cloudformation create-stack \
  --stack-name kitchen-database-prod \
  --template-body file://02-rds.yml \
  --parameters ParameterKey=Environment,ParameterValue=prod \
               ParameterKey=NetworkStackName,ParameterValue=kitchen-network-prod \
               ParameterKey=DBMasterPassword,ParameterValue=SecurePassword123!

# Step 3: Deploy Secrets
aws cloudformation create-stack \
  --stack-name kitchen-secrets-prod \
  --template-body file://04-secrets.yml \
  --parameters ParameterKey=Environment,ParameterValue=prod \
  --capabilities CAPABILITY_IAM

# Step 4: Deploy Compute
aws cloudformation create-stack \
  --stack-name kitchen-compute-prod \
  --template-body file://03-ec2.yml \
  --parameters ParameterKey=Environment,ParameterValue=prod \
               ParameterKey=NetworkStackName,ParameterValue=kitchen-network-prod \
  --capabilities CAPABILITY_IAM

# Step 5: Deploy Load Balancer
aws cloudformation create-stack \
  --stack-name kitchen-loadbalancer-prod \
  --template-body file://05-alb.yml \
  --parameters ParameterKey=Environment,ParameterValue=prod \
               ParameterKey=NetworkStackName,ParameterValue=kitchen-network-prod
```

### 1.7 Cost Estimate

**Free Tier (First 12 Months)**:
- EC2 t2.micro: 750 hours/month (FREE)
- RDS db.t3.micro: 750 hours/month (FREE)
- ALB: 750 hours/month (FREE)
- Secrets Manager: $0.40/secret × 3 = $1.20/month
- **Total Year 1**: ~$15/month

**After Free Tier**:
- EC2 t2.micro: $8.50/month
- RDS db.t3.micro: $15/month
- ALB: $16/month
- Secrets: $1.20/month
- **Total Year 2+**: ~$41/month

---

## 📋 PART 2: Database Repository & Migration

### Goal
Extract all SQL code from `kitchen-backend` into separate `kitchen-database` repository owned by Data Engineer.

### 2.1 Repository Structure

```
kitchen-database/
├── README.md
├── .github/
│   └── workflows/
│       ├── validate-sql.yml       # CI: Check SQL syntax
│       └── deploy-schema.yml      # CD: Apply to RDS
│
├── schema/
│   ├── 00-extensions.sql          # CREATE EXTENSION uuid-ossp, etc.
│   ├── 01-enums.sql               # All ENUM types
│   ├── 02-tables/                 # Table definitions (one file per table)
│   │   ├── user_info.sql
│   │   ├── restaurant_info.sql
│   │   ├── plate_info.sql
│   │   └── ... (40+ tables)
│   ├── 03-indexes.sql             # All indexes
│   ├── 04-constraints.sql         # Foreign keys, constraints
│   ├── 05-functions/
│   │   ├── uuid7_function.sql
│   │   └── audit_triggers.sql
│   └── 06-views.sql               # Materialized views
│
├── migrations/
│   ├── v1.0.0_initial_schema.sql
│   ├── v1.1.0_add_credential_recovery.sql
│   ├── v1.2.0_add_user_preferences.sql
│   └── rollback/
│       └── v1.2.0_rollback.sql
│
├── seeds/
│   ├── 00-reference-data.sql      # Countries, currencies (all envs)
│   ├── dev/
│   │   ├── 01-dev-users.sql
│   │   └── 02-dev-restaurants.sql
│   └── prod/
│       └── 01-prod-reference.sql  # No user data
│
├── tests/
│   ├── schema_validation.sql
│   └── constraint_tests.sql
│
└── scripts/
    ├── apply-schema.sh            # Deploy full schema to RDS
    ├── migrate.sh                 # Run specific migration
    └── backup.sh                  # Database backup
```

### 2.2 Files to Move from kitchen-backend

**From `app/db/` to `kitchen-database/schema/`**:
- `schema.sql` → Split into:
  - `02-tables/*.sql` (one file per table)
  - `03-indexes.sql`
  - `04-constraints.sql`
- `uuid7_function.sql` → `05-functions/uuid7_function.sql`
- `trigger.sql` → `05-functions/audit_triggers.sql`
- `seed.sql` → `seeds/dev/01-dev-data.sql`
- `test.sql` → `tests/schema_validation.sql`
- `index.sql` → `03-indexes.sql`

**Keep in `kitchen-backend`**:
- Python code (`app/`)
- Tests (`app/tests/`)
- Requirements (`requirements.txt`)
- Application entry (`application.py`)

### 2.3 Migration Steps

#### Phase 1: Create kitchen-database Repository
```bash
# 1. Create new repo on GitHub
gh repo create kitchen-database --public

# 2. Clone locally
git clone https://github.com/cdeachaval/kitchen-database.git
cd kitchen-database

# 3. Copy SQL files from kitchen-backend
cp ../kitchen-backend/app/db/*.sql ./schema/

# 4. Reorganize into structure
# (Manual work: split schema.sql into table files)

# 5. Commit and push
git add .
git commit -m "Initial database repository structure"
git push origin main
```

#### Phase 2: Update kitchen-backend
```bash
cd kitchen-backend

# 1. Remove SQL files
rm -rf app/db/*.sql

# 2. Update documentation
# Point to kitchen-database repo

# 3. Update CI/CD to clone kitchen-database
# .github/workflows/deploy.yml references kitchen-database

# 4. Commit changes
git add .
git commit -m "Extract SQL to kitchen-database repository"
git push origin main
```

#### Phase 3: Deploy Schema to RDS
```bash
# From kitchen-database repo
cd kitchen-database

# Get RDS credentials from Secrets Manager
export DB_HOST=$(aws secretsmanager get-secret-value \
  --secret-id kitchen/prod/database/credentials \
  --query 'SecretString' | jq -r '.host')

# Apply schema
./scripts/apply-schema.sh $DB_HOST kitchen_db_prod kitchen_admin
```

### 2.4 Integration with Backend Deployment

**kitchen-backend CI/CD** (`.github/workflows/deploy.yml`):
```yaml
name: Deploy Backend to EC2

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout backend code
        uses: actions/checkout@v3
      
      - name: Clone database repository
        run: |
          git clone https://github.com/cdeachaval/kitchen-database.git
          cd kitchen-database
          git checkout v1.2.0  # Pin to specific version
      
      - name: Apply database migrations
        run: |
          cd kitchen-database
          ./scripts/migrate.sh ${{ secrets.DB_HOST }} \
                               ${{ secrets.DB_NAME }} \
                               ${{ secrets.DB_USER }}
        env:
          PGPASSWORD: ${{ secrets.DB_PASSWORD }}
      
      - name: Deploy backend application
        run: |
          # SSH to EC2, pull latest code, restart services
          ./scripts/deploy-to-ec2.sh
```

### 2.5 Version Compatibility Matrix

| kitchen-backend | kitchen-database | Notes |
|----------------|------------------|-------|
| v1.0.0 - v1.5.0 | Monorepo (app/db/) | Before split |
| v2.0.0+ | v1.0.0+ | After split |
| v2.1.0 | v1.2.0+ | Requires user_preferences table |
| v3.0.0 | v2.0.0+ | Requires NoSQL integration |

---

## 📋 PART 3: Backend Roadmap (Python Only)

### After SQL Extraction

**kitchen-backend** focuses exclusively on:
1. **Password Recovery**: SMTP integration (Gmail → AWS SES)
2. **Google Maps API**: Geolocation service
3. **Recommendation Engine**: Python business logic (data from DB)
4. **MercadoPago Integration**: Payment processing
5. **Testing**: Unit/integration tests
6. **API Documentation**: OpenAPI/Swagger

**Does NOT include**:
- SQL schema design
- Database migrations
- PL/pgSQL functions
- Index optimization

---

## 🤝 PART 4: Agent Coordination Strategy

### Three Parallel Agents

#### Agent 1: DevOps / Infrastructure Agent
**Repository**: `infrastructure` (new repo or `docs/infrastructure/`)  
**Responsibilities**:
- Create CloudFormation YAML files
- Deploy stacks to AWS
- Manage secrets (initial setup)
- Monitor CloudWatch alarms
- Handle EC2 bootstrap scripts
- Configure Nginx/Supervisor

**Tools**: AWS CLI, CloudFormation, Terraform (alternative)

---

#### Agent 2: Database Agent
**Repository**: `kitchen-database`  
**Responsibilities**:
- Design database schema
- Write migrations
- Optimize queries/indexes
- Create PL/pgSQL functions
- Seed data management
- Database performance tuning

**Tools**: PostgreSQL, psql, pgAdmin, DBeaver

---

#### Agent 3: Backend Agent
**Repository**: `kitchen-backend`  
**Responsibilities**:
- Python API development
- Business logic
- Authentication/authorization
- External API integration (Google, MercadoPago)
- Unit/integration tests
- API documentation

**Tools**: Python, FastAPI, pytest, Postman

---

### Communication Protocol

**Scenario 1: Backend needs new table**
1. Backend Agent: Opens issue in `kitchen-database` repo
2. Database Agent: Designs table, creates migration
3. Database Agent: Deploys migration to dev/staging
4. Backend Agent: Tests against new schema, deploys code

**Scenario 2: Schema change breaks backend**
1. Database Agent: Follows backwards-compatible migration strategy
2. Two-phase deployment:
   - Phase 1: Add new column (optional), deploy backend to use it
   - Phase 2: Remove old column after backend is stable

**Scenario 3: AWS resource needs adjustment**
1. Backend/DB Agent: Opens issue in `infrastructure` repo
2. DevOps Agent: Updates CloudFormation template
3. DevOps Agent: Deploys stack update
4. Backend/DB Agent: Verifies changes

---

## 📅 Implementation Timeline

### Week 1: AWS Setup
- [ ] Create CloudFormation YAML files (01-05)
- [ ] Create parameter files (dev, staging, prod)
- [ ] Deploy to dev environment
- [ ] Verify connectivity (EC2 → RDS)

### Week 2: Database Repository
- [ ] Create `kitchen-database` repository
- [ ] Extract SQL files from `kitchen-backend`
- [ ] Reorganize into schema structure
- [ ] Create deployment scripts
- [ ] Deploy schema to dev RDS

### Week 3: Backend Integration
- [ ] Update `kitchen-backend` to remove SQL files
- [ ] Update CI/CD to reference `kitchen-database`
- [ ] Test backend against separate database repo
- [ ] Deploy to staging

### Week 4: Production Deployment
- [ ] Deploy CloudFormation to production
- [ ] Apply production schema
- [ ] Deploy backend application
- [ ] Configure monitoring/alerts

---

## ✅ Success Criteria

### Infrastructure
- [ ] All CloudFormation stacks deploy successfully
- [ ] EC2 can connect to RDS
- [ ] Secrets Manager properly configured
- [ ] CloudWatch alarms triggering correctly

### Database
- [ ] Schema applied to RDS without errors
- [ ] All tables, indexes, functions created
- [ ] Seed data loaded
- [ ] Migrations runnable

### Backend
- [ ] Application starts without SQL file dependencies
- [ ] All tests pass
- [ ] API endpoints functional
- [ ] Integration with Google Maps working

---

## 📚 Deliverables

### For DevOps Agent
1. `01-network.yml` - Network infrastructure
2. `02-rds.yml` - Database infrastructure
3. `03-ec2.yml` - Compute infrastructure
4. `04-secrets.yml` - Secrets management
5. `05-alb.yml` - Load balancer
6. `DEPLOYMENT_GUIDE.md` - Step-by-step deployment
7. `parameters/prod.json` - Production parameters

### For Database Agent
1. `kitchen-database` repository structure
2. `MIGRATION_GUIDE.md` - Migration procedures
3. `SCHEMA_DESIGN.md` - Database design docs
4. `scripts/apply-schema.sh` - Deployment script

### For Backend Agent
1. Updated `kitchen-backend` (no SQL files)
2. `.github/workflows/deploy.yml` - Updated CI/CD
3. `DATABASE_INTEGRATION.md` - How to work with separate DB repo

---

## ❓ Open Questions

1. **AWS Account**: Create new account with new email for free tier?
2. **Domain**: Do you own a domain or need to register one?
3. **Multi-Region**: Deploy to single region initially (us-east-1)?
4. **Backup Strategy**: RDS automated backups sufficient or need manual S3 backups?
5. **Monitoring**: Email alerts or Slack/PagerDuty integration?
6. **Database Repository**: Public or private GitHub repo?

---

**Next Step**: Create CloudFormation YAML files after plan approval
