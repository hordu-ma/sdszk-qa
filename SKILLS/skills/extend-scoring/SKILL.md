---
name: extend-scoring
description: Extend or refactor rule-based scoring for luyun-sizheng sessions. Use when updating scoring dimensions, weighting, scoring_details output, or score-related tests while preserving traceability and backward compatibility.
status: placeholder
---

> **⚠️ 预留 Skill**：当前项目不包含评分模块（见 `README.md`），`services/scoring.py` 和 `schemas/scores.py` 尚未实现。本 skill 为未来扩展评分功能时的工作流预留，暂不可执行。

> 基础设施与部署请参考：`src/infra/README.md`。

# Extend Scoring（预留）

Apply this workflow for scoring logic changes.

## Execute Workflow

1. Read `references/scoring-rules.md`.
2. Change scoring behavior in `src/apps/api/services/scoring.py`.
3. Keep `scoring_details` explanatory and versioned.
4. Align response schema types in `src/apps/api/schemas/scores.py` if fields change.
5. Verify session submit and score retrieval routes still serialize correctly.
6. Update tests for key branches and regression cases.

## Guardrails

- Preserve deterministic output for same input.
- Keep score dimensions and total score consistent.
- Track rule version updates whenever semantics change.

## References

- Rule design and validation: `references/scoring-rules.md`
- Touchpoints in routes/schemas: `references/scoring-touchpoints.md`
