"""Document rendering broker interface."""

from typing import Protocol


class DocumentRenderBrokerInterface(Protocol):
    """Low-level document type detection and image rendering."""

    def detect_file_type(self, filename: str) -> str:
        """Return pdf, image, or unknown."""

    def first_page_png(self, content: bytes, filename: str) -> bytes:
        """Render a PDF first page or normalize an image to PNG."""

    def all_pages_png(self, content: bytes, filename: str) -> list[bytes]:
        """Render all PDF pages or normalize one image to PNG."""

    def limited_pages_png(self, content: bytes, filename: str, max_pages: int) -> list[bytes]:
        """Render up to max_pages PDF pages or normalize one image to PNG."""

    def pdf_page_count(self, content: bytes) -> int:
        """Return PDF page count."""
