# Royal Horizon Document AI

Layered FastAPI service for document extraction workflows across shipment forms,
arrival notices, bank advice documents, cost sheets, purchase tracker documents,
tax invoices, and stock sheets.

## Features

- Multipart upload APIs with the same public paths and response shapes as the previous service.
- Direct async request/response execution; no background job queue in V1.
- Replaceable LLM provider boundary through `LLMBrokerInterface`.
- AWS Textract isolated behind `TextractBroker` using `boto3`.
- Prompts and API defaults loaded from YAML under `config/`.
- All Pydantic models live under `src/models`; there is no live `src/schemas` package.

## Setup

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY and any AWS Textract settings needed for stock-sheet OCR.

poetry install
poetry run start
```

Server runs at `http://0.0.0.0:8000` by default.

## API Documentation

Interactive Swagger docs are available at `/docs` when the service is running.

Detailed endpoint documentation lives under `docs/{api_endpoint_name}/api_docs.md`:

| API | Endpoint | Documentation |
| --- | --- | --- |
| Shipment Form | `POST /shipment-form` | [docs/shipment-form/api_docs.md](docs/shipment-form/api_docs.md) |
| Arrival Notice Extract | `POST /arrival-notice/extract` | [docs/arrival-notice-extract/api_docs.md](docs/arrival-notice-extract/api_docs.md) |
| Bank Advice Is Signed | `POST /bank-advice-doc/is-signed` | [docs/bank-advice-is-signed/api_docs.md](docs/bank-advice-is-signed/api_docs.md) |
| BOE Extract | `POST /boe/extract` | [docs/boe-extract/api_docs.md](docs/boe-extract/api_docs.md) |
| Costsheet Is Signed | `POST /costsheet/is-signed` | [docs/costsheet-is-signed/api_docs.md](docs/costsheet-is-signed/api_docs.md) |
| Purchase Tracker Fetch Details | `POST /purchase-tracker/fetch-details` | [docs/purchase-tracker-fetch-details/api_docs.md](docs/purchase-tracker-fetch-details/api_docs.md) |
| Stock Sheet Extract | `POST /extract/stock-sheet` | [docs/stock-sheet-extract/api_docs.md](docs/stock-sheet-extract/api_docs.md) |
| Tax Invoice Extraction | `POST /tax_invoice_extraction` | [docs/tax-invoice-extraction/api_docs.md](docs/tax-invoice-extraction/api_docs.md) |

Each API doc includes:

- V1 requirement notes and future requirement slots.
- Endpoint, headers, parameters, request schema, and response schema.
- Sample cURL commands and JSON responses.
- E2E workflow explanation with Mermaid diagrams.
- Swagger/OpenAPI details.

## Configuration

- `.env`: secrets and environment overrides.
- `config/settings.yml`: app defaults, model/provider settings, AWS settings, stock-sheet limits.
- `config/apis/*.yml`: per-API defaults such as page limits and default INCO terms.
- `config/prompts/*.yml`: prompt text and prompt templates.

Important environment variables are listed in `.env.example`.

## Architecture

```text
routers -> dispatchers -> coordination -> orchestration -> processing -> foundation -> brokers
```

- `src/routers`: FastAPI decorators, file/form declarations, HTTP error mapping.
- `src/dispatchers`: convert uploads and form values into internal command models.
- `src/coordination`: high-level workflow entrypoint for future multi-orchestrator coordination.
- `src/orchestration`: workflow sequencing and cross-step decisions.
- `src/processing`: pure parsing, validation, normalization, calculations, and table transforms.
- `src/foundation`: domain-focused wrappers around low-level providers.
- `src/brokers`: OpenAI/LangChain, Textract, PDF/image rendering, and YAML config integrations.
- `src/models`: all Pydantic API, domain, LLM, and common models.
- `src/containers`: Dependency Injector wiring.

`OLD_CODE/` is retained only as a reference copy of the previous implementation.

## Supporting Docs

- [Developer basics](docs/devs/basic.md)
- [LLM token consumption and metadata](docs/devs/llm_token_consumption.md)
- [Shipment form calculation logic](docs/shipment-form/calculation_logic.md)
- [Shipment calculations reference](doc-mds/SHIPMENT_CALCULATIONS.md)
- [Quick reference](doc-mds/QUICK_REFERENCE.md)

`doc-mds/` contains legacy/reference documentation from the previous project structure. New API-specific and developer documentation should go under `docs/`.

## Tests

```bash
poetry run pytest -q
```
