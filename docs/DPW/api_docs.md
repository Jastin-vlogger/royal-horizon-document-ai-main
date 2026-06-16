# DPW Cargo Extractor API

Extracts receipt date, receipt number, container references, and per-container storage date ranges from a DP World cargo receipt PDF.

## V1_REQUIREMENT

- Accept one uploaded PDF as `file`.
- Validate PDF page count before rendering or model extraction.
- Use the configured `dpw_cargo.pdf_max_pages` value from `config/apis/document_defaults.yml`.
- Default configured PDF page limit is `10`.
- Use the dedicated `config/prompts/dpw_cargo.yml` prompt.
- Render valid PDF pages once and send optimized header/container crops in one vision call.
- Return a flat response containing extracted fields, per-container date ranges, LLM metadata, and `error`.
- On errors, keep all extraction fields and metadata as `null`, and populate `error`.

## Endpoint

POST `/dpw-cargo-extractor`

## Description

This endpoint reads DPW cargo receipt PDFs and extracts:

- `date`: receipt header `Date`, normalized to `DD/MM/YYYY`.
- `containers`: all valid container values shown after `Container` labels in charge rows, with their storage `from` and `to` dates.
- `receipt_no`: receipt header `Receipt No`, or visible BOL/B/L reference if used as the receipt reference.
- `total_containers`: count of unique normalized containers.
- `pages_processed`: number of rendered PDF pages actually processed.

The workflow does not infer missing values. If a field is absent or unreadable, the field is returned as `null`, except `containers`, which returns an empty list on successful extraction.

## Headers

| Header | Required | Value |
| --- | --- | --- |
| `Content-Type` | Yes | `multipart/form-data` |

## API Parameters

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `file` | form file | PDF | Yes | DPW cargo receipt PDF. PDFs must not exceed the configured page limit. |

## E2E Workflow

1. Router accepts the uploaded PDF.
2. Dispatcher reads the upload into `SingleDocumentCommand`.
3. Orchestrator validates that the file is a PDF.
4. Orchestrator reads PDF page count and rejects files over `dpw_cargo.pdf_max_pages`.
5. Document foundation renders valid PDF pages to PNG.
6. Processing builds compact header and charge-description crops to reduce vision payload size.
7. Prompt foundation loads `dpw_cargo.yml`.
8. LLM foundation runs one multi-image vision extraction call.
9. Processing parses strict JSON, normalizes date/receipt/container/date-range values, removes duplicate containers, and sets `pages_processed`.
10. Router returns the flat DPW response or a contract-shaped error body.

```mermaid
flowchart TD
    A["Client POST /dpw-cargo-extractor"] --> B["Router"]
    B --> C["Dispatcher: UploadFile to DocumentInput"]
    C --> D["Orchestrator: PDF validation"]
    D --> E["PDF page count <= dpw_cargo.pdf_max_pages"]
    E --> F["Document Foundation: pages to PNG"]
    F --> G["Processing: header and container crops"]
    G --> H["Prompt Foundation: dpw_cargo.yml"]
    H --> I["LLM Foundation: vision call"]
    I --> J["Processing: parse, normalize dates, dedupe"]
    J --> K["DpwCargoExtractorResponse"]
```

## Request Schema

```text
multipart/form-data

file: binary PDF file, required
```

## Success Response Schema

```json
{
  "date": "DD/MM/YYYY|null",
  "containers": [
    {
      "container": "string",
      "from": "DD/MM/YYYY|null",
      "to": "DD/MM/YYYY|null"
    }
  ],
  "total_containers": 0,
  "pages_processed": 0,
  "receipt_no": "string|null",
  "metadata": {
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0,
    "cost_incurred": 0.0,
    "cost_currency": "USD",
    "latency_ms": 0.0,
    "model": "gpt-4o"
  },
  "error": null
}
```

## Example Request

```bash
curl -X 'POST' \
  'http://localhost:8005/dpw-cargo-extractor' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@DPW PAYMENT-1.pdf;type=application/pdf'
```

## Example Response

```json
{
  "date": "08/06/2026",
  "containers": [
    {
      "container": "BSIU314828",
      "from": "24/05/2026",
      "to": "08/06/2026"
    },
    {
      "container": "DPWU200491",
      "from": "29/05/2026",
      "to": "11/06/2026"
    },
    {
      "container": "DPWU201512",
      "from": "24/05/2026",
      "to": "08/06/2026"
    }
  ],
  "total_containers": 3,
  "pages_processed": 6,
  "receipt_no": "56710421",
  "metadata": {
    "input_tokens": 1800,
    "output_tokens": 120,
    "total_tokens": 1920,
    "cost_incurred": 0.00384,
    "cost_currency": "USD",
    "latency_ms": 3200.5,
    "model": "gpt-4o"
  },
  "error": null
}
```

## Empty Extraction Response

```json
{
  "date": null,
  "containers": [],
  "total_containers": 0,
  "pages_processed": 1,
  "receipt_no": null,
  "metadata": {
    "input_tokens": 500,
    "output_tokens": 30,
    "total_tokens": 530,
    "cost_incurred": 0.0018,
    "cost_currency": "USD",
    "latency_ms": 1300.0,
    "model": "gpt-4o"
  },
  "error": null
}
```

## Error Response

Status: `400`, `502`, `503`, or `500` depending on the failure.

```json
{
  "date": null,
  "containers": null,
  "total_containers": null,
  "pages_processed": null,
  "receipt_no": null,
  "metadata": null,
  "error": "PDF exceeds maximum allowed pages"
}
```

## Real example:

- curl
```
curl -X 'POST' \
  'http://localhost:8000/dpw-cargo-extractor' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@DPW PAYMENT-1 BL-MUNKLF26139815.pdf;type=application/pdf'

```

- Response

```

{
  "date": "08/06/2026",
  "containers": [
    {"container": "BSIU314828", "from": "24/05/2026", "to": "08/06/2026"},
    {"container": "DPWU200491", "from": "29/05/2026", "to": "11/06/2026"},
    {"container": "DPWU201512", "from": "24/05/2026", "to": "08/06/2026"},
    {"container": "DPWU202048", "from": "22/05/2026", "to": "08/06/2026"},
    {"container": "DPWU202277", "from": "24/05/2026", "to": "08/06/2026"},
    {"container": "DPWU202406", "from": "22/05/2026", "to": "08/06/2026"},
    {"container": "DPWU203386", "from": "23/05/2026", "to": "08/06/2026"},
    {"container": "DPWU207991", "from": "24/05/2026", "to": "08/06/2026"},
    {"container": "DPWU212177", "from": "26/05/2026", "to": "08/06/2026"},
    {"container": "DPWU213015", "from": "24/05/2026", "to": "08/06/2026"},
    {"container": "DPWU214023", "from": "22/05/2026", "to": "08/06/2026"},
    {"container": "DPWU214845", "from": "26/05/2026", "to": "08/06/2026"},
    {"container": "DPWU215663", "from": "23/05/2026", "to": "08/06/2026"},
    {"container": "DPWU216085", "from": "29/05/2026", "to": "11/06/2026"},
    {"container": "DPWU216268", "from": "27/05/2026", "to": "09/06/2026"},
    {"container": "DPWU221602", "from": "27/05/2026", "to": "09/06/2026"},
    {"container": "DRYU286212", "from": "23/05/2026", "to": "08/06/2026"},
    {"container": "FYCU723869", "from": "22/05/2026", "to": "08/06/2026"},
    {"container": "FYCU724060", "from": "24/05/2026", "to": "08/06/2026"},
    {"container": "FYCU724092", "from": "25/05/2026", "to": "08/06/2026"},
    {"container": "LEGU201592", "from": "26/05/2026", "to": "08/06/2026"},
    {"container": "LEGU201628", "from": "23/05/2026", "to": "08/06/2026"},
    {"container": "LEGU201822", "from": "23/05/2026", "to": "08/06/2026"},
    {"container": "LEGU202374", "from": "24/05/2026", "to": "08/06/2026"},
    {"container": "LEGU202423", "from": "29/05/2026", "to": "11/06/2026"},
    {"container": "LEGU203017", "from": "24/05/2026", "to": "08/06/2026"},
    {"container": "LEGU203212", "from": "23/05/2026", "to": "08/06/2026"},
    {"container": "LEGU203363", "from": "22/05/2026", "to": "08/06/2026"},
    {"container": "LEGU203387", "from": "23/05/2026", "to": "08/06/2026"},
    {"container": "LEGU203446", "from": "22/05/2026", "to": "08/06/2026"},
    {"container": "LEGU203458", "from": "22/05/2026", "to": "08/06/2026"},
    {"container": "LEGU203716", "from": "23/05/2026", "to": "08/06/2026"},
    {"container": "LEGU203786", "from": "22/05/2026", "to": "08/06/2026"},
    {"container": "LEGU203920", "from": "24/05/2026", "to": "08/06/2026"},
    {"container": "SEGU234612", "from": "23/05/2026", "to": "08/06/2026"},
    {"container": "SEGU397342", "from": "22/05/2026", "to": "08/06/2026"},
    {"container": "SEKU113029", "from": "22/05/2026", "to": "08/06/2026"},
    {"container": "TIIU234250", "from": "22/05/2026", "to": "08/06/2026"},
    {"container": "TLLU361240", "from": "24/05/2026", "to": "08/06/2026"}
  ],
  "total_containers": 39,
  "pages_processed": 6,
  "receipt_no": "56710421",
  "metadata": {
    "input_tokens": 8283,
    "output_tokens": 219,
    "total_tokens": 8502,
    "cost_incurred": 0.017561,
    "cost_currency": "USD",
    "latency_ms": 8050.89,
    "model": "gpt-5.2"
  },
  "error": null
}
```

## Extraction Rules

### date

- Use the header field labelled `Date`.
- Accept values with time, such as `08/06/2026 13:30`.
- Return only the date in `DD/MM/YYYY`.
- Do not use `Arr Date`, storage date ranges, payment dates, footer dates, or due dates.
- Return `null` if the receipt date is absent or unreadable.

### containers

- Extract values directly after visible `Container` labels in charge-description rows.
- For each container, extract the closest following storage date range in the form `from <date> to <date>`.
- Return each item as an object with `container`, `from`, and `to`.
- Process all pages in document order.
- Trim whitespace and remove spaces/hyphens inside container values.
- Normalize to uppercase.
- Normalize `from` and `to` dates to `DD/MM/YYYY`.
- If a container is visible but its storage date range is unreadable, set `from` and `to` to `null`.
- Accept four letters followed by six or seven digits.
- Remove duplicates while preserving first-seen order.
- Do not extract `CONTAINERS TaxCode` text as a container number.
- Return `[]` if no valid containers are found.

### receipt_no

- Prefer the header field labelled `Receipt No`.
- If `Receipt No` is blank and a BOL/B/L reference is visibly used as the receipt reference, return that value.
- Do not use `DO No`, `B/E No`, `Transaction Id`, `Rotation`, `TRN`, customer reference, or page numbers.
- Trim whitespace and remove line breaks inside the value.
- Return `null` if no receipt reference is visible.

## Error Responses

| Status | When | Shape |
| --- | --- | --- |
| `400` | Missing file, unsupported type, unreadable PDF, PDF over page limit | `DpwCargoExtractorResponse` with `error` populated |
| `502` | LLM JSON is invalid or fails schema validation | `DpwCargoExtractorResponse` with `error` populated |
| `503` | Required prompt/config is missing | `DpwCargoExtractorResponse` with `error` populated |
| `500` | Unexpected workflow failure | `DpwCargoExtractorResponse` with `error` populated |

## Swagger Docs Details

Open Swagger UI at `/docs`.

Swagger should show:

- Tag: `dpw-cargo`
- Method: `POST`
- Path: `/dpw-cargo-extractor`
- Summary: `Extract date, receipt number, and containers from a DPW cargo receipt PDF`
- Request body: `multipart/form-data`
- Response model: `DpwCargoExtractorResponse`
- File field: `file`

## Future Requirement Slots

### V2_REQUIREMENT

Add here if the API later needs invoice totals, payment details, B/E number, DO number, vessel, rotation, customer information, or line-level charge extraction.
