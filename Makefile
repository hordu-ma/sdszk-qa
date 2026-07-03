PYTHON ?= uv run --frozen --extra dev
WEB_DIR := src/apps/web
COMPOSE_DEV := src/infra/compose/dev.yml

.PHONY: setup setup-backend setup-frontend lint typecheck test test-unit test-integration test-api test-cov web-build harness-bootstrap harness-backend harness-quick harness-full dev-up dev-down doctor

setup: setup-backend setup-frontend

harness-bootstrap: doctor setup

harness-backend: lint typecheck test-unit

harness-quick: harness-backend web-build

harness-full: lint typecheck test web-build

setup-backend:
	uv sync --frozen --extra dev

setup-frontend:
	npm --prefix $(WEB_DIR) install

lint:
	$(PYTHON) ruff check .

typecheck:
	$(PYTHON) basedpyright

test:
	$(PYTHON) pytest

test-unit:
	$(PYTHON) pytest -m "not integration"

test-integration:
	$(PYTHON) pytest -m integration

test-api:
	$(PYTHON) pytest tests/test_config.py tests/test_rate_limit.py tests/test_prompt_builder.py

test-cov:
	$(PYTHON) pytest --cov=src/apps/api --cov-report=term-missing

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
