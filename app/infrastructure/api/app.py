from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.errors import CustomerNotFoundError, ForbiddenError
from app.infrastructure.api.lifespan import create_lifespan
from app.infrastructure.api.router import agent_router, health_router
from app.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    api_settings = resolved_settings.api
    app = FastAPI(
        title=api_settings.title,
        version=api_settings.version,
        docs_url="/docs" if api_settings.docs_enabled else None,
        redoc_url="/redoc" if api_settings.docs_enabled else None,
        openapi_url="/openapi.json" if api_settings.docs_enabled else None,
        lifespan=create_lifespan(resolved_settings),
    )

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(_: Request, error: ForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(error)})

    @app.exception_handler(CustomerNotFoundError)
    async def not_found_handler(_: Request, error: CustomerNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    app.include_router(health_router)
    app.include_router(agent_router)
    return app
