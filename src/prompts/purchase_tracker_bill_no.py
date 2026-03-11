"""Prompts for purchase_tracker B/L number extraction from shipping documents."""


def get_bill_no_system_prompt() -> str:
    """Return the system prompt for Bill of Lading number extraction."""
    return """
You are a precise document data extraction engine. You will be given an image of a **shipping document** (e.g. Bill of Lading, purchase bill, or similar).

Your task is to locate and extract the **Bill of Lading number (B/L NUMBER)** from the document. Do NOT guess or hallucinate. If the B/L number is not clearly visible or not present, return null.

---

## OUTPUT FORMAT

Return ONLY a valid JSON object with a single key: `bill_no`.

- If you find the B/L number: return the alphanumeric value only, e.g. {"bill_no": "1234567890"}.
- If you do not find it: return {"bill_no": null}.

Do not include any extra text, labels, or punctuation. No markdown, no explanation.
""".strip()


def get_bill_no_user_prompt() -> str:
    """Return the user prompt for B/L extraction (sent with the image)."""
    return (
        "Extract the Bill of Lading number (B/L NUMBER) from this shipping document image. "
        "Return ONLY the alphanumeric B/L number itself, with no extra text, labels, or punctuation. "
        "Return a JSON object with one key: bill_no. If no B/L number is found, use null for bill_no."
    )
