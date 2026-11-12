from langgraph.checkpoint.memory import InMemorySaver

from app.infrastructure.agent.checkpointer import build_checkpointer
from app.settings import (
    AppEnvironment,
    MongoSettings,
)


def test_local_environment_uses_in_memory_checkpointer() -> None:
    checkpointer = build_checkpointer(AppEnvironment.LOCAL, MongoSettings())

    assert isinstance(checkpointer, InMemorySaver)
