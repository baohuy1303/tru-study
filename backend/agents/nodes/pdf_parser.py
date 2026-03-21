"""Node 1: PDF Parser & Token Evaluator.

Extracts text from:
1. Brightspace assignment instructions (already in state as assignment_text)
2. Brightspace PDF attachments (downloaded via API using bs_token)
3. Manually uploaded PDF (from assignment_pdf_path — legacy field)
4. Uploaded files from frontend (state["uploaded_files"])

Counts tokens for downstream routing.
"""

import time

import httpx

from agents.state import GraphState
from utils.tokens import count_tokens
from utils.pdf import extract_text_from_pdf, extract_text_from_bytes, extract_text_with_ocr, extract_text_with_ocr_bytes
from utils.video import is_video_file, estimate_duration_minutes, get_duration_minutes, transcribe_video, MAX_DURATION_MINUTES
from utils.pipeline_log import log_step

BS_BASE = "https://learn.truman.edu"
LE_VER = "1.92"

# OCR threshold: if extracted text is shorter than this, treat PDF as image-based
_OCR_THRESHOLD = 100


def _try_extract_with_ocr_fallback_bytes(raw_bytes: bytes, label: str) -> str:
    """Extract text from bytes, falling back to OCR if standard extraction is too short."""
    text = extract_text_from_bytes(raw_bytes)
    if len(text.strip()) < _OCR_THRESHOLD:
        print(f"[pdf_parser] '{label}' extracted <{_OCR_THRESHOLD} chars, trying OCR fallback...")
        ocr_text = extract_text_with_ocr_bytes(raw_bytes)
        if ocr_text:
            print(f"[pdf_parser] OCR succeeded for '{label}' ({len(ocr_text)} chars)")
            return ocr_text
    return text


def _try_extract_with_ocr_fallback_path(pdf_path: str, label: str) -> str:
    """Extract text from file path, falling back to OCR if standard extraction is too short."""
    text = extract_text_from_pdf(pdf_path)
    if len(text.strip()) < _OCR_THRESHOLD:
        print(f"[pdf_parser] '{label}' extracted <{_OCR_THRESHOLD} chars, trying OCR fallback...")
        ocr_text = extract_text_with_ocr(pdf_path)
        if ocr_text:
            print(f"[pdf_parser] OCR succeeded for '{label}' ({len(ocr_text)} chars)")
            return ocr_text
    return text


def pdf_parser(state: GraphState) -> dict:
    """Extract assignment text from all sources and count tokens."""
    # Skip if pipeline state is already cached (multi-turn)
    if state.get("assignment_summary") and state.get("assignment_token_count") is not None:
        print("[pdf_parser] Skipping -- cached state available")
        return {
            "pipeline_log": log_step(state, "pdf_parser", "skipped", "cached state available"),
        }

    t0 = time.time()
    parts = []
    supplementary_uploads = []

    # ── Source 1: Uploaded files from frontend ────────────────────────────────
    # Process BEFORE Brightspace instructions so main file text leads the context
    uploaded_files = state.get("uploaded_files") or []
    main_file = next((f for f in uploaded_files if f.get("is_main")), None)
    supplementary_uploads = [f for f in uploaded_files if not f.get("is_main")]

    too_long_videos = []

    if main_file:
        path = main_file.get("path", "")
        label = main_file.get("file_name", "uploaded_file")
        print(label)
        print(path)
        try:
            if is_video_file(label):
                import os
                size_bytes = os.path.getsize(path)
                actual_dur = get_duration_minutes(path)
                duration = actual_dur if actual_dur is not None else estimate_duration_minutes(size_bytes)
                if duration > MAX_DURATION_MINUTES:
                    too_long_videos.append({"id": label, "title": label, "duration_estimate_min": round(duration, 1), "reason": "too_long"})
                    print(f"[pdf_parser] Main video '{label}' too long: {duration:.1f}min (>{MAX_DURATION_MINUTES}min)")
                else:
                    extracted = transcribe_video(path)
                    if extracted:
                        parts.append(f"--- Main Uploaded Video: {label} ---\n{extracted}")
                        print(f"[pdf_parser] Main uploaded video '{label}': {len(extracted)} chars")
                    else:
                        too_long_videos.append({"id": label, "title": label, "duration_estimate_min": round(duration, 1), "reason": "transcription_failed"})
                        print(f"[pdf_parser] Failed to transcribe video '{label}'")
            else:
                extracted = _try_extract_with_ocr_fallback_path(path, label)
                if extracted:
                    parts.append(f"--- Main Uploaded File: {label} ---\n{extracted}")
                    print(f"[pdf_parser] Main uploaded file '{label}': {len(extracted)} chars")
        except Exception as e:
            print(f"[pdf_parser] Failed to parse main uploaded file '{label}': {e}")

    # ── Source 2: Brightspace instructions text ───────────────────────────────
    instructions = state.get("assignment_text") or ""
    if instructions.strip():
        parts.append(instructions.strip())

    # ── Source 3: Brightspace PDF attachments (auto-download) ─────────────────
    attachments = state.get("assignment_attachments") or []
    bs_token = state.get("bs_token", "")
    org_unit_id = state.get("org_unit_id")
    assignment_id = state.get("assignment_id")

    if attachments and bs_token and org_unit_id and assignment_id:
        pdf_attachments = [
            a for a in attachments
            if a.get("file_name", "").lower().endswith(".pdf")
        ]
        for attachment in pdf_attachments:
            file_id = attachment.get("file_id")
            if not file_id:
                continue
            label = attachment.get("file_name", "unknown.pdf")
            try:
                with httpx.Client(
                    base_url=BS_BASE,
                    headers={"Authorization": f"Bearer {bs_token}"},
                    timeout=30,
                    follow_redirects=True,
                ) as client:
                    resp = client.get(
                        f"/d2l/api/le/{LE_VER}/{org_unit_id}/dropbox/folders/{assignment_id}/attachments/{file_id}"
                    )
                    if resp.status_code == 200:
                        extracted = _try_extract_with_ocr_fallback_bytes(resp.content, label)
                        if extracted:
                            parts.append(f"--- Attachment: {label} ---\n{extracted}")
            except Exception as e:
                print(f"[pdf_parser] Failed to download attachment {file_id}: {e}")

    # ── Source 4: Legacy uploaded PDF path ────────────────────────────────────
    pdf_path = state.get("assignment_pdf_path")
    if pdf_path:
        try:
            extracted = _try_extract_with_ocr_fallback_path(pdf_path, "uploaded_pdf")
            if extracted:
                parts.append(f"--- Uploaded PDF ---\n{extracted}")
        except Exception as e:
            print(f"[pdf_parser] Failed to parse uploaded PDF: {e}")

    # ── Combine all sources ───────────────────────────────────────────────────
    full_text = "\n\n".join(parts) if parts else ""

    # If still empty after all sources + OCR attempts, emit warning
    if not full_text and (attachments or pdf_path or main_file):
        full_text = (
            "[Warning] The provided file(s) could not be parsed. "
            "They may be image-based documents that OCR could not process. "
            "Please try uploading a text-based PDF."
        )

    token_count = count_tokens(full_text) if full_text else 0
    elapsed = time.time() - t0
    print(f"[pdf_parser] Done in {elapsed:.1f}s -- {token_count} tokens")

    result = {
        "assignment_text": full_text,
        "assignment_token_count": token_count,
        "pipeline_log": log_step(state, "pdf_parser", "done", f"{token_count} tokens extracted", elapsed),
    }

    if too_long_videos:
        result["too_long_videos"] = state.get("too_long_videos", []) + too_long_videos

    # Pass supplementary uploads forward for material_fetcher
    if supplementary_uploads:
        result["supplementary_uploads"] = supplementary_uploads

    return result
