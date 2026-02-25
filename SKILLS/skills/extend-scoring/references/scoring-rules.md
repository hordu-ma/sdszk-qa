# Scoring Rules

> 生产部署统一入口：`生产部署指南.md`。

Current scoring engine is rule-based and stored in:

- `src/apps/api/services/scoring.py`

When adding dimensions:

1. Define formula and weight.
2. Add dimension output key.
3. Add detail fields to explain score source.
4. Update tests with representative messages and test requests.

Always keep output reproducible for identical inputs.
