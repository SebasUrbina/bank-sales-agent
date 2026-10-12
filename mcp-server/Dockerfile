# Build desde la raíz: docker build -f mcp-server/Dockerfile -t bank-sales-mcp .
FROM ghcr.io/astral-sh/uv:0.10.12 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app/mcp-server
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/app/mcp-server/.venv/bin:$PATH"
COPY packages/bank-sales-contracts /app/packages/bank-sales-contracts
COPY mcp-server/pyproject.toml mcp-server/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY mcp-server/bank_sales_mcp ./bank_sales_mcp
RUN uv sync --frozen --no-dev \
    && useradd --uid 10001 --create-home mcp
USER mcp
EXPOSE 8001
CMD ["bank-sales-mcp"]
