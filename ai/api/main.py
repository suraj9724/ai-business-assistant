import os
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile

from documents.pdf_processor import extract_pdf_text


app = FastAPI(title="AI Business Assistant")

# Limit uploads to 10 MB for this initial milestone.
MAX_FILE_SIZE = 10 * 1024 * 1024


@app.get("/health")
def health_check():
    return {"status": "ok"}


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
