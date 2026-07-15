---
description: "Use when implementing or refactoring FastAPI routes, schemas, services, models, or backend integrations in src/apps/api. Covers layering, validation, and API contract changes."
applyTo: "src/apps/api/**/*.py"
---
# Backend Guidelines

- Keep route handlers thin: parse input, resolve dependencies, call service logic, and shape the response.
- Put business rules in `src/apps/api/services` or a dedicated utility module, not inline in `routes` (current chat orchestration in `routes/chat.py` is technical debt to extract when touched).
- Define or update schemas before changing endpoint behavior when request or response contracts move.
- Reuse dependency aliases and shared exception patterns from `dependencies.py` and `exceptions.py`.
- If database behavior changes, check whether a migration and targeted tests are required.
- Product range for Skills, Memory, teaching projects, and non-scoring diagnosis follows `src/docs/2026-luyun-curriculum-pedagogy-development-plan.md`; do not implement teacher/student total scoring.
- Future Skill/Memory endpoints belong in services with audited SkillRun/memory injection records, not ad-hoc prompts in routes.
