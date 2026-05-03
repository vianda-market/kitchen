# Workplace Groups (B2C Coworker Pickup)

**Status:** Planned  
**Author:** Vianda CTO  
**Date:** 2026-04-13

---

## Motivation

The old `employer_info` table served two unrelated purposes:

1. **Employer Benefits Program** (B2B) — billing, tax entities, employee benefits. Now handled by `institution_info` (type=employer) + `institution_entity_info`. Heavy, admin-managed.

2. **Coworker Pickup Coordination** (B2C) — lightweight grouping so customers at the same office can see each other's orders, volunteer to pick up for coworkers, or request someone else pick up their plate. Customer-created, no billing involvement.

When we removed `employer_info` during the multinational institutions refactor, we lost #2. This plan restores it as a **purpose-built, lightweight model** separate from the employer billing system.

---

## What This Enables

- Customer searches "BigCorp" → finds or creates a workplace group → picks their office address
- Coworkers at the same group + address see each other's orders (privacy-gated)
- "Offer to pick up" / "Request pickup" flow scoped to workplace group + address
- Restaurant explorer shows `has_coworker_offer` / `has_coworker_request` badges
- Internal roles can pre-populate workplace groups for launch campaigns
- Internal roles can curate the list (rename, merge, archive offensive entries)

---

## Data Model

### New table: `core.workplace_group`

```sql
CREATE TABLE core.workplace_group (
    workplace_group_id UUID PRIMARY KEY DEFAULT uuidv7(),
    name               VARCHAR(100) NOT NULL,
    -- Domain verification (deferred — Phase 2)
    email_domain       VARCHAR(255) NULL,      -- e.g. 'bigcorp.com'; when set, enables domain enforcement
    require_domain_verification BOOLEAN NOT NULL DEFAULT FALSE,  -- when TRUE, members must verify email on this domain
    -- No tax_id, no currency, no billing — this is not a legal entity
    is_archived        BOOLEAN     NOT NULL DEFAULT FALSE,
    status             status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by         UUID        NULL,    -- customer who created it, or internal user
    modified_by        UUID        NOT NULL,
    modified_date      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_workplace_group_name ON core.workplace_group USING gin (name gin_trgm_ops);
```

Trigram index enables fuzzy type-ahead search (`name % 'bigcorp'` using trigram similarity).

**Domain verification (Phase 2, deferred):** When `require_domain_verification = TRUE`, members must own an email on `email_domain`. Flow: user requests to join → backend sends verification email to their `@bigcorp.com` address → user clicks link → `workplace_group_id` is set. For large employers, Internal sets `require_domain_verification = TRUE` when creating/curating the group. Small groups created by customers default to FALSE (open join).

### Audit table: `audit.workplace_group_history`

Standard history table mirroring `core.workplace_group`.

### User link: `core.user_info`

```sql
-- New columns on user_info (coworker grouping for B2C)
ALTER TABLE core.user_info ADD COLUMN workplace_group_id UUID NULL
    REFERENCES core.workplace_group(workplace_group_id) ON DELETE SET NULL;
-- employer_address_id already exists — reused as "which office do I pick up from"
```

`workplace_group_id` is the B2C coworker grouping. `employer_entity_id` remains for B2B benefit employees (set by backend during enrollment, not customer-selectable).

A customer can have **both**: `employer_entity_id` (benefit employee) + `workplace_group_id` (coworker pickup). Or just one. Or neither.

### Auto-link from Employer Benefits Program

When an employer enrolls employees via the benefits program, the backend **automatically creates or links a workplace group** for that employer:
- If the employer entity has `email_domain = 'bigcorp.com'` and a workplace group with `email_domain = 'bigcorp.com'` exists → link the employee to that group
- If no matching group exists → auto-create one with `name = institution.name`, `email_domain = entity.email_domain`, `require_domain_verification = FALSE` (already verified via benefits enrollment)
- This means benefit employees automatically get coworker pickup without extra steps

Non-benefit customers can also join the same workplace group — they're not required to be in the employer program. The group is just an aggregation mechanism for coworker visibility.

### Relationship to existing fields

| Field | Purpose | Set by |
|-------|---------|--------|
| `employer_entity_id` | B2B benefit employee link | Backend (signup domain match or admin enrollment) |
| `workplace_group_id` | B2C coworker pickup grouping | Customer (search + select) or auto-linked from employer enrollment |
| `employer_address_id` | Office address for pickup scoping | Customer (select from workplace group's shared addresses) |

---

## Routes

### Customer routes (B2C, JWT required)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/workplace-groups/search?q=BigCorp&limit=10` | Fuzzy type-ahead search by name (trigram similarity). Returns active, non-archived groups with member count. |
| POST | `/api/v1/workplace-groups` | Create new group. Customer provides `name`. |
| GET | `/api/v1/workplace-groups/{id}` | Get group by ID. |
| PUT | `/api/v1/users/me/workplace` | Assign workplace group + office address to current user. Body: `{ "workplace_group_id": "uuid", "address_id": "uuid" }` |

### Internal routes (B2B platform, Internal role)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/workplace-groups` | List all groups (paginated). For curation dashboard. |
| GET | `/api/v1/admin/workplace-groups/enriched` | List with member count, created_by user name. |
| PUT | `/api/v1/admin/workplace-groups/{id}` | Update name, status. For renaming or archiving offensive entries. |
| DELETE | `/api/v1/admin/workplace-groups/{id}` | Soft-archive. Members keep their `workplace_group_id` until they change it. |
| POST | `/api/v1/admin/workplace-groups/bulk` | Bulk create for campaign pre-population. Body: `[{ "name": "BigCorp" }, ...]` |

### Address handling — shared within group

Workplace group addresses are **shared across members**. When a customer joins a group, they see existing office addresses that other members have already registered for that group. They can:
- **Select an existing address** — "I work at the same office as others in this group"
- **Add a new address** — "My office is at a different location" (creates a new address linked to the group)

This is how the system knows people work in the same office: multiple users select the same `employer_address_id` within the same `workplace_group_id`.

**Implementation:** A `workplace_group_id` FK on `address_info` links addresses to groups. When a user selects a group, `GET /workplace-groups/{id}/addresses` returns all non-archived addresses for that group. The user picks one (or creates a new one), and it's set as their `employer_address_id`.

**Edit permissions:** Only Internal and Employer roles can edit workplace group addresses (trusted users). Customer roles who want a different address simply create a new address record and assign it to themselves — the previous address stays for other members. A cron job periodically archives workplace group addresses with 0 users linked to them.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/workplace-groups/{id}/addresses` | Any auth | List office addresses for this group |
| POST | `/api/v1/workplace-groups/{id}/addresses` | Any auth | Add a new office address to this group |
| PUT | `/api/v1/workplace-groups/{id}/addresses/{address_id}` | Internal, Employer only | Edit an existing group address |

---

## Coworker Service Changes

`coworker_service.py` and `restaurant_explorer_service.py` currently match coworkers by `employer_entity_id + employer_address_id`.

**New matching logic:**

```python
# Coworker match: same workplace_group_id + same employer_address_id
# Falls back to employer_entity_id for benefit employees without a workplace group
if user.workplace_group_id:
    match_field = "workplace_group_id"
    match_value = user.workplace_group_id
elif user.employer_entity_id:
    match_field = "employer_entity_id"
    match_value = user.employer_entity_id
else:
    # No coworker matching
    return []
```

This means:
- **B2C customers** who set a workplace group → matched by group + office
- **B2B benefit employees** without a workplace group → matched by employer entity + office (existing behavior)
- **B2B benefit employees with a workplace group** → matched by group (takes precedence)

---

## Schemas

### WorkplaceGroupCreateSchema
```python
class WorkplaceGroupCreateSchema(BaseModel):
    name: str = Field(..., max_length=100, description="Workplace name (e.g., 'BigCorp Buenos Aires')")
    email_domain: Optional[str] = Field(None, max_length=255, description="Email domain for verification (Phase 2)")
```

### WorkplaceGroupResponseSchema
```python
class WorkplaceGroupResponseSchema(BaseModel):
    workplace_group_id: UUID
    name: str
    email_domain: Optional[str] = None
    require_domain_verification: bool = False
    is_archived: bool
    status: Status
    created_date: datetime
    model_config = ConfigDict(from_attributes=True)
```

### WorkplaceGroupSearchResultSchema
```python
class WorkplaceGroupSearchResultSchema(BaseModel):
    workplace_group_id: UUID
    name: str
    member_count: int = 0  # number of active members
    similarity: float = 0.0  # trigram similarity score (0-1)
```

### AssignWorkplaceRequest
```python
class AssignWorkplaceRequest(BaseModel):
    workplace_group_id: UUID = Field(..., description="Workplace group to join")
    address_id: UUID = Field(..., description="Office address for pickup scoping")
```

### User response additions
```python
# On UserResponseSchema and UserEnrichedResponseSchema:
workplace_group_id: Optional[UUID] = None
workplace_group_name: Optional[str] = None  # enriched only
```

---

## DTO

### WorkplaceGroupDTO
```python
class WorkplaceGroupDTO(BaseModel):
    workplace_group_id: UUID
    name: str
    email_domain: Optional[str] = None
    require_domain_verification: bool = False
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime
    model_config = ConfigDict(from_attributes=True)
```

---

## Auth & Scoping

- **Search and create:** Any authenticated customer. No institution scoping — workplace groups are global (a customer in AR can see groups created by anyone).
- **Assign to self:** Customer only. Sets `workplace_group_id` + `employer_address_id` on own user record.
- **Admin CRUD:** Internal Admin / Super Admin only.
- **Privacy:** Coworker visibility controlled by existing `user_messaging_preferences.notify_peer_pickup` flag. Users opted out don't appear in coworker lists even if they share a workplace group.

---

## Implementation

**Approach:** Full DB tear-down and rebuild via `build_kitchen_db.sh`. No incremental migration. No customer-facing breaking changes — this is a new feature with new endpoints. Existing B2C customers have no workplace group set (NULL) and coworker features are simply unavailable until they join one.

- **Schema:** Add `core.workplace_group` table + audit to `schema.sql`. Add `workplace_group_id` column to `user_info` + `user_history`. Add `workplace_group_id` FK to `address_info` (nullable — only set for group-linked office addresses). Add trigger for workplace_group_history.
- **Seed data:** None required. Empty table. Internal users populate via bulk create or individual creation in vianda-platform.
- **Coworker service:** Update matching logic (workplace_group_id takes precedence over employer_entity_id).
- **Enrollment service:** Auto-create/link workplace group when enrolling benefit employees.
- **User DTOs/schemas:** Add `workplace_group_id` field.
- **Address DTOs/schemas:** Add `workplace_group_id` field (nullable).
- **Enriched user:** LEFT JOIN to `workplace_group` for `workplace_group_name`.
- **Cron:** New cron to archive workplace group addresses with 0 users linked (`employer_address_id` not referencing them).

---

## B2C App Integration

1. **Signup/onboarding:** After creating an account, prompt "Where do you work?" → type-ahead search → select or create → pick office address.
2. **Profile:** Show workplace group name + office address. "Change" button to re-search or clear.
3. **Explore:** `has_coworker_offer` / `has_coworker_request` badges on restaurants — works as before but uses `workplace_group_id` for matching.
4. **Post-reservation:** "Offer to pick up" / "Request pickup" flow — scoped to workplace group + office.

## B2B Platform Integration (vianda-platform)

1. **Admin → Workplace Groups** page: List all groups with member count, search, edit name, archive.
2. **Bulk create:** CSV upload or form for campaign pre-population when launching in a new area.
3. **Curation:** Flag/rename inappropriate group names. Merge duplicates.

---

## Estimated Scope

| Area | Effort | Notes |
|------|--------|-------|
| Schema (table + column + audit + trigger) | Small | One table, one column on user_info |
| CRUD service + routes | Small | Standard CRUDService pattern |
| Search endpoint (trigram) | Small | GIN index, ILIKE query |
| Admin routes (list, update, bulk) | Small | Standard admin pattern |
| Coworker service update | Small | Change match field logic |
| User DTO/schema update | Small | Add field |
| B2C app UI | Medium | Search + select + assign flow |
| B2B platform UI | Small | List + edit admin page |
| Postman collection | Small | New collection or extend existing |

**Total:** Small feature. 1-2 day implementation on backend. Independent of employer program — can be done in parallel.

---

## Resolved Decisions

| Question | Decision |
|----------|----------|
| **Deduplication** | Fuzzy match from the start — search uses trigram similarity, shows close matches. Allow non-exact duplicates. Internal can merge later (migrate users from one group to another, archive the duplicate). |
| **Address ownership** | Addresses are shared within a group. Members select from existing group addresses or add new ones. Coworker matching = same `workplace_group_id` + same `employer_address_id`. |
| **Member count** | Yes, show count in search results. Just a number, no PII. |
| **Domain verification** | Schema includes `email_domain` + `require_domain_verification` from the start. Enforcement logic deferred to Phase 2. |
| **Auto-link from employer program** | Benefit employees auto-linked to a matching workplace group on enrollment. Non-benefit customers can join the same group independently. |

## Open Questions

1. **Merge UX for Internal:** When merging duplicates, do we auto-reassign all members, or notify them? Lean towards auto-reassign + log.
2. **Group address limit:** Should we cap the number of addresses per group? Probably not — a large employer could have many offices. Monitor.
3. **Cross-market groups:** Can a workplace group span multiple countries (e.g., "BigCorp" with offices in AR and PE)? Yes — the group is just a name. The address determines the country. Coworker matching is scoped by address, so cross-country coworkers won't match unless they're at the same physical office.
