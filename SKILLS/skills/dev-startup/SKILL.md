---
name: dev-startup
description: Start or troubleshoot local clinic-sim development environment. Use when bringing up vLLM, Docker dependencies, API, and web app for local development and smoke verification.
---

> 生产部署统一入口：`生产部署指南.md`。

# Dev Startup

Use this skill to boot local dev stack quickly and consistently.

## Execute Workflow

1. Read `references/startup-commands.md`.
2. Start local vLLM with `src/scripts/start_vllm_dev.sh`.
3. Start dependencies with `docker compose -f src/infra/compose/dev.yml up -d`.
4. Start frontend from `src/apps/web`.
5. Verify API and web endpoints.
6. Run basic smoke checks for login and session flow.

## Guardrails

- Keep model path explicit in environments where default path differs.
- Ensure `host.docker.internal` resolution when API in Docker calls local vLLM.
- Shutdown in reverse order after tests.

## References

- Commands and env vars: `references/startup-commands.md`
