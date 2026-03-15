# Infrastructure Documentation

Infrastructure for the Kitchen platform (FastAPI backend, PostgreSQL database) is moving to a **separate Pulumi repository**.

## Contents

- **[feedback_for_infra.md](feedback_for_infra.md)** — Requirements and recommendations for the new infrastructure repo. Use this (together with feedback from B2B and B2C clients) to design and build the Pulumi app.

## Current State

- **`infra/`** in this repo — Legacy CloudFormation templates and deploy scripts. Will be superseded by the new Pulumi-based infrastructure repo.

## Related

- **Application architecture** — `docs/architecture/EXTERNAL_SERVICE_GATEWAY.md` (gateway pattern for external APIs)
- **Environment setup** — `docs/readme/ENV_SETUP.md` (env vars, local dev)
- **Technical roadmap** — `docs/roadmap/TECHNICAL_ROADMAP_2026.md`
