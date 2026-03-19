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

- This file is the always-on workspace guidance. Keep it short and move domain-specific rules into `.github/instructions/`.
- Use `.github/skills/` as the GitHub Copilot skill entrypoint.
- For large or cross-cutting work, prefer the closest matching skill or agent before editing code.

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

- Backend deps: `uv sync --extra dev`
- Frontend deps: `cd src/apps/web && npm install`
- Backend tests: `pytest`
- Coverage: `pytest --cov=src/apps/api --cov-report=term-missing`
- Lint and typing: `ruff check .` and `mypy src`
- Frontend build: `cd src/apps/web && npm run build`

## Conventions

- Python uses 4 spaces, type hints on new or changed code, and thin FastAPI routes with business logic in `services`.
- Vue files stay under `src/apps/web/src`; views use PascalCase filenames and shared API callers live in `src/api`.
- Mock external LLM calls in tests. Do not depend on real model endpoints during CI or routine validation.
- When updating Copilot customization, keep `AGENTS.md` minimal, keep `.instructions.md` files focused, and keep skills self-contained under `.github/skills/<name>`.
