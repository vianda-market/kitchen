# B2B Client Documentation (kitchen-web)

**Last Updated**: 2026-03-19  
**Audience**: kitchen-web (Restaurant + Employee)

B2B-specific docs. **Copy with shared_client/** – see [../shared_client/README.md](../shared_client/README.md).

## Copy Instructions

```bash
cp -r docs/api/shared_client /path/to/kitchen-web/docs/api/
cp -r docs/api/b2b_client /path/to/kitchen-web/docs/api/
```

## B2B-Specific Docs (this folder)

| File | Use |
|------|-----|
| FRONTEND_AGENT_README.md | Agent onboarding |
| [LOCAL_NETWORK_DEV.md](./LOCAL_NETWORK_DEV.md) | Local backend run scripts; API URL config for trusted/untrusted network |
| API_CLIENT_EMPLOYER_ASSIGNMENT.md | Backoffice employer management |
| API_CLIENT_EMPLOYER_ADDRESSES_CITIES.md | Employer address protection (Customers 403); Cities API; `city_id` filter |
| API_CLIENT_ROLE_FIELD_ACCESS.md | Role/field access for B2B |
| (CREDIT_AND_CURRENCY_CLIENT in shared_client) | Credit currency create/edit, plan/restaurant/entity currency from market, plate payouts, B2C savings |
| DISCRETIONARY_REQUEST_FORM_GUIDE.md | Discretionary credit requests |
| API_CLIENT_PASSWORD_MANAGEMENT.md | Password change, admin reset |
| (MARKET_SCOPE_FOR_CLIENTS in shared_client) | Markets API and market scope – shared |
| **USER_MODEL_FOR_CLIENTS.md** (shared_client) | **User model:** roles, **`mobile_number` (E.164)**, `/users/me`, markets, forgot-username, password recovery. Long UI samples: [zArchive/.../PASSWORD_RECOVERY_CLIENT.md](../../zArchive/api/shared_client/PASSWORD_RECOVERY_CLIENT.md) |
| (ENUM_SERVICE_API in shared_client) | Enum service – shared |
| TIMEZONE_AUTO_DEDUCTION_UI_GUIDE.md | Timezone deduction UI |
| TIMEZONE_AUTO_DEDUCTION_UI_GUIDE.md | Timezone deduction |
| [API_CLIENT_PRODUCTS.md](./API_CLIENT_PRODUCTS.md) | Product CRUD, image upload (1 upload → 2 stored: thumbnail + full-size); enriched returns both image sizes for suppliers. |
| feedback_from_client/ | B2B team feedback (addressed items moved to [zArchive/api/b2b_client](../../zArchive/api/b2b_client/)) |
| [PAYMENT_METHOD_CHANGES_B2B](./PAYMENT_METHOD_CHANGES_B2B.md) | **B2B:** Institution bank account and fintech links removed; subscription payment flow; migration checklist. |
| [API_CLIENT_QR_CODES.md](./API_CLIENT_QR_CODES.md) | **B2B:** QR code create flow (restaurant only), display (print vs screen), relationship to restaurant activation. |
| [SUPPLIER_DASHBOARD_METRICS_B2B.md](./SUPPLIER_DASHBOARD_METRICS_B2B.md) | **B2B:** Supplier dashboard metrics: reservations by plate, live locked, people waiting, plates delivered, daily balance, average portion size, average plate rating. |
| [API_CLIENT_NATIONAL_HOLIDAYS.md](./API_CLIENT_NATIONAL_HOLIDAYS.md) | **Internal only:** National holidays (country-wide), Nager.Date import, **`POST .../sync-from-provider`** for manual refresh button, CRUD/bulk for gaps. |
| [PAYMENT_AND_BILLING_CLIENT_CHANGES](../shared_client/PAYMENT_AND_BILLING_CLIENT_CHANGES.md) | **Shared:** Payment atomic with billing; remove fintech link pages/modals and manual bill create/process flows. |

## Shared Docs (from shared_client/)

API_PERMISSIONS_BY_ROLE, **USER_MODEL_FOR_CLIENTS** (replaces USER_SELF_UPDATE_PATTERN and related user docs), ENRICHED_ENDPOINT_PATTERN, ARCHIVED_RECORDS_PATTERN, SCOPING_BEHAVIOR_FOR_UI, BULK_API_PATTERN, ENRICHED_ENDPOINT_UI_IMPLEMENTATION, **ADDRESSES_API_CLIENT** (includes **address types by role**: restrict create/edit address forms to allowed types per role to avoid 403 and poor UX), **CREDIT_AND_CURRENCY_CLIENT** (credit currency, plan/restaurant/entity currency from market, plate payouts, B2C savings), PLANS_FILTER_CLIENT_INTEGRATION, MARKET_BASED_SUBSCRIPTIONS, MARKET_MIGRATION_GUIDE, PLATE_API_CLIENT (plate pickup pending, plate selection, enriched endpoint).

Links use `../shared_client/FILE.md` – works when shared_client and b2b_client folders exist in docs/api/.
