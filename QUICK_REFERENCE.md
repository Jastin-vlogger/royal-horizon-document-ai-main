# Quick Reference: Shipment Form API

## API Endpoint

```
POST /shipment-form
```

## Request

### Required Files (multipart/form-data)
- `lpo_invoice` - LPO document (PDF or image)
- `rice_quality_report` - Rice Quality Report (PDF or image)

### Optional Form Fields
- `inco_terms_list` - JSON array of allowed INCO terms (injected into LPO extraction; default list used if omitted)
- `suppliers` - JSON array of supplier names (injected into LPO extraction for vendor matching)

### Example cURL
```bash
curl -X POST http://localhost:8000/shipment-form \
  -F "lpo_invoice=@lpo.pdf" \
  -F "rice_quality_report=@rice_report.pdf" \
  -F 'inco_terms_list=["CIF","FOB","EXWORKS","C&F"]' \
  -F 'suppliers=["LEKH RAJ NARINDER KUMAR"]'
```

### Example Python
```python
import requests

files = {
    'lpo_invoice': open('lpo.pdf', 'rb'),
    'rice_quality_report': open('rice_report.pdf', 'rb')
}
data = {
    'inco_terms_list': '["CIF","FOB","EXWORKS","C&F"]',
    'suppliers': '["LEKH RAJ NARINDER KUMAR"]',
}

response = requests.post(
    'http://localhost:8000/shipment-form',
    files=files,
    data=data,
)

result = response.json()
```

## Response Structure

```json
{
  "lpo_invoice": {
    "po_number": "PO01/26/00117",
    "po_date": "2026-01-13",
    "vendor": "LEKH RAJ NARINDER KUMAR",
    "item_code": "1-RH1-01B-0050",
    "commodity": "rice",
    "item": "PR11 Steam Rice - Indian Pride - 40kg",
    "quantity_in_bags": "15,000.00",
    "unit": "22.40",
    "price": "336,000.00",
    "buying_unit": "BAG",
    "packaging": "1X40KG",
    "inco_terms": "CIF JABEL ALI UAE",
    "payment_terms": "100 % CAD Bank to Bank",
    "vat": "0.00",
    "total_amount": "336,000.00",
    "quality": "Indian PR11 Steam rice LG 90%,SG 5%...",
    "port_of_loading": null,
    "port_of_discharge": null,
    "pi_number": null,
    "pi_date": null
  },
  "shipment_calculations": {
    "container_size": 20,
    "quantity_in_mt": 600.0,
    "fcl": 24,
    "bags": 15000,
    "bags_per_container": 625,
    "pallets": 300,
    "fcl_per_unit": 14000.0,
    "price_per_mt": 560.0
  },
  "classified_data": {
    "is_valid_document": true,
    "has_lpo": true,
    "has_ricequality_doc": true,
    "reason": "Valid LPO and Rice Quality Report detected"
  },
  "s1_quality_report": {
    "report_no": "...",
    "moisture": "...",
    "...": "..."
  },
  "metadata": {
    "input_tokens": 5000,
    "output_tokens": 500,
    "total_tokens": 5500,
    "cost_incurred": 0.025,
    "cost_currency": "USD",
    "latency_ms": 4500,
    "model": "gpt-4o"
  }
}
```

## Shipment Calculations Fields

| Field | Description | Example |
|-------|-------------|---------|
| `container_size` | Container type in feet | 20 |
| `quantity_in_mt` | Total weight in metric tons | 600.0 |
| `fcl` | Number of containers needed | 24 |
| `bags` | Total number of bags | 15000 |
| `bags_per_container` | Bags per container | 625 |
| `pallets` | Number of pallets | 300 |
| `fcl_per_unit` | Price per container | 14000.0 |
| `price_per_mt` | Price per metric ton | 560.0 |

## Calculation Formulas

### Quantity in MT
```
quantity_in_mt = (quantity_in_bags × kg_per_bag) / 1000
```

### FCL (Containers)
```
fcl = ceil(quantity_in_mt / 25)  // for 20ft
fcl = ceil(quantity_in_mt / 26)  // for 40ft
```

### Bags per Container
```
bags_per_container = (container_capacity_mt × 1000) / kg_per_bag
```

### Pallets
```
pallets = ceil(total_bags / 50)
```

### FCL per Unit
```
fcl_per_unit = bags_per_container × price_per_bag
```

### Price per MT
```
price_per_mt = price_per_bag × (1000 / kg_per_bag)
```

## Error Responses

### 400 - Bad Request
Missing files or invalid file types
```json
{
  "detail": "Both files are required: lpo_invoice, rice_quality_report"
}
```

### 422 - Classification Failed
Documents don't match expected types
```json
{
  "detail": {
    "error": "document_classification_failed",
    "reason": "Missing LPO document",
    "has_lpo": false,
    "has_ricequality_doc": true,
    "is_valid_document": false,
    "classified_data": { ... }
  }
}
```

### 500 - Extraction Failed
LLM extraction or processing error
```json
{
  "detail": "Document extraction failed: ..."
}
```

## Commodity Types

Currently supported:
- `rice` → 20ft container
- `sugar` → 20ft container

Extensible for future commodities in `src/core/commodity_normalizer.py`.

## Performance

- **Average response time**: 4-5 seconds
- **LLM calls**: 2 (classification + parallel extraction)
- **Optimization**: Parallel image processing and extraction

## Development

### Run Tests
```bash
poetry run pytest tests/ -v
```

### Start Server
```bash
poetry run start
```

### Check Logs
```bash
tail -f logs/app.log
```

## Documentation

- **Calculation Guide**: [docs/SHIPMENT_CALCULATIONS.md](docs/SHIPMENT_CALCULATIONS.md)
- **Migration Guide**: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- **Implementation Details**: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- **API Docs**: [README.md](README.md)
