"""Entrypoint ASGI de la aplicacion."""

from bank_sales_agent.infrastructure.api.app import create_app

app = create_app()
