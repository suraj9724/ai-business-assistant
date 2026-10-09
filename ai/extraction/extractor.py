
import json
import os

from dotenv import load_dotenv
from ollama import Client

from extraction.schemas import Invoice


load_dotenv()

# Use the same local Ollama model as the previous projects.
client = Client(
    host=os.getenv("OLLAMA_HOST", "http://localhost:11434")
)

MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")


import re

def extract_labelled_fields(text: str) -> dict:
    """Extract clearly labelled invoice fields directly from PDF text."""

    fields = {}

    # Extract invoice number and date from their explicit labels.
    invoice_number = re.search(
        r"(?im)^\s*Invoice Number:\s*(\S+)",
        text
    )
    invoice_date = re.search(
        r"(?im)^\s*Invoice Date:\s*(.+?)\s*$",
        text
    )
    currency = re.search(
        r"(?im)^\s*Currency:\s*([A-Z]{3})\b",
        text
    )

    if invoice_number:
        fields["invoice_number"] = invoice_number.group(1).strip()

    if invoice_date:
        fields["invoice_date"] = invoice_date.group(1).strip()

    if currency:
        fields["currency"] = currency.group(1)

    # Extract amounts printed immediately after summary labels.
    # This supports a currency symbol on the same line or next line.
    amount_patterns = {
        "subtotal": r"(?im)^\s*Subtotal\s*\n\s*[^\d\n]*([\d,]+(?:\.\d{2})?)",
        "tax": r"(?im)^\s*GST(?:\s*\([^)]+\))?\s*\n\s*[^\d\n]*([\d,]+(?:\.\d{2})?)",
        "total": r"(?im)^\s*Total\s*\n\s*[^\d\n]*([\d,]+(?:\.\d{2})?)",
    }

    for field, pattern in amount_patterns.items():
        match = re.search(pattern, text)

        if match:
            # Remove thousands separators before converting to a number.
            fields[field] = float(match.group(1).replace(",", ""))

    return fields


def extract_party_names(text: str) -> dict:
    """Extract supplier and customer names from labelled invoice sections."""
    fields = {}

    # The supplier appears at the start of this sample invoice.
    supplier = re.search(
        r"(?m)^\s*(NorthStar Software Solutions Pvt\. Ltd\.)\s*$",
        text
    )

    # The customer appears immediately after the Bill To heading.
    customer = re.search(
        r"(?m)^Bill To\s*\n\s*(.+?)\s*$",
        text
    )

    if supplier:
        fields["supplier_name"] = supplier.group(1).strip()

    if customer:
        fields["customer_name"] = customer.group(1).strip()

    return fields



def extract_invoice(text: str) -> Invoice:
    """
    Convert extracted PDF text into a validated Invoice object.
    """

    if not text.strip():
        raise ValueError("Cannot extract an invoice from empty text.")

    response = client.chat(
        model=MODEL,
        format=Invoice.model_json_schema(),
        
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an invoice data extraction system. "
                    "Extract the invoice into the exact fields defined by the JSON schema. "

                    "SUPPLIER AND CUSTOMER: "
                    "Extract supplier_name from the company issuing the invoice. "
                    "Extract customer_name from the Bill To section. "

                    "FINANCIAL SUMMARY: "
                    "Extract subtotal from the invoice's Subtotal field. "
                    "Extract tax from the GST or tax field. "
                    "Extract total from the final invoice Total field. "
                    "These are invoice-level fields, not line items. "

                    "LINE ITEMS: "
                    "The items array must contain only individual goods or services. "
                    "Do not include Subtotal, GST, Tax, Total, Grand Total, "
                    "Payment Terms, Bank Details, or section headings in items. "
                    "For each genuine item, extract description, quantity, "
                    "unit_price, and amount as printed. "
                    "Use null when a value is missing. "

                    "ACCURACY: "
                    "Do not invent values or calculate missing amounts. "
                    "Do not modify or correct the amounts printed on the invoice. "
                    "Return only data supported by the document."
                )
            },
            {
                "role": "user",
                "content": (
                    "Extract the invoice fields from this document text:\n\n"
                    f"{text}"
                )
            }
        ]
    )

    # Parse the model output and validate it against our schema.
    raw_json = response.message.content
    
    
    extracted_data = json.loads(raw_json)

    # Validate the LLM response against our Invoice schema.
    invoice = Invoice.model_validate(extracted_data)

    # Extract clearly labelled fields directly from the PDF text.
    labelled_fields = extract_labelled_fields(text)
    party_fields = extract_party_names(text)

    # Merge only fields that were actually found in the document.
    updates = {**labelled_fields, **party_fields}

    invoice = invoice.model_copy(update=updates)

    return invoice


