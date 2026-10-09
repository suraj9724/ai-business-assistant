
from pydantic import BaseModel, Field


class InvoiceItem(BaseModel):
    # Details for an individual invoice line.
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None


class Invoice(BaseModel):
    # Extracted invoice fields. Optional fields accommodate
    # invoices where some information is missing.
    invoice_number: str | None = None
    invoice_date: str | None = None

    supplier_name: str | None = None
    customer_name: str | None = None

    currency: str | None = None

    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None

    items: list[InvoiceItem] = Field(default_factory=list)
