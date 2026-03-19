# .github Documentation Index

Read this file before opening any other file in `.github/`.

## Purpose

This index is the entrypoint for repository customization, agent workflow, and task-specific guidance under `.github`.
Use it to find the minimum relevant documentation for the current task instead of reading the entire `.github` directory.

## Reading Order

When working in this repository, load instructions in this order:

1. System/workspace `rules`
2. `AGENTS.md`
3. `.github/INDEX.md`
4. Only the specific `.github` documents relevant to the current task

If instructions conflict, higher items in the list take precedence.

## Core Documents

### Instructions

Use these for scoped, file-pattern-based guidance.

- `.github/instructions/backend.instructions.md`
  - Read when changing FastAPI routes, schemas, services, models, or backend integrations under `src/apps/api`.

- `.github/instructions/frontend.instructions.md`
  - Read when changing Vue 3, Vite, Vant, frontend state, routing, or API flow under `src/apps/web`.

- `.github/instructions/testing.instructions.md`
  - Read when adding or updating backend tests under `tests`.

- `.github/instructions/infra.instructions.md`
  - Read when editing Dockerfiles, compose files, deployment config, or startup scripts under `src/infra` and `src/scripts`.

- `.github/instructions/codex.instructions.md`
  - Read when the task spans multiple areas, changes repository workflow/docs, or needs default execution, confirmation, validation, and handoff guidance.

- `.github/instructions/copilot-customization.instructions.md`
  - Read when editing `AGENTS.md`, `.instructions.md`, `.agent.md`, or files under `.github/skills`.

### Agents

Use these when delegating or framing a task around a single responsibility.

- `.github/agents/backend-delivery.agent.md`
  - Backend implementation and backend test updates.

- `.github/agents/frontend-delivery.agent.md`
  - Frontend implementation, UI behavior, and web build validation.

- `.github/agents/copilot-workflow.agent.md`
  - Repository customization work for instructions, skills, and agent workflow files.

### Hooks

- `.github/hooks/stop-confirmation.json`
  - Read only when working on repository hook behavior or troubleshooting tool/command interception.

## Skills

Use skills as workflow playbooks for recurring task types.

- `.github/skills/dev-startup/SKILL.md`
  - Start or troubleshoot the local development environment.

- `.github/skills/codex-delivery/SKILL.md`
  - Cross-cutting repository delivery workflow, validation baseline, and handoff expectations.

- `.github/skills/add-api-endpoint/SKILL.md`
  - Add or modify FastAPI endpoints, schemas, service wiring, and endpoint tests.

- `.github/skills/change-db-model/SKILL.md`
  - Change SQLAlchemy models and Alembic migrations safely.

- `.github/skills/api-alignment/SKILL.md`
  - Keep backend API changes and frontend API/types aligned.

- `.github/skills/frontend-flow/SKILL.md`
  - Change Vue page flows, router behavior, and user journey logic.

- `.github/skills/production-deploy/SKILL.md`
  - Production deployment and rollout verification across servers and services.

- `.github/skills/extend-scoring/SKILL.md`
  - Reserved placeholder for future scoring-module work; do not use unless that module is introduced.

## Reference Documents

Open these only through the relevant skill unless the task specifically asks for them.

### API / Backend
- `.github/skills/add-api-endpoint/references/workflow.md`
- `.github/skills/add-api-endpoint/references/api-surface.md`
- `.github/skills/change-db-model/references/migration-workflow.md`
- `.github/skills/change-db-model/references/model-inventory.md`

### Frontend / Contract Alignment
- `.github/skills/api-alignment/references/alignment-workflow.md`
- `.github/skills/api-alignment/references/api-map.md`
- `.github/skills/frontend-flow/references/flow-map.md`

### Delivery / Startup / Deployment
- `.github/skills/dev-startup/references/startup-commands.md`
- `.github/skills/production-deploy/references/deploy-checklist.md`
- `.github/skills/production-deploy/references/runtime-files.md`

### Placeholder / Future Work
- `.github/skills/extend-scoring/references/scoring-rules.md`
- `.github/skills/extend-scoring/references/scoring-touchpoints.md`

## Task Routing Guide

Use the following shortcuts to decide what to read next.

- Backend feature or bug fix
  1. `.github/instructions/backend.instructions.md`
  2. `.github/instructions/testing.instructions.md` if tests change
  3. Relevant backend skill if the task matches a known workflow

- Frontend feature or bug fix
  1. `.github/instructions/frontend.instructions.md`
  2. `.github/skills/frontend-flow/SKILL.md` for route or page-flow changes
  3. `.github/skills/api-alignment/SKILL.md` if backend contract changes are involved

- New API endpoint or contract change
  1. `.github/instructions/backend.instructions.md`
  2. `.github/skills/add-api-endpoint/SKILL.md`
  3. `.github/skills/api-alignment/SKILL.md` if frontend also needs updates
  4. `.github/instructions/testing.instructions.md`

- Database schema/model change
  1. `.github/instructions/backend.instructions.md`
  2. `.github/skills/change-db-model/SKILL.md`
  3. `.github/instructions/testing.instructions.md`

- Local environment startup or smoke verification
  1. `.github/skills/dev-startup/SKILL.md`

- Deployment or infra change
  1. `.github/instructions/infra.instructions.md`
  2. `.github/skills/production-deploy/SKILL.md`

- Repository instruction or agent customization
  1. `.github/instructions/copilot-customization.instructions.md`
  2. `.github/instructions/codex.instructions.md`
  3. `.github/agents/copilot-workflow.agent.md`

- Cross-cutting implementation across multiple areas
  1. `.github/instructions/codex.instructions.md`
  2. `.github/skills/codex-delivery/SKILL.md`
  3. Then open the backend/frontend/infra/testing instructions actually needed

## Reading Policy

- Do not read the entire `.github` directory by default.
- Use this file as the navigation entrypoint.
- Read only the documents required for the current task.
- Prefer the most specific instruction or skill that matches the work.
- For broad tasks, start with `.github/instructions/codex.instructions.md` and `.github/skills/codex-delivery/SKILL.md`.
