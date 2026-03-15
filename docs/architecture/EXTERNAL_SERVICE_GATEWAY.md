# External Service Gateway Architecture

## Overview

All external API calls are now routed through a centralized **Gateway Pattern** that provides:

- **Development Mode**: Use mock responses to avoid API costs during development
- **Centralized Logging**: Track all external API calls for cost monitoring
- **Consistent Error Handling**: Unified exception handling across all services
- **Easy Testing**: Mock responses in JSON files for predictable testing

---

## Architecture

```
Service Layer               Gateway Layer           External APIs
─────────────────          ───────────────          ─────────────

geolocation_service.py  →  GoogleMapsGateway   →   Google Maps API
                               ↓
                          BaseGateway
                               ↓
                          (logs, dev mode, retries)
```

---

## Components

### 1. Base Gateway (`app/gateways/base_gateway.py`)

Abstract base class providing common functionality:
- Development mode detection
- Mock response loading
- API call logging for cost tracking
- Error handling

**Key Methods:**
- `call(operation, **kwargs)`: Main entry point for all external calls
- `_make_request(operation, **kwargs)`: Abstract method for actual API calls
- `_load_mock_responses()`: Abstract method to load mock data
- `_log_api_call()`: Logs all API calls with duration and parameters

### 2. Google Maps Gateway (`app/gateways/google_maps_gateway.py`)

Implements BaseGateway for Google Maps Geocoding API:
- `geocode(address)`: Address → Coordinates
- `reverse_geocode(lat, lng)`: Coordinates → Address
- `get_address_components(address)`: Extract structured address data
- `validate_address(address)`: Check if address is valid

### 3. Mock Responses (`app/mocks/google_maps_responses.json`)

Contains realistic API responses for development:
- Sample geocoding responses for Buenos Aires addresses
- Reverse geocoding responses
- All responses match actual Google Maps API format

---

## Configuration

### Environment Variables (`.env`)

```bash
# Development Mode
DEV_MODE=true  # Set to true for local dev (uses mocks), false for production

# Google API Keys (per environment; local uses _DEV)
GOOGLE_API_KEY_DEV=your_api_key_here
# GOOGLE_API_KEY_STAGING=...
# GOOGLE_API_KEY_PROD=...
```

### Settings (`app/config/settings.py`)

```python
class Settings(BaseSettings):
    DEV_MODE: bool = False  # Enable dev mode
    GOOGLE_API_KEY_DEV: str = ""
    GOOGLE_API_KEY_STAGING: str = ""
    GOOGLE_API_KEY_PROD: str = ""  # App uses env-specific key via get_google_api_key()
    # ... other settings
```

---

## Usage

### In Development (DEV_MODE=true)

```python
from app.services.geolocation_service import geolocation_service

# No API key needed - uses mock responses
result = geolocation_service.geocode_address(
    address="Av. Santa Fe 2567",
    city="Buenos Aires",
    country="Argentina"
)
# Returns mock data from google_maps_responses.json
# No external API call made
# No cost incurred
```

**Console Output:**
```
🚧 Google Maps Geocoding API Gateway running in DEV_MODE - using mock responses
🎭 Returning mock response for Google Maps Geocoding API.geocode
```

### In Production (DEV_MODE=false)

```python
from app.services.geolocation_service import geolocation_service

# Requires GOOGLE_API_KEY_DEV (or _STAGING/_PROD) in .env
result = geolocation_service.geocode_address(
    address="1600 Amphitheatre Parkway",
    city="Mountain View",
    country="USA"
)
# Makes real API call to Google Maps
# Logs call for cost tracking
```

**Console Output:**
```
💰 External API Call: Google Maps Geocoding API.geocode (✅ success) in 234.56ms
```

**Log Data (JSON):**
```json
{
  "service": "Google Maps Geocoding API",
  "operation": "geocode",
  "success": true,
  "duration_ms": 234.56,
  "timestamp": "2026-02-04T21:30:45.123456",
  "parameters": {
    "address": "1600 Amphitheatre Parkway, Mountain View, USA"
  }
}
```

---

## Adding New External Services

To add a new external API (e.g., Mapbox, AWS SES):

### 1. Create Gateway Class

```python
# app/gateways/your_service_gateway.py
from app.gateways.base_gateway import BaseGateway

class YourServiceGateway(BaseGateway):
    @property
    def service_name(self) -> str:
        return "Your Service Name"
    
    def _load_mock_responses(self) -> Dict[str, Any]:
        return self._load_mock_file("your_service_responses.json")
    
    def _make_request(self, operation: str, **kwargs) -> Any:
        # Implement actual API call
        pass
    
    # Add public methods for specific operations
    def do_something(self, param: str) -> Any:
        return self.call("do_something", param=param)
```

### 2. Create Mock Responses

```json
// app/mocks/your_service_responses.json
{
  "do_something": {
    "result": "mock data",
    "status": "success"
  }
}
```

### 3. Update Service

```python
# app/services/your_service.py
from app.gateways.your_service_gateway import YourServiceGateway

gateway = YourServiceGateway()
result = gateway.do_something("parameter")
```

### 4. Register in `app/gateways/__init__.py`

```python
from app.gateways.your_service_gateway import YourServiceGateway

__all__ = [
    "BaseGateway",
    "GoogleMapsGateway",
    "YourServiceGateway",  # Add here
]
```

---

## Cost Tracking

All external API calls are logged with:
- Service name
- Operation name
- Success/failure status
- Duration (ms)
- Timestamp
- Parameters (excluding sensitive data)

### Querying Logs for Costs

```bash
# Find all Google Maps API calls in last 24 hours
grep "💰 External API Call: Google Maps" server.log | tail -n 100

# Count successful calls per service
grep "💰 External API Call" server.log | grep "✅ success" | wc -l

# Find failed calls
grep "💰 External API Call" server.log | grep "❌ failed"
```

### Monthly Cost Estimation

```python
# Example: Count Google Maps API calls
google_maps_calls = 1500  # From logs
cost_per_1000 = 5.00  # After free tier
monthly_cost = (google_maps_calls / 1000) * cost_per_1000
# = $7.50
```

---

## Testing

### Unit Tests

```python
import pytest
from app.gateways.google_maps_gateway import GoogleMapsGateway
from app.config.settings import Settings

def test_geocode_in_dev_mode():
    # Gateway automatically uses mock responses in DEV_MODE
    gateway = GoogleMapsGateway()
    lat, lng = gateway.geocode("Av. Santa Fe 2567, Buenos Aires")
    
    assert lat == -34.5880634
    assert lng == -58.4023328
```

### Integration Tests

Set `DEV_MODE=false` and provide test API key:

```python
def test_geocode_real_api():
    os.environ["DEV_MODE"] = "false"
    os.environ["ENVIRONMENT"] = "local"
    os.environ["GOOGLE_API_KEY_DEV"] = "test_key"
    
    gateway = GoogleMapsGateway()
    result = gateway.geocode("1600 Amphitheatre Parkway")
    # Makes real API call
```

---

## Benefits

| Aspect | Before Gateway | After Gateway |
|--------|---------------|---------------|
| **Development** | API key required, costs $ | No API key needed, free |
| **Testing** | Hard to mock, flaky tests | Predictable mock data |
| **Cost Tracking** | Manual log parsing | Centralized logging |
| **Error Handling** | Inconsistent | Unified pattern |
| **Code Changes** | Scattered API calls | Single entry point |

---

## Next Steps

Future enhancements:
1. **Rate Limiting**: Add request throttling per service
2. **Retry Logic**: Automatic retries for transient failures
3. **Caching**: Cache frequent geocoding requests
4. **Metrics Dashboard**: Visualize API usage and costs
5. **Additional Services**: Add gateways for:
   - Address Verification API (Argentina, Peru)
   - AWS SES (email)
   - Mapbox (future alternative to Google Maps)

---

## File Structure

```
app/
├── gateways/
│   ├── __init__.py
│   ├── base_gateway.py          # Abstract base class
│   └── google_maps_gateway.py   # Google Maps implementation
├── mocks/
│   ├── __init__.py
│   └── google_maps_responses.json  # Mock data
├── services/
│   └── geolocation_service.py   # Updated to use gateway
└── config/
    └── settings.py              # DEV_MODE and API keys
```

---

## References

- [Google Maps Geocoding API Docs](https://developers.google.com/maps/documentation/geocoding/overview)
- [Gateway Pattern (Martin Fowler)](https://martinfowler.com/eaaCatalog/gateway.html)
- Related Docs:
  - `docs/readme/ENV_SETUP.md` - Environment configuration
  - `docs/api/GEOLOCATION.md` - Geolocation service API
