# Discretionary Credit System - Quick Setup Guide

## 🚀 Quick Start

### 1. Run the Enhanced Seed Script
```bash
cd /Users/cdeachaval/Desktop/local/kitchen
source venv/bin/activate
RUN_SEED=true python .seed_data.py
```

This will create:
- ✅ **Super Admin Role** - `dddddddd-dddd-dddd-dddd-dddddddddddd`
- ✅ **Admin User** - `admin` / `admin_password`
- ✅ **Super Admin User** - `superadmin@example.com` / `super_secret`

**Note**: The database seed.sql file has been updated with the correct hashed passwords!

### 2. Start the API Server
```bash
cd /Users/cdeachaval/Desktop/local/kitchen
source venv/bin/activate
uvicorn application:app --reload --host 0.0.0.0 --port 8000
```

### 3. Import Postman Collection
1. Open Postman
2. Click **"Import"**
3. Select `docs/postman/DISCRETIONARY_CREDIT_SYSTEM.postman_collection.json`
4. Import the collection

### 4. Set Up Environment Variables
Create a new environment in Postman with these variables:

```json
{
  "baseUrl": "http://localhost:8000",
  "adminUsername": "admin",
  "adminPassword": "admin_password",
  "superAdminUsername": "superadmin@example.com",
  "superAdminPassword": "super_secret",
  "testUserId": "123e4567-e89b-12d3-a456-426614174000",
  "testRestaurantId": "456e7890-e89b-12d3-a456-426614174000"
}
```

### 5. Run the Tests
Execute the collection in this order:

1. **🔐 Authentication** → Login Admin
2. **🔐 Authentication** → Login Super Admin
3. **👤 Admin Operations** → Create Client Credit Request
4. **👤 Admin Operations** → Create Restaurant Credit Request
5. **🔍 Super Admin Operations** → Get Pending Requests
6. **🔍 Super Admin Operations** → Approve Client Credit Request
7. **🔍 Super Admin Operations** → Reject Restaurant Credit Request
8. **🔍 Super Admin Operations** → Get All Requests Overview

## ✅ Expected Results

### Success Indicators:
- All requests return **200** status codes
- Authentication tokens are captured automatically
- Request IDs are stored and reused
- Status transitions work (Pending → Approved/Rejected)
- Error tests return appropriate **400/401/403/404** codes

### Test Coverage:
- **Authentication** - Admin and Super-Admin login
- **CRUD Operations** - Create, read, update requests
- **Business Logic** - Approval/rejection workflows
- **Error Scenarios** - Invalid data, authorization, not found
- **Security** - Role-based access control

## 🛠️ Troubleshooting

### Common Issues:

#### 401 Unauthorized
- Check username/password in environment variables
- Verify users exist in database

#### 403 Forbidden
- Verify user has correct role (Admin/Super Admin)
- Check role assignments in database

#### 404 Not Found
- Check if test user/restaurant IDs exist
- Verify API endpoints are correct

#### 500 Internal Server Error
- Check database connectivity
- Verify discretionary tables exist

### Debug Steps:
1. **Check API Health**: `curl http://localhost:8000/health`
2. **Verify Database**: Check if users and roles exist
3. **Check Logs**: Look at API server logs for errors
4. **Test Authentication**: Try login manually first

## 📊 What Gets Tested

### Complete Workflow:
1. **Admin creates** discretionary credit request
2. **Super-admin reviews** pending requests
3. **Super-admin approves** client credit request
4. **Super-admin rejects** restaurant credit request
5. **System creates** transactions automatically
6. **Balances updated** via existing services

### Business Logic:
- **Request validation** - Amount, category, reason validation
- **Status transitions** - Pending → Approved/Rejected
- **Role-based access** - Admin vs Super-Admin permissions
- **Transaction creation** - Automatic credit loading
- **Audit trail** - Complete request history

## 🎯 Ready to Test!

The discretionary credit system is now **fully set up and ready for testing**! 

Run the seed script, start the API, import the Postman collection, and execute the tests to see the complete system in action! 🚀
