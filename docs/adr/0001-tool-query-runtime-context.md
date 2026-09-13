# ADR 0001: Tools verticales con cliente SQL en runtime context

- Estado: aceptado
- Fecha: 2026-09-12
- Alcance: tools analíticas que consultan Databricks

## Contexto

El agente expone capacidades de consulta como Vista 360, listado priorizado y, en el futuro,
movimientos, inversiones, alertas y oportunidades. La relación dominante observada es directa:

```text
agent tool -> query fija -> mapping tipado -> JSON para el LLM -> artifact opcional
```

La primera versión introducía un port de repository, una implementación Databricks, un caso de uso
y una función `build_*_tools` por capacidad. Esa separación es apropiada cuando existe un agregado
de dominio o lógica de aplicación independiente, pero en una consulta analítica simple los objetos
eran wrappers de una única llamada y aumentaban el wiring por cada tool.

El objetivo del template es permitir unas veinte tools manteniendo visible la query, el control de
acceso y la transformación del resultado, sin crear agrupaciones de repositories que no representen
la realidad del producto.

## Fuerzas de diseño

1. La unidad de cambio habitual es una capacidad del agente, no una tabla ni un agregado DDD.
2. Cada tool ejecuta SQL fijo y parametrizado; el modelo nunca produce SQL libre.
3. Todas las queries de clientes deben usar identidad autenticada para filtrar filas.
4. `requester_email` y `requester_role` no pueden ser argumentos controlables por el LLM.
5. El cliente Databricks se crea una vez durante el lifespan y se reutiliza.
6. El cliente/conexión no debe persistirse en MongoDB junto con el estado conversacional.
7. Una tool debe poder devolver datos al LLM sin necesariamente generar una card.
8. Agregar una tool debe requerir pocos cambios globales y ser fácil de revisar en un pull request.

## Alternativas consideradas

### A. Un repository y un caso de uso por query

```text
tool -> use case -> repository port -> Databricks repository -> query
```

Ventajas:

- Máximo aislamiento por operación.
- Ports fáciles de sustituir en pruebas.
- Adecuado si cada operación tiene reglas de negocio relevantes.

Desventajas:

- Una interfaz, implementación, mock, wiring y test adicional por query.
- Muchos casos de uso se limitan a delegar argumentos sin aplicar comportamiento.
- La relación tool-query queda distribuida entre varios directorios.

Decisión: descartada como regla general. Sigue disponible cuando una capacidad contiene lógica de
aplicación real.

### B. Readers o repositories agrupados por concepto

```text
CustomerReader
├── get_360
├── list_movements
└── get_products
```

Ventajas:

- Menos tipos que un repository por query.
- Puede ser cohesivo cuando existe un producto de datos claramente definido.

Desventajas:

- Categorías como customer, portfolio o investment pueden ser arbitrarias.
- Una query con joins entre varios dominios no tiene un owner evidente.
- Los readers tienden a crecer hasta convertirse en interfaces y clases extensas.

Decisión: descartada para el template porque la agrupación no surge naturalmente del caso actual.

### C. Builders de tools que capturan dependencias

```python
def build_customer_360_tool(client: SqlWarehouseClient) -> BaseTool:
    @tool
    async def customer_360(...):
        return await client.fetch_all(...)

    return customer_360
```

Ventajas:

- Inyección explícita mediante closure.
- La tool puede probarse con un cliente fake.

Desventajas:

- Requiere una factory por tool.
- El lifespan o registry debe construir cada tool individualmente.
- Agregar una capacidad modifica tanto su módulo como el composition root.

Decisión: descartada. LangChain ya entrega un mecanismo de dependencias por ejecución mediante
`ToolRuntime` y `context_schema`.

### D. Ejecutor o tool SQL genérica

```python
execute_query(query_name, parameters, result_type)
```

Ventajas:

- Muy poco código por query.
- Registro potencialmente declarativo.

Desventajas:

- Oculta contratos y parámetros detrás de strings y diccionarios.
- Facilita omitir filtros de seguridad.
- Hace más difícil revisar qué datos puede consultar una tool.
- Una tool de SQL libre permitiría al modelo ampliar su acceso de forma inaceptable.

Decisión: rechazada. Sólo se comparte el cliente técnico `SqlWarehouseClient`; cada tool mantiene
SQL fijo.

### E. Cliente SQL en `AgentContext`

```text
LangChainAgentRunner
  -> ScopedSqlWarehouseClient por invocación
  -> AgentContext
  -> ToolRuntime
  -> tool de módulo
```

Ventajas:

- No requiere builders por tool.
- Las tools son objetos de módulo registrables directamente.
- El cliente compartido continúa bajo el lifecycle de FastAPI.
- La identidad se incorpora una vez por invocación y queda fuera del schema que ve el modelo.
- `AgentContext` no forma parte del state persistido por el checkpointer.

Desventajas:

- La dependencia SQL no aparece entre los argumentos públicos de la tool.
- Un context con demasiados servicios podría convertirse en service locator.
- Las pruebas directas de tools deben construir un `ToolRuntime`.
- Inyectar parámetros no garantiza que una query efectivamente los utilice; esto debe verificarse.

Decisión: aceptada, con restricciones explícitas.

## Decisión

Las tools analíticas son vertical slices. Cada módulo contiene:

```text
SQL fijo
mapper del resultado
declaración @tool
construcción opcional del artifact
```

El registry importa la tool ya construida:

```python
def build_tool_registry() -> ToolRegistry:
    return ToolRegistry([
        customer_360,
        list_prioritized_customers,
    ])
```

El cliente SQL base se construye una vez en el lifespan. `LangChainAgentRunner` crea un wrapper
scoped para cada invocación:

```python
context = AgentContext(
    principal=invocation.principal,
    request_id=invocation.request_id,
    sql_client=ScopedSqlWarehouseClient(
        self._sql_client,
        invocation.principal,
    ),
)
```

El wrapper agrega la identidad después de los parámetros aportados por la tool:

```python
return await self._client.fetch_all(
    statement,
    {
        **parameters,
        "requester_email": self._principal.email,
        "requester_role": self._principal.role.value,
    },
)
```

El orden es una propiedad de seguridad: si una tool intentara incluir valores falsos, el wrapper
los sobrescribe con la identidad autenticada.

## Ejemplo de tool

```python
CUSTOMER_MOVEMENTS_SQL = """
SELECT m.movement_id, m.rut, m.occurred_at, m.amount
FROM gold.customer_movements m
JOIN gold.assignments a ON a.rut = m.rut AND a.is_current = TRUE
WHERE m.rut = :rut
  AND (
    :requester_role = 'admin'
    OR a.executive_email = :requester_email
    OR EXISTS (
      SELECT 1 FROM gold.commercial_hierarchy h
      WHERE h.leader_email = :requester_email
        AND h.executive_email = a.executive_email
        AND h.is_current = TRUE
    )
  )
ORDER BY m.occurred_at DESC
LIMIT :limit
"""


@tool(response_format="content_and_artifact")
async def customer_movements(
    rut: str,
    runtime: ToolRuntime[AgentContext],
    limit: int = 20,
    render: bool = False,
) -> tuple[str, AgentArtifact | None]:
    rows = await runtime.context.sql_client.fetch_all(
        CUSTOMER_MOVEMENTS_SQL,
        {"rut": rut, "limit": limit},
    )
    movements = map_movements(rows)
    content = json.dumps([asdict(item) for item in movements], default=str)
    artifact = CustomerMovementsArtifact(movements) if render else None
    return content, artifact
```

El LLM sólo puede controlar `rut`, `limit` y `render`. No puede indicar requester ni rol.

## Límites del runtime context

`AgentContext` puede contener únicamente dependencias request-scoped necesarias para ejecutar el
agente:

```text
Permitido
- principal autenticado
- request_id
- ScopedSqlWarehouseClient

No permitido
- Settings completo
- token OAuth de Google
- GoogleChatPublisher
- checkpointer
- clientes sin relación con las tools
```

Si aparecen muchas fuentes de datos, se debe revisar la decisión antes de agregar clientes
indefinidamente. No se introducirá un contenedor genérico de servicios de forma preventiva.

## Autorización en profundidad

La selección de tools por rol mejora la experiencia, pero no es una frontera de seguridad. Cada
tool conserva un chequeo de capability y cada query aplica seguridad por filas.

Se aplican tres niveles:

1. El middleware sólo muestra tools permitidas para el rol.
2. La tool vuelve a validar la capability y restricciones de argumentos.
3. El SQL filtra por `requester_email` y `requester_role`, incluida la jerarquía vigente.

Idealmente las queries consumirán una vista gobernada `authorized_customer_scope` para centralizar
la lógica ejecutivo-líder-admin. Mientras esa vista no exista, tests estructurales comprueban que
cada query protegida utiliza los parámetros de scope y la tabla de jerarquía.

## Testing

Cada nueva tool debe cubrir como mínimo:

1. Mapping de filas válidas y vacías.
2. `render=false` devuelve contenido sin artifact.
3. `render=true` devuelve el artifact esperado.
4. El rol sin capability recibe un error de dominio.
5. Ejecutivo, líder y admin observan únicamente filas autorizadas.
6. El SQL incluye parámetros de scope.
7. `ScopedSqlWarehouseClient` sobrescribe intentos de spoofing.
8. El registry y catálogo contienen exactamente la misma tool.

El mock local implementa `SqlWarehouseClient`; no implementa un repository paralelo. De este modo,
las tools locales recorren el mismo flujo que producción desde `ToolRuntime` hacia el cliente SQL.

## Cómo agregar una nueva tool

Para agregar `customer_movements`:

1. Agregar el modelo de salida al dominio si expresa un concepto estable.
2. Crear `infrastructure/agent/tools/customer_movements.py`.
3. Declarar SQL fijo, mapper y función decorada con `@tool`.
4. Usar exclusivamente `runtime.context.sql_client` para consultar.
5. No aceptar email, rol, SQL, tabla ni credenciales como argumentos del modelo.
6. Agregar capability y metadata al catálogo.
7. Importar la tool en `registry.py`.
8. Agregar el artifact neutral y su renderer sólo si la tool soporta `render=true`.
9. Implementar tests de mapping, autorización, scope y presentación.

## Cuándo introducir un caso de uso

Este ADR no elimina application ni prohíbe casos de uso. Se agrega uno cuando exista comportamiento
independiente de la query, por ejemplo:

- combinar varias fuentes antes de decidir un resultado;
- aplicar reglas de priorización o elegibilidad del banco;
- coordinar una operación con efectos laterales;
- reutilizar la misma política desde API, batch y agente;
- requerir transacciones o consistencia entre pasos.

En esos casos el flujo puede ser:

```text
tool -> caso de uso -> uno o más ports -> infraestructura
```

No se creará un caso de uso cuyo único cuerpo sea delegar una query.

## Consecuencias

Positivas:

- Menos wiring y archivos ceremoniales por tool.
- Relación tool-query visible en un único módulo.
- Identidad fuera del control del modelo.
- Mocks alineados con el contrato real utilizado por las tools.
- Incorporación incremental de nuevas capacidades.

Negativas:

- Algunas tools pueden crecer demasiado si acumulan lógica.
- El SQL queda en módulos Python; una query muy extensa deberá migrarse a un archivo `.sql` vecino.
- Cambiar de Databricks a una fuente no SQL requiere modificar el slice correspondiente.
- La disciplina de autorización necesita tests y revisión; el wrapper no puede reparar SQL que
  ignore completamente los parámetros de scope.

## Criterios de revisión futura

Revisar esta decisión si ocurre alguno de estos eventos:

- más de un cliente de datos aparece en la mayoría de las tools;
- varias tools repiten una misma composición o política compleja;
- una tool supera aproximadamente 200 líneas por lógica no relacionada con mapping;
- se necesitan operaciones de escritura o transacciones;
- las mismas capacidades deben exponerse fuera del agente;
- la vista de autorización cambia de forma que exige un componente dedicado.

Hasta entonces, el patrón oficial del template es:

```text
una tool -> una query explícita -> un resultado tipado -> artifact opcional
```
