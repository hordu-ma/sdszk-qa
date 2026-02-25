---
name: random-case-mode
description: Implement or maintain random case generation mode in luyun-sizheng. Use when modifying LLM-generated case payloads, random session creation flow, prompt contracts, or compatibility checks between available_tests and recommended_tests.
---

> 生产部署统一入口：`生产部署指南.md`。

# Random Case Mode

Use this skill when working on random-case generation and session wiring.

## Execute Workflow

1. Read `references/random-case-flow.md`.
2. Update generation logic in `src/apps/api/services/case_generation.py`.
3. Ensure payload fields satisfy `Case` model requirements.
4. Validate `recommended_tests` are subset of `available_tests[].type`.
5. Confirm session creation route handles malformed payload safely.
6. Add or update tests for generation validation and create-session behavior.

## Guardrails

- Keep generated case content stable per session after persistence.
- Reject or normalize malformed LLM output before DB write.
- Keep scoring compatibility with generated case fields.

## References

- Generation contract: `references/random-case-flow.md`
- Field contract checklist: `references/payload-contract.md`
