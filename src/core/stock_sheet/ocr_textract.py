"""AWS Textract integration for stock-sheet tables."""

from collections import defaultdict
from typing import Any

import boto3
from botocore.config import Config

from src.config.settings import get_settings


class TextractTableExtractor:
    """Extract stock-sheet tables from images using AWS Textract."""

    def __init__(self) -> None:
        settings = get_settings()
        session = boto3.session.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        self._client = session.client(
            "textract",
            config=Config(retries={"max_attempts": settings.retry, "mode": "standard"}),
        )

    def extract_tables(self, image_bytes: bytes) -> list[list[list[str]]]:
        """Run Textract AnalyzeDocument and return all detected tables."""
        response: dict[str, Any] = self._client.analyze_document(
            Document={"Bytes": image_bytes},
            FeatureTypes=["TABLES"],
        )
        return self._extract_tables(response)

    def extract_rows(self, image_bytes: bytes) -> list[list[str]]:
        """Backward-compatible flattened view of all table rows."""
        return [row for table in self.extract_tables(image_bytes) for row in table]

    def _extract_tables(self, response: dict[str, Any]) -> list[list[list[str]]]:
        blocks = response.get("Blocks", [])
        block_map = {block["Id"]: block for block in blocks if "Id" in block}
        tables: list[list[list[str]]] = []

        for block in blocks:
            if block.get("BlockType") != "TABLE":
                continue

            cells: list[tuple[int, int, str]] = []
            for rel in block.get("Relationships", []):
                if rel.get("Type") != "CHILD":
                    continue
                for child_id in rel.get("Ids", []):
                    child = block_map.get(child_id, {})
                    if child.get("BlockType") != "CELL":
                        continue
                    row_index = int(child.get("RowIndex", 0))
                    col_index = int(child.get("ColumnIndex", 0))
                    if row_index <= 0 or col_index <= 0:
                        continue
                    cells.append((row_index, col_index, self._get_text_from_block(child, block_map)))

            if not cells:
                continue

            row_map: dict[int, dict[int, str]] = defaultdict(dict)
            for row_index, col_index, text in cells:
                row_map[row_index][col_index] = text

            table: list[list[str]] = []
            for row_number in sorted(row_map):
                row_data = [row_map[row_number][col_number] for col_number in sorted(row_map[row_number])]
                if any(cell.strip() for cell in row_data):
                    table.append(row_data)

            if table:
                tables.append(table)

        return tables

    @staticmethod
    def _get_text_from_block(block: dict[str, Any], block_map: dict[str, dict[str, Any]]) -> str:
        """Reconstruct text content from a Textract block and its children."""
        parts: list[str] = []
        for rel in block.get("Relationships", []):
            if rel.get("Type") != "CHILD":
                continue
            for child_id in rel.get("Ids", []):
                child = block_map.get(child_id, {})
                block_type = child.get("BlockType")
                if block_type == "WORD":
                    parts.append(child.get("Text", ""))
                elif (
                    block_type == "SELECTION_ELEMENT"
                    and child.get("SelectionStatus") == "SELECTED"
                ):
                    parts.append("X")
        return " ".join(part for part in parts if part).strip()
