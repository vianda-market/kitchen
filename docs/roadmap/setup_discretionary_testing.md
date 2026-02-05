# Discretionary Credit System - Postman Testing Setup

## Quick Setup Guide

### 1. Database Setup
Ensure the database has been rebuilt with the super-admin role:

```bash
# Rebuild database with super-admin role
cd /Users/cdeachaval/Desktop/local/kitchen
source venv/bin/activate
psql -h localhost -U your_username -d your_database -f app/db/seed.sql
```

### 2. Environment Variables
Set up these environment variables in Postman:

```json
{
  "baseUrl": "http://localhost:8000",
  "adminUsername": "admin@example.com",
  "adminPassword": "your_admin_password",
  "superAdminUsername": "superadmin@example.com", 
  "superAdminPassword": "your_superadmin_password",
  "testUserId": "123e4567-e89b-12d3-a456-426614174000",
  "testRestaurantId": "456e7890-e89b-12d3-a456-426614174000"
}
```

### 3. Import Collection
1. Open Postman
2. Click "Import"
3. Select `DISCRETIONARY_CREDIT_SYSTEM.postman_collection.json`
4. Import the collection

### 4. Create Test Users
You'll need to create test users with the following roles:
- **Admin User**: `role_type: "Employee"`, `role_name: "Admin"`
- **Super Admin User**: `role_type: "Employee"`, `role_name: "Super Admin"`

### 5. Run Tests
Execute the collection in this order:

1. **Authentication** → Login Admin
2. **Authentication** → Login Super Admin  
3. **Admin Operations** → Create Client Credit Request
4. **Admin Operations** → Create Restaurant Credit Request
5. **Super Admin Operations** → Get Pending Requests
6. **Super Admin Operations** → Approve Client Credit Request
7. **Super Admin Operations** → Reject Restaurant Credit Request
8. **Super Admin Operations** → Get All Requests Overview

## Expected Results

### ✅ Success Indicators
- All requests return 200 status codes
- Authentication tokens are properly set
- Request IDs are captured and reused
- Status transitions work correctly (Pending → Approved/Rejected)
- Error scenarios return appropriate 400/401/403/404 status codes

### ❌ Common Issues
- **401 Unauthorized**: Check username/password
- **403 Forbidden**: Verify user has correct role
- **404 Not Found**: Check if test user/restaurant IDs exist
- **500 Internal Server Error**: Check database connectivity

## Test Data Validation

After running the tests, verify in the database:

```sql
-- Check discretionary requests
SELECT * FROM discretionary_info WHERE discretionary_id IN (
  '{{clientCreditRequestId}}',
  '{{restaurantCreditRequestId}}'
);

-- Check resolutions
SELECT * FROM discretionary_resolution_info WHERE discretionary_id IN (
  '{{clientCreditRequestId}}',
  '{{restaurantCreditRequestId}}'
);

-- Check transactions (if approved)
SELECT * FROM client_transaction WHERE discretionary_id = '{{clientCreditRequestId}}';
SELECT * FROM restaurant_transaction WHERE discretionary_id = '{{restaurantCreditRequestId}}';
```

## Performance Benchmarks

- **Authentication**: < 2 seconds
- **Request Creation**: < 3 seconds  
- **Request Retrieval**: < 2 seconds
- **Approval/Rejection**: < 4 seconds

## Troubleshooting

### Database Issues
```bash
# Check if tables exist
psql -h localhost -U your_username -d your_database -c "\dt discretionary*"

# Check if super-admin user exists (role_info table deprecated - roles are now enums)
psql -h localhost -U your_username -d your_database -c "SELECT * FROM user_info WHERE role_type = 'Employee' AND role_name = 'Super Admin';"
```

### API Issues
```bash
# Check if API is running
curl http://localhost:8000/health

# Check discretionary endpoints
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/admin/discretionary/requests/
```

### Authentication Issues
- Verify user credentials in database
- Check if user has correct role assigned
- Ensure JWT secret is properly configured
- Verify token expiration settings

## Next Steps

After successful Postman testing:

1. **Integration Testing**: Test with real user data
2. **Load Testing**: Test with multiple concurrent requests
3. **Security Testing**: Test with invalid tokens and malformed requests
4. **Performance Testing**: Test with large datasets
5. **User Acceptance Testing**: Test with actual business users

## Support

For issues with the discretionary credit system:
1. Check the unit tests: `pytest app/tests/services/test_discretionary_service.py -v`
2. Check the service logs for detailed error messages
3. Verify database schema and data integrity
4. Review the comprehensive Postman guide for detailed troubleshooting
