---
name: change-db-model
description: Safely modify SQLAlchemy models and Alembic migrations in luyun-sizheng. Use when changing table fields, constraints, relations, or migration scripts, including schema rollout checks and API/schema alignment.
---

> 生产部署统一入口：`生产部署指南.md`。

# Change DB Model

Use this skill for model and migration changes.

## Execute Workflow

1. Read `references/migration-workflow.md`.
2. Update model definitions in `src/apps/api/models`.
3. Create or edit Alembic migration under `src/apps/api/migrations/versions`.
4. Ensure route/schema/service code is aligned with new fields.
5. Validate migration upgrade and downgrade logic locally.
6. Update tests for new constraints and behavior.

## Guardrails

- Do not ship model changes without migration scripts.
- Do not rely on implicit defaults when data compatibility matters.
- Do not run automatic migration in production startup flow.

## References

- Migration workflow: `references/migration-workflow.md`
- Model inventory: `references/model-inventory.md`
