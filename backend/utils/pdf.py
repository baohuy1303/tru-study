"""PDF text extraction utilities using pymupdf."""

import base64
import os

import pymupdf
from dotenv import load_dotenv

load_dotenv()


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


def extract_text_with_ocr_bytes(pdf_bytes: bytes) -> str:
    """Extract text from image-based PDF using GPT-4o Vision as fallback.

    Called when standard PyMuPDF extraction returns near-empty text from a
    non-empty PDF (image-based slides, scanned documents, etc.).
    """
    from openai import OpenAI

    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        print(f"[ocr] Failed to open PDF for OCR: {e}")
        return ""

    if doc.page_count == 0:
        return ""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[ocr] OPENAI_API_KEY not set, cannot run OCR")
        return ""

    client = OpenAI(api_key=api_key)
    pages_text = []

    for page_num, page in enumerate(doc):
        mat = pymupdf.Matrix(150 / 72, 150 / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode("utf-8")

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract all text from this page exactly as it appears. Return only the extracted text, no commentary.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}",
                                "detail": "high",
                            },
                        },
                    ],
                }],
                max_tokens=2000,
            )
            page_text = response.choices[0].message.content or ""
            if page_text.strip():
                pages_text.append(page_text.strip())
            print(f"[ocr] Page {page_num + 1}/{doc.page_count} extracted ({len(page_text)} chars)")
        except Exception as e:
            print(f"[ocr] GPT-4o Vision failed on page {page_num + 1}: {e}")

    doc.close()
    return "\n\n".join(pages_text)


def extract_text_with_ocr(pdf_path: str) -> str:
    """Extract text from image-based PDF file using GPT-4o Vision."""
    try:
        with open(pdf_path, "rb") as f:
            return extract_text_with_ocr_bytes(f.read())
    except Exception as e:
        print(f"[ocr] Failed to read file for OCR at {pdf_path}: {e}")
        return ""
