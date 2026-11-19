# Docling SaaS Purchase Order Consolidator

A Flask web application that uses the **IBM Docling SaaS API** to extract and consolidate data from PDF purchase-order documents.

---

## Features

- Upload one or more PDF purchase orders
- Extracts line-item data via the Docling document-intelligence API
- Consolidates results into a unified view (HTML table + downloadable Excel)
- Simple, dependency-light Flask backend

---

## Project Structure

```
.
├── app/
│   ├── __init__.py          # Flask application factory
│   ├── config.py            # Environment-based configuration
│   ├── models/              # Data models
│   ├── routes/views.py      # HTTP routes
│   ├── services/            # Docling client & consolidator logic
│   └── templates/           # Jinja2 HTML templates
├── static/js/               # Front-end JavaScript
├── tests/                   # Pytest integration tests
├── sample/                  # Sample PDF for manual testing
├── run.py                   # App entry point
├── requirements.txt         # Python dependencies
├── Procfile                 # Process declaration (Heroku / Render)
└── .env.example             # Template for required environment variables
```

---

## Quick Start (local)

### 1. Clone & create a virtual environment

```bash
git clone https://github.com/mohammadalfreijat-jbs/Docling_purchase_order.git
cd Docling_purchase_order
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Then edit .env and fill in your SERVICE_URL and API_KEY
```

| Variable      | Description                              |
|---------------|------------------------------------------|
| `SERVICE_URL` | IBM Docling SaaS endpoint URL            |
| `API_KEY`     | Base64-encoded IBM Docling API key       |
| `PORT`        | Port the Flask server listens on (default `5000`) |

### 4. Run the application

```bash
python run.py
```

Open your browser at `http://localhost:5000`.

---

## Running Tests

```bash
pytest tests/
```

---

## Deployment

### Heroku / Render / Railway

1. Set the environment variables (`SERVICE_URL`, `API_KEY`, `PORT`) in your platform's dashboard — **never commit `.env`**.
2. The `Procfile` already declares the web process:
   ```
   web: python run.py
   ```
3. Push to the platform's git remote as instructed by that provider.

### Environment Variables (production)

Set these in your hosting platform's secrets/environment settings:

```
SERVICE_URL=<your-docling-saas-endpoint>
API_KEY=<your-base64-encoded-api-key>
PORT=5000
```

---

## Security Notes

- `.env` is listed in `.gitignore` and will **never** be committed.
- Use `.env.example` as a reference — it contains placeholder values only.
- Rotate your API key immediately if it is ever accidentally exposed.

---

## License

MIT
