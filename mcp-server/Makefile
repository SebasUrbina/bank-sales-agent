.PHONY: dev test lint check

dev:
	uv run bank-sales-mcp

test:
	uv run pytest

lint:
	uv run ruff check bank_sales_mcp tests ../packages/bank-sales-contracts
	uv run ruff format --check bank_sales_mcp tests ../packages/bank-sales-contracts
	uv run mypy bank_sales_mcp ../packages/bank-sales-contracts/bank_sales_contracts

check: lint test
