# Developer Basics

This guide explains how to set up, run, debug, and test the Royal Horizon Document AI service locally.

## Requirements

- Python `>=3.10,<3.15`
- Poetry
- Docker, optional
- Poppler installed locally if you run PDF conversion outside Docker
- OpenAI API key for LLM-backed endpoints
- AWS credentials for stock-sheet Textract OCR

## 1. Clone And Open The Project

```bash
cd royal-horizon-document-ai-main
```

The active application code lives under `src/`.

`OLD_CODE/` is only a reference copy of the previous implementation.

## 2. Create Environment File

```bash
cp .env.example .env
```

Edit `.env` and set values as needed:

```bash
OPENAI_API_KEY=sk-your-key-here
MODEL_TO_USE=gpt-4o
TEMPERATURE=0.0
MAX_TOKENS=4096
LLM_PROVIDER=langchain_openai
LLM_TIMEOUT_SECONDS=120

PORT=8000
HOST=0.0.0.0
RETRY=3
LOG_LEVEL=INFO

AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=

STOCK_SHEET_PDF_MAX_PAGES=3
STOCK_SHEET_MAX_IMAGE_PIXELS=25000000
STOCK_SHEET_ENABLE_PREPROCESS=true
STOCK_SHEET_LLM_BATCH_SIZE=60
```

## 3. Install Dependencies

```bash
poetry install
```

## 4. Run The App

```bash
poetry run start
```

The service starts at:

```text
http://localhost:8000
```

Swagger UI:

```text
http://localhost:8000/docs
```

OpenAPI JSON:

```text
http://localhost:8000/openapi.json
```

## 5. Run With Uvicorn Directly

```bash
poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

## 6. Run Tests

```bash
poetry run pytest -q
```

Run one test file:

```bash
poetry run pytest tests/test_stock_sheet_api.py -q
```

Run one test by name:

```bash
poetry run pytest -q -k "shipment_form"
```

## 7. Docker Run

```bash
docker compose build
docker compose up
```

The container maps `${PORT:-8000}` to container port `8000`.

## 8. VS Code Launch Config

Create this file at `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Royal Horizon Document AI",
      "type": "debugpy",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "src.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload"
      ],
      "console": "integratedTerminal",
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      },
      "justMyCode": true
    }
  ]
}
```

## 9. Project Layout

```text
src/
  routers/        FastAPI route declarations and HTTP error mapping
  dispatchers/    Upload/form parsing into command models
  coordination/   High-level workflow coordination
  orchestration/  Workflow sequencing
  processing/     Pure business logic and transformations
  foundation/     Domain wrappers around brokers
  brokers/        LLM, Textract, rendering, prompt/config integrations
  containers/     Dependency Injector wiring
  models/         All Pydantic API, domain, common, and LLM models
```

Dependency direction:

```text
routers -> dispatchers -> coordination -> orchestration -> processing -> foundation -> brokers
```

## 10. Where To Edit Prompts And Config

Prompts:

```text
config/prompts/*.yml
```

API defaults:

```text
config/apis/*.yml
```

App settings:

```text
config/settings.yml
```

Secrets and environment overrides:

```text
.env
```

## 11. API Docs

Each endpoint has detailed documentation under:

```text
docs/{api_endpoint_name}/api_docs.md
```

Start with:

- `docs/shipment-form/api_docs.md`
- `docs/arrival-notice-extract/api_docs.md`
- `docs/bank-advice-is-signed/api_docs.md`
- `docs/costsheet-is-signed/api_docs.md`
- `docs/purchase-tracker-fetch-details/api_docs.md`
- `docs/stock-sheet-extract/api_docs.md`
- `docs/tax-invoice-extraction/api_docs.md`

## 12. Developer Concept Docs

- `docs/devs/llm_token_consumption.md`: how LLM token usage, latency, and cost metadata are captured.
- `docs/shipment-form/calculation_logic.md`: how shipment calculations work with real project examples.
