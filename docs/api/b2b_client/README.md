# B2B Client Documentation (kitchen-web)

**Last Updated**: 2026-02-10  
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
| EMPLOYER_ASSIGNMENT_WORKFLOW.md | Backoffice employer management |
| EMPLOYER_ADDRESS_PROTECTION_AND_CITIES_B2B.md | Employer address protection (Customers 403); Cities API; `city_id` filter |
| ROLE_AND_FIELD_ACCESS_CLIENT.md | Role/field access for B2B |
| PLAN_API_MARKET_CURRENCY.md | Plan create/update: no credit_currency_id; currency from market |
| RESTAURANT_AND_INSTITUTION_ENTITY_CREDIT_CURRENCY.md | Restaurant and institution entity create: no credit_currency_id; derived from entity address → market |
| DISCRETIONARY_REQUEST_FORM_GUIDE.md | Discretionary credit requests |
| CHANGE_PASSWORD_AND_ADMIN_RESET.md | Password change, admin reset |
| (MARKET_SCOPE_FOR_CLIENTS in shared_client) | Markets API and market scope – shared |
| PASSWORD_RECOVERY_CLIENT.md | Password recovery |
| [USERNAME_RECOVERY.md](../shared_client/USERNAME_RECOVERY.md) | Username recovery (forgot username) |
| (ENUM_SERVICE_API in shared_client) | Enum service – shared |
| TIMEZONE_AUTO_DEDUCTION_UI_GUIDE.md | Timezone deduction UI |
| TIMEZONE_AUTO_DEDUCTION_UI_GUIDE.md | Timezone deduction |
| [SUPPORTED_CURRENCIES_API.md](./SUPPORTED_CURRENCIES_API.md) | Supported currencies list (dropdown); credit currency create with currency_name only (backend assigns currency_code). |
| [PRODUCT_API_B2B.md](./PRODUCT_API_B2B.md) | Product CRUD, image upload (1 upload → 2 stored: thumbnail + full-size); enriched returns both image sizes for suppliers. |
| feedback_from_client/ | B2B team feedback (addressed items moved to [zArchive/api/b2b_client](../../zArchive/api/b2b_client/)) |
| [PAYMENT_METHOD_CHANGES_B2B](./PAYMENT_METHOD_CHANGES_B2B.md) | **B2B:** Institution bank account and fintech links removed; subscription payment flow; migration checklist. |
| [QR_CODE_B2B.md](./QR_CODE_B2B.md) | **B2B:** QR code create flow (restaurant only), display (print vs screen), relationship to restaurant activation. |
| [SUPPLIER_DASHBOARD_METRICS_B2B.md](./SUPPLIER_DASHBOARD_METRICS_B2B.md) | **B2B:** Supplier dashboard metrics: reservations by plate, live locked, people waiting, plates delivered, daily balance, average portion size, average plate rating. |
| [PAYMENT_AND_BILLING_CLIENT_CHANGES](../shared_client/PAYMENT_AND_BILLING_CLIENT_CHANGES.md) | **Shared:** Payment atomic with billing; remove fintech link pages/modals and manual bill create/process flows. |

## Shared Docs (from shared_client/)

API_PERMISSIONS_BY_ROLE, USER_SELF_UPDATE_PATTERN, ENRICHED_ENDPOINT_PATTERN, ARCHIVED_RECORDS_PATTERN, SCOPING_BEHAVIOR_FOR_UI, BULK_API_PATTERN, ENRICHED_ENDPOINT_UI_IMPLEMENTATION, **ADDRESSES_API_CLIENT** (includes **address types by role**: restrict create/edit address forms to allowed types per role to avoid 403 and poor UX), PLANS_FILTER_CLIENT_INTEGRATION, MARKET_BASED_SUBSCRIPTIONS, MARKET_MIGRATION_GUIDE, PLATE_API_CLIENT (plate pickup pending, plate selection, enriched endpoint).

Links use `../shared_client/FILE.md` – works when shared_client and b2b_client folders exist in docs/api/.
