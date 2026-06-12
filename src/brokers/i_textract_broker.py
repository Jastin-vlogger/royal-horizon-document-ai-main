"""Textract broker interface."""

from typing import Protocol


class TextractBrokerInterface(Protocol):
    """Low-level OCR table extraction interface."""

    def extract_tables(self, image_bytes: bytes) -> list[list[list[str]]]:
        """Return tables as rows and cells."""
