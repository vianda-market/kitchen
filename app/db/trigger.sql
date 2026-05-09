-- role_info trigger removed - role_info table deprecated, roles stored directly on core.user_info as enums

-- Trigger function for core.institution_info history logging
CREATE OR REPLACE FUNCTION institution_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.institution_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE institution_id = OLD.institution_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.institution_history (
        event_id,
        institution_id,
        name,
        institution_type,
        -- market_id REMOVED — institution markets now in core.institution_market junction
        support_email_suppressed_until,
        last_support_email_date,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.institution_id,
        NEW.name,
        NEW.institution_type,
        NEW.support_email_suppressed_until,
        NEW.last_support_email_date,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS institution_trigger ON core.institution_info;
CREATE TRIGGER institution_trigger
AFTER INSERT OR UPDATE ON core.institution_info
FOR EACH ROW
EXECUTE FUNCTION institution_trigger_func();

-- Trigger function for core.user_info history logging
CREATE OR REPLACE FUNCTION user_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this user as not current
        UPDATE audit.user_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE user_id = OLD.user_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.user_history (
        event_id,
        user_id,
        institution_id,
        role_type,
        role_name,
        username,
        email,
        hashed_password,
        first_name,
        last_name,
        mobile_number,
        mobile_number_verified,
        mobile_number_verified_at,
        email_verified,
        email_verified_at,
        support_email_suppressed_until,
        last_support_email_date,
        market_id,
        city_metadata_id,
        locale,
        referral_code,
        referred_by_code,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.user_id,
        NEW.institution_id,
        NEW.role_type,
        NEW.role_name,
        NEW.username,
        NEW.email,
        NEW.hashed_password,
        NEW.first_name,
        NEW.last_name,
        NEW.mobile_number,
        NEW.mobile_number_verified,
        NEW.mobile_number_verified_at,
        NEW.email_verified,
        NEW.email_verified_at,
        NEW.support_email_suppressed_until,
        NEW.last_support_email_date,
        NEW.market_id,
        NEW.city_metadata_id,
        NEW.locale,
        NEW.referral_code,
        NEW.referred_by_code,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger on core.user_info
DROP TRIGGER IF EXISTS user_history_trigger ON core.user_info;
CREATE TRIGGER user_history_trigger
AFTER INSERT OR UPDATE ON core.user_info
FOR EACH ROW
EXECUTE FUNCTION user_history_trigger_func();

-- Trigger: create default core.user_messaging_preferences on user insert
CREATE OR REPLACE FUNCTION user_messaging_preferences_insert_func()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO core.user_messaging_preferences (user_id)
    VALUES (NEW.user_id)
    ON CONFLICT (user_id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS user_messaging_preferences_trigger ON core.user_info;
CREATE TRIGGER user_messaging_preferences_trigger
AFTER INSERT ON core.user_info
FOR EACH ROW
EXECUTE FUNCTION user_messaging_preferences_insert_func();

-- Trigger function for ops.institution_entity_info history logging
CREATE OR REPLACE FUNCTION institution_entity_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this supplier entity as not current
        UPDATE audit.institution_entity_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE institution_entity_id = OLD.institution_entity_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.institution_entity_history (
        event_id,
        institution_entity_id,
        institution_id,
        address_id,
        currency_metadata_id,
        tax_id,
        name,
        payout_provider_account_id,
        payout_aggregator,
        payout_onboarding_status,
        email_domain,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.institution_entity_id,
        NEW.institution_id,
        NEW.address_id,
        NEW.currency_metadata_id,
        NEW.tax_id,
        NEW.name,
        NEW.payout_provider_account_id,
        NEW.payout_aggregator,
        NEW.payout_onboarding_status,
        NEW.email_domain,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger on ops.institution_entity_info
DROP TRIGGER IF EXISTS institution_entity_history_trigger ON ops.institution_entity_info;
CREATE TRIGGER institution_entity_history_trigger
AFTER INSERT OR UPDATE ON ops.institution_entity_info
FOR EACH ROW
EXECUTE FUNCTION institution_entity_history_trigger_func();

-- Trigger function for core.address_info history logging
CREATE OR REPLACE FUNCTION address_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this supplier entity as not current
        UPDATE audit.address_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE address_id = OLD.address_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.address_history (
        event_id,
        address_id,
        institution_id,
        user_id,
        address_type,
        country_code,
        province,
        city,
        city_metadata_id,
        postal_code,
        street_type,
        street_name,
        building_number,
        timezone,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.address_id,
        NEW.institution_id,
        NEW.user_id,
        NEW.address_type,
        NEW.country_code,
        NEW.province,
        NEW.city,
        NEW.city_metadata_id,
        NEW.postal_code,
        NEW.street_type,
        NEW.street_name,
        NEW.building_number,
        NEW.timezone,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger on core.address_info
DROP TRIGGER IF EXISTS address_history_trigger ON core.address_info;
CREATE TRIGGER address_history_trigger
AFTER INSERT OR UPDATE ON core.address_info
FOR EACH ROW
EXECUTE FUNCTION address_history_trigger_func();

-- Trigger function for core.geolocation_info history logging
CREATE OR REPLACE FUNCTION geolocation_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this supplier entity as not current
        UPDATE audit.geolocation_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE geolocation_id = OLD.geolocation_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.geolocation_history (
        event_id,
        geolocation_id,
        address_id,
        latitude,
        longitude,
        place_id,
        viewport,
        formatted_address_google,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.geolocation_id,
        NEW.address_id,
        NEW.latitude,
        NEW.longitude,
        NEW.place_id,
        NEW.viewport,
        NEW.formatted_address_google,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger on core.geolocation_info
DROP TRIGGER IF EXISTS geolocation_history_trigger ON core.geolocation_info;
CREATE TRIGGER geolocation_history_trigger
AFTER INSERT OR UPDATE ON core.geolocation_info
FOR EACH ROW
EXECUTE FUNCTION geolocation_history_trigger_func();

-- Trigger function for ops.cuisine history logging
CREATE OR REPLACE FUNCTION cuisine_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.cuisine_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE cuisine_id = OLD.cuisine_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.cuisine_history (
        event_id,
        cuisine_id,
        cuisine_name,
        cuisine_name_i18n,
        slug,
        parent_cuisine_id,
        description,
        origin_source,
        display_order,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.cuisine_id,
        NEW.cuisine_name,
        NEW.cuisine_name_i18n,
        NEW.slug,
        NEW.parent_cuisine_id,
        NEW.description,
        NEW.origin_source,
        NEW.display_order,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS cuisine_history_trigger ON ops.cuisine;
CREATE TRIGGER cuisine_history_trigger
AFTER INSERT OR UPDATE ON ops.cuisine
FOR EACH ROW
EXECUTE FUNCTION cuisine_history_trigger_func();

-- Trigger function for ops.restaurant_info history logging
CREATE OR REPLACE FUNCTION restaurant_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.restaurant_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE restaurant_id = OLD.restaurant_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.restaurant_history (
        event_id,
        restaurant_id,
        institution_id,
        institution_entity_id,
        address_id,
        name,
        cuisine_id,
        pickup_instructions,
        tagline,
        tagline_i18n,
        is_featured,
        cover_image_url,
        average_rating,
        review_count,
        verified_badge,
        spotlight_label,
        spotlight_label_i18n,
        member_perks,
        member_perks_i18n,
        require_kiosk_code_verification,
        kitchen_open_time,
        kitchen_close_time,
        location,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.restaurant_id,
        NEW.institution_id,
        NEW.institution_entity_id,
        NEW.address_id,
        NEW.name,
        NEW.cuisine_id,
        NEW.pickup_instructions,
        NEW.tagline,
        NEW.tagline_i18n,
        NEW.is_featured,
        NEW.cover_image_url,
        NEW.average_rating,
        NEW.review_count,
        NEW.verified_badge,
        NEW.spotlight_label,
        NEW.spotlight_label_i18n,
        NEW.member_perks,
        NEW.member_perks_i18n,
        NEW.require_kiosk_code_verification,
        NEW.kitchen_open_time,
        NEW.kitchen_close_time,
        NEW.location,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS restaurant_history_trigger ON ops.restaurant_info;
CREATE TRIGGER restaurant_history_trigger
AFTER INSERT OR UPDATE ON ops.restaurant_info
FOR EACH ROW
EXECUTE FUNCTION restaurant_history_trigger_func();

-- Trigger function for ops.product_info history logging
CREATE OR REPLACE FUNCTION product_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this product as not current
        UPDATE audit.product_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE product_id = OLD.product_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.product_history (
        event_id,
        product_id,
        institution_id,
        name,
        name_i18n,
        ingredients,
        ingredients_i18n,
        description,
        description_i18n,
        dietary,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.product_id,
        NEW.institution_id,
        NEW.name,
        NEW.name_i18n,
        NEW.ingredients,
        NEW.ingredients_i18n,
        NEW.description,
        NEW.description_i18n,
        NEW.dietary,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger on ops.product_info
DROP TRIGGER IF EXISTS product_history_trigger ON ops.product_info;
CREATE TRIGGER product_history_trigger
AFTER INSERT OR UPDATE ON ops.product_info
FOR EACH ROW
EXECUTE FUNCTION product_history_trigger_func();

-- Trigger function for ops.image_asset history logging
CREATE OR REPLACE FUNCTION image_asset_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.image_asset_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE image_asset_id = OLD.image_asset_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.image_asset_history (
        event_id,
        image_asset_id,
        product_id,
        institution_id,
        original_storage_path,
        original_checksum,
        pipeline_status,
        moderation_status,
        moderation_signals,
        processing_version,
        failure_count,
        created_date,
        modified_date,
        modified_by,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.image_asset_id,
        NEW.product_id,
        NEW.institution_id,
        NEW.original_storage_path,
        NEW.original_checksum,
        NEW.pipeline_status,
        NEW.moderation_status,
        NEW.moderation_signals,
        NEW.processing_version,
        NEW.failure_count,
        NEW.created_date,
        NEW.modified_date,
        NEW.modified_by,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS image_asset_history_trigger ON ops.image_asset;
CREATE TRIGGER image_asset_history_trigger
AFTER INSERT OR UPDATE ON ops.image_asset
FOR EACH ROW
EXECUTE FUNCTION image_asset_history_trigger_func();

-- Before insert/update on ops.plate_info: set expected_payout_local_currency = credit * credit_value_supplier_local
CREATE OR REPLACE FUNCTION plate_info_set_expected_payout_local_currency_func()
RETURNS TRIGGER AS $$
DECLARE
    cv NUMERIC;
BEGIN
    SELECT cm.credit_value_supplier_local INTO cv
    FROM ops.restaurant_info r
    JOIN ops.institution_entity_info ie ON r.institution_entity_id = ie.institution_entity_id
    JOIN core.currency_metadata cm ON ie.currency_metadata_id = cm.currency_metadata_id
    WHERE r.restaurant_id = NEW.restaurant_id;
    NEW.expected_payout_local_currency := COALESCE(NEW.credit * NULLIF(cv, 0), 0);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS plate_info_set_expected_payout_local_currency_trigger ON ops.plate_info;
CREATE TRIGGER plate_info_set_expected_payout_local_currency_trigger
BEFORE INSERT OR UPDATE ON ops.plate_info
FOR EACH ROW
EXECUTE FUNCTION plate_info_set_expected_payout_local_currency_func();

-- Trigger function for ops.plate_info history logging
CREATE OR REPLACE FUNCTION plate_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this plate as not current
        UPDATE audit.plate_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE plate_id = OLD.plate_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.plate_history (
        event_id,
        plate_id,
        product_id,
        restaurant_id,
        price,
        credit,
        expected_payout_local_currency,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.plate_id,
        NEW.product_id,
        NEW.restaurant_id,
        NEW.price,
        NEW.credit,
        NEW.expected_payout_local_currency,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger on ops.plate_info
DROP TRIGGER IF EXISTS plate_history_trigger ON ops.plate_info;
CREATE TRIGGER plate_history_trigger
AFTER INSERT OR UPDATE ON ops.plate_info
FOR EACH ROW
EXECUTE FUNCTION plate_history_trigger_func();

-- Trigger function for billing.client_transaction from plate_selection event
CREATE OR REPLACE FUNCTION log_plate_selection_txn()
  RETURNS TRIGGER
  SECURITY DEFINER               -- run with the trigger owner’s privileges
AS $$
BEGIN
  INSERT INTO billing.client_transaction (
    user_id,
    source,
    plate_selection_id,
    credit,
    is_archived,
    status,
    created_date,
    modified_by
  )
  VALUES (
    NEW.user_id,
    'plate_selection',
    NEW.plate_selection_id,
    -NEW.credit,
    FALSE,                       -- mirror the default
    'active',                    -- mirror the default
    now(),                       -- explicit timestamp
    NEW.modified_by
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_plate_selection_ct ON customer.plate_selection_info;

CREATE TRIGGER trg_plate_selection_ct
  AFTER INSERT ON customer.plate_selection_info
  FOR EACH ROW
  WHEN (NEW.status = 'active')  -- guard clause
  EXECUTE FUNCTION log_plate_selection_txn();

-- Trigger function for customer.plate_selection_info history logging
CREATE OR REPLACE FUNCTION plate_selection_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.plate_selection_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE plate_selection_id = OLD.plate_selection_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.plate_selection_history (
        event_id,
        plate_selection_id,
        user_id,
        plate_id,
        restaurant_id,
        product_id,
        qr_code_id,
        credit,
        kitchen_day,
        pickup_date,
        pickup_time_range,
        pickup_intent,
        flexible_on_time,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.plate_selection_id,
        NEW.user_id,
        NEW.plate_id,
        NEW.restaurant_id,
        NEW.product_id,
        NEW.qr_code_id,
        NEW.credit,
        NEW.kitchen_day,
        NEW.pickup_date,
        NEW.pickup_time_range,
        NEW.pickup_intent,
        NEW.flexible_on_time,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS plate_selection_history_trigger ON customer.plate_selection_info;
CREATE TRIGGER plate_selection_history_trigger
AFTER INSERT OR UPDATE ON customer.plate_selection_info
FOR EACH ROW
EXECUTE FUNCTION plate_selection_history_trigger_func();

-- Before insert/update on customer.plan_info: set credit_cost_local_currency and credit_cost_usd
CREATE OR REPLACE FUNCTION plan_info_set_credit_cost_func()
RETURNS TRIGGER AS $$
DECLARE
    conv_usd NUMERIC;
BEGIN
    NEW.credit_cost_local_currency := COALESCE(NEW.price / NULLIF(NEW.credit, 0), 0);
    SELECT cm.currency_conversion_usd INTO conv_usd
    FROM core.market_info m
    JOIN core.currency_metadata cm ON m.currency_metadata_id = cm.currency_metadata_id
    WHERE m.market_id = NEW.market_id;
    NEW.credit_cost_usd := COALESCE(NEW.credit_cost_local_currency / NULLIF(conv_usd, 0), 0);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS plan_info_set_credit_worth_trigger ON customer.plan_info;
DROP TRIGGER IF EXISTS plan_info_set_credit_cost_trigger ON customer.plan_info;
CREATE TRIGGER plan_info_set_credit_cost_trigger
BEFORE INSERT OR UPDATE ON customer.plan_info
FOR EACH ROW
EXECUTE FUNCTION plan_info_set_credit_cost_func();

-- Trigger function for customer.plan_info history logging
CREATE OR REPLACE FUNCTION plan_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this plan as not current
        UPDATE audit.plan_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE plan_id = OLD.plan_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.plan_history (
        event_id,
        plan_id,
        market_id,
        name,
        name_i18n,
        marketing_description,
        marketing_description_i18n,
        features,
        features_i18n,
        cta_label,
        cta_label_i18n,
        credit,
        price,
        highlighted,
        credit_cost_local_currency,
        credit_cost_usd,
        rollover,
        rollover_cap,
        canonical_key,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.plan_id,
        NEW.market_id,
        NEW.name,
        NEW.name_i18n,
        NEW.marketing_description,
        NEW.marketing_description_i18n,
        NEW.features,
        NEW.features_i18n,
        NEW.cta_label,
        NEW.cta_label_i18n,
        NEW.credit,
        NEW.price,
        NEW.highlighted,
        NEW.credit_cost_local_currency,
        NEW.credit_cost_usd,
        NEW.rollover,
        NEW.rollover_cap,
        NEW.canonical_key,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger on customer.plan_info
DROP TRIGGER IF EXISTS plan_history_trigger ON customer.plan_info;
CREATE TRIGGER plan_history_trigger
AFTER INSERT OR UPDATE ON customer.plan_info
FOR EACH ROW
EXECUTE FUNCTION plan_history_trigger_func();

-- Trigger function for customer.subscription_info history logging
CREATE OR REPLACE FUNCTION subscription_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this subscription as not current
        UPDATE audit.subscription_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE user_id = OLD.user_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.subscription_history (
        event_id,
        subscription_id,
        user_id,
        market_id,
        plan_id,
        renewal_date,
        balance,
        subscription_status,
        hold_start_date,
        hold_end_date,
        early_renewal_threshold,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.subscription_id,
        NEW.user_id,
        NEW.market_id,
        NEW.plan_id,
        NEW.renewal_date,
        NEW.balance,
        NEW.subscription_status,
        NEW.hold_start_date,
        NEW.hold_end_date,
        NEW.early_renewal_threshold,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger on customer.subscription_info
DROP TRIGGER IF EXISTS subscription_history_trigger ON customer.subscription_info;
CREATE TRIGGER subscription_history_trigger
AFTER INSERT OR UPDATE ON customer.subscription_info
FOR EACH ROW
EXECUTE FUNCTION subscription_history_trigger_func();

-- Trigger function for subscription status activation (Pending -> Active when balance becomes positive)
CREATE OR REPLACE FUNCTION subscription_status_activation_trigger()
RETURNS TRIGGER AS $$
BEGIN
    -- Only activate if transitioning from Pending to positive balance
    -- Condition: status is 'Pending' AND balance transitions from <= 0 to > 0
    IF OLD.status = 'pending' AND NEW.balance > 0 AND OLD.balance <= 0 THEN
        NEW.status := 'active';
        -- Log the status change (visible in PostgreSQL logs)
        RAISE NOTICE 'Subscription % status automatically changed from pending to active (balance: % -> %)',
            NEW.subscription_id, OLD.balance, NEW.balance;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger on customer.subscription_info for automatic status activation
DROP TRIGGER IF EXISTS subscription_status_activation ON customer.subscription_info;
CREATE TRIGGER subscription_status_activation
BEFORE UPDATE ON customer.subscription_info
FOR EACH ROW
WHEN (OLD.status = 'pending' AND NEW.balance > 0 AND OLD.balance <= 0)
EXECUTE FUNCTION subscription_status_activation_trigger();

-- Trigger function for billing.client_bill_info history logging
CREATE OR REPLACE FUNCTION client_bill_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this client_bill as not current
        UPDATE audit.client_bill_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE client_bill_id = OLD.client_bill_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.client_bill_history (
        event_id,
        client_bill_id,
        subscription_payment_id,
        subscription_id,
        user_id,
        plan_id,
        currency_metadata_id,
        amount,
        currency_code,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.client_bill_id,
        NEW.subscription_payment_id,
        NEW.subscription_id,
        NEW.user_id,
        NEW.plan_id,
        NEW.currency_metadata_id,
        NEW.amount,
        NEW.currency_code,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger on billing.client_bill_info
DROP TRIGGER IF EXISTS client_bill_history_trigger ON billing.client_bill_info;
CREATE TRIGGER client_bill_history_trigger
AFTER INSERT OR UPDATE ON billing.client_bill_info
FOR EACH ROW
EXECUTE FUNCTION client_bill_history_trigger_func();


-- Trigger function for billing.restaurant_balance_info history logging
CREATE OR REPLACE FUNCTION restaurant_balance_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this restaurant_balance as not current
        UPDATE audit.restaurant_balance_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE restaurant_id = OLD.restaurant_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.restaurant_balance_history (
        event_id,
        restaurant_id,
        currency_metadata_id,
        transaction_count,
        balance,
        currency_code,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.restaurant_id,
        NEW.currency_metadata_id,
        NEW.transaction_count,
        NEW.balance,
        NEW.currency_code,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger on billing.restaurant_balance_info
DROP TRIGGER IF EXISTS restaurant_balance_history_trigger ON billing.restaurant_balance_info;
CREATE TRIGGER restaurant_balance_history_trigger
AFTER INSERT OR UPDATE ON billing.restaurant_balance_info
FOR EACH ROW
EXECUTE FUNCTION restaurant_balance_history_trigger_func();

-- Trigger function for billing.institution_bill_info history logging
CREATE OR REPLACE FUNCTION institution_bill_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this institution_bill as not current
        UPDATE audit.institution_bill_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE institution_bill_id = OLD.institution_bill_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.institution_bill_history (
        event_id,
        institution_bill_id,
        institution_id,
        institution_entity_id,
        currency_metadata_id,
        transaction_count,
        amount,
        currency_code,
        period_start,
        period_end,
        is_archived,
        status,
        resolution,
        tax_doc_external_id,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.institution_bill_id,
        NEW.institution_id,
        NEW.institution_entity_id,
        NEW.currency_metadata_id,
        NEW.transaction_count,
        NEW.amount,
        NEW.currency_code,
        NEW.period_start,
        NEW.period_end,
        NEW.is_archived,
        NEW.status,
        NEW.resolution,
        NEW.tax_doc_external_id,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger on billing.institution_bill_info
DROP TRIGGER IF EXISTS institution_bill_history_trigger ON billing.institution_bill_info;
CREATE TRIGGER institution_bill_history_trigger
AFTER INSERT OR UPDATE ON billing.institution_bill_info
FOR EACH ROW
EXECUTE FUNCTION institution_bill_history_trigger_func();

-- Trigger function for billing.institution_settlement history logging
CREATE OR REPLACE FUNCTION institution_settlement_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.institution_settlement_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE settlement_id = OLD.settlement_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.institution_settlement_history (
        event_id,
        settlement_id,
        institution_entity_id,
        restaurant_id,
        period_start,
        period_end,
        kitchen_day,
        amount,
        currency_code,
        currency_metadata_id,
        transaction_count,
        balance_event_id,
        settlement_number,
        settlement_run_id,
        institution_bill_id,
        country_code,
        status,
        is_archived,
        created_at,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.settlement_id,
        NEW.institution_entity_id,
        NEW.restaurant_id,
        NEW.period_start,
        NEW.period_end,
        NEW.kitchen_day,
        NEW.amount,
        NEW.currency_code,
        NEW.currency_metadata_id,
        NEW.transaction_count,
        NEW.balance_event_id,
        NEW.settlement_number,
        NEW.settlement_run_id,
        NEW.institution_bill_id,
        NEW.country_code,
        NEW.status,
        NEW.is_archived,
        NEW.created_at,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS institution_settlement_history_trigger ON billing.institution_settlement;
CREATE TRIGGER institution_settlement_history_trigger
AFTER INSERT OR UPDATE ON billing.institution_settlement
FOR EACH ROW
EXECUTE FUNCTION institution_settlement_history_trigger_func();

-- Trigger function for billing.supplier_invoice history logging
CREATE OR REPLACE FUNCTION supplier_invoice_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.supplier_invoice_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE supplier_invoice_id = OLD.supplier_invoice_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.supplier_invoice_history (
        event_id,
        supplier_invoice_id,
        institution_entity_id,
        country_code,
        invoice_type,
        external_invoice_number,
        issued_date,
        amount,
        currency_code,
        tax_amount,
        tax_rate,
        document_storage_path,
        document_format,
        status,
        rejection_reason,
        reviewed_by,
        reviewed_at,
        is_archived,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.supplier_invoice_id,
        NEW.institution_entity_id,
        NEW.country_code,
        NEW.invoice_type,
        NEW.external_invoice_number,
        NEW.issued_date,
        NEW.amount,
        NEW.currency_code,
        NEW.tax_amount,
        NEW.tax_rate,
        NEW.document_storage_path,
        NEW.document_format,
        NEW.status,
        NEW.rejection_reason,
        NEW.reviewed_by,
        NEW.reviewed_at,
        NEW.is_archived,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS supplier_invoice_history_trigger ON billing.supplier_invoice;
CREATE TRIGGER supplier_invoice_history_trigger
AFTER INSERT OR UPDATE ON billing.supplier_invoice
FOR EACH ROW
EXECUTE FUNCTION supplier_invoice_history_trigger_func();

-- credit_currency_history_trigger and credit_currency_refresh_plate_payouts_trigger retired
-- along with core.credit_currency_info. Currency is now a two-tier split
-- (external.iso4217_currency raw + core.currency_metadata policy); metadata history
-- is logged by currency_metadata_history_trigger_func further below.
-- Plate-payout refresh on currency-rate change is a backlog service-layer concern.

-- Trigger function for core.market_info history logging
CREATE OR REPLACE FUNCTION market_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this market as not current
        UPDATE audit.market_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE market_id = OLD.market_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.market_history (
        event_id,
        market_id,
        country_code,
        currency_metadata_id,
        language,
        phone_dial_code,
        phone_local_digits,
        min_credit_spread_pct,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.market_id,
        NEW.country_code,
        NEW.currency_metadata_id,
        NEW.language,
        NEW.phone_dial_code,
        NEW.phone_local_digits,
        NEW.min_credit_spread_pct,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger on core.market_info
DROP TRIGGER IF EXISTS market_history_trigger ON core.market_info;
CREATE TRIGGER market_history_trigger
AFTER INSERT OR UPDATE ON core.market_info
FOR EACH ROW
EXECUTE FUNCTION market_history_trigger_func();

-- Trigger function for ops.restaurant_holidays history logging
CREATE OR REPLACE FUNCTION restaurant_holidays_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    v_operation audit_operation_enum;
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_operation := 'create'::audit_operation_enum;
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.is_archived = FALSE AND NEW.is_archived = TRUE THEN
            v_operation := 'archive'::audit_operation_enum;
        ELSE
            v_operation := 'update'::audit_operation_enum;
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        v_operation := 'delete'::audit_operation_enum;
    END IF;

    -- Mark previous records as not current
    IF TG_OP = 'UPDATE' THEN
        UPDATE audit.restaurant_holidays_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE holiday_id = OLD.holiday_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.restaurant_holidays_history (
        event_id,
        holiday_id,
        restaurant_id,
        country_code,
        holiday_date,
        holiday_name,
        is_recurring,
        recurring_month,
        recurring_day,
        status,
        is_archived,
        created_date,
        created_by,
        modified_by,
        modified_date,
        source,
        operation,
        is_current,
        valid_until
    ) VALUES (
        uuidv7(),
        COALESCE(NEW.holiday_id, OLD.holiday_id),
        COALESCE(NEW.restaurant_id, OLD.restaurant_id),
        COALESCE(NEW.country_code, OLD.country_code),
        COALESCE(NEW.holiday_date, OLD.holiday_date),
        COALESCE(NEW.holiday_name, OLD.holiday_name),
        COALESCE(NEW.is_recurring, OLD.is_recurring),
        COALESCE(NEW.recurring_month, OLD.recurring_month),
        COALESCE(NEW.recurring_day, OLD.recurring_day),
        COALESCE(NEW.status, OLD.status),
        COALESCE(NEW.is_archived, OLD.is_archived),
        COALESCE(NEW.created_date, OLD.created_date),
        COALESCE(NEW.created_by, OLD.created_by),
        COALESCE(NEW.modified_by, OLD.modified_by),
        COALESCE(NEW.modified_date, OLD.modified_date),
        COALESCE(NEW.source, OLD.source),
        v_operation,
        TRUE,
        'infinity'
    );
    
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS restaurant_holidays_history_trigger ON ops.restaurant_holidays;
CREATE TRIGGER restaurant_holidays_history_trigger
AFTER INSERT OR UPDATE OR DELETE ON ops.restaurant_holidays
FOR EACH ROW
EXECUTE FUNCTION restaurant_holidays_history_trigger_func();

-- Trigger function for ops.plate_kitchen_days history logging
CREATE OR REPLACE FUNCTION plate_kitchen_days_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    v_operation audit_operation_enum;
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_operation := 'create'::audit_operation_enum;
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.is_archived = FALSE AND NEW.is_archived = TRUE THEN
            v_operation := 'archive'::audit_operation_enum;
        ELSE
            v_operation := 'update'::audit_operation_enum;
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        v_operation := 'delete'::audit_operation_enum;
    END IF;

    -- Mark previous records as not current
    IF TG_OP = 'UPDATE' THEN
        UPDATE audit.plate_kitchen_days_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE plate_kitchen_day_id = OLD.plate_kitchen_day_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.plate_kitchen_days_history (
        event_id,
        plate_kitchen_day_id,
        plate_id,
        kitchen_day,
        status,
        is_archived,
        created_date,
        created_by,
        modified_by,
        modified_date,
        operation,
        is_current,
        valid_until
    ) VALUES (
        uuidv7(),
        COALESCE(NEW.plate_kitchen_day_id, OLD.plate_kitchen_day_id),
        COALESCE(NEW.plate_id, OLD.plate_id),
        COALESCE(NEW.kitchen_day, OLD.kitchen_day),
        COALESCE(NEW.status, OLD.status),
        COALESCE(NEW.is_archived, OLD.is_archived),
        COALESCE(NEW.created_date, OLD.created_date),
        COALESCE(NEW.created_by, OLD.created_by),
        COALESCE(NEW.modified_by, OLD.modified_by),
        COALESCE(NEW.modified_date, OLD.modified_date),
        v_operation,
        TRUE,
        'infinity'
    );
    
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
    RETURN NEW;
END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS plate_kitchen_days_history_trigger ON ops.plate_kitchen_days;
CREATE TRIGGER plate_kitchen_days_history_trigger
AFTER INSERT OR UPDATE OR DELETE ON ops.plate_kitchen_days
FOR EACH ROW
EXECUTE FUNCTION plate_kitchen_days_history_trigger_func();

-- Auto-deactivate restaurant when all its ops.plate_kitchen_days become inactive (archived or deleted)
CREATE OR REPLACE FUNCTION restaurant_auto_deactivate_when_no_plate_kitchen_days()
RETURNS TRIGGER AS $$
DECLARE
    v_restaurant_id UUID;
    v_active_count BIGINT;
BEGIN
    -- Only care when we are removing an active row (UPDATE is_archived to TRUE, or status to Inactive, or DELETE of an active row)
    IF TG_OP = 'UPDATE' AND (
        (OLD.is_archived = FALSE AND NEW.is_archived = TRUE) OR
        (OLD.status = 'active'::status_enum AND NEW.status != 'active'::status_enum)
    ) THEN
        NULL; -- fall through to get restaurant and check
    ELSIF TG_OP = 'DELETE' AND OLD.is_archived = FALSE AND OLD.status = 'active'::status_enum THEN
        NULL; -- fall through
    ELSE
        RETURN COALESCE(NEW, OLD);
    END IF;

    SELECT p.restaurant_id INTO v_restaurant_id
    FROM ops.plate_info p
    WHERE p.plate_id = COALESCE(OLD.plate_id, NEW.plate_id);

    IF v_restaurant_id IS NULL THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    SELECT COUNT(*) INTO v_active_count
    FROM ops.plate_info p
    INNER JOIN ops.plate_kitchen_days pkd ON pkd.plate_id = p.plate_id AND pkd.is_archived = FALSE AND pkd.status = 'active'::status_enum
    WHERE p.restaurant_id = v_restaurant_id AND p.is_archived = FALSE;

    IF v_active_count = 0 THEN
        UPDATE ops.restaurant_info
        SET status = 'inactive'::status_enum,
            modified_date = CURRENT_TIMESTAMP
        WHERE restaurant_id = v_restaurant_id AND status = 'active'::status_enum;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS restaurant_auto_deactivate_on_plate_kitchen_days ON ops.plate_kitchen_days;
CREATE TRIGGER restaurant_auto_deactivate_on_plate_kitchen_days
AFTER UPDATE OR DELETE ON ops.plate_kitchen_days
FOR EACH ROW
EXECUTE FUNCTION restaurant_auto_deactivate_when_no_plate_kitchen_days();

-- Auto-deactivate restaurant when all its active QR codes are removed (archived, deleted, or set to Inactive)
CREATE OR REPLACE FUNCTION restaurant_auto_deactivate_when_no_active_qr_code()
RETURNS TRIGGER AS $$
DECLARE
    v_restaurant_id UUID;
    v_active_count BIGINT;
BEGIN
    -- Only care when we are removing an active QR code (UPDATE is_archived to TRUE, or status to Inactive, or DELETE of an active row)
    IF TG_OP = 'UPDATE' AND (
        (OLD.is_archived = FALSE AND NEW.is_archived = TRUE) OR
        (OLD.status = 'active'::status_enum AND NEW.status != 'active'::status_enum)
    ) THEN
        NULL; -- fall through
    ELSIF TG_OP = 'DELETE' AND OLD.is_archived = FALSE AND OLD.status = 'active'::status_enum THEN
        NULL; -- fall through
    ELSE
        RETURN COALESCE(NEW, OLD);
    END IF;

    v_restaurant_id := COALESCE(OLD.restaurant_id, NEW.restaurant_id);

    IF v_restaurant_id IS NULL THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    SELECT COUNT(*) INTO v_active_count
    FROM ops.qr_code
    WHERE restaurant_id = v_restaurant_id
      AND is_archived = FALSE
      AND status = 'active'::status_enum;

    IF v_active_count = 0 THEN
        UPDATE ops.restaurant_info
        SET status = 'inactive'::status_enum,
            modified_date = CURRENT_TIMESTAMP
        WHERE restaurant_id = v_restaurant_id AND status = 'active'::status_enum;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS restaurant_auto_deactivate_on_qr_code ON ops.qr_code;
CREATE TRIGGER restaurant_auto_deactivate_on_qr_code
AFTER UPDATE OR DELETE ON ops.qr_code
FOR EACH ROW
EXECUTE FUNCTION restaurant_auto_deactivate_when_no_active_qr_code();

-- status_info trigger removed - status_info table deprecated, status stored directly on entities as enum
-- transaction_type_info trigger removed - transaction_type_info table deprecated, transaction_type stored directly on transaction tables as enum

-- National holidays history trigger
CREATE OR REPLACE FUNCTION national_holidays_history_trigger()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit.national_holidays_history (
            holiday_id, country_code, holiday_name, holiday_date, is_recurring,
            recurring_month, recurring_day, status, is_archived, created_date, created_by, modified_by, modified_date,
            source
        ) VALUES (
            NEW.holiday_id, NEW.country_code, NEW.holiday_name, NEW.holiday_date, NEW.is_recurring,
            NEW.recurring_month, NEW.recurring_day, NEW.status, NEW.is_archived, NEW.created_date, NEW.created_by, NEW.modified_by, NEW.modified_date,
            NEW.source
        );
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit.national_holidays_history (
            holiday_id, country_code, holiday_name, holiday_date, is_recurring,
            recurring_month, recurring_day, status, is_archived, created_date, created_by, modified_by, modified_date,
            source
        ) VALUES (
            NEW.holiday_id, NEW.country_code, NEW.holiday_name, NEW.holiday_date, NEW.is_recurring,
            NEW.recurring_month, NEW.recurring_day, NEW.status, NEW.is_archived, NEW.created_date, NEW.created_by, NEW.modified_by, NEW.modified_date,
            NEW.source
        );
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit.national_holidays_history (
            holiday_id, country_code, holiday_name, holiday_date, is_recurring,
            recurring_month, recurring_day, status, is_archived, created_date, created_by, modified_by, modified_date,
            source
        ) VALUES (
            OLD.holiday_id, OLD.country_code, OLD.holiday_name, OLD.holiday_date, OLD.is_recurring,
            OLD.recurring_month, OLD.recurring_day, OLD.status, OLD.is_archived, OLD.created_date, OLD.created_by, OLD.modified_by, OLD.modified_date,
            OLD.source
        );
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS national_holidays_history_trigger ON core.national_holidays;
CREATE TRIGGER national_holidays_history_trigger
    AFTER INSERT OR UPDATE OR DELETE ON core.national_holidays
    FOR EACH ROW EXECUTE FUNCTION national_holidays_history_trigger();

-- Trigger: customer.user_payment_provider history
CREATE OR REPLACE FUNCTION user_payment_provider_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.user_payment_provider_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE user_payment_provider_id = OLD.user_payment_provider_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.user_payment_provider_history (
        event_id,
        user_payment_provider_id,
        user_id,
        provider,
        provider_customer_id,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.user_payment_provider_id,
        NEW.user_id,
        NEW.provider,
        NEW.provider_customer_id,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS user_payment_provider_history_trigger ON customer.user_payment_provider;
CREATE TRIGGER user_payment_provider_history_trigger
AFTER INSERT OR UPDATE ON customer.user_payment_provider
FOR EACH ROW
EXECUTE FUNCTION user_payment_provider_history_trigger_func();

-- =============================================================================
-- Employer Benefits Program history trigger
-- =============================================================================

CREATE OR REPLACE FUNCTION employer_benefits_program_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.employer_benefits_program_history
        SET is_current = FALSE, valid_until = CURRENT_TIMESTAMP
        WHERE program_id = OLD.program_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.employer_benefits_program_history (
        event_id, program_id, institution_id, institution_entity_id,
        benefit_rate, benefit_cap, benefit_cap_period,
        price_discount, minimum_monthly_fee,
        billing_cycle, billing_day, billing_day_of_week,
        enrollment_mode, allow_early_renewal,
        stripe_customer_id, stripe_payment_method_id, payment_method_type,
        is_active, is_archived, status, canonical_key,
        created_date, created_by, modified_by, modified_date,
        is_current, valid_until
    )
    VALUES (
        new_event_id, NEW.program_id, NEW.institution_id, NEW.institution_entity_id,
        NEW.benefit_rate, NEW.benefit_cap, NEW.benefit_cap_period,
        NEW.price_discount, NEW.minimum_monthly_fee,
        NEW.billing_cycle, NEW.billing_day, NEW.billing_day_of_week,
        NEW.enrollment_mode, NEW.allow_early_renewal,
        NEW.stripe_customer_id, NEW.stripe_payment_method_id, NEW.payment_method_type,
        NEW.is_active, NEW.is_archived, NEW.status, NEW.canonical_key,
        NEW.created_date, NEW.created_by, NEW.modified_by, NEW.modified_date,
        TRUE, 'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS employer_benefits_program_history_trigger ON core.employer_benefits_program;
CREATE TRIGGER employer_benefits_program_history_trigger
AFTER INSERT OR UPDATE ON core.employer_benefits_program
FOR EACH ROW
EXECUTE FUNCTION employer_benefits_program_history_trigger_func();

-- =============================================================================
-- Employer Bill history trigger
-- =============================================================================

CREATE OR REPLACE FUNCTION employer_bill_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.employer_bill_history
        SET is_current = FALSE, valid_until = CURRENT_TIMESTAMP
        WHERE employer_bill_id = OLD.employer_bill_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.employer_bill_history (
        event_id, employer_bill_id, institution_id, institution_entity_id,
        billing_period_start, billing_period_end, billing_cycle,
        total_renewal_events, gross_employer_share,
        price_discount, discounted_amount,
        minimum_fee_applied, billed_amount,
        currency_code, stripe_invoice_id,
        payment_status, paid_date,
        is_archived, status,
        created_date, created_by, modified_by, modified_date,
        is_current, valid_until
    )
    VALUES (
        new_event_id, NEW.employer_bill_id, NEW.institution_id, NEW.institution_entity_id,
        NEW.billing_period_start, NEW.billing_period_end, NEW.billing_cycle,
        NEW.total_renewal_events, NEW.gross_employer_share,
        NEW.price_discount, NEW.discounted_amount,
        NEW.minimum_fee_applied, NEW.billed_amount,
        NEW.currency_code, NEW.stripe_invoice_id,
        NEW.payment_status, NEW.paid_date,
        NEW.is_archived, NEW.status,
        NEW.created_date, NEW.created_by, NEW.modified_by, NEW.modified_date,
        TRUE, 'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS employer_bill_history_trigger ON billing.employer_bill;
CREATE TRIGGER employer_bill_history_trigger
AFTER INSERT OR UPDATE ON billing.employer_bill
FOR EACH ROW
EXECUTE FUNCTION employer_bill_history_trigger_func();

-- Trigger function for billing.supplier_terms history logging
CREATE OR REPLACE FUNCTION supplier_terms_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.supplier_terms_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE supplier_terms_id = OLD.supplier_terms_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.supplier_terms_history (
        event_id,
        supplier_terms_id,
        institution_id,
        institution_entity_id,
        no_show_discount,
        payment_frequency,
        kitchen_open_time,
        kitchen_close_time,
        require_invoice,
        invoice_hold_days,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.supplier_terms_id,
        NEW.institution_id,
        NEW.institution_entity_id,
        NEW.no_show_discount,
        NEW.payment_frequency,
        NEW.kitchen_open_time,
        NEW.kitchen_close_time,
        NEW.require_invoice,
        NEW.invoice_hold_days,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS supplier_terms_history_trigger ON billing.supplier_terms;
CREATE TRIGGER supplier_terms_history_trigger
AFTER INSERT OR UPDATE ON billing.supplier_terms
FOR EACH ROW
EXECUTE FUNCTION supplier_terms_history_trigger_func();

-- =============================================================================
-- Referral Config History Trigger
-- =============================================================================

CREATE OR REPLACE FUNCTION referral_config_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.referral_config_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE referral_config_id = OLD.referral_config_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.referral_config_history (
        event_id,
        referral_config_id,
        market_id,
        is_enabled,
        referrer_bonus_rate,
        referrer_bonus_cap,
        referrer_monthly_cap,
        min_plan_price_to_qualify,
        cooldown_days,
        held_reward_expiry_hours,
        pending_expiry_days,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.referral_config_id,
        NEW.market_id,
        NEW.is_enabled,
        NEW.referrer_bonus_rate,
        NEW.referrer_bonus_cap,
        NEW.referrer_monthly_cap,
        NEW.min_plan_price_to_qualify,
        NEW.cooldown_days,
        NEW.held_reward_expiry_hours,
        NEW.pending_expiry_days,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS referral_config_history_trigger ON customer.referral_config;
CREATE TRIGGER referral_config_history_trigger
AFTER INSERT OR UPDATE ON customer.referral_config
FOR EACH ROW
EXECUTE FUNCTION referral_config_history_trigger_func();

-- =============================================================================
-- Referral Info History Trigger
-- =============================================================================

CREATE OR REPLACE FUNCTION referral_info_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.referral_info_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE referral_id = OLD.referral_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.referral_info_history (
        event_id,
        referral_id,
        referrer_user_id,
        referee_user_id,
        referral_code_used,
        market_id,
        referral_status,
        bonus_credits_awarded,
        bonus_plan_price,
        bonus_rate_applied,
        qualified_date,
        rewarded_date,
        reward_held_until,
        expired_date,
        cancelled_date,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.referral_id,
        NEW.referrer_user_id,
        NEW.referee_user_id,
        NEW.referral_code_used,
        NEW.market_id,
        NEW.referral_status,
        NEW.bonus_credits_awarded,
        NEW.bonus_plan_price,
        NEW.bonus_rate_applied,
        NEW.qualified_date,
        NEW.rewarded_date,
        NEW.reward_held_until,
        NEW.expired_date,
        NEW.cancelled_date,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS referral_info_history_trigger ON customer.referral_info;
CREATE TRIGGER referral_info_history_trigger
AFTER INSERT OR UPDATE ON customer.referral_info
FOR EACH ROW
EXECUTE FUNCTION referral_info_history_trigger_func();

CREATE OR REPLACE FUNCTION referral_transaction_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.referral_transaction_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE referral_transaction_id = OLD.referral_transaction_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.referral_transaction_history (
        event_id,
        referral_transaction_id,
        referral_id,
        transaction_id,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.referral_transaction_id,
        NEW.referral_id,
        NEW.transaction_id,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS referral_transaction_history_trigger ON customer.referral_transaction;
CREATE TRIGGER referral_transaction_history_trigger
AFTER INSERT OR UPDATE ON customer.referral_transaction
FOR EACH ROW
EXECUTE FUNCTION referral_transaction_history_trigger_func();

-- =============================================================================
-- METADATA LAYER HISTORY TRIGGERS
-- =============================================================================
-- core.country_metadata / core.city_metadata / core.currency_metadata are the
-- writable Vianda-owned layer on top of external.*. Each gets a standard
-- "mark prior current row as not current, insert new history row" trigger.
-- external.* raw tables deliberately have NO history triggers — they're
-- reproducible from source TSVs via app/scripts/import_geonames.py.

-- ─────────────────────────────── country_metadata ───────────────────────────────

CREATE OR REPLACE FUNCTION country_metadata_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.country_metadata_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE country_metadata_id = OLD.country_metadata_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.country_metadata_history (
        event_id,
        country_metadata_id,
        country_iso,
        market_id,
        display_name_override,
        display_name_i18n,
        is_customer_audience,
        is_supplier_audience,
        is_employer_audience,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.country_metadata_id,
        NEW.country_iso,
        NEW.market_id,
        NEW.display_name_override,
        NEW.display_name_i18n,
        NEW.is_customer_audience,
        NEW.is_supplier_audience,
        NEW.is_employer_audience,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS country_metadata_history_trigger ON core.country_metadata;
CREATE TRIGGER country_metadata_history_trigger
AFTER INSERT OR UPDATE ON core.country_metadata
FOR EACH ROW
EXECUTE FUNCTION country_metadata_history_trigger_func();

-- ─────────────────────────────── city_metadata ───────────────────────────────

CREATE OR REPLACE FUNCTION city_metadata_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.city_metadata_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE city_metadata_id = OLD.city_metadata_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.city_metadata_history (
        event_id,
        city_metadata_id,
        geonames_id,
        country_iso,
        display_name_override,
        display_name_i18n,
        show_in_signup_picker,
        show_in_supplier_form,
        show_in_customer_form,
        is_served,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.city_metadata_id,
        NEW.geonames_id,
        NEW.country_iso,
        NEW.display_name_override,
        NEW.display_name_i18n,
        NEW.show_in_signup_picker,
        NEW.show_in_supplier_form,
        NEW.show_in_customer_form,
        NEW.is_served,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS city_metadata_history_trigger ON core.city_metadata;
CREATE TRIGGER city_metadata_history_trigger
AFTER INSERT OR UPDATE ON core.city_metadata
FOR EACH ROW
EXECUTE FUNCTION city_metadata_history_trigger_func();

-- ─────────────────────────────── currency_metadata ───────────────────────────────

CREATE OR REPLACE FUNCTION currency_metadata_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.currency_metadata_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE currency_metadata_id = OLD.currency_metadata_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.currency_metadata_history (
        event_id,
        currency_metadata_id,
        currency_code,
        credit_value_supplier_local,
        currency_conversion_usd,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.currency_metadata_id,
        NEW.currency_code,
        NEW.credit_value_supplier_local,
        NEW.currency_conversion_usd,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS currency_metadata_history_trigger ON core.currency_metadata;
CREATE TRIGGER currency_metadata_history_trigger
AFTER INSERT OR UPDATE ON core.currency_metadata
FOR EACH ROW
EXECUTE FUNCTION currency_metadata_history_trigger_func();

-- =============================================================================
-- Market Payout Aggregator History Trigger
-- =============================================================================
CREATE OR REPLACE FUNCTION market_payout_aggregator_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.market_payout_aggregator_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE market_id = OLD.market_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.market_payout_aggregator_history (
        event_id,
        market_id,
        aggregator,
        is_active,
        require_invoice,
        max_unmatched_bill_days,
        kitchen_open_time,
        kitchen_close_time,
        notes,
        is_archived,
        status,
        created_date,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.market_id,
        NEW.aggregator,
        NEW.is_active,
        NEW.require_invoice,
        NEW.max_unmatched_bill_days,
        NEW.kitchen_open_time,
        NEW.kitchen_close_time,
        NEW.notes,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS market_payout_aggregator_history_trigger ON billing.market_payout_aggregator;
CREATE TRIGGER market_payout_aggregator_history_trigger
AFTER INSERT OR UPDATE ON billing.market_payout_aggregator
FOR EACH ROW
EXECUTE FUNCTION market_payout_aggregator_history_trigger_func();

-- Trigger function for core.workplace_group history logging
CREATE OR REPLACE FUNCTION workplace_group_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.workplace_group_history
        SET is_current = FALSE, valid_until = CURRENT_TIMESTAMP
        WHERE workplace_group_id = OLD.workplace_group_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.workplace_group_history (
        event_id, workplace_group_id, name, email_domain, require_domain_verification,
        is_archived, status, created_date, created_by, modified_by, modified_date,
        is_current, valid_until
    )
    VALUES (
        new_event_id, NEW.workplace_group_id, NEW.name, NEW.email_domain, NEW.require_domain_verification,
        NEW.is_archived, NEW.status, NEW.created_date, NEW.created_by, NEW.modified_by, NEW.modified_date,
        TRUE, 'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS workplace_group_history_trigger ON core.workplace_group;
CREATE TRIGGER workplace_group_history_trigger
AFTER INSERT OR UPDATE ON core.workplace_group
FOR EACH ROW
EXECUTE FUNCTION workplace_group_history_trigger_func();

-- Trigger function for customer.plate_pickup_live history logging
CREATE OR REPLACE FUNCTION plate_pickup_live_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE audit.plate_pickup_live_history
        SET is_current  = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE plate_pickup_id = OLD.plate_pickup_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.plate_pickup_live_history (
        event_id,
        plate_pickup_id,
        plate_selection_id,
        user_id,
        restaurant_id,
        plate_id,
        product_id,
        qr_code_id,
        qr_code_payload,
        is_archived,
        status,
        was_collected,
        arrival_time,
        completion_time,
        expected_completion_time,
        confirmation_code,
        completion_type,
        extensions_used,
        code_verified,
        code_verified_time,
        handed_out_time,
        window_start,
        window_end,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.plate_pickup_id,
        NEW.plate_selection_id,
        NEW.user_id,
        NEW.restaurant_id,
        NEW.plate_id,
        NEW.product_id,
        NEW.qr_code_id,
        NEW.qr_code_payload,
        NEW.is_archived,
        NEW.status,
        NEW.was_collected,
        NEW.arrival_time,
        NEW.completion_time,
        NEW.expected_completion_time,
        NEW.confirmation_code,
        NEW.completion_type,
        NEW.extensions_used,
        NEW.code_verified,
        NEW.code_verified_time,
        NEW.handed_out_time,
        NEW.window_start,
        NEW.window_end,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS plate_pickup_live_history_trigger ON customer.plate_pickup_live;
CREATE TRIGGER plate_pickup_live_history_trigger
AFTER INSERT OR UPDATE ON customer.plate_pickup_live
FOR EACH ROW
EXECUTE FUNCTION plate_pickup_live_history_trigger_func();


-- Trigger function for billing.payment_attempt history logging
CREATE OR REPLACE FUNCTION payment_attempt_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this payment_attempt as not current
        UPDATE audit.payment_attempt_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE payment_attempt_id = OLD.payment_attempt_id AND is_current = TRUE;
    END IF;

    INSERT INTO audit.payment_attempt_history (
        event_id,
        payment_attempt_id,
        provider,
        provider_payment_id,
        idempotency_key,
        amount_cents,
        currency,
        payment_status,
        provider_status,
        failure_reason,
        provider_fee_cents,
        is_archived,
        status,
        created_date,
        created_by,
        modified_by,
        modified_date,
        is_current,
        valid_until
    )
    VALUES (
        new_event_id,
        NEW.payment_attempt_id,
        NEW.provider,
        NEW.provider_payment_id,
        NEW.idempotency_key,
        NEW.amount_cents,
        NEW.currency,
        NEW.payment_status,
        NEW.provider_status,
        NEW.failure_reason,
        NEW.provider_fee_cents,
        NEW.is_archived,
        NEW.status,
        NEW.created_date,
        NEW.created_by,
        NEW.modified_by,
        NEW.modified_date,
        TRUE,
        'infinity'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS payment_attempt_history_trigger ON billing.payment_attempt;
CREATE TRIGGER payment_attempt_history_trigger
AFTER INSERT OR UPDATE ON billing.payment_attempt
FOR EACH ROW
EXECUTE FUNCTION payment_attempt_history_trigger_func();