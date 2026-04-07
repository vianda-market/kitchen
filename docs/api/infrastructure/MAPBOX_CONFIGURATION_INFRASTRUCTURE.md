# Mapbox Configuration Infrastructure

**Audience**: infra-kitchen-gcp (Pulumi repo)  
**Purpose**: Provision GCP Secret Manager secrets and Cloud Run environment variables for Mapbox address autocomplete and geocoding APIs.  
**Last Updated**: 2026-04-03

---

## Context

The backend is migrating from Google Maps/Places APIs to Mapbox for address autocomplete and geocoding. Google API keys for these services have been turned off. Mapbox is now the default address provider (`ADDRESS_PROVIDER=mapbox`).

Mapbox uses a **single access token** for all APIs (Search Box, Geocoding, Maps). There is no per-API enablement step — one token grants access to everything included in the account plan.

**Roadmap doc**: `docs/plans/MAPBOX_MIGRATION_ROADMAP.md`

---

## Status by Environment

| Environment | Status | Notes |
|-------------|--------|-------|
| Local dev | Mock mode | `DEV_MODE=true`, no token needed (uses mock responses). Set token to test live API. |
| GCP dev/staging | **Needs provisioning** | Mapbox access token must be created and stored in Secret Manager |
| GCP prod | Not yet active | Same as staging; activate once dev/staging validated |

---

## What the Backend Expects

The backend reads these values via `app/config/settings.py` (Pydantic `BaseSettings`, loaded from env). All Mapbox values default to empty string — the app falls back to mock mode (dev) or errors (prod) when the token is missing.

### Required Environment Variables

| Variable | Type | Required When | Description |
|----------|------|---------------|-------------|
| `ADDRESS_PROVIDER` | string | Always | Set to `mapbox` (default) or `google` (fallback). Controls which gateway handles address autocomplete and geocoding. |
| `MAPBOX_ACCESS_TOKEN_DEV` | secret | `ADDRESS_PROVIDER=mapbox` + local/dev env | Mapbox access token for dev. Format: `pk.eyJ1Ijo...` (public token) or `sk.eyJ1Ijo...` (secret token). |
| `MAPBOX_ACCESS_TOKEN_STAGING` | secret | `ADDRESS_PROVIDER=mapbox` + staging env | Mapbox access token for staging. Separate token recommended for usage tracking. |
| `MAPBOX_ACCESS_TOKEN_PROD` | secret | `ADDRESS_PROVIDER=mapbox` + prod env | Mapbox access token for production. Must be a **secret token** with URL restrictions. |

### Environment Selection Logic

The backend selects the token based on the `ENVIRONMENT` env var (defined in `app/config/settings.py:get_mapbox_access_token()`):

| `ENVIRONMENT` value | Token used |
|---------------------|-----------|
| `local`, `dev`, or unset | `MAPBOX_ACCESS_TOKEN_DEV` |
| `staging` | `MAPBOX_ACCESS_TOKEN_STAGING` |
| `prod` | `MAPBOX_ACCESS_TOKEN_PROD` |

### Google API Keys (removed)

Google Maps/Places API keys have been removed from GCP Secret Manager and Cloud Run env vars (April 2026). The backend code retains dormant Google gateway classes (`google_maps_gateway.py`, `google_places_gateway.py`) and the `GOOGLE_API_KEY_*` settings fields for potential Phase 3 fallback, but no secrets are provisioned. If Google fallback is ever needed for a market where Mapbox lacks coverage, new API keys would need to be created in Google Cloud Console and provisioned in Secret Manager.

---

## Mapbox Account Setup

Unlike Google Cloud (where each API must be individually enabled per key), Mapbox uses a single access token that grants access to all APIs:

| API | Used For | Billing Model |
|-----|----------|--------------|
| Search Box API (suggest + retrieve) | Address autocomplete | Per session (suggest + retrieve = 1 session) |
| Geocoding API v6 (forward + reverse) | Address → coordinates, coordinates → address | Per request (100K free/month) |

### Token Types

| Type | Prefix | Use Case | Restriction Options |
|------|--------|----------|-------------------|
| Public token | `pk.eyJ1Ijo...` | Client-side maps, dev/testing | URL restrictions (optional) |
| Secret token | `sk.eyJ1Ijo...` | Server-side API calls (production) | Must set URL restrictions |

**Recommendation:**
- **Dev/staging**: Use a public token (`pk.`) — simpler, sufficient for testing
- **Production**: Create a secret token (`sk.`) with URL restriction to the Cloud Run service URL

### Steps to Create Tokens

1. Sign in at [account.mapbox.com](https://account.mapbox.com)
2. Go to **Tokens** tab
3. For dev/staging: the **Default public token** works; or click **Create a token** with default scopes
4. For production: click **Create a token**, enable **Secret** scope, add URL restriction matching the Cloud Run service URL
5. Copy the token value — it is shown only once for secret tokens

---

## GCP Secret Manager

Store all Mapbox access tokens in GCP Secret Manager — not as plain Cloud Run env vars.

### Secret naming convention

```
kitchen-mapbox-token-dev            # Dev environment access token
kitchen-mapbox-token-staging        # Staging environment access token
kitchen-mapbox-token-prod           # Production environment access token
```

### Secret Manager → Cloud Run binding

Mount each secret as an environment variable on the Cloud Run service. The Cloud Run service account needs `roles/secretmanager.secretAccessor` on each secret.

```
# Pulumi pattern (Python)
mapbox_token = gcp.secretmanager.Secret("kitchen-mapbox-token-staging", ...)
cloud_run_service = gcp.cloudrun.Service(
    "kitchen-backend",
    template=gcp.cloudrun.ServiceTemplateArgs(
        spec=gcp.cloudrun.ServiceTemplateSpecArgs(
            containers=[gcp.cloudrun.ServiceTemplateSpecContainerArgs(
                envs=[
                    # Existing vars...
                    gcp.cloudrun.ServiceTemplateSpecContainerEnvArgs(
                        name="MAPBOX_ACCESS_TOKEN_STAGING",
                        value_from=gcp.cloudrun.ServiceTemplateSpecContainerEnvValueFromArgs(
                            secret_key_ref=gcp.cloudrun.ServiceTemplateSpecContainerEnvSecretKeyRefArgs(
                                name=mapbox_token.secret_id,
                                key="latest",
                            ),
                        ),
                    ),
                    gcp.cloudrun.ServiceTemplateSpecContainerEnvArgs(
                        name="ADDRESS_PROVIDER",
                        value="mapbox",
                    ),
                ],
            )],
        ),
    ),
)
```

### Plain env vars (non-secret)

These can be set directly on Cloud Run (not in Secret Manager):

| Variable | Value | Notes |
|----------|-------|-------|
| `ADDRESS_PROVIDER` | `mapbox` | Default; switch to `google` only if Mapbox needs to be disabled |

---

## Cost & Billing

Mapbox bills based on usage against a free tier. No credit card is required for the free tier.

| API | Free Tier | Cost After Free Tier |
|-----|-----------|---------------------|
| Search Box (suggest + retrieve) | ~500 sessions/month | Per-session pricing |
| Geocoding (temporary) | 100,000 requests/month | $0.75 / 1,000 |
| Geocoding (permanent, Phase 2) | Shared quota | $5.00 / 1,000 |

**Phase 1 expected cost: $0/month** — well within free tiers during testing and early launch.

Monitor usage at [account.mapbox.com/statistics](https://account.mapbox.com/statistics).

---

## Activation Checklist (per environment)

### Dev/Staging

- [ ] Mapbox account created (one account for all environments)
- [ ] Access token created for this environment (public token `pk.` is fine for dev/staging)
- [ ] Token stored in GCP Secret Manager as `kitchen-mapbox-token-{env}`
- [ ] Cloud Run service account granted `roles/secretmanager.secretAccessor` on the new secret
- [ ] Secret mounted as `MAPBOX_ACCESS_TOKEN_{ENV}` env var on Cloud Run service
- [ ] `ADDRESS_PROVIDER=mapbox` env var set on Cloud Run service
- [ ] `ENVIRONMENT={env}` env var set (should already exist)
- [ ] Deploy and verify: `GET /api/v1/addresses/suggest?q=Av+Santa+Fe&country=AR` returns suggestions

### Production (after staging validated)

- [ ] Secret access token (`sk.`) created with URL restriction to prod Cloud Run URL
- [ ] Token stored in GCP Secret Manager as `kitchen-mapbox-token-prod`
- [ ] Same Cloud Run binding as staging
- [ ] Smoke test: address suggest + create flow works end-to-end
- [ ] Verify billing dashboard shows expected usage

---

## Backend References

| Document | What It Covers |
|----------|---------------|
| `app/config/settings.py` | `MAPBOX_ACCESS_TOKEN_*`, `ADDRESS_PROVIDER`, `get_mapbox_access_token()` |
| `app/gateways/address_provider.py` | Factory that selects Mapbox vs Google gateway based on `ADDRESS_PROVIDER` |
| `app/gateways/mapbox_search_gateway.py` | Search Box API gateway (suggest + retrieve) |
| `app/gateways/mapbox_geocoding_gateway.py` | Geocoding API v6 gateway (forward + reverse) |
| `docs/plans/MAPBOX_MIGRATION_ROADMAP.md` | Full migration roadmap (Phase 1-3) |
| `.env.example` | Template with all Mapbox env vars |
