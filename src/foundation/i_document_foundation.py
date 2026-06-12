"""Document foundation interface."""

from typing import Protocol

from src.models.domain.documents import DocumentInput


class DocumentFoundationInterface(Protocol):
    """Domain document operations."""

    def file_type(self, document: DocumentInput) -> str:
        """Return document file type."""

    def first_page_png(self, document: DocumentInput) -> bytes:
        """Return first page PNG bytes."""

    def all_pages_png(self, document: DocumentInput) -> list[bytes]:
        """Return all pages as PNG bytes."""

    def limited_pages_png(self, document: DocumentInput, max_pages: int) -> list[bytes]:
        """Return limited pages as PNG bytes."""

    def strict_limited_pages_png(self, document: DocumentInput, max_pages: int) -> list[bytes]:
        """Return limited pages and reject PDFs above max_pages."""
