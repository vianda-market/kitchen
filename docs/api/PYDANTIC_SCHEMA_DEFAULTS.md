# Pydantic Schema Defaults & Placeholder Management

## Why this matters

The API relies on Pydantic schemas to keep incoming payloads aligned with the database contract. Whenever a column gains a default value or an attribute becomes non-nullable, the corresponding schema **must** be updated to reflect that behaviour. If we fail to mirror defaults in the schema, the route factory will send `null` values explicitly—which overrides the DB-level defaults and leads to constraint violations (as we saw with `product_info.image_url`).

## Default propagation checklist

1. **DB schema change**  
   - If you add a default, make a column non-nullable, or seed a placeholder asset, capture the canonical value (URL, path, checksum, etc.).

2. **DTOs & schemas**  
   - Update the relevant Pydantic DTO (`app/dto/models.py`) and request/response schemas (`app/schemas/...`) so the fields either:
     - Have explicit defaults (preferred), or
     - Are omitted entirely from `Create` schemas when the backend generates them.

3. **Route factory expectations**  
   - The admin CRUD routes generated via `route_factory` blindly pass the schema data to `CRUDService.create/update`. If the schema returns `None`, that value is persisted; the DB default is bypassed. Setting defaults at the schema layer prevents this.

4. **Tests & fixtures**  
   - Update fixtures (`app/tests/conftest.py`) so they include the new fields. This keeps unit tests realistic and prevents accidental regressions.

5. **Docs & Postman**  
   - Record default behaviour here and make sure Postman collections/logs surface the defaulted fields. This makes it obvious when payloads omit image or checksum metadata and rely on placeholders.

## Current placeholder defaults

| Entity | Field | Default | Notes |
| --- | --- | --- | --- |
| `product_info` | `image_url` | `http://localhost:8000/static/placeholders/product_default.png` | Set in schema, DTO, and Postman. |
| `product_info` | `image_storage_path` | `static/placeholders/product_default.png` | Keeps CRUD path consistent. |
| `product_info` | `image_checksum` | `7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c` | SHA-256 of the placeholder asset. |
| `qr_code` | `qr_code_checksum` | Generated during QR creation | Persisted via `QRCodeGenerationService`. |

> Whenever any of these values change, update both the schema defaults and this table.

## Example: Product creation

- DB schema (`app/db/schema.sql`) marks `image_url`, `image_storage_path`, and `image_checksum` as `NOT NULL` with defaults pointing to the shared placeholder.
- `ProductCreateSchema` sets matching defaults so the CRUD route inserts the correct values even if the caller omits them:
  ```python
  image_url: str = Field(default=PLACEHOLDER_IMAGE_URL, max_length=500)
  image_storage_path: str = Field(default=PLACEHOLDER_IMAGE_PATH, max_length=500)
  image_checksum: str = Field(default=PLACEHOLDER_IMAGE_CHECKSUM, max_length=128)
  ```
- Tests (`app/tests/conftest.py`) and Postman scripts rely on the schema defaults and do not need to set image metadata unless they are testing a custom upload.

## Quick reference workflow

1. Modify schema → extract new default.
2. Update Pydantic `Create` schema default values.
3. Adjust DTOs, fixtures, and client docs/collections.
4. Log changes in this document.

By following this loop, we keep the application layer in sync with DB expectations and avoid "null violates not-null constraint" errors when new defaults roll out.***

