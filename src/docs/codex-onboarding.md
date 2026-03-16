# Codex Onboarding

本文件用于让 Codex 或其他代码代理快速进入可工作状态，减少重复探测和误改。

## 项目目标

- 面向思政教学场景的问答支持系统
- 后端位于 `src/apps/api`
- 前端位于 `src/apps/web`
- 基础设施与 compose 位于 `src/infra/compose`
- 测试位于 `tests`

## 优先遵循的规则

1. 先读根目录 `AGENTS.md` 和 `.github/instructions/`
2. 保持最小可行改动，不做无关重构
3. 后端保持薄路由，业务逻辑放入 `services`
4. 外部 LLM 调用在测试中必须 mock，不依赖真实模型服务
5. 改配置或接口时，说明影响范围与回滚方式

## 常用命令

优先使用根目录 `Makefile`：

```bash
make setup
make lint
make typecheck
make test
make test-api
make web-build
make dev-up
make dev-down
make doctor
```

等价原生命令：

```bash
uv sync --extra dev
npm --prefix src/apps/web install
uv run ruff check .
uv run basedpyright
uv run pytest
npm --prefix src/apps/web run build
docker compose -f src/infra/compose/dev.yml up -d
```

## 最低交付标准

- 代码修改后至少运行与改动直接相关的验证
- 后端行为变更优先补或更新 `tests/` 中的回归测试
- 前端行为变更至少执行一次 `make web-build`
- 无法验证时，明确说明原因、影响范围和残余风险

## 高风险区域

- `src/apps/api/routes/chat.py`：SSE 输出链路，容易受响应格式和缓冲行为影响
- `src/apps/api/config.py`：配置项在导入时生效，测试环境变量需稳定
- `src/infra/compose/*.yml` 与 `src/infra/compose/nginx/nginx.conf`：涉及部署和联调，改动前后要说明影响范围
- 数据库模型与迁移：变更 schema 时要同步考虑 migration、service、schema 和 tests

## 推荐工作流

1. 先定位改动表面和依赖文件
2. 优先查找现有 `.github/skills/` 是否已有匹配技能
3. 做最小改动，避免顺手重构
4. 先跑最小相关验证，再决定是否扩大验证范围
5. 输出结果时附关键文件路径和未验证风险
