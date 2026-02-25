# Workflow

> 生产部署统一入口：`生产部署指南.md`。

## Scope Inputs

- Route path and HTTP method
- Requires auth or public
- Request body/query model
- Response model
- Side effects: DB write, external call, streaming

## Implementation Steps

1. Add/adjust schema files in `src/apps/api/schemas`.
2. Add/adjust route function in matching file under `src/apps/api/routes`.
3. Call service function for non-trivial logic.
4. Validate permission checks with `CurrentUser` where required.
5. Keep DB access async and explicit.
6. Add tests for:

- valid request
- validation error
- auth/permission failure
- not found/conflict where relevant

## Done Criteria

- Response format matches schema
- Route layer remains orchestration only
- Tests for happy and critical error paths pass
