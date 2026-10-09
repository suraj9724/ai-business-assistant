
from database.connection import get_db_connection


def _rows_to_dicts(cursor, rows):
    """Convert PostgreSQL query results into dictionaries."""
    columns = [column.name for column in cursor.description]

    return [
        dict(zip(columns, row))
        for row in rows
    ]


def find_customers_by_name(name: str) -> list[dict]:
    """Find customers whose names match the supplied name."""

    # Parameterized SQL prevents SQL injection.
    query = """
        SELECT id, name, email, tax_id
        FROM customers
        WHERE LOWER(TRIM(name)) = LOWER(TRIM(%s))
        ORDER BY id
    """

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (name,))
            rows = cursor.fetchall()
            return _rows_to_dicts(cursor, rows)


def find_invoices_by_number(invoice_number: str) -> list[dict]:
    """Find invoices matching an invoice number."""

    query = """
        SELECT
            i.id,
            i.invoice_number,
            i.customer_id,
            c.name AS customer_name,
            i.supplier_name,
            i.invoice_date,
            i.currency,
            i.subtotal,
            i.tax,
            i.total,
            i.status
        FROM invoices AS i
        LEFT JOIN customers AS c ON c.id = i.customer_id
        WHERE LOWER(TRIM(i.invoice_number)) =
              LOWER(TRIM(%s))
        ORDER BY i.id
    """

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (invoice_number,))
            rows = cursor.fetchall()
            return _rows_to_dicts(cursor, rows)


def get_invoice_items(invoice_id: int) -> list[dict]:
    """Retrieve all line items belonging to an invoice."""

    query = """
        SELECT
            id,
            invoice_id,
            description,
            quantity,
            unit_price,
            amount
        FROM invoice_items
        WHERE invoice_id = %s
        ORDER BY id
    """

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (invoice_id,))
            rows = cursor.fetchall()
            return _rows_to_dicts(cursor, rows)
