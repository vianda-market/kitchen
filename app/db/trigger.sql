-- role_info trigger removed - role_info table deprecated, roles stored directly on user_info as enums

-- Trigger function for institution_info history logging
CREATE OR REPLACE FUNCTION institution_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE institution_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE institution_id = OLD.institution_id AND is_current = TRUE;
    END IF;

    INSERT INTO institution_history (
        event_id,
        institution_id,
        name,
        institution_type,
        market_id,
        no_show_discount,
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
        NEW.market_id,
        NEW.no_show_discount,
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

CREATE TRIGGER institution_trigger
AFTER INSERT OR UPDATE ON institution_info
FOR EACH ROW
EXECUTE FUNCTION institution_trigger_func();

-- Trigger function for user_info history logging
CREATE OR REPLACE FUNCTION user_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this user as not current
        UPDATE user_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE user_id = OLD.user_id AND is_current = TRUE;
    END IF;

    INSERT INTO user_history (
        event_id,
        user_id,
        institution_id,
        role_type,
        role_name,
        username,
        hashed_password,
        first_name,
        last_name,
        email,
        cellphone,
        market_id,
        city_id,
        stripe_customer_id,
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
        NEW.hashed_password,
        NEW.first_name,
        NEW.last_name,
        NEW.email,
        NEW.cellphone,
        NEW.market_id,
        NEW.city_id,
        NEW.stripe_customer_id,
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

-- Create the trigger on user_info
CREATE TRIGGER user_history_trigger
AFTER INSERT OR UPDATE ON user_info
FOR EACH ROW
EXECUTE FUNCTION user_history_trigger_func();

-- Trigger: create default user_messaging_preferences on user insert
CREATE OR REPLACE FUNCTION user_messaging_preferences_insert_func()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_messaging_preferences (user_id)
    VALUES (NEW.user_id)
    ON CONFLICT (user_id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER user_messaging_preferences_trigger
AFTER INSERT ON user_info
FOR EACH ROW
EXECUTE FUNCTION user_messaging_preferences_insert_func();

-- Trigger function for institution_entity_info history logging
CREATE OR REPLACE FUNCTION institution_entity_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this supplier entity as not current
        UPDATE institution_entity_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE institution_entity_id = OLD.institution_entity_id AND is_current = TRUE;
    END IF;

    INSERT INTO institution_entity_history (
        event_id,
        institution_entity_id,
        institution_id,
        address_id,
        credit_currency_id,
        tax_id,
        name,
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
        NEW.credit_currency_id,
        NEW.tax_id,
        NEW.name,
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

-- Create the trigger on institution_entity_info
CREATE TRIGGER institution_entity_history_trigger
AFTER INSERT OR UPDATE ON institution_entity_info
FOR EACH ROW
EXECUTE FUNCTION institution_entity_history_trigger_func();

-- Trigger function for address_info history logging
CREATE OR REPLACE FUNCTION address_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this supplier entity as not current
        UPDATE address_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE address_id = OLD.address_id AND is_current = TRUE;
    END IF;

    INSERT INTO address_history (
        event_id,
        address_id,
        institution_id,
        user_id,
        address_type,
        country_code,
        province,
        city,
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

-- Create the trigger on address_info
CREATE TRIGGER address_history_trigger
AFTER INSERT OR UPDATE ON address_info
FOR EACH ROW
EXECUTE FUNCTION address_history_trigger_func();

-- Trigger function for geolocation_info history logging
CREATE OR REPLACE FUNCTION geolocation_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this supplier entity as not current
        UPDATE geolocation_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE geolocation_id = OLD.geolocation_id AND is_current = TRUE;
    END IF;

    INSERT INTO geolocation_history (
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

-- Create the trigger on geolocation_info
CREATE TRIGGER geolocation_history_trigger
AFTER INSERT OR UPDATE ON geolocation_info
FOR EACH ROW
EXECUTE FUNCTION geolocation_history_trigger_func();

-- Trigger function for restaurant_info history logging
CREATE OR REPLACE FUNCTION restaurant_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this restaurant as not current
        UPDATE restaurant_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE restaurant_id = OLD.restaurant_id AND is_current = TRUE;
    END IF;

    INSERT INTO restaurant_history (
        event_id,
        restaurant_id,
        institution_id,
        institution_entity_id,
        address_id,
        name,
        cuisine,
        pickup_instructions,
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
        NEW.cuisine,
        NEW.pickup_instructions,
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

-- Create the trigger on restaurant_info
CREATE TRIGGER restaurant_history_trigger
AFTER INSERT OR UPDATE ON restaurant_info
FOR EACH ROW
EXECUTE FUNCTION restaurant_history_trigger_func();

-- Trigger function for product_info history logging
CREATE OR REPLACE FUNCTION product_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this product as not current
        UPDATE product_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE product_id = OLD.product_id AND is_current = TRUE;
    END IF;

    INSERT INTO product_history (
        event_id,
        product_id,
        institution_id,
        name,
        ingredients,
        dietary,
        is_archived,
        status,
        image_storage_path,
        image_checksum,
        image_url,
        image_thumbnail_storage_path,
        image_thumbnail_url,
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
        NEW.ingredients,
        NEW.dietary,
        NEW.is_archived,
        NEW.status,
        NEW.image_storage_path,
        NEW.image_checksum,
        NEW.image_url,
        NEW.image_thumbnail_storage_path,
        NEW.image_thumbnail_url,
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

-- Create the trigger on product_info
CREATE TRIGGER product_history_trigger
AFTER INSERT OR UPDATE ON product_info
FOR EACH ROW
EXECUTE FUNCTION product_history_trigger_func();

-- Trigger function for plate_info history logging
CREATE OR REPLACE FUNCTION plate_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this plate as not current
        UPDATE plate_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE plate_id = OLD.plate_id AND is_current = TRUE;
    END IF;

    INSERT INTO plate_history (
        event_id,
        plate_id,
        product_id,
        restaurant_id,
        price,
        credit,
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

-- Create the trigger on plate_info
CREATE TRIGGER plate_history_trigger
AFTER INSERT OR UPDATE ON plate_info
FOR EACH ROW
EXECUTE FUNCTION plate_history_trigger_func();

-- Trigger function for client_transaction from plate_selection event
CREATE OR REPLACE FUNCTION log_plate_selection_txn()
  RETURNS TRIGGER
  SECURITY DEFINER               -- run with the trigger owner’s privileges
AS $$
BEGIN
  INSERT INTO client_transaction (
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
    'Active',                    -- mirror the default
    now(),                       -- explicit timestamp
    NEW.modified_by
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_plate_selection_ct ON plate_selection_info;

CREATE TRIGGER trg_plate_selection_ct
  AFTER INSERT ON plate_selection_info
  FOR EACH ROW
  WHEN (NEW.status = 'Active')  -- guard clause
  EXECUTE FUNCTION log_plate_selection_txn();

-- Trigger function for plate_selection_info history logging
CREATE OR REPLACE FUNCTION plate_selection_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE plate_selection_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE plate_selection_id = OLD.plate_selection_id AND is_current = TRUE;
    END IF;

    INSERT INTO plate_selection_history (
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

CREATE TRIGGER plate_selection_history_trigger
AFTER INSERT OR UPDATE ON plate_selection_info
FOR EACH ROW
EXECUTE FUNCTION plate_selection_history_trigger_func();

-- Before insert/update on plan_info: set credit_worth = price / credit (local currency per credit)
CREATE OR REPLACE FUNCTION plan_info_set_credit_worth_func()
RETURNS TRIGGER AS $$
BEGIN
    NEW.credit_worth := COALESCE(NEW.price / NULLIF(NEW.credit, 0), 0);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER plan_info_set_credit_worth_trigger
BEFORE INSERT OR UPDATE ON plan_info
FOR EACH ROW
EXECUTE FUNCTION plan_info_set_credit_worth_func();

-- Trigger function for plan_info history logging
CREATE OR REPLACE FUNCTION plan_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this plan as not current
        UPDATE plan_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE plan_id = OLD.plan_id AND is_current = TRUE;
    END IF;

    INSERT INTO plan_history (
        event_id,
        plan_id,
        market_id,
        name,
        credit,
        price,
        credit_worth,
        rollover,
        rollover_cap,
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
        NEW.credit,
        NEW.price,
        NEW.credit_worth,
        NEW.rollover,
        NEW.rollover_cap,
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

-- Create the trigger on plan_info
CREATE TRIGGER plan_history_trigger
AFTER INSERT OR UPDATE ON plan_info
FOR EACH ROW
EXECUTE FUNCTION plan_history_trigger_func();

-- Trigger function for subscription_info history logging
CREATE OR REPLACE FUNCTION subscription_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this subscription as not current
        UPDATE subscription_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE user_id = OLD.user_id AND is_current = TRUE;
    END IF;

    INSERT INTO subscription_history (
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

-- Create the trigger on subscription_info
CREATE TRIGGER subscription_history_trigger
AFTER INSERT OR UPDATE ON subscription_info
FOR EACH ROW
EXECUTE FUNCTION subscription_history_trigger_func();

-- Trigger function for subscription status activation (Pending -> Active when balance becomes positive)
CREATE OR REPLACE FUNCTION subscription_status_activation_trigger()
RETURNS TRIGGER AS $$
BEGIN
    -- Only activate if transitioning from Pending to positive balance
    -- Condition: status is 'Pending' AND balance transitions from <= 0 to > 0
    IF OLD.status = 'Pending' AND NEW.balance > 0 AND OLD.balance <= 0 THEN
        NEW.status := 'Active';
        -- Log the status change (visible in PostgreSQL logs)
        RAISE NOTICE 'Subscription % status automatically changed from Pending to Active (balance: % -> %)', 
            NEW.subscription_id, OLD.balance, NEW.balance;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create the trigger on subscription_info for automatic status activation
CREATE TRIGGER subscription_status_activation
BEFORE UPDATE ON subscription_info
FOR EACH ROW
WHEN (OLD.status = 'Pending' AND NEW.balance > 0 AND OLD.balance <= 0)
EXECUTE FUNCTION subscription_status_activation_trigger();

-- Trigger function for client_bill_info history logging
CREATE OR REPLACE FUNCTION client_bill_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this client_bill as not current
        UPDATE client_bill_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE client_bill_id = OLD.client_bill_id AND is_current = TRUE;
    END IF;

    INSERT INTO client_bill_history (
        event_id,
        client_bill_id,
        subscription_payment_id,
        subscription_id,
        user_id,
        plan_id,
        credit_currency_id,
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
        NEW.credit_currency_id,
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

-- Create the trigger on client_bill_info
CREATE TRIGGER client_bill_history_trigger
AFTER INSERT OR UPDATE ON client_bill_info
FOR EACH ROW
EXECUTE FUNCTION client_bill_history_trigger_func();


-- Trigger function for restaurant_balance_info history logging
CREATE OR REPLACE FUNCTION restaurant_balance_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this restaurant_balance as not current
        UPDATE restaurant_balance_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE restaurant_id = OLD.restaurant_id AND is_current = TRUE;
    END IF;

    INSERT INTO restaurant_balance_history (
        event_id,
        restaurant_id,
        credit_currency_id,
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
        NEW.credit_currency_id,
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

-- Create the trigger on restaurant_balance_info
CREATE TRIGGER restaurant_balance_history_trigger
AFTER INSERT OR UPDATE ON restaurant_balance_info
FOR EACH ROW
EXECUTE FUNCTION restaurant_balance_history_trigger_func();

-- Trigger function for institution_bill_info history logging
CREATE OR REPLACE FUNCTION institution_bill_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this institution_bill as not current
        UPDATE institution_bill_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE institution_bill_id = OLD.institution_bill_id AND is_current = TRUE;
    END IF;

    INSERT INTO institution_bill_history (
        event_id,
        institution_bill_id,
        institution_id,
        institution_entity_id,
        credit_currency_id,
        transaction_count,
        amount,
        currency_code,
        period_start,
        period_end,
        is_archived,
        status,
        resolution,
        tax_doc_external_id,
        stripe_payout_id,
        payout_completed_at,
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
        NEW.credit_currency_id,
        NEW.transaction_count,
        NEW.amount,
        NEW.currency_code,
        NEW.period_start,
        NEW.period_end,
        NEW.is_archived,
        NEW.status,
        NEW.resolution,
        NEW.tax_doc_external_id,
        NEW.stripe_payout_id,
        NEW.payout_completed_at,
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

-- Create the trigger on institution_bill_info
CREATE TRIGGER institution_bill_history_trigger
AFTER INSERT OR UPDATE ON institution_bill_info
FOR EACH ROW
EXECUTE FUNCTION institution_bill_history_trigger_func();

-- Trigger function for institution_settlement history logging
CREATE OR REPLACE FUNCTION institution_settlement_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        UPDATE institution_settlement_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE settlement_id = OLD.settlement_id AND is_current = TRUE;
    END IF;

    INSERT INTO institution_settlement_history (
        event_id,
        settlement_id,
        institution_entity_id,
        restaurant_id,
        period_start,
        period_end,
        kitchen_day,
        amount,
        currency_code,
        credit_currency_id,
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
        NEW.credit_currency_id,
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

DROP TRIGGER IF EXISTS institution_settlement_history_trigger ON institution_settlement;
CREATE TRIGGER institution_settlement_history_trigger
AFTER INSERT OR UPDATE ON institution_settlement
FOR EACH ROW
EXECUTE FUNCTION institution_settlement_history_trigger_func();

-- Trigger function for credit_currency_info history logging
CREATE OR REPLACE FUNCTION credit_currency_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this credit_currency as not current
        UPDATE credit_currency_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE credit_currency_id = OLD.credit_currency_id AND is_current = TRUE;
    END IF;

    INSERT INTO credit_currency_history (
        event_id,
        credit_currency_id,
        currency_name,
        currency_code,
        credit_value,
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
        NEW.credit_currency_id,
        NEW.currency_name,
        NEW.currency_code,
        NEW.credit_value,
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

-- Create the trigger on credit_currency_info
CREATE TRIGGER credit_currency_history_trigger
AFTER INSERT OR UPDATE ON credit_currency_info
FOR EACH ROW
EXECUTE FUNCTION credit_currency_history_trigger_func();

-- Trigger function for market_info history logging
CREATE OR REPLACE FUNCTION market_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    new_event_id UUID := uuidv7();
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Mark the previous history record for this market as not current
        UPDATE market_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE market_id = OLD.market_id AND is_current = TRUE;
    END IF;

    INSERT INTO market_history (
        event_id,
        market_id,
        country_name,
        country_code,
        credit_currency_id,
        timezone,
        kitchen_close_time,
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
        NEW.country_name,
        NEW.country_code,
        NEW.credit_currency_id,
        NEW.timezone,
        NEW.kitchen_close_time,
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

-- Create the trigger on market_info
CREATE TRIGGER market_history_trigger
AFTER INSERT OR UPDATE ON market_info
FOR EACH ROW
EXECUTE FUNCTION market_history_trigger_func();

-- Trigger function for restaurant_holidays history logging
CREATE OR REPLACE FUNCTION restaurant_holidays_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    v_operation audit_operation_enum;
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_operation := 'CREATE'::audit_operation_enum;
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.is_archived = FALSE AND NEW.is_archived = TRUE THEN
            v_operation := 'ARCHIVE'::audit_operation_enum;
        ELSE
            v_operation := 'UPDATE'::audit_operation_enum;
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        v_operation := 'DELETE'::audit_operation_enum;
    END IF;

    -- Mark previous records as not current
    IF TG_OP = 'UPDATE' THEN
        UPDATE restaurant_holidays_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE holiday_id = OLD.holiday_id AND is_current = TRUE;
    END IF;

    INSERT INTO restaurant_holidays_history (
        event_id,
        holiday_id,
        restaurant_id,
        country,
        holiday_date,
        holiday_name,
        is_recurring,
        recurring_month_day,
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
        COALESCE(NEW.holiday_id, OLD.holiday_id),
        COALESCE(NEW.restaurant_id, OLD.restaurant_id),
        COALESCE(NEW.country, OLD.country),
        COALESCE(NEW.holiday_date, OLD.holiday_date),
        COALESCE(NEW.holiday_name, OLD.holiday_name),
        COALESCE(NEW.is_recurring, OLD.is_recurring),
        COALESCE(NEW.recurring_month_day, OLD.recurring_month_day),
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

CREATE TRIGGER restaurant_holidays_history_trigger
AFTER INSERT OR UPDATE OR DELETE ON restaurant_holidays
FOR EACH ROW
EXECUTE FUNCTION restaurant_holidays_history_trigger_func();

-- Trigger function for plate_kitchen_days history logging
CREATE OR REPLACE FUNCTION plate_kitchen_days_history_trigger_func()
RETURNS TRIGGER AS $$
DECLARE
    v_operation audit_operation_enum;
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_operation := 'CREATE'::audit_operation_enum;
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.is_archived = FALSE AND NEW.is_archived = TRUE THEN
            v_operation := 'ARCHIVE'::audit_operation_enum;
        ELSE
            v_operation := 'UPDATE'::audit_operation_enum;
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        v_operation := 'DELETE'::audit_operation_enum;
    END IF;

    -- Mark previous records as not current
    IF TG_OP = 'UPDATE' THEN
        UPDATE plate_kitchen_days_history
        SET is_current = FALSE,
            valid_until = CURRENT_TIMESTAMP
        WHERE plate_kitchen_day_id = OLD.plate_kitchen_day_id AND is_current = TRUE;
    END IF;

    INSERT INTO plate_kitchen_days_history (
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

CREATE TRIGGER plate_kitchen_days_history_trigger
AFTER INSERT OR UPDATE OR DELETE ON plate_kitchen_days
FOR EACH ROW
EXECUTE FUNCTION plate_kitchen_days_history_trigger_func();

-- Auto-deactivate restaurant when all its plate_kitchen_days become inactive (archived or deleted)
CREATE OR REPLACE FUNCTION restaurant_auto_deactivate_when_no_plate_kitchen_days()
RETURNS TRIGGER AS $$
DECLARE
    v_restaurant_id UUID;
    v_active_count BIGINT;
BEGIN
    -- Only care when we are removing an active row (UPDATE is_archived to TRUE, or status to Inactive, or DELETE of an active row)
    IF TG_OP = 'UPDATE' AND (
        (OLD.is_archived = FALSE AND NEW.is_archived = TRUE) OR
        (OLD.status = 'Active'::status_enum AND NEW.status != 'Active'::status_enum)
    ) THEN
        NULL; -- fall through to get restaurant and check
    ELSIF TG_OP = 'DELETE' AND OLD.is_archived = FALSE AND OLD.status = 'Active'::status_enum THEN
        NULL; -- fall through
    ELSE
        RETURN COALESCE(NEW, OLD);
    END IF;

    SELECT p.restaurant_id INTO v_restaurant_id
    FROM plate_info p
    WHERE p.plate_id = COALESCE(OLD.plate_id, NEW.plate_id);

    IF v_restaurant_id IS NULL THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    SELECT COUNT(*) INTO v_active_count
    FROM plate_info p
    INNER JOIN plate_kitchen_days pkd ON pkd.plate_id = p.plate_id AND pkd.is_archived = FALSE AND pkd.status = 'Active'::status_enum
    WHERE p.restaurant_id = v_restaurant_id AND p.is_archived = FALSE;

    IF v_active_count = 0 THEN
        UPDATE restaurant_info
        SET status = 'Inactive'::status_enum,
            modified_date = CURRENT_TIMESTAMP
        WHERE restaurant_id = v_restaurant_id AND status = 'Active'::status_enum;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER restaurant_auto_deactivate_on_plate_kitchen_days
AFTER UPDATE OR DELETE ON plate_kitchen_days
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
        (OLD.status = 'Active'::status_enum AND NEW.status != 'Active'::status_enum)
    ) THEN
        NULL; -- fall through
    ELSIF TG_OP = 'DELETE' AND OLD.is_archived = FALSE AND OLD.status = 'Active'::status_enum THEN
        NULL; -- fall through
    ELSE
        RETURN COALESCE(NEW, OLD);
    END IF;

    v_restaurant_id := COALESCE(OLD.restaurant_id, NEW.restaurant_id);

    IF v_restaurant_id IS NULL THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    SELECT COUNT(*) INTO v_active_count
    FROM qr_code
    WHERE restaurant_id = v_restaurant_id
      AND is_archived = FALSE
      AND status = 'Active'::status_enum;

    IF v_active_count = 0 THEN
        UPDATE restaurant_info
        SET status = 'Inactive'::status_enum,
            modified_date = CURRENT_TIMESTAMP
        WHERE restaurant_id = v_restaurant_id AND status = 'Active'::status_enum;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER restaurant_auto_deactivate_on_qr_code
AFTER UPDATE OR DELETE ON qr_code
FOR EACH ROW
EXECUTE FUNCTION restaurant_auto_deactivate_when_no_active_qr_code();

-- status_info trigger removed - status_info table deprecated, status stored directly on entities as enum
-- transaction_type_info trigger removed - transaction_type_info table deprecated, transaction_type stored directly on transaction tables as enum

-- National holidays history trigger
CREATE OR REPLACE FUNCTION national_holidays_history_trigger()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO national_holidays_history (
            holiday_id, country_code, holiday_name, holiday_date, is_recurring,
            recurring_month, recurring_day, status, is_archived, created_date, created_by, modified_by, modified_date
        ) VALUES (
            NEW.holiday_id, NEW.country_code, NEW.holiday_name, NEW.holiday_date, NEW.is_recurring,
            NEW.recurring_month, NEW.recurring_day, NEW.status, NEW.is_archived, NEW.created_date, NEW.created_by, NEW.modified_by, NEW.modified_date
        );
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO national_holidays_history (
            holiday_id, country_code, holiday_name, holiday_date, is_recurring,
            recurring_month, recurring_day, status, is_archived, created_date, created_by, modified_by, modified_date
        ) VALUES (
            NEW.holiday_id, NEW.country_code, NEW.holiday_name, NEW.holiday_date, NEW.is_recurring,
            NEW.recurring_month, NEW.recurring_day, NEW.status, NEW.is_archived, NEW.created_date, NEW.created_by, NEW.modified_by, NEW.modified_date
        );
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO national_holidays_history (
            holiday_id, country_code, holiday_name, holiday_date, is_recurring,
            recurring_month, recurring_day, status, is_archived, created_date, created_by, modified_by, modified_date
        ) VALUES (
            OLD.holiday_id, OLD.country_code, OLD.holiday_name, OLD.holiday_date, OLD.is_recurring,
            OLD.recurring_month, OLD.recurring_day, OLD.status, OLD.is_archived, OLD.created_date, OLD.created_by, OLD.modified_by, OLD.modified_date
        );
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER national_holidays_history_trigger
    AFTER INSERT OR UPDATE OR DELETE ON national_holidays
    FOR EACH ROW EXECUTE FUNCTION national_holidays_history_trigger();