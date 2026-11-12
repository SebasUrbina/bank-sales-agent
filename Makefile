.PHONY: dev test lint format check pre-commit-install

dev:
	uv run uvicorn app.main:app --reload

test:
	uv run pytest
	uv run pytest -c mcp-server/pyproject.toml mcp-server/tests

lint:
	uv run ruff check app tests mcp-server packages
	uv run ruff format --check app tests mcp-server packages
	uv run mypy app mcp-server/bank_sales_mcp packages/bank-sales-contracts/bank_sales_contracts

format:
	uv run ruff check --fix app tests mcp-server packages
	uv run ruff format app tests mcp-server packages

check: lint test

pre-commit-install:
	uv run pre-commit install
