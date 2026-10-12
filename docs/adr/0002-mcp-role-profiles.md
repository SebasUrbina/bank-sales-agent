# ADR 0002: Tools MCP perfiladas por rol

- Estado: aceptado
- Fecha: 2026-10-11
- Complementa ADR 0001: las consultas verticales se ejecutan detrás de MCP.

## Decisión

El agente consume exclusivamente adaptadores que llaman al cliente FastMCP. El servidor mantiene
las consultas fijas y aplica su propia política de capabilities tanto en `tools/list` como en
`tools/call`. El chequeo de la tool y el filtro SQL por filas siguen vigentes.

El servidor vive en `mcp-server/` y tiene deployment, dependencias y configuración propios.
El agente consume exclusivamente Streamable HTTP. La API firma un bearer
HS256 de corta duración con email como subject; el servidor verifica firma, issuer, audience y
expiración y vuelve a resolver el rol desde su directorio. El rol nunca viaja como argumento del LLM.
La configuración requiere un secreto administrado compartido; la validación de identidad de entrada
REST debe implementarse antes de exponer la API en producción.

Los siete perfiles son comercial, inversiones asesor, inversiones no asesor, integral, centro de
servicio, gerente y admin. Centro de servicio recibe sólo consulta 360 de clientes asignados. Los
otros ejecutivos consultan su cartera; gerente consulta su equipo y admin el alcance global. Las
tools actuales consultan información, por lo que ambos perfiles de inversiones comparten permisos.
Una futura capacidad de asesoría necesita autorización específica; un prompt no reemplaza ese control.

El contrato MCP serializa `context` y `artifact` por separado. El artefacto permanece neutral al
canal y se reconstruye desde un discriminador `kind`, conservando tipos de dominio. El contenido
alimenta el modelo y el artefacto alimenta el renderer de Google Chat, que produce `cardsV2`.
El publicador usa sólo el turno actual y limita las tarjetas a tres.

## Consecuencias

- El agente descubre las tools autorizadas por `tools/list`; no tiene catálogo ni permisos locales.
- Las identidades concurrentes se aíslan con contexto por llamada y sesiones independientes.
- En HTTP las credenciales SQL y la conexión Databricks pertenecen al servidor MCP.
- Cada capacidad registra un endpoint y permisos en el MCP; el adaptador LangChain utiliza
  dinámicamente su JSON Schema y descripción.
- Se conserva el directorio mock; `create_server` permite inyectar la implementación corporativa.
- Se fija FastMCP a la serie 2.13.3: la serie 2.14 produjo bloqueos de cierre en las pruebas de
  múltiples sesiones/event loops del entorno actual. Actualizar requiere repetir esas pruebas.

## Separación del servicio

El servidor no depende del paquete del agente ni de LangChain. Su Dockerfile sólo copia `mcp-server/`
y `packages/bank-sales-contracts/`, y usa un lockfile propio. Las consultas y credenciales Databricks
pertenecen al servidor. `AgentContext` contiene únicamente principal, request_id y cliente MCP.
La identidad y payloads están en el paquete compartido versionado `bank-sales-contracts`.
Las capabilities, permisos y catálogo pertenecen exclusivamente a `bank_sales_mcp`.
Se elimina el transporte en memoria del agente; las integraciones se prueban por HTTP.

El rol conocido por el agente es informativo; el servidor consulta la asignación vigente en su propio
directorio. Cambios de autorización o incorporación de tools compatibles se despliegan sólo en MCP.
Se elimina la comparación local de catálogo y el middleware de selección por rol del agente.


El grafo se construye una vez por proceso. El descubrimiento por invocación y la exposición/ejecución
se realizan mediante middleware, conservando el cliente en el contexto temporal. Las skills locales
siguen el mismo alcance de invocación y se cargan progresivamente; no afectan a la autorización MCP.
