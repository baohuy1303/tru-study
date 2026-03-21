"""PDF text extraction utilities using pymupdf."""

import pymupdf


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract and clean text from a PDF file on disk."""
    doc = pymupdf.open(pdf_path)
    pages = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text.strip())
    doc.close()
    full_text = "\n\n".join(pages)
    if len(full_text) < 50:
        return ""
    return full_text


def extract_text_from_bytes(pdf_bytes: bytes) -> str:
    """Extract text from in-memory PDF bytes (for downloaded attachments)."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text.strip())
    doc.close()
    full_text = "\n\n".join(pages)
    if len(full_text) < 50:
        return ""
    return full_text
