# Roadmap: Language-Aware Enums and Market Language

**Status**: Future / Follow-up

**Depends on**: Street Type Enum Onboarding (completed)

---

## Overview

Enable UI to show localized enum labels (e.g. "Calle" vs "Street") based on the user's market language. The backend stores and accepts **codes only** (St, Ave, Blvd); display labels vary by language.

---

## Goals

1. Add a **language** attribute to `market_info` so each market has a preferred language (e.g. en, es, pt).
2. Expose **enum display labels** per language so the UI can render dropdown options in the user's language.
3. Keep **codes** (St, Ave, Blvd, etc.) as the canonical values stored in DB and sent in API requests.

---

## Roadmap Steps

### 1. Add `language` to Market

- **Schema**: Add `language VARCHAR(5)` to `market_info` (ISO 639-1, e.g. `en`, `es`, `pt`).
- **History**: Mirror in `market_history`.
- **Seed**: Populate language for existing markets (e.g. AR → `es`, PE → `es`, CL → `es`, US → `en`).
- **API**: Include `language` in market responses (Markets API, enriched market payloads).

### 2. Enum Labels Endpoint

- **New endpoint**: `GET /api/v1/enums/labels?language={lang}`
- **Response shape**: Per-enum label maps, e.g.:
  ```json
  {
    "street_type": { "St": "Calle", "Ave": "Avenida", "Blvd": "Bulevar", ... },
    "address_type": { "Restaurant": "Restaurante", ... }
  }
  ```
- **Behavior**: If `language` is omitted or unsupported, return labels for a default (e.g. `en`).

**Alternative**: Extend `GET /api/v1/enums/?language=es` to return e.g. `street_type: [{"code": "St", "label": "Calle"}, ...]` for a single-call experience.

### 3. Translation Storage

- **Option A (static)**: Python dict/module mapping `(enum_type, code, language) -> label`.
- **Option B (DB)**: New table `enum_label` (enum_type, code, language, label) for runtime management.
- **Initial scope**: Start with static maps for `street_type` and optionally `address_type`; expand as needed.

### 4. Client Flow

1. Resolve user's market (from institution, JWT, or selection).
2. Read `language` from that market.
3. Call `GET /api/v1/enums/` for codes.
4. Call `GET /api/v1/enums/labels?language={lang}` for labels.
5. Render dropdown with **labels**; on submit send **codes**.

---

## Out of Scope (For Now)

- Full i18n of all enums (prioritize `street_type`, then `address_type` if needed).
- User-level language override (market language is the source of truth for enum labels).
- Translation management UI.

---

## References

- [ENUM_SERVICE_API.md](../api/shared_client/ENUM_SERVICE_API.md) – Current enum API
- Street Type Enum Plan (Section 11) – follow-up design for language-aware enums
