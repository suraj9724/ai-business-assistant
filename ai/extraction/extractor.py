
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
    """Extract clearly labelled invoice fields from PDF text."""

    fields = {}

    # Match a label and its value whether they appear on the same
    # line or on separate lines.
    def get_label_value(label_pattern: str):
        pattern = (
            rf"(?im)^\s*(?:{label_pattern})\s*:?\s*"
            rf"(?:\n\s*)?([^\n]+?)\s*$"
        )
        match = re.search(pattern, text)
        return match.group(1).strip() if match else None

    # Invoice number
    invoice_number = get_label_value(r"Invoice Number")
    if invoice_number:
        fields["invoice_number"] = invoice_number

    # Invoice date
    invoice_date = get_label_value(r"Invoice Date")
    if invoice_date:
        fields["invoice_date"] = invoice_date

    # Currency
    currency_value = get_label_value(r"Currency")
    if currency_value:
        currency_match = re.search(r"\b([A-Z]{3})\b", currency_value)
        if currency_match:
            fields["currency"] = currency_match.group(1)

    # Extract amounts from the line following each summary label.
    amount_patterns = {
        "subtotal": (
            r"(?im)^\s*Subtotal\s*:?\s*\n\s*"
            r"(?:INR|USD|EUR|GBP|₹|\$)?\s*"
            r"([\d,]+(?:\.\d{2})?)\s*$"
        ),
        "tax": (
            r"(?im)^\s*GST(?:\s*\([^)]+\))?\s*:?\s*\n\s*"
            r"(?:INR|USD|EUR|GBP|₹|\$)?\s*"
            r"([\d,]+(?:\.\d{2})?)\s*$"
        ),
        "total": (
            r"(?im)^\s*Total(?:\s+Amount)?\s*:?\s*\n\s*"
            r"(?:INR|USD|EUR|GBP|₹|\$)?\s*"
            r"([\d,]+(?:\.\d{2})?)\s*$"
        ),
    }

    for field, pattern in amount_patterns.items():
        match = re.search(pattern, text)
        if match:
            fields[field] = float(match.group(1).replace(",", ""))

    return fields



def extract_line_items(text: str) -> list[dict]:
    """Extract line items from a clearly structured PDF text table."""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    items = []

    def parse_number(value: str):
        """Convert a printed number into a float, or return None."""
        value = re.sub(r"^(INR|USD|EUR|GBP|₹|\$)\s*", "", value.strip())
        value = value.replace(",", "")

        if not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
            return None

        return float(value)

    i = 0

    while i < len(lines):
        # A standalone integer may indicate the item row number.
        if not re.fullmatch(r"\d+", lines[i]):
            i += 1
            continue

        description_index = i + 1

        # We need a description followed by quantity, unit price,
        # and amount. Skip headings or incomplete rows.
        if description_index >= len(lines):
            break

        description = lines[description_index]

        # Skip a row if its description is actually a number.
        if parse_number(description) is not None:
            i += 1
            continue

        numeric_values = []
        j = description_index + 1

        while j < len(lines) and len(numeric_values) < 3:
            number = parse_number(lines[j])

            if number is None:
                break

            numeric_values.append(number)
            j += 1

        if len(numeric_values) == 3:
            quantity, unit_price, amount = numeric_values

            items.append({
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "amount": amount,
            })

            i = j
        else:
            i += 1

    return items



def extract_party_names(text: str) -> dict:
    """Extract supplier and customer names from invoice text."""

    fields = {}
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # The supplier is the company name near the beginning,
    # before the TAX INVOICE heading.
    for i, line in enumerate(lines):
        if re.search(r"\bTAX\s+INVOICE\b", line, re.IGNORECASE):
            if i > 0:
                candidate = lines[i - 1]
                if not re.search(
                    r"invoice|bill|date|number",
                    candidate,
                    re.IGNORECASE,
                ):
                    fields["supplier_name"] = candidate
            break

    # The customer appears after the Bill To heading.
    for i, line in enumerate(lines):
        if re.fullmatch(r"Bill To\s*:?", line, re.IGNORECASE):
            if i + 1 < len(lines):
                fields["customer_name"] = lines[i + 1]
            break

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

    
    # Extract clearly labelled fields directly from PDF text.
    labelled_fields = extract_labelled_fields(text)
    party_fields = extract_party_names(text)

    # Prefer deterministic line items when the PDF table is readable.
    # Otherwise, retain the items extracted by the LLM.
    parsed_items = extract_line_items(text)

    updates = {**labelled_fields, **party_fields}

    if parsed_items:
        updates["items"] = parsed_items

    # Revalidate the merged data, including nested invoice items.
    invoice_data = invoice.model_dump()
    invoice_data.update(updates)

    invoice = Invoice.model_validate(invoice_data)

    return invoice


