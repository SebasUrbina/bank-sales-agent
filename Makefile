.PHONY: dev test lint format check pre-commit-install

dev:
	uv run uvicorn bank_sales_agent.main:app --reload

test:
	uv run pytest

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run mypy src

format:
	uv run ruff check --fix src tests
	uv run ruff format src tests

check: lint test

pre-commit-install:
	uv run pre-commit install
