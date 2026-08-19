"""Document extraction: turns an uploaded file into searchable chunks"""

import re
import uuid

import pandas as pd
import pdfplumber
import pytesseract
from PIL import Image

from app import db


def chunk_text(text: str, max_chars: int = 800) -> list[str]:
    """Split a text into chunks of about max_chars, cutting at sentence boundaries"""

    text = text.strip()
    if not text:
        return []

    # Split after . ! or ? so a quote is never cut in the middle of an idea
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""

    # Fill the current chunk until the next sentence would make it too long
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                chunks.append(current)
            current = sentence

    # The loop leaves the last chunk unflushed
    if current:
        chunks.append(current)

    return chunks


def extract_pdf(file_path: str) -> list[dict]:
    """Extract a PDF page by page, keeping the page number for citations"""

    results = []
    with pdfplumber.open(file_path) as pdf:
        # start=1 because readers count pages from one, not from zero
        for page_number, page in enumerate(pdf.pages, start=1):
            # A page with only images returns None, not an empty string
            page_text = page.extract_text() or ""
            page_chunks = chunk_text(page_text)
            for position, chunk_content in enumerate(page_chunks):
                results.append(
                    {
                        "content": chunk_content,
                        "page_number": page_number,
                        "position": position,
                    }
                )
    return results


def extract_csv(file_path: str) -> list[dict]:
    """Extract a CSV row by row, one row being one unit of meaning"""

    df = pd.read_csv(file_path)
    results = []

    # No sentence splitting here: a spreadsheet row is already self contained
    for position, row in df.iterrows():
        # Keep the column names so the chunk stays readable out of context
        row_text = "; ".join(f"{col}: {val}" for col, val in row.items())
        if row_text.strip():
            results.append(
                {
                    "content": row_text,
                    # A CSV has no page, position carries the row number instead
                    "page_number": None,
                    "position": int(position),
                }
            )
    return results


def extract_note(file_path: str) -> list[dict]:
    """Extract a plain text note, same chunking as a PDF but without pages"""

    # errors="replace" keeps a badly encoded file readable instead of crashing
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    chunks = chunk_text(text)
    return [
        {"content": c, "page_number": None, "position": position}
        for position, c in enumerate(chunks)
    ]


def extract_image(file_path: str) -> list[dict]:
    """Extract text from a screenshot through local OCR"""

    # Tesseract runs locally and free, consistent with choosing FTS5 over a cloud service
    try:
        text = pytesseract.image_to_string(Image.open(file_path), lang="fra")
    except pytesseract.TesseractError as exc:
        # The French language pack is a system package, pip cannot install it
        if "fra" in str(exc):
            raise RuntimeError(
                "Pack de langue française Tesseract manquant sur cette machine "
                "(sudo apt install tesseract-ocr-fra)."
            ) from exc
        raise

    # An image yields a single indexable passage, no precise highlight inside it
    chunks = chunk_text(text)
    return [
        {"content": c, "page_number": None, "position": position}
        for position, c in enumerate(chunks)
    ]


# One extractor per extension, all returning the same chunk shape
EXTRACTORS = {
    "pdf": extract_pdf,
    "csv": extract_csv,
    "txt": extract_note,
    "md": extract_note,
    "png": extract_image,
    "jpg": extract_image,
    "jpeg": extract_image,
}


def process_document(document_id: str, file_path: str, file_type: str) -> None:
    """Run the right extractor and set the final document status"""

    extractor = EXTRACTORS.get(file_type)

    try:
        # Unknown extension: fail explicitly rather than silently ignoring the file
        if extractor is None:
            db.update_document_status(
                document_id, "error", f"Type de fichier non supporté pour l'instant : {file_type}"
            )
            return

        extracted = extractor(file_path)

        # A readable file can still hold no text, a scanned PDF for instance
        if not extracted:
            db.update_document_status(
                document_id, "error", "Aucun texte extrait (document vide ou illisible)."
            )
            return

        # Each chunk gets its own id, the FTS5 index is filled by a trigger
        for chunk in extracted:
            chunk_id = f"c_{uuid.uuid4().hex[:8]}"
            db.insert_chunk(
                chunk_id,
                document_id,
                chunk["content"],
                page_number=chunk["page_number"],
                position=chunk["position"],
            )

        db.update_document_status(document_id, "processed")

    except Exception as exc:
        # Never leave a document stuck on "processing": a corrupted file turns
        # into an explicit error without breaking the rest of the upload
        db.update_document_status(document_id, "error", str(exc))
