# Environment Setup Guide

This guide explains how to set up environment variables for the Kitchen Backend.

## Quick Start

Create a `.env` file in the project root with the following variables:

```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=kitchen_db_dev
DB_USER=kitchen_admin
DB_PASSWORD=your_database_password_here

# JWT Authentication
JWT_SECRET=your_jwt_secret_key_here_at_least_32_characters_long
JWT_ALGORITHM=HS256
JWT_EXPIRY_HOURS=24

# Email Service (Gmail SMTP for MVP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-specific-password
FROM_EMAIL=your-email@gmail.com
FROM_NAME=Kitchen Backend

# Frontend URL (for password reset links)
FRONTEND_URL=http://localhost:3000

# External API Keys
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
MERCADOPAGO_CLIENT_ID=your_mercadopago_client_id_here
MERCADOPAGO_CLIENT_SECRET=your_mercadopago_client_secret_here

# Application Settings
ENVIRONMENT=dev
DEBUG=true
LOG_LEVEL=INFO
```

---

## 📧 Email Service Setup (Gmail SMTP)

### Step 1: Create or Use Gmail Account

Use an existing Gmail account or create a new one specifically for the application.

### Step 2: Enable 2-Factor Authentication

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Click "2-Step Verification"
3. Follow the prompts to enable 2FA

### Step 3: Generate App-Specific Password

1. Go to [App Passwords](https://myaccount.google.com/apppasswords)
2. Select app: "Mail"
3. Select device: "Other (Custom name)"
4. Enter name: "Kitchen Backend"
5. Click "Generate"
6. Copy the 16-character password

### Step 4: Add to `.env`

```bash
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx  # The 16-char app password (spaces optional)
FROM_EMAIL=your-email@gmail.com
```

### Gmail Limits

- **Free Gmail**: 500 emails/day
- **Google Workspace**: 2,000 emails/day

For production, migrate to AWS SES (50,000 emails/day on free tier).

---

## 🔑 JWT Secret Generation

Generate a secure random JWT secret:

```bash
# Using Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Or using OpenSSL
openssl rand -base64 32
```

Add to `.env`:

```bash
JWT_SECRET=your_generated_secret_here
```

---

## 🗺️ Google Maps API Setup

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project: "Kitchen Backend"
3. Enable billing (required for API access, but free tier is generous)

### Step 2: Enable Geocoding API

1. Navigate to "APIs & Services" > "Library"
2. Search for "Geocoding API"
3. Click "Enable"

### Step 3: Create API Key

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "API Key"
3. Copy the API key

### Step 4: Restrict API Key (Security)

1. Click "Edit API key"
2. Under "API restrictions":
   - Select "Restrict key"
   - Choose "Geocoding API" only
3. (Optional) Under "Application restrictions":
   - Select "IP addresses"
   - Add your server's IP address
4. Click "Save"

### Step 5: Add to `.env`

```bash
GOOGLE_MAPS_API_KEY=AIza... (your API key)
```

### Google Maps Pricing

- **Free tier**: $200 credit/month (~28,500 geocoding requests)
- **After free tier**: $5 per 1,000 requests

For most MVPs, the free tier is sufficient.

---

## 💳 MercadoPago API Setup (Optional - Post-UAT)

### Step 1: Create MercadoPago Account

1. Go to [MercadoPago Developers](https://www.mercadopago.com.ar/developers/)
2. Sign up for a developer account

### Step 2: Get Credentials

1. Navigate to "Your integrations"
2. Create a new application
3. Copy:
   - Client ID
   - Client Secret
   - Access Token (for testing)

### Step 3: Add to `.env`

```bash
MERCADOPAGO_CLIENT_ID=your_client_id
MERCADOPAGO_CLIENT_SECRET=your_client_secret
MERCADOPAGO_ACCESS_TOKEN=your_access_token
```

**Note**: Currently blocked by permissions issue. This will be resolved post-UAT.

---

## 🗄️ Database Configuration

### Local Development

```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=kitchen_db_dev
DB_USER=kitchen_admin
DB_PASSWORD=your_password_here
```

### AWS RDS (Production)

After deploying to AWS:

```bash
DB_HOST=kitchen-db-prod.xxxxx.rds.amazonaws.com
DB_PORT=5432
DB_NAME=kitchen_db_prod
DB_USER=kitchen_admin
DB_PASSWORD=your_strong_password_here
```

Or use AWS Secrets Manager (recommended):

```bash
USE_AWS_SECRETS=true
AWS_REGION=us-east-1
```

The application will automatically fetch credentials from Secrets Manager.

---

## 🚀 Environment-Specific Configurations

### Development

```bash
ENVIRONMENT=dev
DEBUG=true
LOG_LEVEL=DEBUG
FRONTEND_URL=http://localhost:3000
```

### Staging

```bash
ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=INFO
FRONTEND_URL=https://staging.kitchen.com
```

### Production

```bash
ENVIRONMENT=prod
DEBUG=false
LOG_LEVEL=WARNING
FRONTEND_URL=https://app.kitchen.com
USE_AWS_SECRETS=true
```

---

## ✅ Validation

Test your environment configuration:

```bash
# Start the server
python3 -m uvicorn application:app --reload

# Check health endpoint
curl http://localhost:8000/health

# Test email service (after setup)
# Send a test password reset email
curl -X POST http://localhost:8000/api/v1/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

Check server logs for any configuration errors.

---

## 🔒 Security Best Practices

1. **Never commit `.env` to Git** (already in `.gitignore`)
2. **Use strong passwords** for database and JWT secret
3. **Restrict API keys** to only required APIs/IPs
4. **Rotate secrets regularly** (every 90 days recommended)
5. **Use AWS Secrets Manager in production** (not environment variables)

---

## 📚 Related Documentation

- [Start Server Guide](START_SERVER.md)
- [AWS Infrastructure Setup](infrastructure/AWS_INFRASTRUCTURE_SETUP.md)
- [Technical Roadmap](roadmap/TECHNICAL_ROADMAP_2026.md)

---

**Last Updated**: 2026-02-04  
**Maintained By**: Backend Team
