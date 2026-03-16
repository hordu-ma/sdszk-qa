---
description: "Use when editing Dockerfiles, docker compose files, shell startup scripts, or deployment-related configuration under src/infra and src/scripts."
applyTo:
  - "src/infra/**/*.yml"
  - "src/infra/**/*.yaml"
  - "src/apps/api/Dockerfile"
  - "src/scripts/**/*.sh"
---
# Infra Guidelines

- Keep development and production compose concerns separated and consistent with `src/infra/README.md`.
- Do not hardcode secrets, credentials, or environment-specific endpoints into compose files or scripts.
- Prefer explicit environment variables and comments only where behavior would otherwise be easy to misread.
- If startup order or dependency wiring changes, verify the documented local startup flow still matches the files.
