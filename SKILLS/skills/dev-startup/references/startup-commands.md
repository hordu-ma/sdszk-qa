# Startup Commands

> 生产部署统一入口：`生产部署指南.md`。

## vLLM

`src/scripts/start_vllm_dev.sh`

Common env vars:

- `MODEL_PATH`
- `PORT`
- `MAX_MODEL_LEN`
- `GPU_MEMORY_UTILIZATION`

## API + DB + MinIO

Standard mode:

`docker compose -f src/infra/compose/dev.yml up -d --build`

Fallback mode (network constrained):

`docker compose -f src/infra/compose/dev.yml up -d --pull never postgres minio`

Host API startup (fallback mode):

`DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/luyun_sizheng MINIO_ENDPOINT=localhost:9000 LLM_BASE_URL=http://localhost:8001 LLM_MODEL=/home/<you>/.cache/modelscope/hub/models/Qwen/Qwen2.5-1.5B-Instruct uv run uvicorn src.apps.api.main:app --host 0.0.0.0 --port 8000 --reload`

Important:

- `LLM_MODEL` must match the `id` returned by `http://localhost:8001/v1/models`.

## Frontend

From `src/apps/web`:

- `npm install`
- `npm run dev`

## Shutdown

- Stop frontend process
- `docker compose -f src/infra/compose/dev.yml down`
- Stop vLLM process
