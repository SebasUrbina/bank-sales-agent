from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

from bank_sales_agent.infrastructure.config.settings import AppEnvironment, MongoSettings


def build_checkpointer(
    environment: AppEnvironment,
    settings: MongoSettings,
) -> BaseCheckpointSaver[Any]:
    """Selecciona memoria local o persistencia MongoDB según el ambiente."""
    if environment is AppEnvironment.LOCAL:
        return InMemorySaver()

    assert settings.uri is not None
    client: MongoClient[Any] = MongoClient(settings.uri.get_secret_value())
    return MongoDBSaver(
        client=client,
        db_name=settings.database_for(environment),
        checkpoint_collection_name=settings.checkpoint_collection,
        writes_collection_name=settings.writes_collection,
    )


def close_checkpointer(checkpointer: BaseCheckpointSaver[Any]) -> None:
    if isinstance(checkpointer, MongoDBSaver):
        checkpointer.close()
