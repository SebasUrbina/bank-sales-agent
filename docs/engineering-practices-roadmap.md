# Roadmap de prácticas de ingeniería

Este documento registra las prácticas y herramientas evaluadas para evolucionar el template. No
todas deben incorporarse inmediatamente: cada dependencia debe resolver un problema observado y
tener un owner operativo. El estado real de las herramientas ya incorporadas se mantiene en el
README.

## Criterios de priorización

1. Seguridad y aislamiento de datos bancarios.
2. Detección temprana de errores y regresiones.
3. Capacidad de diagnosticar fallas en producción.
4. Bajo costo cognitivo y operacional.
5. Evitar duplicar capacidades ya provistas por Ruff, uv, MyPy, APIM o los SDK utilizados.

## Implementadas

### uv

Responsabilidad:

- Resolver y bloquear dependencias en `uv.lock`.
- Crear y sincronizar el entorno de desarrollo.
- Ejecutar comandos con el entorno del proyecto.

Decisión: mantenerlo como único package manager; no agregar Poetry o Pipenv.

### Ruff lint y formatter

Responsabilidad:

- Errores estáticos básicos.
- Imports y modernización de sintaxis.
- Reglas Bugbear y simplificación.
- Formato automático consistente.
- Formato de ejemplos Python en docstrings.

Comandos:

```bash
make format
make lint
```

Estado actual de reglas:

```toml
select = ["E", "F", "I", "UP", "B", "SIM"]
```

Mejora futura: evaluar incrementalmente `ASYNC`, `S`, `G`, `PT`, `C4`, `PIE`, `RET` y `RUF`.
No se deben activar todos juntos sin revisar falsos positivos y correcciones existentes.

### MyPy strict

Responsabilidad:

- Validar contratos internos y tipos de retorno.
- Detectar incompatibilidades entre ports, adaptadores y modelos.
- Evitar introducir otro type checker con reglas divergentes.

Decisión: mantener MyPy como único type checker; no agregar Pyright salvo que exista una necesidad
específica no cubierta.

### Pytest, pytest-asyncio y pytest-cov

Responsabilidad:

- Tests unitarios y async.
- Branch coverage sobre `bank_sales_agent`.
- Umbral mínimo inicial de 73%, correspondiente a la línea base verificada.
- Reporte de líneas y branches faltantes.

El porcentaje es una barrera contra regresiones, no una medida suficiente de calidad. Son más
importantes los tests de autorización, contratos, errores y efectos externos.

### pre-commit

Responsabilidad:

- Ejecutar Ruff lint con autofix.
- Ejecutar Ruff formatter.
- Entregar feedback rápido antes de crear un commit.

MyPy, tests y auditorías no se ejecutan en este hook para no degradar el ciclo local. La validación
completa corresponde a `make check` y CI.

### pydantic-settings

Responsabilidad:

- Una lectura tipada del environment por aplicación.
- Secciones para API, MongoDB, APIM/LLM, Databricks y Google Chat.
- Validación cruzada según ambiente.
- Redacción de secretos mediante `SecretStr`.

No reemplaza el secret manager de la plataforma. En producción los secretos deben inyectarse como
variables de entorno o mediante el mecanismo nativo del runtime.

## Prioridad alta: siguientes incorporaciones

### 1. CI obligatorio en GitHub Actions

Problema que resuelve: hoy los comandos existen, pero nada garantiza que se ejecuten antes de
integrar cambios.

Pipeline recomendado:

```text
quality
├── uv sync --locked
├── ruff check
├── ruff format --check
├── mypy
└── import-linter

tests
├── pytest
└── branch coverage

security
├── pip-audit
└── gitleaks
```

Criterio de adopción: antes de que más de una persona contribuya o antes del primer despliegue.

### 2. respx para contratos HTTP

Problema que resuelve: verificar el cliente Google Chat y APIM sin llamadas reales.

Debe probar:

- URL y método.
- Authorization y subscription headers sin imprimir secretos.
- `requestId` e información del thread.
- Body de Cards V2.
- Timeouts.
- Respuestas 400, 401, 403, 429 y 5xx.
- Clasificación de errores retryable y no retryable.

Criterio de adopción: antes de conectar Google Chat real.

### 3. import-linter

Problema que resuelve: convertir las reglas de Clean Architecture en checks ejecutables.

Contratos mínimos:

```text
domain no importa application ni infrastructure
application no importa infrastructure
adaptadores Google Chat y Databricks no aparecen en domain
```

Criterio de adopción: ahora que la arquitectura fue estabilizada y documentada mediante ADRs.

### 4. pip-audit

Problema que resuelve: detectar dependencias con vulnerabilidades públicas conocidas.

Uso recomendado:

```bash
uv run pip-audit .
```

Debe ejecutarse en CI porque requiere red. No reemplaza revisión de código, actualización controlada
de dependencias ni análisis de paquetes maliciosos.

Criterio de adopción: antes del primer despliegue conectado a datos reales.

### 5. gitleaks o detect-secrets

Problema que resuelve: impedir commits de:

- OAuth tokens.
- MongoDB URIs con credenciales.
- Tokens Databricks.
- API keys y subscription keys de APIM.
- Service accounts.
- Archivos `.env`.

Recomendación: gitleaks como check de CI. Se puede agregar un hook local cuando el equipo defina su
baseline de falsos positivos.

Criterio de adopción: antes de compartir secretos de ambientes no locales.

## Prioridad media

### 6. Hypothesis

Problema que resuelve: validar invariantes con inputs generados, no sólo ejemplos manuales.

Casos de alto valor:

- `ScopedSqlWarehouseClient` siempre sobrescribe email y rol falsos.
- Model names no pueden escapar la ruta permitida del APIM.
- Límites de `limit`, scores y attachments.
- Normalización de emails.
- Payloads incompletos o con strings extremos.

Criterio de adopción: cuando los schemas y reglas de autorización dejen de cambiar frecuentemente.

### 7. Logging estructurado

Opciones:

- `structlog` si la plataforma espera JSON construido por la aplicación.
- `logging` estándar con `LoggerAdapter` y `contextvars` si la plataforma ya estructura los logs.

Campos recomendados:

```text
environment
request_id
thread_id_hash
principal_hash
tool_name
duration_ms
row_count
artifact_rendered
error_code
```

Datos prohibidos en logs:

```text
OAuth tokens
MongoDB URI
Databricks token
API keys
RUT completo
prompts y resultados financieros sin redacción
```

Criterio de adopción: antes del primer ambiente compartido.

### 8. OpenTelemetry

Problema que resuelve: correlacionar latencia y fallas a través de FastAPI, APIM, tools, Databricks y
Google Chat.

Paquetes candidatos:

```text
opentelemetry-api
opentelemetry-sdk
opentelemetry-instrumentation-fastapi
opentelemetry-instrumentation-httpx
opentelemetry-exporter-otlp
```

Jerarquía deseada:

```text
FastAPI request
└── agent invocation
    ├── APIM model call
    ├── tool
    │   └── Databricks query
    └── Google Chat publish
```

No se deben exportar prompts, artifacts o información financiera sin una decisión explícita de
privacidad.

Criterio de adopción: cuando exista un backend OTLP y un owner de dashboards/alertas.

### 9. Tenacity para retries selectivos

Problema que resuelve: recuperarse de errores externos transitorios.

Aplicar sólo a:

- 429 y 5xx transitorios del APIM.
- Fallas transitorias de Google Chat.
- Errores de conexión clasificados de Databricks o MongoDB.

No reintentar:

- 400, 401 o 403.
- Inputs inválidos.
- Acceso fuera de cartera.
- Errores de mapping o SQL.

Antes de agregarlo se deben revisar los retries nativos de los SDK para evitar multiplicación de
intentos y latencia.

Criterio de adopción: cuando se definan timeouts y presupuesto total de ejecución.

### 10. Modelos Pydantic para filas externas

Problema que resuelve: detectar drift de schemas Databricks con errores claros.

Patrón recomendado:

```python
class Customer360Row(BaseModel):
    rut: str
    executive_email: str
    full_name: str
    segment: str
    total_balance: Decimal
    products: list[str]
```

Estos modelos pertenecen a infraestructura. Los modelos de dominio pueden continuar como
dataclasses.

Criterio de adopción: al conectar las primeras tablas reales de Databricks.

### 11. SQLFluff

Problema que resuelve: formato y convenciones de SQL cuando las queries crezcan o migren a `.sql`.

La compatibilidad del dialecto debe probarse con SQL real de Databricks antes de volver el check
bloqueante. No reemplaza tests de scope ni pruebas contra staging.

Criterio de adopción: cuando existan varias queries largas o un estándar SQL compartido.

## Prácticas operacionales sin nueva librería

### Autenticación verificable

El backend debe derivar o verificar el email desde una credencial confiable. No debe autorizar
solamente con el `user_email` declarado en el payload.

### Thread ID namespaced

La llave interna debería incorporar al menos ambiente, usuario autenticado y thread externo para
evitar colisiones o lectura cruzada de checkpoints.

### Política de checkpoints

Definir:

- TTL.
- Cifrado.
- Eliminación por usuario/thread.
- Datos permitidos en mensajes y tool results.
- Compatibilidad al cambiar schemas o nombres de tools.

### Idempotencia

Apps Script debe entregar un `event_id` estable. El backend debe evitar ejecutar dos veces un mismo
evento aunque el intermediario reintente la llamada.

### Errores de background tasks

Si el agente falla después del `202 Accepted`, debe publicar una respuesta segura al canal y
registrar el error técnico con `request_id`. No debe dejar al usuario esperando indefinidamente.

### Límites explícitos

Aplicar límites de código además de instrucciones al LLM:

- Tiempo máximo total.
- Número máximo de tool calls.
- Número máximo de artifacts.
- Filas máximas por query.
- Tamaño y tipos de attachments.
- Concurrencia máxima hacia Databricks.

### Tests por niveles

Marcadores sugeridos:

```text
unit        sin servicios externos
contract    verifica puertos y adaptadores
integration requiere MongoDB, Databricks/APIM o emuladores controlados
```

Los tests de integración deben usar credenciales y datos de staging, nunca información productiva.

## Herramientas que no se recomiendan por ahora

### dependency-injector

El lifespan ya actúa como composition root de forma explícita. Un framework de DI agregaría una
capa sin resolver un problema actual.

### Black, isort y Flake8

Sus responsabilidades ya están cubiertas por Ruff.

### Pyright

Duplicaría MyPy strict. Puede reevaluarse si el IDE necesita una capacidad que MyPy no entregue.

### Poetry o Pipenv

Duplicarían la gestión ya realizada por uv y `uv.lock`.

### SQLAlchemy

Las operaciones actuales son queries analíticas fijas contra Databricks; no existe un modelo ORM ni
transacciones de escritura que justifiquen incorporarlo.

### Celery/Redis

`BackgroundTasks` es suficiente para la escala declarada. Se debe migrar a una cola durable sólo si
la pérdida de tareas ante reinicios, la ejecución distribuida o el volumen lo requieren.

### Framework genérico para repositories o tools

El patrón adoptado es una vertical slice explícita por tool. Sólo se extraerá una abstracción cuando
varias implementaciones reales demuestren la misma repetición y reglas de evolución.

## Orden recomendado

```text
1. GitHub Actions + branch protection
2. respx
3. import-linter
4. pip-audit + gitleaks
5. logging estructurado
6. OpenTelemetry
7. Hypothesis
8. Pydantic row models
9. retries selectivos
10. SQLFluff
```

Este orden debe cambiar si aparece antes un riesgo operacional o regulatorio concreto.
