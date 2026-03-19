---
description: "Use when Codex or another coding agent is making repository changes and needs the default execution workflow, confirmation boundaries, validation baseline, and handoff expectations for this project."
applyTo: "Makefile, README.md, src/docs/codex-onboarding.md, .github/workflows/**/*.yml, .github/skills/**/*.md"
---
# Codex Delivery Guidelines

- Default to execution mode for implementation or fix requests. Stay in analysis-only mode only when the user asks for planning, a key requirement is missing, or the change crosses a confirmation boundary below.
- Before a multi-step change, write a short TODO list with at most 5 steps when the work touches more than 2 files or spans code plus tests, config, or docs.
- Stop and confirm before changing API contracts, data models, external dependencies, build or deploy behavior, deleting files, or adding new scripts or documentation files that are not explicitly requested.
- Prefer the root `Makefile` targets before ad hoc shell commands so common tasks stay predictable.
- Read `src/docs/codex-onboarding.md` when the task spans multiple areas or requires local environment setup.
- For code changes, run the smallest relevant validation first and report `已验证项`, `未验证项`, and the reason for any remaining gaps explicitly.
- For config or interface changes, include both the impact scope and a rollback note in the handoff.
- Keep repository automation lightweight: prefer CI checks that are fast, deterministic, and do not require private infrastructure.
- When adding agent-facing docs, optimize for short, high-signal instructions instead of repeating general coding advice.
