# Alignment Workflow

> 生产部署统一入口：`生产部署指南.md`。

1. Inspect backend changes in:

- `src/apps/api/routes`
- `src/apps/api/schemas`

2. Update frontend wrappers:

- `src/apps/web/src/api/*.ts`

3. Update frontend types:

- `src/apps/web/src/types/*.ts`

4. Validate:

- build/typecheck frontend
- verify common user flows
