# Manual Operations

This folder contains checklists for manual UI operations that must be completed before backend integrations can function. These are not automated by code or Pulumi.

## Documents

| Document | Platform | Purpose |
|----------|----------|---------|
| Ads Platform section 27 | Google Ads + Meta | Full manual setup checklists embedded in `docs/plans/GOOGLE_META_ADS_INTEGRATION_V2.md` section 27 |

## Why Here

Some infrastructure requires manual UI interaction (creating ad accounts, conversion actions, system users, OAuth tokens). These steps produce credentials and IDs that are then stored in GCP Secret Manager and referenced by the backend.

The detailed checklists live in the main plan document (section 25) so agents reading the full plan see them in context. This folder serves as a pointer.
