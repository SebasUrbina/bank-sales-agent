"""Contrato JSON de tools MCP: contexto para el modelo y artefacto opcional."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter

from bank_sales_contracts.artifacts import (
    AgentArtifact,
    Customer360Artifact,
    PrioritizedCustomersArtifact,
)


class ArtifactPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["customer_360", "prioritized_customers"]
    data: dict[str, object]


class ToolResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: str
    artifact: ArtifactPayload | None = None

    @classmethod
    def from_result(cls, context: str, artifact: AgentArtifact | None) -> "ToolResponse":
        if artifact is None:
            return cls(context=context)
        kind: Literal["customer_360", "prioritized_customers"] = (
            "customer_360" if isinstance(artifact, Customer360Artifact) else "prioritized_customers"
        )
        data = TypeAdapter(type(artifact)).dump_python(artifact, mode="json")
        return cls(context=context, artifact=ArtifactPayload(kind=kind, data=data))

    def to_result(self) -> tuple[str, AgentArtifact | None]:
        if self.artifact is None:
            return self.context, None
        if self.artifact.kind == "customer_360":
            artifact: AgentArtifact = TypeAdapter(Customer360Artifact).validate_python(
                self.artifact.data
            )
        else:
            artifact = TypeAdapter(PrioritizedCustomersArtifact).validate_python(self.artifact.data)
        return self.context, artifact
