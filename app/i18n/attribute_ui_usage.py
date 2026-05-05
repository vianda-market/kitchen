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
    # --- ops.restaurant_lead ---
    #
    # .business_name surfaces in RestaurantLeadResponseSchema (POST /leads/restaurant-interest).
    # vianda-home: RestaurantApplicationForm.tsx submits and receives this field.
    "ops.restaurant_lead.business_name": {"surfaces": ["home"]},
    #
    # .country_code surfaces in RestaurantLeadResponseSchema.
    # vianda-home: RestaurantApplicationForm.tsx — country selection.
    "ops.restaurant_lead.country_code": {"surfaces": ["home"]},
    #
    # .city_name surfaces in RestaurantLeadCreateSchema (submitted) and admin enriched views.
    # vianda-home: RestaurantApplicationForm.tsx — city selection.
    "ops.restaurant_lead.city_name": {"surfaces": ["home"]},
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
    # ==========================================================================
    # billing schema
    # ==========================================================================
    #
    # Billing is primarily an admin/internal domain (vianda-platform). The B2C
    # app surface is modest: employer bill line context (benefit rate/cap shown
    # to employees) and supplier balance/credit values. Over-exposure candidates
    # and uncertain columns are documented below.
    #
    # Rename-at-API (Convention 4): document_storage_path → document_url on
    # billing.supplier_invoice and billing.supplier_w9. The DB column name is
    # used as the inventory key; an inline comment documents the API rename.
    #
    # Tables excluded from inventory (not in any API response):
    #   billing.client_transaction — internal accounting; no response schema.
    #   billing.institution_settlement — pipeline-internal; no API endpoint.
    #
    # Over-exposure candidates (ships in response but zero confirmed frontend
    # references — not inventoried, flagged for Phase 2 lint):
    #   billing.client_bill_info: client_bill_id, subscription_payment_id,
    #     subscription_id, user_id, plan_id, currency_metadata_id, amount,
    #     currency_code, is_archived, status, created_date, modified_by,
    #     modified_date
    #   billing.bill_invoice_match: match_id, institution_bill_id,
    #     supplier_invoice_id, matched_amount, matched_by, matched_at
    #
    # Uncertain / deferred (generic_name=Y — catalog hits are incidental matches
    # on common field names, not confirmed per-table frontend usage):
    #   "status" across all billing tables — defer to Phase 2 lint.
    #   "amount" across all billing tables — defer to Phase 2 lint.
    #   "is_archived", "created_date", "modified_date", "modified_by" —
    #     admin/audit metadata, defer to Phase 2 lint.
    #
    # --- billing.discretionary_info ---
    #
    # .category surfaces in DiscretionaryResponseSchema and
    # DiscretionaryEnrichedResponseSchema.
    # vianda-platform: types/api.ts — category badge in the discretionary dashboard.
    "billing.discretionary_info.category": {"surfaces": ["platform"]},
    #
    # .reason surfaces in DiscretionaryResponseSchema and
    # DiscretionaryEnrichedResponseSchema.
    # vianda-platform: types/api.ts — free-form explanation shown in admin review view.
    # vianda-app: types/api.ts (3 hits — supplier discretionary context).
    "billing.discretionary_info.reason": {"surfaces": ["platform", "app"]},
    #
    # .comment surfaces in DiscretionaryResponseSchema and
    # DiscretionaryEnrichedResponseSchema.
    # vianda-platform: types/api.ts — admin comment field in discretionary detail view.
    # vianda-app: types/api.ts (4 hits — supplementary note context).
    "billing.discretionary_info.comment": {"surfaces": ["platform", "app"]},
    # --- billing.discretionary_resolution_info ---
    #
    # .resolution surfaces in DiscretionaryResolutionResponseSchema.
    # vianda-platform: types/api.ts — approval outcome shown in the resolution panel.
    "billing.discretionary_resolution_info.resolution": {"surfaces": ["platform"]},
    #
    # .resolution_comment surfaces in DiscretionaryResolutionResponseSchema.
    # vianda-platform: types/api.ts — admin note explaining the approval/rejection decision.
    "billing.discretionary_resolution_info.resolution_comment": {"surfaces": ["platform"]},
    # --- billing.restaurant_transaction ---
    #
    # .credit surfaces in RestaurantTransactionResponseSchema.
    # vianda-platform: types/api.ts — credit amount in restaurant transaction list.
    # vianda-app: types/api.ts (7 hits — credit value rendered in transaction context).
    "billing.restaurant_transaction.credit": {"surfaces": ["platform", "app"]},
    #
    # .no_show_discount surfaces in RestaurantTransactionResponseSchema.
    # vianda-platform: types/api.ts — no-show discount applied to this transaction.
    "billing.restaurant_transaction.no_show_discount": {"surfaces": ["platform"]},
    #
    # .was_collected surfaces in RestaurantTransactionResponseSchema.
    # vianda-platform: types/api.ts — pickup confirmation flag in transaction detail.
    "billing.restaurant_transaction.was_collected": {"surfaces": ["platform"]},
    #
    # .arrival_time surfaces in RestaurantTransactionResponseSchema.
    # vianda-platform: types/api.ts — customer arrival time in transaction detail.
    # vianda-app: types/api.ts (2 hits — arrival time displayed in pickup context).
    "billing.restaurant_transaction.arrival_time": {"surfaces": ["platform", "app"]},
    #
    # .completion_time surfaces in RestaurantTransactionResponseSchema.
    # vianda-platform: types/api.ts — pickup completion timestamp in transaction list.
    "billing.restaurant_transaction.completion_time": {"surfaces": ["platform"]},
    #
    # .expected_completion_time surfaces in RestaurantTransactionResponseSchema.
    # vianda-platform: types/api.ts — expected pickup window in admin transaction view.
    "billing.restaurant_transaction.expected_completion_time": {"surfaces": ["platform"]},
    #
    # .transaction_type surfaces in RestaurantTransactionResponseSchema.
    # vianda-platform: types/api.ts — transaction classification in the restaurant billing view.
    "billing.restaurant_transaction.transaction_type": {"surfaces": ["platform"]},
    #
    # .final_amount surfaces in RestaurantTransactionResponseSchema.
    # vianda-platform: types/api.ts — net payout amount after discounts in transaction detail.
    "billing.restaurant_transaction.final_amount": {"surfaces": ["platform"]},
    #
    # .ordered_timestamp surfaces in RestaurantTransactionResponseSchema.
    # vianda-platform: types/api.ts — when the order was placed; shown in transaction timeline.
    "billing.restaurant_transaction.ordered_timestamp": {"surfaces": ["platform"]},
    # --- billing.restaurant_balance_info ---
    #
    # .balance surfaces in RestaurantBalanceResponseSchema and
    # RestaurantBalanceEnrichedResponseSchema.
    # vianda-platform: types/api.ts — pending payout balance on the restaurant balance page.
    # vianda-app: types/api.ts (8 hits — balance displayed in supplier billing context).
    "billing.restaurant_balance_info.balance": {"surfaces": ["platform", "app"]},
    #
    # .transaction_count surfaces in RestaurantBalanceResponseSchema.
    # vianda-platform: types/api.ts — number of unpaid transactions contributing to the balance.
    "billing.restaurant_balance_info.transaction_count": {"surfaces": ["platform"]},
    # --- billing.institution_bill_info ---
    #
    # .period_start surfaces in InstitutionBillEnrichedResponseSchema.
    # vianda-platform: types/api.ts — billing period start date in institution bill view.
    "billing.institution_bill_info.period_start": {"surfaces": ["platform"]},
    #
    # .period_end surfaces in InstitutionBillEnrichedResponseSchema.
    # vianda-platform: types/api.ts — billing period end date in institution bill view.
    "billing.institution_bill_info.period_end": {"surfaces": ["platform"]},
    #
    # .resolution surfaces in InstitutionBillEnrichedResponseSchema.
    # vianda-platform: types/api.ts — bill payment state (pending/invoiced/paid/cancelled).
    "billing.institution_bill_info.resolution": {"surfaces": ["platform"]},
    #
    # .transaction_count surfaces in InstitutionBillEnrichedResponseSchema.
    # vianda-platform: types/api.ts — number of transactions included in this bill.
    "billing.institution_bill_info.transaction_count": {"surfaces": ["platform"]},
    # --- billing.institution_bill_payout ---
    #
    # .provider surfaces in InstitutionBillPayoutResponseSchema and
    # BillPayoutEnrichedResponseSchema.
    # vianda-platform: types/api.ts — payout provider identifier in the payout detail view.
    # vianda-app: types/api.ts (9 hits — provider rendered in supplier billing context).
    "billing.institution_bill_payout.provider": {"surfaces": ["platform", "app"]},
    # --- billing.market_payout_aggregator ---
    #
    # .aggregator surfaces in MarketPayoutAggregatorResponseSchema.
    # vianda-platform: types/api.ts — payment aggregator name in market billing config.
    "billing.market_payout_aggregator.aggregator": {"surfaces": ["platform"]},
    #
    # .require_invoice surfaces in MarketPayoutAggregatorResponseSchema.
    # vianda-platform: types/api.ts — invoice requirement toggle in market billing settings.
    "billing.market_payout_aggregator.require_invoice": {"surfaces": ["platform"]},
    #
    # .max_unmatched_bill_days surfaces in MarketPayoutAggregatorResponseSchema.
    # vianda-platform: types/api.ts — max unmatched bill age threshold in billing config.
    "billing.market_payout_aggregator.max_unmatched_bill_days": {"surfaces": ["platform"]},
    #
    # .kitchen_open_time surfaces in MarketPayoutAggregatorResponseSchema.
    # vianda-platform: types/api.ts — market default kitchen open time in billing settings.
    "billing.market_payout_aggregator.kitchen_open_time": {"surfaces": ["platform"]},
    #
    # .kitchen_close_time surfaces in MarketPayoutAggregatorResponseSchema.
    # vianda-platform: types/api.ts — market default kitchen close time in billing settings.
    "billing.market_payout_aggregator.kitchen_close_time": {"surfaces": ["platform"]},
    # --- billing.supplier_invoice ---
    #
    # .country_code surfaces in SupplierInvoiceResponseSchema and
    # SupplierInvoiceEnrichedResponseSchema.
    # vianda-platform: types/api.ts — country of invoice shown in invoice list and detail.
    # vianda-app: types/api.ts — country context in supplier invoice flow.
    "billing.supplier_invoice.country_code": {"surfaces": ["platform", "app"]},
    #
    # .invoice_type surfaces in SupplierInvoiceResponseSchema.
    # vianda-platform: types/api.ts — invoice type badge in invoice list.
    "billing.supplier_invoice.invoice_type": {"surfaces": ["platform"]},
    #
    # .external_invoice_number surfaces in SupplierInvoiceResponseSchema.
    # vianda-platform: types/api.ts — supplier-assigned invoice number in invoice detail.
    "billing.supplier_invoice.external_invoice_number": {"surfaces": ["platform"]},
    #
    # .issued_date surfaces in SupplierInvoiceResponseSchema.
    # vianda-platform: types/api.ts — invoice issue date shown in invoice list and detail.
    "billing.supplier_invoice.issued_date": {"surfaces": ["platform"]},
    #
    # .rejection_reason surfaces in SupplierInvoiceResponseSchema.
    # vianda-platform: types/api.ts — admin-entered reason when an invoice is rejected.
    "billing.supplier_invoice.rejection_reason": {"surfaces": ["platform"]},
    #
    # .document_storage_path surfaces as "document_url" in SupplierInvoiceResponseSchema
    # (renamed at the response layer — DB path converted to a GCS signed URL).
    # vianda-platform: types/api.ts — document_url link to view/download the invoice PDF.
    "billing.supplier_invoice.document_storage_path": {"surfaces": ["platform"]},
    #
    # .tax_amount surfaces in SupplierInvoiceResponseSchema.
    # vianda-platform: types/api.ts — tax amount shown in invoice detail for compliance review.
    "billing.supplier_invoice.tax_amount": {"surfaces": ["platform"]},
    #
    # .tax_rate surfaces in SupplierInvoiceResponseSchema.
    # vianda-platform: types/api.ts — tax rate shown in invoice detail for compliance review.
    "billing.supplier_invoice.tax_rate": {"surfaces": ["platform"]},
    # --- billing.supplier_invoice_ar ---
    #
    # .cae_code surfaces as nested ar_details.cae_code in SupplierInvoiceResponseSchema.
    # vianda-platform: types/api.ts — AFIP CAE code shown in AR invoice detail.
    "billing.supplier_invoice_ar.cae_code": {"surfaces": ["platform"]},
    #
    # .cae_expiry_date surfaces as nested ar_details.cae_expiry_date.
    # vianda-platform: types/api.ts — CAE expiry date shown in AR invoice detail.
    "billing.supplier_invoice_ar.cae_expiry_date": {"surfaces": ["platform"]},
    #
    # .afip_point_of_sale surfaces as nested ar_details.afip_point_of_sale.
    # vianda-platform: types/api.ts — AFIP punto de venta shown in AR invoice detail.
    "billing.supplier_invoice_ar.afip_point_of_sale": {"surfaces": ["platform"]},
    #
    # .supplier_cuit surfaces as nested ar_details.supplier_cuit.
    # vianda-platform: types/api.ts — supplier CUIT shown in AR invoice detail.
    "billing.supplier_invoice_ar.supplier_cuit": {"surfaces": ["platform"]},
    #
    # .recipient_cuit surfaces as nested ar_details.recipient_cuit.
    # vianda-platform: types/api.ts — recipient CUIT (Vianda) shown in AR invoice detail.
    "billing.supplier_invoice_ar.recipient_cuit": {"surfaces": ["platform"]},
    #
    # .afip_document_type surfaces as nested ar_details.afip_document_type.
    # vianda-platform: types/api.ts — AFIP document type (A/B/C) shown in AR invoice detail.
    "billing.supplier_invoice_ar.afip_document_type": {"surfaces": ["platform"]},
    # --- billing.supplier_invoice_pe ---
    #
    # .sunat_serie surfaces as nested pe_details.sunat_serie in SupplierInvoiceResponseSchema.
    # vianda-platform: types/api.ts — SUNAT serie shown in PE invoice detail.
    "billing.supplier_invoice_pe.sunat_serie": {"surfaces": ["platform"]},
    #
    # .sunat_correlativo surfaces as nested pe_details.sunat_correlativo.
    # vianda-platform: types/api.ts — SUNAT correlativo shown in PE invoice detail.
    "billing.supplier_invoice_pe.sunat_correlativo": {"surfaces": ["platform"]},
    #
    # .cdr_status surfaces as nested pe_details.cdr_status.
    # vianda-platform: types/api.ts — CDR validation status shown in PE invoice detail.
    "billing.supplier_invoice_pe.cdr_status": {"surfaces": ["platform"]},
    #
    # .supplier_ruc surfaces as nested pe_details.supplier_ruc.
    # vianda-platform: types/api.ts — supplier RUC shown in PE invoice detail.
    "billing.supplier_invoice_pe.supplier_ruc": {"surfaces": ["platform"]},
    #
    # .recipient_ruc surfaces as nested pe_details.recipient_ruc.
    # vianda-platform: types/api.ts — recipient RUC (Vianda) shown in PE invoice detail.
    "billing.supplier_invoice_pe.recipient_ruc": {"surfaces": ["platform"]},
    # --- billing.supplier_invoice_us ---
    #
    # .tax_year surfaces as nested us_details.tax_year in SupplierInvoiceResponseSchema.
    # vianda-platform: types/api.ts — tax year shown in US invoice detail (1099-NEC context).
    "billing.supplier_invoice_us.tax_year": {"surfaces": ["platform"]},
    # --- billing.supplier_w9 ---
    #
    # .legal_name surfaces in SupplierW9ResponseSchema.
    # vianda-platform: types/api.ts — legal entity name shown in W-9 detail view.
    "billing.supplier_w9.legal_name": {"surfaces": ["platform"]},
    #
    # .business_name surfaces in SupplierW9ResponseSchema.
    # vianda-platform: types/api.ts — DBA / trade name shown in W-9 detail.
    "billing.supplier_w9.business_name": {"surfaces": ["platform"]},
    #
    # .tax_classification surfaces in SupplierW9ResponseSchema.
    # vianda-platform: types/api.ts — IRS entity tax classification shown in W-9 detail.
    "billing.supplier_w9.tax_classification": {"surfaces": ["platform"]},
    #
    # .ein_last_four surfaces in SupplierW9ResponseSchema.
    # vianda-platform: types/api.ts — last 4 digits of EIN/SSN shown in W-9 detail (masked).
    "billing.supplier_w9.ein_last_four": {"surfaces": ["platform"]},
    #
    # .address_line surfaces in SupplierW9ResponseSchema.
    # vianda-platform: types/api.ts — US mailing address shown in W-9 detail.
    "billing.supplier_w9.address_line": {"surfaces": ["platform"]},
    #
    # .document_storage_path surfaces as "document_url" in SupplierW9ResponseSchema
    # (renamed at the response layer — DB path converted to a GCS signed URL).
    # vianda-platform: types/api.ts — document_url link to download the W-9 PDF.
    "billing.supplier_w9.document_storage_path": {"surfaces": ["platform"]},
    #
    # .collected_at surfaces in SupplierW9ResponseSchema.
    # vianda-platform: types/api.ts — timestamp when the W-9 was submitted.
    "billing.supplier_w9.collected_at": {"surfaces": ["platform"]},
    # --- billing.employer_bill ---
    #
    # .billing_period_start surfaces in EmployerBillResponseSchema.
    # vianda-platform: types/api.ts — employer billing period start in employer bill view.
    "billing.employer_bill.billing_period_start": {"surfaces": ["platform"]},
    #
    # .billing_period_end surfaces in EmployerBillResponseSchema.
    # vianda-platform: types/api.ts — employer billing period end in employer bill view.
    "billing.employer_bill.billing_period_end": {"surfaces": ["platform"]},
    #
    # .billing_cycle surfaces in EmployerBillResponseSchema.
    # vianda-platform: types/api.ts — billing cycle (monthly/weekly) shown in employer bill.
    "billing.employer_bill.billing_cycle": {"surfaces": ["platform"]},
    #
    # .total_renewal_events surfaces in EmployerBillResponseSchema.
    # vianda-platform: types/api.ts — total subscription renewals in this billing period.
    "billing.employer_bill.total_renewal_events": {"surfaces": ["platform"]},
    #
    # .gross_employer_share surfaces in EmployerBillResponseSchema.
    # vianda-platform: types/api.ts — gross subsidy amount before discounts in employer bill.
    "billing.employer_bill.gross_employer_share": {"surfaces": ["platform"]},
    #
    # .price_discount surfaces in EmployerBillResponseSchema.
    # vianda-platform: types/api.ts — discount percentage applied to employer billing.
    "billing.employer_bill.price_discount": {"surfaces": ["platform"]},
    #
    # .discounted_amount surfaces in EmployerBillResponseSchema.
    # vianda-platform: types/api.ts — subsidy amount after price discount applied.
    "billing.employer_bill.discounted_amount": {"surfaces": ["platform"]},
    #
    # .minimum_fee_applied surfaces in EmployerBillResponseSchema.
    # vianda-platform: types/api.ts — flag indicating minimum monthly fee was charged.
    "billing.employer_bill.minimum_fee_applied": {"surfaces": ["platform"]},
    #
    # .billed_amount surfaces in EmployerBillResponseSchema.
    # vianda-platform: types/api.ts — final invoiced amount shown in employer bill detail.
    "billing.employer_bill.billed_amount": {"surfaces": ["platform"]},
    #
    # .payment_status surfaces in EmployerBillResponseSchema.
    # vianda-platform: types/api.ts — Stripe invoice payment status in employer bill view.
    "billing.employer_bill.payment_status": {"surfaces": ["platform"]},
    # --- billing.employer_bill_line ---
    #
    # .plan_price surfaces in EmployerBillLineResponseSchema.
    # vianda-platform: types/api.ts — plan subscription price at renewal time.
    # vianda-app: types/api.ts (1 hit — plan price shown in employee benefit context).
    "billing.employer_bill_line.plan_price": {"surfaces": ["platform", "app"]},
    #
    # .benefit_rate surfaces in EmployerBillLineResponseSchema.
    # vianda-platform: types/api.ts — employer subsidy rate (%) applied to this line.
    # vianda-app: types/api.ts (1 hit — benefit rate in employee benefit summary).
    "billing.employer_bill_line.benefit_rate": {"surfaces": ["platform", "app"]},
    #
    # .benefit_cap surfaces in EmployerBillLineResponseSchema.
    # vianda-platform: types/api.ts — benefit cap applied at renewal for this employee.
    # vianda-app: types/api.ts (1 hit — cap shown in employee benefit context).
    "billing.employer_bill_line.benefit_cap": {"surfaces": ["platform", "app"]},
    #
    # .benefit_cap_period surfaces in EmployerBillLineResponseSchema.
    # vianda-platform: types/api.ts — period for the benefit cap (monthly/annual).
    # vianda-app: types/api.ts (1 hit — cap period shown in employee benefit summary).
    "billing.employer_bill_line.benefit_cap_period": {"surfaces": ["platform", "app"]},
    #
    # .employee_benefit surfaces in EmployerBillLineResponseSchema.
    # vianda-platform: types/api.ts — actual subsidy amount charged to employer per renewal.
    "billing.employer_bill_line.employee_benefit": {"surfaces": ["platform"]},
    #
    # .renewal_date surfaces in EmployerBillLineResponseSchema.
    # vianda-platform: types/api.ts — date of the subscription renewal event for this line.
    # vianda-app: types/api.ts (4 hits — renewal date shown in employee benefit history).
    "billing.employer_bill_line.renewal_date": {"surfaces": ["platform", "app"]},
    # --- billing.supplier_terms ---
    #
    # .no_show_discount surfaces in SupplierTermsResponseSchema.
    # vianda-platform: types/api.ts — no-show penalty percentage in supplier terms settings.
    "billing.supplier_terms.no_show_discount": {"surfaces": ["platform"]},
    #
    # .payment_frequency surfaces in SupplierTermsResponseSchema.
    # vianda-platform: types/api.ts — payout frequency setting in supplier terms.
    "billing.supplier_terms.payment_frequency": {"surfaces": ["platform"]},
    #
    # .kitchen_open_time surfaces in SupplierTermsResponseSchema.
    # vianda-platform: types/api.ts — supplier-level kitchen open time override.
    "billing.supplier_terms.kitchen_open_time": {"surfaces": ["platform"]},
    #
    # .kitchen_close_time surfaces in SupplierTermsResponseSchema.
    # vianda-platform: types/api.ts — supplier-level kitchen close time override.
    "billing.supplier_terms.kitchen_close_time": {"surfaces": ["platform"]},
    #
    # .require_invoice surfaces in SupplierTermsResponseSchema.
    # vianda-platform: types/api.ts — invoice requirement override at supplier level.
    "billing.supplier_terms.require_invoice": {"surfaces": ["platform"]},
    #
    # .invoice_hold_days surfaces in SupplierTermsResponseSchema.
    # vianda-platform: types/api.ts — days to hold payout pending invoice submission.
    "billing.supplier_terms.invoice_hold_days": {"surfaces": ["platform"]},
    # ==========================================================================
    # ops schema
    # ==========================================================================
    # --- ops.institution_entity_info ---
    #
    # .institution_entity_id surfaces in InstitutionEntityResponseSchema.
    # vianda-platform: types/api.ts (InstitutionEntityResponseSchema.institution_entity_id).
    "ops.institution_entity_info.institution_entity_id": {"surfaces": ["platform"]},
    #
    # .institution_id surfaces in InstitutionEntityResponseSchema.
    # vianda-platform: types/api.ts — institution_id field on entity responses.
    # vianda-app: api/types.ts (employer entity context).
    "ops.institution_entity_info.institution_id": {"surfaces": ["platform", "app"]},
    #
    # .address_id surfaces in InstitutionEntityResponseSchema.
    # vianda-platform: types/api.ts — address_id field on entity responses.
    # vianda-app: api/types.ts — used in employer address forms.
    "ops.institution_entity_info.address_id": {"surfaces": ["platform", "app"]},
    #
    # .currency_metadata_id surfaces in InstitutionEntityResponseSchema.
    # vianda-platform: types/api.ts (InstitutionEntityResponseSchema.currency_metadata_id).
    "ops.institution_entity_info.currency_metadata_id": {"surfaces": ["platform"]},
    #
    # .tax_id surfaces in InstitutionEntityResponseSchema.
    # vianda-platform: types/api.ts — rendered in entity setup and detail forms.
    "ops.institution_entity_info.tax_id": {"surfaces": ["platform"]},
    #
    # .name surfaces in InstitutionEntityResponseSchema.
    # vianda-platform: types/api.ts — entity name shown in supplier/employer management.
    # vianda-app: api/types.ts — employer entity name in enrollment.
    "ops.institution_entity_info.name": {"surfaces": ["platform", "app"]},
    #
    # .payout_onboarding_status surfaces in InstitutionEntityResponseSchema.
    # vianda-platform: types/api.ts — payout onboarding status badge in entity management.
    "ops.institution_entity_info.payout_onboarding_status": {"surfaces": ["platform"]},
    #
    # .email_domain surfaces in InstitutionEntityResponseSchema.
    # vianda-platform: types/api.ts — email domain field in employer entity detail.
    "ops.institution_entity_info.email_domain": {"surfaces": ["platform"]},
    #
    # .status surfaces in InstitutionEntityResponseSchema.
    # vianda-platform: types/api.ts — status field in entity management UIs.
    # vianda-app: api/types.ts — entity status for enrollment eligibility checks.
    "ops.institution_entity_info.status": {"surfaces": ["platform", "app"]},
    # --- ops.cuisine ---
    #
    # .cuisine_id surfaces in CuisineResponseSchema and restaurant enriched responses.
    # vianda-home: pages that render cuisine_id for filtering (9 home hits).
    "ops.cuisine.cuisine_id": {"surfaces": ["home"]},
    #
    # .cuisine_name surfaces in CuisineResponseSchema.
    # vianda-home: cuisine display in restaurant cards and filter chips (6 home hits).
    # vianda-platform: cuisine selector in restaurant forms (1 hit).
    "ops.cuisine.cuisine_name": {"surfaces": ["platform", "home"]},
    #
    # .slug surfaces in CuisineResponseSchema.
    # vianda-platform: cuisine slug in admin management (2 hits).
    # vianda-app: api/types.ts (cuisine slug for filtering).
    "ops.cuisine.slug": {"surfaces": ["platform", "app"]},
    #
    # .description surfaces in CuisineResponseSchema.
    # vianda-platform: cuisine description in admin detail.
    # vianda-app: cuisine description in explore filter detail.
    "ops.cuisine.description": {"surfaces": ["platform", "app"]},
    #
    # .status surfaces in CuisineResponseSchema.
    # vianda-platform: status column in cuisine management.
    # vianda-app: status for filtering active cuisines.
    "ops.cuisine.status": {"surfaces": ["platform", "app"]},
    # --- ops.restaurant_info ---
    #
    # .restaurant_id surfaces in RestaurantResponseSchema and all enriched restaurant responses.
    # vianda-platform: types/api.ts (restaurant_id field on many schemas).
    # vianda-app: api/types.ts (restaurant_id used in explore, pickup, and review flows).
    # vianda-home: restaurant pages reference restaurant_id.
    "ops.restaurant_info.restaurant_id": {"surfaces": ["platform", "app", "home"]},
    #
    # .institution_id surfaces in RestaurantResponseSchema.
    # vianda-platform: types/api.ts — institution_id on restaurant responses.
    # vianda-app: api/types.ts — employer/supplier context.
    "ops.restaurant_info.institution_id": {"surfaces": ["platform", "app"]},
    #
    # .institution_entity_id surfaces in RestaurantResponseSchema.
    # vianda-platform: types/api.ts — entity-level restaurant grouping in admin UIs.
    "ops.restaurant_info.institution_entity_id": {"surfaces": ["platform"]},
    #
    # .address_id surfaces in RestaurantResponseSchema.
    # vianda-platform: types/api.ts — address_id field for map and detail views.
    # vianda-app: api/types.ts — restaurant address used in pickup navigation.
    "ops.restaurant_info.address_id": {"surfaces": ["platform", "app"]},
    #
    # .name surfaces in RestaurantResponseSchema and all enriched responses.
    # vianda-platform: types/api.ts — restaurant name shown in admin and explore.
    # vianda-app: api/types.ts — rendered in restaurant cards and pickup screens.
    # vianda-home: restaurant name on marketing and detail pages.
    "ops.restaurant_info.name": {"surfaces": ["platform", "app", "home"]},
    #
    # .pickup_instructions surfaces in RestaurantResponseSchema.
    # vianda-platform: types/api.ts (1 hit).
    # vianda-app: api/types.ts — rendered on the pickup screen (3 hits).
    "ops.restaurant_info.pickup_instructions": {"surfaces": ["platform", "app"]},
    #
    # .tagline surfaces in RestaurantResponseSchema as "tagline".
    # vianda-home: restaurant cards and detail pages (6 home hits).
    "ops.restaurant_info.tagline": {"surfaces": ["home"]},
    #
    # .cover_image_url surfaces in RestaurantResponseSchema.
    # vianda-home: restaurant card images (2 home hits).
    "ops.restaurant_info.cover_image_url": {"surfaces": ["home"]},
    #
    # .average_rating surfaces in RestaurantResponseSchema.
    # vianda-platform: types/api.ts — rating column in restaurant list (3 hits).
    # vianda-app: api/types.ts — star rating on restaurant cards (1 hit).
    # vianda-home: rating display on restaurant detail page (2 hits).
    "ops.restaurant_info.average_rating": {"surfaces": ["platform", "app", "home"]},
    #
    # .review_count surfaces in RestaurantResponseSchema.
    # vianda-platform: types/api.ts (3 hits).
    # vianda-app: api/types.ts (1 hit).
    # vianda-home: review count displayed on restaurant detail page (2 hits).
    "ops.restaurant_info.review_count": {"surfaces": ["platform", "app", "home"]},
    #
    # .verified_badge surfaces in RestaurantResponseSchema.
    # vianda-home: verified badge icon on restaurant detail (1 hit).
    "ops.restaurant_info.verified_badge": {"surfaces": ["home"]},
    #
    # .spotlight_label surfaces in RestaurantResponseSchema as "spotlight_label".
    # vianda-home: promotional badge on restaurant cards (1 hit).
    "ops.restaurant_info.spotlight_label": {"surfaces": ["home"]},
    #
    # .member_perks surfaces in RestaurantResponseSchema as "member_perks".
    # vianda-home: perks list on restaurant detail page (1 hit).
    "ops.restaurant_info.member_perks": {"surfaces": ["home"]},
    #
    # .kitchen_open_time surfaces in RestaurantResponseSchema.
    # vianda-platform: types/api.ts — kitchen hours in admin restaurant detail (3 hits).
    "ops.restaurant_info.kitchen_open_time": {"surfaces": ["platform"]},
    #
    # .kitchen_close_time surfaces in RestaurantResponseSchema.
    # vianda-platform: types/api.ts — kitchen hours in admin restaurant detail (3 hits).
    "ops.restaurant_info.kitchen_close_time": {"surfaces": ["platform"]},
    #
    # .location surfaces in RestaurantResponseSchema as a GeoJSON or coordinate pair.
    # vianda-platform: types/api.ts — map rendering in restaurant detail.
    # vianda-app: api/types.ts — restaurant map pin in explore and pickup.
    "ops.restaurant_info.location": {"surfaces": ["platform", "app"]},
    #
    # .status surfaces in RestaurantResponseSchema.
    # vianda-platform: types/api.ts — status column in restaurant management.
    # vianda-app: api/types.ts — restaurant status used to show/hide in explore.
    "ops.restaurant_info.status": {"surfaces": ["platform", "app"]},
    # --- ops.cuisine_suggestion ---
    #
    # .restaurant_id surfaces in CuisineSuggestionResponseSchema.
    # vianda-platform: types/api.ts — restaurant context in suggestion review.
    # vianda-app: api/types.ts — suggestion list by restaurant.
    "ops.cuisine_suggestion.restaurant_id": {"surfaces": ["platform", "app"]},
    #
    # .status surfaces in CuisineSuggestionResponseSchema.
    # vianda-platform: types/api.ts — status filter in suggestion management.
    # vianda-app: api/types.ts — suggestion status displayed to supplier.
    "ops.cuisine_suggestion.status": {"surfaces": ["platform", "app"]},
    # --- ops.qr_code ---
    #
    # .qr_code_id surfaces in QrCodeResponseSchema.
    # vianda-platform: types/api.ts — QR code ID in kiosk management (4 hits).
    # vianda-app: api/types.ts — QR code reference in pickup flow (7 hits).
    "ops.qr_code.qr_code_id": {"surfaces": ["platform", "app"]},
    #
    # .restaurant_id surfaces in QrCodeResponseSchema.
    # vianda-platform: types/api.ts — restaurant scoping in QR code management.
    # vianda-app: api/types.ts.
    "ops.qr_code.restaurant_id": {"surfaces": ["platform", "app"]},
    #
    # .qr_code_payload surfaces in QrCodeResponseSchema.
    # vianda-platform: types/api.ts — payload rendered in QR management modal (1 hit).
    "ops.qr_code.qr_code_payload": {"surfaces": ["platform"]},
    #
    # .qr_code_image_url surfaces in QrCodeResponseSchema.
    # vianda-platform: types/api.ts — QR image URL displayed in admin kiosk management (3 hits).
    "ops.qr_code.qr_code_image_url": {"surfaces": ["platform"]},
    #
    # .status surfaces in QrCodeResponseSchema.
    # vianda-platform: types/api.ts — status column in QR code management.
    # vianda-app: api/types.ts.
    "ops.qr_code.status": {"surfaces": ["platform", "app"]},
    # --- ops.product_info ---
    #
    # .product_id surfaces in ProductResponseSchema and enriched plate responses.
    # vianda-platform: types/api.ts — product_id in admin product management (4 hits).
    # vianda-app: api/types.ts (1 hit).
    "ops.product_info.product_id": {"surfaces": ["platform", "app"]},
    #
    # .institution_id surfaces in ProductResponseSchema.
    # vianda-platform: types/api.ts — institution scoping for product management (28 hits).
    # vianda-app: api/types.ts (2 hits).
    "ops.product_info.institution_id": {"surfaces": ["platform", "app"]},
    #
    # .name surfaces in ProductResponseSchema and plate enriched responses.
    # vianda-platform: types/api.ts — product name in admin management.
    # vianda-app: api/types.ts — plate/product name displayed to consumers.
    "ops.product_info.name": {"surfaces": ["platform", "app"]},
    #
    # .ingredients surfaces in ProductResponseSchema.
    # vianda-platform: types/api.ts — ingredient list in product detail (7 hits).
    # vianda-app: api/types.ts — ingredient text on plate detail screen (3 hits).
    "ops.product_info.ingredients": {"surfaces": ["platform", "app"]},
    #
    # .description surfaces in ProductResponseSchema.
    # vianda-platform: types/api.ts — product description in admin management.
    # vianda-app: api/types.ts — plate description on explore and detail screens.
    "ops.product_info.description": {"surfaces": ["platform", "app"]},
    #
    # .dietary surfaces in ProductResponseSchema.
    # vianda-platform: types/api.ts — dietary filter chips in admin product list (5 hits).
    # vianda-app: api/types.ts — dietary badges on plate cards (1 hit).
    "ops.product_info.dietary": {"surfaces": ["platform", "app"]},
    #
    # NOTE: image_url and image_thumbnail_url were removed from ops.product_info
    # as part of image-pipeline-uploads-atomic. Image data is now served via
    # ops.image_asset (GET /api/v1/uploads/{image_asset_id}).
    #
    # .status surfaces in ProductResponseSchema.
    # vianda-platform: types/api.ts — status column in product management.
    # vianda-app: api/types.ts — product/plate visibility.
    "ops.product_info.status": {"surfaces": ["platform", "app"]},
    # --- ops.plate_info ---
    #
    # .plate_id surfaces in PlateResponseSchema and PlateSelectionResponseSchema.
    # vianda-platform: types/api.ts — plate_id in admin plate management and daily orders (7 hits).
    # vianda-app: api/types.ts — plate_id in selection and pickup flows (13 hits).
    "ops.plate_info.plate_id": {"surfaces": ["platform", "app"]},
    #
    # .product_id surfaces in PlateResponseSchema.
    # vianda-platform: types/api.ts — product_id for linking plate to product (4 hits).
    # vianda-app: api/types.ts (1 hit).
    "ops.plate_info.product_id": {"surfaces": ["platform", "app"]},
    #
    # .restaurant_id surfaces in PlateResponseSchema.
    # vianda-platform: types/api.ts — restaurant context for plate in admin.
    # vianda-app: api/types.ts — restaurant context in plate selection.
    "ops.plate_info.restaurant_id": {"surfaces": ["platform", "app"]},
    #
    # .price surfaces in PlateResponseSchema and enriched plate responses.
    # vianda-platform: types/api.ts — plate price in admin and billing.
    # vianda-app: api/types.ts — plate price displayed in selection flow.
    "ops.plate_info.price": {"surfaces": ["platform", "app"]},
    #
    # .credit surfaces in PlateResponseSchema and PlateSelectionResponseSchema.
    # vianda-platform: types/api.ts — credit cost in admin plate management.
    # vianda-app: api/types.ts — credit cost shown in selection and balance flows.
    "ops.plate_info.credit": {"surfaces": ["platform", "app"]},
    #
    # .expected_payout_local_currency surfaces in PlateResponseSchema.
    # vianda-platform: types/api.ts — payout amount in admin financial reporting (2 hits).
    # vianda-app: api/types.ts (2 hits).
    "ops.plate_info.expected_payout_local_currency": {"surfaces": ["platform", "app"]},
    #
    # .delivery_time_minutes surfaces in PlateResponseSchema.
    # vianda-platform: types/api.ts — estimated prep time in admin plate management (2 hits).
    # vianda-app: api/types.ts — ETA shown in selection flow (1 hit).
    "ops.plate_info.delivery_time_minutes": {"surfaces": ["platform", "app"]},
    #
    # .status surfaces in PlateResponseSchema and PlateSelectionResponseSchema.
    # vianda-platform: types/api.ts — status in plate management.
    # vianda-app: api/types.ts — plate visibility in explore.
    "ops.plate_info.status": {"surfaces": ["platform", "app"]},
    # --- ops.restaurant_holidays ---
    #
    # .holiday_id surfaces in RestaurantHolidayResponseSchema.
    # vianda-platform: types/api.ts — holiday record ID in admin holiday management (3 hits).
    "ops.restaurant_holidays.holiday_id": {"surfaces": ["platform"]},
    #
    # .restaurant_id surfaces in RestaurantHolidayResponseSchema.
    # vianda-platform: types/api.ts — restaurant context for holiday records.
    # vianda-app: api/types.ts.
    "ops.restaurant_holidays.restaurant_id": {"surfaces": ["platform", "app"]},
    #
    # .country_code surfaces in RestaurantHolidayResponseSchema.
    # vianda-platform: types/api.ts — country filter for holidays.
    # vianda-app: api/types.ts.
    "ops.restaurant_holidays.country_code": {"surfaces": ["platform", "app"]},
    #
    # .holiday_date surfaces in RestaurantHolidayResponseSchema.
    # vianda-platform: types/api.ts — holiday date in admin calendar management (4 hits).
    "ops.restaurant_holidays.holiday_date": {"surfaces": ["platform"]},
    #
    # .holiday_name surfaces in RestaurantHolidayResponseSchema.
    # vianda-platform: types/api.ts — holiday name displayed in admin calendar (4 hits).
    "ops.restaurant_holidays.holiday_name": {"surfaces": ["platform"]},
    #
    # .is_recurring surfaces in RestaurantHolidayResponseSchema.
    # vianda-platform: types/api.ts — recurring toggle in holiday management form (5 hits).
    "ops.restaurant_holidays.is_recurring": {"surfaces": ["platform"]},
    #
    # .recurring_month surfaces in RestaurantHolidayResponseSchema.
    # vianda-platform: types/api.ts — recurring month selector in holiday form (5 hits).
    "ops.restaurant_holidays.recurring_month": {"surfaces": ["platform"]},
    #
    # .recurring_day surfaces in RestaurantHolidayResponseSchema.
    # vianda-platform: types/api.ts — recurring day selector in holiday form (5 hits).
    "ops.restaurant_holidays.recurring_day": {"surfaces": ["platform"]},
    #
    # .status surfaces in RestaurantHolidayResponseSchema.
    # vianda-platform: types/api.ts — status column in holiday management.
    # vianda-app: api/types.ts.
    "ops.restaurant_holidays.status": {"surfaces": ["platform", "app"]},
    # --- ops.plate_kitchen_days ---
    #
    # .plate_kitchen_day_id surfaces in PlateKitchenDayResponseSchema.
    # vianda-platform: types/api.ts — scheduling row ID in plate scheduling admin (2 hits).
    "ops.plate_kitchen_days.plate_kitchen_day_id": {"surfaces": ["platform"]},
    #
    # .plate_id surfaces in PlateKitchenDayResponseSchema.
    # vianda-platform: types/api.ts — plate reference in scheduling management (7 hits).
    # vianda-app: api/types.ts — plate scheduling in selection flow (13 hits).
    "ops.plate_kitchen_days.plate_id": {"surfaces": ["platform", "app"]},
    #
    # .kitchen_day surfaces in PlateKitchenDayResponseSchema and plate enriched responses.
    # vianda-platform: types/api.ts — kitchen day displayed in scheduling admin (5 hits).
    # vianda-app: api/types.ts — available day shown in plate selection flow (14 hits).
    "ops.plate_kitchen_days.kitchen_day": {"surfaces": ["platform", "app"]},
    #
    # .status surfaces in PlateKitchenDayResponseSchema.
    # vianda-platform: types/api.ts — scheduling status in admin.
    # vianda-app: api/types.ts.
    "ops.plate_kitchen_days.status": {"surfaces": ["platform", "app"]},
    # --- ops.ingredient_catalog ---
    #
    # .ingredient_id surfaces in IngredientCatalogResponseSchema.
    # vianda-platform: types/api.ts — ingredient ID in catalog admin (3 hits).
    "ops.ingredient_catalog.ingredient_id": {"surfaces": ["platform"]},
    #
    # .name surfaces in IngredientCatalogResponseSchema.
    # vianda-platform: types/api.ts — canonical ingredient name in catalog management.
    # vianda-app: api/types.ts — ingredient name on plate detail screens.
    "ops.ingredient_catalog.name": {"surfaces": ["platform", "app"]},
    #
    # .name_display surfaces in IngredientCatalogResponseSchema.
    # vianda-platform: types/api.ts — display name in catalog admin (3 hits).
    "ops.ingredient_catalog.name_display": {"surfaces": ["platform"]},
    #
    # .name_en surfaces in IngredientCatalogResponseSchema.
    # vianda-platform: types/api.ts — English name in catalog admin translation panel (3 hits).
    "ops.ingredient_catalog.name_en": {"surfaces": ["platform"]},
    #
    # .off_taxonomy_id surfaces in IngredientCatalogResponseSchema.
    # vianda-platform: types/api.ts — OFF taxonomy ID in catalog enrichment admin (2 hits).
    "ops.ingredient_catalog.off_taxonomy_id": {"surfaces": ["platform"]},
    #
    # .image_url surfaces in IngredientCatalogResponseSchema.
    # vianda-platform: types/api.ts — ingredient image in catalog admin (3 hits).
    # vianda-app: api/types.ts — ingredient image on plate detail screen (7 hits).
    "ops.ingredient_catalog.image_url": {"surfaces": ["platform", "app"]},
    #
    # .image_enriched surfaces in IngredientCatalogResponseSchema.
    # vianda-platform: types/api.ts — enrichment status in catalog admin (2 hits).
    "ops.ingredient_catalog.image_enriched": {"surfaces": ["platform"]},
    #
    # .is_verified surfaces in IngredientCatalogResponseSchema.
    # vianda-platform: types/api.ts — verified flag in catalog admin (2 hits).
    "ops.ingredient_catalog.is_verified": {"surfaces": ["platform"]},
    # --- ops.product_ingredient ---
    #
    # .product_ingredient_id surfaces in ProductIngredientResponseSchema.
    # vianda-platform: types/api.ts — link ID in ingredient-product management (1 hit).
    "ops.product_ingredient.product_ingredient_id": {"surfaces": ["platform"]},
    #
    # .product_id surfaces in ProductIngredientResponseSchema.
    # vianda-platform: types/api.ts — product reference in ingredient assignment (4 hits).
    # vianda-app: api/types.ts (1 hit).
    "ops.product_ingredient.product_id": {"surfaces": ["platform", "app"]},
    #
    # .ingredient_id surfaces in ProductIngredientResponseSchema.
    # vianda-platform: types/api.ts — ingredient reference in product ingredient list (3 hits).
    "ops.product_ingredient.ingredient_id": {"surfaces": ["platform"]},
    #
    # .sort_order surfaces in ProductIngredientResponseSchema.
    # vianda-platform: types/api.ts — ingredient order in product ingredient management (1 hit).
    "ops.product_ingredient.sort_order": {"surfaces": ["platform"]},
    # --- ops.ingredient_alias ---
    #
    # .ingredient_id surfaces in IngredientAliasResponseSchema.
    # vianda-platform: types/api.ts — canonical ingredient reference in alias management (3 hits).
    "ops.ingredient_alias.ingredient_id": {"surfaces": ["platform"]},
}
