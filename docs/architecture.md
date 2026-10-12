# Arquitectura

```text
Apps Script / REST
       |
       v
infrastructure/api -- resuelve identidad desde directorio
       |
       v
infrastructure/agent -- create_agent + middleware + adaptadores MCP
       |
       v
FastMCP Client -- Streamable HTTP autenticado
       |
       v
mcp-server/ -- FastMCP externo: tools/list y tools/call perfilados por rol
       |
       v
ScopedSqlWarehouseClient -- SQL parametrizado con alcance por filas
```

## Flujo asíncrono de Google Chat

```text
interaction event
      |
      v
FastAPI -- BackgroundTasks.add_task(...) -- respuesta inmediata 202 Accepted
                    |
                    v
          Background worker API
                   |
                   v
              AgentRunner
                   |
                   v
     GoogleChatPublisher + renderer
                   |
                   v
          Google Chat messages.create
```

`BackgroundTasks` es deliberadamente una implementación simple y best effort: una tarea puede
perderse si el proceso termina después del acuse. El port `AgentRunner` permite introducir
posteriormente una cola durable sin modificar el agente.

## Decisiones clave

1. **El email es la llave corporativa.** `user_email` se resuelve en el directorio para obtener su
   rol y se conserva como llave del `Principal`; no existe un `employee_id` alternativo.
2. **No existe una tool de SQL genérico.** Cada capacidad tiene un query estable, revisable y
   parametrizado junto a su tool. Una query muy extensa puede moverse a un archivo `.sql` vecino;
   los joins reutilizados o costosos deben evolucionar a vistas Gold de Databricks.
3. **Ocultar una tool no es autorización.** El middleware puede filtrar tools por experiencia de
   usuario, pero la tool valida capability y el SQL siempre aplica autorización por filas.
   El catálogo y la política de visibilidad viven exclusivamente en `mcp-server/`. El agente
   adapta las tools anunciadas por `tools/list` a objetos `BaseTool` de LangChain.
4. **Los resultados estructurados son neutrales al canal.** Cada tool usa
   `response_format="content_and_artifact"`: el contenido alimenta al modelo y el artifact queda en
   el `ToolMessage`. El servidor MCP serializa `context` y `artifact` por separado; el adaptador
   reconstruye el artefacto y el renderer de Google Chat lo convierte a
   objetos `GoogleChatCardV2`. Las dataclasses usan `build()` únicamente en el borde para producir
   el JSON `cardsV2` esperado por Google.
5. **El lifespan posee los recursos.** En producción crea una conexión/pool Databricks al iniciar y
   lo cierra al apagar. También crea y cierra el checkpointer correspondiente al ambiente. Nada
   abre conexiones SQL por invocación ni usa singletons implícitos. Cada invocación sí abre una
   sesión MCP aislada y la cierra al terminar; en HTTP el SQL pertenece al servidor de tools.
6. **LangChain recibe el hilo canónico sin transformaciones.** El `thread_name` normalizado por Apps
   Script se utiliza como `thread_id` y también para publicar en el hilo original de Google Chat.
7. **Google Chat recibe una sola respuesta final.** El endpoint acusa recibo antes de 30 segundos;
   el background task espera `ainvoke`, reúne texto y artifacts, renderiza una sola respuesta y la
   publica con `requestId` idempotente en el `thread.name` original.
8. **Los errores de tools son observaciones seguras.** `DomainError` define un `code` y si el modelo
   puede reintentar. El middleware devuelve un `ToolMessage(status="error")` en JSON. Los errores
   inesperados se registran con detalle, pero el modelo solo recibe un mensaje genérico.
9. **Los checkpoints están aislados por ambiente.** `local` usa `InMemorySaver`; `dsr`, `qa` y `prd`
   usan `MongoDBSaver` y bases distintas con el patrón `{MONGODB_DATABASE}_{APP_ENV}`.
10. **El SQL pertenece al servidor MCP.** El middleware crea un `ScopedSqlWarehouseClient` por
    llamada y lo entrega al ejecutor de datos en `ToolContext`. El wrapper
    sobrescribe email y rol con la identidad autenticada; esos campos nunca son argumentos de la
    tool. En HTTP el servidor valida un token firmado y resuelve el email en su propio directorio.

## Cómo agregar una capacidad

Por ejemplo, `next_best_action`:

1. Agregar modelos/reglas compartidos en `packages/bank-sales-contracts/`.
2. Crear una operación en `mcp-server/bank_sales_mcp/tools/` con SQL fijo y mapper.
3. Consultar exclusivamente mediante `ToolContext.sql_client`.
4. Mantener email, rol, SQL, tablas y credenciales fuera de los argumentos del modelo.
5. Producir contenido JSON y, si corresponde, un artifact neutral condicionado por `render`.
6. Agregar su `AgentToolSpec` al catálogo MCP, capability a `ROLE_CAPABILITIES` del servidor y
   endpoint a `mcp-server/bank_sales_mcp/server.py:build_mcp_server`. El agente adapta dinámicamente
   el schema y descripción de `tools/list`; no necesita registro ni permisos locales.
7. Probar política, selección por rol, alcance, query, artifact y contrato del renderer.

## Evolución sugerida

- Mantener `vista 360` y `priorización` como productos de datos versionados en la capa Gold. Si un
  join es reutilizado o costoso, moverlo de la aplicación a una vista/materialized view.
- Reemplazar headers de desarrollo por validación del token OIDC de Google y un
  `EmployeeDirectoryPort` que traduzca email/subject a `Principal` confiable.
- Usar tablas de vigencia (`valid_from`, `valid_to`) para asignaciones y jerarquía; definir si los
  líderes ven solo reportes directos o el árbol completo.
- Definir TTL, cifrado y eliminación para los checkpoints persistentes; el `thread_id` de entrada se
  usa directamente como llave de estado.
- Auditar: principal, capacidad, filtros normalizados, tablas lógicas, filas devueltas, latencia y
  decisión de acceso. No registrar prompts/resultados con PII sin redacción y política de retención.

## Roles, transporte y artefactos MCP

La matriz completa y la configuración de ambos procesos se documentan en [README](../README.md).
`investments` y `leader` se aceptan como alias de lectura; el dominio emite `investments_advisor`
y `manager`. Centro de servicio sólo accede a vista 360 de clientes asignados.

El servidor usa un `ContextVar` por ejecución y restaura su valor al terminar, para evitar cruzar
identidades entre llamadas concurrentes. El agente nunca envía el rol como argumento de una tool.
La identidad HTTP viaja como un bearer token firmado cuyo subject es el email; el rol se consulta
nuevamente en el directorio del servidor. La validación de identidad del ingreso REST sigue siendo
un requisito independiente para producción.

El contrato `ToolResponse` transporta contexto y un artefacto neutral opcional. La respuesta sólo
incluye artefacto cuando `render=true`. El adaptador valida el JSON y reconstruye la dataclass,
preservando `Decimal` y tuplas. El modelo recibe el contenido y el publisher transforma únicamente
los artefactos del turno actual a `cardsV2`, con un máximo de tres tarjetas.

## Deployments independientes

- `src/bank_sales_agent/`: API, LangChain, cliente HTTP MCP y publicación Google Chat.
- `mcp-server/`: servicio FastMCP con pyproject, lockfile, Dockerfile y entorno propios; SQL y
  autorización viven aquí. No importa el agente ni LangChain.
- `packages/bank-sales-contracts/`: paquete pequeño con identidad, modelos y contrato de resultados; sin permisos.

El paquete del servidor sólo se instala en el grupo de desarrollo del agente para las pruebas HTTP.
La imagen del servidor copia su servicio y los contratos; no copia `src/`. El agente siempre se
conecta al endpoint externo configurado en `MCP__URL`; se elimina el modo MCP en memoria.

La API no compara el catálogo remoto con expectativas por rol. El MCP es la única autoridad sobre
permisos; un rol informativo desactualizado en la API no modifica las tools disponibles. El runner
reutiliza grafo, modelo y checkpointer; el middleware descubre y despacha las tools de cada sesión.
El paquete compartido sólo necesita cambiar cuando cambia el contrato, no cuando cambian permisos.

## Grafo compartido y capacidades por invocación

El composition root construye un `LangChainAgentRunner` y un único grafo. El runner gestiona la
sesión MCP por ejecución; `DynamicCapabilitiesMiddleware.abefore_agent` descubre tools y skills
una vez y las guarda en `AgentContext.capabilities`. `awrap_model_call` expone sus schemas y añade
el catálogo de skills al prompt. `awrap_tool_call` resuelve la instancia de tool dinámica, incluso
cuando no estaba registrada al crear el grafo. El middleware de errores rodea ese despacho.

No se consulta `tools/list` en cada llamada al modelo ni se almacena registry, cliente o recursos
abiertos en el estado persistente. Dos ejecuciones comparten grafo pero usan objetos de contexto
separados. Cambios de tools y skills se reflejan en la siguiente ejecución. MCP sigue autorizando
cada llamada, por lo que una revocación puede bloquear incluso una tool ya descubierta.

`application/skills.py` define el port independiente de LangChain. `infrastructure/skills` descubre
frontmatter YAML de `SKILL.md` y proporciona carga de instrucciones y recursos de texto bajo demanda.
Las rutas están limitadas a cada carpeta y los archivos tienen tamaño acotado. Las skills no agregan
permisos ni ejecutan scripts; sus nombres y descripciones son el único contenido precargado al modelo.
