"""Request schemas for the document extraction API."""

from typing import List

from pydantic import BaseModel, Field


class ShipmentFormRequest(BaseModel):
    """Metadata for shipment-form extraction (lists passed as form fields)."""

    inco_terms_list: List[str] = Field(
        default_factory=lambda: ["CIF", "FOB", "EXWORKS"],
        description="Allowed INCO terms for validation/matching.",
    )
    suppliers: List[str] = Field(
        default_factory=list,
        description="Allowed supplier names for validation/matching.",
    )


# File uploads are handled via FastAPI UploadFile; these lists come as form fields.
