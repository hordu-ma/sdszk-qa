---
name: production-deploy
description: Deploy luyun-sizheng production stack across A/B servers with Nginx, API, vLLM, and storage services. Use when preparing production compose configs, environment variables, rollout checks, and post-deploy verification.
---

# Production Deploy

Use this skill for production release and environment checks.

## Execute Workflow

1. Read `references/deploy-checklist.md`.
2. Validate required environment variables before deployment.
3. Deploy core layer with `src/infra/compose/prod-b.yml`.
4. Build frontend artifacts and upload `src/apps/web/dist` to A server static path.
5. Merge `src/infra/compose/nginx/nginx.conf` location snippet into existing Nginx server block.
6. Verify API health, auth, chat streaming, and frontend access.

## Guardrails

- Never commit production secrets.
- Keep Swagger disabled in production env.
- Open only required ports.
- Run migration explicitly, not via implicit app startup.

## References

- Deployment checklist: `references/deploy-checklist.md`
- Runtime files map: `references/runtime-files.md`
- Unified production guide: `src/infra/README.md`
