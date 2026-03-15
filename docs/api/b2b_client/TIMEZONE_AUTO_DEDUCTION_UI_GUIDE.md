# Timezone Auto-Deduction - UI Implementation Guide

**Version**: 1.0  
**Date**: February 10, 2026  
**Audience**: Frontend Developers (Web, iOS, Android)

---

## TL;DR - What Changed

**The backend now automatically calculates timezone from `country_code` + `province`.**

✅ **DO**: Send `country_code` and `province` in address requests  
❌ **DON'T**: Send `timezone` field (it's calculated automatically)

---

## Quick Start

### Address Creation - Before & After

**❌ OLD WAY (Don't do this anymore):**
```json
{
  "country_code": "US",
  "province": "California",
  "timezone": "America/Los_Angeles"  // ❌ Remove this
}
```

**✅ NEW WAY (Do this):**
```json
{
  "country_code": "US",
  "province": "California"
  // ✅ Timezone calculated automatically
}
```

Use **ISO 3166-1 alpha-2** (e.g. `US`, `AR`). The API accepts case-insensitive input and normalizes to uppercase.

**Response includes auto-calculated timezone:**
```json
{
  "address_id": "uuid",
  "country_code": "US",
  "province": "California",
  "timezone": "America/Los_Angeles",  // ✅ Backend calculated this
  ...
}
```

---

## Implementation Checklist

### ✅ Required Changes

1. **Remove `timezone` from request body**
   - Don't send `timezone` field in POST/PUT requests
   - Backend will calculate it automatically

2. **Ensure `province` is provided**
   - `province` is now critical for multi-timezone countries
   - Make it a required field in your form validation

3. **Display timezone as read-only**
   - Show the auto-calculated timezone from API response
   - Don't allow users to edit it

### 🔍 Optional Improvements

1. **Make `province` required for US, BR, CA, MX** (alpha-2 codes)
   - These countries have multiple timezones
   - Providing `province` ensures accurate timezone

2. **Show timezone preview**
   - Display calculated timezone after user enters province
   - Use response from address creation/update

---

## Code Examples

### React/TypeScript

```typescript
// ✅ Address creation
const createAddress = async (formData: AddressForm) => {
  const requestBody = {
    institution_id: formData.institutionId,
    user_id: formData.userId,
    address_type: ['Restaurant'],
    country_code: formData.countryCode,  // ✅ Required
    province: formData.province,          // ✅ Required
    city: formData.city,
    postal_code: formData.postalCode,
    street_type: formData.streetType,
    street_name: formData.streetName,
    building_number: formData.buildingNumber,
    // ❌ Don't send: timezone
  };

  const response = await apiClient.post('/api/v1/addresses/', requestBody);
  
  // ✅ Display auto-calculated timezone (read-only)
  console.log(`Timezone: ${response.timezone}`); // "America/Los_Angeles"
  return response;
};

// ✅ Display in form
<TextField
  label="Timezone"
  value={address?.timezone || 'Auto-detected'}
  disabled  // Read-only
  helperText="Automatically calculated from location"
  sx={{ backgroundColor: '#f5f5f5' }}
/>
```

### iOS/SwiftUI

```swift
struct AddressFormView: View {
    @State private var countryCode: String = ""
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
            
            // Province text field (required)
            TextField("Province/State*", text: $province)
                .autocapitalization(.words)
            
            // Display calculated timezone (read-only)
            if !calculatedTimezone.isEmpty {
                HStack {
                    Text("Timezone")
                        .foregroundColor(.secondary)
                    Spacer()
                    Text(calculatedTimezone)
                        .foregroundColor(.primary)
                }
            }
        }
    }
    
    func createAddress() async {
        let requestBody: [String: Any] = [
            "country_code": countryCode,  // ✅ Required
            "province": province,          // ✅ Required
            "city": city,
            // ❌ Don't send: "timezone"
        ]
        
        let response = try await apiClient.post("/api/v1/addresses/", body: requestBody)
        calculatedTimezone = response.timezone // ✅ Auto-calculated
    }
}
```

### Android/Jetpack Compose

```kotlin
@Composable
fun AddressFormScreen(viewModel: AddressViewModel) {
    var countryCode by remember { mutableStateOf("") }
    var province by remember { mutableStateOf("") }
    var calculatedTimezone by remember { mutableStateOf("") }
    
    Column(modifier = Modifier.padding(16.dp)) {
        // Country dropdown
        ExposedDropdownMenuBox(
            expanded = expanded,
            onExpandedChange = { expanded = !expanded }
        ) {
            // Markets from API
        }
        
        // Province text field (required)
        OutlinedTextField(
            value = province,
            onValueChange = { province = it },
            label = { Text("Province/State *") },
            modifier = Modifier.fillMaxWidth()
        )
        
        // Display calculated timezone (read-only)
        if (calculatedTimezone.isNotEmpty()) {
            Text(
                text = "Timezone: $calculatedTimezone",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.padding(top = 8.dp)
            )
        }
        
        Button(onClick = {
            viewModel.createAddress(
                countryCode = countryCode,  // ✅ Required
                province = province,         // ✅ Required
                // ❌ Don't send: timezone
            )
        }) {
            Text("Create Address")
        }
    }
}
```

---

## How Timezone Deduction Works

### Single-Timezone Countries
**Argentina, Peru, Chile, Colombia, etc.**

- Backend uses default timezone from `market_info` table
- `province` is optional (same timezone everywhere)

**Example:**
```json
{
  "country_code": "AR",
  "province": "Buenos Aires"  // Any province works
}
// → timezone: "America/Argentina/Buenos_Aires"
```

### Multi-Timezone Countries
**US, Brazil, Canada, Mexico** (use alpha-2: US, BR, CA, MX)

- Backend uses `province` to determine specific timezone
- `province` is **critical** for accuracy

**Example:**
```json
{
  "country_code": "US",
  "province": "California"  // Important!
}
// → timezone: "America/Los_Angeles"

{
  "country_code": "US",
  "province": "New York"
}
// → timezone: "America/New_York"
```

---

## Province Formatting

The backend accepts multiple formats:

### ✅ Accepted Formats

**Full State Names:**
- `"California"`, `"New York"`, `"Texas"`

**State Codes:**
- `"CA"`, `"NY"`, `"TX"`

**Case Insensitive:**
- `"california"`, `"CALIFORNIA"`, `"California"` → all work

**With/Without Suffixes:**
- `"New York State"` → normalized to `"New York"`

---

## Edge Cases

### 1. Province Not Provided (Multi-TZ Country)

**Request:**
```json
{
  "country_code": "US",
  "province": ""  // Empty
}
```

**Result:**
- ✅ Address still created
- Timezone defaults to country's default (e.g., `"America/New_York"`)
- Backend logs warning (not visible to UI)

**UI Recommendation:** Make `province` required for US, BR, CA, MX (alpha-2)

### 2. Invalid Province

**Request:**
```json
{
  "country_code": "US",
  "province": "InvalidProvince"
}
```

**Result:**
- ✅ Address still created
- Timezone defaults to `"America/New_York"`
- Backend logs warning

**UI Recommendation:** Show validation hint if province doesn't match known values (optional)

### 3. Invalid Country Code

**Request:**
```json
{
  "country_code": "XYZ"  // Invalid
}
```

**Result:**
- ❌ 400 Bad Request
- Error: `"Invalid country_code: XYZ. Market not found."`

**UI Recommendation:** Use Markets API to populate country dropdown

---

## Form Validation Rules

### Recommended Validation

```typescript
// Form validation schema
const addressSchema = {
  country_code: {
    required: true,
    validate: (value) => {
      // Validate against available markets
      const validCodes = markets.map(m => m.country_code);
      return validCodes.includes(value);
    }
  },
  province: {
    required: (formData) => {
      // Required for multi-timezone countries
      const multiTZCountries = ['US', 'BR', 'CA', 'MX'];  // alpha-2
      return multiTZCountries.includes(formData.country_code);
    }
  }
};
```

---

## API Reference

### Get Available Countries

Use the Markets API to populate country dropdown:

```http
GET /api/v1/markets/
```

**Response:**
```json
[
  {
    "market_id": "uuid",
    "country_code": "AR",
    "country_name": "Argentina",
    "timezone": "America/Argentina/Buenos_Aires"
  },
  {
    "market_id": "uuid",
    "country_code": "US",
    "country_name": "United States",
    "timezone": "America/New_York"
  }
]
```

### Get Provinces for Multi-TZ Country (Optional)

```http
GET /location-info/countries/{country_code}/provinces
```

**Example:**
```http
GET /location-info/countries/US/provinces
```

**Response:**
```json
[
  "Alabama", "Alaska", "Arizona", "Arkansas", "California",
  "AL", "AK", "AZ", "AR", "CA",
  ...
]
```

---

## Testing

### Test Scenarios

1. **✅ Single-TZ Country**
   - `country_code: "AR"`, `province: "Buenos Aires"`
   - Expected: `timezone: "America/Argentina/Buenos_Aires"`

2. **✅ Multi-TZ Country with Province**
   - `country_code: "US"`, `province: "California"`
   - Expected: `timezone: "America/Los_Angeles"`

3. **✅ Multi-TZ Country without Province**
   - `country_code: "US"`, `province: ""`
   - Expected: `timezone: "America/New_York"` (default)

4. **✅ Invalid Country Code**
   - `country_code: "XYZ"`
   - Expected: `400 Bad Request`

---

## Migration Checklist

- [ ] Remove `timezone` field from address creation forms
- [ ] Remove `timezone` field from address update forms
- [ ] Ensure `province` field exists in all address forms
- [ ] Make `province` required for US, BR, CA, MX (optional but recommended)
- [ ] Display `timezone` from API response as read-only
- [ ] Update form validation to remove timezone validation
- [ ] Test address creation with single-TZ country (AR)
- [ ] Test address creation with multi-TZ country (US + province)
- [ ] Test address update changing province
- [ ] Update any documentation/tooltips mentioning timezone entry

---

## FAQ

**Q: Can users still manually set timezone?**  
A: No. Timezone is now calculated automatically and cannot be overridden.

**Q: What if the auto-calculated timezone is wrong?**  
A: This indicates either invalid `country_code` or `province`. User should verify their input.

**Q: Do existing addresses need updating?**  
A: No. Existing addresses keep their current timezones. Only new addresses and updates use auto-deduction.

**Q: What happens if I still send `timezone` in the request?**  
A: The backend will ignore it and calculate its own timezone value.

---

## Support

For questions or issues:
- Backend API: See [ADDRESSES_API_CLIENT.md](../shared_client/ADDRESSES_API_CLIENT.md)
- Postman Tests: `docs/postman/collections/TIMEZONE_DEDUCTION_TESTS.postman_collection.json`
- Backend Implementation: `docs/database/TIMEZONE_SIMPLIFICATION_COMPLETED.md`

---

**Last Updated**: February 10, 2026  
**Backend Status**: ✅ Deployed and Ready  
**Action Required**: Update frontend address forms per this guide
