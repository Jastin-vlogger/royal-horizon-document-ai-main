"""LLM pricing helpers used for metadata cost estimates."""

from typing import Dict


def get_pricing_table() -> Dict[str, Dict[str, float]]:
    """Return per-1M-token pricing table by model."""

    return {
        "gpt-5": {"input": 1.25, "output": 10.00},
        "gpt-5.1": {"input": 1.25, "output": 10.00},
        "gpt-5.2": {"input": 1.75, "output": 14.00},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.150, "output": 0.600},
        "gpt-4o-mini-2024-07-18": {"input": 0.150, "output": 0.600},
        "gpt-4": {"input": 30.00, "output": 60.00},
    }


def _normalize_model(model: str) -> str:
    if not model:
        return "gpt-4o"
    model_lower = model.lower()
    if "gpt-5.2" in model_lower:
        return "gpt-5.2"
    if "gpt-5.1" in model_lower:
        return "gpt-5.1"
    if "gpt-5" in model_lower:
        return "gpt-5"
    if "gpt-4o-mini" in model_lower:
        return "gpt-4o-mini"
    if "gpt-4o" in model_lower:
        return "gpt-4o"
    if "gpt-4" in model_lower:
        return "gpt-4"
    return model


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate approximate USD cost for token usage."""

    pricing = get_pricing_table().get(_normalize_model(model))
    if pricing is None:
        return 0.0
    cost = (input_tokens / 1_000_000.0) * pricing["input"]
    cost += (output_tokens / 1_000_000.0) * pricing["output"]
    return round(cost, 6)
