"""Entrypoint ASGI de la aplicacion."""

from app.infrastructure.api.app import create_app

app = create_app()
