# 临床医学模拟问诊系统

用于临床医学教学的模拟问诊平台：学生负责诊断，LLM 始终扮演病人，完整流程可审计。

## 功能概览

- 登录认证（无注册，外部系统同步用户）
- 病例浏览与筛选（不暴露标准答案）
- 会话创建与历史查询
- SSE 流式对话（医生提问，病人回答）
- 检查申请与结果回显
- 诊断提交与规则评分
- 评分详情可追溯（维度分、关键点覆盖、检查合理性）

## 系统组件

- 前端：Vue 3 + Vant（移动端友好）
- 后端：FastAPI + SQLAlchemy（异步）
- 模型：vLLM（OpenAI 兼容接口）
- 存储：PostgreSQL（业务数据）、MinIO（对象存储）
- 代理：Nginx（HTTPS 与 SSE 反代）

## 核心流程

登录 → 病例列表 → 创建会话 → 流式问诊 → 申请检查 → 提交诊断 → 查看评分 → 历史会话

## 关键接口

- 认证：`POST /api/auth/login`、`GET /api/auth/me`
- 病例：`GET /api/cases`、`GET /api/cases/{case_id}`、`GET /api/cases/{case_id}/available-tests`
- 会话：`POST /api/sessions`、`GET /api/sessions`、`GET /api/sessions/{session_id}`
- 对话：`POST /api/chat`（SSE）
- 检查：`POST /api/sessions/{session_id}/tests`、`GET /api/sessions/{session_id}/tests`
- 评分：`POST /api/sessions/{session_id}/submit`、`GET /api/sessions/{session_id}/score`

## 开发与部署

- 开发环境与命令：见 [AGENTS.md](AGENTS.md)
- 生产部署总入口：见 [生产部署指南.md](生产部署指南.md)
- 执行流程（SKILL触发）：见 [SKILLS/README.md](SKILLS/README.md)
- 架构详解：见 [src/docs/ARCHITECTURE.md](src/docs/ARCHITECTURE.md)

## 测试

```bash
pytest                                              # 运行全部测试
pytest --cov=src/apps/api --cov-report=term-missing  # 覆盖率
```

## 可审计数据

- messages（对话内容、token、延迟）
- sessions（状态、诊断提交、时间）
- scores（维度分与评分依据）
- audit_logs（用户行为）

## 一键重启本地联调环境（命令顺序清单）

> 适用于当前常态：WSL 开发、vLLM 在宿主机、PostgreSQL/MinIO 用 Docker、API 用 `uv run` 在宿主机启动。

### 0) 先清理旧进程（可重复执行）

```bash
# 项目根目录执行
docker compose -f src/infra/compose/dev.yml down
pkill -f "vllm.entrypoints.openai.api_server" || true
pkill -f "uvicorn src.apps.api.main:app" || true
pkill -f "vite --host 0.0.0.0 --port 5173" || true
```

### 1) 终端 A：启动 vLLM（8001）

```bash
bash src/scripts/start_vllm_dev.sh
```

### 2) 终端 B：启动 PostgreSQL + MinIO（5432/9000/9001）

```bash
docker compose -f src/infra/compose/dev.yml up -d --pull never postgres minio
```

### 3) 终端 C：启动 API（8000）

```bash
DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/clinic_sim' \
MINIO_ENDPOINT='localhost:9000' \
LLM_BASE_URL='http://localhost:8001' \
LLM_MODEL='/home/malig/.cache/modelscope/hub/models/Qwen/Qwen2.5-1.5B-Instruct' \
uv run uvicorn src.apps.api.main:app --host 0.0.0.0 --port 8000 --reload
```

说明：`LLM_MODEL` 需与 `curl -sS http://localhost:8001/v1/models` 返回的 `id` 一致。

### 4) 终端 D：启动前端（5173）

```bash
cd src/apps/web
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

### 5) 冒烟检查（任意终端）

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:8001/v1/models
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:8000/health
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:5173/
curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:9001/
```

预期：`200 / 200 / 200 / 200`。
