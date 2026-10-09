from pypdf import PdfReader


def extract_pdf_text(file_path: str) -> dict:
    """
    Extract text from each page of a PDF.

    Keeping page numbers helps us later provide page citations
    when answering questions about the uploaded document.
    """

    reader = PdfReader(file_path)

    # Reject encrypted PDFs that cannot be read without a password.
    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported.")

    pages = []

    # Extract each page separately so we retain page references.
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        pages.append({
            "page": page_number,
            "text": text.strip(),
        })

    # Return structured data instead of one large text string.
    return {
        "page_count": len(pages),
        "pages": pages,
        "full_text": "\n\n".join(
            page["text"] for page in pages
        ),
    }
