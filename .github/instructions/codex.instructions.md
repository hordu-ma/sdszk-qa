---
description: "Use when Codex or another coding agent is making repository changes and needs the default delivery workflow, validation baseline, and handoff expectations for this project."
applyTo: "Makefile, README.md, src/docs/codex-onboarding.md, .github/workflows/**/*.yml, .github/skills/**/*.md"
---
# Codex Delivery Guidelines

- Prefer the root `Makefile` targets before ad hoc shell commands so common tasks stay predictable.
- Read `src/docs/codex-onboarding.md` when the task spans multiple areas or requires local environment setup.
- For code changes, run the smallest relevant validation first and report any remaining gaps explicitly.
- Keep repository automation lightweight: prefer CI checks that are fast, deterministic, and do not require private infrastructure.
- When adding agent-facing docs, optimize for short, high-signal instructions instead of repeating general coding advice.
