"""
Pydantic models for invoice schema and validation.
"""
from typing import Optional
from pydantic import BaseModel


class InvoiceData(BaseModel):
    """Structured invoice data with all required fields."""

    seller_name: Optional[str] = None
    seller_tax_id: Optional[str] = None
    client_name: Optional[str] = None
    client_tax_id: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    net_worth: Optional[float] = None
    vat: Optional[float] = None
    gross_worth: Optional[float] = None

    def to_dict(self) -> dict:
        """Return as dict with consistent keys for CSV/output."""
        return {
            "seller_name": self.seller_name,
            "seller_tax_id": self.seller_tax_id,
            "client_name": self.client_name,
            "client_tax_id": self.client_tax_id,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "net_worth": self.net_worth,
            "vat": self.vat,
            "gross_worth": self.gross_worth,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InvoiceData":
        """Build from dict, tolerating extra keys."""
        allowed = {
            "seller_name", "seller_tax_id", "client_name", "client_tax_id",
            "invoice_number", "invoice_date", "net_worth", "vat", "gross_worth",
        }
        filtered = {k: v for k, v in data.items() if k in allowed}
        return cls(**filtered)
