# SEO Strategy Plan

**Status:** Placeholder -- scope defined, detailed design deferred.
**Goal:** Organic search acquisition strategy that reinforces paid ad campaigns and the geographic flywheel.
**Relationship:** Reads geographic signals from the Ads Platform (`docs/plans/GOOGLE_META_ADS_INTEGRATION_V2.md`) but executes independently.

---

## Scope

SEO strategy for three audiences across the marketing site (vianda-home):

| Audience | Landing Pages | Search Intent |
|----------|--------------|---------------|
| B2C Individual Consumers | `/cities/{city}`, `/neighborhoods/{zone}` | "meal subscription [city]", "food delivery subscription near me" |
| B2B Employers | `/for-employers`, `/for-employers/{city}` | "employee meal benefit program", "corporate meal subscription" |
| B2B Restaurants | `/for-restaurants`, `/for-restaurants/{city}` | "join food delivery platform", "restaurant partnership [city]" |

## Signals from Ads Platform

The SEO plan should consume these data points from the ads platform:

- **Active zones** (`ad_zone` table): prioritize creating location pages for zones in `demand_activation` or `growth` state
- **Notify-me lead density**: high-density areas without coverage = high-intent organic search opportunity (people searching for meal subscriptions in that area)
- **Restaurant coverage**: zones with active restaurants should have optimized landing pages showing available plans and restaurants
- **Top-performing ad copy**: winning ad creative concepts (from section 13 collateral analysis) can inform organic content direction

## Key Topics (Not Designed Yet)

- Location-based landing page generation (programmatic SEO for city/neighborhood pages)
- Local business schema markup (JSON-LD) for restaurant partners
- Google Business Profile optimization for covered zones
- Content strategy: blog posts, guides, employer benefits ROI calculators
- Technical SEO: sitemap generation for dynamic location pages, canonical URLs, hreflang for multi-language (es/en/pt)
- Link building strategy for B2B authority (employer benefits, restaurant partnership)
- Conversion tracking: organic-to-subscription attribution (separate from paid ad conversion tracking)

## Dependencies

- Marketing site (vianda-home) must support dynamic location pages
- `ad_zone` table and flywheel state data must be accessible via API for page generation decisions
- Restaurant and plan data already exposed via leads public API (`/api/v1/leads/*`)

## When to Design

After the Ads Platform Phase 12 (B2C launch) is live and generating data. SEO planning benefits from having real zone data and ad performance to prioritize against.
