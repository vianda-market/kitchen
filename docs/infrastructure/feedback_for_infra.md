# Feedback for Infrastructure Repo

**Source**: Backend / Infrastructure Agent (this repo)  
**Purpose**: Requirements and recommendations for the new Pulumi-based infrastructure repository so it supports the Kitchen FastAPI app and PostgreSQL database.

**Note**: This doc reflects backend/infra needs only. Use together with feedback from B2B and B2C clients when designing the infrastructure repo.

---

## 1. Applications to Support

| Application | Source | Description |
|-------------|--------|-------------|
| **kitchen-backend** | This repo | FastAPI REST API (Python) |
| **PostgreSQL database** | This repo (`app/db/`) | Schema, migrations, triggers, seed data |

---

## 2. FastAPI Backend Requirements

### Runtime
- **Port**: 8000
- **Health endpoint**: `GET /health` → returns `{"status": "healthy"}`
- **Root**: `GET /` for load balancer / monitoring
- **API base**: `/api/v1/`

### Environment Variables (required by `app/utils/db_pool.py`, `app/config/settings.py`, `docs/readme/ENV_SETUP.md`)

| Variable | Required | Notes |
|----------|----------|-------|
| `DB_HOST` | Yes | RDS/PostgreSQL host |
| `DB_PORT` | Yes | Default 5432 |
| `DB_NAME` | Yes | Database name (e.g. `kitchen_db_prod`) |
| `DB_USER` | Yes | Database user |
| `DB_PASSWORD` | Yes | Database password |
| `DB_POOL_MIN_CONNECTIONS` | No | Default 5 |
| `DB_POOL_MAX_CONNECTIONS` | No | Default 20 |
| `SECRET_KEY` | Yes | JWT signing key |
| `ALGORITHM` | Yes | JWT algorithm (e.g. HS256) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | JWT expiry (minutes) |
| `GOOGLE_API_KEY_DEV` / `_STAGING` / `_PROD` | Prod | Per-environment; required when `DEV_MODE=false` |
| `MERCADOPAGO_CLIENT_ID`, `MERCADOPAGO_CLIENT_SECRET`, `MERCADOPAGO_REDIRECT_URI` | Prod | For MercadoPago payment integration |
| `FRONTEND_URL` | Yes | For password reset links |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `FROM_EMAIL`, `FROM_NAME` | Yes | Email (Gmail SMTP or AWS SES) |
| `DEV_MODE` | No | `true` = mock external APIs; `false` = real APIs |
| `PAYMENT_PROVIDER` | No | `mock` or `stripe` |
| `SUPPLIER_PAYOUT_PROVIDER` | No | `mock` or `stripe` |
| `VIANDA_CUSTOMERS_INSTITUTION_ID` | No | Must match seed data |
| `VIANDA_ENTERPRISES_INSTITUTION_ID` | No | Must match seed data |

### Secrets (production)
- Store sensitive values in AWS Secrets Manager (or equivalent)
- Inject at runtime via env or a secrets-sidecar pattern
- Rotate DB password, JWT secret, and API keys periodically

---

## 3. Database Requirements

### Schema Source
Schema lives in this repo under `app/db/`:

- `schema.sql` — main schema (idempotent: DROP + CREATE IF NOT EXISTS)
- `index.sql` — indexes
- `trigger.sql` — audit triggers
- `archival_config_table.sql` — archival config
- `archival_indexes.sql` — archival indexes
- `seed.sql` — seed data

**Note**: `uuid7_function.sql` archived to `docs/archived/db_migrations/` — PostgreSQL 18+ has built-in `uuidv7()`. Migrations also archived there. Schema.sql is source of truth for fresh builds.

### Apply Order
1. `schema.sql`
2. `index.sql`
3. `trigger.sql`
4. `archival_config_table.sql`
5. `archival_indexes.sql`
6. `seed.sql` (per environment)

### PostgreSQL
- Version: 13+ (or match current RDS default)
- Extensions: `uuid-ossp` (if used by uuid7)

---

## 4. Recommendations for the New Pulumi Repo

### Tooling
- **Pulumi** with Python (or TypeScript) — aligns with backend stack and supports multi-cloud later.
- **Alternative**: Terraform — strong ecosystem and AWS support.

### Structure
```
kitchen-infrastructure/
├── Pulumi.yaml
├── Pulumi.dev.yaml
├── Pulumi.staging.yaml
├── Pulumi.prod.yaml
├── __main__.py
├── README.md
├── docs/
│   ├── DEPLOYMENT_GUIDE.md
│   └── ROLLBACK_PROCEDURES.md
└── ...
```

### What to Provision (AWS)
- **VPC** — subnets, security groups
- **RDS PostgreSQL** — managed DB (or Aurora if preferred)
- **Compute** — EC2, ECS, or Lambda (depending on deployment model)
- **ALB** — route `/api/*` and `/health` to backend
- **Secrets Manager** — DB credentials, JWT secret, API keys, SMTP config
- **CloudWatch** — logs, alarms (5xx, DB CPU, connection issues)

### Deployment Pipeline
- CI/CD (e.g. GitHub Actions) runs `pulumi up` for each environment
- Separate stacks/state for dev, staging, prod
- Schema/migrations applied by backend CI or a dedicated DB job, not by Pulumi

### Multi-Cloud Readiness
- Abstract provider-specific resources (e.g. RDS vs Cloud SQL)
- Use Pulumi’s multi-cloud patterns to ease future GCP/Azure adoption

---

## 5. Integration Points

| Concern | Where it lives |
|--------|----------------|
| Infrastructure provisioning | New Pulumi repo |
| Database schema & migrations | This repo (`app/db/`) |
| Application code | This repo |
| Secrets | Infra repo provisions Secrets Manager; backend consumes at runtime |
| CI/CD for backend | This repo (or central pipeline) |
| CI/CD for infra | New Pulumi repo |

---

## 6. Migration from Current CloudFormation

The `infra/` folder in this repo contains CloudFormation templates that can serve as a reference:
- `infra/cloudformation/01-network.yml` through `05-alb.yml`
- `infra/scripts/deploy-all-stacks.sh`

Use these as a blueprint when implementing the Pulumi stacks. Do not copy YAML verbatim; define equivalent resources in Pulumi.

---

**Last Updated**: 2026-03-08  
**Maintained By**: Backend Team
