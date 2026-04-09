# Ads Tracking Integration (B2C App)

Backend API contract for ad conversion tracking in the B2C mobile app. The backend handles server-side conversion uploads (CAPI + Google Enhanced Conversions). The B2C app is responsible for client-side tracking and click ID capture.

**Full design:** `docs/plans/GOOGLE_META_ADS_INTEGRATION_V2.md` section 32.

---

## 1. Click ID Capture API

When a user lands from an ad click, the app extracts click identifiers from URL parameters and cookies, then submits them to the backend.

### Endpoint

```
POST /api/v1/ad-tracking
Authorization: Bearer {token}
```

### Request Body

```json
{
  "subscription_id": "uuid-or-null",
  "gclid": "CjwKCA...",
  "wbraid": null,
  "gbraid": null,
  "fbclid": "fb.1.1234567890.abcdef",
  "fbc": "fb.1.1234567890.abcdef",
  "fbp": "fb.1.1234567890.987654321",
  "event_id": "conv-{subscription_id}",
  "landing_url": "https://vianda.market/plans?gclid=...",
  "source_platform": "meta"
}
```

All fields except `source_platform` are optional. Submit whatever is available.

### Response (201)

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "subscription_id": "uuid-or-null",
  "source_platform": "meta",
  "google_upload_status": "pending",
  "meta_upload_status": "pending",
  "captured_at": "2026-04-09T12:00:00Z",
  "created_date": "2026-04-09T12:00:00Z"
}
```

### When to Call

1. **On app launch / deep link entry:** If URL contains `gclid`, `fbclid`, or other click params, extract and store them (AsyncStorage or equivalent).
2. **After subscription creation:** Include `subscription_id` in the POST body so the backend can link click IDs to the subscription for conversion attribution.
3. **Idempotent:** If a record already exists for this user + subscription_id, returns the existing record.

---

## 2. Click Identifiers to Capture

### From URL Parameters

| URL Param | Storage Key | Platform |
|-----------|------------|----------|
| `gclid` | `ad_gclid` | Google Ads |
| `wbraid` | `ad_wbraid` | Google Ads (iOS) |
| `gbraid` | `ad_gbraid` | Google Ads (iOS) |
| `fbclid` | `ad_fbclid` | Meta Ads |

### From Cookies (Web Build Only)

| Cookie | Storage Key | Set By |
|--------|------------|--------|
| `_fbc` | `ad_fbc` | Meta Pixel JS |
| `_fbp` | `ad_fbp` | Meta Pixel JS |

Store in AsyncStorage (native) or sessionStorage (web). These must survive navigation through the signup and subscription flow.

---

## 3. Meta Pixel JS (Web Build Only)

Install Meta Pixel base code in the web build entry point (`index.html`).

- Only load when `Platform.OS === 'web'`
- Pixel ID will be provided as environment variable
- Do NOT load on native iOS/Android (will not work)

### Events to Fire

```javascript
// On subscription completion
fbq('track', 'Subscribe', {
  value: 29.99,
  currency: 'USD',
}, { eventID: 'conv-{subscription_id}' });

// On trial activation
fbq('track', 'StartTrial', {
  value: 0,
  currency: 'USD',
}, { eventID: 'conv-{subscription_id}' });
```

---

## 4. Meta SDK (Native iOS/Android)

Install `react-native-fbsdk-next` for native event tracking.

```bash
npm install react-native-fbsdk-next
```

### Platform Setup

- iOS: Add Facebook App ID to `Info.plist`
- Android: Add Facebook App ID to `AndroidManifest.xml`
- Docs: https://developers.facebook.com/docs/app-events/getting-started-app-events-react-native

### Events to Fire

```javascript
import { AppEventsLogger } from 'react-native-fbsdk-next';

// On subscription completion
AppEventsLogger.logEvent('Subscribe', 29.00, {
  currency: 'USD',
  subscription_id: 'sub_uuid',
  event_id: 'conv-sub_uuid'
});

// Set user data for EMQ (after login)
AppEventsLogger.setUserData({
  email: 'user@example.com',
  phone: '+1234567890'
});
```

### Platform Detection

```javascript
import { Platform } from 'react-native';

function trackSubscription(subscriptionId, value, currency) {
  const eventId = `conv-${subscriptionId}`;
  if (Platform.OS === 'web') {
    fbq('track', 'Subscribe', { value, currency }, { eventID: eventId });
  } else {
    AppEventsLogger.logEvent('Subscribe', value, {
      currency, subscription_id: subscriptionId, event_id: eventId
    });
  }
}
```

---

## 5. Event ID (Deduplication)

The backend sends the same conversion event via CAPI (server-side). Meta deduplicates using `event_id`. The app and backend MUST use the same `event_id` format.

**Format:** `conv-{subscription_id}`

**Flow:**
1. App calls `POST /api/v1/subscriptions/with-payment`
2. API returns `subscription_id` in response
3. App fires Meta SDK/Pixel event with `event_id: conv-{subscription_id}`
4. App calls `POST /api/v1/ad-tracking` with `event_id` + click IDs + `subscription_id`
5. Backend webhook fires, reads click tracking, sends CAPI event with same `event_id`
6. Meta deduplicates: keeps CAPI (higher quality), drops SDK/Pixel duplicate

---

## 6. Open Questions for B2C Team

1. How does the app currently handle URL query parameters on deep links? Do params like `?gclid=xxx` survive through the app install flow?
2. Does the RN web build use a separate domain from the marketing site? If same domain, only one Pixel base code is needed.
3. What is the current deep link handling library? Need to ensure click ID extraction works with it.
4. Is there an existing analytics/tracking abstraction? Meta SDK events should integrate with it.
