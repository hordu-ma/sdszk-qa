# Random Case Flow

> 生产部署统一入口：`生产部署指南.md`。

Key files:

- Generation service: `src/apps/api/services/case_generation.py`
- Session creation route: `src/apps/api/routes/sessions.py`
- Model target: `src/apps/api/models/cases.py`

Flow:

1. Select disease/topic.
2. Request JSON-only payload from LLM.
3. Parse and normalize payload.
4. Validate required fields.
5. Persist `Case` with `source=random`.
6. Create `Session` bound to that case.
