"""URL rules: GET /, POST /api/process, GET /api/export/csv."""

from __future__ import annotations

import io
import tempfile
from dataclasses import asdict
from pathlib import Path

import pandas as pd
from flask import Blueprint, Response, jsonify, render_template, request

from app.services.consolidator import POConsolidatorService

bp = Blueprint("views", __name__)
_service = POConsolidatorService()


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@bp.get("/")
def upload_page():
    return render_template("upload.html")


@bp.get("/results")
def results_page():
    return render_template("results.html")


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@bp.post("/api/process")
def process():
    """Accept one or more PO PDF files and return consolidated JSON."""
    files = request.files.getlist("files[]")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "No files uploaded."}), 400

    pdf_paths: list[Path] = []
    tmp_paths: list[Path] = []

    try:
        for f in files:
            if not f.filename.lower().endswith(".pdf"):
                return jsonify({"error": f"File '{f.filename}' is not a PDF."}), 400

            # Use delete=False and close immediately so Docling (and Windows)
            # can open the file without a sharing-violation.
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                f.save(tmp.name)
                tmp_paths.append(Path(tmp.name))

        pdf_paths = list(tmp_paths)

        try:
            result = _service.process(pdf_paths)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502

        return jsonify(asdict(result))

    finally:
        for p in tmp_paths:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass  # Windows: file still locked — will be cleaned by OS on exit


@bp.post("/api/export/csv")
def export_csv():
    """Convert posted line_items JSON back to a downloadable CSV."""
    body = request.get_json(silent=True) or {}
    line_items = body.get("line_items", [])

    if not line_items:
        return jsonify({"error": "No line items provided."}), 400

    columns = [
        "po_number",
        "vendor",
        "date",
        "item_code",
        "description",
        "quantity",
        "unit_price",
        "line_total",
    ]
    df = pd.DataFrame(line_items, columns=columns)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_content = csv_buffer.getvalue()

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=purchase_orders.csv"
        },
    )
