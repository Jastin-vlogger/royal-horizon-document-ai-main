# Royal Horizon Document AI

Production-ready AI microservice for **key-value extraction** from business documents (LPO and Rice Quality Report) using **GPT Vision** via LangChain.

## Features

- **Shipment bundle**: LPO and Rice Quality Report in one classified + extracted flow
- **Automated calculations**: FCL, quantity in MT, pallets, pricing per container and per MT
- **Commodity normalization**: Extensible commodity type handling (rice, sugar)
- **Formats**: PDF (first page only) and images (jpg, jpeg, png)
- **Vision model**: GPT-4o (configurable) via LangChain + OpenAI
- **Structured JSON** output with optional usage metadata (tokens, cost, latency)

## Tech stack

- Python ≥3.10, <3.13
- Poetry, FastAPI, Pydantic, Loguru
- LangChain OpenAI (vision), PyMuPDF, Pillow

## Setup

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY and any overrides

poetry install
poetry run start
```

Server runs at `http://0.0.0.0:8000` (configurable via `PORT` / `HOST`).

## API

### `POST /shipment-form`

- **Content-Type**: `multipart/form-data`
- **Files** (both required):
  - `lpo_invoice`: LPO (PDF or image)
  - `rice_quality_report`: Rice Quality Report (PDF or image)
- **Form fields** (optional):
  - `inco_terms_list`: JSON array, e.g. `["CIF","FOB","EXWORKS"]` (defaults internally to `["CIF","FOB","EXWORKS","C&F"]` when omitted or empty)
  - `suppliers`: JSON array, e.g. `["LEKH RAJ","M RAHEEM RICE PROCESSING MILLS"]` (used to guide vendor/inco matching in the LPO extraction prompt)

**Flow**: A classification pass runs on both documents (PDFs: first page only). If `is_valid_document` is false, the API returns **422** with a structured `detail` object (`error`, `reason`, flags, and `classified_data`). On success, LPO and Rice Quality extractions run in parallel, followed by automated shipment calculations.

**Response**: 
- `lpo_invoice`: Extracted LPO fields including UOM-derived `buying_unit` (e.g. `BAG` from `BAGS/1*40KG`), Terms & Conditions (`inco_terms`, `payment_terms`, `quality`, `vat`, `total_amount`)
- `shipment_calculations`: Automated logistics calculations (container_size, quantity_in_mt, fcl, bags, bags_per_container, pallets, fcl_per_unit, price_per_mt)
- `classified_data`: Full classifier JSON with validation flags
- `s1_quality_report`: Full rice-quality JSON
- `metadata`: Cumulative tokens, cost, and latency summed across all LLM calls

**Shipment Calculations**: The system automatically calculates:
- Container size based on commodity type (rice → 20ft)
- Quantity in metric tons from bags and packaging weight
- FCL (Full Container Load) - number of containers needed
- Bags per container and total pallets
- Pricing per container (FCL per unit) and per metric ton

See [docs/SHIPMENT_CALCULATIONS.md](docs/SHIPMENT_CALCULATIONS.md) for detailed calculation formulas and examples.

### `POST /arrival-notice/extract`

- **Content-Type**: `multipart/form-data`
- **File** (required):
  - `file`: Arrival notice or related shipping document — **PDF** (all pages are rasterized and sent to the model) or **image** (`jpg`, `jpeg`, `png`).

**Flow**: Each PDF page becomes a PNG at 150 DPI; images are normalized to PNG. A single vision call sends all page images with the system prompt from `src/prompts/arrival_notice.py` (`arrival_notice_system_prompt`). The model must return JSON with exactly `arrival_on` and `free_retension_days`; the service validates strictly (ISO date `YYYY-MM-DD` or null; free time as `"N days"` or null).

**Response** example shape:

```json
{
  "arrival_on": "2026-03-03",
  "free_retension_days": "14 days",
  "metadata": {
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0,
    "cost_incurred": 0.0,
    "cost_currency": "USD",
    "latency_ms": 0.0,
    "model": "gpt-4o"
  }
}
```

**Errors**: `400` for missing/invalid file type or unreadable PDF/image; `502` if the model output is not valid JSON or fails Pydantic validation; `500` for unexpected server errors. If `arrival_notice_system_prompt` is left empty after stripping whitespace, the handler returns `503` with a configuration message.

## Configuration (.env)

| Variable        | Description           | Default  |
|----------------|-----------------------|----------|
| OPENAI_API_KEY | OpenAI API key        | (required) |
| MODEL_TO_USE   | Vision model          | gpt-4o   |
| TEMPERATURE    | LLM temperature       | 0.0      |
| MAX_TOKENS     | Max response tokens   | 4096     |
| PORT           | Server port           | 8000     |
| HOST           | Bind host             | 0.0.0.0  |
| RETRY          | Retry count (future)  | 3        |
| LOG_LEVEL      | Log level             | INFO     |

## Project structure

```
royal-horizon-document-ai/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── docs/
│   └── SHIPMENT_CALCULATIONS.md  # Calculation formulas guide
├── src/
│   ├── config/       # logger, settings
│   ├── prompts/      # lpo_invoice, shipment_classification
│   ├── schemas/      # request, response
│   ├── core/         # llm, document_processor, *_business_logics, commodity_normalizer
│   ├── routes/       # apis
│   ├── utils/        # cost_calculator
│   └── main.py
└── tests/
```

## Docker

```bash
docker compose build
docker compose up
```

## Tests

```bash
poetry run pytest tests/ -v
```
