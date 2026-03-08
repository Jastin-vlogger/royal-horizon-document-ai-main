"""Cost calculation for OpenAI model usage (per 1M tokens)."""

from typing import Dict

# Source: OpenAI pricing page (prices in USD per 1M tokens)
PRICING_TABLE: Dict[str, Dict[str, float]] = {
    "gpt-5": {"input": 1.25, "output": 10.00},
    "gpt-5.1": {"input": 1.25, "output": 10.00},
    "gpt-5.2": {"input": 1.75, "output": 14.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.150, "output": 0.600},
    "gpt-4o-mini-2024-07-18": {"input": 0.150, "output": 0.600},
    "gpt-4": {"input": 30.00, "output": 60.00},
}


def get_pricing_table() -> Dict[str, Dict[str, float]]:
    """Return the pricing table (for external use)."""
    return dict(PRICING_TABLE)


def _normalize_model(model: str) -> str:
    """Map common model names to pricing table keys."""
    m = (model or "").strip().lower()
    if not m:
        return "gpt-4o"
    if "gpt-5.2" in m:
        return "gpt-5.2"
    if "gpt-5.1" in m:
        return "gpt-5.1"
    if "gpt-5" in m:
        return "gpt-5"
    if "gpt-4o-mini" in m:
        return "gpt-4o-mini"
    if "gpt-4o" in m:
        return "gpt-4o"
    if "gpt-4" in m:
        return "gpt-4"
    return model


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """
    Compute cost in USD for given token counts.
    Prices are per 1M tokens; amounts are in dollars.
    """
    key = _normalize_model(model)
    pricing = PRICING_TABLE.get(key)
    if not pricing:
        return 0.0
    input_cost = (input_tokens / 1_000_000.0) * pricing["input"]
    output_cost = (output_tokens / 1_000_000.0) * pricing["output"]
    return round(input_cost + output_cost, 6)
