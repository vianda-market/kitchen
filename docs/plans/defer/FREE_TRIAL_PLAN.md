# Free Trial Plan

**Status:** Placeholder -- scope defined, detailed design deferred.
**Goal:** Give new users enough credits for one vianda to explore the service before committing to a paid subscription.

---

## Concept

- New user signs up and receives a trial subscription with credits for 1 vianda (no payment required)
- User selects a restaurant, reserves a vianda, picks it up -- full experience
- After trial vianda is consumed (or trial period expires), user is prompted to subscribe
- If user subscribes, the trial converts to a paid subscription

## Ads Platform Integration

- Trial activation fires `StartTrial` event (value=0, predicted_ltv based on plan price) to Google + Meta
- This gives ad platforms a faster mid-funnel signal (trial happens before payment)
- Helps reach the 50 conversions/week threshold for Advantage+ optimization faster than waiting for paid subscriptions only
- Trial-to-paid conversion rate becomes a key metric for the Gemini advisor

## Dependencies

- Subscription flow must support a $0 "trial" plan or a credit grant without payment
- B2C app needs a trial-specific onboarding flow (skip payment, go straight to vianda selection)
- Ad tracking: `StartTrial` event already defined in `ConversionEventType` and supported by mock/live gateways

## When to Design

After B2C subscription flow is stable and ads platform Phase 12 (B2C launch) is generating data. The trial will be most impactful in new zones where conversion volume is low.
