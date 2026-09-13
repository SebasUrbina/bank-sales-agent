# Arquitectura

```text
Apps Script / REST
       |
       v
infrastructure/api  -- autentica identidad, crea AgentContext
       |
       v
infrastructure/agent -- create_agent + middleware harness + tools
       |
       v
application/use_cases -- autoriza capacidad y crea DataAccessContext
       |
       v
application/ports <--- infrastructure/databricks
       |                         |
       v                         v
domain                   SQL parametrizado y fijo
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
   parametrizado. Los joins viven en `query_catalog.py` o, cuando crezcan, en vistas Gold de
   Databricks.
3. **Ocultar una tool no es autorización.** El middleware puede filtrar tools por experiencia de
   usuario, pero el caso de uso y el repositorio siempre aplican autorización.
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

## Cómo agregar una capacidad

Por ejemplo, `next_best_action`:

1. Agregar sus modelos/reglas puras en `domain/`.
2. Agregar el método necesario a un port de `application/ports.py` (o crear uno cohesivo).
3. Crear un caso de uso que reciba `Principal`, construya `DataAccessContext` y llame al port.
4. Implementar el port en Databricks con SQL parametrizado; nunca aceptar SQL desde el modelo.
5. Crear una tool delgada que traduzca input/output y produzca un artifact neutral.
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
- Añadir checkpointer persistente si habrá conversaciones multi-turno; el `thread_id` de entrada se
  usa directamente como llave de estado.
- Auditar: principal, capacidad, filtros normalizados, tablas lógicas, filas devueltas, latencia y
  decisión de acceso. No registrar prompts/resultados con PII sin redacción y política de retención.
