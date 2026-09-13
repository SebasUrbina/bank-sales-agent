from bank_sales_agent.application.dto import OutboundMessage, ProcessAgentRequestCommand
from bank_sales_agent.application.ports import AgentRunner, ChannelPublisher


class ProcessAgentRequest:
    """Ejecuta el agente y publica una unica respuesta completa al canal."""

    def __init__(
        self,
        runner: AgentRunner,
        publisher: ChannelPublisher,
    ) -> None:
        self._runner = runner
        self._publisher = publisher

    async def execute(self, command: ProcessAgentRequestCommand) -> None:
        result = await self._runner.run(command.invocation)
        await self._publisher.publish(
            destination=command.destination,
            message=OutboundMessage(result.text, result.artifacts),
            idempotency_key=command.invocation.request_id,
        )
