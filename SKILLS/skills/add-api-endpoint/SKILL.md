---
name: add-api-endpoint
description: Create or modify FastAPI endpoints in this luyun-sizheng project. Use when asked to add a new API route, adjust request/response schemas, wire services, or add endpoint tests while preserving route-service-model layering.
---

> 生产部署统一入口：`生产部署指南.md`。

# Add API Endpoint

Follow this workflow when implementing or updating an API endpoint.

## Execute Workflow

1. Read `references/workflow.md` and confirm route prefix, auth requirement, and response contract.
2. Define or update schemas under `src/apps/api/schemas` before changing route code.
3. Keep route handlers thin: validate input, inject dependencies, call service logic, shape response.
4. Put business logic in `src/apps/api/services` or create a new service module when needed.
5. Reuse `DbSession` and `CurrentUser` dependency aliases from `src/apps/api/dependencies.py`.
6. Add or update tests in `tests/` for success and failure paths.
7. Run targeted pytest files and report coverage gaps.

## Guardrails

- Do not embed long business logic in `src/apps/api/routes/*.py`.
- Do not bypass schemas with raw dict responses when schema exists.
- Do not hardcode secrets or environment-specific URLs.
- Keep error behavior consistent with `src/apps/api/exceptions.py`.

## References

- Workflow and checklist: `references/workflow.md`
- API surface summary: `references/api-surface.md`
