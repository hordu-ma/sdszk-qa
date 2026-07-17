# 开发指南

面向所有开发者和 coding agent 的统一上手文档：环境准备、常用命令、验证分层、交付标准和高风险区域。
（本文合并了原 `codex-onboarding.md` 与 `codex-harness.md`。）

## 项目速览

- 这是"鲁韵思政大模型"的代码仓库：一个面向思政课教师的教学智能支持平台。
- 当前已实现：vLLM 问答主链、教学项目/资料/任务、版本化语义 RAG、六个样板 Skills、显式 Memory、纵向样板、版本差异、结构化 Word 导出、带来源标记的版本化工程评测，以及 `luyun-int`/`luyun-demo` 同镜像晋级。模拟资料和工程评测不得写成专家验收。详见 [README](../../README.md)。
- 产品范围、阶段和验收只看一份文档：[主开发计划](2026-luyun-curriculum-pedagogy-development-plan.md)（v1.0）。目标能力不等于已实现能力，写文档和注释时不要混淆。

目录结构：

| 位置 | 内容 |
| --- | --- |
| `src/apps/api` | 后端（FastAPI + SQLAlchemy 异步） |
| `src/apps/web` | 前端（Vue 3 + Vite + TypeScript） |
| `src/infra/compose` | Docker Compose 与部署配置 |
| `tests` | 后端测试（单元 + 集成） |
| `src/cases` | 种子案例数据 |
| `src/docs` | 计划与文档 |

阅读顺序：`AGENTS.md` → 本文 → 涉及产品范围时读主开发计划相关章节 → 开发样板时读[阶段 1 工程冻结基线](2026-stage1-g0-engineering-baseline.md)；替换模拟资料时同时读[模拟信息替换台账](2026-stage1-synthetic-replacement-ledger.md) → 需要具体工作流时经 `.github/INDEX.md` 找最小相关文档。

## 环境准备（新 clone）

```bash
make doctor              # 确认 uv、npm、docker compose 可用
make harness-bootstrap   # 安装前后端依赖
make harness-quick       # 首次完整快速验证
```

## 验证命令分层

优先使用根目录 `Makefile`，避免一次性命令漂移：

| 命令 | 用途 | 外部依赖 |
| --- | --- | --- |
| `make harness-backend` | ruff + basedpyright + 非集成 pytest | 无 |
| `make harness-quick` | 后端快速门禁 + 前端构建 | 无 |
| `make test-integration` | 集成测试 | PostgreSQL |
| `make harness-full` | lint、类型、全部测试、前端构建 | PostgreSQL |
| `make test-cov` | 覆盖率报告 | 视范围 |
| `make validate-cases` | 种子案例一致性校验 | 无 |
| `make web-build` | 仅前端构建 | 无 |

集成测试需要带 `vector` 扩展的 PostgreSQL（Compose 已固定 `pgvector/pgvector:pg17-trixie`）：

```bash
make dev-up      # 启动本地 PostgreSQL、MinIO、API
make test-integration
make dev-down
```

```text
postgresql+psycopg://postgres:postgres@localhost:5432/luyun_sizheng
```

测试夹具读取 `TEST_DATABASE_URL`（不是直接读取 `DATABASE_URL`）。本机默认端口不是带 `vector` 扩展的 PostgreSQL 时，应显式指向独立测试库，禁止把集成测试指向 `luyun-int` 运行库：

```bash
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:<测试端口>/luyun_sizheng make harness-full
```

等价原生命令（不便使用 make 时）：

```bash
uv sync --frozen --extra dev
npm --prefix src/apps/web install
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev basedpyright
uv run --frozen --extra dev pytest -m "not integration"
uv run --frozen --extra dev pytest -m integration
npm --prefix src/apps/web run build
```

依赖校验一律使用 frozen 模式，日常验证不得改写 `uv.lock`。

## 开发约定

1. 最小可行改动，不做无关重构；优先服务当前纵向样板，不并行铺模块。
2. 路由保持薄层，业务逻辑放 `services/`；Skill 执行统一走 `skill_runtime.run_skill`。
3. 测试中必须 mock 外部 LLM、Embedding 和 Reranker 调用，不依赖真实模型服务。
4. 改配置或接口时，交付说明中写清影响范围和回滚方式。
5. 不实现教师/学生评分、排名（`tests/test_no_scoring_paths.py` 有防护断言）。
6. 不把隐式会话历史当作用户 Memory；Memory 只走显式对象与注入审计。
7. 不在本仓实现注册、短信、KYC（由思政课平台用户管理承担，见计划 §2.6）。
8. 不另建 `tasks.md` 之类的第二套排期；阶段状态直接以"实施记录"更新主计划。
9. 实现若需偏离计划中的范围或工程顺序，先改计划或先获确认，再动代码。
10. 评测数据必须声明 `data_origin`；`synthetic` 数据不得改成专业审核通过，替换真实资料时创建新数据集版本并重新跑发布清单绑定回归。

## 交付标准

- 改动后至少运行与其直接相关的最小验证；后端改动跑 `make harness-backend`，前端改动至少 `make web-build`。
- 涉及数据库、认证、会话或 SSE 链路时补跑 `make test-integration`。
- 行为变更配套回归测试。
- 交付说明列出已运行命令、未验证项和残余风险；无法验证时说明原因。

## 高风险区域

| 位置 | 风险 |
| --- | --- |
| `src/apps/api/routes/chat.py` | SSE 输出链路，对响应格式和缓冲行为敏感 |
| `src/apps/api/config.py` | 配置在导入时生效，测试环境变量需稳定 |
| `src/infra/compose/*.yml`、`nginx.conf` | 涉及部署联调，改动前后说明影响范围 |
| 数据库模型与迁移 | 变更 schema 要同步 migration、service、schema 和 tests |
| `services/retrieval_gateway.py` | 外部向量契约；必须校验维度、返回数量、rerank 索引完整性并保留降级链 |

## CI 对齐

GitHub Actions backend job 使用 PostgreSQL service，顺序执行：依赖安装（frozen）→ ruff → basedpyright → `make test-unit` → `make test-integration`；frontend job 执行 `npm ci` 和 `npm run build`。本地 `make harness-quick` 是日常最小门禁，CI 是更完整的回归门禁。

## `.github` 目录约定

- `.github/workflows/` 是 CI 所在位置。
- `.github/instructions/`、`.github/skills/`、`.github/agents/` 是按任务类型索引的辅助工作流文档，入口是 `.github/INDEX.md`；不要默认通读整个目录。
- 新增或调整这些辅助文档时同步更新 `.github/INDEX.md`。
