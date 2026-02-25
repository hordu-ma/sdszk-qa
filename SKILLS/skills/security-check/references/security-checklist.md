# Security Checklist

> 生产部署统一入口：`生产部署指南.md`。

- `.env` and secrets are not committed.
- JWT and service credentials are not hardcoded.
- Production docs endpoints are disabled.
- Database migration behavior is explicit and controlled.
- Rate limiting and auth controls exist on sensitive routes.
