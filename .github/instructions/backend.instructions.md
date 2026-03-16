---
description: "Use when implementing or refactoring FastAPI routes, schemas, services, models, or backend integrations in src/apps/api. Covers layering, validation, and API contract changes."
applyTo: "src/apps/api/**/*.py"
---
# Backend Guidelines

- Keep route handlers thin: parse input, resolve dependencies, call service logic, and shape the response.
- Put business rules in `src/apps/api/services` or a dedicated utility module, not inline in `routes`.
- Define or update schemas before changing endpoint behavior when request or response contracts move.
- Reuse dependency aliases and shared exception patterns from `dependencies.py` and `exceptions.py`.
- If database behavior changes, check whether a migration and targeted tests are required.
