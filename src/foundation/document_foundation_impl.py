"""Document foundation implementation."""

from src.brokers.document_render_broker import DocumentRenderBroker
from src.models.domain.documents import DocumentInput


class DocumentFoundation:
    """Domain wrapper for document rendering operations."""

    def __init__(self, document_broker: DocumentRenderBroker) -> None:
        self._document_broker = document_broker

    def file_type(self, document: DocumentInput) -> str:
        return self._document_broker.detect_file_type(document.filename)

    def first_page_png(self, document: DocumentInput) -> bytes:
        return self._document_broker.first_page_png(document.content, document.filename)

    def all_pages_png(self, document: DocumentInput) -> list[bytes]:
        return self._document_broker.all_pages_png(document.content, document.filename)

    def limited_pages_png(self, document: DocumentInput, max_pages: int) -> list[bytes]:
        return self._document_broker.limited_pages_png(
            document.content,
            document.filename,
            max_pages,
        )

    def strict_limited_pages_png(self, document: DocumentInput, max_pages: int) -> list[bytes]:
        return self._document_broker.strict_limited_pages_png(
            document.content,
            document.filename,
            max_pages,
        )

    def pdf_page_count(self, document: DocumentInput) -> int:
        return self._document_broker.pdf_page_count(document.content)
