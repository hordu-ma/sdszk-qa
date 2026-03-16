---
description: "Use when creating or refactoring GitHub Copilot customization files such as AGENTS.md, .instructions.md, .agent.md, or project skills under .github/skills."
applyTo:
  - "AGENTS.md"
  - ".github/**/*.md"
---
# Copilot Customization Guidelines

- Keep `AGENTS.md` minimal and always-on; move domain-specific rules into focused `.github/instructions/*.instructions.md` files.
- Keep each instruction file centered on one concern with a narrow `applyTo` or a keyword-rich `description`.
- Keep custom agents single-role, with the smallest tool set that still lets them finish their job.
- Treat `.github/skills/` as the runtime source of truth.
- Make descriptions explicit about when the instruction, skill, or agent should be invoked so Copilot can discover them reliably.
