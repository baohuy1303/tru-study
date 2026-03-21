"""POST /api/upload — Accept file uploads and save to local storage."""

import os
import shutil
import uuid

from fastapi import APIRouter, Depends, UploadFile, File

from dependencies import get_bs_token

router = APIRouter(prefix="/api")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "storage", "uploads")


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), token: str = Depends(get_bs_token)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    file_id = str(uuid.uuid4())
    original_name = file.filename or "upload"
    ext = os.path.splitext(original_name)[-1].lower()
    save_path = os.path.abspath(os.path.join(UPLOAD_DIR, f"{file_id}{ext}"))

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    print(f"[upload] Saved '{original_name}' -> {save_path}")
    return {"file_id": file_id, "file_name": original_name, "path": save_path}
