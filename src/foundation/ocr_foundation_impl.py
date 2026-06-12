"""OCR foundation implementation."""

from src.brokers.i_textract_broker import TextractBrokerInterface


class OCRFoundation:
    """Domain wrapper around OCR broker."""

    def __init__(self, textract_broker: TextractBrokerInterface) -> None:
        self._textract_broker = textract_broker

    def extract_tables(self, image_bytes: bytes) -> list[list[list[str]]]:
        return self._textract_broker.extract_tables(image_bytes)
