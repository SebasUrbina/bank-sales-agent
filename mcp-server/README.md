# Bank Sales MCP

Deployment independiente del agente. Este proyecto contiene FastMCP, autorización por rol,
consultas SQL, acceso a Databricks y datos mock. No importa `bank_sales_agent` ni usa LangChain,
LLM, Google Chat o MongoDB. Sólo comparte los contratos de `../packages/bank-sales-contracts`.

## Ejecutar localmente

Desde este directorio:

```bash
cp .env.example .env
# Reemplazar MCP__SIGNING_SECRET por el mismo secreto administrado de la API.
uv sync --locked
uv run bank-sales-mcp
```

El endpoint Streamable HTTP está en `http://127.0.0.1:8001/mcp`. El agente usa `MCP__URL` para
conectarse y firma un token de corta duración. El servidor valida la firma, issuer, audience y
expiración, resuelve el rol del usuario y aplica scope SQL. Configuración propia en `.env.example`.
`DATABRICKS__*` se configura solamente aquí; con `DATABRICKS__ENABLED=false` se usan datos mock.
`create_server()` permite inyectar el directorio corporativo y el cliente SQL.

## Construir y ejecutar el contenedor

Desde la raíz del repositorio (el contexto incluye sólo este servicio y los contratos compartidos):

```bash
docker build -f mcp-server/Dockerfile -t bank-sales-mcp:local .
docker run --rm --env-file mcp-server/.env -p 8001:8001 bank-sales-mcp:local
```

La imagen instala su propio lockfile sin dependencias de desarrollo y corre como usuario sin
privilegios. El agente no se copia en la imagen. Para otro puerto, cambiar `MCP__PORT` y el mapeo.
En el deployment del agente, apuntar `MCP__URL` al DNS/URL de este servicio y suministrar el mismo
secreto de firma desde el gestor de secretos. No publicar `.env` dentro de la imagen.

Las dos imágenes/releases pueden versionarse y desplegarse por separado. El paquete compartido
`bank-sales-contracts==0.2.0` puede publicarse en el registro interno; para este monorepo ambos
proyectos lo instalan desde la ruta local, que la imagen copia en tiempo de build.

## Validación

```bash
make check
```

Las pruebas propias cubren configuración, consultas, alcance SQL y resultados de las tools. Las
pruebas HTTP agente→servidor permanecen en `../tests/test_roles_mcp.py` y se ejecutan con `make check`
en la raíz. El servidor es una dependencia de desarrollo del agente únicamente para esas pruebas;
`uv sync --no-dev` no lo instala en el deployment de la API.

## Propiedad de los permisos

`bank_sales_mcp/policies.py` define capabilities y permisos por rol; `catalog.py` vincula tools con
capabilities. Ambos módulos pertenecen únicamente al servidor. El paquete compartido contiene
identidad y payloads, sin decisiones de autorización. El MCP filtra `tools/list` y autoriza
`tools/call` desde su directorio, independientemente del rol que crea conocer la API.

Para agregar una tool, registrar su operación y endpoint en el MCP, agregar su entrada al catálogo
y definir permisos aquí. El agente descubre su schema y descripción dinámicamente sin una nueva
versión del agente, siempre que la respuesta conserve el contrato de intercambio compatible.
