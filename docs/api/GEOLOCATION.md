# Geolocation Service - Google Maps API Integration

**Status**: ✅ Implemented  
**Version**: 1.0  
**Last Updated**: 2026-02-04

---

## Overview

The Geolocation Service provides address-to-coordinates conversion (geocoding) and coordinates-to-address conversion (reverse geocoding) using Google Maps Geocoding API.

**Key Features**:
- ✅ Address geocoding (address → lat/lng)
- ✅ Reverse geocoding (lat/lng → address)
- ✅ Distance calculation (Haversine formula)
- ✅ Radius checking (is point A within X km of point B?)
- ✅ Address component extraction (city, country, postal code, etc.)

---

## Setup Instructions

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project: "Kitchen Backend"
3. Enable billing (required, but free tier is very generous)

### Step 2: Enable Geocoding API

1. Navigate to "APIs & Services" > "Library"
2. Search for "Geocoding API"
3. Click "Enable"

### Step 3: Create API Key

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "API Key"
3. Copy the API key

### Step 4: Restrict API Key (Security Best Practice)

1. Click "Edit API key"
2. Under "API restrictions":
   - Select "Restrict key"
   - Choose **"Geocoding API"** only
3. (Optional) Under "Application restrictions":
   - Select "IP addresses"
   - Add your server's IP address
4. Click "Save"

### Step 5: Add to Environment

Add to `.env`:
```bash
GOOGLE_MAPS_API_KEY=AIza... (your API key)
```

---

## Pricing & Limits

### Free Tier
- **$200 credit/month** (auto-renews monthly)
- Approximately **28,500 geocoding requests/month** free
- Sufficient for most MVPs and small-scale production

### After Free Tier
- **$5 per 1,000 requests**
- Example: 100,000 requests/month = ~$500/month

### Rate Limits
- No explicit rate limit
- Best practice: Cache results to minimize API calls

---

## Service API

### GeolocationService Class

```python
from app.services.geolocation_service import geolocation_service

# Check if configured
if geolocation_service.is_configured():
    # Ready to use
    pass
```

---

## Methods

### 1. geocode_address()

Convert address to geographic coordinates.

**Function Signature**:
```python
def geocode_address(
    address: str,
    city: Optional[str] = None,
    state: Optional[str] = None,
    country: Optional[str] = None,
    postal_code: Optional[str] = None
) -> Optional[Dict[str, Any]]
```

**Parameters**:
- `address`: Street address (required)
- `city`: City name (optional, improves accuracy)
- `state`: State/province (optional)
- `country`: Country code or name (optional, **highly recommended**)
- `postal_code`: Postal/ZIP code (optional)

**Returns**:
```python
{
    'latitude': 37.423021,
    'longitude': -122.083739,
    'formatted_address': '1600 Amphitheatre Parkway, Mountain View, CA 94043, USA',
    'place_id': 'ChIJ2eUgeAK6j4ARbn5u_wAGqWA',
    'address_components': [...],
    'location_type': 'ROOFTOP'  # Accuracy level
}
```

Or `None` if geocoding fails.

**Location Types** (accuracy):
- `ROOFTOP`: Most accurate (exact building)
- `RANGE_INTERPOLATED`: Interpolated between two points
- `GEOMETRIC_CENTER`: Center of area (e.g., street, neighborhood)
- `APPROXIMATE`: Approximate location

**Example**:
```python
result = geolocation_service.geocode_address(
    address="Av. Corrientes 1234",
    city="Buenos Aires",
    country="Argentina"
)

if result:
    print(f"Coordinates: {result['latitude']}, {result['longitude']}")
    print(f"Formatted: {result['formatted_address']}")
```

---

### 2. reverse_geocode()

Convert geographic coordinates to address.

**Function Signature**:
```python
def reverse_geocode(
    latitude: float,
    longitude: float
) -> Optional[Dict[str, Any]]
```

**Parameters**:
- `latitude`: Latitude coordinate
- `longitude`: Longitude coordinate

**Returns**:
```python
{
    'formatted_address': '1600 Amphitheatre Parkway, Mountain View, CA 94043, USA',
    'address_components': [...],
    'place_id': 'ChIJ2eUgeAK6j4ARbn5u_wAGqWA'
}
```

**Example**:
```python
result = geolocation_service.reverse_geocode(-34.603722, -58.381592)

if result:
    print(f"Address: {result['formatted_address']}")
    # Address: Av. Corrientes 1234, Buenos Aires, Argentina
```

---

### 3. calculate_distance()

Calculate distance between two points using Haversine formula.

**Function Signature**:
```python
def calculate_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    unit: str = 'km'
) -> float
```

**Parameters**:
- `lat1, lon1`: First point coordinates
- `lat2, lon2`: Second point coordinates
- `unit`: `'km'` for kilometers or `'mi'` for miles

**Returns**: Distance as `float`

**Example**:
```python
# Distance from Mountain View to San Francisco
distance = geolocation_service.calculate_distance(
    37.423021, -122.083739,  # Mountain View
    37.774929, -122.419418   # San Francisco
)
print(f"Distance: {distance:.2f} km")
# Distance: 49.08 km
```

---

### 4. is_within_radius()

Check if two points are within a specified radius.

**Function Signature**:
```python
def is_within_radius(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    radius_km: float
) -> bool
```

**Returns**: `True` if within radius, `False` otherwise

**Example**:
```python
is_close = geolocation_service.is_within_radius(
    37.423021, -122.083739,  # Restaurant
    37.774929, -122.419418,  # User location
    50                       # 50 km radius
)
# Returns: True
```

---

### 5. extract_address_component()

Extract specific component from Google Maps response.

**Function Signature**:
```python
def extract_address_component(
    address_components: list,
    component_type: str
) -> Optional[str]
```

**Common Component Types**:
- `'street_number'`: Street number
- `'route'`: Street name
- `'locality'`: City
- `'administrative_area_level_1'`: State/province
- `'country'`: Country
- `'postal_code'`: Postal/ZIP code

**Example**:
```python
result = geolocation_service.geocode_address(
    "Av. Corrientes 1234, Buenos Aires, Argentina"
)

if result:
    city = geolocation_service.extract_address_component(
        result['address_components'],
        'locality'
    )
    print(f"City: {city}")
    # City: Buenos Aires
```

---

## Integration Examples

### Example 1: Geocode Address on User Signup

```python
from app.services.geolocation_service import geolocation_service

def create_address(address_data: dict, db):
    # Geocode the address
    geocode_result = geolocation_service.geocode_address(
        address=address_data['street'],
        city=address_data['city'],
        state=address_data.get('state'),
        country=address_data['country'],
        postal_code=address_data.get('postal_code')
    )
    
    if not geocode_result:
        raise HTTPException(400, "Unable to geocode address")
    
    # Store in database
    with db.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO address_info (street, city, country, created_by)
            VALUES (%s, %s, %s, %s)
            RETURNING address_id
            """,
            (address_data['street'], address_data['city'], address_data['country'], user_id)
        )
        address_id = cursor.fetchone()[0]
        
        # Store geolocation
        cursor.execute(
            """
            INSERT INTO geolocation_info (address_id, latitude, longitude, formatted_address)
            VALUES (%s, %s, %s, %s)
            """,
            (
                address_id,
                geocode_result['latitude'],
                geocode_result['longitude'],
                geocode_result['formatted_address']
            )
        )
        
        db.commit()
    
    return address_id
```

---

### Example 2: Find Restaurants Within Radius

```python
def find_nearby_restaurants(user_lat: float, user_lng: float, radius_km: float, db):
    """Find restaurants within specified radius of user location."""
    
    # Get all restaurants with geolocation
    with db.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            SELECT 
                r.restaurant_id,
                r.name,
                g.latitude,
                g.longitude,
                a.street,
                a.city
            FROM restaurant_info r
            INNER JOIN address_info a ON r.address_id = a.address_id
            INNER JOIN geolocation_info g ON a.address_id = g.address_id
            WHERE r.is_archived = FALSE
            """
        )
        restaurants = cursor.fetchall()
    
    # Filter by distance
    nearby = []
    for restaurant in restaurants:
        if geolocation_service.is_within_radius(
            user_lat, user_lng,
            restaurant['latitude'], restaurant['longitude'],
            radius_km
        ):
            # Calculate exact distance
            distance = geolocation_service.calculate_distance(
                user_lat, user_lng,
                restaurant['latitude'], restaurant['longitude']
            )
            
            restaurant['distance_km'] = round(distance, 2)
            nearby.append(restaurant)
    
    # Sort by distance
    nearby.sort(key=lambda x: x['distance_km'])
    
    return nearby
```

---

### Example 3: Distance-Based Filtering in Plate Selection

```python
@router.get("/plates/nearby")
def get_nearby_plates(
    user_lat: float = Query(...),
    user_lng: float = Query(...),
    max_distance_km: float = Query(5.0, ge=0.1, le=50),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get today's plates from restaurants within specified distance.
    """
    nearby_restaurants = find_nearby_restaurants(user_lat, user_lng, max_distance_km, db)
    
    if not nearby_restaurants:
        return {"plates": [], "message": "No restaurants found within radius"}
    
    restaurant_ids = [r['restaurant_id'] for r in nearby_restaurants]
    
    # Get plates from nearby restaurants
    with db.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            SELECT 
                p.plate_id,
                p.name,
                p.price,
                r.restaurant_id,
                r.name as restaurant_name
            FROM plate_info p
            INNER JOIN restaurant_info r ON p.restaurant_id = r.restaurant_id
            WHERE p.restaurant_id = ANY(%s)
              AND p.is_archived = FALSE
              AND p.kitchen_day = CURRENT_DATE
            """,
            (restaurant_ids,)
        )
        plates = cursor.fetchall()
    
    # Enrich with distance
    restaurant_distances = {r['restaurant_id']: r['distance_km'] for r in nearby_restaurants}
    for plate in plates:
        plate['distance_km'] = restaurant_distances[plate['restaurant_id']]
    
    return {"plates": plates, "total": len(plates)}
```

---

## Error Handling

### Common Errors

**API Key Not Configured**:
```python
if not geolocation_service.is_configured():
    raise HTTPException(500, "Geolocation service not configured")
```

**Geocoding Failed (Invalid Address)**:
```python
result = geolocation_service.geocode_address("invalid address 12345xyz")
# Returns: None

if not result:
    raise HTTPException(400, "Unable to geocode address. Please check the address.")
```

**API Quota Exceeded**:
```
# Log message:
"Google Maps API quota exceeded"

# Solution: Upgrade Google Cloud billing or optimize caching
```

**Request Denied (API Key Restriction)**:
```
# Log message:
"Google Maps API request denied: API key not valid"

# Solution: Check API key restrictions in Google Cloud Console
```

---

## Performance Optimization

### 1. Caching

Cache geocoding results to reduce API calls:

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def geocode_with_cache(address: str, city: str, country: str):
    return geolocation_service.geocode_address(address, city=city, country=country)
```

### 2. Batch Geocoding

For bulk operations, geocode addresses during off-peak hours or async:

```python
import asyncio

async def batch_geocode(addresses: list):
    # Implement async geocoding for bulk operations
    pass
```

### 3. Pre-compute Distances

Store pre-computed distances in database for frequently accessed routes.

---

## Testing

### Manual Testing

```bash
# Test geocoding
python3 << EOF
from app.services.geolocation_service import geolocation_service

result = geolocation_service.geocode_address(
    "Av. Corrientes 1234",
    city="Buenos Aires",
    country="Argentina"
)

print(f"Coordinates: {result['latitude']}, {result['longitude']}")
print(f"Formatted: {result['formatted_address']}")
EOF
```

### Unit Tests

See `app/tests/services/test_geolocation_service.py` (pending implementation).

---

## Migration from Placeholder

### Before (Placeholder):
```python
def call_geocode_api(full_address: str) -> dict:
    response = requests.get(f"https://api.example.com/geocode?address={full_address}")
    return response.json() if response.status_code == 200 else {}
```

### After (Google Maps):
```python
from app.services.geolocation_service import geolocation_service

result = geolocation_service.geocode_address(
    "Av. Corrientes 1234",
    city="Buenos Aires",
    country="Argentina"
)
```

---

## Monitoring

### Metrics to Track

- Geocoding requests per day
- Successful vs. failed geocoding attempts
- Average response time
- API quota usage

### CloudWatch/Logs

```bash
# View geocoding logs
tail -f /var/log/kitchen-backend.log | grep "Geocod"
```

---

## Future Enhancements

1. **Google Distance Matrix API**: Get travel time and distance (walking, biking, driving)
2. **Mapbox Alternative**: Consider switching to Mapbox for lower costs at scale
3. **Offline Geocoding**: Use local database for common addresses (Argentina only)
4. **Geospatial Database**: PostgreSQL PostGIS extension for advanced spatial queries

---

## Related Documentation

- [ENV_SETUP.md](../ENV_SETUP.md) - Google Maps API setup
- [Recommendation Service](RECOMMENDATIONS.md) - Uses geolocation for distance filtering
- [Address API](ADDRESS.md) - Address management endpoints

---

**Implemented By**: Backend Team  
**Last Updated**: 2026-02-04  
**Status**: ✅ Ready for Testing
