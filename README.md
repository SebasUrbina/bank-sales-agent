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
    ├── api/                # FastAPI, DI, lifespan y autenticación
    ├── databricks/         # SQL catalog + implementaciones de ports
    ├── google_chat/        # renderer de artifacts a cardsV2
    └── mock/               # datos locales reemplazables
```

La explicación de límites y extensibilidad está en [docs/architecture.md](docs/architecture.md).

## Ejecutar

```bash
cp .env.example .env
uv sync --group dev
uv run uvicorn bank_sales_agent.infrastructure.api.app:create_app --factory --reload
```

La instancia mock usa un modelo real y requiere `OPENAI_API_KEY`. Una prueba REST:

```bash
curl -X POST http://127.0.0.1:8000/v1/agent/invoke \
  -H 'content-type: application/json' \
  -d '{"user_email":"ejecutivo@bank.test","thread_id":"spaces/AAAA","message":"Dame mi lista de clientes prioritarios"}'
```

## Importante antes de producción

- El mock resuelve `user_email` contra un directorio local. Google Chat debe autenticarse validando
  OIDC; el email del payload solo es confiable después de validar al emisor y debe resolverse contra
  el directorio interno.
- `build_container` usa un repositorio mock. Allí se intercambia por
  `DatabricksCustomerInsightsRepository`; la relación líder-ejecutivo se evalúa dentro de cada
  query Databricks usando sus emails.
- Las consultas de ejemplo usan nombres de tablas ficticios y deben adaptarse al catálogo real.
- Agregar secretos administrados, timeouts, retries acotados, circuit breaker, auditoría redactada,
  rate limiting y tests de contrato contra un SQL Warehouse de staging.
- `BackgroundTasks` es best effort: una terminación del proceso puede perder una ejecución activa.
  Los ports permiten migrar a una cola durable si ese riesgo deja de ser aceptable.
