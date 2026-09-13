.PHONY: dev test lint

dev:
	uv run uvicorn bank_sales_agent.infrastructure.api.app:create_app --factory --reload

test:
	uv run pytest

lint:
	uv run ruff check src tests
	uv run mypy src

