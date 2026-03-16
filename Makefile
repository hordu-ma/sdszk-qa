PYTHON ?= uv run
WEB_DIR := src/apps/web
COMPOSE_DEV := src/infra/compose/dev.yml

.PHONY: setup setup-backend setup-frontend lint typecheck test test-api test-cov web-build dev-up dev-down doctor

setup: setup-backend setup-frontend

setup-backend:
	uv sync --extra dev

setup-frontend:
	npm --prefix $(WEB_DIR) install

lint:
	uv run ruff check .

typecheck:
	uv run basedpyright

test:
	uv run pytest

test-api:
	uv run pytest tests/test_config.py tests/test_rate_limit.py tests/test_prompt_builder.py tests/test_integration.py

test-cov:
	uv run pytest --cov=src/apps/api --cov-report=term-missing

web-build:
	npm --prefix $(WEB_DIR) run build

dev-up:
	docker compose -f $(COMPOSE_DEV) up -d

dev-down:
	docker compose -f $(COMPOSE_DEV) down

doctor:
	uv --version
	npm --version
	docker compose version
