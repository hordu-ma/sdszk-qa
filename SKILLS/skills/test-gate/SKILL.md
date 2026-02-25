---
name: test-gate
description: Apply test and change-quality gate for luyun-sizheng modifications. Use when reviewing or shipping changes to ensure affected paths are tested, schema updates are covered, and regressions are explicitly called out.
---

> 生产部署统一入口：`生产部署指南.md`。

# Test Gate

Use this skill before finalizing non-trivial code changes.

## Execute Workflow

1. Read `references/change-review-checklist.md`.
2. Identify affected backend, frontend, and infra surfaces.
3. Run smallest meaningful test set first, then wider regression tests.
4. Confirm schema/contract changes include matching test updates.
5. Report residual risks and uncovered areas explicitly.

## Guardrails

- Do not claim verification without commands and outcomes.
- Distinguish environment failures from code regressions.
- Require critical path tests for auth, sessions, chat, and scoring changes.

## References

- Review checklist: `references/change-review-checklist.md`
- API release checks: `references/api-release-checklist.md`
