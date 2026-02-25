---
name: api-alignment
description: Keep frontend and backend API contracts aligned in clinic-sim. Use when backend schemas/routes change, frontend API clients/types need updates, or request/response mismatches cause runtime issues.
---

> 生产部署统一入口：`生产部署指南.md`。

# API Alignment

Use this skill when syncing backend contract changes to frontend clients and types.

## Execute Workflow

1. Read `references/alignment-workflow.md`.
2. Identify changed backend schema/route files.
3. Update frontend API wrappers in `src/apps/web/src/api`.
4. Update shared frontend types in `src/apps/web/src/types`.
5. Verify route guards and error handling behavior.
6. Run frontend build/typecheck and backend tests relevant to changed APIs.

## Guardrails

- Avoid `any` for API payloads when project types already define structure.
- Keep endpoint paths and query/body shapes identical across layers.
- Preserve backward compatibility unless explicitly changing contract.

## References

- Contract sync workflow: `references/alignment-workflow.md`
- API map: `references/api-map.md`
