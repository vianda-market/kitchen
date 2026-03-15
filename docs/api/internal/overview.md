# Kitchen API Overview

**Last Updated**: 2026-02-10  
**API Version**: v1  
**Base Path**: `/api/v1`

This document provides frontend developers with a high-level overview of the Kitchen API: base URLs, versioning, authentication, and OpenAPI access.

---

## Base URLs by Environment

| Environment | Base URL | Notes |
|-------------|----------|-------|
| **Local** | `http://localhost:8000` | Default for local development |
| **Staging** | TBD | Pre-production validation |
| **Production** | TBD | Production deployment |

All business endpoints are versioned: `/api/v1/...`

---

## OpenAPI Contract

### Interactive Documentation

- **Swagger UI**: `{BASE_URL}/docs`
- **ReDoc**: `{BASE_URL}/redoc` (if enabled)

### OpenAPI JSON (for codegen)

- **Spec URL**: `{BASE_URL}/openapi.json`

Example for local development:
```
http://localhost:8000/openapi.json
```

**Frontend Codegen**: Use this URL with `openapi-typescript`, `orval`, or similar tools to generate TypeScript types and API client. See [handoffs.md](./handoffs.md) for codegen examples.

---

## Versioning

- **Current version**: v1
- **Path prefix**: All business endpoints use `/api/v1/`
- **Future versions**: v2, v3, etc. will be additive; deprecated endpoints documented in [BREAKING_CHANGES.md](./BREAKING_CHANGES.md)

---

## Authentication

### JWT Bearer Token

1. **Login**: `POST /api/v1/auth/token` with `username` + `password` (form data)
2. **Response**: `{ "access_token": "...", "token_type": "bearer" }`
3. **Subsequent requests**: `Authorization: Bearer {access_token}`

### Role Types (affect which endpoints are accessible)

| Role Type | Audience | Access |
|-----------|----------|--------|
| **Employee** | Backoffice (admin) | Global access, system config |
| **Supplier** | Restaurant staff | Institution-scoped only |
| **Customer** | B2C (mobile/web) | Own data, plans, subscriptions |

See [API_PERMISSIONS_BY_ROLE.md](./API_PERMISSIONS_BY_ROLE.md) for detailed permission matrices.

---

## CORS

CORS is configured to allow requests from frontend origins. Update `allow_origins` in production to restrict to known frontend domains.

---

## Health Check

- **Endpoint**: `GET /health`
- **Response**: `{ "status": "healthy" }`
- **Use**: Load balancer health checks, monitoring

---

## Related Documentation

- [API_PERMISSIONS_BY_ROLE.md](./API_PERMISSIONS_BY_ROLE.md) – Permission matrix by role
- [handoffs.md](./handoffs.md) – Backend ↔ frontend coordination
- [BREAKING_CHANGES.md](./BREAKING_CHANGES.md) – Breaking changes log
- [shared_client/README.md](./shared_client/README.md) – Shared docs for both client repos
- [b2b_client/README.md](./b2b_client/README.md) – B2B client docs (Restaurant + Employee)
- [b2c_client/README.md](./b2c_client/README.md) – B2C client docs (React Native, Customer)
