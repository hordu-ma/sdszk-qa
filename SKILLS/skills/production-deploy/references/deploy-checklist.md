# Deploy Checklist

> 生产部署统一入口：`生产部署指南.md`。

## Required env vars

- `POSTGRES_PASSWORD`
- `MINIO_ROOT_PASSWORD`
- `JWT_SECRET`
- `LLM_BASE_URL`
- `LLM_MODEL`

## Deploy sequence

1. Core services up on B server.
2. API up and healthy.
3. Frontend build artifacts ready.
4. Frontend artifacts uploaded to A server static path.
5. Nginx location snippet merged into existing A server Nginx config.
6. End-to-end smoke tests.
