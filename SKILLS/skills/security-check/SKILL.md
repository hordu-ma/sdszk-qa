---
name: security-check
description: Run a focused security hygiene review for luyun-sizheng changes. Use when touching auth, config, deployment, or external integrations to verify secret handling, access control, and exposure risks.
---

> 生产部署统一入口：`生产部署指南.md`。

# Security Check

Use this skill for change-time security checks.

## Execute Workflow

1. Read `references/security-checklist.md`.
2. Verify secret handling in code, compose files, and docs.
3. Check auth and permission paths for changed endpoints.
4. Confirm production-safe defaults for docs, debug, and migration behavior.
5. Flag risks and required follow-up actions with file references.

## Guardrails

- Never allow committed `.env` files.
- Never keep weak JWT defaults in production settings.
- Require explicit mention of any unresolved security risk.

## References

- Security checklist: `references/security-checklist.md`
