"""OCR foundation interface."""

from typing import Protocol


class OCRFoundationInterface(Protocol):
    """Domain OCR operations."""

    def extract_tables(self, image_bytes: bytes) -> list[list[list[str]]]:
        """Extract OCR tables from an image."""
