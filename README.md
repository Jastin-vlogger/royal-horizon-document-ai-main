# Royal Horizon Document AI

Production-ready AI microservice for **key-value extraction** from business documents (Performa Invoice and LPO) using **GPT Vision** via LangChain.

## Features

- **Dual document types**: Performa Invoice and LPO (Foreign Purchase Order) in a single API
- **Formats**: PDF (first page only) and images (jpg, jpeg, png)
- **Vision model**: GPT-4o (configurable) via LangChain + OpenAI
- **Structured JSON** output with optional usage metadata (tokens, cost, latency)
- **Configurable prompts** and validation lists (INCO terms, suppliers)

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
- **Files** (optional but at least one required):
  - `performa_invoice`: Performa Invoice (PDF or image)
  - `lpo_invoice`: LPO document (PDF or image)
- **Form fields** (optional):
  - `inco_terms_list`: JSON array, e.g. `["CIF","FOB","EXWORKS"]`
  - `suppliers`: JSON array, e.g. `["LEKH RAJ","M RAHEEM RICE PROCESSING MILLS"]`

**Response**: Combined JSON with `lpo_invoice`, `performa_invoice`, and `metadata` (tokens, cost, latency).

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
├── src/
│   ├── config/       # logger, settings
│   ├── prompts/      # performa_invoice, lpo_invoice
│   ├── schemas/      # request, response
│   ├── core/         # llm, document_processor, *_business_logics
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
