# ADR 0003: Cards de Google Chat en el `structuredContent` de MCP

- Estado: aceptado
- Fecha: 2026-11-11
- Reemplaza el contrato `context`/`artifact` descrito en ADR 0002.

## Contexto

El agente se integra con Google Chat mediante un middleware que intercepta las tool calls y, si el
resultado trae `cardsV2`, las publica con el cliente de Google. Con el contrato anterior, el MCP
devolvía un artefacto neutral (`kind`/`data`) y el agente necesitaba un renderer por tipo de
artefacto, lo que acoplaba el agente a los modelos de dominio de cada tool.

## Decisión

1. Cada tool MCP devuelve un `ToolResult` de FastMCP:
   - `content`: un `TextContent` con el JSON que lee el modelo.
   - `structuredContent`: `{"cardsV2": [...]}` con el formato de Google Chat; lista vacía cuando
     `render=false`.
2. Las tools declaran `outputSchema` generado desde `CardsV2Output` (Pydantic, alias camelCase) y
   `ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)`. El
   `ClientSession` de MCP valida el `structuredContent` contra ese schema.
3. El adaptador LangChain entrega `content` al modelo y guarda `structuredContent` como
   `ToolMessage.artifact`.
4. `GoogleChatCardsMiddleware` (`awrap_tool_call`) detecta `cardsV2` de forma genérica y las publica
   en el hilo apenas termina la tool. Usa autenticación de app, porque Google Chat no acepta cards
   con OAuth de usuario. El `requestId` se deriva de `request_id` y `tool_call_id`.
5. El texto final se publica después, con el OAuth del usuario, como antes.

## Consecuencias

- El agente no conoce modelos de dominio para presentar resultados; cualquier tool MCP que emita
  `cardsV2` se publica sin cambios en el agente.
- El contrato de presentación pasa a ser el de Google Chat. Si se agrega otro canal, el MCP debe
  emitir otra clave en `structuredContent` o volver a un formato neutral.
- El usuario puede ver la card antes que el texto. Las instrucciones piden al modelo complementar
  la card sin repetir todos sus datos, y el middleware agrega una nota al `ToolMessage` indicando si
  la card se mostró o falló.
- Si falla la publicación de una card, la tool no falla: se registra el error y el modelo recibe
  una nota para incluir los datos en texto.
- `bank-sales-contracts` pasa a 0.3.0 y elimina `artifacts.py` y `responses.py`.
