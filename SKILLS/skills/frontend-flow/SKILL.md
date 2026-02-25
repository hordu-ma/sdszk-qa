---
name: frontend-flow
description: Modify or extend clinic-sim Vue frontend page flows. Use when changing login, case list, chat, or session history navigation, including router guards, state handling, and API integration behavior.
---

> 生产部署统一入口：`生产部署指南.md`。

# Frontend Flow

Use this skill for Vue page-flow changes and route behavior updates.

## Execute Workflow

1. Read `references/flow-map.md`.
2. Locate impacted views and router entries.
3. Update page logic in `src/apps/web/src/views`.
4. Keep auth checks consistent in `src/apps/web/src/router/index.ts` and user store.
5. Route all non-stream API calls through `src/apps/web/src/api/request.ts` wrappers.
6. Validate mobile view behavior and main user journey.

## Guardrails

- Keep navigation behavior deterministic for unauthenticated users.
- Avoid duplicated request/error handling paths across components.
- Preserve existing visual language unless task explicitly requests redesign.

## References

- Page flow map: `references/flow-map.md`
