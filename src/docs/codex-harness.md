# Codex Harness

本文件是新 clone 仓库后的 Codex 验证 harness 入口，用于把初始化、快速验证、依赖型集成验证和最终交付检查分层执行。

## 目标

- 新环境先确认工具链，再安装依赖。
- 默认快速检查不依赖真实 LLM、MinIO 或 PostgreSQL。
- 需要外部服务的测试显式标记为 `integration`，单独运行。
- Codex 交付时优先使用根目录 `Makefile` 目标，减少一次性命令漂移。

## 分层命令

| 层级           | 命令                     | 用途                                                                   | 外部依赖          |
| -------------- | ------------------------ | ---------------------------------------------------------------------- | ----------------- |
| 环境探测       | `make doctor`            | 查看 `uv`、`npm`、`docker compose` 是否可用                            | 本机工具链        |
| 首次初始化     | `make harness-bootstrap` | 执行 `doctor`、后端 `uv sync --frozen --extra dev`、前端 `npm install` | 网络、包管理器    |
| 后端快速门禁   | `make harness-backend`   | `ruff`、`basedpyright`、非集成 pytest                                  | 无真实外部服务    |
| 本地快速门禁   | `make harness-quick`     | 后端快速门禁 + 前端构建                                                | 无真实外部服务    |
| 依赖型集成测试 | `make test-integration`  | 运行标记为 `integration` 的测试                                        | PostgreSQL 可访问 |
| 完整本地门禁   | `make harness-full`      | lint、类型检查、全部 pytest、前端构建                                  | 取决于集成测试    |

## 新 clone 推荐流程

```bash
make harness-bootstrap
make harness-quick
```

如果要运行集成测试，先准备 PostgreSQL：

```bash
make dev-up
make test-integration
make dev-down
```

`make dev-up` 会启动 `src/infra/compose/dev.yml` 中的 PostgreSQL、MinIO 和 API。若只想运行集成测试，也可以自行提供与 `tests/conftest.py` 一致的 PostgreSQL：

```text
postgresql+psycopg://postgres:postgres@localhost:5432/luyun_sizheng
```

## Codex 交付约定

1. 改动前先读 `AGENTS.md` 和本文件；产品范围/阶段问题以 `src/docs/2026-luyun-curriculum-pedagogy-development-plan.md` 为准；再通过 `.github/INDEX.md` 打开最小相关文档。
2. 优先选择最小可验证命令：后端改动先跑 `make harness-backend`，前端改动至少跑 `make web-build`。
3. 涉及数据库、认证、会话或 SSE 链路时，补跑 `make test-integration`。
4. 最终交付说明中明确列出已运行命令、未验证项和残余风险。
5. 文档驱动：若实现偏离开发计划中的 Skills/Memory/非评分/工程顺序，须在 handoff 标明并先改计划或获确认。

## `.github` 对齐原则

- `.github/workflows/` 是 CI 所需位置，保留不迁移。
- `.github/instructions/`、`.github/agents/`、`.github/skills/` 是 Codex 可读取的辅助规则与 playbook，不作为主入口。
- 新增或调整这些辅助文档时，必须同步更新 `.github/INDEX.md`，避免重复来源和发现路径混乱。

## CI 对齐

GitHub Actions 中 backend job 使用 PostgreSQL service，并按以下顺序执行：

1. `uv sync --frozen --extra dev`
2. `uv run ruff check .`
3. `uv run basedpyright`
4. `make test-unit`
5. `make test-integration`

frontend job 使用 `npm ci` 和 `npm run build`。本地 `make harness-quick` 是日常最小门禁，CI 是更完整的回归门禁。
