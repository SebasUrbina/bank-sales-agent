# Bank Sales Agent

Mockup ejecutable de un agente para ejecutivos bancarios, construido con FastAPI, LangChain
`create_agent` y Clean Architecture. Incluye Vista 360, listado priorizado, roles, alcance por
cartera, jerarquía de líderes, cards de Google Chat y un adaptador Databricks.

Los eventos de Google Chat reciben un acuse inmediato. FastAPI ejecuta el agente mediante
`BackgroundTasks` y, al terminar, publica una única respuesta con texto y cards usando Google Chat
API. El modo local usa un cliente mock; `GOOGLE_CHAT_ENABLED=true` activa ADC/Workload Identity.

## Estructura

```text
src/bank_sales_agent/
├── domain/                 # entidades, roles, capacidades y reglas puras
├── application/
│   ├── agent/              # instrucciones, catálogo y política sin LangChain
│   ├── ports.py            # contratos requeridos por el negocio
│   ├── services/           # resolución de alcance
│   └── use_cases/          # Vista 360 y listado priorizado
└── infrastructure/
    ├── agent/              # create_agent, runner, registry y tools por feature
    ├── api/                # factory, rutas, schemas y composition root en lifespan
    ├── config/             # settings y secretos tipados
    ├── databricks/         # SQL catalog + implementaciones de ports
    ├── google_chat/        # renderer de artifacts a cardsV2
    └── mock/               # datos locales reemplazables
```

La explicación de límites y extensibilidad está en [docs/architecture.md](docs/architecture.md).

## Ejecutar

```bash
cp .env.example .env
uv sync --group dev
uv run uvicorn bank_sales_agent.main:app --reload
```

La instancia mock usa un modelo real y requiere `OPENAI_API_KEY`. Una prueba REST:

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
las secciones `api`, `mongodb`, `langchain`, `databricks` y `google_chat` son `BaseModel` y se
configuran con variables como `LANGCHAIN__MODEL_NAME` o `GOOGLE_CHAT__ENABLED`.

## Importante antes de producción

- El mock resuelve `user_email` contra un directorio local. Google Chat debe autenticarse validando
  OIDC; el email del payload solo es confiable después de validar al emisor y debe resolverse contra
  el directorio interno.
- `infrastructure/api/lifespan.py` es el composition root. Usa repositorios mock por defecto y
  conecta `DatabricksCustomerInsightsRepository` cuando `DATABRICKS_ENABLED=true`; sólo guarda en
  `app.state` los casos de uso consumidos por las rutas.
- `pydantic-settings` carga configuración desde variables de entorno y `.env` sólo para desarrollo.
  Los secretos se tipan como `SecretStr`; en producción deben inyectarse desde el secret manager de
  la plataforma y nunca almacenarse en el repositorio.
- Las consultas de ejemplo usan nombres de tablas ficticios y deben adaptarse al catálogo real.
- Agregar secretos administrados, timeouts, retries acotados, circuit breaker, auditoría redactada,
  rate limiting y tests de contrato contra un SQL Warehouse de staging.
- `BackgroundTasks` es best effort: una terminación del proceso puede perder una ejecución activa.
  Los ports permiten migrar a una cola durable si ese riesgo deja de ser aceptable.
