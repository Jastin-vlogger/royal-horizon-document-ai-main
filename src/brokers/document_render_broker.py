"""PDF/image normalization broker."""

import io
from pathlib import Path

import fitz
from pdf2image import convert_from_bytes, pdfinfo_from_bytes
from PIL import Image

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_PDF_EXTENSION = ".pdf"


class DocumentRenderBroker:
    """Render uploaded documents into PNG page bytes."""

    def get_file_extension(self, filename: str) -> str:
        return Path(filename or "").suffix.lower()

    def is_pdf(self, filename: str) -> bool:
        return self.get_file_extension(filename) == ALLOWED_PDF_EXTENSION

    def is_image(self, filename: str) -> bool:
        return self.get_file_extension(filename) in ALLOWED_IMAGE_EXTENSIONS

    def detect_file_type(self, filename: str) -> str:
        ext = self.get_file_extension(filename)
        if ext == ALLOWED_PDF_EXTENSION:
            return "pdf"
        if ext in ALLOWED_IMAGE_EXTENSIONS:
            return "image"
        return "unknown"

    @staticmethod
    def _pil_to_png(pil_img: Image.Image) -> bytes:
        if pil_img.mode in ("RGBA", "P"):
            pil_img = pil_img.convert("RGB")
        buffer = io.BytesIO()
        pil_img.save(buffer, format="PNG")
        return buffer.getvalue()

    def _image_to_png(self, content: bytes) -> bytes:
        return self._pil_to_png(Image.open(io.BytesIO(content)))

    def first_page_png(self, content: bytes, filename: str) -> bytes:
        if self.is_pdf(filename):
            pages = convert_from_bytes(content, first_page=1, last_page=1, dpi=150)
            if not pages:
                raise ValueError("PDF has no pages")
            return self._pil_to_png(pages[0])
        return self._image_to_png(content)

    def all_pages_png(self, content: bytes, filename: str) -> list[bytes]:
        if self.is_pdf(filename):
            pages = convert_from_bytes(content, dpi=150)
            if not pages:
                raise ValueError("PDF has no readable pages")
            return [self._pil_to_png(page) for page in pages]
        return [self._image_to_png(content)]

    def limited_pages_png(self, content: bytes, filename: str, max_pages: int) -> list[bytes]:
        if max_pages < 1:
            raise ValueError("max_pages must be at least 1")
        if self.is_pdf(filename):
            pages = convert_from_bytes(content, first_page=1, last_page=max_pages, dpi=150)
            if not pages:
                raise ValueError("PDF has no readable pages")
            return [self._pil_to_png(page) for page in pages]
        return [self._image_to_png(content)]

    def strict_limited_pages_png(
        self,
        content: bytes,
        filename: str,
        max_pages: int,
    ) -> list[bytes]:
        if self.is_pdf(filename):
            try:
                info = pdfinfo_from_bytes(content)
                total_pages = int(info.get("Pages", 0))
            except Exception:
                total_pages = self.pdf_page_count(content)
            if total_pages > max_pages:
                raise ValueError(
                    f"PDF has {total_pages} pages, but maximum {max_pages} pages allowed"
                )
        return self.limited_pages_png(content, filename, max_pages)

    def pdf_page_count(self, content: bytes) -> int:
        with fitz.open(stream=content, filetype="pdf") as doc:
            return doc.page_count


_default_broker = DocumentRenderBroker()


def get_file_extension(filename: str) -> str:
    """Compatibility helper for low-level tests and callers."""

    return _default_broker.get_file_extension(filename)


def is_pdf(filename: str) -> bool:
    """Return True if filename suggests PDF."""

    return _default_broker.is_pdf(filename)


def is_image(filename: str) -> bool:
    """Return True if filename suggests an allowed image."""

    return _default_broker.is_image(filename)


def detect_file_type(filename: str) -> str:
    """Detect pdf, image, or unknown by extension."""

    return _default_broker.detect_file_type(filename)


def pdf_first_page_to_image(pdf_bytes: bytes) -> bytes:
    """Convert first PDF page to PNG."""

    pages = convert_from_bytes(pdf_bytes, first_page=1, last_page=1, dpi=150)
    if not pages:
        raise ValueError("PDF has no pages")
    return _default_broker._pil_to_png(pages[0])


def pdf_pages_to_png_images(
    pdf_bytes: bytes,
    first_page: int = 1,
    last_page: int = 2,
) -> list[bytes]:
    """Convert a PDF page range to PNG images."""

    pages = convert_from_bytes(
        pdf_bytes,
        first_page=first_page,
        last_page=last_page,
        dpi=150,
    )
    if not pages:
        raise ValueError("PDF has no readable pages")
    return [_default_broker._pil_to_png(page) for page in pages]


def load_image_bytes(content: bytes, filename: str) -> bytes:
    """Normalize a PDF first page or image to PNG bytes."""

    if is_pdf(filename):
        return pdf_first_page_to_image(content)
    return _default_broker._image_to_png(content)


def load_bill_document_pages(
    content: bytes,
    filename: str,
    max_pages: int = 2,
) -> list[bytes]:
    """Load B/L document pages using the old default page limit."""

    if max_pages < 1:
        raise ValueError("max_pages must be at least 1")
    if is_pdf(filename):
        return pdf_pages_to_png_images(content, first_page=1, last_page=max_pages)
    return [load_image_bytes(content, filename)]


def load_packaging_list_pages(content: bytes, filename: str) -> list[bytes]:
    """Load packaging list pages using the old two-page limit."""

    return _default_broker.strict_limited_pages_png(content, filename, 2)
