# Plate Pickup Pending Orders API

## Endpoint
```
GET /plate-pickup/pending
```

## Authentication
Requires Bearer token authentication (JWT).

## Response Structure

### Overview
This endpoint returns **a single pending order group** (one restaurant) or `null` if no pending orders exist. The response is **NOT an array** - it's either `null` or a single object.

### Response Types

#### 1. No Pending Orders
**Status Code**: `200 OK`  
**Response Body**: `null`

```json
null
```

**Frontend Handling**:
- Check if response is `null` or `undefined`
- Display "No pending orders" message
- Hide any order-related UI elements

---

#### 2. Pending Orders Found
**Status Code**: `200 OK`  
**Response Body**: Single `PendingOrdersResponse` object

```typescript
interface PendingOrdersResponse {
  restaurant_id: string;           // UUID
  restaurant_name: string;
  qr_code_id: string;               // UUID
  total_orders: number;             // Total count of all plates
  orders: PlateOrderSummary[];      // Array of plate orders (can be empty, 1, or multiple)
  pickup_window: PickupTimeWindow;
  status: string;                   // "Pending" or "Arrived"
  created_date: string;             // ISO 8601 datetime
}

interface PlateOrderSummary {
  plate_name: string;
  order_count: string;              // "x1", "x2", "x3", etc.
  delivery_time_minutes: number;
}

interface PickupTimeWindow {
  start_time: string;              // ISO 8601 datetime
  end_time: string;                // ISO 8601 datetime
  window_minutes: number;          // Always 15
}
```

**Example Response**:
```json
{
  "restaurant_id": "123e4567-e89b-12d3-a456-426614174000",
  "restaurant_name": "La Cocina",
  "qr_code_id": "987fcdeb-51a2-43f7-b890-123456789abc",
  "total_orders": 3,
  "orders": [
    {
      "plate_name": "Grilled Chicken",
      "order_count": "x1",
      "delivery_time_minutes": 15
    },
    {
      "plate_name": "Vegetarian Pasta",
      "order_count": "x2",
      "delivery_time_minutes": 20
    }
  ],
  "pickup_window": {
    "start_time": "2025-11-17T12:00:00-08:00",
    "end_time": "2025-11-17T12:15:00-08:00",
    "window_minutes": 15
  },
  "status": "Pending",
  "created_date": "2025-11-17T11:30:00-08:00"
}
```

---

## Frontend Parsing Guide

### TypeScript/JavaScript Example

```typescript
interface PendingOrdersResponse {
  restaurant_id: string;
  restaurant_name: string;
  qr_code_id: string;
  total_orders: number;
  orders: Array<{
    plate_name: string;
    order_count: string;
    delivery_time_minutes: number;
  }>;
  pickup_window: {
    start_time: string;
    end_time: string;
    window_minutes: number;
  };
  status: "Pending" | "Arrived";
  created_date: string;
}

async function fetchPendingOrders(): Promise<PendingOrdersResponse | null> {
  const response = await fetch('/plate-pickup/pending', {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  const data = await response.json();
  
  // Handle null response (no orders)
  if (data === null || data === undefined) {
    return null;
  }
  
  // Validate response structure
  if (typeof data !== 'object') {
    throw new Error('Invalid response format');
  }
  
  return data as PendingOrdersResponse;
}

// Usage
const pendingOrders = await fetchPendingOrders();

if (pendingOrders === null) {
  // No orders - show empty state
  displayEmptyState();
} else {
  // Orders found - display them
  displayOrders(pendingOrders);
  
  // Check orders array length
  if (pendingOrders.orders.length === 0) {
    console.warn('Response has no orders in array (unexpected)');
  } else if (pendingOrders.orders.length === 1) {
    // Single order
    displaySingleOrder(pendingOrders.orders[0]);
  } else {
    // Multiple orders
    displayMultipleOrders(pendingOrders.orders);
  }
}
```

---

## Key Points for Frontend

1. **Response is NOT an array**: The endpoint returns a single object or `null`, never an array of objects.

2. **Null handling**: Always check for `null` before accessing properties:
   ```typescript
   if (response === null) {
     // Handle no orders
   } else {
     // Access response.restaurant_id, response.orders, etc.
   }
   ```

3. **Orders array**: The `orders` field is an array that can contain:
   - **0 items**: Empty array (unlikely but possible)
   - **1 item**: Single plate order
   - **Multiple items**: Multiple different plates

4. **Order count format**: The `order_count` field is a string like `"x1"`, `"x2"`, `"x3"` representing quantity.

5. **Pickup window**: Informational only - shows the 15-minute window when pickup is planned (constrained to 11:30 AM - 2:30 PM local time).

6. **Status values**: Can be `"Pending"` or `"Arrived"`.

7. **Date formats**: All datetime fields are ISO 8601 strings (e.g., `"2025-11-17T12:00:00-08:00"`).

---

## Error Handling

### HTTP Status Codes
- `200 OK`: Success (response may be `null` or an object)
- `401 Unauthorized`: Missing or invalid authentication token
- `500 Internal Server Error`: Server error

### Common Frontend Errors

**Error**: "Cannot read property 'restaurant_id' of null"
- **Cause**: Accessing properties without checking for `null` first
- **Fix**: Always check `if (response !== null)` before accessing properties

**Error**: "response.map is not a function"
- **Cause**: Treating the response as an array when it's a single object
- **Fix**: Access `response.orders` (which is the array) instead of `response`

**Error**: "orders is undefined"
- **Cause**: Response structure is invalid or corrupted
- **Fix**: Validate response structure before accessing nested properties

---

## Example UI States

### Empty State (response === null)
```
┌─────────────────────────┐
│   No Pending Orders     │
│                         │
│  You don't have any     │
│  pending plate orders.  │
└─────────────────────────┘
```

### Single Order State
```
┌─────────────────────────┐
│  La Cocina              │
│  ─────────────────────  │
│  • Grilled Chicken (x1)  │
│                         │
│  Pickup: 12:00 - 12:15  │
│  [Scan QR Code]         │
└─────────────────────────┘
```

### Multiple Orders State
```
┌─────────────────────────┐
│  La Cocina              │
│  ─────────────────────  │
│  • Grilled Chicken (x1)  │
│  • Vegetarian Pasta (x2) │
│                         │
│  Total: 3 plates        │
│  Pickup: 12:00 - 12:15  │
│  [Scan QR Code]         │
└─────────────────────────┘
```

---

## Related Endpoints

- `POST /plate-pickup/scan-qr`: Scan QR code to mark arrival
- `DELETE /plate-pickup/{pickup_id}`: Delete a pickup record

