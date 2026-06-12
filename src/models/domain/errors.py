"""Domain exceptions used for router HTTP mapping."""

from typing import Any


class DomainValidationError(Exception):
    """Input failed domain validation."""


class LLMOutputError(Exception):
    """LLM output could not be parsed or validated."""


class ConfigurationError(Exception):
    """Required configuration or prompt is missing."""


class WorkflowExecutionError(Exception):
    """Workflow failed unexpectedly."""


class ShipmentClassificationError(Exception):
    """Shipment document classification failed with a structured detail payload."""

    def __init__(self, classified_data: dict[str, Any]) -> None:
        self.classified_data = classified_data
        super().__init__(str(classified_data.get("reason", "")))
