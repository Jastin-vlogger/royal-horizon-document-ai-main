"""Input validation and preprocessing for stock-sheet pipeline."""

import asyncio
import io
from dataclasses import dataclass, field

import fitz
from PIL import Image

from src.config.settings import get_settings
from src.core.document_processor import detect_file_type, pdf_pages_to_png_images
from src.core.stock_sheet.vision_checks import detect_orientation
from src.schemas.response import ExtractionMetadata


@dataclass
class PreparedPages:
    """Prepared stock-sheet pages ready for OCR and signature checks."""

    file_type: str
    pages_detected: int
    page_images: list[bytes]
    temp_artifacts_deleted: int = 0
    orientation_metadata: list[ExtractionMetadata] = field(default_factory=list)
    rotation_angles: list[int] = field(default_factory=list)


def get_pdf_page_count(content: bytes) -> int:
    """Count PDF pages using PyMuPDF."""
    with fitz.open(stream=content, filetype="pdf") as doc:
        return doc.page_count


def _normalize_image_to_png(content: bytes) -> bytes:
    settings = get_settings()
    image = Image.open(io.BytesIO(content))
    if image.width * image.height > settings.stock_sheet_max_image_pixels:
        raise ValueError(
            f"Image dimensions exceed max allowed pixels ({settings.stock_sheet_max_image_pixels})."
        )
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _rotate_png_bytes(image_bytes: bytes, clockwise_degrees: int) -> bytes:
    if clockwise_degrees == 0:
        return image_bytes
    image = Image.open(io.BytesIO(image_bytes))
    # PIL rotate is counter-clockwise for positive angle.
    rotated = image.rotate(-clockwise_degrees, expand=True)
    if rotated.mode in ("RGBA", "P"):
        rotated = rotated.convert("RGB")
    buffer = io.BytesIO()
    rotated.save(buffer, format="PNG")
    return buffer.getvalue()


async def _apply_orientation(images: list[bytes]) -> tuple[list[bytes], list[ExtractionMetadata], list[int]]:
    if not images:
        return [], [], []

    orientation_results = await asyncio.gather(*(detect_orientation(page) for page in images))
    rotated_images = await asyncio.gather(
        *[
            asyncio.to_thread(_rotate_png_bytes, image, angle)
            for image, (angle, _) in zip(images, orientation_results)
        ]
    )
    angles = [angle for angle, _ in orientation_results]
    metadata = [meta for _, meta in orientation_results]
    return rotated_images, metadata, angles


async def prepare_pages(content: bytes, filename: str) -> PreparedPages:
    """Validate input type and convert it into oriented PNG page images."""
    settings = get_settings()
    file_type = detect_file_type(filename)
    if file_type == "unknown":
        raise ValueError("Unsupported file type. Allowed: PDF, JPG, JPEG, PNG.")

    if file_type == "pdf":
        pages_detected = await asyncio.to_thread(get_pdf_page_count, content)
        if pages_detected > settings.stock_sheet_pdf_max_pages:
            raise ValueError(
                f"PDF has {pages_detected} pages; max allowed is {settings.stock_sheet_pdf_max_pages}."
            )
        images = await asyncio.to_thread(
            pdf_pages_to_png_images,
            content,
            1,
            settings.stock_sheet_pdf_max_pages,
        )
    else:
        pages_detected = 1
        images = [await asyncio.to_thread(_normalize_image_to_png, content)]

    orientation_metadata: list[ExtractionMetadata] = []
    rotation_angles = [0 for _ in images]
    if settings.stock_sheet_enable_preprocess:
        images, orientation_metadata, rotation_angles = await _apply_orientation(images)

    return PreparedPages(
        file_type=file_type,
        pages_detected=pages_detected,
        page_images=images,
        temp_artifacts_deleted=0,
        orientation_metadata=orientation_metadata,
        rotation_angles=rotation_angles,
    )
