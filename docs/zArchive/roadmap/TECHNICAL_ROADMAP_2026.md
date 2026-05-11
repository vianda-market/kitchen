# Technical Roadmap 2026 - Kitchen Backend

**Last Updated**: 2026-02-04  
**Status**: Monorepo with AWS infrastructure ready for deployment  
**Priority**: Local development → UAT → AWS production deployment

---

## 🎯 Current State

### Repository Structure
```
kitchen/ (monorepo)
├── app/                        # Python backend code
│   ├── db/                     # SQL files (schema, migrations, functions)
│   ├── routes/                 # API endpoints
│   ├── services/               # Business logic
│   ├── tests/                  # Unit tests (322 passing!)
│   └── ...
├── infra/                      # AWS CloudFormation infrastructure
│   ├── cloudformation/         # 5 YAML files ready to deploy
│   ├── scripts/                # Deployment automation
│   └── README.md
├── docs/                       # Documentation
│   ├── infrastructure/         # AWS setup guides
│   ├── roadmap/                # Technical planning
│   └── ...
└── static/                     # Assets (QR codes, product images)
```

### Completed Features ✅
- ✅ User authentication (JWT, ABAC policies)
- ✅ Restaurant management
- ✅ Plate selection & pickup
- ✅ Credit currency system
- ✅ Subscription billing
- ✅ QR code generation
- ✅ Restaurant staff daily orders view
- ✅ Postman E2E test collection (36+ tests)
- ✅ UUIDv7 implementation
- ✅ AWS infrastructure (CloudFormation YAMLs)
- ✅ 322 unit tests passing

### Known Limitations ⚠️
- 🔴 Password recovery (DB tables exist, no API/service logic)
- 🔴 Geolocation (placeholder, needs Google Maps API)
- 🔴 Plate recommendation engine (no ML, manual filtering only)
- 🔴 MercadoPago (QR code only, no full integration - permissions issue)
- 🟡 AWS deployment (infrastructure ready, not deployed)
- 🟡 Email service (needs Gmail SMTP or AWS SES setup)

---

## 📋 Roadmap Phases

### **Phase 1: Local Development (Pre-UAT)** 🏃 IN PROGRESS

**Goal**: Complete MVP features for User Acceptance Testing (UAT)  
**Timeline**: 2-4 weeks  
**Priority**: HIGH

#### 1.1 Password Recovery 🔴 HIGH PRIORITY
**Status**: Database tables exist, needs implementation

**Tasks**:
- [ ] Create `app/services/password_recovery_service.py`
- [ ] Add routes to `app/routes/user_public.py`:
  - `POST /api/v1/auth/forgot-password` (send reset email)
  - `POST /api/v1/auth/reset-password` (validate token, update password)
- [ ] Email service implementation:
  - **MVP**: Gmail SMTP (free, quick setup)
  - **Post-UAT**: Migrate to AWS SES
- [ ] Update `credential_recovery` table (token generation, expiry)
- [ ] Unit tests for password recovery flow
- [ ] Postman collection tests

**Dependencies**:
- Gmail account with app-specific password OR
- AWS SES (after AWS deployment)

**Email Setup (MVP - Gmail SMTP)**:
```python
# app/services/email_service.py
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "kitchen-backend@gmail.com"
SMTP_PASSWORD = "app-specific-password"  # From Google Account settings
```

**Estimated Effort**: 1-2 days

---

#### 1.2 Geolocation API Integration 🔴 HIGH PRIORITY
**Status**: Placeholder functions, needs Google Maps API

**Tasks**:
- [ ] Set up Google Cloud Platform project
- [ ] Enable Google Maps Geocoding API
- [ ] Get API key (27K requests/month free)
- [ ] Update `app/services/geolocation_service.py`:
  - Replace placeholder with real Google API calls
  - `geocode_address()` → Google Geocoding API
  - `reverse_geocode()` → Google Reverse Geocoding
- [ ] Add distance calculation service:
  - `calculate_distance(lat1, lon1, lat2, lon2)` using Haversine formula
  - Client-side distance filtering (stateless)
- [ ] Update `app/config/settings.py` with API key
- [ ] Unit tests with mocked Google API responses
- [ ] Integration test with real API (dev only)

**Google API Setup**:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project: "Kitchen Backend"
3. Enable "Geocoding API"
4. Create API key, restrict to Geocoding API only
5. Add to `.env` or AWS Secrets Manager

**Estimated Effort**: 1 day

**Future Optimization** (Post-UAT):
- Evaluate switching to Mapbox (cheaper at scale)
- Implement caching for frequently geocoded addresses

---

#### 1.3 Plate Recommendation Engine (MVP) 🟡 MEDIUM PRIORITY
**Status**: Manual filtering only, needs basic recommendation logic

**MVP Approach** (Simple, no ML):
```python
def recommend_plates(user_id, max_distance_km=5):
    """
    Simple recommendation:
    1. Get user's last order location
    2. Filter plates within distance
    3. Prioritize latest plates (last 7 days)
    4. Return top 10
    """
    pass
```

**Tasks**:
- [ ] Create `app/services/recommendation_service.py`
- [ ] Implement distance-based filtering:
  - Get user's last order address
  - Calculate distance to all restaurants with today's plates
  - Filter by max distance (5km default)
- [ ] Add recency scoring:
  - Plates from last 7 days get priority
  - User's previously ordered plates get slight boost
- [ ] Add route: `GET /api/v1/plates/recommended`
- [ ] Index `plate_selection(user_id, created_date)` for performance
- [ ] Unit tests

**Estimated Effort**: 2 days

**Future Enhancement** (Post-UAT - ML-Powered):
- **Ingredient-based recommendations:** Recommend plates that share a significant overlap of ingredients with plates the user has favorited (e.g. user favorites plates with tomato, basil, mozzarella → boost plates with similar ingredient profiles). **Prerequisite:** Option A tabular schema (`ingredient_info`, `product_ingredient`) — see Phase 3.2.
- NoSQL DB (DynamoDB) for user preferences:
  - Cuisine preferences
  - Ingredient preferences
  - Restaurant preferences
  - Walk distance preference
- ML model for taste trends (population-level analysis)
- Order history analysis (last 6 months, not all history for UI)

---

#### 1.4 Transport Mode & Distance Filtering 🟡 MEDIUM PRIORITY
**Status**: Not implemented

**User Story**:
> "As a user, I want to indicate if I'm walking or riding a bike/scooter so I can see restaurants within my travel range and estimated time to destination."

**Tasks**:
- [ ] Add `transport_mode` to plate filtering:
  - `walk` (max 1.5 km)
  - `bike` (max 5 km)
  - `scooter` (max 10 km)
- [ ] Integrate Google Distance Matrix API:
  - Get estimated travel time
  - Return to client for display
- [ ] Update `GET /api/v1/plates/` query params:
  - `?transport_mode=walk&max_distance=1.5`
- [ ] Client-side filtering (stateless service)

**Estimated Effort**: 1 day

---

#### 1.5 Enhanced Testing 🟡 MEDIUM PRIORITY
**Status**: 322 unit tests passing, Postman has 36+ tests

**Tasks**:
- [ ] Add more Postman tests (target: 50+ tests)
- [ ] Create route duplication test (prevent conflicts like `/restaurants/{id}` vs `/restaurants/daily-orders`)
- [ ] Add integration tests for:
  - Password recovery flow
  - Geolocation API
  - Recommendation engine
- [ ] Performance benchmarks for key queries

**Estimated Effort**: Ongoing (2-3 days total)

---

### **Phase 2: AWS Deployment (Post-UAT)** ☁️ READY, NOT DEPLOYED

**Goal**: Deploy to production on AWS  
**Timeline**: 1 week  
**Priority**: MEDIUM (after UAT approval)

#### 2.1 Pre-Deployment Checklist
- [ ] **AWS Account Setup**:
  - [ ] Create AWS account (consider new email for 12-month free tier)
  - [ ] Set up billing alerts ($10, $50, $100)
  - [ ] Create IAM admin user
- [ ] **Parameter Configuration**:
  - [ ] Update `infra/cloudformation/parameters/prod.json`:
    - Strong database password
    - Your IP for SSH access
    - EC2 key pair name
  - [ ] Generate secrets:
    - JWT secret (64 characters)
    - Google Maps API key
    - MercadoPago credentials
    - Gmail app-specific password

#### 2.2 Infrastructure Deployment
**All CloudFormation YAMLs are ready in `infra/cloudformation/`**

```bash
# Deploy all stacks (automated)
cd infra
./scripts/deploy-all-stacks.sh prod

# Or deploy manually (step-by-step)
# See infra/README.md for detailed instructions
```

**Stacks**:
1. **Network** (`01-network.yml`): VPC, subnets, security groups
2. **Database** (`02-rds.yml`): RDS PostgreSQL
3. **Secrets** (`03-secrets.yml`): AWS Secrets Manager
4. **Compute** (`04-ec2.yml`): EC2 instance with Nginx
5. **Load Balancer** (`05-alb.yml`): Application Load Balancer

**Post-Deployment**:
- [ ] Update secrets with real values (JWT, API keys)
- [ ] Apply database schema: `psql -h <RDS_ENDPOINT> -f app/db/schema.sql`
- [ ] Test health endpoint: `curl http://<ALB_DNS>/health`
- [ ] Test API: `curl http://<ALB_DNS>/api/v1/`
- [ ] Configure DNS (optional): Point domain to ALB

**Cost Estimate**:
- Free tier (Year 1): ~$15/month (Secrets Manager only)
- After free tier: ~$41/month
- Production (recommended): ~$94/month (Multi-AZ, t3.small)

#### 2.3 Migrate Email to AWS SES
**After AWS deployment**:
- [ ] Set up AWS SES
- [ ] Verify domain or email address
- [ ] Update `app/services/email_service.py` to use SES
- [ ] Test password recovery emails

---

### **Phase 3: Post-UAT Enhancements** 🚀 FUTURE

**Goal**: Advanced features after initial launch  
**Timeline**: Ongoing  
**Priority**: LOW (after production is stable)

#### 3.1 MercadoPago Full Integration
**Status**: Blocked by permissions issue

**Tasks**:
- [ ] **Resolve MercadoPago permissions** (blocking issue)
  - Contact MercadoPago support
  - Verify app permissions in dashboard
  - Test webhook callbacks
- [ ] Implement full payment processing:
  - Payment creation API
  - Webhook handling for payment status
  - Refund processing
- [ ] Update billing service to use MercadoPago API (not just QR)
- [ ] Integration tests with MercadoPago sandbox

**Estimated Effort**: 3-5 days (after permissions resolved)

---

#### 3.2 ML-Powered Recommendation Engine
**Status**: Future enhancement

**Tasks**:
- [ ] Set up DynamoDB for user preferences:
  - Cuisine preferences
  - Ingredient preferences
  - Restaurant preferences
  - Walk distance preference
- [ ] **Option A: Tabular ingredient schema** (ingredient_info, product_ingredient):
  - Create `ingredient_info` and `product_ingredient` tables
  - Build ETL/cron to parse existing `product_info.ingredients` (comma-separated) and populate junction table (with normalization: lowercase, singular/plural handling)
  - Add admin UI or API for suppliers to manage product-ingredient links (optional; can start with ETL-only)
  - Update recommendation service to query `product_ingredient` for overlap scoring (e.g. `WHERE ingredient_id IN (SELECT ingredient_id FROM product_ingredient WHERE product_id IN (user_favorited_plate_products))`)
  - Keep `product_info.ingredients` for backward compatibility and display; ML reads from tabular tables
- [ ] Build cuisine database (NoSQL):
  - Cuisine categories
  - Allergen information
- [ ] ML model development:
  - Order history analysis (6-12 months)
  - Taste trend detection (population-level)
  - Collaborative filtering (user similarity)
- [ ] Deploy ML model (SageMaker or Lambda)
- [ ] Update recommendation service to use ML

**Estimated Effort**: 2-3 weeks

---

#### 3.3 Order History Optimization
**Status**: Basic functionality exists

**Tasks**:
- [ ] Index `plate_selection(user_id, created_date)` for efficient querying
- [ ] Implement pagination for order history API
- [ ] Time-based filtering:
  - UI: Show last 3 months by default
  - ML: Access all data for trend analysis
- [ ] Caching for frequently accessed orders

**Estimated Effort**: 1 day

---

#### 3.4 CI/CD Pipeline
**Status**: Not implemented

**Tasks**:
- [ ] GitHub Actions workflow:
  - Run unit tests on PR
  - Run linter (flake8, black)
  - Security scan (bandit)
- [ ] Automated deployment:
  - Deploy to staging on merge to `staging` branch
  - Deploy to prod on tag/release
- [ ] Database migration automation:
  - Apply migrations as part of deployment
- [ ] Rollback runbook

**Estimated Effort**: 2-3 days

---

#### 3.5 Repository Restructuring (Optional)
**Status**: Currently monorepo, can split when needed

**Future Split** (when team grows):
1. **kitchen-backend** - Python API code
2. **kitchen-database** - SQL schema, migrations, functions
3. **infrastructure** - CloudFormation YAMLs, deployment scripts

**When to split**:
- Hiring separate data engineer and backend engineer
- Database changes are frequent and independent
- Need separate release cycles

**See**:
- `docs/infrastructure/feedback_for_infra.md` - Infrastructure requirements and recommendations

---

## 🎯 Priority Decision Matrix

| Feature | Priority | Effort | UAT Blocking? | AWS Required? |
|---------|----------|--------|---------------|---------------|
| Password Recovery | 🔴 HIGH | 2 days | ✅ Yes | ❌ No (Gmail SMTP) |
| Geolocation API | 🔴 HIGH | 1 day | ✅ Yes | ❌ No |
| Recommendation (MVP) | 🟡 MEDIUM | 2 days | ⚠️ Nice to have | ❌ No |
| Transport Mode | 🟡 MEDIUM | 1 day | ⚠️ Nice to have | ❌ No |
| Enhanced Testing | 🟡 MEDIUM | 3 days | ⚠️ Nice to have | ❌ No |
| AWS Deployment | 🟡 MEDIUM | 1 week | ❌ No (post-UAT) | ✅ Yes |
| MercadoPago Full | 🟢 LOW | 5 days | ❌ No | ❌ No |
| ML Recommendations | 🟢 LOW | 3 weeks | ❌ No | ✅ Yes (DynamoDB) |
| CI/CD Pipeline | 🟢 LOW | 3 days | ❌ No | ✅ Yes |

---

## 📊 Recommended Next Steps

### Option A: Focus on UAT (Recommended)
**Goal**: Complete MVP features for user testing

1. ✅ **Implement Password Recovery** (2 days)
   - Use Gmail SMTP for MVP
   - Migrate to AWS SES later

2. ✅ **Integrate Google Maps API** (1 day)
   - Get API key
   - Replace placeholder functions

3. ✅ **Add Basic Recommendations** (2 days)
   - Distance + recency based
   - No ML required

4. ✅ **Enhanced Testing** (2-3 days)
   - More Postman tests
   - Route duplication check

**Total**: 1-2 weeks → Ready for UAT

---

### Option B: Deploy to AWS First
**Goal**: Get production infrastructure running

1. ✅ **AWS Account Setup** (1 day)
   - Create account
   - Configure billing alerts

2. ✅ **Deploy Infrastructure** (1 day)
   - Run `infra/scripts/deploy-all-stacks.sh prod`
   - Update secrets

3. ✅ **Apply Database Schema** (1 hour)
   - Connect to RDS
   - Run SQL files

4. ✅ **Configure Email Service** (2 hours)
   - Set up AWS SES
   - Or use Gmail SMTP initially

5. ✅ **Testing & Validation** (1 day)
   - Verify all endpoints
   - Load testing

**Total**: 1 week → Production ready (but missing password recovery)

---

## 🤔 Recommended Approach

**I recommend Option A** (Focus on UAT) for these reasons:

1. **User Validation First**: Get feedback on features before investing in AWS
2. **Local Development is Faster**: No AWS billing, quicker iteration
3. **Password Recovery is Critical**: Users expect this feature
4. **AWS is Ready When Needed**: Infrastructure is pre-built, can deploy in 1 day

**After UAT Approval** → Deploy to AWS (Option B) → Post-UAT enhancements (Phase 3)

---

## 📚 Documentation

### Infrastructure
- `infra/README.md` - AWS deployment guide (CloudFormation; infra moving to separate Pulumi repo)
- `docs/infrastructure/README.md` - Infrastructure documentation index
- `docs/infrastructure/feedback_for_infra.md` - Requirements for the new infrastructure repo

### Backend
- `docs/START_SERVER.md` - Local development setup
- `docs/CODING_GUIDELINES.md` - Code standards
- `CLAUDE.md` - AI development notes

### Testing
- `docs/testing/TESTING_STRATEGY.md` - Test approach
- `docs/TESTING_IMPROVEMENTS_COMPLETED.md` - Test improvements log
- `docs/postman/` - Postman collection & docs

---

## ✅ Success Criteria

### UAT Ready
- [x] 322 unit tests passing
- [ ] Password recovery functional
- [ ] Geolocation returning real data (not placeholder)
- [ ] Basic plate recommendations working
- [ ] 50+ Postman tests passing
- [ ] No critical bugs in E2E tests

### Production Ready (AWS)
- [ ] All CloudFormation stacks deployed
- [ ] Database schema applied
- [ ] Health check responding
- [ ] All API endpoints functional
- [ ] CloudWatch alarms configured
- [ ] SSL certificate installed (optional)

### Post-Launch
- [ ] MercadoPago full integration
- [ ] ML-powered recommendations
- [ ] CI/CD pipeline operational
- [ ] Monitoring and alerting stable

---

**Next Action**: Please decide:
- **Option A**: Focus on local development (password recovery, geolocation, recommendations)
- **Option B**: Deploy to AWS now (infrastructure is ready)

Let me know which direction you'd like to take! 🚀
