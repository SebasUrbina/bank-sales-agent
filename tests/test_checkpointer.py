from langgraph.checkpoint.memory import InMemorySaver

from bank_sales_agent.infrastructure.agent.checkpointer import build_checkpointer
from bank_sales_agent.infrastructure.config.settings import (
    AppEnvironment,
    MongoSettings,
)


def test_local_environment_uses_in_memory_checkpointer() -> None:
    checkpointer = build_checkpointer(AppEnvironment.LOCAL, MongoSettings())

    assert isinstance(checkpointer, InMemorySaver)
