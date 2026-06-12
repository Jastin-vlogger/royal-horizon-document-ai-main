"""Pydantic schemas for POST /arrival-notice/extract."""

import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.models.api.response import ExtractionMetadata

_ARRIVAL_ON_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FREE_DAYS_RE = re.compile(r"^(\d+)\s*", re.IGNORECASE)


class ArrivalNoticeLLMOutput(BaseModel):
    """
    Strict shape of JSON returned by the model (only keys: print_date, arrival_on, free_retension_days).
    Values are ISO date string, \"N days\" string, or null.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    print_date: Optional[str] = Field(default=None, description="YYYY-MM-DD or null.")
    arrival_on: Optional[str] = Field(default=None, description="YYYY-MM-DD or null.")
    free_retension_days: Optional[str] = Field(
        default=None,
        description='Combined free time as "N days" or null (key spelling matches LLM contract).',
    )

    @field_validator("print_date", mode="before")
    @classmethod
    def _validate_print_date(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("print_date must be a string or null")
        s = v.strip()
        if not s or s.lower() == "null":
            return None
        if not _ARRIVAL_ON_RE.match(s):
            raise ValueError("print_date must match YYYY-MM-DD")
        return s

    @field_validator("arrival_on", mode="before")
    @classmethod
    def _validate_arrival_on(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("arrival_on must be a string or null")
        s = v.strip()
        if not s or s.lower() == "null":
            return None
        if not _ARRIVAL_ON_RE.match(s):
            raise ValueError("arrival_on must match YYYY-MM-DD")
        return s

    @field_validator("free_retension_days", mode="before")
    @classmethod
    def _validate_free_days(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("free_retension_days must be a string or null")
        s = v.strip()
        if not s or s.lower() == "null":
            return None
        m = _FREE_DAYS_RE.match(s)
        if not m:
            raise ValueError('free_retension_days must match "<integer> days"')
        return f"{int(m.group(1))} days"


class ArrivalNoticeExtractResponse(BaseModel):
    """API response: extracted fields plus usage metadata from the vision call."""

    print_date: Optional[str] = None
    arrival_on: Optional[str] = None
    free_retension_days: Optional[str] = None
    metadata: ExtractionMetadata
