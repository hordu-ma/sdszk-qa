---
description: "Use when changing Vue 3, Vite, Vant, or frontend state and API flow under src/apps/web. Covers views, api clients, routing, and UI consistency."
applyTo: "src/apps/web/src/**/*.vue, src/apps/web/src/**/*.ts, src/apps/web/src/**/*.tsx, src/apps/web/src/**/*.js"
---
# Frontend Guidelines

- Keep page-level components in `src/views` and preserve the existing Vue 3 + Vite structure.
- Use shared API modules under `src/api` instead of embedding request logic in views.
- Match existing routing, store, and Vant usage patterns for current Q&A pages; for teaching-workbench features (plan stage 1+), prefer desktop-first layouts over mobile-only chat patterns.
- Prefer explicit loading, empty, and error states for user-facing flows.
- For behavior-affecting frontend changes, validate with at least a production build.
- Product Skills task entry, Memory management, and non-scoring diagnosis UX follow the development plan; do not build score/rank UIs.
