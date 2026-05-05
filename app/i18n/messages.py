"""
Message catalog for localized API responses.
Phase 1: scaffold. Phase 5: full entity CRUD, DB constraint, and email subject translations.
"""

from typing import Any

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        # Auth / user errors
        "error.user_not_found": "User not found.",
        "error.duplicate_email": "An account with this email already exists.",
        "error.invalid_credentials": "Invalid username or password.",
        "error.email_change_code_expired": "Verification code has expired. Please request a new one.",
        "error.email_change_code_invalid": "Invalid verification code.",
        # Auth / user alerts
        "alert.email_verified": "Email verified successfully.",
        "alert.email_change_requested": "A verification code has been sent to {email}.",
        # Entity CRUD errors
        "error.entity_not_found": "{entity} not found",
        "error.entity_not_found_by_id": "{entity} with ID {id} not found",
        "error.entity_creation_failed": "Failed to create {entity}",
        "error.entity_update_failed": "Failed to update {entity}",
        "error.entity_deletion_failed": "Failed to delete {entity}",
        "error.entity_operation_failed": "{entity} not found or {operation} failed",
        # Database constraint errors
        "error.db_duplicate_key": "Record with this value already exists",
        "error.db_duplicate_email": "User with this email already exists",
        "error.db_duplicate_username": "User with this username already exists",
        "error.db_duplicate_market": "Market already exists for this country",
        "error.db_duplicate_currency": "Credit currency with this code already exists",
        "error.db_duplicate_institution": "Institution with this name already exists",
        "error.db_duplicate_restaurant": "Restaurant with this name already exists",
        "error.db_fk_user": "Referenced user does not exist",
        "error.db_fk_institution": "Referenced institution does not exist",
        "error.db_fk_currency": "Referenced credit currency does not exist",
        "error.db_fk_subscription": "Referenced subscription does not exist",
        "error.db_fk_plan": "Referenced plan does not exist",
        "error.db_fk_payment": "Referenced payment attempt does not exist",
        "error.db_fk_generic": "Referenced record does not exist",
        "error.db_notnull_modified_by": "Modified by field is required",
        "error.db_notnull_currency_code": "Currency code is required",
        "error.db_notnull_currency_name": "Currency name is required",
        "error.db_notnull_username": "Username is required",
        "error.db_notnull_email": "Email is required",
        "error.db_notnull_generic": "Required field is missing",
        "error.db_check_violation": "Invalid data provided violates business rules",
        "error.db_invalid_uuid": "Invalid UUID format",
        "error.db_invalid_format": "Invalid data format",
        "error.db_generic": "Database error during {operation}: {detail}",
        # Email subjects
        "email.subject_password_reset": "Reset Your Vianda Password",
        "email.subject_b2b_invite": "You've been invited to Vianda – Set your password",
        "email.subject_benefit_invite": "{employer_name} has set up a Vianda meal benefit for you",
        "email.subject_email_change_verify": "Confirm your new email for Vianda",
        "email.subject_email_change_confirm": "Your Vianda account email was changed",
        "email.subject_username_recovery": "Your Vianda username",
        "email.subject_signup_verify": "Verify your email to complete signup",
        "email.subject_welcome": "Welcome to Vianda!",
        # Onboarding outreach
        "email.subject_onboarding_getting_started": "Welcome to Vianda — let's set up your restaurant",
        "email.subject_onboarding_need_help": "Need help finishing your Vianda setup?",
        "email.subject_onboarding_incomplete": "Your Vianda setup is almost there",
        "email.subject_onboarding_complete": "Your restaurant is live on Vianda!",
        # Customer engagement
        "email.subject_customer_subscribe": "Start your Vianda subscription",
        "email.subject_customer_missing_out": "You're missing out on Vianda",
        "email.subject_benefit_waiting": "{employer_name} is covering your meals — activate now",
        "email.subject_benefit_reminder": "Your meal benefit from {employer_name} is still waiting",
        # Promotional
        "email.subject_subscription_promo": "Special offer: {promo_details}",
        # Rate limiting
        "error.rate_limit_exceeded": "Too many requests. Please try again later.",
        # ── ErrorCode registry keys (K2) ──────────────────────────────────
        # request.* — pre-route errors (set by catch-all handler, K3)
        "request.not_found": "The requested resource was not found.",
        "request.method_not_allowed": "This HTTP method is not allowed for this endpoint.",
        "request.malformed_body": "The request body could not be parsed.",
        "request.too_large": "The request payload is too large.",
        "request.rate_limited": "Too many requests. Please try again in {retry_after_seconds} seconds.",
        # validation.* — emitted by RequestValidationError handler (K3/K5/K67)
        "validation.field_required": "This field is required.",
        "validation.invalid_format": "The value has an invalid format.",
        "validation.value_too_short": "The value is too short.",
        "validation.value_too_long": "The value is too long.",
        "validation.invalid_value": "The value is not one of the allowed options.",
        "validation.invalid_type": "The value has an invalid type.",
        "validation.custom": "{msg}",
        # validation.user.*
        "validation.user.invalid_role_combination": "Invalid role combination: {role_type} + {role_name}.",
        "validation.user.unsupported_locale": "Unsupported locale '{requested}'. Must be one of: {allowed}.",
        "validation.user.passwords_do_not_match": "New password and confirmation do not match.",
        "validation.user.new_password_same_as_current": "New password must differ from current password.",
        # validation.address.*
        "validation.address.city_required": "Either city_metadata_id or city_name is required.",
        "validation.address.invalid_address_type": "Invalid address type '{address_type}'.",
        "validation.address.duplicate_address_type": "Address type cannot contain duplicate values.",
        "validation.address.invalid_street_type": "Invalid street type '{street_type}'.",
        "validation.address.country_required": "Either country_code or country name must be provided, or use place_id.",
        "validation.address.field_required": "Field '{address_field}' is required when place_id is not provided.",
        "validation.address.city_metadata_id_required": "city_metadata_id is required when place_id is not provided.",
        # validation.plate.*
        "validation.plate.kitchen_days_empty": "kitchen_days cannot be empty.",
        "validation.plate.kitchen_days_duplicate": "kitchen_days cannot contain duplicate days.",
        # validation.discretionary.*
        "validation.discretionary.recipient_required": "Either user_id or restaurant_id must be provided.",
        "validation.discretionary.conflicting_recipients": "Cannot specify both user_id and restaurant_id.",
        "validation.discretionary.restaurant_required": "This category requires restaurant_id.",
        # validation.holiday.*
        "validation.holiday.recurring_fields_required": "Both recurring_month and recurring_day are required when is_recurring is True.",
        "validation.holiday.list_empty": "At least one holiday must be provided.",
        # validation.subscription.*
        "validation.subscription.window_invalid": "hold_end_date must be after hold_start_date.",
        "validation.subscription.window_too_long": "Hold duration cannot exceed 3 months.",
        # validation.payment.*
        "validation.payment.conflicting_address_fields": "Cannot provide both address_id and address_data.",
        "validation.payment.unsupported_brand": "Payment method type is not supported.",
        "validation.payment.address_required": "Payment method type '{method_type}' requires an address. Provide address_id or address_data.",
        # validation.supplier_invoice.* — K67
        "validation.supplier_invoice.cae_format": "CAE code must be exactly 14 digits.",
        "validation.supplier_invoice.cuit_format": "CUIT must match format XX-XXXXXXXX-X.",
        "validation.supplier_invoice.afip_doc_type": "AFIP document type must be one of: A, B, C.",
        "validation.supplier_invoice.sunat_serie_format": "SUNAT serie must match format F + 3 digits (e.g. F001).",
        "validation.supplier_invoice.sunat_correlativo_format": "SUNAT correlativo must be 1–8 digits.",
        "validation.supplier_invoice.ruc_format": "RUC must be exactly 11 digits.",
        "validation.supplier_invoice.cdr_status": "CDR status must be one of: accepted, rejected, pending.",
        "validation.supplier_invoice.ar_details_required": "AR invoices require ar_details.",
        "validation.supplier_invoice.pe_details_required": "PE invoices require pe_details.",
        "validation.supplier_invoice.us_details_required": "US invoices require us_details.",
        "validation.supplier_invoice.rejection_reason_required": "rejection_reason is required when rejecting an invoice.",
        "validation.supplier_invoice.status_cannot_reset": "Cannot set invoice status back to Pending Review.",
        "validation.supplier_invoice.w9_ein_format": "ein_last_four must be exactly 4 digits.",
        # validation.market.* — K67
        "validation.market.language_unsupported": "Unsupported language '{language}'. Must be one of: {allowed}.",
        # auth.* — K7
        "auth.invalid_token": "Authentication token is invalid or expired.",
        "auth.captcha_required": "CAPTCHA verification is required.",
        "auth.captcha_verification_failed": "CAPTCHA verification failed.",
        "auth.captcha_action_mismatch": "CAPTCHA action mismatch.",
        "auth.captcha_score_too_low": "CAPTCHA score is too low. Please try again.",
        "auth.captcha_token_missing": "Missing reCAPTCHA token.",
        "auth.credentials_invalid": "Invalid username or password.",
        "auth.account_inactive": "Account is not active. Please contact support.",
        "auth.customer_app_only": "Customer accounts must use the Vianda mobile app.",
        "auth.dummy_admin_not_configured": "Dummy admin user is not configured.",
        "auth.token_user_id_invalid": "Invalid user identifier in token.",
        "auth.token_institution_id_invalid": "Invalid institution identifier in token.",
        "auth.token_missing_fields": "Token is missing required fields.",
        # security.* — K7
        "security.institution_mismatch": "Access denied: institution mismatch.",
        "security.insufficient_permissions": "You do not have permission to perform this action.",
        "security.forbidden": "Access denied.",
        "security.token_user_id_missing": "User ID not found in token.",
        "security.token_user_id_invalid": "Invalid user ID format in token.",
        "security.address_type_not_allowed": "Address type not allowed for your role.",
        "security.address_type_institution_mismatch": "Address type is not compatible with this institution type.",
        "security.user_role_type_not_allowed": "You are not allowed to create or update users with this role type.",
        "security.user_role_name_not_allowed": "You are not allowed to assign this role name.",
        "security.operator_cannot_create_users": "Operators cannot create or edit user accounts.",
        "security.cannot_assign_role": "You do not have permission to assign this role.",
        "security.cannot_edit_user": "You do not have permission to edit this user.",
        "security.customer_cannot_edit_employer_address": "Customers cannot edit or delete employer addresses.",
        "security.supplier_address_mutation_denied": "Supplier Operators cannot create or edit addresses.",
        "security.supplier_user_mutation_denied": "Supplier Operators cannot create or edit users.",
        "security.supplier_management_denied": "Supplier Operators cannot access management operations.",
        "security.supplier_admin_only": "Only Supplier Admin can access this resource.",
        "security.supplier_password_reset_denied": "Supplier Operators cannot reset other users' passwords.",
        "security.institution_type_mismatch": "Institution type does not match user role type.",
        "security.supplier_institution_only": "Suppliers can only add users to their own institution.",
        "security.supplier_institution_required": "Your account has no institution configured.",
        "security.employer_not_for_supplier": "Employer is not applicable to Supplier, Internal, or Employer users.",
        "security.supplier_terms_edit_denied": "Only authorized Internal users can edit supplier terms.",
        # subscription.*
        "subscription.already_active": "This subscription is already active.",
        # entity.* — generic entity CRUD errors (K6)
        "entity.not_found": "{entity} not found",
        "entity.not_found_or_operation_failed": "{entity} not found or {operation} failed",
        "entity.creation_failed": "Failed to create {entity}",
        "entity.update_failed": "Failed to update {entity}",
        "entity.deletion_failed": "Failed to delete {entity}",
        # entity.* — additional codes (K8)
        "entity.field_immutable": "The field '{field}' cannot be changed after creation.",
        # product.* — K8
        "product.image_too_large": "Image too large. Maximum size is 5 MB.",
        # credit_currency.* — K8
        "credit_currency.name_not_supported": "Currency name not supported. Use GET /api/v1/currencies/ for the list.",
        "credit_currency.rate_unavailable": "Currency '{currency_code}' is not supported by the exchange rate API.",
        # employer.* — K8
        "employer.benefit_program_not_found": "No employer benefit program found.",
        # user.* — K8
        "user.market_not_assigned": "User has no market assigned.",
        # institution.* — K8
        "institution.system_protected": "System institutions cannot be archived.",
        "institution.supplier_terms_invalid": "supplier_terms can only be provided when institution_type is Supplier.",
        # institution_entity.* — K8
        "institution_entity.market_mismatch": "Entity's address country is not in institution's assigned markets.",
        # user.signup.* / user.* — user identity errors (K9)
        "user.city_not_found": "City not found.",
        "user.city_archived": "City is archived. Use an active city.",
        "user.city_must_be_specific": "Customers must have a specific city, not Global.",
        "user.city_required": "City is required and cannot be removed.",
        "user.city_country_mismatch": "City must be in the same country as your market.",
        "user.market_not_found": "Market not found.",
        "user.market_archived": "Market is archived. Use an active market.",
        "user.market_global_not_allowed": "Only Admin or Super Admin can assign Global market.",
        "user.market_id_invalid": "Invalid market identifier.",
        "user.signup_code_invalid": "Invalid or expired verification code.",
        "user.signup_country_required": "country_code is required. Use GET /api/v1/leads/markets for valid country codes.",
        "user.signup_institution_required": "institution_id is required for this user type.",
        "user.lookup_param_required": "At least one of username or email must be provided.",
        "user.address_not_found": "Address not found.",
        "user.address_archived": "Address is archived. Use an active address.",
        "user.address_institution_mismatch": "Address does not belong to the specified employer.",
        "user.workplace_group_not_found": "Workplace group not found.",
        "user.workplace_group_archived": "Workplace group is archived.",
        "user.invite_no_email": "User has no email address. Cannot send invite.",
        "user.onboarding_customer_only": "Onboarding status is only available for Customer users.",
        # server.* — generic suppressed internal error (K9, Decision F)
        "server.internal_error": "An internal error occurred. Please try again or contact support.",
        # subscription.* — lifecycle errors (K10)
        "subscription.not_found": "Subscription not found.",
        "subscription.not_pending": "Subscription is not Pending.",
        "subscription.not_on_hold": "Subscription is not on hold.",
        "subscription.already_on_hold": "Subscription is already on hold.",
        "subscription.already_cancelled": "Subscription is already cancelled.",
        "subscription.cannot_hold_cancelled": "Cannot put a cancelled subscription on hold.",
        "subscription.confirm_mock_only": "confirm-payment is only available when PAYMENT_PROVIDER=mock. Use Stripe webhook for live.",
        "subscription.payment_not_found": "No pending payment found for this subscription.",
        "subscription.payment_record_not_found": "No subscription payment found for this subscription.",
        "subscription.payment_provider_unavailable": "Payment details not available for this provider.",
        "subscription.access_denied": "You do not have access to this subscription.",
        # plate_selection.* — lifecycle errors (K10)
        "plate_selection.not_found": "Plate selection not found.",
        "plate_selection.immutable_fields": "Cannot modify {fields}. Only pickup_time_range, pickup_intent, and flexible_on_time are editable. To change the plate, cancel this selection and create a new one.",
        "plate_selection.access_denied": "Not authorized to access this plate selection.",
        "plate_selection.not_editable": "Plate selection is no longer editable. Edits are allowed until 1 hour before kitchen day opens.",
        "plate_selection.not_cancellable": "Plate selection is no longer editable. Cancellation is allowed until 1 hour before kitchen day opens.",
        "plate_selection.duplicate_kitchen_day": "You already have a plate reserved for {kitchen_day}. Continue to cancel your meal and reserve this plate?",
        # plate_pickup.* — errors (K10)
        "plate_pickup.access_denied": "Not authorized to access this pickup record.",
        "plate_pickup.invalid_qr_code": "This QR code is not recognized.",
        "plate_pickup.wrong_restaurant": "You scanned the wrong restaurant's QR code.",
        "plate_pickup.no_active_reservation": "No active reservation found for this restaurant.",
        "plate_pickup.invalid_status": "Cannot perform this action with the current pickup status.",
        "plate_pickup.invalid_signature": "Invalid QR code signature.",
        "plate_pickup.cannot_delete": "Cannot delete pickup record with status {pickup_status}. Only pending orders can be deleted.",
        # plate_review.* — errors (K10)
        "plate_review.not_found": "Pickup not found.",
        "plate_review.access_denied": "This pickup does not belong to you.",
        "plate_review.not_eligible": "You can only review plates you have picked up. Complete the pickup first.",
        "plate_review.pickup_archived": "Cannot review an archived pickup.",
        "plate_review.already_exists": "This pickup has already been reviewed. Reviews are immutable.",
        "plate_review.invalid_portion_rating": "Portion complaints can only be filed for reviews with portion size rating of 1 (small).",
        "plate_review.complaint_exists": "A portion complaint has already been filed for this review.",
        # payment_provider.* — Stripe Connect errors (K10)
        "payment_provider.onboarding_required": "Entity has no payout provider account. Complete onboarding first.",
        "payment_provider.not_ready": "Stripe Connect account is not yet enabled for payouts. Supplier must complete onboarding.",
        "payment_provider.payout_exists": "A payout for this bill already exists with status '{payout_status}'.",
        "payment_provider.unavailable": "Payment provider temporarily unavailable.",
        "payment_provider.rate_limited": "Payment provider rate limit exceeded.",
        "payment_provider.auth_failed": "Payment provider authentication failed.",
        "payment_provider.error": "Payment provider error.",
        "payment_provider.bill_not_pending": "Bill resolution is '{resolution}'; only pending bills can be paid out.",
        # mercado_pago.* — OAuth errors (K10)
        "mercado_pago.auth_code_missing": "Missing authorization code.",
        "mercado_pago.auth_failed": "Mercado Pago authorization failed.",
        # database.* — constraint violation errors (K6)
        "database.duplicate_key": "A record with this value already exists.",
        "database.duplicate_email": "A user with this email already exists.",
        "database.duplicate_username": "A user with this username already exists.",
        "database.duplicate_market": "A market already exists for this country.",
        "database.duplicate_currency": "A credit currency with this code already exists.",
        "database.duplicate_institution": "An institution with this name already exists.",
        "database.duplicate_restaurant": "A restaurant with this name already exists.",
        "database.foreign_key_user": "The referenced user does not exist.",
        "database.foreign_key_institution": "The referenced institution does not exist.",
        "database.foreign_key_currency": "The referenced credit currency does not exist.",
        "database.foreign_key_subscription": "The referenced subscription does not exist.",
        "database.foreign_key_plan": "The referenced plan does not exist.",
        "database.foreign_key_payment": "The referenced payment attempt does not exist.",
        "database.foreign_key_violation": "The referenced record does not exist.",
        "database.not_null_modified_by": "The modified by field is required.",
        "database.not_null_currency_code": "Currency code is required.",
        "database.not_null_currency_name": "Currency name is required.",
        "database.not_null_username": "Username is required.",
        "database.not_null_email": "Email is required.",
        "database.not_null_violation": "A required field is missing.",
        "database.check_violation": "The provided data violates business rules.",
        "database.invalid_uuid": "Invalid UUID format.",
        "database.invalid_format": "Invalid data format.",
        "database.error": "Database error during {operation}: {detail}",
        # restaurant.* — restaurant management errors (K11)
        "restaurant.not_found": "Restaurant not found.",
        "restaurant.entity_id_required": "institution_entity_id is required.",
        "restaurant.market_required": "A market is required. Send market_id or ensure the user has a primary market.",
        "restaurant.market_access_denied": "market_id must be one of your assigned markets.",
        "restaurant.active_requires_setup": "Cannot set restaurant to Active. The restaurant must have at least one plate with active plate_kitchen_days and at least one active QR code. Add plate_kitchen_days and create a QR code via POST /api/v1/qr-codes, then try again.",
        "restaurant.active_requires_plate_days": "Cannot set restaurant to Active. The restaurant must have at least one plate with active plate_kitchen_days. Add and activate plate_kitchen_days for the restaurant's plates, then try again.",
        "restaurant.active_requires_qr": "Cannot set restaurant to Active. The restaurant must have at least one active QR code. Create a QR code via POST /api/v1/qr-codes for this restaurant, then try again.",
        "restaurant.active_requires_entity_payouts": "Cannot activate restaurant: the linked institution entity has not completed Stripe Connect. Complete payout onboarding for the entity, then try again.",
        # restaurant_holiday.* — K11
        "restaurant_holiday.not_found": "Restaurant holiday not found.",
        "restaurant_holiday.duplicate": "Restaurant already has a holiday registered for {holiday_date}.",
        "restaurant_holiday.on_national_holiday": "Date {holiday_date} is already a national holiday. Restaurants cannot register holidays on national holidays.",
        # national_holiday.* — K11
        "national_holiday.not_found": "National holiday not found.",
        "national_holiday.update_empty": "No fields provided for update.",
        # push.* — FCM notification copy (K4)
        "push.pickup_ready_title": "Plate ready",
        "push.pickup_ready_body": "Did you receive your plate from {restaurant_name}?",
        # market.* — K12 (admin + billing sweep)
        "market.not_found": "Market not found.",
        "market.country_not_supported": "Country not supported for new markets. Use GET /api/v1/countries/ for the list of supported countries.",
        "market.super_admin_only": "Only Super Admin can perform this action on the Global Marketplace.",
        "market.no_coverage_to_activate": "Cannot activate: market has no active restaurant with an active plate on an active weekly kitchen-day. Schedule coverage first, then set status to active.",
        "market.has_coverage_confirm_deactivate": "This market currently has active plate coverage. Deactivating will hide it from customers immediately. Resubmit with confirm_deactivate=true to proceed.",
        "market.global_cannot_be_archived": "The Global Marketplace cannot be archived.",
        "market.billing_config_not_found": "No billing config found for this market.",
        # ad_zone.* — K12
        "ad_zone.not_found": "Ad zone not found.",
        # cuisine.* — K12
        "cuisine.not_found": "Cuisine not found.",
        "cuisine.suggestion_not_found": "Suggestion not found or already reviewed.",
        # archival.* — K12
        "archival.no_records_provided": "No record IDs provided.",
        "archival.too_many_records": "Cannot archive more than 1000 records at once.",
        "archival_config.not_found": "Archival configuration not found.",
        "archival_config.already_exists": "A configuration already exists for table {table_name}.",
        # referral_config.* — K12
        "referral_config.not_found": "Referral config not found for this market.",
        # supplier_invoice.* — K12
        "supplier_invoice.not_found": "Supplier invoice not found.",
        "supplier_invoice.invalid_status": "Cannot review invoice with status '{invoice_status}'. Must be 'pending_review'.",
        # billing.* — K12
        "billing.bill_not_found": "Bill not found.",
        "billing.bill_already_paid": "Cannot cancel a paid bill.",
        "billing.bill_already_cancelled": "Bill is already cancelled.",
        "billing.plan_no_credits": "Plan has no credits; cannot process.",
        "billing.no_data_found": "No billing data found for this institution.",
        # discretionary.* — K12
        "discretionary.not_found": "Discretionary request not found.",
        "discretionary.not_pending": "Cannot update request with status: {request_status}.",
        # discretionary.* — K13
        "discretionary.recipient_institution_mismatch": "Selected recipient is not in the specified institution.",
        "discretionary.recipient_market_mismatch": "Selected recipient is not in the specified market.",
        "discretionary.invalid_amount": "Amount must be greater than 0.",
        "discretionary.invalid_category": "Invalid category value: {category}.",
        "discretionary.category_requires_restaurant": "Category '{category}' requires restaurant_id to be specified.",
        # enrollment.* — K13
        "enrollment.no_active_program": "No active benefits program for this institution.",
        "enrollment.email_already_registered": "Email already registered in the system.",
        "enrollment.city_no_market": "City not found or has no active market.",
        "enrollment.employer_institution_id_required": "Internal users must provide institution_id query parameter to specify which Employer institution to operate on.",
        "enrollment.partial_subsidy_requires_app": "This benefit only covers part of the plan price. The employee must subscribe through the Vianda app to pay their share.",
        # employer.program.* — K13
        "employer.program_already_exists": "A benefits program already exists for this {scope}.",
        # user.market.* — K14
        "user.market_ids_empty": "market_ids must contain at least one market.",
        "user.market_ids_invalid": "Invalid or archived market_id(s): {market_ids}.",
        "user.market_not_in_institution": "Market {market_id} is not assigned to the user's institution.",
        "user.duplicate_username": "Username already exists.",
        "user.duplicate_email_in_system": "Email already exists.",
        # entity.archive.* — K14
        "entity.search_invalid_param": "search_by must be one of: {allowed}.",
        "entity.archive_active_pickups": "Cannot archive entity: {count} active plate pickup(s) exist. Complete or cancel them first.",
        "entity.archive_active_restaurants": "Cannot archive entity: {count} active restaurant(s) must be archived first: {names}.",
        "restaurant.archive_active_pickups": "Cannot archive restaurant: {count} active plate pickup(s) exist. Complete or cancel them first.",
        # plate_kitchen_day.* — K14
        "plate_kitchen_day.not_found": "Plate kitchen day not found.",
        "plate_kitchen_day.duplicate": "Plate {plate_id} is already assigned to {kitchen_day}.",
        "plate_kitchen_day.plate_id_immutable": "plate_id cannot be changed on an existing kitchen day; create a new record and archive the old one if needed.",
        "plate_kitchen_day.archive_failed": "Failed to archive plate kitchen day.",
        "plate_kitchen_day.update_failed": "Failed to update plate kitchen day.",
        "plate_kitchen_day.delete_failed": "Failed to delete plate kitchen day.",
        # restaurant.status.* — K14 (plate selection validation)
        "restaurant.archived": "Restaurant '{name}' is archived and cannot accept new orders.",
        "restaurant.entity_archived": "Restaurant '{name}' belongs to an archived entity and cannot accept new orders.",
        "restaurant.unavailable": "Restaurant '{name}' {status_message} and cannot accept new orders. Please try another restaurant.",
        "restaurant.national_holiday": "Restaurant '{name}' cannot accept orders on {date} due to a national holiday. Please select another date.",
        "restaurant.restaurant_holiday": "Restaurant '{name}' is closed on {date} due to a restaurant holiday. Please select another date.",
        # plate_selection.window.* — K14
        "plate_selection.pickup_time_required": "pickup_time_range is required and must be in HH:MM-HH:MM format (e.g. 11:30-11:45).",
        "plate_selection.no_pickup_windows": "No pickup windows available for {kitchen_day} in this market. Please select another day.",
        "plate_selection.invalid_pickup_window": "pickup_time_range '{pickup_time_range}' is not a valid pickup window for {kitchen_day}. Allowed windows: {allowed_windows}.",
        "plate_selection.kitchen_day_invalid": "Kitchen is not operational on {kitchen_day}. Available days: {available_days}.",
        "plate_selection.kitchen_day_not_available": "Plate is not available for {kitchen_day}. Available days: {available_days}.",
        "plate_selection.kitchen_day_too_far": "Cannot order for {kitchen_day} from {current_day}. Orders are only allowed up to 1 week ahead.",
        "plate_selection.no_kitchen_days": "No available kitchen days found within the next week. Available days: {available_days}.",
        # plate_selection.create.* — K14
        "plate_selection.plate_id_required": "plate_id is required.",
        "plate_selection.plate_id_invalid": "Invalid plate_id format.",
        # plate_review.access.* — K14
        "plate_review.customer_only": "Customers cannot access institution reviews.",
        "plate_review.no_institution": "No institution assigned.",
        "plate_review.by_pickup_not_found": "Review not found for this pickup.",
        # ingredient.* — K14
        "ingredient.not_found": "Ingredient {ingredient_id} not found.",
        # plate_pickup.staff.* — K14
        "plate_pickup.staff_only": "Access restricted to restaurant staff.",
        "plate_pickup.invalid_user_id": "Invalid user ID format.",
        "plate_pickup.invalid_filter": "Invalid filter parameter.",
        # locale.* — K15
        "locale.unsupported": "Unsupported language '{lang}'. Supported: {supported}.",
        # address.* (business-logic) — K15
        "address.institution_required": "institution_id is required for B2B address creation.",
        "address.customer_institution_required": "Customer address requires institution context; missing institution_id on user.",
        "address.target_user_not_found": "Target user not found.",
        "address.user_institution_mismatch": "The user assigned to the address must belong to the same institution as the address.",
        "address.creation_failed": "Error creating address.",
        "address.invalid_country": "Invalid country_code. Market not found.",
        "address.not_found": "Address not found.",
        # address.* extended — K15
        "address.manual_entry_not_allowed": "Address creation via manual entry is only available in development. Use the address search for production.",
        "address.global_market_invalid": "Addresses cannot be registered to Global Marketplace. Please select a specific country.",
        "address.city_country_mismatch": "The city does not belong to the specified country. Resolve a city in the same country.",
        "address.place_details_failed": "Could not fetch address details for the selected place. Please try again or enter the address manually.",
        "address.outside_service_area": "Address is outside our service area.",
        "address.city_metadata_unresolvable": "Could not resolve a valid city for the provided location.",
        # workplace_group.* — K15
        "workplace_group.not_found": "Workplace group not found.",
        "workplace_group.creation_failed": "Failed to create workplace group.",
        "workplace_group.update_failed": "Failed to update workplace group.",
        "workplace_group.archive_failed": "Failed to archive workplace group.",
        # supplier_terms.* — K15
        "supplier_terms.access_denied": "Suppliers can only view their own supplier terms.",
        "supplier_terms.not_found": "Supplier terms not found for {scope}.",
        "supplier_terms.internal_only": "Only Internal users can list all supplier terms.",
        # webhook.* — K15
        "webhook.secret_not_configured": "Webhook secret not configured.",
        "webhook.invalid_payload": "Invalid webhook payload.",
        "webhook.invalid_signature": "Invalid webhook signature.",
        # payment_method.* — K15
        "payment_method.not_found": "Payment method not found.",
        "payment_method.access_denied": "You do not have access to this payment method.",
        "payment_method.setup_url_required": "success_url is required (request body or STRIPE_CUSTOMER_SETUP_SUCCESS_URL).",
        "payment_method.mock_only": "This operation is only available when PAYMENT_PROVIDER=mock.",
        "payment_method.provider_unavailable": "Payment setup is temporarily unavailable. Please try again.",
        # referral.* — K15
        "referral.code_invalid": "Invalid referral code.",
        "referral.code_not_found": "Referral code not found.",
        "referral.assignment_not_found": "No active referral code assignment found.",
        # email_change.* — K15
        "email_change.email_required": "Email is required.",
        "email_change.same_as_current": "New email must differ from your current email.",
        "email_change.already_taken": "This email is already registered to another account.",
        "email_change.pending_for_email": "Another verification is pending for this email address.",
        "email_change.code_expired": "Verification code has expired. Please request a new one.",
        "email_change.code_invalid": "Invalid verification code.",
        "email_change.user_not_found": "User not found.",
        # credit.* — K15
        "credit.amount_must_be_positive": "Credit amount must be positive.",
        "credit.currency_not_found": "Credit currency not found for this restaurant.",
        # checksum.* — K15
        "checksum.unsupported_algorithm": "Unsupported checksum algorithm: {algorithm}.",
        "checksum.mismatch": "Image checksum mismatch. Please re-upload the file.",
        # country.* — K15
        "country.invalid_code": "Invalid country_code.",
        # dev.* — K15
        "dev.mode_only": "This endpoint is only available in DEV_MODE.",
        # institution_entity.* (additional) — K15
        "institution_entity.no_markets": "Institution has no assigned markets.",
        "institution_entity.no_payout_aggregator": "No payout aggregator configured for this market.",
        "institution_entity.payout_setup_required": "Payout provider setup is required.",
        # qr_code.* — K15
        "qr_code.no_image": "QR code has no stored image.",
        # product_image.* — K15
        "product_image.empty": "Uploaded image is empty.",
        "product_image.format_invalid": "Invalid image format.",
        "product_image.checksum_mismatch": "Image checksum mismatch. Please re-upload the file.",
        "product_image.unreadable": "Unable to read image file.",
        # leads.* — K15
        "leads.country_code_required": "country_code is required.",
        "leads.email_required": "Valid email is required.",
        "leads.invalid_interest_type": "Invalid interest_type '{interest_type}'. Must be: customer, employer, or supplier.",
        "leads.invalid_restaurant_data": "Invalid restaurant lead data. Check referral_source and cuisine_ids.",
        # timezone.* — K15
        "timezone.country_code_required": "country_code is required for timezone deduction.",
        "timezone.not_found": "Timezone not found for the provided location.",
        # ad_zone.* extended — K15
        "ad_zone.invalid_flywheel_state": "Invalid flywheel state.",
        # coworker.* — K15
        "coworker.employer_required": "You must have an employer assigned to list coworkers.",
        "coworker.user_ineligible": "One or more users are not eligible coworkers for this plate selection.",
        # user.me.* — K15
        "user.use_me_endpoint": "Use the /me endpoint for your own profile.",
        # subscription.* — K15
        "subscription.creation_failed": "Failed to create subscription.",
        "subscription.payment_record_failed": "Failed to record subscription payment.",
        # plate_review.operation.* — K15
        "plate_review.creation_failed": "Failed to create plate review.",
        "plate_review.complaint_failed": "Failed to file portion complaint.",
        # plate_kitchen_days.* — K15
        "plate_kitchen_days.list_failed": "Failed to list plate kitchen days.",
        "plate_kitchen_days.enriched_list_failed": "Failed to get enriched plate kitchen days.",
        "plate_kitchen_days.enriched_get_failed": "Failed to get enriched plate kitchen day.",
        # national_holiday.* — K15
        "national_holiday.update_failed": "Failed to update national holiday.",
        "national_holiday.delete_failed": "Failed to delete national holiday.",
        # qr_code.* — K15
        "qr_code.list_failed": "Failed to retrieve QR codes.",
        "qr_code.get_failed": "Failed to retrieve QR code.",
        "qr_code.delete_failed": "Failed to delete QR code.",
        # restaurant_balance.* — #87-d (404 hijack sweep)
        "restaurant_balance.not_found": "Restaurant balance not found.",
        # restaurant_transaction.* — #87-d (404 hijack sweep)
        "restaurant_transaction.not_found": "Restaurant transaction not found.",
        # restaurant.* — K15
        "restaurant.creation_failed": "Failed to create restaurant.",
        "restaurant.balance_creation_failed": "Failed to create restaurant balance record.",
        "restaurant.list_failed": "Failed to retrieve restaurants.",
        "restaurant.cities_list_failed": "Failed to list cities with restaurants.",
        "restaurant.enriched_list_failed": "Failed to retrieve enriched restaurants.",
        "restaurant.enriched_get_failed": "Failed to retrieve enriched restaurant.",
        "restaurant.get_failed": "Failed to retrieve restaurant.",
        "restaurant.update_failed": "Failed to update restaurant.",
        "restaurant.delete_failed": "Failed to delete restaurant.",
        # restaurant_holiday.* — K15
        "restaurant_holiday.update_failed": "Failed to update restaurant holiday.",
        "restaurant_holiday.delete_failed": "Failed to delete restaurant holiday.",
        # plate_selection.* operation — K15
        "plate_selection.creation_failed": "Failed to create plate selection.",
        # enrollment.* extended — K15
        "enrollment.benefit_employee_creation_failed": "Failed to create benefit employee.",
        "enrollment.subscription_creation_failed": "Failed to create subscription for enrollment.",
        # employer.* extended — K15
        "employer.bill_creation_failed": "Failed to create employer bill.",
        "employer.benefits_program_creation_failed": "Failed to create benefits program.",
        # discretionary.* — K15
        "discretionary.request_creation_failed": "Failed to create discretionary request.",
        "discretionary.request_approval_failed": "Failed to approve discretionary request.",
        "discretionary.request_rejection_failed": "Failed to reject discretionary request.",
        "discretionary.list_failed": "Failed to retrieve discretionary requests.",
        "discretionary.transaction_creation_failed": "Failed to create discretionary transaction.",
        # credit.* extended — K15
        "credit.transaction_creation_failed": "Failed to create credit transaction.",
        "credit.validation_failed": "Error validating user credits. Please try again.",
        # currency_refresh.* — K15
        "currency_refresh.rate_unavailable": "Currency exchange rate not available.",
        # favorite.* — K15
        "favorite.entity_type_invalid": "Invalid entity type. Must be one of: plate, restaurant.",
        "favorite.not_found": "Entity not found.",
        "favorite.already_added": "Already added to favorites.",
        # notification.* — K15
        "notification.not_found": "Notification not found.",
        # billing.payout.* — K15
        "billing.payout_bill_not_pending": "Only pending bills can be paid out.",
        # plate_selection.* extended — K15
        "plate_selection.pickup_intent_invalid": "pickup_intent must be offer, request, or self.",
        # institution.* — K15
        "institution.restricted": "This institution cannot be assigned to a {context}. Use a Supplier institution.",
        # tax_id.* — K15
        "tax_id.format_invalid": "Invalid {label} format for {country_code}. Expected {digit_count} digits (e.g. {example}).",
        # api.* — K15
        "api.version_unsupported": "Unsupported API version: {version}.",
        # market.* extended — K15
        "market.global_entity_invalid": "Global Marketplace cannot be assigned to {entity_name}.",
        # ── K16: services sweep ───────────────────────────────────────────────
        # qr_code.* (operation failures) — K16
        "qr_code.create_failed": "Failed to create QR code.",
        "qr_code.update_failed": "Failed to update QR code status.",
        "qr_code.image_generation_failed": "Failed to generate QR code image.",
        "qr_code.image_not_found": "QR code image file not found on server.",
        "qr_code.image_load_failed": "Failed to load QR code image.",
        # product.* (operation failures) — K16
        "product.enriched_list_failed": "Failed to retrieve products.",
        "product.enriched_get_failed": "Failed to retrieve product.",
        "product.creation_failed": "Failed to create product.",
        "product.update_failed": "Failed to update product.",
        "product.image_update_failed": "Failed to update product image.",
        "product.image_revert_failed": "Failed to revert product image to placeholder.",
        # plan.* (operation failures) — K16
        "plan.enriched_list_failed": "Failed to retrieve plans.",
        "plan.enriched_get_failed": "Failed to retrieve plan.",
        # institution.* (operation failures) — K16
        "institution.creation_failed": "Failed to create institution.",
        "institution.update_failed": "Failed to update institution.",
        "institution.supplier_terms_creation_failed": "Failed to create supplier terms.",
        # ingredient.* (operation failures) — K16
        "ingredient.creation_failed": "Failed to create ingredient.",
        "ingredient.product_update_failed": "Failed to update product ingredients.",
        # notification.* (operation failures) — K16
        "notification.acknowledge_failed": "Failed to acknowledge notification.",
        # subscription.* (operation failures) — K16
        "subscription.renewal_update_failed": "Failed to update renewal preferences.",
        # user.* (service operation failures) — K16
        "user.get_failed": "Failed to retrieve user.",
        "user.creation_failed": "Failed to create user.",
        "user.list_failed": "Failed to retrieve users.",
        "user.enriched_get_failed": "Failed to retrieve user details.",
        "user.market_update_failed": "Failed to update market assignments.",
        # service.* (product/plate/bill/geolocation helpers) — K16
        "service.product_list_failed": "Failed to retrieve products.",
        "service.product_search_failed": "Failed to search products.",
        "service.plate_list_failed": "Failed to retrieve plates.",
        "service.bill_list_failed": "Failed to retrieve bills.",
        "service.geolocation_get_failed": "Failed to retrieve geolocation.",
    },
    "es": {
        # Auth / user errors
        "error.user_not_found": "Usuario no encontrado.",
        "error.duplicate_email": "Ya existe una cuenta con este correo electrónico.",
        "error.invalid_credentials": "Usuario o contraseña inválidos.",
        "error.email_change_code_expired": "El código de verificación ha expirado. Solicita uno nuevo.",
        "error.email_change_code_invalid": "Código de verificación inválido.",
        # Auth / user alerts
        "alert.email_verified": "Correo electrónico verificado exitosamente.",
        "alert.email_change_requested": "Se ha enviado un código de verificación a {email}.",
        # Entity CRUD errors
        "error.entity_not_found": "{entity} no encontrado/a",
        "error.entity_not_found_by_id": "{entity} con ID {id} no encontrado/a",
        "error.entity_creation_failed": "Error al crear {entity}",
        "error.entity_update_failed": "Error al actualizar {entity}",
        "error.entity_deletion_failed": "Error al eliminar {entity}",
        "error.entity_operation_failed": "{entity} no encontrado/a o la operación {operation} falló",
        # Database constraint errors
        "error.db_duplicate_key": "Ya existe un registro con este valor",
        "error.db_duplicate_email": "Ya existe un usuario con este correo electrónico",
        "error.db_duplicate_username": "Ya existe un usuario con este nombre de usuario",
        "error.db_duplicate_market": "Ya existe un mercado para este país",
        "error.db_duplicate_currency": "Ya existe una moneda con este código",
        "error.db_duplicate_institution": "Ya existe una institución con este nombre",
        "error.db_duplicate_restaurant": "Ya existe un restaurante con este nombre",
        "error.db_fk_user": "El usuario referenciado no existe",
        "error.db_fk_institution": "La institución referenciada no existe",
        "error.db_fk_currency": "La moneda referenciada no existe",
        "error.db_fk_subscription": "La suscripción referenciada no existe",
        "error.db_fk_plan": "El plan referenciado no existe",
        "error.db_fk_payment": "El intento de pago referenciado no existe",
        "error.db_fk_generic": "El registro referenciado no existe",
        "error.db_notnull_modified_by": "El campo modificado por es obligatorio",
        "error.db_notnull_currency_code": "El código de moneda es obligatorio",
        "error.db_notnull_currency_name": "El nombre de moneda es obligatorio",
        "error.db_notnull_username": "El nombre de usuario es obligatorio",
        "error.db_notnull_email": "El correo electrónico es obligatorio",
        "error.db_notnull_generic": "Falta un campo obligatorio",
        "error.db_check_violation": "Los datos proporcionados violan las reglas de negocio",
        "error.db_invalid_uuid": "Formato de UUID inválido",
        "error.db_invalid_format": "Formato de datos inválido",
        "error.db_generic": "Error de base de datos durante {operation}: {detail}",
        # Email subjects
        "email.subject_password_reset": "Restablece tu contraseña de Vianda",
        "email.subject_b2b_invite": "Has sido invitado a Vianda – Configura tu contraseña",
        "email.subject_benefit_invite": "{employer_name} ha configurado un beneficio de comidas Vianda para ti",
        "email.subject_email_change_verify": "Confirma tu nuevo correo para Vianda",
        "email.subject_email_change_confirm": "Tu correo de Vianda fue actualizado",
        "email.subject_username_recovery": "Tu nombre de usuario de Vianda",
        "email.subject_signup_verify": "Verifica tu correo para completar el registro",
        "email.subject_welcome": "¡Bienvenido a Vianda!",
        # Onboarding outreach
        "email.subject_onboarding_getting_started": "Bienvenido a Vianda — configuremos tu restaurante",
        "email.subject_onboarding_need_help": "¿Necesitas ayuda para completar tu configuración de Vianda?",
        "email.subject_onboarding_incomplete": "Tu configuración de Vianda está casi lista",
        "email.subject_onboarding_complete": "¡Tu restaurante ya está activo en Vianda!",
        # Customer engagement
        "email.subject_customer_subscribe": "Activa tu suscripción en Vianda",
        "email.subject_customer_missing_out": "Te estás perdiendo Vianda",
        "email.subject_benefit_waiting": "{employer_name} cubre tus comidas — actívalo ahora",
        "email.subject_benefit_reminder": "Tu beneficio de comidas de {employer_name} te está esperando",
        # Promotional
        "email.subject_subscription_promo": "Oferta especial: {promo_details}",
        # Rate limiting
        "error.rate_limit_exceeded": "Demasiadas solicitudes. Intenta de nuevo más tarde.",
        # ── ErrorCode registry keys (K2) ──────────────────────────────────
        # request.*
        "request.not_found": "El recurso solicitado no fue encontrado.",
        "request.method_not_allowed": "Este método HTTP no está permitido para este endpoint.",
        "request.malformed_body": "No se pudo interpretar el cuerpo de la solicitud.",
        "request.too_large": "El cuerpo de la solicitud es demasiado grande.",
        "request.rate_limited": "Demasiadas solicitudes. Intenta de nuevo en {retry_after_seconds} segundos.",
        # validation.*
        "validation.field_required": "Este campo es obligatorio.",
        "validation.invalid_format": "El valor tiene un formato inválido.",
        "validation.value_too_short": "El valor es demasiado corto.",
        "validation.value_too_long": "El valor es demasiado largo.",
        "validation.invalid_value": "El valor no es una de las opciones permitidas.",
        "validation.invalid_type": "El valor tiene un tipo inválido.",
        "validation.custom": "{msg}",
        # validation.user.*
        "validation.user.invalid_role_combination": "Combinación de roles inválida: {role_type} + {role_name}.",
        "validation.user.unsupported_locale": "Idioma no soportado '{requested}'. Debe ser uno de: {allowed}.",
        "validation.user.passwords_do_not_match": "La nueva contraseña y la confirmación no coinciden.",
        "validation.user.new_password_same_as_current": "La nueva contraseña debe ser diferente a la actual.",
        # validation.address.*
        "validation.address.city_required": "Se requiere city_metadata_id o city_name.",
        "validation.address.invalid_address_type": "Tipo de dirección inválido '{address_type}'.",
        "validation.address.duplicate_address_type": "El tipo de dirección no puede contener valores duplicados.",
        "validation.address.invalid_street_type": "Tipo de calle inválido '{street_type}'.",
        "validation.address.country_required": "Se debe proporcionar country_code, el nombre del país o place_id.",
        "validation.address.field_required": "El campo '{address_field}' es obligatorio cuando no se proporciona place_id.",
        "validation.address.city_metadata_id_required": "city_metadata_id es obligatorio cuando no se proporciona place_id.",
        # validation.plate.*
        "validation.plate.kitchen_days_empty": "kitchen_days no puede estar vacío.",
        "validation.plate.kitchen_days_duplicate": "kitchen_days no puede contener días duplicados.",
        # validation.discretionary.*
        "validation.discretionary.recipient_required": "Se debe proporcionar user_id o restaurant_id.",
        "validation.discretionary.conflicting_recipients": "No se puede especificar user_id y restaurant_id al mismo tiempo.",
        "validation.discretionary.restaurant_required": "Esta categoría requiere restaurant_id.",
        # validation.holiday.*
        "validation.holiday.recurring_fields_required": "Se requieren recurring_month y recurring_day cuando is_recurring es True.",
        "validation.holiday.list_empty": "Se debe proporcionar al menos un feriado.",
        # validation.subscription.*
        "validation.subscription.window_invalid": "hold_end_date debe ser posterior a hold_start_date.",
        "validation.subscription.window_too_long": "La duración de la pausa no puede superar los 3 meses.",
        # validation.payment.*
        "validation.payment.conflicting_address_fields": "No se puede proporcionar address_id y address_data al mismo tiempo.",
        "validation.payment.unsupported_brand": "El tipo de método de pago no está soportado.",
        "validation.payment.address_required": "El tipo de método de pago '{method_type}' requiere una dirección. Proporciona address_id o address_data.",
        # validation.supplier_invoice.* — K67
        "validation.supplier_invoice.cae_format": "El código CAE debe tener exactamente 14 dígitos.",
        "validation.supplier_invoice.cuit_format": "El CUIT debe tener el formato XX-XXXXXXXX-X.",
        "validation.supplier_invoice.afip_doc_type": "El tipo de documento AFIP debe ser uno de: A, B, C.",
        "validation.supplier_invoice.sunat_serie_format": "La serie SUNAT debe tener el formato F + 3 dígitos (p. ej. F001).",
        "validation.supplier_invoice.sunat_correlativo_format": "El correlativo SUNAT debe tener entre 1 y 8 dígitos.",
        "validation.supplier_invoice.ruc_format": "El RUC debe tener exactamente 11 dígitos.",
        "validation.supplier_invoice.cdr_status": "El estado CDR debe ser uno de: accepted, rejected, pending.",
        "validation.supplier_invoice.ar_details_required": "Las facturas AR requieren ar_details.",
        "validation.supplier_invoice.pe_details_required": "Las facturas PE requieren pe_details.",
        "validation.supplier_invoice.us_details_required": "Las facturas US requieren us_details.",
        "validation.supplier_invoice.rejection_reason_required": "rejection_reason es obligatorio al rechazar una factura.",
        "validation.supplier_invoice.status_cannot_reset": "No se puede volver a cambiar el estado de la factura a Pendiente de revisión.",
        "validation.supplier_invoice.w9_ein_format": "ein_last_four debe tener exactamente 4 dígitos.",
        # validation.market.* — K67
        "validation.market.language_unsupported": "Idioma no soportado '{language}'. Debe ser uno de: {allowed}.",
        # auth.* — K7
        "auth.invalid_token": "El token de autenticación es inválido o expiró.",
        "auth.captcha_required": "Se requiere verificación CAPTCHA.",
        "auth.captcha_verification_failed": "La verificación CAPTCHA falló.",
        "auth.captcha_action_mismatch": "La acción CAPTCHA no coincide.",
        "auth.captcha_score_too_low": "Puntuación CAPTCHA demasiado baja. Intenta de nuevo.",
        "auth.captcha_token_missing": "Falta el token reCAPTCHA.",
        "auth.credentials_invalid": "Usuario o contraseña inválidos.",
        "auth.account_inactive": "La cuenta no está activa. Contacta al soporte.",
        "auth.customer_app_only": "Las cuentas de cliente deben usar la aplicación móvil de Vianda.",
        "auth.dummy_admin_not_configured": "El usuario administrador de prueba no está configurado.",
        "auth.token_user_id_invalid": "Identificador de usuario inválido en el token.",
        "auth.token_institution_id_invalid": "Identificador de institución inválido en el token.",
        "auth.token_missing_fields": "El token no contiene los campos requeridos.",
        # security.* — K7
        "security.institution_mismatch": "Acceso denegado: institución no coincide.",
        "security.insufficient_permissions": "No tienes permiso para realizar esta acción.",
        "security.forbidden": "Acceso denegado.",
        "security.token_user_id_missing": "ID de usuario no encontrado en el token.",
        "security.token_user_id_invalid": "Formato de ID de usuario inválido en el token.",
        "security.address_type_not_allowed": "Tipo de dirección no permitido para tu rol.",
        "security.address_type_institution_mismatch": "El tipo de dirección no es compatible con este tipo de institución.",
        "security.user_role_type_not_allowed": "No puedes crear o actualizar usuarios con este tipo de rol.",
        "security.user_role_name_not_allowed": "No puedes asignar este nombre de rol.",
        "security.operator_cannot_create_users": "Los operadores no pueden crear ni editar cuentas de usuario.",
        "security.cannot_assign_role": "No tienes permiso para asignar este rol.",
        "security.cannot_edit_user": "No tienes permiso para editar este usuario.",
        "security.customer_cannot_edit_employer_address": "Los clientes no pueden editar ni eliminar direcciones del empleador.",
        "security.supplier_address_mutation_denied": "Los operadores de proveedor no pueden crear ni editar direcciones.",
        "security.supplier_user_mutation_denied": "Los operadores de proveedor no pueden crear ni editar usuarios.",
        "security.supplier_management_denied": "Los operadores de proveedor no pueden acceder a operaciones de gestión.",
        "security.supplier_admin_only": "Solo el administrador del proveedor puede acceder a este recurso.",
        "security.supplier_password_reset_denied": "Los operadores de proveedor no pueden restablecer contraseñas de otros usuarios.",
        "security.institution_type_mismatch": "El tipo de institución no coincide con el tipo de rol del usuario.",
        "security.supplier_institution_only": "Los proveedores solo pueden agregar usuarios a su propia institución.",
        "security.supplier_institution_required": "Tu cuenta no tiene ninguna institución configurada.",
        "security.employer_not_for_supplier": "El empleador no aplica a usuarios Proveedor, Interno o Empleador.",
        "security.supplier_terms_edit_denied": "Solo los usuarios internos autorizados pueden editar los términos del proveedor.",
        # subscription.*
        "subscription.already_active": "Esta suscripción ya está activa.",
        # entity.* — errores genéricos de entidades CRUD (K6)
        "entity.not_found": "{entity} no encontrado/a",
        "entity.not_found_or_operation_failed": "{entity} no encontrado/a o la operación {operation} falló",
        "entity.creation_failed": "Error al crear {entity}",
        "entity.update_failed": "Error al actualizar {entity}",
        "entity.deletion_failed": "Error al eliminar {entity}",
        # entity.* — códigos adicionales (K8)
        "entity.field_immutable": "El campo '{field}' no puede modificarse tras la creación.",
        # product.* — K8
        "product.image_too_large": "Imagen demasiado grande. El tamaño máximo es 5 MB.",
        # credit_currency.* — K8
        "credit_currency.name_not_supported": "Nombre de moneda no soportado. Usa GET /api/v1/currencies/ para ver la lista.",
        "credit_currency.rate_unavailable": "La moneda '{currency_code}' no está soportada por la API de tipos de cambio.",
        # employer.* — K8
        "employer.benefit_program_not_found": "No se encontró ningún programa de beneficios del empleador.",
        # user.* — K8
        "user.market_not_assigned": "El usuario no tiene un mercado asignado.",
        # institution.* — K8
        "institution.system_protected": "Las instituciones del sistema no pueden archivarse.",
        "institution.supplier_terms_invalid": "supplier_terms solo puede proporcionarse cuando institution_type es Proveedor.",
        # institution_entity.* — K8
        "institution_entity.market_mismatch": "El país de la dirección de la entidad no pertenece a los mercados asignados a la institución.",
        # user.signup.* / user.* — errores de identidad de usuario (K9)
        "user.city_not_found": "Ciudad no encontrada.",
        "user.city_archived": "La ciudad está archivada. Usa una ciudad activa.",
        "user.city_must_be_specific": "Los clientes deben tener una ciudad específica, no Global.",
        "user.city_required": "La ciudad es obligatoria y no puede eliminarse.",
        "user.city_country_mismatch": "La ciudad debe estar en el mismo país que tu mercado.",
        "user.market_not_found": "Mercado no encontrado.",
        "user.market_archived": "El mercado está archivado. Usa un mercado activo.",
        "user.market_global_not_allowed": "Solo Admin o Super Admin pueden asignar el mercado Global.",
        "user.market_id_invalid": "Identificador de mercado inválido.",
        "user.signup_code_invalid": "Código de verificación inválido o expirado.",
        "user.signup_country_required": "Se requiere country_code. Usa GET /api/v1/leads/markets para códigos válidos.",
        "user.signup_institution_required": "Se requiere institution_id para este tipo de usuario.",
        "user.lookup_param_required": "Se debe proporcionar al menos uno de los parámetros: username o email.",
        "user.address_not_found": "Dirección no encontrada.",
        "user.address_archived": "La dirección está archivada. Usa una dirección activa.",
        "user.address_institution_mismatch": "La dirección no pertenece al empleador especificado.",
        "user.workplace_group_not_found": "Grupo de trabajo no encontrado.",
        "user.workplace_group_archived": "El grupo de trabajo está archivado.",
        "user.invite_no_email": "El usuario no tiene dirección de correo electrónico. No se puede enviar la invitación.",
        "user.onboarding_customer_only": "El estado de incorporación solo está disponible para usuarios Cliente.",
        # server.* — error interno suprimido (K9, Decision F)
        "server.internal_error": "Ocurrió un error interno. Intenta de nuevo o contacta al soporte.",
        # subscription.* — errores de ciclo de vida (K10)
        "subscription.not_found": "Suscripción no encontrada.",
        "subscription.not_pending": "La suscripción no está en estado Pendiente.",
        "subscription.not_on_hold": "La suscripción no está en pausa.",
        "subscription.already_on_hold": "La suscripción ya está en pausa.",
        "subscription.already_cancelled": "La suscripción ya está cancelada.",
        "subscription.cannot_hold_cancelled": "No se puede pausar una suscripción cancelada.",
        "subscription.confirm_mock_only": "confirm-payment solo está disponible cuando PAYMENT_PROVIDER=mock. Usa el webhook de Stripe para pagos reales.",
        "subscription.payment_not_found": "No se encontró un pago pendiente para esta suscripción.",
        "subscription.payment_record_not_found": "No se encontró un registro de pago para esta suscripción.",
        "subscription.payment_provider_unavailable": "Los detalles de pago no están disponibles para este proveedor.",
        "subscription.access_denied": "No tienes acceso a esta suscripción.",
        # plate_selection.* — errores de ciclo de vida (K10)
        "plate_selection.not_found": "Selección de plato no encontrada.",
        "plate_selection.immutable_fields": "No se puede modificar {fields}. Solo pickup_time_range, pickup_intent y flexible_on_time son editables. Para cambiar el plato, cancela esta selección y crea una nueva.",
        "plate_selection.access_denied": "No estás autorizado para acceder a esta selección de plato.",
        "plate_selection.not_editable": "La selección de plato ya no es editable. Las ediciones se permiten hasta 1 hora antes de que abra el kitchen day.",
        "plate_selection.not_cancellable": "La selección de plato ya no es editable. La cancelación se permite hasta 1 hora antes de que abra el kitchen day.",
        "plate_selection.duplicate_kitchen_day": "Ya tienes un plato reservado para {kitchen_day}. ¿Deseas cancelar tu comida actual y reservar este plato?",
        # plate_pickup.* — errores (K10)
        "plate_pickup.access_denied": "No estás autorizado para acceder a este registro de recogida.",
        "plate_pickup.invalid_qr_code": "Este código QR no es reconocido.",
        "plate_pickup.wrong_restaurant": "Escaneaste el código QR de un restaurante incorrecto.",
        "plate_pickup.no_active_reservation": "No se encontró una reserva activa para este restaurante.",
        "plate_pickup.invalid_status": "No se puede realizar esta acción con el estado de recogida actual.",
        "plate_pickup.invalid_signature": "Firma de código QR inválida.",
        "plate_pickup.cannot_delete": "No se puede eliminar el registro de recogida con estado {pickup_status}. Solo se pueden eliminar pedidos pendientes.",
        # plate_review.* — errores (K10)
        "plate_review.not_found": "Recogida no encontrada.",
        "plate_review.access_denied": "Esta recogida no te pertenece.",
        "plate_review.not_eligible": "Solo puedes reseñar platos que hayas recogido. Completa la recogida primero.",
        "plate_review.pickup_archived": "No se puede reseñar una recogida archivada.",
        "plate_review.already_exists": "Esta recogida ya fue reseñada. Las reseñas son inmutables.",
        "plate_review.invalid_portion_rating": "Las quejas de porción solo se pueden presentar para reseñas con calificación de porción 1 (pequeña).",
        "plate_review.complaint_exists": "Ya se presentó una queja de porción para esta reseña.",
        # payment_provider.* — errores de Stripe Connect (K10)
        "payment_provider.onboarding_required": "La entidad no tiene cuenta de proveedor de pagos. Completa el registro primero.",
        "payment_provider.not_ready": "La cuenta Stripe Connect aún no está habilitada para pagos. El proveedor debe completar el registro.",
        "payment_provider.payout_exists": "Ya existe un pago para esta factura con estado '{payout_status}'.",
        "payment_provider.unavailable": "El proveedor de pagos no está disponible temporalmente.",
        "payment_provider.rate_limited": "Límite de solicitudes del proveedor de pagos excedido.",
        "payment_provider.auth_failed": "Error de autenticación con el proveedor de pagos.",
        "payment_provider.error": "Error del proveedor de pagos.",
        "payment_provider.bill_not_pending": "La resolución de la factura es '{resolution}'; solo se pueden pagar facturas pendientes.",
        # mercado_pago.* — errores de OAuth (K10)
        "mercado_pago.auth_code_missing": "Falta el código de autorización.",
        "mercado_pago.auth_failed": "La autorización de Mercado Pago falló.",
        # database.* — errores de violación de restricciones (K6)
        "database.duplicate_key": "Ya existe un registro con este valor.",
        "database.duplicate_email": "Ya existe un usuario con este correo electrónico.",
        "database.duplicate_username": "Ya existe un usuario con este nombre de usuario.",
        "database.duplicate_market": "Ya existe un mercado para este país.",
        "database.duplicate_currency": "Ya existe una moneda con este código.",
        "database.duplicate_institution": "Ya existe una institución con este nombre.",
        "database.duplicate_restaurant": "Ya existe un restaurante con este nombre.",
        "database.foreign_key_user": "El usuario referenciado no existe.",
        "database.foreign_key_institution": "La institución referenciada no existe.",
        "database.foreign_key_currency": "La moneda referenciada no existe.",
        "database.foreign_key_subscription": "La suscripción referenciada no existe.",
        "database.foreign_key_plan": "El plan referenciado no existe.",
        "database.foreign_key_payment": "El intento de pago referenciado no existe.",
        "database.foreign_key_violation": "El registro referenciado no existe.",
        "database.not_null_modified_by": "El campo modificado por es obligatorio.",
        "database.not_null_currency_code": "El código de moneda es obligatorio.",
        "database.not_null_currency_name": "El nombre de moneda es obligatorio.",
        "database.not_null_username": "El nombre de usuario es obligatorio.",
        "database.not_null_email": "El correo electrónico es obligatorio.",
        "database.not_null_violation": "Falta un campo obligatorio.",
        "database.check_violation": "Los datos proporcionados violan las reglas de negocio.",
        "database.invalid_uuid": "Formato de UUID inválido.",
        "database.invalid_format": "Formato de datos inválido.",
        "database.error": "Error de base de datos durante {operation}: {detail}",
        # restaurant.* — errores de gestión de restaurantes (K11)
        "restaurant.not_found": "Restaurante no encontrado.",
        "restaurant.entity_id_required": "Se requiere institution_entity_id.",
        "restaurant.market_required": "Se requiere un mercado. Envía market_id o asegúrate de que el usuario tenga un mercado principal.",
        "restaurant.market_access_denied": "market_id debe ser uno de tus mercados asignados.",
        "restaurant.active_requires_setup": "No se puede activar el restaurante. Debe tener al menos un plato con plate_kitchen_days activos y al menos un código QR activo. Agrega plate_kitchen_days y crea un código QR.",
        "restaurant.active_requires_plate_days": "No se puede activar el restaurante. Debe tener al menos un plato con plate_kitchen_days activos.",
        "restaurant.active_requires_qr": "No se puede activar el restaurante. Debe tener al menos un código QR activo. Crea un código QR para este restaurante.",
        "restaurant.active_requires_entity_payouts": "No se puede activar el restaurante: la entidad institucional vinculada no ha completado Stripe Connect. Completa el proceso de pago para la entidad e inténtalo de nuevo.",
        # restaurant_holiday.* — K11
        "restaurant_holiday.not_found": "Feriado de restaurante no encontrado.",
        "restaurant_holiday.duplicate": "El restaurante ya tiene un feriado registrado para {holiday_date}.",
        "restaurant_holiday.on_national_holiday": "La fecha {holiday_date} ya es un feriado nacional. Los restaurantes no pueden registrar feriados en fechas de feriados nacionales.",
        # national_holiday.* — K11
        "national_holiday.not_found": "Feriado nacional no encontrado.",
        "national_holiday.update_empty": "No se proporcionaron campos para actualizar.",
        # push.* — FCM notification copy (K4)
        "push.pickup_ready_title": "Plato listo",
        "push.pickup_ready_body": "¿Recibiste tu plato de {restaurant_name}?",
        # market.* — K12
        "market.not_found": "Mercado no encontrado.",
        "market.country_not_supported": "País no soportado para nuevos mercados. Usa GET /api/v1/countries/ para la lista de países soportados.",
        "market.super_admin_only": "Solo el Super Admin puede realizar esta acción en el Mercado Global.",
        "market.no_coverage_to_activate": "No se puede activar: el mercado no tiene un restaurante activo con un plato activo en un día de cocina semanal activo. Programa la cobertura primero y luego establece el estado como activo.",
        "market.has_coverage_confirm_deactivate": "Este mercado actualmente tiene cobertura activa de platos. Desactivarlo lo ocultará a los clientes inmediatamente. Reenvía con confirm_deactivate=true para continuar.",
        "market.global_cannot_be_archived": "El Mercado Global no puede ser archivado.",
        "market.billing_config_not_found": "No se encontró configuración de facturación para este mercado.",
        # ad_zone.* — K12
        "ad_zone.not_found": "Zona publicitaria no encontrada.",
        # cuisine.* — K12
        "cuisine.not_found": "Tipo de cocina no encontrado.",
        "cuisine.suggestion_not_found": "Sugerencia no encontrada o ya revisada.",
        # archival.* — K12
        "archival.no_records_provided": "No se proporcionaron IDs de registros.",
        "archival.too_many_records": "No se pueden archivar más de 1000 registros a la vez.",
        "archival_config.not_found": "Configuración de archivado no encontrada.",
        "archival_config.already_exists": "Ya existe una configuración para la tabla {table_name}.",
        # referral_config.* — K12
        "referral_config.not_found": "Configuración de referidos no encontrada para este mercado.",
        # supplier_invoice.* — K12
        "supplier_invoice.not_found": "Factura de proveedor no encontrada.",
        "supplier_invoice.invalid_status": "No se puede revisar la factura con estado '{invoice_status}'. Debe estar en 'pending_review'.",
        # billing.* — K12
        "billing.bill_not_found": "Factura no encontrada.",
        "billing.bill_already_paid": "No se puede cancelar una factura pagada.",
        "billing.bill_already_cancelled": "La factura ya está cancelada.",
        "billing.plan_no_credits": "El plan no tiene créditos; no se puede procesar.",
        "billing.no_data_found": "No se encontraron datos de facturación para esta institución.",
        # discretionary.* — K12
        "discretionary.not_found": "Solicitud discrecional no encontrada.",
        "discretionary.not_pending": "No se puede actualizar la solicitud con estado: {request_status}.",
        # discretionary.* — K13
        "discretionary.recipient_institution_mismatch": "El destinatario seleccionado no pertenece a la institución especificada.",
        "discretionary.recipient_market_mismatch": "El destinatario seleccionado no pertenece al mercado especificado.",
        "discretionary.invalid_amount": "El monto debe ser mayor que 0.",
        "discretionary.invalid_category": "Valor de categoría inválido: {category}.",
        "discretionary.category_requires_restaurant": "La categoría '{category}' requiere que se especifique restaurant_id.",
        # enrollment.* — K13
        "enrollment.no_active_program": "No hay un programa de beneficios activo para esta institución.",
        "enrollment.email_already_registered": "El correo electrónico ya está registrado en el sistema.",
        "enrollment.city_no_market": "Ciudad no encontrada o sin mercado activo.",
        "enrollment.employer_institution_id_required": "Los usuarios internos deben proporcionar el parámetro institution_id para especificar en qué institución Empleador operar.",
        "enrollment.partial_subsidy_requires_app": "Este beneficio cubre solo parte del precio del plan. El empleado debe suscribirse a través de la aplicación Vianda para pagar su parte.",
        # employer.program.* — K13
        "employer.program_already_exists": "Ya existe un programa de beneficios para este {scope}.",
        # user.market.* — K14
        "user.market_ids_empty": "market_ids debe contener al menos un mercado.",
        "user.market_ids_invalid": "market_id(s) inválido(s) o archivado(s): {market_ids}.",
        "user.market_not_in_institution": "El mercado {market_id} no está asignado a la institución del usuario.",
        "user.duplicate_username": "El nombre de usuario ya existe.",
        "user.duplicate_email_in_system": "El correo electrónico ya existe.",
        # entity.archive.* — K14
        "entity.search_invalid_param": "search_by debe ser uno de: {allowed}.",
        "entity.archive_active_pickups": "No se puede archivar la entidad: existen {count} recogida(s) activa(s). Completa o cancélalas primero.",
        "entity.archive_active_restaurants": "No se puede archivar la entidad: {count} restaurante(s) activo(s) debe(n) archivarse primero: {names}.",
        "restaurant.archive_active_pickups": "No se puede archivar el restaurante: existen {count} recogida(s) activa(s). Completa o cancélalas primero.",
        # plate_kitchen_day.* — K14
        "plate_kitchen_day.not_found": "Día de cocina del plato no encontrado.",
        "plate_kitchen_day.duplicate": "El plato {plate_id} ya está asignado a {kitchen_day}.",
        "plate_kitchen_day.plate_id_immutable": "plate_id no puede modificarse en un día de cocina existente; crea un nuevo registro y archiva el anterior.",
        "plate_kitchen_day.archive_failed": "Error al archivar el día de cocina del plato.",
        "plate_kitchen_day.update_failed": "Error al actualizar el día de cocina del plato.",
        "plate_kitchen_day.delete_failed": "Error al eliminar el día de cocina del plato.",
        # restaurant.status.* — K14
        "restaurant.archived": "El restaurante '{name}' está archivado y no puede aceptar nuevos pedidos.",
        "restaurant.entity_archived": "El restaurante '{name}' pertenece a una entidad archivada y no puede aceptar nuevos pedidos.",
        "restaurant.unavailable": "El restaurante '{name}' {status_message} y no puede aceptar nuevos pedidos. Por favor intenta con otro restaurante.",
        "restaurant.national_holiday": "El restaurante '{name}' no puede aceptar pedidos el {date} debido a un feriado nacional. Por favor selecciona otra fecha.",
        "restaurant.restaurant_holiday": "El restaurante '{name}' está cerrado el {date} por feriado del restaurante. Por favor selecciona otra fecha.",
        # plate_selection.window.* — K14
        "plate_selection.pickup_time_required": "pickup_time_range es obligatorio y debe estar en formato HH:MM-HH:MM (ej. 11:30-11:45).",
        "plate_selection.no_pickup_windows": "No hay ventanas de recogida disponibles para {kitchen_day} en este mercado. Por favor selecciona otro día.",
        "plate_selection.invalid_pickup_window": "pickup_time_range '{pickup_time_range}' no es una ventana de recogida válida para {kitchen_day}. Ventanas permitidas: {allowed_windows}.",
        "plate_selection.kitchen_day_invalid": "La cocina no opera el {kitchen_day}. Días disponibles: {available_days}.",
        "plate_selection.kitchen_day_not_available": "El plato no está disponible el {kitchen_day}. Días disponibles: {available_days}.",
        "plate_selection.kitchen_day_too_far": "No se puede pedir para {kitchen_day} desde {current_day}. Los pedidos solo se permiten con hasta 1 semana de anticipación.",
        "plate_selection.no_kitchen_days": "No se encontraron días de cocina disponibles en la próxima semana. Días disponibles: {available_days}.",
        # plate_selection.create.* — K14
        "plate_selection.plate_id_required": "plate_id es obligatorio.",
        "plate_selection.plate_id_invalid": "Formato de plate_id inválido.",
        # plate_review.access.* — K14
        "plate_review.customer_only": "Los clientes no pueden acceder a las reseñas de la institución.",
        "plate_review.no_institution": "No hay institución asignada.",
        "plate_review.by_pickup_not_found": "Reseña no encontrada para esta recogida.",
        # ingredient.* — K14
        "ingredient.not_found": "Ingrediente {ingredient_id} no encontrado.",
        # plate_pickup.staff.* — K14
        "plate_pickup.staff_only": "Acceso restringido al personal del restaurante.",
        "plate_pickup.invalid_user_id": "Formato de ID de usuario inválido.",
        "plate_pickup.invalid_filter": "Parámetro de filtro inválido.",
        # locale.* — K15
        "locale.unsupported": "Idioma no soportado '{locale}'. Soportados: {supported}.",
        # address.* (business-logic) — K15
        "address.institution_required": "Se requiere institution_id para la creación de direcciones B2B.",
        "address.customer_institution_required": "La dirección del cliente requiere contexto de institución; falta institution_id en el usuario.",
        "address.target_user_not_found": "Usuario objetivo no encontrado.",
        "address.user_institution_mismatch": "El usuario asignado a la dirección debe pertenecer a la misma institución que la dirección.",
        "address.creation_failed": "Error al crear la dirección.",
        "address.invalid_country": "Código de país inválido. Mercado no encontrado.",
        "address.not_found": "Dirección no encontrada.",
        # address.* extended — K15
        "address.manual_entry_not_allowed": "La creación de dirección por entrada manual solo está disponible en desarrollo. Use la búsqueda de dirección para producción.",
        "address.global_market_invalid": "Las direcciones no pueden registrarse en el Marketplace Global. Por favor seleccione un país específico.",
        "address.city_country_mismatch": "La ciudad no pertenece al país especificado. Resuelva una ciudad del mismo país.",
        "address.place_details_failed": "No se pudieron obtener los detalles de la dirección seleccionada. Intente nuevamente o ingrese la dirección manualmente.",
        "address.outside_service_area": "La dirección está fuera de nuestra área de servicio.",
        "address.city_metadata_unresolvable": "No se pudo resolver una ciudad válida para la ubicación proporcionada.",
        # workplace_group.* — K15
        "workplace_group.not_found": "Grupo de trabajo no encontrado.",
        "workplace_group.creation_failed": "Error al crear el grupo de trabajo.",
        "workplace_group.update_failed": "Error al actualizar el grupo de trabajo.",
        "workplace_group.archive_failed": "Error al archivar el grupo de trabajo.",
        # supplier_terms.* — K15
        "supplier_terms.access_denied": "Los proveedores solo pueden ver sus propios términos de proveedor.",
        "supplier_terms.not_found": "Términos de proveedor no encontrados para {scope}.",
        "supplier_terms.internal_only": "Solo los usuarios internos pueden listar todos los términos de proveedor.",
        # webhook.* — K15
        "webhook.secret_not_configured": "El secreto del webhook no está configurado.",
        "webhook.invalid_payload": "Payload del webhook inválido.",
        "webhook.invalid_signature": "Firma del webhook inválida.",
        # payment_method.* — K15
        "payment_method.not_found": "Método de pago no encontrado.",
        "payment_method.access_denied": "No tienes acceso a este método de pago.",
        "payment_method.setup_url_required": "Se requiere success_url (cuerpo de la solicitud o STRIPE_CUSTOMER_SETUP_SUCCESS_URL).",
        "payment_method.mock_only": "Esta operación solo está disponible cuando PAYMENT_PROVIDER=mock.",
        "payment_method.provider_unavailable": "La configuración de pagos no está disponible temporalmente. Inténtalo de nuevo.",
        # referral.* — K15
        "referral.code_invalid": "Código de referido inválido.",
        "referral.code_not_found": "Código de referido no encontrado.",
        "referral.assignment_not_found": "No se encontró ninguna asignación de código de referido activa.",
        # email_change.* — K15
        "email_change.email_required": "El correo electrónico es obligatorio.",
        "email_change.same_as_current": "El nuevo correo debe ser diferente al actual.",
        "email_change.already_taken": "Este correo ya está registrado en otra cuenta.",
        "email_change.pending_for_email": "Hay otra verificación pendiente para esta dirección de correo.",
        "email_change.code_expired": "El código de verificación ha expirado. Solicita uno nuevo.",
        "email_change.code_invalid": "Código de verificación inválido.",
        "email_change.user_not_found": "Usuario no encontrado.",
        # credit.* — K15
        "credit.amount_must_be_positive": "El monto de crédito debe ser positivo.",
        "credit.currency_not_found": "Moneda de crédito no encontrada para este restaurante.",
        # checksum.* — K15
        "checksum.unsupported_algorithm": "Algoritmo de checksum no soportado: {algorithm}.",
        "checksum.mismatch": "El checksum de la imagen no coincide. Por favor sube el archivo de nuevo.",
        # country.* — K15
        "country.invalid_code": "Código de país inválido.",
        # dev.* — K15
        "dev.mode_only": "Este endpoint solo está disponible en modo DEV.",
        # institution_entity.* (additional) — K15
        "institution_entity.no_markets": "La institución no tiene mercados asignados.",
        "institution_entity.no_payout_aggregator": "No hay agregador de pagos configurado para este mercado.",
        "institution_entity.payout_setup_required": "Se requiere configuración del proveedor de pagos.",
        # qr_code.* — K15
        "qr_code.no_image": "El código QR no tiene imagen almacenada.",
        # product_image.* — K15
        "product_image.empty": "La imagen subida está vacía.",
        "product_image.format_invalid": "Formato de imagen inválido.",
        "product_image.checksum_mismatch": "El checksum de la imagen no coincide. Por favor sube el archivo de nuevo.",
        "product_image.unreadable": "No se puede leer el archivo de imagen.",
        # leads.* — K15
        "leads.country_code_required": "Se requiere country_code.",
        "leads.email_required": "Se requiere un correo electrónico válido.",
        "leads.invalid_interest_type": "Tipo de interés inválido '{interest_type}'. Debe ser: customer, employer o supplier.",
        "leads.invalid_restaurant_data": "Datos de restaurante inválidos. Verifica referral_source y cuisine_ids.",
        # timezone.* — K15
        "timezone.country_code_required": "Se requiere country_code para deducir la zona horaria.",
        "timezone.not_found": "Zona horaria no encontrada para la ubicación proporcionada.",
        # ad_zone.* extended — K15
        "ad_zone.invalid_flywheel_state": "Estado de flywheel inválido.",
        # coworker.* — K15
        "coworker.employer_required": "Debes tener un empleador asignado para listar compañeros de trabajo.",
        "coworker.user_ineligible": "Uno o más usuarios no son compañeros de trabajo elegibles para esta selección de plato.",
        # user.me.* — K15
        "user.use_me_endpoint": "Usa el endpoint /me para tu propio perfil.",
        # subscription.* — K15
        "subscription.creation_failed": "No se pudo crear la suscripción.",
        "subscription.payment_record_failed": "No se pudo registrar el pago de suscripción.",
        # plate_review.operation.* — K15
        "plate_review.creation_failed": "No se pudo crear la reseña del plato.",
        "plate_review.complaint_failed": "No se pudo registrar la queja de porción.",
        # plate_kitchen_days.* — K15
        "plate_kitchen_days.list_failed": "Error al listar los días de cocina.",
        "plate_kitchen_days.enriched_list_failed": "Error al obtener los días de cocina enriquecidos.",
        "plate_kitchen_days.enriched_get_failed": "Error al obtener el día de cocina enriquecido.",
        # national_holiday.* — K15
        "national_holiday.update_failed": "No se pudo actualizar el feriado nacional.",
        "national_holiday.delete_failed": "No se pudo eliminar el feriado nacional.",
        # qr_code.* — K15
        "qr_code.list_failed": "Error al obtener los códigos QR.",
        "qr_code.get_failed": "Error al obtener el código QR.",
        "qr_code.delete_failed": "Error al eliminar el código QR.",
        # restaurant_balance.* — #87-d (404 hijack sweep)
        "restaurant_balance.not_found": "Saldo de restaurante no encontrado.",
        # restaurant_transaction.* — #87-d (404 hijack sweep)
        "restaurant_transaction.not_found": "Transacción de restaurante no encontrada.",
        # restaurant.* — K15
        "restaurant.creation_failed": "No se pudo crear el restaurante.",
        "restaurant.balance_creation_failed": "No se pudo crear el registro de saldo del restaurante.",
        "restaurant.list_failed": "Error al obtener los restaurantes.",
        "restaurant.cities_list_failed": "Error al listar las ciudades con restaurantes.",
        "restaurant.enriched_list_failed": "Error al obtener los restaurantes enriquecidos.",
        "restaurant.enriched_get_failed": "Error al obtener el restaurante enriquecido.",
        "restaurant.get_failed": "Error al obtener el restaurante.",
        "restaurant.update_failed": "No se pudo actualizar el restaurante.",
        "restaurant.delete_failed": "No se pudo eliminar el restaurante.",
        # restaurant_holiday.* — K15
        "restaurant_holiday.update_failed": "No se pudo actualizar el feriado del restaurante.",
        "restaurant_holiday.delete_failed": "No se pudo eliminar el feriado del restaurante.",
        # plate_selection.* operation — K15
        "plate_selection.creation_failed": "No se pudo crear la selección de plato.",
        # enrollment.* extended — K15
        "enrollment.benefit_employee_creation_failed": "No se pudo crear el empleado beneficiario.",
        "enrollment.subscription_creation_failed": "No se pudo crear la suscripción para la inscripción.",
        # employer.* extended — K15
        "employer.bill_creation_failed": "No se pudo crear la factura del empleador.",
        "employer.benefits_program_creation_failed": "No se pudo crear el programa de beneficios.",
        # discretionary.* — K15
        "discretionary.request_creation_failed": "No se pudo crear la solicitud discrecional.",
        "discretionary.request_approval_failed": "No se pudo aprobar la solicitud discrecional.",
        "discretionary.request_rejection_failed": "No se pudo rechazar la solicitud discrecional.",
        "discretionary.list_failed": "Error al obtener las solicitudes discrecionales.",
        "discretionary.transaction_creation_failed": "No se pudo crear la transacción discrecional.",
        # credit.* extended — K15
        "credit.transaction_creation_failed": "No se pudo crear la transacción de crédito.",
        "credit.validation_failed": "Error al validar los créditos del usuario. Por favor intente de nuevo.",
        # currency_refresh.* — K15
        "currency_refresh.rate_unavailable": "Tipo de cambio de moneda no disponible.",
        # favorite.* — K15
        "favorite.entity_type_invalid": "Tipo de entidad inválido. Debe ser: plate o restaurant.",
        "favorite.not_found": "Entidad no encontrada.",
        "favorite.already_added": "Ya está en favoritos.",
        # notification.* — K15
        "notification.not_found": "Notificación no encontrada.",
        # billing.payout.* — K15
        "billing.payout_bill_not_pending": "Solo las facturas pendientes pueden ser pagadas.",
        # plate_selection.* extended — K15
        "plate_selection.pickup_intent_invalid": "pickup_intent debe ser offer, request o self.",
        # institution.* — K15
        "institution.restricted": "Esta institución no puede asignarse a un {context}. Usa una institución Supplier.",
        # tax_id.* — K15
        "tax_id.format_invalid": "Formato de {label} inválido para {country_code}. Se esperan {digit_count} dígitos (ej. {example}).",
        # api.* — K15
        "api.version_unsupported": "Versión de API no soportada: {version}.",
        # market.* extended — K15
        "market.global_entity_invalid": "El Mercado Global no puede asignarse a {entity_name}.",
        # ── K16: services sweep ───────────────────────────────────────────────
        # qr_code.* (operation failures) — K16
        "qr_code.create_failed": "Error al crear el código QR.",
        "qr_code.update_failed": "Error al actualizar el estado del código QR.",
        "qr_code.image_generation_failed": "Error al generar la imagen del código QR.",
        "qr_code.image_not_found": "Archivo de imagen del código QR no encontrado en el servidor.",
        "qr_code.image_load_failed": "Error al cargar la imagen del código QR.",
        # product.* (operation failures) — K16
        "product.enriched_list_failed": "Error al obtener los productos.",
        "product.enriched_get_failed": "Error al obtener el producto.",
        "product.creation_failed": "Error al crear el producto.",
        "product.update_failed": "Error al actualizar el producto.",
        "product.image_update_failed": "Error al actualizar la imagen del producto.",
        "product.image_revert_failed": "Error al revertir la imagen del producto al marcador de posición.",
        # plan.* (operation failures) — K16
        "plan.enriched_list_failed": "Error al obtener los planes.",
        "plan.enriched_get_failed": "Error al obtener el plan.",
        # institution.* (operation failures) — K16
        "institution.creation_failed": "Error al crear la institución.",
        "institution.update_failed": "Error al actualizar la institución.",
        "institution.supplier_terms_creation_failed": "Error al crear los términos de proveedor.",
        # ingredient.* (operation failures) — K16
        "ingredient.creation_failed": "Error al crear el ingrediente.",
        "ingredient.product_update_failed": "Error al actualizar los ingredientes del producto.",
        # notification.* (operation failures) — K16
        "notification.acknowledge_failed": "Error al confirmar la notificación.",
        # subscription.* (operation failures) — K16
        "subscription.renewal_update_failed": "Error al actualizar las preferencias de renovación.",
        # user.* (service operation failures) — K16
        "user.get_failed": "Error al obtener el usuario.",
        "user.creation_failed": "Error al crear el usuario.",
        "user.list_failed": "Error al obtener los usuarios.",
        "user.enriched_get_failed": "Error al obtener los detalles del usuario.",
        "user.market_update_failed": "Error al actualizar las asignaciones de mercado.",
        # service.* (product/plate/bill/geolocation helpers) — K16
        "service.product_list_failed": "Error al obtener los productos.",
        "service.product_search_failed": "Error al buscar productos.",
        "service.plate_list_failed": "Error al obtener los platos.",
        "service.bill_list_failed": "Error al obtener las facturas.",
        "service.geolocation_get_failed": "Error al obtener la geolocalización.",
    },
    "pt": {
        # Auth / user errors
        "error.user_not_found": "Usuário não encontrado.",
        "error.duplicate_email": "Já existe uma conta com este e-mail.",
        "error.invalid_credentials": "Usuário ou senha inválidos.",
        "error.email_change_code_expired": "O código de verificação expirou. Solicite um novo.",
        "error.email_change_code_invalid": "Código de verificação inválido.",
        # Auth / user alerts
        "alert.email_verified": "E-mail verificado com sucesso.",
        "alert.email_change_requested": "Um código de verificação foi enviado para {email}.",
        # Entity CRUD errors
        "error.entity_not_found": "{entity} não encontrado/a",
        "error.entity_not_found_by_id": "{entity} com ID {id} não encontrado/a",
        "error.entity_creation_failed": "Falha ao criar {entity}",
        "error.entity_update_failed": "Falha ao atualizar {entity}",
        "error.entity_deletion_failed": "Falha ao excluir {entity}",
        "error.entity_operation_failed": "{entity} não encontrado/a ou a operação {operation} falhou",
        # Database constraint errors
        "error.db_duplicate_key": "Já existe um registro com este valor",
        "error.db_duplicate_email": "Já existe um usuário com este e-mail",
        "error.db_duplicate_username": "Já existe um usuário com este nome de usuário",
        "error.db_duplicate_market": "Já existe um mercado para este país",
        "error.db_duplicate_currency": "Já existe uma moeda com este código",
        "error.db_duplicate_institution": "Já existe uma instituição com este nome",
        "error.db_duplicate_restaurant": "Já existe um restaurante com este nome",
        "error.db_fk_user": "O usuário referenciado não existe",
        "error.db_fk_institution": "A instituição referenciada não existe",
        "error.db_fk_currency": "A moeda referenciada não existe",
        "error.db_fk_subscription": "A assinatura referenciada não existe",
        "error.db_fk_plan": "O plano referenciado não existe",
        "error.db_fk_payment": "A tentativa de pagamento referenciada não existe",
        "error.db_fk_generic": "O registro referenciado não existe",
        "error.db_notnull_modified_by": "O campo modificado por é obrigatório",
        "error.db_notnull_currency_code": "O código da moeda é obrigatório",
        "error.db_notnull_currency_name": "O nome da moeda é obrigatório",
        "error.db_notnull_username": "O nome de usuário é obrigatório",
        "error.db_notnull_email": "O e-mail é obrigatório",
        "error.db_notnull_generic": "Campo obrigatório ausente",
        "error.db_check_violation": "Os dados fornecidos violam regras de negócio",
        "error.db_invalid_uuid": "Formato de UUID inválido",
        "error.db_invalid_format": "Formato de dados inválido",
        "error.db_generic": "Erro de banco de dados durante {operation}: {detail}",
        # Email subjects
        "email.subject_password_reset": "Redefina sua senha da Vianda",
        "email.subject_b2b_invite": "Você foi convidado para a Vianda – Configure sua senha",
        "email.subject_benefit_invite": "{employer_name} configurou um benefício de refeições Vianda para você",
        "email.subject_email_change_verify": "Confirme seu novo e-mail para a Vianda",
        "email.subject_email_change_confirm": "Seu e-mail da Vianda foi atualizado",
        "email.subject_username_recovery": "Seu nome de usuário da Vianda",
        "email.subject_signup_verify": "Verifique seu e-mail para completar o cadastro",
        "email.subject_welcome": "Bem-vindo à Vianda!",
        # Onboarding outreach
        "email.subject_onboarding_getting_started": "Bem-vindo à Vianda — vamos configurar seu restaurante",
        "email.subject_onboarding_need_help": "Precisa de ajuda para concluir sua configuração na Vianda?",
        "email.subject_onboarding_incomplete": "Sua configuração na Vianda está quase pronta",
        "email.subject_onboarding_complete": "Seu restaurante está ativo na Vianda!",
        # Customer engagement
        "email.subject_customer_subscribe": "Ative sua assinatura na Vianda",
        "email.subject_customer_missing_out": "Você está perdendo a Vianda",
        "email.subject_benefit_waiting": "{employer_name} está cobrindo suas refeições — ative agora",
        "email.subject_benefit_reminder": "Seu benefício de refeições de {employer_name} ainda está esperando",
        # Promotional
        "email.subject_subscription_promo": "Oferta especial: {promo_details}",
        # Rate limiting
        "error.rate_limit_exceeded": "Muitas solicitações. Tente novamente mais tarde.",
        # ── ErrorCode registry keys (K2) ──────────────────────────────────
        # request.*
        "request.not_found": "O recurso solicitado não foi encontrado.",
        "request.method_not_allowed": "Este método HTTP não é permitido para este endpoint.",
        "request.malformed_body": "Não foi possível interpretar o corpo da solicitação.",
        "request.too_large": "O corpo da solicitação é muito grande.",
        "request.rate_limited": "Muitas solicitações. Tente novamente em {retry_after_seconds} segundos.",
        # validation.*
        "validation.field_required": "Este campo é obrigatório.",
        "validation.invalid_format": "O valor tem um formato inválido.",
        "validation.value_too_short": "O valor é muito curto.",
        "validation.value_too_long": "O valor é muito longo.",
        "validation.invalid_value": "O valor não é uma das opções permitidas.",
        "validation.invalid_type": "O valor tem um tipo inválido.",
        "validation.custom": "{msg}",
        # validation.user.*
        "validation.user.invalid_role_combination": "Combinação de papéis inválida: {role_type} + {role_name}.",
        "validation.user.unsupported_locale": "Idioma não suportado '{requested}'. Deve ser um de: {allowed}.",
        "validation.user.passwords_do_not_match": "A nova senha e a confirmação não coincidem.",
        "validation.user.new_password_same_as_current": "A nova senha deve ser diferente da senha atual.",
        # validation.address.*
        "validation.address.city_required": "city_metadata_id ou city_name é obrigatório.",
        "validation.address.invalid_address_type": "Tipo de endereço inválido '{address_type}'.",
        "validation.address.duplicate_address_type": "O tipo de endereço não pode conter valores duplicados.",
        "validation.address.invalid_street_type": "Tipo de logradouro inválido '{street_type}'.",
        "validation.address.country_required": "É necessário fornecer country_code, o nome do país ou place_id.",
        "validation.address.field_required": "O campo '{address_field}' é obrigatório quando place_id não é fornecido.",
        "validation.address.city_metadata_id_required": "city_metadata_id é obrigatório quando place_id não é fornecido.",
        # validation.plate.*
        "validation.plate.kitchen_days_empty": "kitchen_days não pode estar vazio.",
        "validation.plate.kitchen_days_duplicate": "kitchen_days não pode conter dias duplicados.",
        # validation.discretionary.*
        "validation.discretionary.recipient_required": "É necessário fornecer user_id ou restaurant_id.",
        "validation.discretionary.conflicting_recipients": "Não é possível especificar user_id e restaurant_id ao mesmo tempo.",
        "validation.discretionary.restaurant_required": "Esta categoria requer restaurant_id.",
        # validation.holiday.*
        "validation.holiday.recurring_fields_required": "recurring_month e recurring_day são obrigatórios quando is_recurring é True.",
        "validation.holiday.list_empty": "É necessário fornecer pelo menos um feriado.",
        # validation.subscription.*
        "validation.subscription.window_invalid": "hold_end_date deve ser posterior a hold_start_date.",
        "validation.subscription.window_too_long": "A duração da pausa não pode exceder 3 meses.",
        # validation.payment.*
        "validation.payment.conflicting_address_fields": "Não é possível fornecer address_id e address_data ao mesmo tempo.",
        "validation.payment.unsupported_brand": "O tipo de método de pagamento não é suportado.",
        "validation.payment.address_required": "O tipo de método de pagamento '{method_type}' requer um endereço. Forneça address_id ou address_data.",
        # validation.supplier_invoice.* — K67
        "validation.supplier_invoice.cae_format": "O código CAE deve ter exatamente 14 dígitos.",
        "validation.supplier_invoice.cuit_format": "O CUIT deve ter o formato XX-XXXXXXXX-X.",
        "validation.supplier_invoice.afip_doc_type": "O tipo de documento AFIP deve ser um de: A, B, C.",
        "validation.supplier_invoice.sunat_serie_format": "A série SUNAT deve ter o formato F + 3 dígitos (ex.: F001).",
        "validation.supplier_invoice.sunat_correlativo_format": "O correlativo SUNAT deve ter entre 1 e 8 dígitos.",
        "validation.supplier_invoice.ruc_format": "O RUC deve ter exatamente 11 dígitos.",
        "validation.supplier_invoice.cdr_status": "O status CDR deve ser um de: accepted, rejected, pending.",
        "validation.supplier_invoice.ar_details_required": "Faturas AR requerem ar_details.",
        "validation.supplier_invoice.pe_details_required": "Faturas PE requerem pe_details.",
        "validation.supplier_invoice.us_details_required": "Faturas US requerem us_details.",
        "validation.supplier_invoice.rejection_reason_required": "rejection_reason é obrigatório ao rejeitar uma fatura.",
        "validation.supplier_invoice.status_cannot_reset": "Não é possível reverter o status da fatura para Pendente de revisão.",
        "validation.supplier_invoice.w9_ein_format": "ein_last_four deve ter exatamente 4 dígitos.",
        # validation.market.* — K67
        "validation.market.language_unsupported": "Idioma não suportado '{language}'. Deve ser um de: {allowed}.",
        # auth.* — K7
        "auth.invalid_token": "O token de autenticação é inválido ou expirou.",
        "auth.captcha_required": "Verificação CAPTCHA é necessária.",
        "auth.captcha_verification_failed": "A verificação CAPTCHA falhou.",
        "auth.captcha_action_mismatch": "Ação CAPTCHA não corresponde.",
        "auth.captcha_score_too_low": "Pontuação CAPTCHA muito baixa. Tente novamente.",
        "auth.captcha_token_missing": "Token reCAPTCHA ausente.",
        "auth.credentials_invalid": "Usuário ou senha inválidos.",
        "auth.account_inactive": "A conta não está ativa. Entre em contato com o suporte.",
        "auth.customer_app_only": "Contas de cliente devem usar o aplicativo móvel da Vianda.",
        "auth.dummy_admin_not_configured": "O usuário administrador de teste não está configurado.",
        "auth.token_user_id_invalid": "Identificador de usuário inválido no token.",
        "auth.token_institution_id_invalid": "Identificador de instituição inválido no token.",
        "auth.token_missing_fields": "O token não contém os campos obrigatórios.",
        # security.* — K7
        "security.institution_mismatch": "Acesso negado: instituição não corresponde.",
        "security.insufficient_permissions": "Você não tem permissão para realizar esta ação.",
        "security.forbidden": "Acesso negado.",
        "security.token_user_id_missing": "ID de usuário não encontrado no token.",
        "security.token_user_id_invalid": "Formato de ID de usuário inválido no token.",
        "security.address_type_not_allowed": "Tipo de endereço não permitido para o seu papel.",
        "security.address_type_institution_mismatch": "O tipo de endereço não é compatível com este tipo de instituição.",
        "security.user_role_type_not_allowed": "Você não pode criar ou atualizar usuários com este tipo de papel.",
        "security.user_role_name_not_allowed": "Você não pode atribuir este nome de papel.",
        "security.operator_cannot_create_users": "Operadores não podem criar ou editar contas de usuário.",
        "security.cannot_assign_role": "Você não tem permissão para atribuir este papel.",
        "security.cannot_edit_user": "Você não tem permissão para editar este usuário.",
        "security.customer_cannot_edit_employer_address": "Clientes não podem editar ou excluir endereços do empregador.",
        "security.supplier_address_mutation_denied": "Operadores de fornecedor não podem criar ou editar endereços.",
        "security.supplier_user_mutation_denied": "Operadores de fornecedor não podem criar ou editar usuários.",
        "security.supplier_management_denied": "Operadores de fornecedor não podem acessar operações de gestão.",
        "security.supplier_admin_only": "Somente o administrador do fornecedor pode acessar este recurso.",
        "security.supplier_password_reset_denied": "Operadores de fornecedor não podem redefinir senhas de outros usuários.",
        "security.institution_type_mismatch": "O tipo de instituição não corresponde ao tipo de papel do usuário.",
        "security.supplier_institution_only": "Fornecedores só podem adicionar usuários à sua própria instituição.",
        "security.supplier_institution_required": "Sua conta não tem nenhuma instituição configurada.",
        "security.employer_not_for_supplier": "Empregador não é aplicável a usuários Fornecedor, Interno ou Empregador.",
        "security.supplier_terms_edit_denied": "Somente usuários internos autorizados podem editar os termos do fornecedor.",
        # subscription.*
        "subscription.already_active": "Esta assinatura já está ativa.",
        # entity.* — erros genéricos de entidades CRUD (K6)
        "entity.not_found": "{entity} não encontrado/a",
        "entity.not_found_or_operation_failed": "{entity} não encontrado/a ou a operação {operation} falhou",
        "entity.creation_failed": "Falha ao criar {entity}",
        "entity.update_failed": "Falha ao atualizar {entity}",
        "entity.deletion_failed": "Falha ao excluir {entity}",
        # entity.* — códigos adicionais (K8)
        "entity.field_immutable": "O campo '{field}' não pode ser alterado após a criação.",
        # product.* — K8
        "product.image_too_large": "Imagem muito grande. O tamanho máximo é 5 MB.",
        # credit_currency.* — K8
        "credit_currency.name_not_supported": "Nome de moeda não suportado. Use GET /api/v1/currencies/ para ver a lista.",
        "credit_currency.rate_unavailable": "A moeda '{currency_code}' não é suportada pela API de taxas de câmbio.",
        # employer.* — K8
        "employer.benefit_program_not_found": "Nenhum programa de benefícios do empregador encontrado.",
        # user.* — K8
        "user.market_not_assigned": "O usuário não tem um mercado atribuído.",
        # institution.* — K8
        "institution.system_protected": "As instituições do sistema não podem ser arquivadas.",
        "institution.supplier_terms_invalid": "supplier_terms só pode ser fornecido quando institution_type é Fornecedor.",
        # institution_entity.* — K8
        "institution_entity.market_mismatch": "O país do endereço da entidade não pertence aos mercados atribuídos à instituição.",
        # user.signup.* / user.* — erros de identidade de usuário (K9)
        "user.city_not_found": "Cidade não encontrada.",
        "user.city_archived": "A cidade está arquivada. Use uma cidade ativa.",
        "user.city_must_be_specific": "Os clientes devem ter uma cidade específica, não Global.",
        "user.city_required": "A cidade é obrigatória e não pode ser removida.",
        "user.city_country_mismatch": "A cidade deve estar no mesmo país que o seu mercado.",
        "user.market_not_found": "Mercado não encontrado.",
        "user.market_archived": "O mercado está arquivado. Use um mercado ativo.",
        "user.market_global_not_allowed": "Somente Admin ou Super Admin podem atribuir o mercado Global.",
        "user.market_id_invalid": "Identificador de mercado inválido.",
        "user.signup_code_invalid": "Código de verificação inválido ou expirado.",
        "user.signup_country_required": "country_code é obrigatório. Use GET /api/v1/leads/markets para códigos válidos.",
        "user.signup_institution_required": "institution_id é obrigatório para este tipo de usuário.",
        "user.lookup_param_required": "Pelo menos um dos parâmetros deve ser fornecido: username ou email.",
        "user.address_not_found": "Endereço não encontrado.",
        "user.address_archived": "O endereço está arquivado. Use um endereço ativo.",
        "user.address_institution_mismatch": "O endereço não pertence ao empregador especificado.",
        "user.workplace_group_not_found": "Grupo de trabalho não encontrado.",
        "user.workplace_group_archived": "O grupo de trabalho está arquivado.",
        "user.invite_no_email": "O usuário não tem endereço de e-mail. Não é possível enviar o convite.",
        "user.onboarding_customer_only": "O status de integração só está disponível para usuários Cliente.",
        # server.* — erro interno suprimido (K9, Decision F)
        "server.internal_error": "Ocorreu um erro interno. Tente novamente ou entre em contato com o suporte.",
        # subscription.* — erros de ciclo de vida (K10)
        "subscription.not_found": "Assinatura não encontrada.",
        "subscription.not_pending": "A assinatura não está no estado Pendente.",
        "subscription.not_on_hold": "A assinatura não está em pausa.",
        "subscription.already_on_hold": "A assinatura já está em pausa.",
        "subscription.already_cancelled": "A assinatura já foi cancelada.",
        "subscription.cannot_hold_cancelled": "Não é possível pausar uma assinatura cancelada.",
        "subscription.confirm_mock_only": "confirm-payment só está disponível quando PAYMENT_PROVIDER=mock. Use o webhook do Stripe para pagamentos reais.",
        "subscription.payment_not_found": "Nenhum pagamento pendente encontrado para esta assinatura.",
        "subscription.payment_record_not_found": "Nenhum registro de pagamento encontrado para esta assinatura.",
        "subscription.payment_provider_unavailable": "Detalhes de pagamento não disponíveis para este provedor.",
        "subscription.access_denied": "Você não tem acesso a esta assinatura.",
        # plate_selection.* — erros de ciclo de vida (K10)
        "plate_selection.not_found": "Seleção de prato não encontrada.",
        "plate_selection.immutable_fields": "Não é possível modificar {fields}. Apenas pickup_time_range, pickup_intent e flexible_on_time são editáveis. Para alterar o prato, cancele esta seleção e crie uma nova.",
        "plate_selection.access_denied": "Não autorizado a acessar esta seleção de prato.",
        "plate_selection.not_editable": "A seleção de prato não é mais editável. Edições são permitidas até 1 hora antes da abertura do kitchen day.",
        "plate_selection.not_cancellable": "A seleção de prato não é mais editável. O cancelamento é permitido até 1 hora antes da abertura do kitchen day.",
        "plate_selection.duplicate_kitchen_day": "Você já tem um prato reservado para {kitchen_day}. Deseja cancelar sua refeição atual e reservar este prato?",
        # plate_pickup.* — erros (K10)
        "plate_pickup.access_denied": "Não autorizado a acessar este registro de retirada.",
        "plate_pickup.invalid_qr_code": "Este código QR não é reconhecido.",
        "plate_pickup.wrong_restaurant": "Você escaneou o código QR do restaurante errado.",
        "plate_pickup.no_active_reservation": "Nenhuma reserva ativa encontrada para este restaurante.",
        "plate_pickup.invalid_status": "Não é possível realizar esta ação com o status de retirada atual.",
        "plate_pickup.invalid_signature": "Assinatura de código QR inválida.",
        "plate_pickup.cannot_delete": "Não é possível excluir o registro de retirada com status {pickup_status}. Apenas pedidos pendentes podem ser excluídos.",
        # plate_review.* — erros (K10)
        "plate_review.not_found": "Retirada não encontrada.",
        "plate_review.access_denied": "Esta retirada não pertence a você.",
        "plate_review.not_eligible": "Você só pode avaliar pratos que retirou. Complete a retirada primeiro.",
        "plate_review.pickup_archived": "Não é possível avaliar uma retirada arquivada.",
        "plate_review.already_exists": "Esta retirada já foi avaliada. As avaliações são imutáveis.",
        "plate_review.invalid_portion_rating": "Reclamações de porção só podem ser feitas para avaliações com nota de porção 1 (pequena).",
        "plate_review.complaint_exists": "Uma reclamação de porção já foi registrada para esta avaliação.",
        # payment_provider.* — erros do Stripe Connect (K10)
        "payment_provider.onboarding_required": "A entidade não tem conta de provedor de pagamento. Complete o cadastro primeiro.",
        "payment_provider.not_ready": "A conta Stripe Connect ainda não está habilitada para pagamentos. O fornecedor deve completar o cadastro.",
        "payment_provider.payout_exists": "Já existe um pagamento para esta fatura com status '{payout_status}'.",
        "payment_provider.unavailable": "O provedor de pagamento está temporariamente indisponível.",
        "payment_provider.rate_limited": "Limite de solicitações do provedor de pagamento excedido.",
        "payment_provider.auth_failed": "Falha na autenticação com o provedor de pagamento.",
        "payment_provider.error": "Erro do provedor de pagamento.",
        "payment_provider.bill_not_pending": "A resolução da fatura é '{resolution}'; apenas faturas pendentes podem ser pagas.",
        # mercado_pago.* — erros de OAuth (K10)
        "mercado_pago.auth_code_missing": "Código de autorização ausente.",
        "mercado_pago.auth_failed": "Autorização do Mercado Pago falhou.",
        # database.* — erros de violação de restrições (K6)
        "database.duplicate_key": "Já existe um registro com este valor.",
        "database.duplicate_email": "Já existe um usuário com este e-mail.",
        "database.duplicate_username": "Já existe um usuário com este nome de usuário.",
        "database.duplicate_market": "Já existe um mercado para este país.",
        "database.duplicate_currency": "Já existe uma moeda com este código.",
        "database.duplicate_institution": "Já existe uma instituição com este nome.",
        "database.duplicate_restaurant": "Já existe um restaurante com este nome.",
        "database.foreign_key_user": "O usuário referenciado não existe.",
        "database.foreign_key_institution": "A instituição referenciada não existe.",
        "database.foreign_key_currency": "A moeda referenciada não existe.",
        "database.foreign_key_subscription": "A assinatura referenciada não existe.",
        "database.foreign_key_plan": "O plano referenciado não existe.",
        "database.foreign_key_payment": "A tentativa de pagamento referenciada não existe.",
        "database.foreign_key_violation": "O registro referenciado não existe.",
        "database.not_null_modified_by": "O campo modificado por é obrigatório.",
        "database.not_null_currency_code": "O código da moeda é obrigatório.",
        "database.not_null_currency_name": "O nome da moeda é obrigatório.",
        "database.not_null_username": "O nome de usuário é obrigatório.",
        "database.not_null_email": "O e-mail é obrigatório.",
        "database.not_null_violation": "Campo obrigatório ausente.",
        "database.check_violation": "Os dados fornecidos violam regras de negócio.",
        "database.invalid_uuid": "Formato de UUID inválido.",
        "database.invalid_format": "Formato de dados inválido.",
        "database.error": "Erro de banco de dados durante {operation}: {detail}",
        # restaurant.* — erros de gestão de restaurantes (K11)
        "restaurant.not_found": "Restaurante não encontrado.",
        "restaurant.entity_id_required": "institution_entity_id é obrigatório.",
        "restaurant.market_required": "Um mercado é necessário. Envie market_id ou certifique-se de que o usuário tem um mercado principal.",
        "restaurant.market_access_denied": "market_id deve ser um dos seus mercados atribuídos.",
        "restaurant.active_requires_setup": "Não é possível ativar o restaurante. Ele deve ter pelo menos um prato com plate_kitchen_days ativos e pelo menos um código QR ativo.",
        "restaurant.active_requires_plate_days": "Não é possível ativar o restaurante. Ele deve ter pelo menos um prato com plate_kitchen_days ativos.",
        "restaurant.active_requires_qr": "Não é possível ativar o restaurante. Ele deve ter pelo menos um código QR ativo. Crie um código QR para este restaurante.",
        "restaurant.active_requires_entity_payouts": "Não é possível ativar o restaurante: a entidade institucional vinculada não concluiu o Stripe Connect. Conclua o processo de pagamento para a entidade e tente novamente.",
        # restaurant_holiday.* — K11
        "restaurant_holiday.not_found": "Feriado do restaurante não encontrado.",
        "restaurant_holiday.duplicate": "O restaurante já tem um feriado registrado para {holiday_date}.",
        "restaurant_holiday.on_national_holiday": "A data {holiday_date} já é um feriado nacional. Os restaurantes não podem registrar feriados em datas de feriados nacionais.",
        # national_holiday.* — K11
        "national_holiday.not_found": "Feriado nacional não encontrado.",
        "national_holiday.update_empty": "Nenhum campo fornecido para atualização.",
        # push.* — FCM notification copy (K4)
        "push.pickup_ready_title": "Prato pronto",
        "push.pickup_ready_body": "Você recebeu seu prato de {restaurant_name}?",
        # market.* — K12
        "market.not_found": "Mercado não encontrado.",
        "market.country_not_supported": "País não suportado para novos mercados. Use GET /api/v1/countries/ para a lista de países suportados.",
        "market.super_admin_only": "Somente o Super Admin pode realizar esta ação no Mercado Global.",
        "market.no_coverage_to_activate": "Não é possível ativar: o mercado não tem restaurante ativo com prato ativo em dia de cozinha semanal ativo. Agende cobertura primeiro e depois defina o status como ativo.",
        "market.has_coverage_confirm_deactivate": "Este mercado atualmente tem cobertura ativa de pratos. Desativá-lo o ocultará dos clientes imediatamente. Reenvie com confirm_deactivate=true para continuar.",
        "market.global_cannot_be_archived": "O Mercado Global não pode ser arquivado.",
        "market.billing_config_not_found": "Nenhuma configuração de faturamento encontrada para este mercado.",
        # ad_zone.* — K12
        "ad_zone.not_found": "Zona publicitária não encontrada.",
        # cuisine.* — K12
        "cuisine.not_found": "Tipo de culinária não encontrado.",
        "cuisine.suggestion_not_found": "Sugestão não encontrada ou já revisada.",
        # archival.* — K12
        "archival.no_records_provided": "Nenhum ID de registro fornecido.",
        "archival.too_many_records": "Não é possível arquivar mais de 1000 registros de uma vez.",
        "archival_config.not_found": "Configuração de arquivamento não encontrada.",
        "archival_config.already_exists": "Já existe uma configuração para a tabela {table_name}.",
        # referral_config.* — K12
        "referral_config.not_found": "Configuração de referral não encontrada para este mercado.",
        # supplier_invoice.* — K12
        "supplier_invoice.not_found": "Fatura do fornecedor não encontrada.",
        "supplier_invoice.invalid_status": "Não é possível revisar a fatura com status '{invoice_status}'. Deve estar em 'pending_review'.",
        # billing.* — K12
        "billing.bill_not_found": "Fatura não encontrada.",
        "billing.bill_already_paid": "Não é possível cancelar uma fatura paga.",
        "billing.bill_already_cancelled": "A fatura já está cancelada.",
        "billing.plan_no_credits": "O plano não tem créditos; não é possível processar.",
        "billing.no_data_found": "Nenhum dado de faturamento encontrado para esta instituição.",
        # discretionary.* — K12
        "discretionary.not_found": "Solicitação discricionária não encontrada.",
        "discretionary.not_pending": "Não é possível atualizar a solicitação com status: {request_status}.",
        # discretionary.* — K13
        "discretionary.recipient_institution_mismatch": "O destinatário selecionado não pertence à instituição especificada.",
        "discretionary.recipient_market_mismatch": "O destinatário selecionado não pertence ao mercado especificado.",
        "discretionary.invalid_amount": "O valor deve ser maior que 0.",
        "discretionary.invalid_category": "Valor de categoria inválido: {category}.",
        "discretionary.category_requires_restaurant": "A categoria '{category}' requer que restaurant_id seja especificado.",
        # enrollment.* — K13
        "enrollment.no_active_program": "Nenhum programa de benefícios ativo para esta instituição.",
        "enrollment.email_already_registered": "E-mail já registrado no sistema.",
        "enrollment.city_no_market": "Cidade não encontrada ou sem mercado ativo.",
        "enrollment.employer_institution_id_required": "Usuários internos devem fornecer o parâmetro institution_id para especificar qual instituição Empregador operar.",
        "enrollment.partial_subsidy_requires_app": "Este benefício cobre apenas parte do preço do plano. O funcionário deve se inscrever através do aplicativo Vianda para pagar sua parte.",
        # employer.program.* — K13
        "employer.program_already_exists": "Já existe um programa de benefícios para este {scope}.",
        # user.market.* — K14
        "user.market_ids_empty": "market_ids deve conter pelo menos um mercado.",
        "user.market_ids_invalid": "market_id(s) inválido(s) ou arquivado(s): {market_ids}.",
        "user.market_not_in_institution": "O mercado {market_id} não está atribuído à instituição do usuário.",
        "user.duplicate_username": "Nome de usuário já existe.",
        "user.duplicate_email_in_system": "E-mail já existe.",
        # entity.archive.* — K14
        "entity.search_invalid_param": "search_by deve ser um de: {allowed}.",
        "entity.archive_active_pickups": "Não é possível arquivar a entidade: existem {count} retirada(s) ativa(s). Complete ou cancele-as primeiro.",
        "entity.archive_active_restaurants": "Não é possível arquivar a entidade: {count} restaurante(s) ativo(s) deve(m) ser arquivado(s) primeiro: {names}.",
        "restaurant.archive_active_pickups": "Não é possível arquivar o restaurante: existem {count} retirada(s) ativa(s). Complete ou cancele-as primeiro.",
        # plate_kitchen_day.* — K14
        "plate_kitchen_day.not_found": "Dia de cozinha do prato não encontrado.",
        "plate_kitchen_day.duplicate": "O prato {plate_id} já está atribuído a {kitchen_day}.",
        "plate_kitchen_day.plate_id_immutable": "plate_id não pode ser alterado em um dia de cozinha existente; crie um novo registro e arquive o antigo.",
        "plate_kitchen_day.archive_failed": "Falha ao arquivar o dia de cozinha do prato.",
        "plate_kitchen_day.update_failed": "Falha ao atualizar o dia de cozinha do prato.",
        "plate_kitchen_day.delete_failed": "Falha ao excluir o dia de cozinha do prato.",
        # restaurant.status.* — K14
        "restaurant.archived": "O restaurante '{name}' está arquivado e não pode aceitar novos pedidos.",
        "restaurant.entity_archived": "O restaurante '{name}' pertence a uma entidade arquivada e não pode aceitar novos pedidos.",
        "restaurant.unavailable": "O restaurante '{name}' {status_message} e não pode aceitar novos pedidos. Por favor tente outro restaurante.",
        "restaurant.national_holiday": "O restaurante '{name}' não pode aceitar pedidos em {date} devido a um feriado nacional. Por favor selecione outra data.",
        "restaurant.restaurant_holiday": "O restaurante '{name}' está fechado em {date} devido a um feriado do restaurante. Por favor selecione outra data.",
        # plate_selection.window.* — K14
        "plate_selection.pickup_time_required": "pickup_time_range é obrigatório e deve estar no formato HH:MM-HH:MM (ex. 11:30-11:45).",
        "plate_selection.no_pickup_windows": "Não há janelas de retirada disponíveis para {kitchen_day} neste mercado. Por favor selecione outro dia.",
        "plate_selection.invalid_pickup_window": "pickup_time_range '{pickup_time_range}' não é uma janela de retirada válida para {kitchen_day}. Janelas permitidas: {allowed_windows}.",
        "plate_selection.kitchen_day_invalid": "A cozinha não opera em {kitchen_day}. Dias disponíveis: {available_days}.",
        "plate_selection.kitchen_day_not_available": "O prato não está disponível em {kitchen_day}. Dias disponíveis: {available_days}.",
        "plate_selection.kitchen_day_too_far": "Não é possível pedir para {kitchen_day} a partir de {current_day}. Pedidos são permitidos com até 1 semana de antecedência.",
        "plate_selection.no_kitchen_days": "Nenhum dia de cozinha disponível encontrado na próxima semana. Dias disponíveis: {available_days}.",
        # plate_selection.create.* — K14
        "plate_selection.plate_id_required": "plate_id é obrigatório.",
        "plate_selection.plate_id_invalid": "Formato de plate_id inválido.",
        # plate_review.access.* — K14
        "plate_review.customer_only": "Clientes não podem acessar avaliações da instituição.",
        "plate_review.no_institution": "Nenhuma instituição atribuída.",
        "plate_review.by_pickup_not_found": "Avaliação não encontrada para esta retirada.",
        # ingredient.* — K14
        "ingredient.not_found": "Ingrediente {ingredient_id} não encontrado.",
        # plate_pickup.staff.* — K14
        "plate_pickup.staff_only": "Acesso restrito à equipe do restaurante.",
        "plate_pickup.invalid_user_id": "Formato de ID de usuário inválido.",
        "plate_pickup.invalid_filter": "Parâmetro de filtro inválido.",
        # locale.* — K15
        "locale.unsupported": "Idioma não suportado '{locale}'. Suportados: {supported}.",
        # address.* (business-logic) — K15
        "address.institution_required": "institution_id é obrigatório para criação de endereço B2B.",
        "address.customer_institution_required": "O endereço do cliente requer contexto de instituição; institution_id ausente no usuário.",
        "address.target_user_not_found": "Usuário alvo não encontrado.",
        "address.user_institution_mismatch": "O usuário atribuído ao endereço deve pertencer à mesma instituição que o endereço.",
        "address.creation_failed": "Erro ao criar endereço.",
        "address.invalid_country": "Código de país inválido. Mercado não encontrado.",
        "address.not_found": "Endereço não encontrado.",
        # address.* extended — K15
        "address.manual_entry_not_allowed": "A criação de endereço por entrada manual só está disponível em desenvolvimento. Use a busca de endereço para produção.",
        "address.global_market_invalid": "Endereços não podem ser registrados no Marketplace Global. Por favor selecione um país específico.",
        "address.city_country_mismatch": "A cidade não pertence ao país especificado. Resolva uma cidade do mesmo país.",
        "address.place_details_failed": "Não foi possível obter os detalhes do endereço selecionado. Tente novamente ou insira o endereço manualmente.",
        "address.outside_service_area": "Endereço fora da nossa área de atendimento.",
        "address.city_metadata_unresolvable": "Não foi possível resolver uma cidade válida para a localização fornecida.",
        # workplace_group.* — K15
        "workplace_group.not_found": "Grupo de trabalho não encontrado.",
        "workplace_group.creation_failed": "Falha ao criar grupo de trabalho.",
        "workplace_group.update_failed": "Falha ao atualizar grupo de trabalho.",
        "workplace_group.archive_failed": "Falha ao arquivar grupo de trabalho.",
        # supplier_terms.* — K15
        "supplier_terms.access_denied": "Fornecedores só podem ver seus próprios termos de fornecedor.",
        "supplier_terms.not_found": "Termos de fornecedor não encontrados para {scope}.",
        "supplier_terms.internal_only": "Somente usuários internos podem listar todos os termos de fornecedor.",
        # webhook.* — K15
        "webhook.secret_not_configured": "Segredo do webhook não configurado.",
        "webhook.invalid_payload": "Payload do webhook inválido.",
        "webhook.invalid_signature": "Assinatura do webhook inválida.",
        # payment_method.* — K15
        "payment_method.not_found": "Método de pagamento não encontrado.",
        "payment_method.access_denied": "Você não tem acesso a este método de pagamento.",
        "payment_method.setup_url_required": "success_url é obrigatório (corpo da solicitação ou STRIPE_CUSTOMER_SETUP_SUCCESS_URL).",
        "payment_method.mock_only": "Esta operação só está disponível quando PAYMENT_PROVIDER=mock.",
        "payment_method.provider_unavailable": "A configuração de pagamento está temporariamente indisponível. Tente novamente.",
        # referral.* — K15
        "referral.code_invalid": "Código de indicação inválido.",
        "referral.code_not_found": "Código de indicação não encontrado.",
        "referral.assignment_not_found": "Nenhuma atribuição de código de indicação ativa encontrada.",
        # email_change.* — K15
        "email_change.email_required": "O e-mail é obrigatório.",
        "email_change.same_as_current": "O novo e-mail deve ser diferente do atual.",
        "email_change.already_taken": "Este e-mail já está registrado em outra conta.",
        "email_change.pending_for_email": "Há outra verificação pendente para este endereço de e-mail.",
        "email_change.code_expired": "O código de verificação expirou. Solicite um novo.",
        "email_change.code_invalid": "Código de verificação inválido.",
        "email_change.user_not_found": "Usuário não encontrado.",
        # credit.* — K15
        "credit.amount_must_be_positive": "O valor do crédito deve ser positivo.",
        "credit.currency_not_found": "Moeda de crédito não encontrada para este restaurante.",
        # checksum.* — K15
        "checksum.unsupported_algorithm": "Algoritmo de checksum não suportado: {algorithm}.",
        "checksum.mismatch": "O checksum da imagem não corresponde. Por favor faça o upload do arquivo novamente.",
        # country.* — K15
        "country.invalid_code": "Código de país inválido.",
        # dev.* — K15
        "dev.mode_only": "Este endpoint só está disponível no modo DEV.",
        # institution_entity.* (additional) — K15
        "institution_entity.no_markets": "A instituição não tem mercados atribuídos.",
        "institution_entity.no_payout_aggregator": "Nenhum agregador de pagamento configurado para este mercado.",
        "institution_entity.payout_setup_required": "Configuração do provedor de pagamento é obrigatória.",
        # qr_code.* — K15
        "qr_code.no_image": "O código QR não tem imagem armazenada.",
        # product_image.* — K15
        "product_image.empty": "A imagem enviada está vazia.",
        "product_image.format_invalid": "Formato de imagem inválido.",
        "product_image.checksum_mismatch": "O checksum da imagem não corresponde. Por favor faça o upload do arquivo novamente.",
        "product_image.unreadable": "Não é possível ler o arquivo de imagem.",
        # leads.* — K15
        "leads.country_code_required": "country_code é obrigatório.",
        "leads.email_required": "Um e-mail válido é obrigatório.",
        "leads.invalid_interest_type": "Tipo de interesse inválido '{interest_type}'. Deve ser: customer, employer ou supplier.",
        "leads.invalid_restaurant_data": "Dados de restaurante inválidos. Verifique referral_source e cuisine_ids.",
        # timezone.* — K15
        "timezone.country_code_required": "country_code é obrigatório para deduzir o fuso horário.",
        "timezone.not_found": "Fuso horário não encontrado para a localização fornecida.",
        # ad_zone.* extended — K15
        "ad_zone.invalid_flywheel_state": "Estado de flywheel inválido.",
        # coworker.* — K15
        "coworker.employer_required": "Você precisa ter um empregador atribuído para listar colegas de trabalho.",
        "coworker.user_ineligible": "Um ou mais usuários não são colegas de trabalho elegíveis para esta seleção de prato.",
        # user.me.* — K15
        "user.use_me_endpoint": "Use o endpoint /me para o seu próprio perfil.",
        # subscription.* — K15
        "subscription.creation_failed": "Falha ao criar a assinatura.",
        "subscription.payment_record_failed": "Falha ao registrar o pagamento da assinatura.",
        # plate_review.operation.* — K15
        "plate_review.creation_failed": "Falha ao criar a avaliação do prato.",
        "plate_review.complaint_failed": "Falha ao registrar a reclamação de porção.",
        # plate_kitchen_days.* — K15
        "plate_kitchen_days.list_failed": "Falha ao listar os dias de cozinha.",
        "plate_kitchen_days.enriched_list_failed": "Falha ao obter os dias de cozinha enriquecidos.",
        "plate_kitchen_days.enriched_get_failed": "Falha ao obter o dia de cozinha enriquecido.",
        # national_holiday.* — K15
        "national_holiday.update_failed": "Falha ao atualizar o feriado nacional.",
        "national_holiday.delete_failed": "Falha ao excluir o feriado nacional.",
        # qr_code.* — K15
        "qr_code.list_failed": "Falha ao recuperar os QR codes.",
        "qr_code.get_failed": "Falha ao recuperar o QR code.",
        "qr_code.delete_failed": "Falha ao excluir o QR code.",
        # restaurant_balance.* — #87-d (404 hijack sweep)
        "restaurant_balance.not_found": "Saldo do restaurante não encontrado.",
        # restaurant_transaction.* — #87-d (404 hijack sweep)
        "restaurant_transaction.not_found": "Transação do restaurante não encontrada.",
        # restaurant.* — K15
        "restaurant.creation_failed": "Falha ao criar o restaurante.",
        "restaurant.balance_creation_failed": "Falha ao criar o registro de saldo do restaurante.",
        "restaurant.list_failed": "Falha ao recuperar os restaurantes.",
        "restaurant.cities_list_failed": "Falha ao listar cidades com restaurantes.",
        "restaurant.enriched_list_failed": "Falha ao recuperar os restaurantes enriquecidos.",
        "restaurant.enriched_get_failed": "Falha ao recuperar o restaurante enriquecido.",
        "restaurant.get_failed": "Falha ao recuperar o restaurante.",
        "restaurant.update_failed": "Falha ao atualizar o restaurante.",
        "restaurant.delete_failed": "Falha ao excluir o restaurante.",
        # restaurant_holiday.* — K15
        "restaurant_holiday.update_failed": "Falha ao atualizar o feriado do restaurante.",
        "restaurant_holiday.delete_failed": "Falha ao excluir o feriado do restaurante.",
        # plate_selection.* operation — K15
        "plate_selection.creation_failed": "Falha ao criar a seleção de prato.",
        # enrollment.* extended — K15
        "enrollment.benefit_employee_creation_failed": "Falha ao criar o funcionário beneficiário.",
        "enrollment.subscription_creation_failed": "Falha ao criar a assinatura para a inscrição.",
        # employer.* extended — K15
        "employer.bill_creation_failed": "Falha ao criar a fatura do empregador.",
        "employer.benefits_program_creation_failed": "Falha ao criar o programa de benefícios.",
        # discretionary.* — K15
        "discretionary.request_creation_failed": "Falha ao criar a solicitação discricionária.",
        "discretionary.request_approval_failed": "Falha ao aprovar a solicitação discricionária.",
        "discretionary.request_rejection_failed": "Falha ao rejeitar a solicitação discricionária.",
        "discretionary.list_failed": "Falha ao recuperar as solicitações discricionárias.",
        "discretionary.transaction_creation_failed": "Falha ao criar a transação discricionária.",
        # credit.* extended — K15
        "credit.transaction_creation_failed": "Falha ao criar a transação de crédito.",
        "credit.validation_failed": "Erro ao validar os créditos do usuário. Por favor tente novamente.",
        # currency_refresh.* — K15
        "currency_refresh.rate_unavailable": "Taxa de câmbio de moeda não disponível.",
        # favorite.* — K15
        "favorite.entity_type_invalid": "Tipo de entidade inválido. Deve ser: plate ou restaurant.",
        "favorite.not_found": "Entidade não encontrada.",
        "favorite.already_added": "Já adicionado aos favoritos.",
        # notification.* — K15
        "notification.not_found": "Notificação não encontrada.",
        # billing.payout.* — K15
        "billing.payout_bill_not_pending": "Somente faturas pendentes podem ser pagas.",
        # plate_selection.* extended — K15
        "plate_selection.pickup_intent_invalid": "pickup_intent deve ser offer, request ou self.",
        # institution.* — K15
        "institution.restricted": "Esta instituição não pode ser atribuída a um {context}. Use uma instituição Supplier.",
        # tax_id.* — K15
        "tax_id.format_invalid": "Formato de {label} inválido para {country_code}. Esperado {digit_count} dígitos (ex. {example}).",
        # api.* — K15
        "api.version_unsupported": "Versão de API não suportada: {version}.",
        # market.* extended — K15
        "market.global_entity_invalid": "O Mercado Global não pode ser atribuído a {entity_name}.",
        # ── K16: services sweep ───────────────────────────────────────────────
        # qr_code.* (operation failures) — K16
        "qr_code.create_failed": "Falha ao criar o código QR.",
        "qr_code.update_failed": "Falha ao atualizar o status do código QR.",
        "qr_code.image_generation_failed": "Falha ao gerar a imagem do código QR.",
        "qr_code.image_not_found": "Arquivo de imagem do código QR não encontrado no servidor.",
        "qr_code.image_load_failed": "Falha ao carregar a imagem do código QR.",
        # product.* (operation failures) — K16
        "product.enriched_list_failed": "Falha ao recuperar os produtos.",
        "product.enriched_get_failed": "Falha ao recuperar o produto.",
        "product.creation_failed": "Falha ao criar o produto.",
        "product.update_failed": "Falha ao atualizar o produto.",
        "product.image_update_failed": "Falha ao atualizar a imagem do produto.",
        "product.image_revert_failed": "Falha ao reverter a imagem do produto para o marcador.",
        # plan.* (operation failures) — K16
        "plan.enriched_list_failed": "Falha ao recuperar os planos.",
        "plan.enriched_get_failed": "Falha ao recuperar o plano.",
        # institution.* (operation failures) — K16
        "institution.creation_failed": "Falha ao criar a instituição.",
        "institution.update_failed": "Falha ao atualizar a instituição.",
        "institution.supplier_terms_creation_failed": "Falha ao criar os termos do fornecedor.",
        # ingredient.* (operation failures) — K16
        "ingredient.creation_failed": "Falha ao criar o ingrediente.",
        "ingredient.product_update_failed": "Falha ao atualizar os ingredientes do produto.",
        # notification.* (operation failures) — K16
        "notification.acknowledge_failed": "Falha ao confirmar a notificação.",
        # subscription.* (operation failures) — K16
        "subscription.renewal_update_failed": "Falha ao atualizar as preferências de renovação.",
        # user.* (service operation failures) — K16
        "user.get_failed": "Falha ao recuperar o usuário.",
        "user.creation_failed": "Falha ao criar o usuário.",
        "user.list_failed": "Falha ao recuperar os usuários.",
        "user.enriched_get_failed": "Falha ao recuperar os detalhes do usuário.",
        "user.market_update_failed": "Falha ao atualizar as atribuições de mercado.",
        # service.* (product/plate/bill/geolocation helpers) — K16
        "service.product_list_failed": "Falha ao recuperar os produtos.",
        "service.product_search_failed": "Falha ao pesquisar produtos.",
        "service.plate_list_failed": "Falha ao recuperar os pratos.",
        "service.bill_list_failed": "Falha ao recuperar as faturas.",
        "service.geolocation_get_failed": "Falha ao recuperar a geolocalização.",
    },
}


def get_message(key: str, locale: str = "en", **params: Any) -> str:
    """
    Localized message for key; falls back to English then to key string.
    Supports str.format for params when the template exists.
    """
    msg = MESSAGES.get(locale, {}).get(key) or MESSAGES["en"].get(key, key)
    if params:
        try:
            msg = msg.format(**params)
        except KeyError:
            pass
    return msg
