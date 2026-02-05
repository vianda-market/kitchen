# AWS Infrastructure Setup - Multi-Application Environment

**Purpose**: Reusable infrastructure documentation for all Kitchen applications (backend API, frontend webapp, data pipelines)

**Target Audience**: DevOps Engineer, Infrastructure Agent, SRE

**Deployment Method**: AWS CloudFormation (YAML templates)

---

## 🏗️ Architecture Overview

### Applications Deployed
1. **kitchen-backend** - FastAPI REST API (Python)
2. **kitchen-frontend** - React SPA (future)
3. **kitchen-data** - ETL/Analytics (future)

### AWS Services Used
- **EC2**: Application servers
- **RDS**: PostgreSQL database (shared or per-app)
- **S3**: Static assets, backups, logs
- **Secrets Manager**: Credentials, API keys
- **IAM**: Roles and policies
- **CloudWatch**: Monitoring, logs, alerts
- **Application Load Balancer**: Traffic distribution (multi-app)
- **Route53**: DNS management
- **Certificate Manager**: SSL/TLS certificates

---

## 📋 Prerequisites

### 1. AWS Account Setup
- [ ] Create AWS account (use new email for 12-month free tier if needed)
- [ ] Enable MFA on root account
- [ ] Create IAM admin user (don't use root for deployments)
- [ ] Configure AWS CLI with admin credentials
- [ ] Set up billing alerts ($10, $50, $100 thresholds)

### 2. Domain & DNS (Optional but recommended)
- [ ] Register domain (e.g., `kitchen.com`) via Route53 or external registrar
- [ ] Create hosted zone in Route53

### 3. Repository Structure
```
infrastructure/
├── cloudformation/
│   ├── 01-network.yml           # VPC, subnets, security groups
│   ├── 02-database.yml          # RDS PostgreSQL
│   ├── 03-secrets.yml           # Secrets Manager
│   ├── 04-compute.yml           # EC2 instances
│   ├── 05-loadbalancer.yml      # ALB (for multiple apps)
│   ├── 06-monitoring.yml        # CloudWatch alarms
│   └── parameters/
│       ├── dev.json
│       ├── staging.json
│       └── prod.json
├── scripts/
│   ├── deploy-stack.sh          # Deploy CloudFormation stacks
│   ├── rollback-stack.sh        # Rollback on failure
│   └── update-secrets.sh        # Update Secrets Manager
└── docs/
    └── DEPLOYMENT_GUIDE.md
```

---

## 🚀 Deployment Steps

### Step 1: Deploy Network Infrastructure
```bash
aws cloudformation create-stack \
  --stack-name kitchen-network-prod \
  --template-body file://cloudformation/01-network.yml \
  --parameters file://cloudformation/parameters/prod.json \
  --capabilities CAPABILITY_IAM
```

### Step 2: Deploy Database
```bash
aws cloudformation create-stack \
  --stack-name kitchen-database-prod \
  --template-body file://cloudformation/02-database.yml \
  --parameters file://cloudformation/parameters/prod.json \
  --capabilities CAPABILITY_IAM
```

### Step 3: Deploy Secrets
```bash
aws cloudformation create-stack \
  --stack-name kitchen-secrets-prod \
  --template-body file://cloudformation/03-secrets.yml \
  --parameters file://cloudformation/parameters/prod.json \
  --capabilities CAPABILITY_IAM
```

### Step 4: Deploy Compute
```bash
aws cloudformation create-stack \
  --stack-name kitchen-compute-prod \
  --template-body file://cloudformation/04-compute.yml \
  --parameters file://cloudformation/parameters/prod.json \
  --capabilities CAPABILITY_IAM
```

### Step 5: Deploy Load Balancer (Multi-App)
```bash
aws cloudformation create-stack \
  --stack-name kitchen-loadbalancer-prod \
  --template-body file://cloudformation/05-loadbalancer.yml \
  --parameters file://cloudformation/parameters/prod.json \
  --capabilities CAPABILITY_IAM
```

---

## 📦 Application-Specific Requirements

### Kitchen Backend API

**Required Resources**:
- EC2 instance: t2.micro (free tier) or t3.small (production)
- RDS PostgreSQL: db.t3.micro (free tier) or db.t3.small (production)
- Application port: 8000
- Health check: `GET /health`
- ALB target group path: `/api/*`

**Secrets Required**:
```json
{
  "kitchen-backend/database": {
    "host": "kitchen-db.xxxxx.rds.amazonaws.com",
    "port": 5432,
    "username": "kitchen_admin",
    "password": "<generated>",
    "database": "kitchen_db_prod"
  },
  "kitchen-backend/api-keys": {
    "jwt_secret": "<generated>",
    "google_maps_api_key": "<from Google Cloud Console>",
    "mercadopago_client_id": "<from MercadoPago>",
    "mercadopago_client_secret": "<from MercadoPago>"
  },
  "kitchen-backend/email": {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_username": "kitchen-noreply@gmail.com",
    "smtp_password": "<app-specific password>",
    "from_email": "kitchen-noreply@gmail.com"
  }
}
```

**Database Schema Source**: 
- **Separate Repository**: `kitchen-database` (see Database Repository Structure section)
- **Migration Strategy**: Schema applied during EC2 bootstrap or via CI/CD pipeline

---

## 📁 Database Repository Structure

### Recommendation: Separate `kitchen-database` Repository

**Purpose**: 
- Data engineer owns database schema, migrations, functions
- Backend engineer owns Python code
- Independent versioning and deployment

**Repository Structure**:
```
kitchen-database/
├── schema/
│   ├── 00-extensions.sql       # PostgreSQL extensions
│   ├── 01-enums.sql            # ENUM types
│   ├── 02-tables.sql           # Table definitions
│   ├── 03-indexes.sql          # Performance indexes
│   ├── 04-constraints.sql      # Foreign keys, checks
│   └── 05-functions.sql        # PL/pgSQL functions
├── migrations/
│   ├── v1.0.0_initial.sql
│   ├── v1.1.0_add_user_preferences.sql
│   └── v1.2.0_add_recommendations.sql
├── seeds/
│   ├── dev/
│   │   └── seed_dev_data.sql
│   ├── staging/
│   │   └── seed_staging_data.sql
│   └── prod/
│       └── seed_prod_minimal.sql
├── scripts/
│   ├── apply-schema.sh         # Apply full schema
│   ├── migrate.sh              # Run migrations
│   └── backup.sh               # Database backup
├── tests/
│   └── schema_validation.sql   # Schema integrity tests
└── README.md
```

**Integration with Backend**:
```yaml
# kitchen-backend/.github/workflows/deploy.yml
- name: Apply Database Migrations
  run: |
    # Clone kitchen-database repo
    git clone https://github.com/cdeachaval/kitchen-database.git
    
    # Apply migrations
    cd kitchen-database
    ./scripts/migrate.sh $DB_HOST $DB_NAME $DB_USER
```

**Benefits**:
- Data engineer can work independently on schema optimizations
- Backend engineer doesn't need to review SQL changes
- Database changes can be deployed separately from code
- Clear ownership and responsibility

---

## 🔧 Cost Optimization

### Free Tier Strategy (Year 1)

**Eligible Services**:
- EC2 t2.micro: 750 hours/month
- RDS db.t3.micro: 750 hours/month (20GB storage)
- ALB: 750 hours/month (15 LCU)
- S3: 5GB storage, 20,000 GET, 2,000 PUT
- Secrets Manager: Not free ($0.40/secret/month)

**Multi-Application Setup**:
1. **Single EC2 instance** runs multiple apps via Nginx reverse proxy:
   - `/api/*` → kitchen-backend (port 8000)
   - `/*` → kitchen-frontend (port 3000)
   - This uses only 730 hours/month of free tier

2. **Shared RDS** for development/staging:
   - Multiple databases on one instance: `kitchen_backend_dev`, `kitchen_frontend_dev`
   - Separate instances for production

**Cost After Free Tier** (Year 2):
- EC2 t2.micro × 2 (backend + frontend): $17/month
- RDS db.t3.micro: $15/month
- ALB: $16/month
- Secrets Manager: $2/month (5 secrets)
- **Total**: ~$50/month

---

## 📊 Monitoring Strategy

### CloudWatch Alarms

**Database Alarms**:
- CPU > 80% for 5 minutes
- Free storage < 2GB
- Failed connections > 10/minute

**Application Alarms**:
- 5xx errors > 10/minute
- API response time > 1 second (95th percentile)
- Memory usage > 80%

**SNS Topics**: Send alerts to email/Slack

---

## 🔒 Security Best Practices

### IAM Roles (Principle of Least Privilege)

**EC2 Role** (`kitchen-ec2-role`):
- Read access to Secrets Manager (`kitchen/*`)
- Write access to CloudWatch Logs
- Read access to S3 (for static assets)
- SES send email permissions

**RDS Access**:
- No public access (only from VPC)
- Security group allows port 5432 from EC2 security group only

**Application Secrets**:
- Never commit to git
- Store in AWS Secrets Manager
- Rotate credentials quarterly

---

## 📝 Next Steps for DevOps Engineer

1. **Review CloudFormation templates** in next sections
2. **Customize parameters** for your environment (VPC CIDR, instance sizes)
3. **Deploy stacks in order** (network → database → secrets → compute → loadbalancer)
4. **Coordinate with Backend Engineer** on:
   - Database connection strings (from Secrets Manager)
   - Application deployment process
   - Migration strategy
5. **Set up CI/CD pipeline** (GitHub Actions or AWS CodePipeline)
6. **Configure monitoring and alerts**

---

## 🤝 Agent Coordination

### Recommended Approach: Separate Agents

**Infrastructure Agent** (this repo + documentation):
- AWS infrastructure setup
- CloudFormation templates
- Networking, security, monitoring
- Multi-application orchestration
- Frontend deployment (future)

**Backend Agent** (kitchen-backend repo):
- Python code
- API endpoints
- Business logic
- Unit/integration tests
- Application-level concerns

**Database Agent** (kitchen-database repo):
- Schema design
- Migrations
- Performance optimization
- PL/pgSQL functions
- Data integrity

**Benefits**:
- Parallel development (no blocking)
- Clear separation of concerns
- Specialized expertise
- Independent versioning

---

## 📚 Related Documentation

- `CLOUDFORMATION_TEMPLATES.md` - Detailed YAML templates
- `DEPLOYMENT_RUNBOOK.md` - Step-by-step deployment guide
- `ROLLBACK_PROCEDURES.md` - Emergency rollback steps
- `MONITORING_ALERTS.md` - Alert configuration
- `DISASTER_RECOVERY.md` - Backup and restore procedures

---

## ❓ Questions for Team

1. **Free Tier**: Create new AWS account with new email for 12 months free tier?
2. **Domain**: Do you own a domain or need to register one?
3. **Multi-App Strategy**: Deploy backend + frontend on same EC2 (cost savings) or separate instances?
4. **Database**: Shared RDS for dev/staging, separate for prod?
5. **Backup Strategy**: How many days of backups to retain (RDS automated backups)?
6. **Monitoring**: Email alerts sufficient or need Slack/PagerDuty integration?

---

**Document Version**: 1.0  
**Last Updated**: 2026-02-04  
**Maintained By**: DevOps Team  
**Related Repos**: `kitchen-backend`, `kitchen-frontend`, `kitchen-database`
