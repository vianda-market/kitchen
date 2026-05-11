# Password Recovery - Client Implementation Guide

**Status**: ✅ Backend Implemented - Ready for Frontend  
**Version**: v1  
**Last Updated**: 2026-02-05

---

## Overview

This guide provides frontend implementation details for the password recovery feature. The backend supports password reset via email with a 6-digit code (no link).

**Supported Platforms**:
- ✅ Web (Safari, Chrome, Firefox, Edge)
- ✅ iOS App
- ✅ Android App

**User Flow**:
1. User clicks "Forgot Password?" on login screen
2. User enters email address
3. User receives email with 6-digit reset code (no link)
4. User enters the code and new password in the app
5. User is redirected to login with success message

---

## API Endpoints

### 1. Request Password Reset

**POST** `/api/v1/auth/forgot-password`

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
  "message": "If an account with that email exists, a password reset code has been sent."
}
```

**Important**: The API always returns success, even if the email doesn't exist. This prevents attackers from discovering valid email addresses (email enumeration attack prevention).

**TypeScript Interface**:
```typescript
interface ForgotPasswordRequest {
  email: string;
}

interface ForgotPasswordResponse {
  success: boolean;
  message: string;
}
```

---

### 2. Reset Password

**POST** `/api/v1/auth/reset-password`

**Authentication**: None (public endpoint, token validation via request body)

**Request Body**:
```json
{
  "code": "123456",
  "new_password": "MyNewSecurePassword123!"
}
```

Either `code` (6-digit from email) or legacy `token` is required.

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
  "detail": "Invalid or expired reset code."
}
```

**Validation Rules**:
- `code`: 6-digit string from email (or legacy `token`)
- `new_password`: Minimum 8 characters

**Code Constraints**:
- Valid for 24 hours
- Can only be used once
- Automatically invalidated after use

**TypeScript Interface**:
```typescript
interface ResetPasswordRequest {
  code?: string;
  token?: string;  // legacy
  new_password: string;
}

interface ResetPasswordResponse {
  success: boolean;
  message: string;
}
```

---

### Related: Username recovery

The same auth area exposes **POST** `/api/v1/auth/forgot-username` for "Forgot your username?": the user submits their email and can optionally request that a password reset link also be sent. Full contract: consolidated in [USER_MODEL_FOR_CLIENTS.md](../../api/shared_client/USER_MODEL_FOR_CLIENTS.md#8-forgot-username); legacy copy: [USERNAME_RECOVERY.md](./USERNAME_RECOVERY.md).

---

## Frontend Implementation

### Web Application (React/Next.js/Vue)

#### Forgot Password Page

**Route**: `/forgot-password`

```typescript
import React, { useState } from 'react';

const ForgotPasswordPage = () => {
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError('');

    try {
      const response = await fetch('/api/v1/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });

      if (response.ok) {
        setSubmitted(true);
      } else {
        setError('An error occurred. Please try again.');
      }
    } catch (err) {
      setError('Network error. Please check your connection.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="success-message">
        <h2>Check Your Email</h2>
        <p>
          If an account with that email exists, a password reset link has been sent.
        </p>
        <p>Please check your inbox and spam folder.</p>
        <a href="/login">Return to Login</a>
      </div>
    );
  }

  return (
    <div className="forgot-password-page">
      <h1>Forgot Password?</h1>
      <p>Enter your email address and we'll send you a link to reset your password.</p>
      
      <form onSubmit={handleSubmit}>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="your.email@example.com"
          required
          disabled={isSubmitting}
        />
        
        {error && <p className="error">{error}</p>}
        
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Sending...' : 'Send Reset Link'}
        </button>
      </form>
      
      <a href="/login">Back to Login</a>
    </div>
  );
};
```

---

#### Reset Password Page

**Route**: `/reset-password?token=abc123...xyz789`

```typescript
import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

const ResetPasswordPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  
  const [token, setToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    const tokenParam = searchParams.get('token');
    if (!tokenParam) {
      setError('No reset token provided. Please use the link from your email.');
    } else {
      setToken(tokenParam);
    }
  }, [searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Client-side validation
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await fetch('/api/v1/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: token,
          new_password: newPassword
        })
      });

      const data = await response.json();

      if (response.ok) {
        setSuccess(true);
        // Redirect to login after 3 seconds
        setTimeout(() => {
          navigate('/login?message=password_reset_success');
        }, 3000);
      } else {
        setError(data.detail || 'Failed to reset password. The link may have expired.');
      }
    } catch (err) {
      setError('Network error. Please check your connection.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="success-message">
        <h2>Password Reset Successful!</h2>
        <p>You can now log in with your new password.</p>
        <p>Redirecting to login...</p>
      </div>
    );
  }

  if (!token && error) {
    return (
      <div className="error-message">
        <h2>Invalid Reset Link</h2>
        <p>{error}</p>
        <a href="/forgot-password">Request New Reset Link</a>
      </div>
    );
  }

  return (
    <div className="reset-password-page">
      <h1>Reset Your Password</h1>
      
      <form onSubmit={handleSubmit}>
        <div>
          <label>New Password:</label>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Enter new password"
            minLength={8}
            required
            disabled={isSubmitting}
          />
          <small>Minimum 8 characters</small>
        </div>
        
        <div>
          <label>Confirm Password:</label>
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Confirm new password"
            minLength={8}
            required
            disabled={isSubmitting}
          />
        </div>
        
        {error && <p className="error">{error}</p>}
        
        <button type="submit" disabled={isSubmitting || !token}>
          {isSubmitting ? 'Resetting...' : 'Reset Password'}
        </button>
      </form>
      
      <a href="/login">Back to Login</a>
    </div>
  );
};
```

---

### iOS App (Swift/SwiftUI)

#### Deep Link Configuration

**Info.plist**:
```xml
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleTypeRole</key>
    <string>Editor</string>
    <key>CFBundleURLName</key>
    <string>com.kitchen.app</string>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>kitchen</string>
    </array>
  </dict>
</array>

<!-- Support HTTPS Universal Links -->
<key>com.apple.developer.associated-domains</key>
<array>
  <string>applinks:kitchen.app.com</string>
</array>
```

**Email Link Formats**:
- **Deep Link**: `kitchen://reset-password?token=abc123...xyz789`
- **Universal Link**: `https://kitchen.app.com/reset-password?token=abc123...xyz789`

---

#### Forgot Password View (SwiftUI)

```swift
import SwiftUI

struct ForgotPasswordView: View {
    @State private var email: String = ""
    @State private var isSubmitting: Bool = false
    @State private var submitted: Bool = false
    @State private var errorMessage: String = ""
    
    var body: some View {
        VStack(spacing: 20) {
            if submitted {
                VStack(spacing: 15) {
                    Image(systemName: "envelope.circle.fill")
                        .font(.system(size: 60))
                        .foregroundColor(.blue)
                    
                    Text("Check Your Email")
                        .font(.title)
                    
                    Text("If an account with that email exists, a password reset link has been sent.")
                        .multilineTextAlignment(.center)
                        .foregroundColor(.secondary)
                    
                    Button("Return to Login") {
                        // Navigate back to login
                    }
                    .padding()
                }
            } else {
                Text("Forgot Password?")
                    .font(.largeTitle)
                    .bold()
                
                Text("Enter your email address and we'll send you a link to reset your password.")
                    .multilineTextAlignment(.center)
                    .foregroundColor(.secondary)
                
                TextField("Email", text: $email)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .autocapitalization(.none)
                    .keyboardType(.emailAddress)
                    .disabled(isSubmitting)
                
                if !errorMessage.isEmpty {
                    Text(errorMessage)
                        .foregroundColor(.red)
                        .font(.caption)
                }
                
                Button(action: handleSubmit) {
                    if isSubmitting {
                        ProgressView()
                    } else {
                        Text("Send Reset Link")
                    }
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.blue)
                .foregroundColor(.white)
                .cornerRadius(10)
                .disabled(isSubmitting || email.isEmpty)
                
                Button("Back to Login") {
                    // Navigate back to login
                }
                .foregroundColor(.blue)
            }
        }
        .padding()
    }
    
    func handleSubmit() {
        isSubmitting = true
        errorMessage = ""
        
        guard let url = URL(string: "https://api.kitchen.app.com/api/v1/auth/forgot-password") else {
            errorMessage = "Invalid API URL"
            isSubmitting = false
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: String] = ["email": email]
        request.httpBody = try? JSONEncoder().encode(body)
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                isSubmitting = false
                
                if let error = error {
                    errorMessage = "Network error: \(error.localizedDescription)"
                    return
                }
                
                if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                    submitted = true
                } else {
                    errorMessage = "An error occurred. Please try again."
                }
            }
        }.resume()
    }
}
```

---

#### Reset Password View (SwiftUI)

```swift
import SwiftUI

struct ResetPasswordView: View {
    let token: String
    
    @State private var newPassword: String = ""
    @State private var confirmPassword: String = ""
    @State private var isSubmitting: Bool = false
    @State private var success: Bool = false
    @State private var errorMessage: String = ""
    
    var body: some View {
        VStack(spacing: 20) {
            if success {
                VStack(spacing: 15) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 60))
                        .foregroundColor(.green)
                    
                    Text("Password Reset Successful!")
                        .font(.title)
                    
                    Text("You can now log in with your new password.")
                        .foregroundColor(.secondary)
                    
                    Button("Go to Login") {
                        // Navigate to login
                    }
                    .padding()
                }
            } else {
                Text("Reset Your Password")
                    .font(.largeTitle)
                    .bold()
                
                SecureField("New Password", text: $newPassword)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .disabled(isSubmitting)
                
                Text("Minimum 8 characters")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                SecureField("Confirm Password", text: $confirmPassword)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .disabled(isSubmitting)
                
                if !errorMessage.isEmpty {
                    Text(errorMessage)
                        .foregroundColor(.red)
                        .font(.caption)
                }
                
                Button(action: handleSubmit) {
                    if isSubmitting {
                        ProgressView()
                    } else {
                        Text("Reset Password")
                    }
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(Color.blue)
                .foregroundColor(.white)
                .cornerRadius(10)
                .disabled(isSubmitting || newPassword.isEmpty || confirmPassword.isEmpty)
            }
        }
        .padding()
    }
    
    func handleSubmit() {
        errorMessage = ""
        
        // Client-side validation
        if newPassword.count < 8 {
            errorMessage = "Password must be at least 8 characters long."
            return
        }
        
        if newPassword != confirmPassword {
            errorMessage = "Passwords do not match."
            return
        }
        
        isSubmitting = true
        
        guard let url = URL(string: "https://api.kitchen.app.com/api/v1/auth/reset-password") else {
            errorMessage = "Invalid API URL"
            isSubmitting = false
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: String] = [
            "token": token,
            "new_password": newPassword
        ]
        request.httpBody = try? JSONEncoder().encode(body)
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                isSubmitting = false
                
                if let error = error {
                    errorMessage = "Network error: \(error.localizedDescription)"
                    return
                }
                
                if let httpResponse = response as? HTTPURLResponse {
                    if httpResponse.statusCode == 200 {
                        success = true
                    } else if let data = data,
                              let json = try? JSONDecoder().decode([String: String].self, from: data),
                              let detail = json["detail"] {
                        errorMessage = detail
                    } else {
                        errorMessage = "Failed to reset password. The link may have expired."
                    }
                }
            }
        }.resume()
    }
}
```

---

#### Deep Link Handler (SwiftUI App)

```swift
import SwiftUI

@main
struct KitchenApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .onOpenURL { url in
                    handleDeepLink(url)
                }
        }
    }
    
    func handleDeepLink(_ url: URL) {
        // Handle deep link: kitchen://reset-password?token=abc123
        guard url.scheme == "kitchen",
              url.host == "reset-password" else {
            return
        }
        
        if let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
           let queryItems = components.queryItems,
           let tokenItem = queryItems.first(where: { $0.name == "token" }),
           let token = tokenItem.value {
            // Navigate to ResetPasswordView with token
            // Use your app's navigation system
            print("Navigating to reset password with token: \(token)")
        }
    }
}
```

---

### Android App (Kotlin/Jetpack Compose)

#### Deep Link Configuration

**AndroidManifest.xml**:
```xml
<activity
    android:name=".MainActivity"
    android:exported="true">
    
    <!-- Deep Link: kitchen://reset-password?token=xxx -->
    <intent-filter>
        <action android:name="android.intent.action.VIEW" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.BROWSABLE" />
        <data
            android:scheme="kitchen"
            android:host="reset-password" />
    </intent-filter>
    
    <!-- App Link: https://kitchen.app.com/reset-password?token=xxx -->
    <intent-filter android:autoVerify="true">
        <action android:name="android.intent.action.VIEW" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.BROWSABLE" />
        <data
            android:scheme="https"
            android:host="kitchen.app.com"
            android:pathPrefix="/reset-password" />
    </intent-filter>
</activity>
```

---

#### Forgot Password Screen (Jetpack Compose)

```kotlin
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

@Composable
fun ForgotPasswordScreen(
    onNavigateToLogin: () -> Unit,
    viewModel: AuthViewModel = viewModel()
) {
    var email by remember { mutableStateOf("") }
    var isSubmitting by remember { mutableStateOf(false) }
    var submitted by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf("") }
    
    val scope = rememberCoroutineScope()
    
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        if (submitted) {
            Icon(
                imageVector = Icons.Default.Email,
                contentDescription = null,
                modifier = Modifier.size(60.dp),
                tint = MaterialTheme.colorScheme.primary
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            Text(
                text = "Check Your Email",
                style = MaterialTheme.typography.headlineMedium
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Text(
                text = "If an account with that email exists, a password reset link has been sent.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            Button(onClick = onNavigateToLogin) {
                Text("Return to Login")
            }
        } else {
            Text(
                text = "Forgot Password?",
                style = MaterialTheme.typography.headlineLarge
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Text(
                text = "Enter your email address and we'll send you a link to reset your password.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            OutlinedTextField(
                value = email,
                onValueChange = { email = it },
                label = { Text("Email") },
                singleLine = true,
                enabled = !isSubmitting,
                modifier = Modifier.fillMaxWidth()
            )
            
            if (errorMessage.isNotEmpty()) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = errorMessage,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall
                )
            }
            
            Spacer(modifier = Modifier.height(16.dp))
            
            Button(
                onClick = {
                    scope.launch {
                        isSubmitting = true
                        errorMessage = ""
                        
                        val result = viewModel.forgotPassword(email)
                        isSubmitting = false
                        
                        if (result.isSuccess) {
                            submitted = true
                        } else {
                            errorMessage = result.exceptionOrNull()?.message 
                                ?: "An error occurred. Please try again."
                        }
                    }
                },
                enabled = !isSubmitting && email.isNotEmpty(),
                modifier = Modifier.fillMaxWidth()
            ) {
                if (isSubmitting) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(24.dp),
                        color = MaterialTheme.colorScheme.onPrimary
                    )
                } else {
                    Text("Send Reset Link")
                }
            }
            
            Spacer(modifier = Modifier.height(16.dp))
            
            TextButton(onClick = onNavigateToLogin) {
                Text("Back to Login")
            }
        }
    }
}
```

---

#### Reset Password Screen (Jetpack Compose)

```kotlin
@Composable
fun ResetPasswordScreen(
    token: String,
    onNavigateToLogin: () -> Unit,
    viewModel: AuthViewModel = viewModel()
) {
    var newPassword by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }
    var isSubmitting by remember { mutableStateOf(false) }
    var success by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf("") }
    
    val scope = rememberCoroutineScope()
    
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        if (success) {
            Icon(
                imageVector = Icons.Default.CheckCircle,
                contentDescription = null,
                modifier = Modifier.size(60.dp),
                tint = Color.Green
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            Text(
                text = "Password Reset Successful!",
                style = MaterialTheme.typography.headlineMedium
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Text(
                text = "You can now log in with your new password.",
                style = MaterialTheme.typography.bodyMedium
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            Button(onClick = onNavigateToLogin) {
                Text("Go to Login")
            }
        } else {
            Text(
                text = "Reset Your Password",
                style = MaterialTheme.typography.headlineLarge
            )
            
            Spacer(modifier = Modifier.height(24.dp))
            
            OutlinedTextField(
                value = newPassword,
                onValueChange = { newPassword = it },
                label = { Text("New Password") },
                singleLine = true,
                enabled = !isSubmitting,
                visualTransformation = PasswordVisualTransformation(),
                modifier = Modifier.fillMaxWidth()
            )
            
            Text(
                text = "Minimum 8 characters",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            OutlinedTextField(
                value = confirmPassword,
                onValueChange = { confirmPassword = it },
                label = { Text("Confirm Password") },
                singleLine = true,
                enabled = !isSubmitting,
                visualTransformation = PasswordVisualTransformation(),
                modifier = Modifier.fillMaxWidth()
            )
            
            if (errorMessage.isNotEmpty()) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = errorMessage,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall
                )
            }
            
            Spacer(modifier = Modifier.height(16.dp))
            
            Button(
                onClick = {
                    errorMessage = ""
                    
                    // Client-side validation
                    if (newPassword.length < 8) {
                        errorMessage = "Password must be at least 8 characters long."
                        return@Button
                    }
                    
                    if (newPassword != confirmPassword) {
                        errorMessage = "Passwords do not match."
                        return@Button
                    }
                    
                    scope.launch {
                        isSubmitting = true
                        
                        val result = viewModel.resetPassword(token, newPassword)
                        isSubmitting = false
                        
                        if (result.isSuccess) {
                            success = true
                        } else {
                            errorMessage = result.exceptionOrNull()?.message 
                                ?: "Failed to reset password. The link may have expired."
                        }
                    }
                },
                enabled = !isSubmitting && newPassword.isNotEmpty() && confirmPassword.isNotEmpty(),
                modifier = Modifier.fillMaxWidth()
            ) {
                if (isSubmitting) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(24.dp),
                        color = MaterialTheme.colorScheme.onPrimary
                    )
                } else {
                    Text("Reset Password")
                }
            }
        }
    }
}
```

---

#### Deep Link Handler (MainActivity)

```kotlin
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        handleIntent(intent)
        
        setContent {
            KitchenAppTheme {
                // Your app's navigation
            }
        }
    }
    
    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        intent?.let { handleIntent(it) }
    }
    
    private fun handleIntent(intent: Intent) {
        val action = intent.action
        val data = intent.data
        
        if (Intent.ACTION_VIEW == action && data != null) {
            // Handle deep link: kitchen://reset-password?token=abc123
            // Or App Link: https://kitchen.app.com/reset-password?token=abc123
            
            if (data.host == "reset-password" || data.path == "/reset-password") {
                val token = data.getQueryParameter("token")
                
                if (token != null) {
                    // Navigate to ResetPasswordScreen with token
                    // Use your navigation component
                    Log.d("DeepLink", "Navigating to reset password with token: $token")
                }
            }
        }
    }
}
```

---

## Email Link Configuration

### Email Template Requirements

The backend sends emails with reset links. Ensure your email service is configured correctly:

**Link Format for Web**:
```
https://yourdomain.com/reset-password?token=abc123...xyz789
```

**Link Format for Mobile Apps** (Universal Links / App Links):
```
https://yourdomain.com/reset-password?token=abc123...xyz789
```

**Alternative Deep Link Format**:
```
kitchen://reset-password?token=abc123...xyz789
```

**Recommendation**: Use Universal Links (iOS) and App Links (Android) instead of custom URL schemes for better security and user experience.

---

## Multi-Device Support Strategy

### 1. User Has Multiple Devices

**Scenario**: User requests reset on iPhone, opens link on desktop browser.

**Solution**: Token-based authentication works across all devices. The token is device-agnostic.

**Implementation**: No special handling needed. The token in the URL is valid on any device.

---

### 2. User Opens Link in Wrong App

**Scenario**: User clicks email link on Android, but link opens in browser instead of app.

**Solution**: 
- Implement Universal Links (iOS) and App Links (Android) with proper domain verification
- Fallback: Provide "Open in App" button in web version

**Implementation**:
```html
<!-- Web reset password page -->
<div id="open-in-app-banner">
  <p>Have the Kitchen app? <button onclick="openInApp()">Open in App</button></p>
</div>

<script>
function openInApp() {
  const token = new URLSearchParams(window.location.search).get('token');
  
  // Try to open in app
  window.location.href = `kitchen://reset-password?token=${token}`;
  
  // Fallback to app store after 2 seconds if app doesn't open
  setTimeout(() => {
    // User didn't have app installed, continue with web version
  }, 2000);
}
</script>
```

---

### 3. User Logged In on Multiple Devices

**Scenario**: User resets password while logged in on other devices.

**Solution**: After password reset, invalidate all existing sessions (optional security measure).

**Implementation**: 
- Backend can invalidate all JWT tokens on password reset
- Or, include password hash in JWT claims and verify on each request

**Note**: This is a backend concern. Frontend should handle logout gracefully if token is invalidated.

---

## Security Considerations

### 1. Token Handling

**DO**:
- ✅ Extract token from URL immediately
- ✅ Clear token from browser history after use (if possible)
- ✅ Validate token format before sending to API
- ✅ Show generic error messages for invalid tokens

**DON'T**:
- ❌ Store token in localStorage or sessionStorage
- ❌ Log token to console or analytics
- ❌ Share token via insecure channels
- ❌ Expose specific error details to users

---

### 2. Password Validation

**Client-Side Validation**:
```typescript
const validatePassword = (password: string): string | null => {
  if (password.length < 8) {
    return 'Password must be at least 8 characters long.';
  }
  
  // Optional: Add more rules
  if (!/[A-Z]/.test(password)) {
    return 'Password must contain at least one uppercase letter.';
  }
  
  if (!/[a-z]/.test(password)) {
    return 'Password must contain at least one lowercase letter.';
  }
  
  if (!/[0-9]/.test(password)) {
    return 'Password must contain at least one number.';
  }
  
  return null; // Valid
};
```

**Note**: Always validate on backend as well. Client-side validation is for UX only.

---

### 3. SSL/TLS Requirements

**CRITICAL**: All password recovery endpoints MUST use HTTPS in production.

- ✅ Development: `http://localhost:8000` (acceptable)
- ✅ Production: `https://api.yourdomain.com` (required)

---

## Testing

### Manual Testing Checklist

#### Web Application
- [ ] Navigate to forgot password page
- [ ] Submit email address
- [ ] Check email inbox for reset link
- [ ] Click link, verify redirect to reset password page
- [ ] Enter new password
- [ ] Verify redirect to login page
- [ ] Log in with new password

#### iOS App
- [ ] Navigate to forgot password screen
- [ ] Submit email address
- [ ] Open email on iPhone
- [ ] Click link, verify app opens to reset password screen
- [ ] Enter new password
- [ ] Verify success message and redirect to login
- [ ] Log in with new password

#### Android App
- [ ] Navigate to forgot password screen
- [ ] Submit email address
- [ ] Open email on Android device
- [ ] Click link, verify app opens to reset password screen
- [ ] Enter new password
- [ ] Verify success message and redirect to login
- [ ] Log in with new password

#### Cross-Device Testing
- [ ] Request reset on Device A, open link on Device B
- [ ] Request reset in browser, open link in mobile app
- [ ] Request reset in mobile app, open link in browser

---

## Error Handling

### User-Friendly Error Messages

| Backend Error | User-Facing Message |
|---------------|---------------------|
| `Invalid or expired reset token` | "This reset link has expired or is invalid. Please request a new one." |
| `Token already used` | "This reset link has already been used. Please request a new one if you need to reset your password again." |
| Network error | "Unable to connect to the server. Please check your internet connection and try again." |
| Email not found | (Always show success to prevent enumeration) |

---

## Best Practices

1. **Always Use HTTPS**: Never transmit passwords over HTTP
2. **Clear Form on Success**: Clear password fields after successful reset
3. **Show Password Strength**: Visual indicator for password strength
4. **Confirm Password Field**: Require users to confirm their new password
5. **Auto-Focus**: Auto-focus first field for better UX
6. **Loading States**: Show loading indicators during API calls
7. **Responsive Design**: Ensure forms work on all screen sizes
8. **Accessibility**: Add proper ARIA labels and keyboard navigation
9. **Deep Link Testing**: Test deep links on real devices, not just emulators
10. **Token Expiry Communication**: Clearly communicate 24-hour expiry

---

## Related Documentation

- [Backend Password Recovery API](../../api/internal/PASSWORD_RECOVERY.md)
- [User model for clients (consolidated)](../../api/shared_client/USER_MODEL_FOR_CLIENTS.md)
- [API Permissions by Role](../../api/shared_client/API_PERMISSIONS_BY_ROLE.md)

---

**Frontend Implementation**: Required  
**Backend Status**: ✅ Ready  
**Priority**: High (User-Critical Feature)
