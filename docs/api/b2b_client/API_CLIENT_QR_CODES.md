# QR Code (B2B)

**Audience:** B2B clients (Restaurant + Employee roles)

This document describes how to create and display QR codes for restaurant vianda pickup. QR codes let customers scan to confirm arrival when picking up viandas.

## Create flow

- **POST /api/v1/qr-codes** accepts only **`restaurant_id`** (no payload input).
- The backend auto-generates `qr_code_payload` as `restaurant_id:{uuid}`.
- **B2B client**: Do **not** show "QR Code Payload" as an input field. Only restaurant selection is needed.

**Request:**
```json
{ "restaurant_id": "<uuid>" }
```

**Response** includes:
- `qr_code_id`
- `qr_code_payload` (backend-generated)
- `qr_code_image_url` (e.g. `http://localhost:8000/static/qr_codes/...` or full URL)
- `image_storage_path`
- `qr_code_checksum`

## Display options (print and screen)

The response provides `qr_code_image_url`. Use the **same** URL for on-screen preview (tablets, kiosks, modals).

### Recommended: server print page (canonical layout)

For physical labels (restaurant name + address + large QR for phone cameras), use the **HTML print endpoints**. The PNG is **embedded as base64** in the HTML so printing still works after signed URLs expire.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/qr-codes/{qr_code_id}/print` | Printable HTML for a QR by id |
| GET | `/api/v1/qr-codes/restaurant/{restaurant_id}/print` | Same content resolved by restaurant |

- **Auth:** `Authorization: Bearer <token>` (same as other QR routes; institution scoping applies).
- **Query `autoprint`:** Use `?autoprint=true` (value must be the word `true`, case-insensitive) to run `window.print()` when the page loads. Omit it (or use any other value) for a preview with a **Print** button only—no auto dialog.
- **Address:** Street line follows market `address_street_order` (same rules as the rest of the app); locality line uses city, province, postal code, and country name.

### B2B SPA integration (token auth)

Browsers do not send `Authorization` headers to a URL opened in a new tab. Fetch the HTML with your API client, then open it as a blob URL:

```typescript
const handlePrint = async (qrCodeId: string) => {
  const response = await apiClient.get(
    `/api/v1/qr-codes/${qrCodeId}/print?autoprint=true`,
    { responseType: 'text' }
  )
  const blob = new Blob([response.data], { type: 'text/html' })
  const url = URL.createObjectURL(blob)
  const printWindow = window.open(url, '_blank')
  printWindow?.addEventListener('afterprint', () => {
    URL.revokeObjectURL(url)
    printWindow.close()
  })
}
```

### Legacy / simple screen display

1. **Screen display**: Render `<img src={qr_code_image_url} alt="Scan to confirm arrival" />` in a full-screen or modal view.
2. **Ad-hoc print**: You may still print from a page that only shows `qr_code_image_url`, but prefer the print endpoints above for consistent sizing and restaurant labeling.

## Relationship to restaurant activation

A restaurant can be set to **Active** only when:
1. It has at least one non-archived vianda with at least one **active** vianda_kitchen_days row, **and**
2. It has at least one non-archived QR code with **status = 'Active'**.

If a restaurant has no active QR code, `PUT /api/v1/restaurants/{id}` with `{"status": "Active"}` returns **400** with:
*"Cannot set restaurant to Active. The restaurant must have at least one active QR code. Create a QR code via POST /api/v1/qr-codes for this restaurant, then try again."*

When the last active QR code is archived, deleted, or set to Inactive, the system automatically sets the restaurant to **Inactive**.

See [RESTAURANT_STATUS_AND_VIANDA_KITCHEN_DAYS.md](../shared_client/RESTAURANT_STATUS_AND_VIANDA_KITCHEN_DAYS.md) for the full activation checklist.
