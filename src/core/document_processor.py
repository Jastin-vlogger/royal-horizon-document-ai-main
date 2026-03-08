"""Document processing: file type detection, PDF first-page to image, image loading."""

import io
from pathlib import Path
from typing import Tuple

from PIL import Image

# PDF: first page only -> image via pdf2image (requires poppler in Docker)
from pdf2image import convert_from_bytes

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_PDF_EXTENSION = ".pdf"


def get_file_extension(filename: str) -> str:
    """Return lowercase extension including dot, e.g. '.pdf'."""
    return Path(filename or "").suffix.lower()


def is_pdf(filename: str) -> bool:
    """Return True if filename suggests PDF."""
    return get_file_extension(filename) == ALLOWED_PDF_EXTENSION


def is_image(filename: str) -> bool:
    """Return True if filename suggests an allowed image type."""
    return get_file_extension(filename) in ALLOWED_IMAGE_EXTENSIONS


def detect_file_type(filename: str) -> str:
    """
    Detect file type from filename.
    Returns one of: 'pdf', 'image', or 'unknown'.
    """
    ext = get_file_extension(filename)
    if ext == ALLOWED_PDF_EXTENSION:
        return "pdf"
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return "image"
    return "unknown"


def pdf_first_page_to_image(pdf_bytes: bytes) -> bytes:
    """
    Convert the first page of a PDF to PNG image bytes.
    :param pdf_bytes: Raw PDF file content.
    :return: PNG image as bytes.
    """
    pages = convert_from_bytes(pdf_bytes, first_page=1, last_page=1, dpi=150)
    if not pages:
        raise ValueError("PDF has no pages")
    pil_img = pages[0]
    if pil_img.mode in ("RGBA", "P"):
        pil_img = pil_img.convert("RGB")
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()


def load_image_bytes(content: bytes, filename: str) -> bytes:
    """
    Ensure we have image bytes. If content is PDF, convert first page to image.
    Otherwise assume content is already image (jpg/png) and return as-is (or normalize to PNG for consistency).
    :param content: Raw file bytes.
    :param filename: Original filename for type detection.
    :return: Image as PNG bytes (for consistent handling by vision API).
    """
    if is_pdf(filename):
        return pdf_first_page_to_image(content)
    # Already image: optionally convert to PNG so we have a single format
    pil_img = Image.open(io.BytesIO(content))
    if pil_img.mode in ("RGBA", "P"):
        pil_img = pil_img.convert("RGB")
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()


def read_upload_to_bytes(upload) -> Tuple[bytes, str]:
    """
    Read an UploadFile and return (bytes, filename).
    Caller should validate filename before processing.
    """
    content = upload.file.read()
    filename = upload.filename or "unknown"
    return content, filename
