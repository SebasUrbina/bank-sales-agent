.PHONY: dev test lint

dev:
	uv run uvicorn bank_sales_agent.main:app --reload

test:
	uv run pytest

lint:
	uv run ruff check src tests
	uv run mypy src
