# Bank Sales Agent

Mockup ejecutable de un agente para ejecutivos bancarios, construido con FastAPI, LangChain
`create_agent` y Clean Architecture. Incluye Vista 360, listado priorizado, roles, alcance por
cartera, jerarquía de líderes, cards de Google Chat y un adaptador Databricks.

Apps Script normaliza los eventos de Google Chat y llama a FastAPI, que responde inmediatamente.
El agente se ejecuta mediante `BackgroundTasks` y al terminar publica una única respuesta con texto
y cards. El modo local usa clientes mock; `GOOGLE_CHAT__ENABLED=true` activa ADC/Workload Identity.

## Estructura

```text
src/bank_sales_agent/
├── domain/                 # entidades, roles, capacidades y reglas puras
├── application/
│   ├── agent/              # instrucciones, catálogo y política sin LangChain
│   ├── ports.py            # contratos requeridos por el negocio
│   └── use_cases/          # sólo orquestación de negocio real, no wrappers de queries
└── infrastructure/
    ├── agent/              # runtime, registry y slices tool-query
    ├── api/                # factory, rutas, schemas y composition root en lifespan
    ├── config/             # settings y secretos tipados
    ├── databricks/         # cliente base y wrapper request-scoped
    ├── google_chat/        # renderer de artifacts a cardsV2
    └── mock/               # datos locales reemplazables
```

La explicación general está en [docs/architecture.md](docs/architecture.md). La discusión y decisión
sobre la relación tool-query quedó registrada en
[ADR 0001](docs/adr/0001-tool-query-runtime-context.md). Las prácticas recomendadas y su orden de
adopción están en [Engineering Practices Roadmap](docs/engineering-practices-roadmap.md).

## Ejecutar

```bash
cp .env.example .env
uv sync --group dev
uv run uvicorn bank_sales_agent.main:app --reload
```

## Desarrollo

### Herramientas actuales

- `uv`: dependencias reproducibles y lockfile.
- Ruff: lint, imports, modernización y formato automático.
- MyPy strict: validación estática de tipos.
- Pytest y `pytest-asyncio`: pruebas unitarias y asíncronas.
- `pytest-cov`: branch coverage con un mínimo inicial de 73%.
- `pre-commit`: Ruff lint con autofix y formatter antes de cada commit.
- `pydantic-settings`: configuración tipada y secretos redactados.

```bash
# Instala los hooks locales una vez
make pre-commit-install

# Corrige lint y formato
make format

# Ejecuta lint, format check, MyPy, tests y coverage
make check
```

Pytest mide branch coverage sobre `bank_sales_agent` y exige un mínimo inicial de 73%. Pre-commit
ejecuta solamente los checks rápidos y autocorregibles de Ruff; la validación completa queda en
`make check` y debe ejecutarse también en CI.

La instancia mock usa un modelo real y requiere `LLM_GATEWAY__API_KEY`. Una prueba REST:

```bash
curl -X POST http://127.0.0.1:8000/v1/agent/invoke \
  -H 'content-type: application/json' \
  -d '{
    "message":"Dame mi lista de clientes prioritarios",
    "space_name":"spaces/AAAA",
    "thread_name":"spaces/AAAA/threads/BBBB",
    "user_email":"ejecutivo@bank.test",
    "user_oauth_token":"oauth-token-del-usuario",
    "attachments":[]
  }'
```

La API responde `202 Accepted`; el procesamiento continúa en `BackgroundTasks` y el resultado se
publica en `space_name/thread_name`. El token OAuth sólo se usa para esa publicación y no se agrega
al estado ni a los mensajes de LangChain.

Cada tool de datos expone `render: bool = false`. El resultado estructurado siempre queda disponible
para el análisis del modelo; sólo se genera una card cuando el agente decide invocarla con
`render=true`. El publisher reúne esas cards y las envía junto con la respuesta final.

## Ambientes y memoria conversacional

`APP_ENV` acepta exclusivamente `local`, `dsr`, `qa` o `prd`. En `local`, LangGraph usa
`InMemorySaver`; los demás ambientes exigen `MONGODB__URI` y usan `MongoDBSaver`. Los checkpoints se
separan en bases `{MONGODB__DATABASE}_{APP_ENV}` para evitar cruces entre ambientes, por ejemplo
`bank_sales_agent_qa`. El `thread_name` de entrada sigue siendo la llave `thread_id` de LangGraph.

La configuración usa secciones anidadas de `pydantic-settings`. Sólo `Settings` lee el environment;
las secciones `api`, `mongodb`, `llm_gateway`, `databricks` y `google_chat` son `BaseModel`. El
cliente LLM se conecta a un APIM OpenAI-compatible y deriva su endpoint como
`{LLM_GATEWAY__BASE_URL}/{model_name}/v1`.

## Importante antes de producción

- El mock resuelve `user_email` contra un directorio local. Google Chat debe autenticarse validando
  OIDC; el email del payload solo es confiable después de validar al emisor y debe resolverse contra
  el directorio interno.
- `infrastructure/api/lifespan.py` es el composition root. Construye un cliente SQL mock en local o
  `DatabricksSqlWarehouseClient` cuando `DATABRICKS__ENABLED=true`. El runner entrega un cliente
  request-scoped a las tools mediante `AgentContext`.
- `pydantic-settings` carga configuración desde variables de entorno y `.env` sólo para desarrollo.
  Los secretos se tipan como `SecretStr`; en producción deben inyectarse desde el secret manager de
  la plataforma y nunca almacenarse en el repositorio.
- Las consultas de ejemplo usan nombres de tablas ficticios y deben adaptarse al catálogo real.
- Agregar secretos administrados, timeouts, retries acotados, circuit breaker, auditoría redactada,
  rate limiting y tests de contrato contra un SQL Warehouse de staging.
- `BackgroundTasks` es best effort: una terminación del proceso puede perder una ejecución activa.
  Los ports permiten migrar a una cola durable si ese riesgo deja de ser aceptable.
