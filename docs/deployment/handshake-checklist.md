# Pre-Deploy Handshake Checklist

**Last Updated**: 2026-02-10  
**Purpose**: Checklist before deploying backend changes that affect frontend apps.

---

## Before Deploying Backend

### Additive Changes (new endpoints, new optional fields)

- [ ] Document new endpoints in [API_PERMISSIONS_BY_ROLE.md](../api/API_PERMISSIONS_BY_ROLE.md) if role-dependent
- [ ] Update client docs in `docs/api/client/` if UI patterns change
- [ ] Verify `/openapi.json` reflects changes (run server, check `/docs`)
- [ ] Deploy backend first; frontend can integrate in separate PRs

### Breaking Changes (removed endpoints, changed response shape)

- [ ] Add entry to [BREAKING_CHANGES.md](../api/BREAKING_CHANGES.md)
- [ ] Coordinate with kitchen-web and kitchen-mobile repos
- [ ] Ensure frontend has migrated before deprecation/removal, OR plan deploy order (backend + frontend in same window)
- [ ] Consider backward compatibility period if possible

### Schema / Type Changes

- [ ] Frontend repos should re-run OpenAPI codegen after backend deploy
- [ ] Note in handoffs if codegen output changes significantly

---

## Deployment Order by Change Type

| Change Type | Backend Deploy | Frontend Deploy |
|-------------|----------------|-----------------|
| New endpoint | First | Anytime after |
| New optional field | First | Anytime after |
| Removed endpoint | After frontend migrated | First |
| Changed required field | Coordinate; often backend + frontend together | Same window |
| Auth change | Coordinate | Same window |

---

## Per-Repo Quick Reference

| Repo | Main Docs | Codegen Command |
|------|-----------|------------------|
| kitchen-web | [client/README.md](../api/client/README.md) | `npx openapi-typescript $API_URL/openapi.json -o src/api/types.ts` |
| kitchen-mobile | [client/README.md](../api/client/README.md) | Same |

Replace `$API_URL` with `http://localhost:8000` (dev) or deployed backend URL.
