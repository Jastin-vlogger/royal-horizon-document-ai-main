"""Application entry and FastAPI app."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config.logger import get_logger
from src.config.settings import get_settings
from src.routes.apis import router as extraction_router
from src.routes.costsheet import router as costsheet_router
from src.routes.purchase_tracker import router as purchase_tracker_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure config and logger are ready."""
    get_logger()
    yield
    # Shutdown if needed
    pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Royal Horizon Document AI",
        description="AI service for key-value extraction from business documents (Performa Invoice, LPO).",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(extraction_router)
    app.include_router(costsheet_router)
    app.include_router(purchase_tracker_router)
    return app


app = create_app()


def run() -> None:
    """Entry point for `poetry run start`: run uvicorn server."""
    import uvicorn

    s = get_settings()
    uvicorn.run(
        "src.main:app",
        host=s.host,
        port=s.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
