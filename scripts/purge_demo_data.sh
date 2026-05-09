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

-- Plate reviews (linked to plate_pickup_live via plate_pickup_id)
DELETE FROM customer.plate_review_info
WHERE user_id IN (
    SELECT user_id FROM core.user_info
    WHERE user_id::text LIKE 'dddddddd-dec0-%'
       OR username LIKE 'demo.cliente.pe.%@vianda.demo'
       OR username LIKE 'demo.cliente.ar.%@vianda.demo'
       OR username LIKE 'demo.cliente.us.%@vianda.demo'
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
    )
);

-- Subscriptions
DELETE FROM customer.subscription_info
WHERE user_id IN (
    SELECT user_id FROM core.user_info
    WHERE username LIKE 'demo.cliente.pe.%@vianda.demo'
       OR username LIKE 'demo.cliente.ar.%@vianda.demo'
       OR username LIKE 'demo.cliente.us.%@vianda.demo'
);
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

DELETE FROM audit.address_history
WHERE address_id IN (SELECT address_id FROM _demo_address_ids);

DELETE FROM core.address_info
WHERE address_id IN (SELECT address_id FROM _demo_address_ids);

-- -------------------------------------------------------------------------
-- Tier 10: Demo users (depend on institution)
-- -------------------------------------------------------------------------

-- Capture all demo user_ids (dec0 prefix + customer username pattern for all markets)
CREATE TEMP TABLE _demo_user_ids ON COMMIT DROP AS
SELECT user_id FROM core.user_info
WHERE user_id::text LIKE 'dddddddd-dec0-%'
   OR username LIKE 'demo.cliente.pe.%@vianda.demo'
   OR username LIKE 'demo.cliente.ar.%@vianda.demo'
   OR username LIKE 'demo.cliente.us.%@vianda.demo';

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
   OR username LIKE 'demo.cliente.us.%@vianda.demo';

DELETE FROM core.user_info
WHERE user_id::text LIKE 'dddddddd-dec0-%'
   OR username LIKE 'demo.cliente.pe.%@vianda.demo'
   OR username LIKE 'demo.cliente.ar.%@vianda.demo'
   OR username LIKE 'demo.cliente.us.%@vianda.demo';

-- -------------------------------------------------------------------------
-- Tier 11: Institution markets and institution
-- -------------------------------------------------------------------------

DELETE FROM core.institution_market
WHERE institution_id::text LIKE 'dddddddd-dec0-%';

DELETE FROM audit.institution_history
WHERE institution_id::text LIKE 'dddddddd-dec0-%';

DELETE FROM core.institution_info
WHERE institution_id::text LIKE 'dddddddd-dec0-%';

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
