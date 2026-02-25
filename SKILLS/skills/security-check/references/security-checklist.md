# Security Checklist

> 基础设施与部署请参考：`src/infra/README.md`。

- `.env` and secrets are not committed.
- JWT and service credentials are not hardcoded.
- Production docs endpoints are disabled.
- Database migration behavior is explicit and controlled.
- Rate limiting and auth controls exist on sensitive routes.
