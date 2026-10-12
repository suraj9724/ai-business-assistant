
from decimal import Decimal, InvalidOperation

from extraction.schemas import Invoice


def to_decimal(value) -> Decimal | None:
    """Convert a numeric value safely for financial comparisons."""

    if value is None:
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def validate_invoice(invoice: Invoice) -> dict:
    """
    Validate extracted invoice data without modifying it.

    Returns validation errors and warnings separately so the
    caller can decide whether the invoice needs manual review.
    """

    errors = []
    warnings = []

    # --------------------------------------------------
    # 1. Check important invoice fields.
    # Missing values are warnings because some documents
    # may genuinely omit these fields.
    # --------------------------------------------------

    if not invoice.invoice_number:
        warnings.append("Invoice number is missing.")

    if not invoice.invoice_date:
        warnings.append("Invoice date is missing.")

    if invoice.total is None:
        errors.append("Invoice total is missing.")

    if invoice.subtotal is None:
        warnings.append("Invoice subtotal is missing.")

    if invoice.tax is None:
        warnings.append("Invoice tax is missing.")

    if not invoice.items:
        warnings.append("No invoice line items were extracted.")

    # --------------------------------------------------
    # 2. Validate each line item's arithmetic.
    # We report mismatches rather than correcting amounts.
    # --------------------------------------------------

    for index, item in enumerate(invoice.items, start=1):

        quantity = to_decimal(item.quantity)
        unit_price = to_decimal(item.unit_price)
        amount = to_decimal(item.amount)

        if quantity is None:
            warnings.append(
                f"Item {index}: quantity is missing or invalid."
            )

        if unit_price is None:
            warnings.append(
                f"Item {index}: unit price is missing or invalid."
            )

        if amount is None:
            warnings.append(
                f"Item {index}: amount is missing or invalid."
            )

        # Compare only when all required values are present.
        if (
            quantity is not None
            and unit_price is not None
            and amount is not None
        ):
            expected_amount = quantity * unit_price

            if expected_amount != amount:
                errors.append(
                    f"Item {index} ({item.description}): "
                    f"quantity × unit price is "
                    f"{expected_amount}, but the extracted "
                    f"amount is {amount}."
                )

    # --------------------------------------------------
    # 3. Compare line-item total against subtotal.
    # Do not compare if an item amount is missing.
    # --------------------------------------------------

    if invoice.subtotal is not None and invoice.items:

        amounts = [
            to_decimal(item.amount)
            for item in invoice.items
        ]

        if all(amount is not None for amount in amounts):

            item_total = sum(amounts, Decimal("0"))
            subtotal = to_decimal(invoice.subtotal)

            if item_total != subtotal:
                errors.append(
                    f"Line items total {item_total}, but "
                    f"the extracted subtotal is {subtotal}."
                )

    # --------------------------------------------------
    # 4. Compare subtotal + tax against invoice total.
    # --------------------------------------------------

    if invoice.subtotal is not None and invoice.tax is not None:
        if invoice.total is not None:

            subtotal = to_decimal(invoice.subtotal)
            tax = to_decimal(invoice.tax)
            total = to_decimal(invoice.total)

            if (
                subtotal is not None
                and tax is not None
                and total is not None
                and subtotal + tax != total
            ):
                errors.append(
                    f"Subtotal + tax equals {subtotal + tax}, "
                    f"but the extracted invoice total is {total}."
                )

    # --------------------------------------------------
    # 5. Decide whether the invoice needs manual review.
    # --------------------------------------------------

    
    # An invoice cannot be accepted if required financial data
    # or line-item details are missing or inconsistent.
    needs_review = bool(errors or warnings)

    return {
        "is_valid": not needs_review,
        "status": "needs_review" if needs_review else "accepted",
        "errors": errors,
        "warnings": warnings,
    }

