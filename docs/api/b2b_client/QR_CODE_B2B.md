# QR Code (B2B)

**Audience:** B2B clients (Restaurant + Employee roles)

This document describes how to create and display QR codes for restaurant plate pickup. QR codes let customers scan to confirm arrival when picking up plates.

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

The response provides `qr_code_image_url`. Use the **same** URL for both:

1. **Screen display**: Render `<img src={qr_code_image_url} alt="Scan to confirm arrival" />` in a full-screen or modal view. Suitable for tablets or kiosks.
2. **Print**: Provide a "Print" action that prints the image—for example, open a print-friendly page with the image, or use `window.print()` with the image visible. Alternatively, let the user download the image and print from their device.

## Relationship to restaurant activation

A restaurant can be set to **Active** only when:
1. It has at least one non-archived plate with at least one **active** plate_kitchen_days row, **and**
2. It has at least one non-archived QR code with **status = 'Active'**.

If a restaurant has no active QR code, `PUT /api/v1/restaurants/{id}` with `{"status": "Active"}` returns **400** with:
*"Cannot set restaurant to Active. The restaurant must have at least one active QR code. Create a QR code via POST /api/v1/qr-codes for this restaurant, then try again."*

When the last active QR code is archived, deleted, or set to Inactive, the system automatically sets the restaurant to **Inactive**.

See [RESTAURANT_STATUS_AND_PLATE_KITCHEN_DAYS.md](../shared_client/RESTAURANT_STATUS_AND_PLATE_KITCHEN_DAYS.md) for the full activation checklist.
