---
name: codex-delivery
description: Use when Codex is implementing, validating, or shipping repository changes in this project and needs the standard workflow for task entry, verification, and handoff.
---

# Codex Delivery

Use this skill for cross-cutting delivery work that touches multiple areas of the repository.

## Execute Workflow

1. Read `src/docs/codex-onboarding.md` for project entrypoints and validation expectations.
2. Prefer root `Makefile` targets for setup, lint, typing, tests, web build, and local compose tasks.
3. Reuse existing `.github/instructions/` and more specific `.github/skills/` before creating new patterns.
4. Run the smallest relevant validation set first, then expand only if the change surface requires it.
5. In the handoff, include key file paths, validation results, and any unverified risk.

## Guardrails

- Keep changes minimal and aligned with current structure.
- Do not claim full verification when only partial checks ran.
- Treat config, infra, and API contract edits as higher-risk and call out rollback impact.

## References

- Onboarding guide: `src/docs/codex-onboarding.md`
- Testing guidance: `.github/instructions/testing.instructions.md`
