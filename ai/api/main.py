import os
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile

from documents.pdf_processor import extract_pdf_text

from extraction.extractor import extract_invoice
from extraction.validator import validate_invoice

from database.connection import get_db_connection
from database.comparison import compare_invoice_with_database

app = FastAPI(title="AI Business Assistant")

# Limit uploads to 10 MB for this initial milestone.
MAX_FILE_SIZE = 10 * 1024 * 1024



@app.get("/api/db/health")
def database_health():
    """Verify that the API can connect to PostgreSQL."""

    try:
        # Open and close the connection safely.
        with get_db_connection() as conn:
            result = conn.execute(
                "SELECT current_database()"
            ).fetchone()

        return {
            "connected": True,
            "database": result[0]
        }

    except Exception:
        # Avoid exposing database credentials or internal errors.
        raise HTTPException(
            status_code=503,
            detail="Database connection failed."
        )



@app.post("/api/documents/extract")
async def extract_document(file: UploadFile = File(...)):
    # Only accept PDF uploads.
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF file.",
        )

    # Read the upload and enforce the size limit.
    content = await file.read(MAX_FILE_SIZE + 1)

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="The PDF must be 10 MB or smaller.",
        )

    # Use a temporary file so the uploaded document isn't
    # permanently stored on disk in this first version.
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False,
        ) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        result = extract_pdf_text(temp_path)

        # Reject PDFs that contain no extractable text.
        if not result["full_text"]:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No extractable text found. "
                    "The PDF may be scanned or image-based."
                ),
            )

        return result

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to process this PDF: {exc}",
        ) from exc

    finally:
        # Always remove the temporary file, including on errors.
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)



@app.post("/api/documents/extract-invoice")
async def extract_invoice_endpoint(file: UploadFile = File(...)):
    # Reuse the existing PDF extraction logic.
    # Save the uploaded file temporarily, then extract its text.
    content = await file.read(MAX_FILE_SIZE + 1)

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF file.",
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="The PDF must be 10 MB or smaller.",
        )

    temp_path = None
    
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False,
        ) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        document = extract_pdf_text(temp_path)

        if not document["full_text"]:
            raise HTTPException(
                status_code=422,
                detail="No extractable text found in this PDF.",
            )
            
        # Temporary debugging: inspect the exact text extracted from the PDF.
        print("===== EXTRACTED PDF TEXT =====")
        print(document["full_text"])
        print("===== END PDF TEXT =====")

        # Ask the LLM to extract invoice fields from the text.
        invoice = extract_invoice(document["full_text"])

        # Check the extracted data without silently modifying it.
        validation = validate_invoice(invoice)

        return {
            "page_count": document["page_count"],
            "invoice": invoice.model_dump(),
            "validation": validation,
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Invoice extraction failed: {exc}",
        ) from exc

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)



@app.post("/api/documents/compare-invoice")
async def compare_uploaded_invoice(file: UploadFile = File(...)):
    """Extract, validate, and compare an uploaded invoice with PostgreSQL."""

    # Accept PDF files only.
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=415,
            detail="Only PDF files are supported."
        )

    temp_path = None

    try:
        # Read at most 10 MB plus one byte to detect oversized uploads.
        content = await file.read(MAX_FILE_SIZE + 1)

        if not content:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty."
            )

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="The PDF exceeds the 10 MB limit."
            )

        # Save temporarily because the PDF processor reads from a file path.
        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False
        ) as temp_file:
            temp_path = temp_file.name
            temp_file.write(content)

        # Step 1: Extract text from the PDF.
        document = extract_pdf_text(temp_path)

        if not document["full_text"].strip():
            raise HTTPException(
                status_code=422,
                detail="No readable text was found in the PDF."
            )

        # Step 2: Extract structured invoice data.
        invoice = extract_invoice(document["full_text"])

        # Step 3: Validate the extracted invoice independently.
        validation = validate_invoice(invoice)

       
        # Step 4: Compare extracted values with database records.
        comparison = compare_invoice_with_database(invoice)

        # Step 5: Determine the overall outcome.
        # Accept an invoice only when validation passes and the database
        # comparison is a complete match.
        overall_status = (
            "accepted"
            if validation["status"] == "accepted"
            and comparison["status"] == "matched"
            else "needs_review"
        )

        # Return the overall decision plus detailed diagnostic results.
        return {
            "page_count": document["page_count"],
            "overall_status": overall_status,
            "validation_status": validation["status"],
            "comparison_status": comparison["status"],
            "invoice": invoice.model_dump(mode="json"),
            "validation": validation,
            "comparison": comparison,
        }


    except HTTPException:
        # Preserve intentional HTTP errors raised above.
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc)
        ) from exc

    finally:
        # Always remove the temporary file, including on failure.
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

        await file.close()
