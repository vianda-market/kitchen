# Cursor rules for this project

1. **Paths**: Use the **short** workspace path only: **`~/Desktop/local/kitchen`** (or `$HOME/Desktop/local/kitchen`). Never use the long iCloud path (`Library/Mobile Documents/com~apple~CloudDocs/Desktop/local/...`) when editing files, running commands, or requesting permissions—always reference and operate from `~/Desktop/local/kitchen`.

2. **Database changes**: Do not write or run database migrations. Assume the database will be **torn down and rebuilt** for schema changes. Do not add migration scripts unless explicitly requested.

3. **Postman**: For every new service or API, add or update Postman collections under [docs/postman](docs/postman) so the new endpoints and flows are covered by tests.

4. **Tests**: When changing structural code (DB schema, triggers, DTOs), update the **unit tests** that depend on them so they stay in sync with the new structure.
