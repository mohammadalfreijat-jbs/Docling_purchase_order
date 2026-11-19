"""Integration test for the PO Consolidator using the real Docling SaaS API.

Before running:
  1. Copy .env.example to .env and fill in your API_KEY.
  2. Activate the virtual environment.
  3. Run:  pytest tests/test_integration.py -v
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load .env before the skip guard evaluates API_KEY
load_dotenv()

# ---------------------------------------------------------------------------
# Guard: skip if API_KEY is not set
# ---------------------------------------------------------------------------

SAMPLE_PDF = Path(__file__).parent.parent / "sample" / "PO_10001_Acme.pdf"

API_KEY = os.environ.get("API_KEY", "")
SKIP_REASON = "API_KEY not set in environment / .env — fill in .env before running integration tests."


@pytest.fixture(scope="module")
def flask_client():
    """Return a Flask test client with the app in test mode."""
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.mark.skipif(not API_KEY, reason=SKIP_REASON)
def test_process_sample_pdf(flask_client):
    """Upload the sample PO PDF and assert the consolidated result is valid."""
    assert SAMPLE_PDF.exists(), f"Sample PDF not found: {SAMPLE_PDF}"

    with open(SAMPLE_PDF, "rb") as f:
        response = flask_client.post(
            "/api/process",
            data={"files[]": (f, "PO_10001_Acme.pdf")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.data}"

    data = response.get_json()
    assert data is not None

    # line_items must be non-empty
    line_items = data.get("line_items", [])
    assert len(line_items) > 0, "Expected at least one line item"

    # Each line item must have required fields
    for item in line_items:
        assert item.get("po_number"), f"po_number is empty in item: {item}"
        assert item.get("vendor"), f"vendor is empty in item: {item}"
        assert item.get("line_total", 0) > 0, f"line_total is not positive in item: {item}"

    # Aggregations must be present
    by_vendor = data.get("by_vendor", [])
    assert len(by_vendor) > 0, "Expected at least one vendor summary"

    by_product = data.get("by_product", [])
    assert len(by_product) > 0, "Expected at least one product summary"

    # Global stats
    assert data.get("total_pos", 0) > 0
    assert data.get("total_vendors", 0) > 0
    assert data.get("total_spend", 0) > 0


@pytest.mark.skipif(not API_KEY, reason=SKIP_REASON)
def test_export_csv(flask_client):
    """After processing, the CSV export should return valid CSV content."""
    assert SAMPLE_PDF.exists()

    with open(SAMPLE_PDF, "rb") as f:
        process_resp = flask_client.post(
            "/api/process",
            data={"files[]": (f, "PO_10001_Acme.pdf")},
            content_type="multipart/form-data",
        )
    assert process_resp.status_code == 200
    result = process_resp.get_json()

    export_resp = flask_client.post(
        "/api/export/csv",
        data=json.dumps({"line_items": result["line_items"]}),
        content_type="application/json",
    )
    assert export_resp.status_code == 200
    assert export_resp.content_type == "text/csv; charset=utf-8"

    csv_text = export_resp.data.decode("utf-8")
    lines = [l for l in csv_text.splitlines() if l.strip()]
    # Header + at least one data row
    assert len(lines) >= 2, "CSV should have at least a header and one data row"
    assert "po_number" in lines[0]
