"""Data models for Purchase Order consolidation."""

from dataclasses import dataclass, field


@dataclass
class POLineItem:
    po_number: str
    vendor: str
    date: str
    item_code: str
    description: str
    quantity: float
    unit_price: float
    line_total: float


@dataclass
class VendorSummary:
    vendor: str
    total_pos: int
    total_spend: float


@dataclass
class ProductSummary:
    item_code: str
    description: str
    total_quantity: float
    total_cost: float
    vendors: list[str] = field(default_factory=list)


@dataclass
class ConsolidationResult:
    line_items: list[POLineItem] = field(default_factory=list)
    by_vendor: list[VendorSummary] = field(default_factory=list)
    by_product: list[ProductSummary] = field(default_factory=list)
    total_pos: int = 0
    total_vendors: int = 0
    total_spend: float = 0.0
