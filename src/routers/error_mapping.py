"""HTTP exception mapping for routers."""

from fastapi import HTTPException

from src.models.domain.errors import (
    ConfigurationError,
    DomainValidationError,
    LLMOutputError,
    ShipmentClassificationError,
)


async def run_http(coro, *, failure_detail: str):
    """Execute a workflow coroutine and map domain errors to HTTP errors."""

    try:
        return await coro
    except ShipmentClassificationError as exc:
        classified_data = exc.classified_data
        raise HTTPException(
            status_code=422,
            detail={
                "error": "document_classification_failed",
                "reason": classified_data.get("reason", ""),
                "has_lpo": classified_data.get("has_lpo", False),
                "has_ricequality_doc": classified_data.get("has_ricequality_doc", False),
                "is_valid_document": False,
                "classified_data": classified_data,
            },
        ) from exc
    except DomainValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMOutputError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LLM response could not be validated: {exc}",
        ) from exc
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"{failure_detail}: {exc}",
        ) from exc
