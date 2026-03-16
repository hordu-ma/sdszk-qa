---
description: "Use when adding or updating pytest coverage, integration tests, service-level tests, or regression tests for backend behavior."
applyTo: "tests/**/*.py"
---
# Testing Guidelines

- Prefer focused service tests plus integration coverage for request flows that cross route, service, and persistence layers.
- Cover both the success path and the most relevant failure path for each changed behavior.
- Keep test naming aligned with pytest discovery: `test_*.py`, `Test*`, and `test_*`.
- Mock external LLM or network-bound dependencies; CI and routine local runs should not call real model endpoints.
- When a bug fix changes behavior, add or update a regression test close to that behavior.
