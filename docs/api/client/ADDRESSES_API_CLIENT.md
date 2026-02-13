# Address API - Timezone Auto-Deduction

**Document Version**: 1.0  
**Date**: February 10, 2026  
**For**: Frontend Team (Web, iOS, Android)

---

## Overview

The Address API automatically calculates the correct timezone for addresses based on `country_code` and `province/state`. Users **do not** need to manually enter timezone values.

**Key Principle**: Minimize user friction - users only provide `country_code` and `province`, the backend automatically deduces the timezone.

---

## API Endpoints

### Create Address

```http
POST /api/v1/addresses/
```

**Request Body** (timezone is **NOT** required):

```json
{
  "institution_id": "uuid",
  "user_id": "uuid",
  "address_type": ["Restaurant"],
  "country_code": "ARG",
  "province": "Buenos Aires",
  "city": "Buenos Aires",
  "postal_code": "C1000",
  "street_type": "Avenida",
  "street_name": "Corrientes",
  "building_number": "1234",
  "apartment_unit": "5A",
  "floor": "5"
}
```

**Response** (timezone is auto-calculated):

```json
{
  "address_id": "uuid",
  "institution_id": "uuid",
  "user_id": "uuid",
  "address_type": ["Restaurant"],
  "country_code": "ARG",
  "country_name": "Argentina",
  "province": "Buenos Aires",
  "city": "Buenos Aires",
  "postal_code": "C1000",
  "street_type": "Avenida",
  "street_name": "Corrientes",
  "building_number": "1234",
  "apartment_unit": "5A",
  "floor": "5",
  "timezone": "America/Argentina/Buenos_Aires",
  "is_default": false,
  "is_archived": false,
  "status": "Active",
  "created_date": "2026-02-10T12:00:00Z",
  "modified_date": "2026-02-10T12:00:00Z"
}
```

### Update Address

```http
PUT /api/v1/addresses/{address_id}
```

**Request Body** (timezone is automatically updated if country_code or province changes):

```json
{
  "province": "Cordoba"
}
```

**Response**:

```json
{
  "address_id": "uuid",
  "province": "Cordoba",
  "timezone": "America/Argentina/Cordoba",
  ...
}
```

---

## Timezone Deduction Logic

### Single-Timezone Countries

For countries with one timezone, the backend uses the default timezone from the `market_info` table.

**Examples**:
- **Argentina (ARG)**: All provinces → `America/Argentina/Buenos_Aires`
- **Peru (PER)**: All provinces → `America/Lima`
- **Chile (CHL)**: All provinces → `America/Santiago`

**Frontend Behavior**:
- User selects `country_code` (e.g., "ARG")
- User enters `province` (e.g., "Buenos Aires")
- Backend automatically sets timezone to country default
- ✅ No additional user input needed

### Multi-Timezone Countries

For countries with multiple timezones, the backend uses province/state mappings.

**Examples**:

**United States (USA)**:
- `province: "California"` → `America/Los_Angeles` (Pacific Time)
- `province: "New York"` → `America/New_York` (Eastern Time)
- `province: "Texas"` → `America/Chicago` (Central Time)
- `province: "Arizona"` → `America/Phoenix` (Mountain Time, no DST)

**Brazil (BRA)**:
- `province: "Sao Paulo"` → `America/Sao_Paulo`
- `province: "Amazonas"` → `America/Manaus`
- `province: "Bahia"` → `America/Bahia`

**Canada (CAN)**:
- `province: "Ontario"` → `America/Toronto` (Eastern Time)
- `province: "British Columbia"` → `America/Vancouver` (Pacific Time)
- `province: "Alberta"` → `America/Edmonton` (Mountain Time)

**Frontend Behavior**:
- User selects `country_code` (e.g., "USA")
- User enters `province` (e.g., "California" or "CA")
- Backend automatically sets timezone to province-specific value
- ✅ No additional user input needed

---

## Province Name Normalization

The backend accepts multiple formats for province names:

**State Full Names**:
- "California", "New York", "Texas"

**State Codes**:
- "CA", "NY", "TX"

**Case Insensitive**:
- "california", "CALIFORNIA", "California" → all resolve to `America/Los_Angeles`

**With/Without Suffixes**:
- "New York State" → normalized to "New York"
- "Texas State" → normalized to "Texas"

---

## Edge Cases

### 1. Province Not Found

**Scenario**: User enters an invalid or unrecognized province for a multi-timezone country.

**Backend Behavior**:
- Returns the country's **default timezone**
- Logs a warning (not visible to frontend)
- Address is **still created successfully**

**Example**:

```json
{
  "country_code": "USA",
  "province": "InvalidProvince"
}
```

**Response**:

```json
{
  "country_code": "USA",
  "province": "InvalidProvince",
  "timezone": "America/New_York"
}
```

**Frontend Behavior**:
- ✅ Address creation succeeds
- Display timezone in UI (read-only)
- Consider showing validation message if province doesn't match known values

### 2. Province Not Provided (Multi-Timezone Country)

**Scenario**: User creates address for multi-timezone country without specifying province.

**Backend Behavior**:
- Returns the country's **default timezone**
- Logs a warning
- Address is **still created successfully**

**Example**:

```json
{
  "country_code": "USA",
  "province": ""
}
```

**Response**:

```json
{
  "country_code": "USA",
  "province": "",
  "timezone": "America/New_York"
}
```

**Frontend Behavior**:
- ⚠️ Consider making `province` a required field in UI for multi-timezone countries
- If province is optional in UI, timezone will default to country's default

### 3. Country Not Found

**Scenario**: User provides invalid `country_code`.

**Backend Behavior**:
- Returns `400 Bad Request`
- Error message: `"Invalid country_code: {code}. Market not found in market_info."`

**Frontend Behavior**:
- Validate `country_code` against available markets before submission
- Use Markets API (`GET /api/v1/markets/`) to fetch valid country codes
- Display error message to user if invalid code is provided

---

## Frontend Integration

### Web (React/TypeScript)

```typescript
// Fetch available markets for country dropdown
const markets = await apiClient.get('/api/v1/markets/');

// User selects country
const selectedCountry = markets.find(m => m.country_code === 'USA');

// Create address (no timezone field)
const addressData = {
  institution_id: institutionId,
  user_id: userId,
  address_type: ['Restaurant'],
  country_code: 'USA',
  province: 'California',  // User enters province
  city: 'San Francisco',
  postal_code: '94103',
  street_type: 'Street',
  street_name: 'Market',
  building_number: '123'
};

const response = await apiClient.post('/api/v1/addresses/', addressData);

// Display auto-calculated timezone (read-only)
console.log(`Timezone: ${response.timezone}`); // "America/Los_Angeles"
```

### iOS (SwiftUI)

```swift
struct CreateAddressView: View {
    @State private var countryCode: String = "USA"
    @State private var province: String = ""
    @State private var calculatedTimezone: String = ""
    
    var body: some View {
        Form {
            // Country picker (from Markets API)
            Picker("Country", selection: $countryCode) {
                ForEach(markets) { market in
                    Text(market.countryName).tag(market.countryCode)
                }
            }
            
            // Province text field
            TextField("Province/State", text: $province)
            
            // Display calculated timezone (read-only)
            Text("Timezone: \(calculatedTimezone)")
                .foregroundColor(.secondary)
        }
        .onSubmit {
            createAddress()
        }
    }
    
    func createAddress() async {
        let addressData = [
            "country_code": countryCode,
            "province": province,
            // ... other fields
        ]
        
        let response = try await apiClient.post("/api/v1/addresses/", body: addressData)
        calculatedTimezone = response.timezone // "America/Los_Angeles"
    }
}
```

### Android (Jetpack Compose)

```kotlin
@Composable
fun CreateAddressScreen(viewModel: AddressViewModel) {
    var countryCode by remember { mutableStateOf("USA") }
    var province by remember { mutableStateOf("") }
    var calculatedTimezone by remember { mutableStateOf("") }
    
    Column {
        // Country dropdown (from Markets API)
        ExposedDropdownMenuBox(
            expanded = expanded,
            onExpandedChange = { expanded = !expanded }
        ) {
            // Country options from markets API
        }
        
        // Province text field
        OutlinedTextField(
            value = province,
            onValueChange = { province = it },
            label = { Text("Province/State") }
        )
        
        // Display calculated timezone (read-only)
        if (calculatedTimezone.isNotEmpty()) {
            Text(
                text = "Timezone: $calculatedTimezone",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.secondary
            )
        }
        
        Button(onClick = {
            viewModel.createAddress(
                countryCode = countryCode,
                province = province,
                // ... other fields
            )
        }) {
            Text("Create Address")
        }
    }
}
```

---

## UI/UX Recommendations

### 1. Country Selection

- Use dropdown/picker populated from Markets API (`GET /api/v1/markets/`)
- Display both country name and code (e.g., "Argentina (ARG)")
- Make it a required field

### 2. Province/State Field

- Use text input (not dropdown, too many options)
- Make it a required field for multi-timezone countries
- Consider showing placeholder text (e.g., "California", "Buenos Aires")
- Accept both full names and codes ("CA", "California")

### 3. Timezone Display

- Show the auto-calculated timezone in UI (read-only)
- Display it after user enters province (optional: live update)
- Use descriptive format: `"Pacific Time (America/Los_Angeles)"`
- Do NOT allow manual timezone editing

### 4. Validation

- Validate `country_code` against available markets before submission
- Consider warning if province doesn't match known values (optional)
- Handle 400 errors gracefully with user-friendly messages

---

## Supported Countries

### Single-Timezone Countries

Backend automatically uses default from `market_info`:

- **ARG** (Argentina): `America/Argentina/Buenos_Aires`
- **PER** (Peru): `America/Lima`
- **CHL** (Chile): `America/Santiago`

### Multi-Timezone Countries

Backend uses province mappings:

- **USA** (United States): 50 states + territories, 6 main timezones
- **BRA** (Brazil): 27 states, 4 main timezones
- **CAN** (Canada): 13 provinces/territories, 6 main timezones
- **MEX** (Mexico): 32 states, 4 main timezones

---

## Common Questions

### Q: Can users manually override the timezone?

**A:** No. Timezone is automatically calculated and read-only. This ensures data consistency and prevents user errors.

### Q: What if the auto-calculated timezone is wrong?

**A:** This indicates either:
1. Invalid `country_code` (user should select from Markets API)
2. Invalid `province` (user should double-check spelling)
3. Missing province mapping (contact backend team to add)

### Q: Do I need to store timezone on the frontend?

**A:** No. Always fetch timezone from the API response. The backend is the source of truth.

### Q: How do I know which countries have multiple timezones?

**A:** Use this rule:
- **ARG, PER, CHL**: Single timezone (province is informational only)
- **USA, BRA, CAN, MEX**: Multiple timezones (province determines timezone)

You can also query the backend for this information if needed (future enhancement).

### Q: What happens if I update the province?

**A:** The timezone is automatically recalculated when you update `country_code` or `province` via `PUT /api/v1/addresses/{id}`.

---

## Error Handling

### 400 Bad Request - Invalid Country Code

```json
{
  "detail": "Invalid country_code: XYZ. Market not found in market_info."
}
```

**Frontend Action**: Validate country code before submission using Markets API.

### 400 Bad Request - Missing Country Code

```json
{
  "detail": "country_code is required"
}
```

**Frontend Action**: Make `country_code` a required field in UI.

---

## Testing Checklist

- [ ] Create address with single-timezone country (ARG) → timezone auto-set
- [ ] Create address with multi-timezone country + valid province (USA, "California") → timezone auto-set
- [ ] Create address with multi-timezone country + invalid province → timezone defaults, address created
- [ ] Create address with multi-timezone country + no province → timezone defaults, address created
- [ ] Update address province → timezone automatically updated
- [ ] Update address country_code → timezone automatically updated
- [ ] Display timezone in UI (read-only)
- [ ] Handle 400 error for invalid country_code gracefully

---

## Migration Notes

**Existing Addresses**: No action needed. Existing addresses keep their current timezones. Only new addresses and updates will use the new auto-deduction logic.

**API Compatibility**: The `timezone` field is still present in responses (read-only). Frontend code doesn't need immediate changes, but should stop sending `timezone` in requests.

---

## Related Documentation

- [Markets API Client](./MARKETS_API_CLIENT.md) - Fetching available countries
- [Enum Service API](./ENUM_SERVICE_API.md) - Fetching address types and other enums
- [API Permissions by Role](./API_PERMISSIONS_BY_ROLE.md) - Who can create/update addresses

---

**Document Status**: Ready for Frontend Implementation  
**Backend Implementation**: Complete  
**Next Steps**: Update frontend to use country_code + province (stop sending timezone)
