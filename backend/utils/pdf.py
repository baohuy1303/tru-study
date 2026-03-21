"""PDF text extraction utilities using pymupdf."""

import pymupdf


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract and clean text from a PDF file on disk."""
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as e:
        print(f"[pdf] Failed to open PDF at {pdf_path}: {e}")
        return ""
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
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        print(f"[pdf] Failed to open PDF from bytes: {e}")
        return ""
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


def extract_text_with_ocr(pdf_path: str) -> str:
    """Placeholder for OCR-based text extraction from image PDFs.

    TODO: Implement using pytesseract or similar OCR library.
    This should be called as a fallback when standard extraction
    returns near-empty text from a non-empty PDF.
    """
    # Future: pip install pytesseract pillow
    # 1. Convert PDF pages to images using pymupdf
    # 2. Run pytesseract.image_to_string() on each page
    # 3. Join and return extracted text
    return ""


def extract_text_with_ocr_bytes(pdf_bytes: bytes) -> str:
    """Placeholder for OCR extraction from in-memory PDF bytes.

    TODO: Implement using pytesseract or similar OCR library.
    """
    return ""
