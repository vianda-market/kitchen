# Kitchen Infrastructure

AWS infrastructure for the Kitchen platform using CloudFormation.

## 📁 Structure

```
infra/
├── cloudformation/
│   ├── 01-network.yml           # VPC, subnets, security groups
│   ├── 02-rds.yml               # PostgreSQL RDS database
│   ├── 03-secrets.yml           # AWS Secrets Manager
│   ├── 04-ec2.yml               # Backend API server
│   ├── 05-alb.yml               # Application Load Balancer
│   └── parameters/
│       ├── dev.json             # Development environment
│       ├── staging.json         # Staging environment
│       └── prod.json            # Production environment
├── scripts/
│   └── deploy-all-stacks.sh    # Deploy all stacks in order
└── README.md
```

## 🚀 Quick Start

### Prerequisites

1. **AWS CLI** installed and configured:
   ```bash
   aws configure
   # Enter your AWS Access Key ID, Secret Access Key, and Region
   ```

2. **jq** installed (for JSON processing):
   ```bash
   # macOS
   brew install jq
   
   # Linux
   sudo apt-get install jq
   ```

3. **AWS Account** with appropriate permissions

### Deploy All Stacks

```bash
# Deploy to dev environment
cd infra
./scripts/deploy-all-stacks.sh dev

# Deploy to staging
./scripts/deploy-all-stacks.sh staging

# Deploy to production (requires confirmation)
./scripts/deploy-all-stacks.sh prod
```

### Deploy Individual Stacks

```bash
# Set environment
ENVIRONMENT=dev
REGION=us-east-1

# 1. Network
aws cloudformation create-stack \
  --stack-name kitchen-network-${ENVIRONMENT} \
  --template-body file://cloudformation/01-network.yml \
  --parameters file://cloudformation/parameters/${ENVIRONMENT}.json \
  --region ${REGION}

# 2. Database
aws cloudformation create-stack \
  --stack-name kitchen-database-${ENVIRONMENT} \
  --template-body file://cloudformation/02-rds.yml \
  --parameters file://cloudformation/parameters/${ENVIRONMENT}.json \
       ParameterKey=NetworkStackName,ParameterValue=kitchen-network-${ENVIRONMENT} \
  --region ${REGION}

# 3. Secrets
aws cloudformation create-stack \
  --stack-name kitchen-secrets-${ENVIRONMENT} \
  --template-body file://cloudformation/03-secrets.yml \
  --parameters file://cloudformation/parameters/${ENVIRONMENT}.json \
       ParameterKey=DatabaseStackName,ParameterValue=kitchen-database-${ENVIRONMENT} \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --region ${REGION}

# 4. Compute (EC2)
aws cloudformation create-stack \
  --stack-name kitchen-compute-${ENVIRONMENT} \
  --template-body file://cloudformation/04-ec2.yml \
  --parameters file://cloudformation/parameters/${ENVIRONMENT}.json \
       ParameterKey=NetworkStackName,ParameterValue=kitchen-network-${ENVIRONMENT} \
       ParameterKey=SecretsStackName,ParameterValue=kitchen-secrets-${ENVIRONMENT} \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --region ${REGION}

# 5. Load Balancer
aws cloudformation create-stack \
  --stack-name kitchen-loadbalancer-${ENVIRONMENT} \
  --template-body file://cloudformation/05-alb.yml \
  --parameters file://cloudformation/parameters/${ENVIRONMENT}.json \
       ParameterKey=NetworkStackName,ParameterValue=kitchen-network-${ENVIRONMENT} \
       ParameterKey=ComputeStackName,ParameterValue=kitchen-compute-${ENVIRONMENT} \
  --region ${REGION}
```

## ⚙️ Configuration

### Update Parameters

Edit the appropriate parameter file:

```bash
# Dev
vim infra/cloudformation/parameters/dev.json

# Staging
vim infra/cloudformation/parameters/staging.json

# Production
vim infra/cloudformation/parameters/prod.json
```

**Important Parameters to Update**:

- `DBMasterPassword`: Change from placeholder to strong password
- `SSHAccessCIDR`: Restrict to your IP (production)
- `KeyPairName`: Add EC2 key pair for SSH access
- `CertificateArn`: Add SSL certificate ARN for HTTPS
- `GitHubRepoURL`: Update if using a fork

### Update Secrets

After deployment, update placeholder secrets:

```bash
ENVIRONMENT=dev

# Database credentials (update password)
aws secretsmanager update-secret \
  --secret-id kitchen/${ENVIRONMENT}/database/credentials \
  --secret-string '{
    "host": "kitchen-db-dev.xxx.rds.amazonaws.com",
    "port": 5432,
    "username": "kitchen_admin",
    "password": "YOUR_ACTUAL_PASSWORD",
    "database": "kitchen_db_dev"
  }'

# Backend API keys
aws secretsmanager update-secret \
  --secret-id kitchen/${ENVIRONMENT}/backend/api-keys \
  --secret-string '{
    "jwt_secret": "GENERATE_64_CHAR_RANDOM_STRING",
    "google_maps_api_key": "AIza...",
    "mercadopago_client_id": "...",
    "mercadopago_client_secret": "..."
  }'

# Email configuration
aws secretsmanager update-secret \
  --secret-id kitchen/${ENVIRONMENT}/email/config \
  --secret-string '{
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_username": "your-email@gmail.com",
    "smtp_password": "your-app-specific-password",
    "from_email": "your-email@gmail.com"
  }'
```

## 🗄️ Database Schema Deployment

After RDS is created, apply the database schema:

```bash
# Get database endpoint
DB_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name kitchen-database-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`DBInstanceEndpoint`].OutputValue' \
  --output text)

# Apply schema
psql -h $DB_ENDPOINT \
     -U kitchen_admin \
     -d kitchen_db_dev \
     -f ../app/db/schema.sql

# Enter password when prompted
```

Or use the full schema application:

```bash
# Apply all SQL files in order
for sql_file in ../app/db/{uuid7_function,schema,index,trigger}.sql; do
  echo "Applying: $sql_file"
  psql -h $DB_ENDPOINT -U kitchen_admin -d kitchen_db_dev -f "$sql_file"
done
```

## 🧪 Testing the Deployment

```bash
# Get ALB DNS
ALB_DNS=$(aws cloudformation describe-stacks \
  --stack-name kitchen-loadbalancer-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerDNS`].OutputValue' \
  --output text)

# Test health endpoint
curl http://$ALB_DNS/health

# Test API
curl http://$ALB_DNS/api/v1/
```

## 📊 Monitoring

### CloudWatch Alarms

Alarms are automatically created for:

- **Database**: High CPU, low storage, high connections, read latency
- **ALB**: High 5xx errors, unhealthy targets, high response time

View alarms:

```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix kitchen- \
  --region us-east-1
```

### Logs

View EC2 bootstrap logs:

```bash
# SSH into EC2
ssh -i ~/.ssh/your-key.pem ec2-user@<PUBLIC_IP>

# View user-data log
sudo tail -f /var/log/user-data.log

# View backend application log
sudo tail -f /var/log/kitchen-backend.log
```

## 🔄 Updating Stacks

```bash
# Update a stack
aws cloudformation update-stack \
  --stack-name kitchen-network-dev \
  --template-body file://cloudformation/01-network.yml \
  --parameters file://cloudformation/parameters/dev.json

# Wait for update
aws cloudformation wait stack-update-complete \
  --stack-name kitchen-network-dev
```

## 🗑️ Deleting Stacks

**Warning**: This will delete all resources!

```bash
ENVIRONMENT=dev

# Delete in reverse order
aws cloudformation delete-stack --stack-name kitchen-loadbalancer-${ENVIRONMENT}
aws cloudformation delete-stack --stack-name kitchen-compute-${ENVIRONMENT}
aws cloudformation delete-stack --stack-name kitchen-secrets-${ENVIRONMENT}
aws cloudformation delete-stack --stack-name kitchen-database-${ENVIRONMENT}  # Creates final snapshot
aws cloudformation delete-stack --stack-name kitchen-network-${ENVIRONMENT}
```

## 💰 Cost Estimate

### Free Tier (First 12 Months)

- EC2 t2.micro: **FREE** (750 hours/month)
- RDS db.t3.micro: **FREE** (750 hours/month)
- ALB: **FREE** (750 hours/month)
- Secrets Manager: **~$1.20/month** (3 secrets × $0.40)
- **Total**: **~$15/year**

### After Free Tier

- EC2 t2.micro: $8.50/month
- RDS db.t3.micro: $15/month
- ALB: $16/month
- Secrets Manager: $1.20/month
- **Total**: **~$41/month** (~$500/year)

### Production (Recommended)

- EC2 t3.small: $17/month
- RDS db.t3.small (Multi-AZ): $60/month
- ALB: $16/month
- Secrets Manager: $1.20/month
- **Total**: **~$94/month** (~$1,128/year)

## 🔒 Security Best Practices

1. **Restrict SSH Access**: Update `SSHAccessCIDR` to your IP only
2. **Use Strong Passwords**: Change all placeholder passwords
3. **Enable SSL**: Add ACM certificate ARN to parameters
4. **Rotate Secrets**: Regularly rotate database passwords and API keys
5. **Monitor Alarms**: Set up SNS notifications for CloudWatch alarms
6. **Review Security Groups**: Ensure minimum necessary access

## 📚 Related Documentation

- [AWS CloudFormation Docs](https://docs.aws.amazon.com/cloudformation/)
- [AWS RDS PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html)
- [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/)
- [Backend Setup](../docs/START_SERVER.md)

## ❓ Troubleshooting

### Stack Creation Failed

```bash
# View stack events
aws cloudformation describe-stack-events \
  --stack-name kitchen-network-dev \
  --max-items 20

# View detailed error
aws cloudformation describe-stack-resources \
  --stack-name kitchen-network-dev
```

### EC2 Instance Not Healthy

```bash
# SSH into instance
ssh -i ~/.ssh/your-key.pem ec2-user@<PUBLIC_IP>

# Check user-data execution
sudo tail -100 /var/log/user-data.log

# Check backend application
sudo supervisorctl status kitchen-backend
sudo tail -100 /var/log/kitchen-backend.log

# Check Nginx
sudo systemctl status nginx
sudo tail -50 /var/log/nginx/error.log
```

### Database Connection Issues

```bash
# Test connection from EC2
psql -h $DB_ENDPOINT -U kitchen_admin -d kitchen_db_dev

# Check security group rules
aws ec2 describe-security-groups \
  --group-ids <RDS_SECURITY_GROUP_ID>
```

## 🤝 Support

For issues or questions:
1. Check CloudWatch logs
2. Review CloudFormation stack events
3. Consult AWS documentation
4. Open issue in repository

---

**Version**: 1.0  
**Last Updated**: 2026-02-04  
**Maintainer**: Christian de Achaval
