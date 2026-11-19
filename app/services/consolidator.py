"""Parsing and aggregation logic for Purchase Order markdown documents."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from app.models.purchase_order import (
    ConsolidationResult,
    POLineItem,
    ProductSummary,
    VendorSummary,
)
from app.services.docling_client import DoclingClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_float(value: str) -> float:
    """Strip currency symbols / commas and coerce to float; default 0.0."""
    try:
        return float(re.sub(r"[^\d.\-]", "", value))
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# POParser — converts Docling markdown → list[POLineItem]
# ---------------------------------------------------------------------------

class POParser:
    """Parse a single PO markdown document into a list of line items."""

    # Metadata patterns (case-insensitive, multiline-friendly)
    _RE_PO_NUMBER = re.compile(
        r"PO\s*(?:Number|#|No\.?)\s*[:\-]?\s*([A-Za-z0-9\-]+)",
        re.IGNORECASE,
    )
    _RE_VENDOR = re.compile(
        r"(?:Vendor|Supplier|Sold\s*By|From)\s*[:\-]?\s*([^\n\|]+)",
        re.IGNORECASE,
    )
    _RE_DATE = re.compile(
        r"(?:Date|Order\s*Date|PO\s*Date)\s*[:\-]?\s*(\d{1,4}[\-/]\d{1,2}[\-/]\d{1,4})",
        re.IGNORECASE,
    )

    def parse(self, markdown: str) -> list[POLineItem]:
        """Return a list of `POLineItem` objects extracted from *markdown*."""
        po_number = self._extract_po_number(markdown)
        vendor = self._extract_vendor(markdown)
        date = self._extract_date(markdown)

        line_items: list[POLineItem] = []
        for table_block in self._extract_tables(markdown):
            items = self._parse_table(table_block, po_number, vendor, date)
            line_items.extend(items)

        return line_items

    # ------------------------------------------------------------------
    # Metadata extraction
    # ------------------------------------------------------------------

    def _extract_po_number(self, text: str) -> str:
        m = self._RE_PO_NUMBER.search(text)
        return m.group(1).strip() if m else "UNKNOWN"

    def _extract_vendor(self, text: str) -> str:
        m = self._RE_VENDOR.search(text)
        return m.group(1).strip() if m else "UNKNOWN"

    def _extract_date(self, text: str) -> str:
        m = self._RE_DATE.search(text)
        return m.group(1).strip() if m else ""

    # ------------------------------------------------------------------
    # Table extraction
    # ------------------------------------------------------------------

    def _extract_tables(self, markdown: str) -> list[list[str]]:
        """Split markdown into table blocks (list of row strings per table)."""
        tables: list[list[str]] = []
        current: list[str] = []
        for line in markdown.splitlines():
            stripped = line.strip()
            if stripped.startswith("|"):
                current.append(stripped)
            else:
                if current:
                    tables.append(current)
                    current = []
        if current:
            tables.append(current)
        return tables

    # ------------------------------------------------------------------
    # Row parsing
    # ------------------------------------------------------------------

    def _parse_table(
        self,
        rows: list[str],
        po_number: str,
        vendor: str,
        date: str,
    ) -> list[POLineItem]:
        """Parse a single markdown table block into line items."""
        if len(rows) < 3:  # need header + separator + at least one data row
            return []

        # Find the separator row (contains |---|)
        sep_idx = None
        for i, row in enumerate(rows):
            if re.match(r"^\|[\s\-\|:]+\|$", row):
                sep_idx = i
                break

        if sep_idx is None or sep_idx == 0:
            return []

        # Headers are on the row just before the separator
        headers = self._split_row(rows[sep_idx - 1])
        headers_lower = [h.lower().strip() for h in headers]

        # Column index resolution (flexible column name matching)
        col = self._resolve_columns(headers_lower)
        if col is None:
            return []

        items: list[POLineItem] = []
        for row in rows[sep_idx + 1:]:
            cells = self._split_row(row)
            if len(cells) < len(headers):
                continue

            item_code = cells[col["item_code"]].strip() if col.get("item_code") is not None else ""
            description = cells[col["description"]].strip() if col.get("description") is not None else ""
            qty_str = cells[col["quantity"]].strip() if col.get("quantity") is not None else "0"
            price_str = cells[col["unit_price"]].strip() if col.get("unit_price") is not None else "0"
            total_str = cells[col["line_total"]].strip() if col.get("line_total") is not None else ""

            # Skip summary / total rows
            if re.search(r"total|subtotal|grand", description, re.IGNORECASE):
                continue
            if not description and not item_code:
                continue

            quantity = _to_float(qty_str)
            unit_price = _to_float(price_str)
            line_total = _to_float(total_str) if total_str else quantity * unit_price

            items.append(
                POLineItem(
                    po_number=po_number,
                    vendor=vendor,
                    date=date,
                    item_code=item_code,
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )

        return items

    @staticmethod
    def _split_row(row: str) -> list[str]:
        """Split a markdown table row on `|` delimiters."""
        return [cell.strip() for cell in row.strip("|").split("|")]

    @staticmethod
    def _resolve_columns(headers: list[str]) -> dict[str, int] | None:
        """Map logical column names to positional indices from header list."""
        mapping: dict[str, list[str]] = {
            "item_code": ["item code", "item #", "sku", "code", "part", "part #", "part no", "product code"],
            "description": ["description", "item description", "product", "product name", "name", "details"],
            "quantity": ["quantity", "qty", "units", "amount", "count"],
            "unit_price": ["unit price", "price", "unit cost", "cost", "rate", "unit rate"],
            "line_total": ["line total", "total", "line amount", "amount", "ext. price", "extended price", "subtotal"],
        }

        col: dict[str, int | None] = {}
        for field, aliases in mapping.items():
            col[field] = None
            for alias in aliases:
                for i, h in enumerate(headers):
                    if alias in h:
                        col[field] = i
                        break
                if col[field] is not None:
                    break

        # Must have at least description or item_code, plus quantity or price
        has_item = col.get("item_code") is not None or col.get("description") is not None
        has_price = col.get("quantity") is not None or col.get("unit_price") is not None
        if not (has_item and has_price):
            return None

        return col


# ---------------------------------------------------------------------------
# POConsolidatorService — orchestrates conversion, parsing, and aggregation
# ---------------------------------------------------------------------------

class POConsolidatorService:
    """Accept multiple PDF paths, convert via Docling, parse, and aggregate."""

    def __init__(self, docling_client: DoclingClient | None = None) -> None:
        self._client = docling_client or DoclingClient()
        self._parser = POParser()

    def process(self, pdf_paths: list[Path]) -> ConsolidationResult:
        """Process a list of PDF file paths and return a `ConsolidationResult`."""
        all_items: list[POLineItem] = []

        for path in pdf_paths:
            markdown = self._client.convert(path)
            items = self._parser.parse(markdown)
            all_items.extend(items)

        return self._aggregate(all_items)

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _aggregate(self, items: list[POLineItem]) -> ConsolidationResult:
        if not items:
            return ConsolidationResult()

        df = pd.DataFrame(
            [
                {
                    "po_number": i.po_number,
                    "vendor": i.vendor,
                    "date": i.date,
                    "item_code": i.item_code,
                    "description": i.description,
                    "quantity": i.quantity,
                    "unit_price": i.unit_price,
                    "line_total": i.line_total,
                }
                for i in items
            ]
        )

        # By Vendor
        vendor_grp = df.groupby("vendor").agg(
            total_pos=("po_number", "nunique"),
            total_spend=("line_total", "sum"),
        ).reset_index()
        by_vendor = [
            VendorSummary(
                vendor=row["vendor"],
                total_pos=int(row["total_pos"]),
                total_spend=round(float(row["total_spend"]), 2),
            )
            for _, row in vendor_grp.iterrows()
        ]

        # By Product
        product_grp = df.groupby("item_code").agg(
            description=("description", "first"),
            total_quantity=("quantity", "sum"),
            total_cost=("line_total", "sum"),
        ).reset_index()
        by_product = []
        for _, row in product_grp.iterrows():
            vendors = sorted(
                df[df["item_code"] == row["item_code"]]["vendor"].unique().tolist()
            )
            by_product.append(
                ProductSummary(
                    item_code=row["item_code"],
                    description=row["description"],
                    total_quantity=round(float(row["total_quantity"]), 2),
                    total_cost=round(float(row["total_cost"]), 2),
                    vendors=vendors,
                )
            )

        total_pos = int(df["po_number"].nunique())
        total_vendors = int(df["vendor"].nunique())
        total_spend = round(float(df["line_total"].sum()), 2)

        return ConsolidationResult(
            line_items=items,
            by_vendor=by_vendor,
            by_product=by_product,
            total_pos=total_pos,
            total_vendors=total_vendors,
            total_spend=total_spend,
        )
