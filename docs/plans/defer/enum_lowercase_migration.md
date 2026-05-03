# Plan: Migrate Enums to Lowercase Values

## Context
Audit found **22 of 31 Python enums** use Title Case or UPPERCASE values instead of the target pattern: lowercase value, Title Case member name.

## Compliant (no changes needed)
PickupType, PortionSizeDisplay, DietaryFlag, TaxClassification, BenefitCapPeriod, EnrollmentMode, BillingCycle, PaymentFrequency, InterestType, LeadInterestStatus, LeadInterestSource, FavoriteEntityType, CuisineOriginSource

## Need migration (Title Case -> lowercase)
Status, RoleType, RoleName, SubscriptionStatus, AddressType, TransactionType, DiscretionaryStatus, DiscretionaryReason, BillResolution, BillPayoutStatus, EmployerBillPaymentStatus, SupplierInvoiceStatus, SupplierInvoiceType, CuisineSuggestionStatus, PaymentMethodProvider

## Special cases
- **AuditOperation** — UPPERCASE values ("CREATE", "UPDATE", etc.)
- **KitchenDay** — day names ("Monday", "Tuesday") — may want to keep as-is
- **StreetType** — abbreviations ("St", "Ave", "Blvd") — display values, likely keep as-is

## Migration scope per enum
1. `schema.sql` — ALTER TYPE or recreate enum with lowercase values
2. `seed.sql` — update all seeded rows
3. `trigger.sql` — update any hardcoded enum references
4. Python enum file — change `.value` strings to lowercase
5. Existing DB data — UPDATE statements for every table/column using the enum
6. `enum_labels.py` — verify i18n labels still map correctly

## Risks
- Stripe webhooks or external systems may send/expect specific casing
- Frontend may compare against enum values directly
- Seed data and test collections reference current values
