# Password Recovery API

**Status**: ✅ Implemented  
**Version**: v1  
**Last Updated**: 2026-02-04

---

## Overview

The password recovery feature allows users to reset their forgotten passwords via email.

**Flow**:
1. User requests password reset → Email sent with token
2. User clicks link in email → Token validated
3. User submits new password → Password updated

---

## API Endpoints

### 1. Request Password Reset

**POST** `/api/v1/auth/forgot-password`

**Description**: Request a password reset link to be sent via email.

**Authentication**: None (public endpoint)

**Request Body**:
```json
{
  "email": "user@example.com"
}
```

**Success Response** (200 OK):
```json
{
  "success": true,
  "message": "If an account with that email exists, a password reset link has been sent."
}
```

**Security Note**: This endpoint always returns success, even if the email doesn't exist. This prevents email enumeration attacks.

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "john.doe@example.com"}'
```

---

### 2. Reset Password

**POST** `/api/v1/auth/reset-password`

**Description**: Reset password using the token from the email link.

**Authentication**: None (public endpoint, token validation required)

**Request Body**:
```json
{
  "token": "abc123...xyz789",
  "new_password": "MyNewSecurePassword123!"
}
```

**Success Response** (200 OK):
```json
{
  "success": true,
  "message": "Password reset successful. You can now log in with your new password."
}
```

**Error Response** (400 Bad Request):
```json
{
  "detail": "Invalid or expired reset token."
}
```

**Validation Rules**:
- `token`: Required, non-empty string
- `new_password`: Minimum 8 characters

**Token Constraints**:
- Valid for 24 hours
- Can only be used once
- Automatically invalidated after use

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "token": "abc123...xyz789",
    "new_password": "MyNewSecurePassword123!"
  }'
```

---

## Email Template

### Subject
```
Reset Your Kitchen Password
```

### HTML Body
```html
<!DOCTYPE html>
<html>
<body>
  <h1>Reset Your Password</h1>
  <p>Hi {{user_first_name}},</p>
  <p>You requested to reset your password for your Kitchen account.</p>
  <a href="{{reset_link}}">Reset Password</a>
  <p>This link will expire in 24 hours.</p>
  <p>If you didn't request this, please ignore this email.</p>
</body>
</html>
```

**Reset Link Format**:
```
http://localhost:3000/reset-password?token=abc123...xyz789
```

---

## Database Schema

### Table: `credential_recovery`

```sql
CREATE TABLE credential_recovery (
    credential_recovery_id UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    user_id UUID NOT NULL REFERENCES user_info(user_id),
    recovery_token VARCHAR(255) NOT NULL,
    token_expiry TIMESTAMP NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    used_date TIMESTAMP,
    status VARCHAR(50),
    is_archived BOOLEAN DEFAULT FALSE,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_credential_recovery_token ON credential_recovery(recovery_token);
CREATE INDEX idx_credential_recovery_user_id ON credential_recovery(user_id);
```

---

## Security Features

### 1. Email Enumeration Prevention
The API always returns success, preventing attackers from discovering valid email addresses.

### 2. Secure Token Generation
Tokens are generated using `secrets.token_urlsafe(64)` (cryptographically secure random).

### 3. Token Expiry
Tokens automatically expire after 24 hours.

### 4. Single-Use Tokens
Each token can only be used once. After use, it's marked as `is_used=TRUE`.

### 5. Token Invalidation
When a new reset is requested, all previous unused tokens for that user are invalidated.

### 6. Password Hashing
New passwords are hashed using bcrypt before storage.

---

## Configuration

### Environment Variables

```bash
# Email Service (Gmail SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
FROM_EMAIL=your-email@gmail.com
FROM_NAME=Kitchen Backend

# Frontend URL
FRONTEND_URL=http://localhost:3000
```

### Gmail Setup

See [ENV_SETUP.md](../ENV_SETUP.md) for detailed Gmail SMTP configuration.

---

## Testing

### Manual Testing

#### 1. Request Password Reset
```bash
# Request reset
curl -X POST http://localhost:8000/api/v1/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# Check email inbox for reset link
```

#### 2. Reset Password
```bash
# Use token from email
curl -X POST http://localhost:8000/api/v1/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "token": "TOKEN_FROM_EMAIL",
    "new_password": "NewPassword123!"
  }'
```

#### 3. Login with New Password
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "NewPassword123!"
  }'
```

### Postman Collection

See `docs/postman/collections/E2E Plate Selection.postman_collection.json`:
- "Forgot Password" request
- "Reset Password" request

---

## Error Handling

### Common Errors

**Invalid Email Format**:
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

**Weak Password**:
```json
{
  "detail": [
    {
      "loc": ["body", "new_password"],
      "msg": "ensure this value has at least 8 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

**Invalid/Expired Token**:
```json
{
  "detail": "Invalid or expired reset token."
}
```

**Email Service Not Configured**:
```
Email sent successfully = False
(Check server logs for SMTP configuration issues)
```

---

## Maintenance

### Cleanup Expired Tokens

Run periodically (e.g., daily cron job):

```python
from app.services.password_recovery_service import password_recovery_service

archived_count = password_recovery_service.cleanup_expired_tokens(db)
print(f"Archived {archived_count} expired tokens")
```

Or via cron:
```bash
0 2 * * * python3 /opt/kitchen-backend/scripts/cleanup_expired_tokens.py
```

---

## Migration to AWS SES (Post-UAT)

After deploying to AWS:

1. **Set up AWS SES**:
   - Verify domain or email address
   - Request production access (50,000 emails/day free)

2. **Update email service**:
   ```python
   # app/services/email_service.py
   import boto3
   
   class EmailService:
       def __init__(self):
           if os.getenv('USE_AWS_SES') == 'true':
               self.ses_client = boto3.client('ses', region_name='us-east-1')
           else:
               # Use Gmail SMTP
   ```

3. **Update environment**:
   ```bash
   USE_AWS_SES=true
   AWS_REGION=us-east-1
   ```

---

## Monitoring

### Metrics to Track

- Password reset requests per day
- Successful resets per day
- Failed reset attempts (invalid/expired tokens)
- Email delivery failures

### CloudWatch Logs

```bash
# View email service logs
tail -f /var/log/kitchen-backend.log | grep "Email sent"
```

---

## FAQ

**Q: What happens if user requests multiple resets?**  
A: Previous unused tokens are invalidated. Only the latest token is valid.

**Q: Can I customize the token expiry time?**  
A: Yes, modify `token_expiry_hours` in `PasswordRecoveryService.__init__()`.

**Q: Does this work with social login (Google, Facebook)?**  
A: No. Social login users should use their provider's password reset.

**Q: How many emails can I send per day with Gmail?**  
A: 500 emails/day for free Gmail accounts. Upgrade to AWS SES for higher limits.

---

## Related Documentation

- [ENV_SETUP.md](../ENV_SETUP.md) - Environment configuration
- [Authentication API](AUTH.md) - Login/logout endpoints
- [Email Service](../services/EMAIL_SERVICE.md) - Email service details

---

**Implemented By**: Backend Team  
**Reviewed By**: Pending  
**Status**: Ready for UAT
