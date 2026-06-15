"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config.logger import get_logger
from src.config.settings import get_settings
from src.containers.application_container import create_container
from src.routers.arrival_notice import router as arrival_notice_router
from src.routers.bank_advice import router as bank_advice_router
from src.routers.boe import router as boe_router
from src.routers.costsheet import router as costsheet_router
from src.routers.dpw_cargo import router as dpw_cargo_router
from src.routers.purchase_tracker import router as purchase_tracker_router
from src.routers.shipment import router as shipment_router
from src.routers.stock_sheet import router as stock_sheet_router
from src.routers.tax_invoice import router as tax_invoice_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize process-wide infrastructure."""

    get_logger()
    app.state.container = create_container()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="Royal Horizon Document AI",
        description="Layered AI service for document extraction workflows.",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.include_router(shipment_router)
    app.include_router(arrival_notice_router)
    app.include_router(bank_advice_router)
    app.include_router(boe_router)
    app.include_router(costsheet_router)
    app.include_router(dpw_cargo_router)
    app.include_router(purchase_tracker_router)
    app.include_router(stock_sheet_router)
    app.include_router(tax_invoice_router)
    return app


app = create_app()


def run() -> None:
    """Run uvicorn server for `poetry run start`."""

    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
