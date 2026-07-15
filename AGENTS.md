# Project Guidelines

## Communication

- Default to Chinese for user-visible plans, progress updates, explanations, and final handoff.
- Lead with the conclusion, then the key details.
- Mark uncertain information explicitly as `假设/待确认`.

## Instruction Loading Order

Before making changes, load instructions in this order:

1. System/workspace `rules`
2. `AGENTS.md`
3. `.github/INDEX.md`
4. Only the specific `.github` documents referenced by the index that are relevant to the current task

Instruction precedence follows the same order. Do not scan the entire `.github` directory by default; use `.github/INDEX.md` as the entrypoint for on-demand reading.

## Scope

- This file is the always-on workspace guidance. Keep it short and move domain-specific rules into scoped docs.
- Product range, phases, acceptance, product Skills, and user Memory: `src/docs/2026-luyun-curriculum-pedagogy-development-plan.md` (v1.0) is the single source of truth. Do not treat `2026-product-extension-*.md` as schedule.
- User registration and identity upgrade (registered vs verified) are specified in plan §2.6 and **must be implemented in the 思政课平台 user-management system**, not in this repo. Do not add phone signup, SMS, or KYC flows here; only consume platform tokens/claims when integrating.
- Use `src/docs/codex-harness.md` as the Codex validation harness entrypoint.
- Keep `.github` for GitHub Actions plus Codex-readable auxiliary instructions, skills, hooks, and agent playbooks; use `.github/INDEX.md` before opening other `.github` files.
- For large or cross-cutting work, prefer the closest matching skill or agent before editing code.
- Do not implement teacher/student total scoring or ranking. Diagnosis is formative and evidence-based, not a score product.
- Do not invent open agent tool markets or silent long-term user profiling; follow the plan's product Skills and Memory model when those features are built.

## Delivery Baseline

- Prefer the smallest viable change and keep the existing code style and structure unless the task explicitly asks for a broader refactor.
- If config, interface, or workflow behavior changes, explain the affected scope and the rollback path in the handoff.
- Run the smallest relevant validation you can for the changed area. If validation cannot run, state why and call out the remaining risk.
- Ask before destructive or high-risk operations that are not already explicitly requested.

## Architecture

- Backend API: `src/apps/api`
- Frontend app: `src/apps/web`
- Infra and compose files: `src/infra/compose`
- Test suite: `tests`
- Seed cases and docs: `src/cases`, `src/docs`

## Build And Test

- Backend deps: `uv sync --frozen --extra dev`
- Frontend deps: `cd src/apps/web && npm install`
- Backend unit tests: `pytest -m "not integration"`
- Backend integration tests: `pytest -m integration` after PostgreSQL is available
- Coverage: `pytest --cov=src/apps/api --cov-report=term-missing`
- Lint and typing: `ruff check .` and `basedpyright`
- Frontend build: `cd src/apps/web && npm run build`

## Conventions

- Python uses 4 spaces, type hints on new or changed code, and thin FastAPI routes with business logic in `services` (today much chat orchestration still lives in `routes/chat.py`; prefer extracting when touching that path).
- Vue files stay under `src/apps/web/src`; views use PascalCase filenames and shared API callers live in `src/api`. Target UX for teaching workflows is desktop-first workbench, not mobile-only chat.
- Mock external LLM calls in tests. Do not depend on real model endpoints during CI or routine validation.
- When updating Codex workflow customization, keep `AGENTS.md` minimal, keep `.instructions.md` files focused, and keep harness docs concise.
- Prefer the vertical-sample engineering order in the development plan over parallel feature sprawl.
