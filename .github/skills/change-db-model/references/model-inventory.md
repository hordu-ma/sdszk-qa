# Model Inventory

> 基础设施与部署请参考：`src/infra/README.md`。

Core models:

- `users`
- `cases`
- `sessions`
- `messages`
- `audit_logs`

Historical migrations may mention removed medical-domain tables and fields. Treat the latest migration state and current ORM models as authoritative; do not recreate `scores`, `test_requests`, or medical case fields.

Location: `src/apps/api/models`
Migration location: `src/apps/api/migrations/versions`
