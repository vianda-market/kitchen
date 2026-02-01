# Discretionary Credit System - Postman E2E Testing Guide

## Overview

This Postman collection provides comprehensive end-to-end testing for the Discretionary Credit System, covering all admin and super-admin operations, error scenarios, and authorization tests.

## Collection Structure

### 🔐 Authentication
- **Login Admin** - Authenticate as admin user
- **Login Super Admin** - Authenticate as super-admin user

### 👤 Admin Operations
- **Create Client Credit Request** - Create discretionary credit request for client
- **Create Restaurant Credit Request** - Create discretionary credit request for restaurant
- **Get Admin Requests** - Retrieve all requests created by the admin
- **Update Pending Request** - Update a pending request (only if still pending)

### 🔍 Super Admin Operations
- **Get Pending Requests** - Retrieve all pending requests for approval/rejection
- **Get Request Details** - Get detailed information about a specific request
- **Approve Client Credit Request** - Approve a request and load credits
- **Reject Restaurant Credit Request** - Reject a request with reason
- **Get All Requests Overview** - Get comprehensive overview of all requests

### ❌ Error Scenarios
- **Create Request - Invalid Amount** - Test validation with negative amount
- **Create Request - Invalid Category** - Test validation with invalid category
- **Approve Non-Existent Request** - Test 404 error handling
- **Approve Already Processed Request** - Test status validation

### 🔒 Authorization Tests
- **Admin Access Super Admin Endpoint** - Test role-based access control
- **Unauthorized Access** - Test authentication requirements

## Environment Variables

### Required Variables
```json
{
  "baseUrl": "http://localhost:8000",
  "adminUsername": "admin@example.com",
  "adminPassword": "admin_password",
  "superAdminUsername": "superadmin@example.com",
  "superAdminPassword": "superadmin_password",
  "testUserId": "123e4567-e89b-12d3-a456-426614174000",
  "testRestaurantId": "456e7890-e89b-12d3-a456-426614174000"
}
```

### Auto-Generated Variables
The collection automatically sets these variables during execution:
- `adminAuthToken` - Admin authentication token
- `superAdminAuthToken` - Super-admin authentication token
- `clientCreditRequestId` - ID of created client credit request
- `restaurantCreditRequestId` - ID of created restaurant credit request
- `clientApprovalResolutionId` - ID of client request approval resolution
- `restaurantRejectionResolutionId` - ID of restaurant request rejection resolution

## Test Scenarios

### 1. Complete Workflow Test
**Run these requests in order:**
1. Login Admin
2. Create Client Credit Request
3. Create Restaurant Credit Request
4. Login Super Admin
5. Get Pending Requests
6. Approve Client Credit Request
7. Reject Restaurant Credit Request
8. Get All Requests Overview

### 2. Admin Operations Test
**Run these requests in order:**
1. Login Admin
2. Create Client Credit Request
3. Get Admin Requests
4. Update Pending Request
5. Get Admin Requests (verify update)

### 3. Error Handling Test
**Run these requests individually:**
1. Create Request - Invalid Amount
2. Create Request - Invalid Category
3. Approve Non-Existent Request
4. Approve Already Processed Request

### 4. Authorization Test
**Run these requests individually:**
1. Admin Access Super Admin Endpoint
2. Unauthorized Access

## Expected Results

### Successful Operations
- **Status Code**: 200
- **Response Time**: < 5000ms
- **Content Type**: application/json
- **Required Fields**: Present in response

### Error Scenarios
- **Validation Errors**: 400 status with descriptive error messages
- **Not Found Errors**: 404 status with entity identification
- **Authorization Errors**: 401/403 status with access control messages

### Business Logic Validation
- **Request Creation**: Proper validation, status set to "Pending"
- **Request Approval**: Status changes to "Approved", resolution created
- **Request Rejection**: Status changes to "Rejected", resolution created
- **Credit Loading**: Transactions created automatically (verified via existing services)

## Test Data

### Valid Request Categories
- `client_refund` - Refund for client issues
- `restaurant_refund` - Refund for restaurant issues
- `promotion` - Promotional credits
- `compensation` - Compensation credits

### Valid Request Reasons
- `service_issue` - Service-related problems
- `quality_complaint` - Quality-related complaints
- `promotion` - Promotional reasons
- `compensation` - Compensation reasons
- `other` - Other reasons

### Sample Request Bodies

#### Client Credit Request
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "category": "client_refund",
  "reason": "service_issue",
  "amount": 15.50,
  "comment": "Customer service issue resolved - late delivery compensation"
}
```

#### Restaurant Credit Request
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "restaurant_id": "456e7890-e89b-12d3-a456-426614174000",
  "category": "restaurant_refund",
  "reason": "quality_complaint",
  "amount": 25.00,
  "comment": "Restaurant quality issue - food preparation delay"
}
```

## Troubleshooting

### Common Issues

#### Authentication Failures
- **Issue**: 401 Unauthorized errors
- **Solution**: Verify username/password in environment variables
- **Check**: Ensure user roles are properly set in database

#### Validation Errors
- **Issue**: 400 Bad Request with validation messages
- **Solution**: Check request body format and required fields
- **Check**: Verify UUID format and valid enum values

#### Database Errors
- **Issue**: 500 Internal Server Error
- **Solution**: Check database connectivity and table existence
- **Check**: Verify discretionary_info and discretionary_resolution_info tables exist

#### Role Access Issues
- **Issue**: 403 Forbidden errors
- **Solution**: Verify user has correct role (Admin/Super Admin)
- **Check**: Ensure super-admin role exists in database

### Debug Steps

1. **Check Environment Variables**
   ```javascript
   console.log("Base URL:", pm.environment.get("baseUrl"));
   console.log("Admin Token:", pm.environment.get("adminAuthToken"));
   ```

2. **Verify Request Headers**
   ```javascript
   console.log("Request Headers:", pm.request.headers);
   ```

3. **Check Response Details**
   ```javascript
   console.log("Response Status:", pm.response.status);
   console.log("Response Body:", pm.response.json());
   ```

## Integration with Existing System

### Database Dependencies
- **discretionary_info** table - Stores credit requests
- **discretionary_history** table - Stores credit request history
- **discretionary_resolution_info** table - Stores approval/rejection decisions
- **discretionary_resolution_history** table - Stores resolution history
- **client_transaction** table - Stores client credit transactions
- **restaurant_transaction** table - Stores restaurant credit transactions
- **role_info** table - Contains super-admin role definition

### Service Dependencies
- **DiscretionaryService** - Business logic for request management
- **CreditLoadingService** - Business logic for transaction creation
- **CRUD Services** - Database operations
- **Authentication Service** - User authentication and authorization

### Balance Management
- **Client Credits** - Automatically update user subscription balance
- **Restaurant Credits** - Automatically update restaurant balance
- **Transaction History** - Complete audit trail maintained

## Performance Expectations

### Response Times
- **Authentication**: < 2 seconds
- **Request Creation**: < 3 seconds
- **Request Retrieval**: < 2 seconds
- **Approval/Rejection**: < 4 seconds (includes transaction creation)

### Throughput
- **Concurrent Requests**: Test with multiple admin users
- **Batch Operations**: Test with multiple pending requests
- **Database Load**: Monitor transaction creation performance

## Security Considerations

### Authentication
- **Token Expiration**: Tokens expire after configured time
- **Role Validation**: Each endpoint validates user role
- **Request Ownership**: Admins can only access their own requests

### Data Validation
- **Input Sanitization**: All inputs validated and sanitized
- **UUID Validation**: Proper UUID format required
- **Amount Validation**: Positive amounts only
- **Enum Validation**: Valid categories and reasons only

### Audit Trail
- **Request History**: Complete request lifecycle tracked
- **Approval History**: All approvals/rejections logged
- **Transaction History**: Credit loading transactions recorded
- **User Tracking**: All actions tied to authenticated users

## Maintenance

### Regular Testing
- **Daily**: Run complete workflow test
- **Weekly**: Run all error scenarios
- **Monthly**: Run performance and load tests

### Updates Required
- **New Categories**: Update test data and validation
- **New Reasons**: Update test data and validation
- **API Changes**: Update request/response formats
- **Database Changes**: Update test data and dependencies

### Monitoring
- **Response Times**: Monitor for performance degradation
- **Error Rates**: Monitor for increased error rates
- **Database Performance**: Monitor transaction creation performance
- **Authentication Issues**: Monitor for authentication failures
