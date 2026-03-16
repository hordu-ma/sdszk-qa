# Project Guidelines

## Scope

- This file is the always-on workspace guidance. Keep it short and move domain-specific rules into `.github/instructions/`.
- Use `.github/skills/` as the GitHub Copilot skill entrypoint.
- For large or cross-cutting work, prefer the closest matching skill or agent before editing code.

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
