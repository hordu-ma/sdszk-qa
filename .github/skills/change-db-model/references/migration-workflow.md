# Migration Workflow

> 基础设施与部署请参考：`src/infra/README.md`。

## Steps

1. Change SQLAlchemy model in `src/apps/api/models`.
2. Generate or handwrite migration in `src/apps/api/migrations/versions`.
3. Verify `upgrade()` applies cleanly.
4. Verify `downgrade()` rolls back safely.
5. Run tests affected by changed entities.

## Checklist

- Column type and nullability are explicit.
- Index/constraint names remain stable.
- Existing rows have a compatibility path.
- API schemas are synchronized.
