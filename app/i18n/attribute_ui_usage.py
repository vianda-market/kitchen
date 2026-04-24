"""UI-usage inventory: columns rendered in at least one frontend today.

Denominator for the Phase 2 coverage lint. Maintained per schema PR.

Key format: <schema>.<table>.<column>
Optional tag: surfaces — list of frontend names that render this column.
  Valid surface names: "platform", "app", "home"

Columns omitted from this inventory either:
  (a) never ship in any API response, or
  (b) ship in responses but no frontend references them — these are over-exposure
      candidates surfaced by the Phase 2 enriched-endpoint-vs-inventory lint.
"""

from typing import TypedDict


class InventoryEntry(TypedDict, total=False):
    surfaces: list[str]  # optional — which frontends render this column


INVENTORY: dict[str, InventoryEntry] = {
    # --- external.iso4217_currency ---
    #
    # .code surfaces as "currency_code" in enriched responses (renamed at the JOIN layer).
    # vianda-platform: types/api.ts (CreditCurrencyResponseSchema, MarketEnrichedSchema, etc.),
    #   utils/columnConfigs.ts, utils/formConfigs.ts — rendered in currency dropdowns and bills.
    # vianda-app: api/types.ts (expected_payout_local_currency context), SyncUserMarketToSelector.tsx.
    "external.iso4217_currency.code": {"surfaces": ["platform", "app"]},
    #
    # .name surfaces as "currency_name" in enriched responses (renamed at the JOIN layer).
    # vianda-platform: types/api.ts (CreditCurrencyResponseSchema, EnrichedPlanResponseSchema),
    #   utils/formConfigs.ts — rendered in credit currency form dropdowns and plan forms.
    "external.iso4217_currency.name": {"surfaces": ["platform"]},
    # --- core.currency_metadata ---
    #
    # .currency_code surfaces directly in MarketResponseSchema and enriched responses.
    # vianda-platform: types/api.ts (MarketResponseSchema, EnrichedPlanResponseSchema, etc.)
    # vianda-app: api/types.ts (SelectedMarket, SyncUserMarketToSelector.tsx).
    "core.currency_metadata.currency_code": {"surfaces": ["platform", "app"]},
    #
    # .credit_value_local_currency surfaces in MarketResponseSchema as market_credit_value_local_currency.
    # vianda-platform: types/api.ts — used in plan pricing preview calculations.
    "core.currency_metadata.credit_value_local_currency": {"surfaces": ["platform"]},
    #
    # .currency_conversion_usd surfaces in MarketResponseSchema.
    # vianda-platform: types/api.ts — used for USD cost estimates in plan forms.
    "core.currency_metadata.currency_conversion_usd": {"surfaces": ["platform"]},
    # --- core.market_info ---
    #
    # .country_code surfaces in MarketResponseSchema and all enriched responses.
    # vianda-platform: types/api.ts (MarketResponseSchema), many enriched response types.
    # vianda-app: api/types.ts (SelectedMarket, MarketContext.tsx — market selection).
    # vianda-home: CountryContext.tsx, RestaurantApplicationForm.tsx.
    "core.market_info.country_code": {"surfaces": ["platform", "app", "home"]},
    #
    # .currency_metadata_id surfaces in MarketResponseSchema and entity enriched responses.
    # vianda-platform: types/api.ts (MarketResponseSchema, InstitutionEntityResponseSchema).
    "core.market_info.currency_metadata_id": {"surfaces": ["platform"]},
    #
    # .language surfaces in MarketPublicMinimalSchema (/leads/markets) and MarketResponseSchema.
    # vianda-app: MarketContext.tsx — sets API locale from market.language.
    # vianda-home: CountryContext.test.tsx, api/types.ts.
    "core.market_info.language": {"surfaces": ["app", "home"]},
    #
    # .phone_dial_code surfaces in MarketPublicMinimalSchema (/leads/countries) as phone_dial_code.
    # vianda-platform: types/api.ts (MarketResponseSchema — phone_dial_code field).
    # vianda-home: contexts/CountryContext.test.tsx, landing/forms/countryToMarket.ts.
    "core.market_info.phone_dial_code": {"surfaces": ["platform", "home"]},
    #
    # .phone_local_digits surfaces in MarketResponseSchema.
    # vianda-platform: types/api.ts (MarketResponseSchema — phone_local_digits field).
    "core.market_info.phone_local_digits": {"surfaces": ["platform"]},
    #
    # .status surfaces in MarketResponseSchema.
    # vianda-platform: types/api.ts — rendered in market management UI.
    "core.market_info.status": {"surfaces": ["platform"]},
    # --- core.institution_info ---
    #
    # .name surfaces as "institution_name" in all enriched user/entity/restaurant responses.
    # vianda-platform: types/api.ts (many types include institution_name: string).
    "core.institution_info.name": {"surfaces": ["platform"]},
    #
    # .institution_type surfaces in enriched institution responses and onboarding status.
    # vianda-platform: types/api.ts (OnboardingStatusResponseSchema, institution types).
    "core.institution_info.institution_type": {"surfaces": ["platform"]},
    #
    # .status surfaces in enriched institution responses.
    # vianda-platform: types/api.ts — institution status field.
    "core.institution_info.status": {"surfaces": ["platform"]},
    # --- core.address_info ---
    #
    # .address_type surfaces in address enriched responses.
    # vianda-platform: types/api.ts (AddressResponseSchema — address_type field).
    # vianda-app: ProfileContent.tsx — renders address type labels.
    "core.address_info.address_type": {"surfaces": ["platform", "app"]},
    #
    # .country_code surfaces in address enriched responses.
    # vianda-platform: types/api.ts (AddressResponseSchema, enriched institution responses).
    "core.address_info.country_code": {"surfaces": ["platform"]},
    #
    # .province surfaces in address enriched responses.
    # vianda-platform: types/api.ts (AddressResponseSchema — province field).
    "core.address_info.province": {"surfaces": ["platform"]},
    #
    # .postal_code surfaces in address enriched responses.
    # vianda-platform: types/api.ts, utils/forms.ts — postal code display.
    # vianda-app: utils/addressFormat.ts, addressFormat.test.ts.
    "core.address_info.postal_code": {"surfaces": ["platform", "app"]},
    #
    # .street_type surfaces in address enriched responses.
    # vianda-platform: types/api.ts (AddressResponseSchema — street_type field).
    # vianda-app: RestaurantMapSection.web.tsx — builds address display string.
    "core.address_info.street_type": {"surfaces": ["platform", "app"]},
    #
    # .street_name surfaces in address enriched responses.
    # vianda-platform: types/api.ts (AddressResponseSchema — street_name field).
    # vianda-app: utils/addressFormat.ts, RestaurantMapSection.web.tsx.
    "core.address_info.street_name": {"surfaces": ["platform", "app"]},
    #
    # .building_number surfaces in address enriched responses.
    # vianda-platform: types/api.ts (AddressResponseSchema — building_number field).
    # vianda-app: utils/addressFormat.ts, RestaurantMapSection.web.tsx.
    "core.address_info.building_number": {"surfaces": ["platform", "app"]},
    #
    # .timezone surfaces in address enriched responses (restaurant timezone for scheduling).
    # vianda-platform: types/api.ts — timezone field for kitchen scheduling.
    "core.address_info.timezone": {"surfaces": ["platform"]},
    # --- core.address_subpremise ---
    #
    # .floor surfaces in address enriched responses.
    # vianda-platform: types/api.ts (AddressResponseSchema — floor field).
    "core.address_subpremise.floor": {"surfaces": ["platform"]},
    #
    # .apartment_unit surfaces in address enriched responses.
    # vianda-platform: types/api.ts (AddressResponseSchema — apartment_unit field).
    "core.address_subpremise.apartment_unit": {"surfaces": ["platform"]},
    # --- core.user_info ---
    #
    # .first_name surfaces in user enriched responses and /users/me.
    # vianda-platform: types/api.ts (UserResponseSchema — first_name field).
    # vianda-app: ProfileContent.tsx — displayed in profile view.
    "core.user_info.first_name": {"surfaces": ["platform", "app"]},
    #
    # .last_name surfaces in user enriched responses and /users/me.
    # vianda-platform: types/api.ts (UserResponseSchema — last_name field).
    # vianda-app: ProfileContent.tsx — displayed in profile view.
    "core.user_info.last_name": {"surfaces": ["platform", "app"]},
    #
    # .email surfaces in user enriched responses and /users/me.
    # vianda-platform: types/api.ts — displayed in user management.
    # vianda-app: AuthContext.tsx — meta user data for analytics.
    "core.user_info.email": {"surfaces": ["platform", "app"]},
    #
    # .mobile_number surfaces in /users/me and user enriched responses.
    # vianda-platform: types/api.ts (UserResponseSchema — mobile_number field).
    # vianda-app: ProfileContent.tsx, AuthContext.tsx — displayed and used for analytics.
    "core.user_info.mobile_number": {"surfaces": ["platform", "app"]},
    #
    # .mobile_number_verified surfaces in user enriched responses.
    # vianda-platform: types/api.ts — displayed in user management.
    "core.user_info.mobile_number_verified": {"surfaces": ["platform"]},
    #
    # .email_verified surfaces in user enriched responses and /users/me.
    # vianda-platform: types/api.ts, pages/Users.tsx — email verified badge.
    # vianda-app: ProfileContent.tsx — triggers email verify nudge.
    "core.user_info.email_verified": {"surfaces": ["platform", "app"]},
    #
    # .role_type surfaces in user enriched responses.
    # vianda-platform: types/api.ts — displayed in user management and permission checks.
    # vianda-app: utils/jwt.ts, hooks/usePickupFlow.ts — role-based rendering.
    "core.user_info.role_type": {"surfaces": ["platform", "app"]},
    #
    # .role_name surfaces in user enriched responses.
    # vianda-platform: types/api.ts (UserResponseSchema — role_name field).
    "core.user_info.role_name": {"surfaces": ["platform"]},
    #
    # .username surfaces in user enriched responses.
    # vianda-platform: types/api.ts — displayed in user management.
    "core.user_info.username": {"surfaces": ["platform"]},
    #
    # .referral_code surfaces in /users/me/referral-code and profile responses.
    # vianda-app: api/endpoints/referrals.ts — displayed in the referral flow.
    "core.user_info.referral_code": {"surfaces": ["app"]},
    #
    # .locale surfaces in /users/me and used for API locale resolution.
    # vianda-app: api/types.ts — user locale preference.
    "core.user_info.locale": {"surfaces": ["app"]},
    #
    # .city_metadata_id surfaces in user enriched responses and employer enrollment.
    # vianda-platform: utils/formConfigs.ts (city_metadata_id selector in user form).
    # vianda-app: api/endpoints/auth.ts, api/types.ts.
    "core.user_info.city_metadata_id": {"surfaces": ["platform", "app"]},
    #
    # .market_id surfaces in user enriched responses.
    # vianda-platform: types/api.ts — market_id on user and institution enriched types.
    # vianda-app: hooks/useExploreFilters.ts — market_id for filter scoping.
    "core.user_info.market_id": {"surfaces": ["platform", "app"]},
    #
    # .workplace_group_id surfaces in /users/me and coworker coordination responses.
    # vianda-app: ProfileContent.tsx, api/types.ts — workplace group display.
    "core.user_info.workplace_group_id": {"surfaces": ["app"]},
    # --- core.employer_benefits_program ---
    #
    # .institution_entity_id surfaces in employer program enriched responses.
    # vianda-platform: types/api.ts — entity-level program display.
    "core.employer_benefits_program.institution_entity_id": {"surfaces": ["platform"]},
    #
    # .benefit_rate surfaces in employer program responses.
    # vianda-platform: types/api.ts (EmployerProgramResponseSchema), utils/formConfigs.ts.
    "core.employer_benefits_program.benefit_rate": {"surfaces": ["platform"]},
    #
    # .benefit_cap surfaces in employer program responses.
    # vianda-platform: types/api.ts, utils/formConfigs.ts — benefit cap field.
    "core.employer_benefits_program.benefit_cap": {"surfaces": ["platform"]},
    #
    # .benefit_cap_period surfaces in employer program responses.
    # vianda-platform: types/api.ts, utils/formConfigs.ts — benefit cap period selector.
    "core.employer_benefits_program.benefit_cap_period": {"surfaces": ["platform"]},
    #
    # .price_discount surfaces in employer program responses.
    # vianda-platform: types/api.ts, utils/formConfigs.ts — price discount field.
    "core.employer_benefits_program.price_discount": {"surfaces": ["platform"]},
    #
    # .minimum_monthly_fee surfaces in employer program responses.
    # vianda-platform: types/api.ts, utils/formConfigs.ts — minimum fee field.
    "core.employer_benefits_program.minimum_monthly_fee": {"surfaces": ["platform"]},
    #
    # .billing_cycle surfaces in employer program responses.
    # vianda-platform: types/api.ts, utils/columnConfigs.ts — billing cycle column.
    "core.employer_benefits_program.billing_cycle": {"surfaces": ["platform"]},
    #
    # .billing_day surfaces in employer program responses.
    # vianda-platform: types/api.ts, utils/formConfigs.ts — billing day field.
    "core.employer_benefits_program.billing_day": {"surfaces": ["platform"]},
    #
    # .billing_day_of_week surfaces in employer program responses.
    # vianda-platform: types/api.ts — billing day of week field.
    "core.employer_benefits_program.billing_day_of_week": {"surfaces": ["platform"]},
    #
    # .enrollment_mode surfaces in employer program responses.
    # vianda-platform: types/api.ts, utils/formConfigs.ts — enrollment mode selector.
    "core.employer_benefits_program.enrollment_mode": {"surfaces": ["platform"]},
    #
    # .allow_early_renewal surfaces in employer program responses.
    # vianda-platform: types/api.ts, utils/formConfigs.ts — allow early renewal toggle.
    "core.employer_benefits_program.allow_early_renewal": {"surfaces": ["platform"]},
    # --- core.lead_interest ---
    #
    # .email surfaces in LeadInterestResponseSchema for admin lead interest dashboard.
    # vianda-platform: types/api.ts (LeadInterest.email), pages/LeadInterest.tsx.
    "core.lead_interest.email": {"surfaces": ["platform"]},
    #
    # .country_code surfaces in LeadInterestResponseSchema.
    # vianda-platform: types/api.ts (LeadInterest.country_code).
    "core.lead_interest.country_code": {"surfaces": ["platform"]},
    #
    # .city_name surfaces in LeadInterestResponseSchema.
    # vianda-platform: types/api.ts (LeadInterest.city_name), pages/LeadInterest.tsx.
    "core.lead_interest.city_name": {"surfaces": ["platform"]},
    #
    # .zipcode surfaces in LeadInterestResponseSchema.
    # vianda-platform: types/api.ts (LeadInterest.zipcode).
    "core.lead_interest.zipcode": {"surfaces": ["platform"]},
    #
    # .zipcode_only surfaces in LeadInterestResponseSchema.
    # vianda-platform: types/api.ts (LeadInterest.zipcode_only).
    "core.lead_interest.zipcode_only": {"surfaces": ["platform"]},
    #
    # .interest_type surfaces in LeadInterestResponseSchema.
    # vianda-platform: types/api.ts (LeadInterest.interest_type), pages/LeadInterest.tsx.
    "core.lead_interest.interest_type": {"surfaces": ["platform"]},
    #
    # .business_name surfaces in LeadInterestResponseSchema.
    # vianda-platform: types/api.ts (LeadInterest.business_name), pages/LeadInterest.tsx.
    "core.lead_interest.business_name": {"surfaces": ["platform"]},
    #
    # .message surfaces in LeadInterestResponseSchema.
    # vianda-platform: types/api.ts (LeadInterest.message).
    "core.lead_interest.message": {"surfaces": ["platform"]},
    #
    # .employee_count_range surfaces in LeadInterestResponseSchema.
    # vianda-platform: types/api.ts — employee count range filter.
    "core.lead_interest.employee_count_range": {"surfaces": ["platform"]},
    #
    # .status surfaces in LeadInterestResponseSchema.
    # vianda-platform: types/api.ts (LeadInterest.status), pages/LeadInterest.tsx.
    "core.lead_interest.status": {"surfaces": ["platform"]},
    #
    # .source surfaces in LeadInterestResponseSchema.
    # vianda-platform: types/api.ts (LeadInterest.source).
    "core.lead_interest.source": {"surfaces": ["platform"]},
    # --- core.restaurant_lead ---
    #
    # .business_name surfaces in RestaurantLeadResponseSchema (POST /leads/restaurant-interest).
    # vianda-home: RestaurantApplicationForm.tsx submits and receives this field.
    "core.restaurant_lead.business_name": {"surfaces": ["home"]},
    #
    # .contact_email surfaces in RestaurantLeadResponseSchema.
    # vianda-home: forms that capture and confirm the contact email.
    "core.restaurant_lead.contact_email": {"surfaces": ["home"]},
    #
    # .country_code surfaces in RestaurantLeadResponseSchema.
    # vianda-home: RestaurantApplicationForm.tsx — country selection.
    "core.restaurant_lead.country_code": {"surfaces": ["home"]},
    #
    # .lead_status surfaces in RestaurantLeadResponseSchema as "lead_status".
    # vianda-home: receives confirmation of lead submission status.
    "core.restaurant_lead.lead_status": {"surfaces": ["home"]},
    #
    # .city_name surfaces in RestaurantLeadCreateSchema (submitted) and admin enriched views.
    # vianda-home: RestaurantApplicationForm.tsx — city selection.
    "core.restaurant_lead.city_name": {"surfaces": ["home"]},
    # --- core.geolocation_info ---
    #
    # .latitude surfaces in restaurant enriched responses and geolocation responses.
    # vianda-platform: types/api.ts (GeolocationResponseSchema — latitude field).
    # vianda-app: MapCenterToggle.tsx — map center coordinates.
    "core.geolocation_info.latitude": {"surfaces": ["platform", "app"]},
    #
    # .longitude surfaces in restaurant enriched responses and geolocation responses.
    # vianda-platform: types/api.ts (GeolocationResponseSchema — longitude field).
    # vianda-app: MapCenterToggle.tsx — map center coordinates.
    "core.geolocation_info.longitude": {"surfaces": ["platform", "app"]},
    #
    # .formatted_address_google surfaces as "formatted_address" in address enriched responses.
    # vianda-platform: types/api.ts (formatted_address), formConfigs.ts, QrCodeViewModal.tsx, QRCodes.tsx.
    "core.geolocation_info.formatted_address_google": {"surfaces": ["platform"]},
    # --- core.user_messaging_preferences ---
    #
    # .notify_coworker_pickup_alert surfaces in /users/me/messaging-preferences.
    # vianda-app: api/types.ts (UserMessagingPreferences) — rendered in preferences settings.
    "core.user_messaging_preferences.notify_coworker_pickup_alert": {"surfaces": ["app"]},
    #
    # .notify_plate_readiness_alert surfaces in /users/me/messaging-preferences.
    # vianda-app: api/types.ts — plate readiness push notification toggle.
    "core.user_messaging_preferences.notify_plate_readiness_alert": {"surfaces": ["app"]},
    #
    # .notify_promotions_push surfaces in /users/me/messaging-preferences.
    # vianda-app: api/types.ts — promotional push notification toggle.
    "core.user_messaging_preferences.notify_promotions_push": {"surfaces": ["app"]},
    #
    # .notify_promotions_email surfaces in /users/me/messaging-preferences.
    # vianda-app: api/types.ts — promotional email toggle.
    "core.user_messaging_preferences.notify_promotions_email": {"surfaces": ["app"]},
    #
    # .coworkers_can_see_my_orders surfaces in /users/me/messaging-preferences.
    # vianda-app: api/types.ts — coworker visibility toggle.
    "core.user_messaging_preferences.coworkers_can_see_my_orders": {"surfaces": ["app"]},
    #
    # .can_participate_in_plate_pickups surfaces in /users/me/messaging-preferences.
    # vianda-app: api/types.ts — pickup participation toggle.
    "core.user_messaging_preferences.can_participate_in_plate_pickups": {"surfaces": ["app"]},
    # --- core.workplace_group ---
    #
    # .name surfaces as "workplace_group_name" in /users/me enriched response.
    # vianda-app: ProfileContent.tsx, api/types.ts (workplace_group_name field).
    "core.workplace_group.name": {"surfaces": ["app"]},
    # --- core.ad_zone ---
    #
    # .name surfaces in AdZoneResponseSchema for the admin ad zones dashboard.
    # vianda-platform: types/api.ts (AdZoneResponseSchema — name field), pages/AdZones.tsx.
    "core.ad_zone.name": {"surfaces": ["platform"]},
    #
    # .country_code surfaces in AdZoneResponseSchema.
    # vianda-platform: types/api.ts, pages/AdZoneDetail.tsx.
    "core.ad_zone.country_code": {"surfaces": ["platform"]},
    #
    # .city_name surfaces in AdZoneResponseSchema.
    # vianda-platform: types/api.ts, pages/AdZones.tsx, pages/AdZoneDetail.tsx, AdZoneFormModal.tsx.
    "core.ad_zone.city_name": {"surfaces": ["platform"]},
    #
    # .neighborhood surfaces in AdZoneResponseSchema.
    # vianda-platform: types/api.ts, utils/columnConfigs.ts, AdZoneFormModal.tsx.
    "core.ad_zone.neighborhood": {"surfaces": ["platform"]},
    #
    # .latitude surfaces in AdZoneResponseSchema.
    # vianda-platform: types/api.ts, pages/AdZoneDetail.tsx (ZoneMap center).
    "core.ad_zone.latitude": {"surfaces": ["platform"]},
    #
    # .longitude surfaces in AdZoneResponseSchema.
    # vianda-platform: types/api.ts, pages/AdZoneDetail.tsx (ZoneMap center).
    "core.ad_zone.longitude": {"surfaces": ["platform"]},
    #
    # .radius_km surfaces in AdZoneResponseSchema.
    # vianda-platform: types/api.ts, AdZoneFormModal.tsx, pages/AdZoneDetail.tsx.
    "core.ad_zone.radius_km": {"surfaces": ["platform"]},
    #
    # .flywheel_state surfaces in AdZoneResponseSchema.
    # vianda-platform: types/api.ts (flywheel_state field), AdZoneFormModal.tsx.
    "core.ad_zone.flywheel_state": {"surfaces": ["platform"]},
    #
    # .state_changed_at surfaces in AdZoneResponseSchema.
    # vianda-platform: types/api.ts (state_changed_at field).
    "core.ad_zone.state_changed_at": {"surfaces": ["platform"]},
    #
    # .notify_me_lead_count surfaces in AdZoneResponseSchema.
    # vianda-platform: types/api.ts (notify_me_lead_count field), components/ad-zones/MetricsCards.tsx.
    "core.ad_zone.notify_me_lead_count": {"surfaces": ["platform"]},
    #
    # .active_restaurant_count surfaces in AdZoneResponseSchema.
    # vianda-platform: types/api.ts (active_restaurant_count field).
    "core.ad_zone.active_restaurant_count": {"surfaces": ["platform"]},
    #
    # .active_subscriber_count surfaces in AdZoneResponseSchema.
    # vianda-platform: types/api.ts (active_subscriber_count field).
    "core.ad_zone.active_subscriber_count": {"surfaces": ["platform"]},
    #
    # .estimated_mau surfaces in AdZoneResponseSchema.
    # vianda-platform: types/api.ts, components/ad-zones/MetricsCards.tsx — MAU display.
    "core.ad_zone.estimated_mau": {"surfaces": ["platform"]},
    #
    # .budget_allocation surfaces in AdZoneResponseSchema.
    # vianda-platform: types/api.ts (BudgetAllocation), AdZoneFormModal.tsx.
    "core.ad_zone.budget_allocation": {"surfaces": ["platform"]},
    #
    # .daily_budget_cents surfaces in AdZoneResponseSchema.
    # vianda-platform: types/api.ts (daily_budget_cents field), AdZoneFormModal.tsx.
    "core.ad_zone.daily_budget_cents": {"surfaces": ["platform"]},
    #
    # .created_by surfaces in AdZoneResponseSchema as string (operator/advisor label).
    # vianda-platform: types/api.ts (created_by field).
    "core.ad_zone.created_by": {"surfaces": ["platform"]},
    # ==========================================================================
    # customer schema
    # ==========================================================================
    #
    # B2C domain: plate selections, pickups, reviews, plans, referrals,
    # subscriptions, payment methods, and notification banners.
    #
    # Tables excluded from inventory (not in any API response):
    #   customer.credential_recovery — internal auth flow; no response schema.
    #   customer.email_change_request — internal auth flow; no response schema.
    #   customer.pending_customer_signup — transient; no response schema.
    #   customer.coworker_pickup_notification — push-only; no response schema.
    #   customer.pickup_preferences — no frontend references confirmed yet;
    #     defer to Phase 2 lint.
    #   customer.referral_config — admin-only form; over-exposure candidate.
    #
    # Uncertain / deferred (generic_name=Y — catalog hits are incidental matches
    # on common field names, not confirmed per-table frontend usage):
    #   "status" across customer tables — defer to Phase 2 lint where not
    #     confirmed below.
    #   "created_date", "modified_date", "modified_by" — admin/audit metadata,
    #     defer to Phase 2 lint.
    #
    # --- customer.plate_selection_info ---
    #
    # .kitchen_day surfaces in PlateSelectionResponseSchema and DailyOrderItemSchema.
    # vianda-platform: types/api.ts (DailyOrder.kitchen_day).
    # vianda-app: api/types.ts (PlateSelection.kitchen_day).
    "customer.plate_selection_info.kitchen_day": {"surfaces": ["platform", "app"]},
    #
    # .pickup_date surfaces in PlateSelectionResponseSchema.
    # vianda-app: api/types.ts (PlateSelection.pickup_date).
    "customer.plate_selection_info.pickup_date": {"surfaces": ["app"]},
    #
    # .pickup_time_range surfaces in PlateSelectionResponseSchema and DailyOrderItemSchema.
    # vianda-platform: types/api.ts (DailyOrder.pickup_time_range).
    # vianda-app: api/types.ts (PlateSelection.pickup_time_range).
    "customer.plate_selection_info.pickup_time_range": {"surfaces": ["platform", "app"]},
    #
    # .pickup_intent surfaces in PlateSelectionResponseSchema.
    # vianda-app: api/types.ts (PlateSelection.pickup_intent).
    "customer.plate_selection_info.pickup_intent": {"surfaces": ["app"]},
    #
    # .flexible_on_time surfaces in PlateSelectionResponseSchema.
    # vianda-app: api/types.ts (PlateSelection.flexible_on_time).
    "customer.plate_selection_info.flexible_on_time": {"surfaces": ["app"]},
    #
    # .credit surfaces in PlateSelectionResponseSchema (credit cost of this selection).
    # vianda-app: api/types.ts (PlateSelection.credit).
    "customer.plate_selection_info.credit": {"surfaces": ["app"]},
    #
    # .status surfaces in PlateSelectionResponseSchema.
    # vianda-app: api/types.ts (PlateSelection.status).
    "customer.plate_selection_info.status": {"surfaces": ["app"]},
    # --- customer.notification_banner ---
    #
    # .notification_type surfaces as "type" in AppNotification (renamed at the API layer).
    # vianda-app: api/endpoints/notifications.ts (AppNotification.type).
    "customer.notification_banner.notification_type": {"surfaces": ["app"]},
    #
    # .priority surfaces in AppNotification.
    # vianda-app: api/endpoints/notifications.ts (AppNotification.priority).
    "customer.notification_banner.priority": {"surfaces": ["app"]},
    #
    # .expires_at surfaces in AppNotification.
    # vianda-app: api/endpoints/notifications.ts (AppNotification.expires_at).
    "customer.notification_banner.expires_at": {"surfaces": ["app"]},
    #
    # .action_type surfaces as "action.type" in AppNotification (nested action object).
    # vianda-app: api/endpoints/notifications.ts (AppNotification.action.type).
    "customer.notification_banner.action_type": {"surfaces": ["app"]},
    #
    # .action_label surfaces as "action.label" in AppNotification (nested action object).
    # vianda-app: api/endpoints/notifications.ts (AppNotification.action.label).
    "customer.notification_banner.action_label": {"surfaces": ["app"]},
    # --- customer.plate_pickup_live ---
    #
    # .was_collected surfaces in PlatePickupEnrichedResponseSchema and DailyOrderItemSchema.
    # vianda-platform: types/api.ts (PlatePickupEnriched.was_collected, DailyOrder.was_collected).
    # vianda-app: api/types.ts (PlatePickup.was_collected).
    "customer.plate_pickup_live.was_collected": {"surfaces": ["platform", "app"]},
    #
    # .arrival_time surfaces in PlatePickupEnrichedResponseSchema and DailyOrderItemSchema.
    # vianda-platform: types/api.ts (PlatePickupEnriched.arrival_time, DailyOrder.arrival_time).
    # vianda-app: api/types.ts (PlatePickup.arrival_time).
    "customer.plate_pickup_live.arrival_time": {"surfaces": ["platform", "app"]},
    #
    # .completion_time surfaces in PlatePickupEnrichedResponseSchema and DailyOrderItemSchema.
    # vianda-platform: types/api.ts (PlatePickupEnriched.completion_time, DailyOrder.completion_time).
    "customer.plate_pickup_live.completion_time": {"surfaces": ["platform"]},
    #
    # .expected_completion_time surfaces in PlatePickupEnrichedResponseSchema and DailyOrderItemSchema.
    # vianda-platform: types/api.ts (DailyOrder.expected_completion_time).
    # vianda-app: api/types.ts (PlatePickup.expected_completion_time).
    "customer.plate_pickup_live.expected_completion_time": {"surfaces": ["platform", "app"]},
    #
    # .confirmation_code surfaces in PlatePickupEnrichedResponseSchema and DailyOrderItemSchema.
    # vianda-platform: types/api.ts (DailyOrder.confirmation_code, PlatePickupEnriched.confirmation_code).
    # vianda-app: api/types.ts (PlatePickup.confirmation_code).
    "customer.plate_pickup_live.confirmation_code": {"surfaces": ["platform", "app"]},
    #
    # .extensions_used surfaces in DailyOrderItemSchema.
    # vianda-platform: types/api.ts (DailyOrder.extensions_used).
    "customer.plate_pickup_live.extensions_used": {"surfaces": ["platform"]},
    #
    # .completion_type surfaces in DailyOrderItemSchema.
    # vianda-platform: types/api.ts (DailyOrder.completion_type).
    "customer.plate_pickup_live.completion_type": {"surfaces": ["platform"]},
    #
    # .qr_code_payload surfaces in PlatePickupEnrichedResponseSchema.
    # vianda-platform: types/api.ts (PlatePickupEnriched.qr_code_payload).
    # vianda-app: api/types.ts — QR code string rendered at the pickup screen.
    "customer.plate_pickup_live.qr_code_payload": {"surfaces": ["platform", "app"]},
    #
    # .handed_out_time surfaces in HandOutResponse (POST /plate-pickups/{id}/hand-out).
    # vianda-platform: types/api.ts (HandOutResponse.handed_out_time).
    "customer.plate_pickup_live.handed_out_time": {"surfaces": ["platform"]},
    # --- customer.plate_review_info ---
    #
    # .stars_rating surfaces in PlateReviewResponseSchema and PlateReviewEnriched.
    # vianda-platform: types/api.ts (PlateReviewEnriched.stars_rating).
    # vianda-app: api/types.ts (PlateReviewResponse.stars_rating).
    "customer.plate_review_info.stars_rating": {"surfaces": ["platform", "app"]},
    #
    # .portion_size_rating surfaces in PlateReviewResponseSchema and PlateReviewEnriched.
    # vianda-platform: types/api.ts (PlateReviewEnriched.portion_size_rating).
    # vianda-app: api/types.ts (PlateReviewResponse.portion_size_rating).
    "customer.plate_review_info.portion_size_rating": {"surfaces": ["platform", "app"]},
    #
    # .would_order_again surfaces in PlateReviewResponseSchema and PlateReviewEnriched.
    # vianda-platform: types/api.ts (PlateReviewEnriched.would_order_again).
    # vianda-app: api/types.ts (PlateReviewResponse.would_order_again).
    "customer.plate_review_info.would_order_again": {"surfaces": ["platform", "app"]},
    #
    # .comment surfaces in PlateReviewResponseSchema and PlateReviewEnriched.
    # vianda-platform: types/api.ts (PlateReviewEnriched.comment).
    # vianda-app: api/types.ts (PlateReviewResponse.comment).
    "customer.plate_review_info.comment": {"surfaces": ["platform", "app"]},
    # --- customer.plan_info ---
    #
    # .name surfaces in PlanResponseSchema and PlanEnrichedResponseSchema.
    # vianda-platform: types/api.ts (Plan.name, PlanEnriched.name).
    # vianda-app: api/types.ts (PlanEnriched.name).
    "customer.plan_info.name": {"surfaces": ["platform", "app"]},
    #
    # .credit surfaces in PlanResponseSchema and PlanEnrichedResponseSchema.
    # vianda-platform: types/api.ts (Plan.credit).
    # vianda-app: api/types.ts (PlanEnriched.credit).
    "customer.plan_info.credit": {"surfaces": ["platform", "app"]},
    #
    # .price surfaces in PlanResponseSchema and PlanEnrichedResponseSchema.
    # vianda-platform: types/api.ts (Plan.price).
    # vianda-app: api/types.ts (PlanEnriched.price).
    "customer.plan_info.price": {"surfaces": ["platform", "app"]},
    #
    # .credit_cost_local_currency surfaces in PlanResponseSchema and PlanEnrichedResponseSchema.
    # vianda-platform: types/api.ts (Plan.credit_cost_local_currency).
    # vianda-app: api/types.ts (PlanEnriched.credit_cost_local_currency).
    "customer.plan_info.credit_cost_local_currency": {"surfaces": ["platform", "app"]},
    #
    # .credit_cost_usd surfaces in PlanResponseSchema and PlanEnrichedResponseSchema.
    # vianda-platform: types/api.ts (Plan.credit_cost_usd).
    # vianda-app: api/types.ts (PlanEnriched.credit_cost_usd).
    "customer.plan_info.credit_cost_usd": {"surfaces": ["platform", "app"]},
    #
    # .status surfaces in PlanResponseSchema.
    # vianda-platform: types/api.ts (Plan.status).
    # vianda-app: api/types.ts (PlanEnriched.status).
    "customer.plan_info.status": {"surfaces": ["platform", "app"]},
    #
    # .rollover surfaces in PlanResponseSchema and PlanEnrichedResponseSchema.
    # vianda-platform: types/api.ts (Plan.rollover).
    # vianda-app: api/types.ts (PlanEnriched.rollover).
    "customer.plan_info.rollover": {"surfaces": ["platform", "app"]},
    #
    # .rollover_cap surfaces in PlanResponseSchema and PlanEnrichedResponseSchema.
    # vianda-platform: types/api.ts (Plan.rollover_cap).
    # vianda-app: api/types.ts (PlanEnriched.rollover_cap).
    "customer.plan_info.rollover_cap": {"surfaces": ["platform", "app"]},
    #
    # .marketing_description surfaces in PlanEnrichedResponseSchema.
    # vianda-app: api/types.ts (PlanEnriched.marketing_description).
    "customer.plan_info.marketing_description": {"surfaces": ["app"]},
    #
    # .features surfaces in PlanEnrichedResponseSchema (JSON array of feature strings).
    # vianda-app: api/types.ts (PlanEnriched.features).
    "customer.plan_info.features": {"surfaces": ["app"]},
    #
    # .cta_label surfaces in PlanEnrichedResponseSchema.
    # vianda-app: api/types.ts (PlanEnriched.cta_label).
    "customer.plan_info.cta_label": {"surfaces": ["app"]},
    # --- customer.referral_config ---
    #
    # .is_enabled surfaces in ReferralConfigResponseSchema.
    # vianda-platform: utils/formConfigs.ts (is_enabled toggle in referral config form).
    "customer.referral_config.is_enabled": {"surfaces": ["platform"]},
    #
    # .referrer_bonus_rate surfaces in ReferralConfigResponseSchema.
    # vianda-platform: utils/formConfigs.ts (referrer_bonus_rate field).
    "customer.referral_config.referrer_bonus_rate": {"surfaces": ["platform"]},
    #
    # .referrer_bonus_cap surfaces in ReferralConfigResponseSchema.
    # vianda-platform: utils/formConfigs.ts (referrer_bonus_cap field).
    "customer.referral_config.referrer_bonus_cap": {"surfaces": ["platform"]},
    #
    # .referrer_monthly_cap surfaces in ReferralConfigResponseSchema.
    # vianda-platform: utils/formConfigs.ts (referrer_monthly_cap field).
    "customer.referral_config.referrer_monthly_cap": {"surfaces": ["platform"]},
    #
    # .min_plan_price_to_qualify surfaces in ReferralConfigResponseSchema.
    # vianda-platform: utils/formConfigs.ts (min_plan_price_to_qualify field).
    "customer.referral_config.min_plan_price_to_qualify": {"surfaces": ["platform"]},
    #
    # .cooldown_days surfaces in ReferralConfigResponseSchema.
    # vianda-platform: utils/formConfigs.ts (cooldown_days field).
    "customer.referral_config.cooldown_days": {"surfaces": ["platform"]},
    #
    # .held_reward_expiry_hours surfaces in ReferralConfigResponseSchema.
    # vianda-platform: utils/formConfigs.ts (held_reward_expiry_hours field).
    "customer.referral_config.held_reward_expiry_hours": {"surfaces": ["platform"]},
    #
    # .pending_expiry_days surfaces in ReferralConfigResponseSchema.
    # vianda-platform: utils/formConfigs.ts (pending_expiry_days field).
    "customer.referral_config.pending_expiry_days": {"surfaces": ["platform"]},
    # --- customer.referral_info ---
    #
    # .referral_code_used surfaces in ReferralInfoResponseSchema.
    # vianda-app: api/endpoints/referrals.ts (Referral.referral_code_used).
    "customer.referral_info.referral_code_used": {"surfaces": ["app"]},
    #
    # .referral_status surfaces in ReferralInfoResponseSchema.
    # vianda-app: api/endpoints/referrals.ts (Referral.referral_status).
    "customer.referral_info.referral_status": {"surfaces": ["app"]},
    #
    # .bonus_credits_awarded surfaces in ReferralInfoResponseSchema.
    # vianda-app: api/endpoints/referrals.ts (Referral.bonus_credits_awarded).
    "customer.referral_info.bonus_credits_awarded": {"surfaces": ["app"]},
    #
    # .bonus_plan_price surfaces in ReferralInfoResponseSchema.
    # vianda-app: api/endpoints/referrals.ts (Referral.bonus_plan_price).
    "customer.referral_info.bonus_plan_price": {"surfaces": ["app"]},
    #
    # .bonus_rate_applied surfaces in ReferralInfoResponseSchema.
    # vianda-app: api/endpoints/referrals.ts (Referral.bonus_rate_applied).
    "customer.referral_info.bonus_rate_applied": {"surfaces": ["app"]},
    #
    # .qualified_date surfaces in ReferralInfoResponseSchema.
    # vianda-app: api/endpoints/referrals.ts (Referral.qualified_date).
    "customer.referral_info.qualified_date": {"surfaces": ["app"]},
    #
    # .rewarded_date surfaces in ReferralInfoResponseSchema.
    # vianda-app: api/endpoints/referrals.ts (Referral.rewarded_date).
    "customer.referral_info.rewarded_date": {"surfaces": ["app"]},
    # --- customer.referral_code_assignment ---
    #
    # .referral_code surfaces in /referrals/my-code and /referrals/assigned-code responses.
    # vianda-app: api/endpoints/referrals.ts — displayed in the referral share screen.
    "customer.referral_code_assignment.referral_code": {"surfaces": ["app"]},
    # --- customer.subscription_info ---
    #
    # .renewal_date surfaces in SubscriptionResponseSchema.
    # vianda-platform: types/api.ts (SubscriptionEnriched.renewal_date).
    # vianda-app: api/types.ts (Subscription.renewal_date).
    "customer.subscription_info.renewal_date": {"surfaces": ["platform", "app"]},
    #
    # .balance surfaces in SubscriptionResponseSchema.
    # vianda-platform: types/api.ts (SubscriptionEnriched.balance).
    # vianda-app: api/types.ts (Subscription.balance).
    "customer.subscription_info.balance": {"surfaces": ["platform", "app"]},
    #
    # .subscription_status surfaces in SubscriptionResponseSchema.
    # vianda-platform: types/api.ts (SubscriptionEnriched.subscription_status).
    # vianda-app: api/types.ts (Subscription.subscription_status).
    "customer.subscription_info.subscription_status": {"surfaces": ["platform", "app"]},
    #
    # .hold_start_date surfaces in SubscriptionResponseSchema.
    # vianda-platform: types/api.ts (SubscriptionEnriched.hold_start_date).
    # vianda-app: api/types.ts (Subscription.hold_start_date).
    "customer.subscription_info.hold_start_date": {"surfaces": ["platform", "app"]},
    #
    # .hold_end_date surfaces in SubscriptionResponseSchema.
    # vianda-platform: types/api.ts (SubscriptionEnriched.hold_end_date).
    # vianda-app: api/types.ts (Subscription.hold_end_date).
    "customer.subscription_info.hold_end_date": {"surfaces": ["platform", "app"]},
    #
    # .early_renewal_threshold surfaces in SubscriptionResponseSchema.
    # vianda-app: api/types.ts (Subscription.early_renewal_threshold).
    "customer.subscription_info.early_renewal_threshold": {"surfaces": ["app"]},
    # --- customer.subscription_payment ---
    #
    # .amount_cents surfaces in SubscriptionWithPaymentResponseSchema.
    # vianda-app: api/types.ts (WithPaymentResponse.amount_cents).
    "customer.subscription_payment.amount_cents": {"surfaces": ["app"]},
    #
    # .currency surfaces in SubscriptionWithPaymentResponseSchema.
    # vianda-app: api/types.ts (WithPaymentResponse.currency).
    "customer.subscription_payment.currency": {"surfaces": ["app"]},
    # --- customer.payment_method ---
    #
    # .method_type surfaces in PaymentMethodResponseSchema.
    # vianda-app: api/types.ts — payment method type rendered in the payment method list.
    "customer.payment_method.method_type": {"surfaces": ["app"]},
    #
    # .is_default surfaces in PaymentMethodResponseSchema and CustomerPaymentMethodItemSchema.
    # vianda-app: api/types.ts (PaymentMethod.is_default).
    "customer.payment_method.is_default": {"surfaces": ["app"]},
    # --- customer.external_payment_method ---
    #
    # .last4 ships via JOIN into payment_method responses (DB column on external_payment_method;
    # API field name is also "last4"). vianda-app: api/types.ts (PaymentMethod.last4).
    "customer.external_payment_method.last4": {"surfaces": ["app"]},
    #
    # .brand ships via JOIN into payment_method responses (API field name same as DB column).
    # vianda-app: api/types.ts (PaymentMethod.brand).
    "customer.external_payment_method.brand": {"surfaces": ["app"]},
    # --- customer.user_payment_provider ---
    #
    # .provider surfaces in UserPaymentProviderResponseSchema.
    # vianda-app: api/types.ts (PaymentProvider.provider).
    "customer.user_payment_provider.provider": {"surfaces": ["app"]},
}
