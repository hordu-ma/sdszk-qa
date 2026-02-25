# 仓库协作规范

## 项目结构与模块组织

- `src/apps/api/`：FastAPI 后端（`routes/`、`schemas/`、`models/`、`services/`、`migrations/`）。
- `src/apps/web/`：Vue 3 + Vite 前端（`src/views`、`src/api`、`src/stores`、`src/router`）。
- `src/infra/compose/`：开发与生产环境的 Docker Compose 文件（`dev.yml`、`prod-a.yml` 占位、`prod-b.yml`）。
- `src/cases/`：主题种子 JSON 文件。
- `tests/`：后端 pytest 测试套件（集成测试与服务/配置测试）。
- `src/scripts/`：工具脚本（例如 `start_vllm_dev.sh`、`import_cases.py`）。

## 构建、测试与开发命令

- 后端依赖：`uv sync --extra dev`
- 前端依赖：`cd src/apps/web && npm install`
- 启动本地栈（API + PostgreSQL + MinIO）：`docker compose -f src/infra/compose/dev.yml up -d`
- 启动前端开发服务器：`cd src/apps/web && npm run dev`
- 运行后端测试：`pytest`
- 运行覆盖率：`pytest --cov=src/apps/api --cov-report=term-missing`
- 后端静态检查：`ruff check .`
- 后端类型检查：`mypy src`
- 构建前端：`cd src/apps/web && npm run build`

## 编码风格与命名规范

- Python：4 空格缩进；新建/修改代码需补充类型注解；最大行宽 `100`（Ruff）。
- Python 模块/函数：`snake_case`；类/Pydantic 模型：`PascalCase`；常量：`UPPER_SNAKE_CASE`。
- Vue/TypeScript：视图组件放在 `src/views`，文件名使用 `PascalCase.vue`（例如 `SessionList.vue`）；API 封装放在 `src/api/*.ts`。
- 保持后端分层命名一致（`routes/sessions.py` ↔ `schemas/sessions.py` ↔ `models/sessions.py`）。

## 测试规范

- 测试框架：`pytest` + `pytest-asyncio`（`asyncio_mode=auto`）。
- 命名规范：文件 `test_*.py`，类 `Test*`，函数 `test_*`（由 `pyproject.toml` 约束）。
- 优先使用 API 流程的集成测试（`tests/test_integration.py`）与服务层的聚焦单元测试（`tests/test_prompt_builder.py`）。
- 测试中应 mock 外部 LLM 调用；CI 中不要请求真实模型端点。

## Commit 与 Pull Request 规范

- 遵循仓库历史中的 Conventional Commit 风格：`feat: ...`、`fix: ...`、`refactor(scope): ...`、`docs: ...`。
- 保持提交范围清晰且原子化（尽量分离 API、前端、基础设施改动）。
- PR 需包含清晰摘要、关联 issue/任务（如有）以及测试证据（`pytest`、前端构建输出）。
- UI 更新请附截图或 GIF。
- 涉及 `src/apps/api/migrations/` 时请补充迁移说明。

## 安全与配置建议

- 复制 `.env.example` 为 `.env`；严禁提交真实密钥。
- 必填敏感变量包括 `JWT_SECRET`、数据库/MinIO 密码、`LLM_BASE_URL`。
- 生产环境请关闭 Swagger，避免使用默认开发凭据。

## 部署文档入口

- 本地开发启动：`src/docs/本地开发启动指南.md`
- 基础设施与部署：`src/infra/README.md`
