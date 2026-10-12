.PHONY: dev test lint format check pre-commit-install

dev:
	uv run uvicorn bank_sales_agent.main:app --reload

test:
	uv run pytest
	uv run pytest -c mcp-server/pyproject.toml mcp-server/tests

lint:
	uv run ruff check src tests mcp-server packages
	uv run ruff format --check src tests mcp-server packages
	uv run mypy src mcp-server/bank_sales_mcp packages/bank-sales-contracts/bank_sales_contracts

format:
	uv run ruff check --fix src tests mcp-server packages
	uv run ruff format src tests mcp-server packages

check: lint test

pre-commit-install:
	uv run pre-commit install
