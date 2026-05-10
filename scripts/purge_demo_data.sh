#!/usr/bin/env bash
# =============================================================================
# purge_demo_data.sh — Remove all demo-day data rows from the dev DB
#
# Usage:
#   bash scripts/purge_demo_data.sh
#
# Deletes all rows whose primary key starts with 'dddddddd-dec0-' in
# dependency order (children first, parents last).  Runs in a single
# transaction — a partial failure rolls back completely.
#
# Safe: same ENV and DB_HOST guards as load_demo_data.sh.
# Idempotent: re-running against an already-clean DB is a no-op.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Environment guards
# ---------------------------------------------------------------------------

ENV="${ENV:-dev}"
if [ "${ENV}" != "dev" ]; then
  echo "ERROR: purge_demo_data.sh is dev-only. ENV=${ENV} is not permitted."
  exit 1
fi

DB_HOST="${DB_HOST:-localhost}"
case "${DB_HOST}" in
  *prod*|*staging*)
    echo "ERROR: purge_demo_data.sh refuses to run against DB_HOST=${DB_HOST}."
    exit 1
    ;;
esac

# ---------------------------------------------------------------------------
# DB connection defaults
# ---------------------------------------------------------------------------

DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-kitchen}"
DB_USER="${DB_USER:-$(whoami)}"

PSQL_ARGS=(
  -h "${DB_HOST}"
  -p "${DB_PORT}"
  -U "${DB_USER}"
  -d "${DB_NAME}"
  -v ON_ERROR_STOP=1
)

# ---------------------------------------------------------------------------
# Purge in dependency order (children → parents), wrapped in a transaction
# ---------------------------------------------------------------------------

echo ""
echo "=== DEMO DATA PURGE ==="
echo ""
echo "Purging all rows with UUID prefix 'dddddddd-dec0-' from kitchen..."
echo "Running in a single transaction (rolls back on any error)."
echo ""

psql "${PSQL_ARGS[@]}" <<'PGSQL'
BEGIN;

SET search_path = core, ops, customer, billing, audit, public;

-- -------------------------------------------------------------------------
-- Tier 1: Most granular child rows (reviews, billing, orders)
-- -------------------------------------------------------------------------

-- Institution settlements (run-settlement-pipeline results).
-- institution_settlement.balance_event_id → restaurant_balance_history (RESTRICT)
-- institution_settlement.institution_bill_id → institution_bill_info (RESTRICT)
-- Must be deleted before both restaurant_balance_history and institution_bill_info.
DELETE FROM audit.institution_settlement_history
WHERE settlement_id IN (
    SELECT settlement_id FROM billing.institution_settlement
    WHERE restaurant_id IN (
        SELECT restaurant_id FROM ops.restaurant_info
        WHERE canonical_key LIKE 'DEMO_%'
    )
);

DELETE FROM billing.institution_settlement
WHERE restaurant_id IN (
    SELECT restaurant_id FROM ops.restaurant_info
    WHERE canonical_key LIKE 'DEMO_%'
);

-- Institution bills: audit history + bills for all demo entities.
-- Covers:
--   dec0-0050 sub-range: Layer C billing backfill for secondary suppliers
--                        (entity IDs are dynamic/non-dec0; matched by bill_id prefix)
--   dynamic UUIDs:       pipeline-generated bills for primary entities that now
--                        have DB-assigned UUIDs (matched by entity canonical_key)
--   dec0-prefixed:       legacy/fixed entity IDs from the old seed approach
-- Must go before institution_entity deletion (FK RESTRICT).
DELETE FROM audit.institution_bill_history
WHERE institution_bill_id IN (
    SELECT institution_bill_id FROM billing.institution_bill_info
    WHERE institution_entity_id::text LIKE 'dddddddd-dec0-%'
       OR institution_bill_id::text LIKE 'dddddddd-dec0-0050%'
       OR institution_entity_id IN (
           SELECT institution_entity_id FROM ops.institution_entity_info
           WHERE canonical_key LIKE 'DEMO_INSTITUTION_ENTITY_%'
       )
);

DELETE FROM billing.institution_bill_info
WHERE institution_entity_id::text LIKE 'dddddddd-dec0-%'
   OR institution_bill_id::text LIKE 'dddddddd-dec0-0050%'
   OR institution_entity_id IN (
       SELECT institution_entity_id FROM ops.institution_entity_info
       WHERE canonical_key LIKE 'DEMO_INSTITUTION_ENTITY_%'
   );

-- Plate reviews (linked to plate_pickup_live via plate_pickup_id)
DELETE FROM customer.plate_review_info
WHERE user_id IN (
    SELECT user_id FROM core.user_info
    WHERE user_id::text LIKE 'dddddddd-dec0-%'
       OR username LIKE 'demo.cliente.pe.%@vianda.demo'
       OR username LIKE 'demo.cliente.ar.%@vianda.demo'
       OR username LIKE 'demo.cliente.us.%@vianda.demo'
       OR username LIKE 'demo.proveedor.%@vianda.demo'
       OR username LIKE 'demo.empresa.%@vianda.demo'
       OR username LIKE 'demo.empleado.%@vianda.demo'
);
-- Also catch any review linked to a demo pickup regardless of user_id
DELETE FROM customer.plate_review_info
WHERE plate_pickup_id IN (
    SELECT plate_pickup_id FROM customer.plate_pickup_live
    WHERE user_id IN (
        SELECT user_id FROM core.user_info
        WHERE username LIKE 'demo.cliente.pe.%@vianda.demo'
           OR username LIKE 'demo.cliente.ar.%@vianda.demo'
           OR username LIKE 'demo.cliente.us.%@vianda.demo'
    )
);

-- Billing: client transactions triggered by plate_selection inserts
DELETE FROM billing.client_transaction
WHERE user_id IN (
    SELECT user_id FROM core.user_info
    WHERE username LIKE 'demo.cliente.pe.%@vianda.demo'
       OR username LIKE 'demo.cliente.ar.%@vianda.demo'
       OR username LIKE 'demo.cliente.us.%@vianda.demo'
);

-- Billing: restaurant transactions linked to demo restaurant
DELETE FROM billing.restaurant_transaction
WHERE plate_selection_id IN (
    SELECT plate_selection_id FROM customer.plate_selection_info
    WHERE user_id IN (
        SELECT user_id FROM core.user_info
        WHERE username LIKE 'demo.cliente.pe.%@vianda.demo'
           OR username LIKE 'demo.cliente.ar.%@vianda.demo'
           OR username LIKE 'demo.cliente.us.%@vianda.demo'
    )
);

-- Billing: client bills for demo subscriptions
-- (must be deleted before subscription_payment due to FK RESTRICT)
DELETE FROM audit.client_bill_history
WHERE client_bill_id IN (
    SELECT client_bill_id FROM billing.client_bill_info
    WHERE user_id IN (
        SELECT user_id FROM core.user_info
        WHERE username LIKE 'demo.cliente.pe.%@vianda.demo'
           OR username LIKE 'demo.cliente.ar.%@vianda.demo'
           OR username LIKE 'demo.cliente.us.%@vianda.demo'
    )
);

DELETE FROM billing.client_bill_info
WHERE user_id IN (
    SELECT user_id FROM core.user_info
    WHERE username LIKE 'demo.cliente.pe.%@vianda.demo'
       OR username LIKE 'demo.cliente.ar.%@vianda.demo'
       OR username LIKE 'demo.cliente.us.%@vianda.demo'
);

-- Capture payment_attempt_ids tied to demo subscriptions before deleting
-- subscription_payment (subscription_payment.payment_attempt_id RESTRICTs
-- payment_attempt deletion, but the demo-attempt rows have no other FKs).
CREATE TEMP TABLE _demo_payment_attempt_ids ON COMMIT DROP AS
SELECT DISTINCT payment_attempt_id
FROM customer.subscription_payment
WHERE payment_attempt_id IS NOT NULL
  AND subscription_id IN (
    SELECT subscription_id FROM customer.subscription_info
    WHERE user_id IN (
        SELECT user_id FROM core.user_info
        WHERE username LIKE 'demo.cliente.pe.%@vianda.demo'
           OR username LIKE 'demo.cliente.ar.%@vianda.demo'
           OR username LIKE 'demo.cliente.us.%@vianda.demo'
    )
  );

-- Subscription payments (FK gateway: client_bill_info → subscription_payment → {subscription_info, payment_attempt})
DELETE FROM customer.subscription_payment
WHERE subscription_id IN (
    SELECT subscription_id FROM customer.subscription_info
    WHERE user_id IN (
        SELECT user_id FROM core.user_info
        WHERE username LIKE 'demo.cliente.pe.%@vianda.demo'
           OR username LIKE 'demo.cliente.ar.%@vianda.demo'
           OR username LIKE 'demo.cliente.us.%@vianda.demo'
    )
);

-- Now safe to delete the captured payment_attempt rows (and their audit trail)
DELETE FROM audit.payment_attempt_history
WHERE payment_attempt_id IN (SELECT payment_attempt_id FROM _demo_payment_attempt_ids);

DELETE FROM billing.payment_attempt
WHERE payment_attempt_id IN (SELECT payment_attempt_id FROM _demo_payment_attempt_ids);

-- Plate selection history (audit trail for plate_selection_info)
DELETE FROM audit.plate_selection_history
WHERE plate_selection_id IN (
    SELECT plate_selection_id FROM customer.plate_selection_info
    WHERE user_id IN (
        SELECT user_id FROM core.user_info
        WHERE username LIKE 'demo.cliente.pe.%@vianda.demo'
           OR username LIKE 'demo.cliente.ar.%@vianda.demo'
           OR username LIKE 'demo.cliente.us.%@vianda.demo'
    )
);

-- Plate pickup history (audit trail for plate_pickup_live)
DELETE FROM audit.plate_pickup_live_history
WHERE plate_pickup_id IN (
    SELECT plate_pickup_id FROM customer.plate_pickup_live
    WHERE user_id IN (
        SELECT user_id FROM core.user_info
        WHERE username LIKE 'demo.cliente.pe.%@vianda.demo'
           OR username LIKE 'demo.cliente.ar.%@vianda.demo'
           OR username LIKE 'demo.cliente.us.%@vianda.demo'
    )
);

-- Plate pickup live (must go before plate_selection_info — FK plate_pickup_live → plate_selection_info)
DELETE FROM customer.plate_pickup_live
WHERE user_id IN (
    SELECT user_id FROM core.user_info
    WHERE username LIKE 'demo.cliente.pe.%@vianda.demo'
       OR username LIKE 'demo.cliente.ar.%@vianda.demo'
       OR username LIKE 'demo.cliente.us.%@vianda.demo'
);

-- Plate selections (customer orders)
DELETE FROM customer.plate_selection_info
WHERE user_id IN (
    SELECT user_id FROM core.user_info
    WHERE username LIKE 'demo.cliente.pe.%@vianda.demo'
       OR username LIKE 'demo.cliente.ar.%@vianda.demo'
       OR username LIKE 'demo.cliente.us.%@vianda.demo'
);

-- Subscription history
DELETE FROM audit.subscription_history
WHERE subscription_id IN (
    SELECT subscription_id FROM customer.subscription_info
    WHERE user_id IN (
        SELECT user_id FROM core.user_info
        WHERE username LIKE 'demo.cliente.pe.%@vianda.demo'
           OR username LIKE 'demo.cliente.ar.%@vianda.demo'
           OR username LIKE 'demo.cliente.us.%@vianda.demo'
           OR username LIKE 'demo.empleado.%@vianda.demo'
    )
)
   OR subscription_id IN (
    SELECT subscription_id FROM customer.subscription_info
    WHERE canonical_key LIKE 'DEMO_EMPLOYER_%'
);

-- Subscriptions (customers + enrolled employees)
DELETE FROM customer.subscription_info
WHERE user_id IN (
    SELECT user_id FROM core.user_info
    WHERE username LIKE 'demo.cliente.pe.%@vianda.demo'
       OR username LIKE 'demo.cliente.ar.%@vianda.demo'
       OR username LIKE 'demo.cliente.us.%@vianda.demo'
       OR username LIKE 'demo.empleado.%@vianda.demo'
);
-- Also catch any subscriptions with canonical_key DEMO_EMPLOYER_*
DELETE FROM customer.subscription_info
WHERE canonical_key LIKE 'DEMO_EMPLOYER_%';
-- Also catch any dec0-prefixed subscription IDs from old approach
DELETE FROM customer.subscription_info
WHERE subscription_id::text LIKE 'dddddddd-dec0-%';

-- Discretionary credit records (auto-created when a subscription is confirmed)
DELETE FROM audit.discretionary_resolution_history
WHERE discretionary_id IN (
    SELECT discretionary_id FROM billing.discretionary_info
    WHERE user_id IN (
        SELECT user_id FROM core.user_info
        WHERE user_id::text LIKE 'dddddddd-dec0-%'
           OR username LIKE 'demo.cliente.pe.%@vianda.demo'
           OR username LIKE 'demo.cliente.ar.%@vianda.demo'
           OR username LIKE 'demo.cliente.us.%@vianda.demo'
    )
);
-- Live discretionary_resolution_info rows RESTRICT discretionary_info delete.
-- Must be deleted before billing.discretionary_info below.
DELETE FROM billing.discretionary_resolution_info
WHERE discretionary_id IN (
    SELECT discretionary_id FROM billing.discretionary_info
    WHERE user_id IN (
        SELECT user_id FROM core.user_info
        WHERE user_id::text LIKE 'dddddddd-dec0-%'
           OR username LIKE 'demo.cliente.pe.%@vianda.demo'
           OR username LIKE 'demo.cliente.ar.%@vianda.demo'
           OR username LIKE 'demo.cliente.us.%@vianda.demo'
    )
);
DELETE FROM audit.discretionary_history
WHERE discretionary_id IN (
    SELECT discretionary_id FROM billing.discretionary_info
    WHERE user_id IN (
        SELECT user_id FROM core.user_info
        WHERE user_id::text LIKE 'dddddddd-dec0-%'
           OR username LIKE 'demo.cliente.pe.%@vianda.demo'
           OR username LIKE 'demo.cliente.ar.%@vianda.demo'
           OR username LIKE 'demo.cliente.us.%@vianda.demo'
    )
);
DELETE FROM billing.discretionary_info
WHERE user_id IN (
    SELECT user_id FROM core.user_info
    WHERE user_id::text LIKE 'dddddddd-dec0-%'
       OR username LIKE 'demo.cliente.pe.%@vianda.demo'
       OR username LIKE 'demo.cliente.ar.%@vianda.demo'
       OR username LIKE 'demo.cliente.us.%@vianda.demo'
);

-- -------------------------------------------------------------------------
-- Tier 2: Plate kitchen days (depend on plates)
-- -------------------------------------------------------------------------

DELETE FROM audit.plate_kitchen_days_history
WHERE plate_kitchen_day_id IN (
    SELECT plate_kitchen_day_id FROM ops.plate_kitchen_days
    WHERE canonical_key LIKE 'DEMO_%'
);

DELETE FROM ops.plate_kitchen_days
WHERE canonical_key LIKE 'DEMO_%';

-- -------------------------------------------------------------------------
-- Tier 3: Plates (depend on products and restaurants)
-- -------------------------------------------------------------------------

DELETE FROM audit.plate_history
WHERE plate_id IN (
    SELECT plate_id FROM ops.plate_info WHERE canonical_key LIKE 'DEMO_%'
);

DELETE FROM ops.plate_info
WHERE canonical_key LIKE 'DEMO_%';

-- -------------------------------------------------------------------------
-- Tier 4: Restaurant holidays and QR codes (depend on restaurants)
-- -------------------------------------------------------------------------

DELETE FROM audit.restaurant_holidays_history
WHERE holiday_id IN (
    SELECT holiday_id FROM ops.restaurant_holidays
    WHERE restaurant_id IN (
        SELECT restaurant_id FROM ops.restaurant_info WHERE canonical_key LIKE 'DEMO_%'
    )
);

DELETE FROM ops.restaurant_holidays
WHERE restaurant_id IN (
    SELECT restaurant_id FROM ops.restaurant_info WHERE canonical_key LIKE 'DEMO_%'
);

DELETE FROM ops.qr_code
WHERE restaurant_id IN (
    SELECT restaurant_id FROM ops.restaurant_info WHERE canonical_key LIKE 'DEMO_%'
);

-- -------------------------------------------------------------------------
-- Tier 4b: Restaurant balance (auto-created when a restaurant is activated)
-- -------------------------------------------------------------------------

DELETE FROM audit.restaurant_balance_history
WHERE restaurant_id IN (
    SELECT restaurant_id FROM ops.restaurant_info
    WHERE canonical_key LIKE 'DEMO_%'
);

DELETE FROM billing.restaurant_balance_info
WHERE restaurant_id IN (
    SELECT restaurant_id FROM ops.restaurant_info
    WHERE canonical_key LIKE 'DEMO_%'
);

-- -------------------------------------------------------------------------
-- Tier 5: Restaurants (depend on institution_entity and addresses)
-- -------------------------------------------------------------------------

DELETE FROM audit.restaurant_history
WHERE restaurant_id IN (
    SELECT restaurant_id FROM ops.restaurant_info
    WHERE canonical_key LIKE 'DEMO_%'
);

DELETE FROM ops.restaurant_info
WHERE canonical_key LIKE 'DEMO_%';

-- -------------------------------------------------------------------------
-- Tier 6: Products (depend on institution)
-- -------------------------------------------------------------------------

DELETE FROM audit.product_history
WHERE product_id IN (
    SELECT product_id FROM ops.product_info
    WHERE canonical_key LIKE 'DEMO_%'
      AND institution_id::text LIKE 'dddddddd-dec0-%'
);

DELETE FROM ops.product_info
WHERE canonical_key LIKE 'DEMO_%'
  AND institution_id::text LIKE 'dddddddd-dec0-%';

-- -------------------------------------------------------------------------
-- Tier 7: Plans (depend on markets — markets are reference data, not purged)
-- -------------------------------------------------------------------------

DELETE FROM audit.plan_history
WHERE plan_id IN (
    SELECT plan_id FROM customer.plan_info WHERE canonical_key LIKE 'DEMO_%'
);

DELETE FROM customer.plan_info
WHERE canonical_key LIKE 'DEMO_%';

-- -------------------------------------------------------------------------
-- Tier 8: Institution entity (depends on institution and address)
-- -------------------------------------------------------------------------

DELETE FROM audit.institution_entity_history
WHERE institution_entity_id::text LIKE 'dddddddd-dec0-%';

DELETE FROM ops.institution_entity_info
WHERE institution_entity_id::text LIKE 'dddddddd-dec0-%';

-- -------------------------------------------------------------------------
-- Tier 8b: Secondary supplier institution entities — dynamically created by
-- Newman (Layer B) using PUT /institution-entities/by-key.  They have
-- DB-assigned UUIDs (not dec0-prefixed), so we match on canonical_key.
-- -------------------------------------------------------------------------

DELETE FROM audit.institution_entity_history
WHERE institution_entity_id IN (
    SELECT institution_entity_id FROM ops.institution_entity_info
    WHERE canonical_key IN (
        'DEMO_INSTITUTION_ENTITY_PE2',
        'DEMO_INSTITUTION_ENTITY_AR2',
        'DEMO_INSTITUTION_ENTITY_US2'
    )
);

DELETE FROM ops.institution_entity_info
WHERE canonical_key IN (
    'DEMO_INSTITUTION_ENTITY_PE2',
    'DEMO_INSTITUTION_ENTITY_AR2',
    'DEMO_INSTITUTION_ENTITY_US2'
);

-- -------------------------------------------------------------------------
-- Tier 8c: Primary institution entities — dynamically created by Newman
-- (Layer B) with PUT /institution-entities/by-key.
-- -------------------------------------------------------------------------

DELETE FROM audit.institution_entity_history
WHERE institution_entity_id IN (
    SELECT institution_entity_id FROM ops.institution_entity_info
    WHERE canonical_key IN (
        'DEMO_INSTITUTION_ENTITY_PE',
        'DEMO_INSTITUTION_ENTITY_AR',
        'DEMO_INSTITUTION_ENTITY_US'
    )
);

DELETE FROM ops.institution_entity_info
WHERE canonical_key IN (
    'DEMO_INSTITUTION_ENTITY_PE',
    'DEMO_INSTITUTION_ENTITY_AR',
    'DEMO_INSTITUTION_ENTITY_US'
);

-- -------------------------------------------------------------------------
-- Tier 8d: Employer institution entities (depend on address; must precede
-- address deletion because entity.address_id → address_info RESTRICT).
-- -------------------------------------------------------------------------

-- Entity history MUST be deleted before entity rows (RESTRICT FK)
DELETE FROM audit.institution_entity_history
WHERE institution_entity_id IN (
    SELECT institution_entity_id FROM ops.institution_entity_info
    WHERE canonical_key LIKE 'DEMO_INSTITUTION_ENTITY_%_EMPLOYER'
);

DELETE FROM ops.institution_entity_info
WHERE canonical_key LIKE 'DEMO_INSTITUTION_ENTITY_%_EMPLOYER';

-- -------------------------------------------------------------------------
-- Tier 9: Addresses (depend on institution and city_metadata; user_info FK
-- via created_by/modified_by RESTRICTs user_info delete, so addresses must
-- go first.  Match on: dec0-prefixed seed rows, demo-supplier institution,
-- and any address created by a demo user.)
-- -------------------------------------------------------------------------

CREATE TEMP TABLE _demo_address_ids ON COMMIT DROP AS
SELECT address_id FROM core.address_info
WHERE address_id::text LIKE 'dddddddd-dec0-%'
   OR institution_id::text LIKE 'dddddddd-dec0-%'
   OR created_by IN (
       SELECT user_id FROM core.user_info
       WHERE user_id::text LIKE 'dddddddd-dec0-%'
          OR username LIKE 'demo.cliente.pe.%@vianda.demo'
          OR username LIKE 'demo.cliente.ar.%@vianda.demo'
          OR username LIKE 'demo.cliente.us.%@vianda.demo'
   )
   OR modified_by IN (
       SELECT user_id FROM core.user_info
       WHERE user_id::text LIKE 'dddddddd-dec0-%'
          OR username LIKE 'demo.cliente.pe.%@vianda.demo'
          OR username LIKE 'demo.cliente.ar.%@vianda.demo'
          OR username LIKE 'demo.cliente.us.%@vianda.demo'
   );

-- Geolocation audit rows must be deleted before geolocation_info, which in
-- turn must be deleted before address_info (geolocation_info.address_id has
-- ON DELETE CASCADE, but geolocation_history.geolocation_id is RESTRICT —
-- so we must manually purge the audit trail first).
DELETE FROM audit.geolocation_history
WHERE geolocation_id IN (
    SELECT geolocation_id FROM core.geolocation_info
    WHERE address_id IN (SELECT address_id FROM _demo_address_ids)
);

DELETE FROM core.geolocation_info
WHERE address_id IN (SELECT address_id FROM _demo_address_ids);

DELETE FROM audit.address_history
WHERE address_id IN (SELECT address_id FROM _demo_address_ids);

DELETE FROM core.address_info
WHERE address_id IN (SELECT address_id FROM _demo_address_ids);

-- -------------------------------------------------------------------------
-- Tier 9b: Employer benefits program (depends on institution + users)
-- employer_benefits_program.institution_id → institution_info (RESTRICT)
-- Must be deleted before institution and before employer admin users.
-- -------------------------------------------------------------------------

DELETE FROM audit.employer_benefits_program_history
WHERE program_id IN (
    SELECT program_id FROM core.employer_benefits_program
    WHERE canonical_key LIKE 'DEMO_EMPLOYER_PROGRAM_%'
);

DELETE FROM core.employer_benefits_program
WHERE canonical_key LIKE 'DEMO_EMPLOYER_PROGRAM_%';

-- Purge employer institutions marked via canonical_key on institution_info
-- (institution with canonical_key 'DEMO_INSTITUTION_*_EMPLOYER')
-- Employer institution_entity_info already deleted in Tier 8b above.
-- Audit history for employer institutions
DELETE FROM audit.institution_history
WHERE institution_id IN (
    SELECT institution_id FROM core.institution_info
    WHERE canonical_key LIKE 'DEMO_INSTITUTION_%_EMPLOYER'
);

DELETE FROM core.institution_market
WHERE institution_id IN (
    SELECT institution_id FROM core.institution_info
    WHERE canonical_key LIKE 'DEMO_INSTITUTION_%_EMPLOYER'
);

-- -------------------------------------------------------------------------
-- Tier 10: Institution cleanup
-- Circular FK: institution_info.modified_by → user_info (RESTRICT, NOT NULL)
--              user_info.institution_id → institution_info (RESTRICT)
-- Resolution: re-point modified_by on demo institutions to the superadmin
-- user (which is never deleted), then delete users, then delete institutions.
-- -------------------------------------------------------------------------

-- Re-point modified_by to superadmin so demo-user deletion does not block
UPDATE core.institution_info
SET modified_by = (SELECT user_id FROM core.user_info WHERE username = 'superadmin' LIMIT 1)
WHERE (institution_id::text LIKE 'dddddddd-dec0-%'
   OR canonical_key LIKE 'DEMO_INSTITUTION_%_EMPLOYER')
  AND modified_by IN (SELECT user_id FROM core.user_info
                      WHERE user_id::text LIKE 'dddddddd-dec0-%'
                         OR username LIKE 'demo.empresa.%@vianda.demo');

-- institution_history (audit) also has modified_by → user_info (RESTRICT);
-- delete institution audit rows before demo users.
DELETE FROM audit.institution_history
WHERE institution_id::text LIKE 'dddddddd-dec0-%'
   OR institution_id IN (
       SELECT institution_id FROM core.institution_info
       WHERE canonical_key LIKE 'DEMO_INSTITUTION_%_EMPLOYER'
   );

-- -------------------------------------------------------------------------
-- Tier 11: Demo users
-- -------------------------------------------------------------------------

-- Capture all demo user_ids (dec0 prefix + customer + supplier username patterns for all markets)
CREATE TEMP TABLE _demo_user_ids ON COMMIT DROP AS
SELECT user_id FROM core.user_info
WHERE user_id::text LIKE 'dddddddd-dec0-%'
   OR username LIKE 'demo.cliente.pe.%@vianda.demo'
   OR username LIKE 'demo.cliente.ar.%@vianda.demo'
   OR username LIKE 'demo.cliente.us.%@vianda.demo'
   OR username LIKE 'demo.proveedor.%@vianda.demo'
       OR username LIKE 'demo.empresa.%@vianda.demo'
       OR username LIKE 'demo.empleado.%@vianda.demo';

-- User market assignments
DELETE FROM core.user_market_assignment
WHERE user_id IN (SELECT user_id FROM _demo_user_ids);

-- User messaging preferences and FCM tokens
DELETE FROM core.user_messaging_preferences
WHERE user_id IN (SELECT user_id FROM _demo_user_ids);

DELETE FROM core.user_fcm_token
WHERE user_id IN (SELECT user_id FROM _demo_user_ids);

DELETE FROM audit.user_history
WHERE user_id::text LIKE 'dddddddd-dec0-%'
   OR username LIKE 'demo.cliente.pe.%@vianda.demo'
   OR username LIKE 'demo.cliente.ar.%@vianda.demo'
   OR username LIKE 'demo.cliente.us.%@vianda.demo'
   OR username LIKE 'demo.proveedor.%@vianda.demo'
       OR username LIKE 'demo.empresa.%@vianda.demo'
       OR username LIKE 'demo.empleado.%@vianda.demo';

DELETE FROM core.user_info
WHERE user_id::text LIKE 'dddddddd-dec0-%'
   OR username LIKE 'demo.cliente.pe.%@vianda.demo'
   OR username LIKE 'demo.cliente.ar.%@vianda.demo'
   OR username LIKE 'demo.cliente.us.%@vianda.demo'
   OR username LIKE 'demo.proveedor.%@vianda.demo'
       OR username LIKE 'demo.empresa.%@vianda.demo'
       OR username LIKE 'demo.empleado.%@vianda.demo';

-- -------------------------------------------------------------------------
-- Tier 12: Institution markets and institution
-- (after users are gone, institution FK constraints are satisfied;
-- institution_history already deleted in Tier 10 above)
-- -------------------------------------------------------------------------

DELETE FROM core.institution_market
WHERE institution_id::text LIKE 'dddddddd-dec0-%';

-- Final audit-history sweep: triggers fired between Tier 9b/10 and here can
-- re-insert audit.institution_history rows (e.g. user delete cascading audit
-- writes). Re-run the delete just before institution_info DELETE so the
-- RESTRICT FK is satisfied.
DELETE FROM audit.institution_history
WHERE institution_id::text LIKE 'dddddddd-dec0-%'
   OR institution_id IN (
       SELECT institution_id FROM core.institution_info
       WHERE canonical_key LIKE 'DEMO_INSTITUTION_%_EMPLOYER'
   );

DELETE FROM core.institution_info
WHERE institution_id::text LIKE 'dddddddd-dec0-%'
   OR canonical_key LIKE 'DEMO_INSTITUTION_%_EMPLOYER';

-- -------------------------------------------------------------------------
-- Final notice
-- -------------------------------------------------------------------------

DO $$
BEGIN
    RAISE NOTICE 'Demo data purge complete. All dddddddd-dec0-* rows removed.';
END $$;

COMMIT;
PGSQL

echo ""
echo "Purge complete. The .demo_credentials.local file (if present) is now stale."
echo "You may delete it:  rm -f .demo_credentials.local"
echo ""
