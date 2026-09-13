# Arquitectura

```text
Apps Script / REST
       |
       v
infrastructure/api  -- autentica identidad, crea AgentContext
       |
       v
infrastructure/agent -- create_agent + middleware harness + tools
       |                             |
       v                             v
domain policies             ScopedSqlWarehouseClient
                                      |
                                      v
                            SQL parametrizado y fijo
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
   El catálogo y la política de visibilidad viven en aplicación; `ToolRegistry` solo los adapta a
   objetos `BaseTool` de LangChain.
4. **Los resultados estructurados son neutrales al canal.** Cada tool usa
   `response_format="content_and_artifact"`: el contenido alimenta al modelo y el artifact queda en
   el `ToolMessage`. REST lo serializa como JSON y el renderer de Google Chat lo convierte a
   objetos `GoogleChatCardV2`. Las dataclasses usan `build()` únicamente en el borde para producir
   el JSON `cardsV2` esperado por Google.
5. **El lifespan posee los recursos.** En producción crea una conexión/pool Databricks al iniciar y
   lo cierra al apagar. También crea y cierra el checkpointer correspondiente al ambiente. Nada
   abre conexiones por invocación ni usa singletons implícitos.
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
10. **El cliente SQL llega por runtime context.** El runner crea un `ScopedSqlWarehouseClient` por
    invocación y lo entrega en `AgentContext`. El wrapper sobrescribe email y rol con la identidad
    autenticada; esos campos nunca son argumentos de la tool.

## Cómo agregar una capacidad

Por ejemplo, `next_best_action`:

1. Agregar sus modelos/reglas puras en `domain/`.
2. Crear un módulo de tool con SQL fijo, mapper y `@tool`.
3. Consultar exclusivamente mediante `runtime.context.sql_client`.
4. Mantener email, rol, SQL, tablas y credenciales fuera de los argumentos del modelo.
5. Producir contenido JSON y, si corresponde, un artifact neutral condicionado por `render`.
6. Agregar su `AgentToolSpec` al catálogo y registrarla en `build_tool_registry`; el registry falla
   al iniciar si el catálogo y las implementaciones divergen.
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
