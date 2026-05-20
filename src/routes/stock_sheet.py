"""Stock-sheet extraction API route."""

from fastapi import APIRouter, File, UploadFile

from src.config.logger import logger
from src.core.stock_sheet.pipeline import run_stock_sheet_pipeline
from src.schemas.stock_sheet import StockSheetResponse

router = APIRouter(prefix="", tags=["stock-sheet"])


@router.post(
    "/extract/stock-sheet",
    response_model=StockSheetResponse,
    summary="Extract stock-sheet table rows from PDF or image",
)
async def extract_stock_sheet(
    file: UploadFile = File(
        ...,
        description="Stock-sheet input file (PDF/JPG/JPEG/PNG).",
    ),
) -> StockSheetResponse:
    """Process stock-sheet file and always return a unified JSON response."""
    logger.debug("Processing stock-sheet extraction API")
    content = await file.read()
    filename = file.filename or "unknown"
    return await run_stock_sheet_pipeline(content, filename)
