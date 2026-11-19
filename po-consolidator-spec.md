# Purchase Order Consolidator — Technical Specification

> Methodology: Spec-Driven Development (SDD)
> Scope: Greenfield Python/Flask SaaS-connected web app. Stateless. No persistent storage. No Docker.

---

## 1. Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Browser Client                    │
│  Page 1: Upload (drag-and-drop)                     │
│  Page 2: Results (stat cards + 3 tables + CSV)      │
└───────────────┬─────────────────────────────────────┘
                │ HTTP multipart/form-data (POST /api/process)
                │ HTTP GET /api/export/csv
                ▼
┌─────────────────────────────────────────────────────┐
│               Flask Application Server               │
│  ┌──────────────┐   ┌───────────────────────────┐   │
│  │   Routes     │──▶│   POConsolidatorService    │   │
│  │  (views.py)  │   │  (consolidator.py)         │   │
│  └──────────────┘   └──────────┬────────────────┘   │
│                                 │                    │
│                     ┌───────────▼──────────┐         │
│                     │   DoclingClient       │         │
│                     │  (docling_client.py)  │         │
│                     └───────────┬──────────┘         │
└─────────────────────────────────│───────────────────┘
                                  │ HTTPS (DoclingServiceClient)
                                  ▼
                   ┌──────────────────────────────┐
                   │  Docling watsonx SaaS API     │
                   │  → Markdown document output   │
                   └──────────────────────────────┘
```

---

## 2. Tech Stack

| Layer | Choice | Version / Notes |
|---|---|---|
| Runtime | Python | 3.11+ |
| Web framework | Flask | 3.x |
| PDF parsing | Docling SaaS | `docling>=2.95.0` via `DoclingServiceClient` |
| Data processing | pandas | `>=2.2.0` |
| UI framework | IBM Carbon Design System | CDN-linked (`@carbon/styles`, `carbon-components`) |
| Config | python-dotenv | `.env` for `SERVICE_URL`, `API_KEY`, `PORT` |
| Testing | pytest | Integration test against real Docling SaaS |
| Environment | Python `venv` | No Docker |

---

## 3. Directory Structure

```
docling-saas-purchase-order/
├── app/
│   ├── __init__.py              # Flask app factory (create_app)
│   ├── config.py                # Config class — reads .env
│   ├── routes/
│   │   ├── __init__.py
│   │   └── views.py             # URL rules: GET /, POST /api/process, GET /api/export/csv
│   ├── services/
│   │   ├── __init__.py
│   │   ├── docling_client.py    # Thin wrapper around DoclingServiceClient
│   │   └── consolidator.py     # Parsing + aggregation logic (POConsolidatorService)
│   ├── models/
│   │   ├── __init__.py
│   │   └── purchase_order.py    # Dataclasses: POLineItem, VendorSummary, ProductSummary
│   └── templates/
│       ├── base.html            # Carbon shell + shared head (CDN links)
│       ├── upload.html          # Page 1 — drag-and-drop upload
│       └── results.html         # Page 2 — stat cards + 3 data tables
├── static/
│   └── js/
│       └── upload.js            # Drag-and-drop, fetch POST, render results page
├── tests/
│   ├── __init__.py
│   └── test_integration.py      # Integration test using sample/PO_10001_Acme.pdf
├── sample/
│   └── PO_10001_Acme.pdf
├── .env                         # SERVICE_URL, API_KEY, PORT (gitignored)
├── .env.example                 # Template with placeholder values
├── requirements.txt
├── run.py                       # Entry point: app.run(port=config.PORT)
└── requirements-intent.md
```

---

## 4. Core Data Models

Defined in [`app/models/purchase_order.py`](app/models/purchase_order.py).

### 4.1 `POLineItem` (dataclass)

```
po_number     : str       # e.g. "PO-10001"
vendor        : str       # Supplier name
date          : str       # ISO date string
item_code     : str       # SKU / product code
description   : str       # Item description
quantity      : float
unit_price    : float
line_total    : float     # quantity * unit_price
```

### 4.2 `VendorSummary` (dataclass)

```
vendor        : str
total_pos     : int       # count of distinct PO numbers
total_spend   : float
```

### 4.3 `ProductSummary` (dataclass)

```
item_code     : str
description   : str
total_quantity: float
total_cost    : float
vendors       : list[str] # distinct vendor sources
```

### 4.4 `ConsolidationResult` (dataclass)

```
line_items    : list[POLineItem]
by_vendor     : list[VendorSummary]
by_product    : list[ProductSummary]
total_pos     : int
total_vendors : int
total_spend   : float
```

---

## 5. API Endpoints

### `POST /api/process`

**Purpose:** Accept one or more PO PDF files, convert each via Docling SaaS, parse, and consolidate.

| Field | Detail |
|---|---|
| Content-Type | `multipart/form-data` |
| Input key | `files[]` — one or more `.pdf` files |
| Response | `application/json` — serialised `ConsolidationResult` |
| Error | `400` for non-PDF or missing files; `502` for Docling API failure |

**Processing flow per file:**
1. Save upload to a temp file.
2. Call `DoclingServiceClient.convert(source=Path(tmp))` → markdown string.
3. Parse markdown with `POParser` (regex-based, handles multiline metadata and table separators).
4. Accumulate `POLineItem` list.

**Aggregation (pandas):**
- Group by `vendor` → `VendorSummary`.
- Group by `item_code` → `ProductSummary`.
- Compute global totals.

---

### `GET /api/export/csv`

**Purpose:** Return the last-processed line items as a downloadable CSV.

| Field | Detail |
|---|---|
| Input | Session-scoped result passed as JSON body or query param `data` (base64-encoded) |
| Response | `text/csv`, `Content-Disposition: attachment; filename=purchase_orders.csv` |
| Columns | po_number, vendor, date, item_code, description, quantity, unit_price, line_total |

> **Note:** Since the service is stateless, the client posts the `line_items` JSON back to the export endpoint, which converts to CSV server-side using `pandas.DataFrame.to_csv()`.

---

### `GET /`

Serves the Upload page (`upload.html`).

---

## 6. Parsing Strategy

Implemented in `consolidator.py` → `POParser.parse(markdown: str) -> list[POLineItem]`.

- **Metadata block** (PO number, vendor, date): flexible multiline regex, e.g. `r"PO\s*(?:Number|#|No\.?)\s*[:\-]?\s*(\S+)"` (case-insensitive).
- **Table headers**: captured before separator lines (`|---|`), not after.
- **Line items**: iterate rows after header separator; skip empty or total rows.
- **Numeric coercion**: strip `$`, `,`; cast to `float`; default to `0.0` on failure.

---

## 7. UI Design Constraints (Carbon Design System)

| Page | Key Elements |
|---|---|
| Upload | Blue-to-purple gradient hero header; `cds--file-uploader` drag-and-drop zone; feature cards (`cds--tile`) |
| Results | Gradient hero; stat cards with purple/green/magenta/blue left-border accents; three `cds--data-table` panels (All Line Items, By Vendor, By Product); color-coded `cds--tag` for PO numbers and vendors; CSV export button |

Carbon loaded via CDN (`unpkg.com`). No build step required.

---

## 8. Configuration (`.env`)

```
SERVICE_URL=https://api.aws-c1.dcls.saas.ibm.com/20260519-2040-0213-6007-20006a73b966
API_KEY=your-api-key-here
PORT=5000
```

Loaded in [`app/config.py`](app/config.py) via `python-dotenv`.

---

## 9. Integration Test

File: [`tests/test_integration.py`](tests/test_integration.py)

- Requires valid `API_KEY` in `.env` (user must fill before running).
- Uploads `sample/PO_10001_Acme.pdf` via `POST /api/process`.
- Assertions:
  - Response status `200`.
  - `line_items` list is non-empty.
  - Each `POLineItem` has non-empty `po_number`, `vendor`, positive `line_total`.
  - `by_vendor` and `by_product` aggregations are present.

---

## 10. `requirements.txt` (pinned minimums)

```
flask>=3.0.0
python-dotenv>=1.0.0
docling>=2.95.0
pandas>=2.2.0
pytest>=8.0.0
```
