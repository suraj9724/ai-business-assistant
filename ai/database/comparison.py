
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from extraction.schemas import Invoice
from database.queries import (
    find_invoices_by_number,
    get_invoice_items,
)


def normalize_text(value: str | None) -> str | None:
    """Normalize text for case-insensitive comparisons."""
    if value is None:
        return None

    return " ".join(value.strip().casefold().split())


def to_decimal(value) -> Decimal | None:
    """Convert numeric values safely for financial comparisons."""
    if value is None:
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_invoice_date(value):
    """Parse common invoice date formats for comparison."""
    if not value:
        return None

    if isinstance(value, date):
        return value

    formats = (
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d/%m/%Y",
    )

    for date_format in formats:
        try:
            return datetime.strptime(value.strip(), date_format).date()
        except ValueError:
            continue

    return None


def compare_value(field, extracted, stored, errors, warnings):
    """Compare one field without treating missing data as a mismatch."""
    if extracted is None or extracted == "":
        warnings.append(f"{field} is missing from the extracted invoice.")
        return

    if stored is None or stored == "":
        warnings.append(f"{field} is missing from the database record.")
        return

    if normalize_text(str(extracted)) != normalize_text(str(stored)):
        errors.append(
            f"{field} mismatch: extracted '{extracted}', "
            f"database has '{stored}'."
        )


def compare_amount(field, extracted, stored, errors, warnings):
    """Compare monetary values to two decimal places."""
    extracted_value = to_decimal(extracted)
    stored_value = to_decimal(stored)

    if extracted_value is None:
        warnings.append(
            f"{field} is missing or invalid in the extracted invoice."
        )
        return

    if stored_value is None:
        warnings.append(f"{field} is missing in the database record.")
        return

    if extracted_value.quantize(Decimal("0.01")) != stored_value.quantize(
        Decimal("0.01")
    ):
        errors.append(
            f"{field} mismatch: extracted {extracted_value}, "
            f"database has {stored_value}."
        )


def compare_line_items(extracted_items, stored_items):
    """Compare invoice items by normalized description."""
    errors = []
    warnings = []

    # Index stored items by description. Duplicate descriptions are
    # treated as ambiguous instead of silently selecting one.
    stored_by_description = {}

    for item in stored_items:
        key = normalize_text(item["description"])
        stored_by_description.setdefault(key, []).append(item)

    matched_descriptions = set()

    for item in extracted_items:
        key = normalize_text(item.description)
        candidates = stored_by_description.get(key, [])

        if not candidates:
            errors.append(
                f"Line item '{item.description}' was not found "
                "in the database invoice."
            )
            continue

        if len(candidates) > 1:
            warnings.append(
                f"Multiple database line items match '{item.description}'."
            )
            continue

        stored_item = candidates[0]
        matched_descriptions.add(key)

        for field in ("quantity", "unit_price", "amount"):
            extracted_value = to_decimal(getattr(item, field))
            stored_value = to_decimal(stored_item[field])

            if extracted_value is None or stored_value is None:
                warnings.append(
                    f"Cannot compare {field} for '{item.description}': "
                    "a value is missing."
                )
                continue

            if extracted_value != stored_value:
                errors.append(
                    f"Line item '{item.description}' {field} mismatch: "
                    f"extracted {extracted_value}, database has "
                    f"{stored_value}."
                )

    # Report database items absent from the uploaded invoice.
    for key, items in stored_by_description.items():
        if key not in matched_descriptions:
            for item in items:
                if not any(
                    normalize_text(extracted.description) == key
                    for extracted in extracted_items
                ):
                    errors.append(
                        f"Database line item '{item['description']}' "
                        "was not found in the extracted invoice."
                    )

    return errors, warnings


def compare_invoice_with_database(invoice: Invoice) -> dict:
    """Compare an extracted invoice against its database record."""

    if not invoice.invoice_number:
        return {
            "status": "needs_review",
            "invoice_found": False,
            "errors": [],
            "warnings": ["Invoice number is missing; matching is not possible."],
        }

    records = find_invoices_by_number(invoice.invoice_number)

    if not records:
        return {
            "status": "not_found",
            "invoice_found": False,
            "errors": [],
            "warnings": [
                f"Invoice '{invoice.invoice_number}' was not found in the database."
            ],
        }

    if len(records) > 1:
        return {
            "status": "ambiguous",
            "invoice_found": False,
            "errors": [],
            "warnings": [
                "Multiple database invoices have this invoice number. "
                "A unique record must be selected before comparison."
            ],
        }

    stored = records[0]
    errors = []
    warnings = []

    compare_value(
        "Supplier name", invoice.supplier_name,
        stored["supplier_name"], errors, warnings
    )
    compare_value(
        "Customer name", invoice.customer_name,
        stored["customer_name"], errors, warnings
    )
    compare_value(
        "Currency", invoice.currency,
        stored["currency"], errors, warnings
    )

    # Compare dates only when both values can be parsed.
    extracted_date = parse_invoice_date(invoice.invoice_date)
    stored_date = parse_invoice_date(stored["invoice_date"])

    if not invoice.invoice_date:
        warnings.append("Invoice date is missing from the extracted invoice.")
    elif extracted_date is None:
        warnings.append("Extracted invoice date could not be parsed.")
    elif stored_date is None:
        warnings.append("Database invoice date could not be parsed.")
    elif extracted_date != stored_date:
        errors.append(
            f"Invoice date mismatch: extracted {extracted_date}, "
            f"database has {stored_date}."
        )

    for field in ("subtotal", "tax", "total"):
        compare_amount(
            field.capitalize(),
            getattr(invoice, field),
            stored[field],
            errors,
            warnings,
        )

    stored_items = get_invoice_items(stored["id"])
    item_errors, item_warnings = compare_line_items(
        invoice.items, stored_items
    )

    errors.extend(item_errors)
    warnings.extend(item_warnings)

    return {
        "status": "matched" if not errors and not warnings else "needs_review",
        "invoice_found": True,
        "invoice_number": stored["invoice_number"],
        "database_invoice_id": stored["id"],
        "errors": errors,
        "warnings": warnings,
    }
