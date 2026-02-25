---
name: extend-scoring
description: Extend or refactor rule-based scoring for luyun-sizheng sessions. Use when updating scoring dimensions, weighting, scoring_details output, or score-related tests while preserving traceability and backward compatibility.
---

> 基础设施与部署请参考：`src/infra/README.md`。

# Extend Scoring

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
