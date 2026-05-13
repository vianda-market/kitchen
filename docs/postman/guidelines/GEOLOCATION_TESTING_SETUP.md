# Geolocation Testing Postman Collection - Setup Guide

## 🔧 Quick Setup

### 1. Import the Collection
Import `docs/postman/collections/Geolocation Testing.postman_collection.json` into Postman.

### 2. Configure Environment Variables

Create or update your Postman environment with these variables:

| Variable | Value | Description |
|----------|-------|-------------|
| `baseUrl` | `http://localhost:8000` | API base URL |
| `adminUsername` | `admin_user` | Admin username (from seed data) |
| `adminPassword` | `admin_password` | Admin password (from seed data) |
| `authToken` | *(auto-set)* | JWT token (set automatically after login) |
| `adminAuthToken` | *(auto-set)* | Admin JWT token (set automatically) |

### 3. Configure Application for Testing

**Option A: Development Mode (Recommended for Testing)**
```bash
# .env file
DEV_MODE=true
# No GOOGLE_API_KEY_* needed (uses mocks)
```

**Option B: Production Mode (Real Google Maps API)**
```bash
# .env file
DEV_MODE=false
ENVIRONMENT=local
GOOGLE_API_KEY_DEV=your_actual_api_key_here  # local uses dev key
```

### 4. Ensure Database is Seeded

The collection requires at least one address in the database:

```bash
cd /Users/cdeachaval/learn/vianda/kitchen
./app/db/build_kitchen_db.sh
```

### 5. Start the Server

```bash
source venv/bin/activate
python application.py
# or
uvicorn application:app --reload
```

---

## 🧪 Running the Tests

### Full Collection
Run the entire collection to test all geolocation functionality.

**Expected Output:**
```
✅ Login successful
✅ Query successful
✅ At least one address exists
✅ Found test address: Av. Santa Fe 2567
✅ Response successful
✅ Geolocation testing complete
```

### Individual Requests
You can also run requests individually:

1. **Login Admin** - Authenticate and get JWT token
2. **Query Test Address** - Find an address to test with
3. **Test Geocoding** - Test address geocoding (uses mock or real API)
4. **Verify DEV_MODE Active** - Check setup and view documentation
5. **Collection Summary** - View completion status

---

## 📊 Understanding Test Results

### Development Mode (DEV_MODE=true)
- ✅ **No API costs** - Uses mock responses
- ✅ **Fast** - No external API calls
- ✅ **Predictable** - Same results every time
- 🎭 **Console**: "Returning mock response for Google Maps Geocoding API..."

**Mock Data Location:** `app/mocks/google_maps_responses.json`

### Production Mode (DEV_MODE=false)
- 💰 **API costs apply** - Real Google Maps calls
- 🌐 **Real data** - Actual geocoding results
- 📝 **Logged** - All calls logged for cost tracking
- 💰 **Console**: "External API Call: Google Maps Geocoding API... (✅ success) in 234ms"

---

## 🔍 Troubleshooting

### "Not Found" Error on Login
**Problem:** `POST /api/v1/auth/token` returns 404

**Solution:** Ensure you're using the correct endpoint:
- ✅ Correct: `/api/v1/auth/token`
- ❌ Wrong: `/api/v1/token`

### "No addresses found" Warning
**Problem:** Collection can't find test addresses

**Solution:** Run database seed:
```bash
./app/db/build_kitchen_db.sh
```

### "GOOGLE_API_KEY not configured" Error
**Problem:** DEV_MODE=false but no API key

**Solution:** Either:
1. Set `DEV_MODE=true` in `.env` (recommended for testing)
2. Add `GOOGLE_API_KEY_DEV=your_key` to `.env` (local uses dev key)

### Mock Responses Not Working
**Problem:** Still making real API calls in DEV_MODE

**Solution:**
1. Check `.env` has `DEV_MODE=true`
2. Restart the server after changing `.env`
3. Check server logs for: "🚧 Google Maps Geocoding API Gateway running in DEV_MODE"

---

## 📖 Self-Contained Design

This collection follows the **self-contained design pattern** documented in `CLAUDE.md`:

✅ **Queries Existing Data:**
- Automatically finds any active address in the database
- No hardcoded UUIDs
- Works on fresh database with seed data

✅ **Includes Authentication:**
- Login step included in collection
- Tokens stored in environment variables

✅ **Clear Feedback:**
- Console logs show what's happening
- Tests provide meaningful assertions

---

## 🎯 What's Being Tested

This collection tests the **geolocation service** through the API, verifying:

1. **Gateway Infrastructure**
   - DEV_MODE switching (mock vs real API)
   - Error handling and logging
   - Cost tracking functionality

2. **Geocoding Functionality**
   - Address to coordinates conversion
   - Mock response accuracy
   - API integration (when DEV_MODE=false)

3. **Service Integration**
   - Geolocation service works with address endpoints
   - Database queries execute correctly
   - Authentication and authorization work

---

## 📚 Related Documentation

- **Gateway Architecture**: `docs/architecture/EXTERNAL_SERVICE_GATEWAY.md`
- **Testing Guidelines**: `CLAUDE.md` (Testing Standards section)
- **E2E Collection**: `docs/postman/collections/E2E Vianda Selection.postman_collection.json`

---

## 🚀 Next Steps After Testing

Once geolocation testing is complete:

1. **Verify Results** - Check that all tests pass
2. **Review Logs** - Check server logs for gateway behavior
3. **Cost Tracking** - Review API call logs (if DEV_MODE=false)
4. **Phase 1** - Proceed with database schema updates (pending approval)

---

**Last Updated:** 2026-02-04  
**Collection Version:** 1.0  
**Status:** ✅ Ready for Use
