"""Node 4: Course Material Fetcher & Embedder.

Takes extracted references, fuzzy-matches against the course content tree,
downloads new files, and embeds them into ChromaDB.
"""

import hashlib
import os
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rapidfuzz import fuzz

from agents.state import GraphState
from utils.brightspace import get_content_catalog, BS_BASE, LE_VER
from utils.chroma import get_course_materials_collection
from utils.manifest import load_manifest, save_manifest
from utils.pdf import extract_text_from_bytes, extract_text_with_ocr_bytes
from utils.video import is_video_file, detect_video, estimate_duration_minutes, get_duration_minutes, transcribe_video, MAX_DURATION_MINUTES

load_dotenv()

FUZZY_THRESHOLD = 60

_embeddings = None


def _get_embeddings() -> OpenAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        )
    return _embeddings


def _is_already_in_chroma(collection, topic_id: int, course_id: int) -> bool:
    """Check if a material is already embedded in ChromaDB by querying its metadata."""
    try:
        results = collection.get(
            where={"topic_id": str(topic_id)},
            limit=1,
        )
        return len(results.get("ids", [])) > 0
    except Exception:
        return False


def _fuzzy_match(references: list[dict], catalog: list[dict]) -> list[dict]:
    """Match extracted references against the content catalog using fuzzy string matching.

    Returns list of catalog items that matched above threshold.
    """
    matched = []
    seen_ids = set()

    for ref in references:
        ref_name = ref.get("name", "")
        ref_hint = ref.get("context_hint", "")
        best_score = 0
        best_item = None

        for item in catalog:
            title = item.get("title", "")
            full_context = f"{item.get('module_path', '')} {title}"

            # Use both token_sort_ratio (word reordering) and partial_ratio (substring matching)
            score_name_sort = fuzz.token_sort_ratio(ref_name, title)
            score_name_partial = fuzz.partial_ratio(ref_name.lower(), title.lower())
            score_hint = fuzz.token_sort_ratio(ref_hint, full_context)
            score = max(score_name_sort, score_name_partial, score_hint)

            if score > best_score:
                best_score = score
                best_item = item

        if best_item and best_score >= FUZZY_THRESHOLD and best_item["id"] not in seen_ids:
            seen_ids.add(best_item["id"])
            matched.append({**best_item, "match_score": best_score, "matched_ref": ref_name})
            print(f"  [match] '{ref_name}' -> '{best_item['title']}' (score={best_score})")
        elif ref_name:
            print(f"  [no match] '{ref_name}' — best score {best_score} < {FUZZY_THRESHOLD}")

    return matched


def _download_and_extract(topic_id: int, org_unit_id: int, bs_token: str, title: str = "", timeout: int = 30) -> tuple[bytes, str]:
    """Download a file from Brightspace and extract text. Returns (raw_bytes, extracted_text)."""
    with httpx.Client(
        base_url=BS_BASE,
        headers={"Authorization": f"Bearer {bs_token}"},
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        resp = client.get(f"/d2l/api/le/{LE_VER}/{org_unit_id}/content/topics/{topic_id}/file")
        if resp.status_code != 200:
            print(f"  [download] Failed for topic {topic_id}: {resp.status_code}")
            return b"", ""

        raw = resp.content
        content_type = resp.headers.get("content-type", "")

        # Video file — check content-type AND filename extension
        if detect_video(content_type, title):
            return raw, "__VIDEO__"

        # Try PDF extraction first
        if "pdf" in content_type:
            text = extract_text_from_bytes(raw)
            if text:
                return raw, text

        # Fallback: try decoding as plain text
        try:
            text = raw.decode("utf-8", errors="ignore")
            if len(text.strip()) > 50:
                return raw, text
        except Exception:
            pass

        # Last resort: try PDF extraction regardless of content-type
        text = extract_text_from_bytes(raw)
        if text:
            return raw, text

        return raw, ""


def material_fetcher(state: GraphState) -> dict:
    """Fetch, match, download, and embed course materials."""
    import time
    from utils.pipeline_log import log_step
    
    t0 = time.time()

    user_topics = state.get("user_selected_topics") or []

    supp_uploads_pending = state.get("supplementary_uploads") or []

    # Skip entirely if cached AND no user-selected topics AND no supplementary uploads to process
    if state.get("embedded_materials") is not None and not user_topics and not supp_uploads_pending:
        print("[material_fetcher] Skipping -- materials already cached, no new selections")
        return {"pipeline_log": log_step(state, "material_fetcher", "skipped", "materials already cached", time.time() - t0)}

    org_unit_id = state.get("org_unit_id")
    bs_token = state.get("bs_token", "")
    course_id = state.get("course_id")

    if not bs_token:
        print("[material_fetcher] Missing bs_token, skipping")
        return {"embedded_materials": [], "materials_metadata": {}, "inaccessible_topics": [], "too_long_videos": [], "effective_course_id": 0, "pipeline_log": log_step(state, "material_fetcher", "error", "missing token", time.time() - t0)}

    # In freeform mode org_unit_id may be 0, but topics carry their own orgUnitId
    has_topics_with_org = any(t.get("orgUnitId") for t in user_topics)
    if not org_unit_id and not has_topics_with_org and not supp_uploads_pending:
        print("[material_fetcher] Missing org_unit_id and no topics with orgUnitId, skipping")
        return {"embedded_materials": [], "materials_metadata": {}, "inaccessible_topics": [], "too_long_videos": [], "effective_course_id": 0, "pipeline_log": log_step(state, "material_fetcher", "error", "missing org_unit_id", time.time() - t0)}

    # If cached but only supplementary uploads to process: skip catalog fetch entirely
    if state.get("embedded_materials") is not None and not user_topics and supp_uploads_pending:
        print(f"[material_fetcher] Cache hit but {len(supp_uploads_pending)} supplementary upload(s) need processing")
        try:
            existing_embedded = list(state["embedded_materials"])
            effective_course_id = course_id if course_id is not None else 0
            collection = get_course_materials_collection(effective_course_id)
            manifest = load_manifest(effective_course_id)
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            embeddings_model = _get_embeddings()
            new_names = []
            for upload in supp_uploads_pending:
                path = upload.get("path", "")
                title = upload.get("file_name", "uploaded_file")
                file_id = upload.get("file_id", title)
                if title in manifest:
                    print(f"  [skip] Supplementary '{title}' already in manifest")
                    if title not in existing_embedded:
                        existing_embedded.append(title)
                    continue
                if is_video_file(title):
                    print(f"  [skip] Supplementary video '{title}' -- handle on first turn")
                    continue
                try:
                    with open(path, "rb") as fh:
                        raw_bytes = fh.read()
                    text = extract_text_from_bytes(raw_bytes)
                    if len(text.strip()) < 100:
                        text = extract_text_with_ocr_bytes(raw_bytes)
                    if not text:
                        continue
                    chunks = splitter.split_text(text)
                    if not chunks or not collection:
                        continue
                    vectors = embeddings_model.embed_documents(chunks)
                    content_hash = hashlib.md5(raw_bytes).hexdigest()
                    collection.upsert(
                        ids=[f"material_{effective_course_id}_{file_id}_chunk_{i}" for i in range(len(chunks))],
                        documents=chunks,
                        embeddings=vectors,
                        metadatas=[{"source": title, "course_id": str(effective_course_id),
                                   "material_type": "user-upload", "chunk_index": i,
                                   "topic_id": str(file_id)} for i in range(len(chunks))],
                    )
                    manifest[title] = {"topic_id": file_id, "content_hash": content_hash,
                                       "chunk_count": len(chunks), "embedded_at": datetime.now(timezone.utc).isoformat()}
                    existing_embedded.append(title)
                    new_names.append(title)
                    print(f"  [embedded] Supplementary '{title}' -- {len(chunks)} chunks")
                except Exception as e:
                    print(f"  [error] Failed to embed supplementary '{title}': {e}")
            if effective_course_id is not None and manifest:
                save_manifest(effective_course_id, manifest)
            elapsed = time.time() - t0
            detail = f"{len(new_names)} supplementary embedded"
            return {
                "embedded_materials": existing_embedded,
                "materials_metadata": manifest,
                "inaccessible_topics": [],
                "too_long_videos": [],
                "effective_course_id": effective_course_id,
                "pipeline_log": log_step(state, "material_fetcher", "done", detail, elapsed),
            }
        except Exception as e:
            print(f"[material_fetcher] Error processing supplementary uploads: {e}")
            return {
                "embedded_materials": list(state.get("embedded_materials") or []),
                "materials_metadata": {},
                "inaccessible_topics": [],
                "too_long_videos": [],
                "effective_course_id": course_id or 0,
                "pipeline_log": log_step(state, "material_fetcher", "error", str(e), time.time() - t0),
            }

    # If cached but user added new topics: skip catalog fetch + fuzzy match, only process user selections
    if state.get("embedded_materials") is not None and user_topics:
        print(f"[material_fetcher] Cache hit but {len(user_topics)} user-selected topic(s) need processing")
        try:
            existing_embedded = list(state["embedded_materials"])
            # In freeform mode, use first topic's orgUnitId as fallback for collection/manifest
            effective_course_id = course_id if course_id is not None else next((t.get("orgUnitId") for t in user_topics if t.get("orgUnitId")), 0)
            collection = get_course_materials_collection(effective_course_id)
            manifest = load_manifest(effective_course_id)
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            embeddings_model = _get_embeddings()
            new_names = []
            cached_too_long = []

            # Separate local-file topics from Brightspace topics
            cached_local_files = []
            for topic in user_topics:
                topic_id = topic.get("id")
                title = topic.get("title", f"topic_{topic_id}")
                if not topic_id:
                    continue

                # Local file (replaced link upload) — process separately
                if topic.get("path"):
                    cached_local_files.append({
                        "file_id": str(topic_id),
                        "file_name": topic.get("file_name") or title,
                        "path": topic["path"],
                    })
                    continue

                if collection and _is_already_in_chroma(collection, topic_id, effective_course_id):
                    print(f"  [skip] '{title}' already in Chroma")
                    if title not in manifest:
                        manifest[title] = {"topic_id": topic_id, "chunk_count": "?", "embedded_at": "pre-existing"}
                    if title not in existing_embedded:
                        existing_embedded.append(title)
                    continue

                if title in manifest:
                    print(f"  [skip] '{title}' found in manifest")
                    if title not in existing_embedded:
                        existing_embedded.append(title)
                    continue

                topic_org_id = topic.get("orgUnitId") or org_unit_id
                dl_timeout = 120 if is_video_file(title) else 30
                print(f"  [download] '{title}' (topic_id={topic_id}, org={topic_org_id})...")
                raw_bytes, text = _download_and_extract(topic_id, topic_org_id, bs_token, title, timeout=dl_timeout)

                # Handle video files
                if text == "__VIDEO__":
                    import tempfile
                    file_ext = os.path.splitext(title)[1] or ".mp4"
                    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
                        tmp.write(raw_bytes)
                        tmp_path = tmp.name
                    try:
                        actual_dur = get_duration_minutes(tmp_path)
                        duration_est = actual_dur if actual_dur is not None else estimate_duration_minutes(len(raw_bytes))
                        print(f"  [video] '{title}' duration: {duration_est:.1f}min {'(actual)' if actual_dur else '(estimate)'}")
                        if duration_est > MAX_DURATION_MINUTES:
                            cached_too_long.append({"id": topic_id, "title": title, "duration_estimate_min": round(duration_est, 1)})
                            print(f"  [skip] Video '{title}' {duration_est:.1f}min (>{MAX_DURATION_MINUTES}min limit)")
                            continue
                        text = transcribe_video(tmp_path)
                    finally:
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                    if not text:
                        cached_too_long.append({"id": topic_id, "title": title, "duration_estimate_min": round(duration_est, 1), "reason": "transcription_failed"})
                        print(f"  [skip] Could not transcribe video '{title}'")
                        continue
                    print(f"  [transcribed] Video '{title}' -- {len(text)} chars")

                if not text:
                    print(f"  [skip] Could not extract text from '{title}'")
                    continue

                chunks = splitter.split_text(text)
                if not chunks:
                    continue

                if collection:
                    try:
                        vectors = embeddings_model.embed_documents(chunks)
                        content_hash = hashlib.md5(raw_bytes).hexdigest()
                        collection.upsert(
                            ids=[f"material_{effective_course_id}_{topic_id}_chunk_{i}" for i in range(len(chunks))],
                            documents=chunks,
                            embeddings=vectors,
                            metadatas=[{"source": title, "course_id": str(effective_course_id), "material_type": "user-selected", "chunk_index": i, "topic_id": str(topic_id)} for i in range(len(chunks))],
                        )
                        manifest[title] = {"topic_id": topic_id, "content_hash": content_hash, "chunk_count": len(chunks), "embedded_at": datetime.now(timezone.utc).isoformat()}
                        existing_embedded.append(title)
                        new_names.append(title)
                        print(f"  [embedded] '{title}' -- {len(chunks)} chunks")
                    except Exception as e:
                        print(f"  [error] Failed to embed '{title}': {e}")

            # Process local file topics (replaced link uploads)
            for upload in cached_local_files:
                path = upload.get("path", "")
                title = upload.get("file_name", "uploaded_file")
                file_id = upload.get("file_id", title)
                if title in manifest:
                    print(f"  [skip] Local file '{title}' already in manifest")
                    if title not in existing_embedded:
                        existing_embedded.append(title)
                    continue
                try:
                    if is_video_file(title):
                        size_bytes = os.path.getsize(path)
                        actual_dur = get_duration_minutes(path)
                        duration = actual_dur if actual_dur is not None else estimate_duration_minutes(size_bytes)
                        if duration > MAX_DURATION_MINUTES:
                            cached_too_long.append({"id": file_id, "title": title, "duration_estimate_min": round(duration, 1), "reason": "too_long"})
                            print(f"  [skip] Local video '{title}' {duration:.1f}min (>{MAX_DURATION_MINUTES}min limit)")
                            continue
                        text = transcribe_video(path)
                        if not text:
                            cached_too_long.append({"id": file_id, "title": title, "duration_estimate_min": round(duration, 1), "reason": "transcription_failed"})
                            print(f"  [skip] Could not transcribe local video '{title}'")
                            continue
                        print(f"  [transcribed] Local video '{title}' -- {len(text)} chars")
                        with open(path, "rb") as fh:
                            raw_bytes = fh.read()
                    else:
                        with open(path, "rb") as fh:
                            raw_bytes = fh.read()
                        text = extract_text_from_bytes(raw_bytes)
                        if len(text.strip()) < 100:
                            text = extract_text_with_ocr_bytes(raw_bytes)
                    if not text:
                        print(f"  [skip] Could not extract text from local file '{title}'")
                        continue
                    chunks = splitter.split_text(text)
                    if not chunks or not collection:
                        continue
                    vectors = embeddings_model.embed_documents(chunks)
                    content_hash = hashlib.md5(raw_bytes).hexdigest()
                    collection.upsert(
                        ids=[f"material_{effective_course_id}_{file_id}_chunk_{i}" for i in range(len(chunks))],
                        documents=chunks,
                        embeddings=vectors,
                        metadatas=[{"source": title, "course_id": str(effective_course_id), "material_type": "user-upload", "chunk_index": i, "topic_id": str(file_id)} for i in range(len(chunks))],
                    )
                    manifest[title] = {"topic_id": file_id, "content_hash": content_hash, "chunk_count": len(chunks), "embedded_at": datetime.now(timezone.utc).isoformat()}
                    existing_embedded.append(title)
                    new_names.append(title)
                    print(f"  [embedded] Local file '{title}' -- {len(chunks)} chunks")
                except Exception as e:
                    print(f"  [error] Failed to embed local file '{title}': {e}")

            # Process supplementary uploaded files (from pdf_parser) in the fast-path
            for upload in supp_uploads_pending:
                path = upload.get("path", "")
                title = upload.get("file_name", "uploaded_file")
                file_id = upload.get("file_id", title)
                if title in manifest:
                    print(f"  [skip] Supplementary '{title}' already in manifest")
                    if title not in existing_embedded:
                        existing_embedded.append(title)
                    continue
                if is_video_file(title):
                    print(f"  [skip] Supplementary video '{title}' skipped in fast-path (process via full path on first turn)")
                    continue
                try:
                    with open(path, "rb") as fh:
                        raw_bytes = fh.read()
                    text = extract_text_from_bytes(raw_bytes)
                    if len(text.strip()) < 100:
                        text = extract_text_with_ocr_bytes(raw_bytes)
                    if not text:
                        print(f"  [skip] Could not extract text from supplementary '{title}'")
                        continue
                    chunks = splitter.split_text(text)
                    if not chunks or not collection:
                        continue
                    vectors = embeddings_model.embed_documents(chunks)
                    content_hash = hashlib.md5(raw_bytes).hexdigest()
                    collection.upsert(
                        ids=[f"material_{effective_course_id}_{file_id}_chunk_{i}" for i in range(len(chunks))],
                        documents=chunks,
                        embeddings=vectors,
                        metadatas=[{"source": title, "course_id": str(effective_course_id),
                                   "material_type": "user-upload", "chunk_index": i,
                                   "topic_id": str(file_id)} for i in range(len(chunks))],
                    )
                    manifest[title] = {"topic_id": file_id, "content_hash": content_hash,
                                       "chunk_count": len(chunks), "embedded_at": datetime.now(timezone.utc).isoformat()}
                    existing_embedded.append(title)
                    new_names.append(title)
                    print(f"  [embedded] Supplementary '{title}' -- {len(chunks)} chunks")
                except Exception as e:
                    print(f"  [error] Failed to embed supplementary '{title}': {e}")

            if effective_course_id is not None and manifest:
                save_manifest(effective_course_id, manifest)

            elapsed = time.time() - t0
            detail = f"{len(new_names)} new user-selected embedded" if new_names else "all user-selected already cached"
            print(f"[material_fetcher] Done in {elapsed:.1f}s -- {detail}")
            return {
                "embedded_materials": existing_embedded,
                "materials_metadata": manifest,
                "inaccessible_topics": [],
                "too_long_videos": cached_too_long,
                "effective_course_id": effective_course_id,
                "pipeline_log": log_step(state, "material_fetcher", "done", detail, elapsed),
            }
        except Exception as e:
            print(f"[material_fetcher] Error processing user-selected topics: {e}")
            return {
                "embedded_materials": list(state.get("embedded_materials") or []),
                "materials_metadata": {},
                "inaccessible_topics": [],
                "too_long_videos": [],
                "effective_course_id": effective_course_id,
                "pipeline_log": log_step(state, "material_fetcher", "error", str(e), time.time() - t0),
            }

    references = state.get("material_references") or []
    if not references and not user_topics and not supp_uploads_pending:
        print("[material_fetcher] No material references to fetch")
        return {"embedded_materials": [], "materials_metadata": {}, "inaccessible_topics": [], "too_long_videos": [], "effective_course_id": 0, "pipeline_log": log_step(state, "material_fetcher", "done", "no references", time.time() - t0)}

    # In freeform mode, use first topic's orgUnitId as fallback
    effective_course_id = course_id or next((t.get("orgUnitId") for t in user_topics if t.get("orgUnitId")), 0)
    effective_org_unit_id = org_unit_id or effective_course_id

    try:
        # Step 1: Get content catalog from Brightspace (skip in freeform with no global org_unit_id)
        catalog = []
        if org_unit_id:
            print(f"[material_fetcher] Walking content tree for org_unit {org_unit_id}...")
            catalog = get_content_catalog(org_unit_id, bs_token)
            if not catalog and not user_topics:
                print("[material_fetcher] Empty content catalog -- token may be expired or user lacks access.")
                return {"embedded_materials": [], "materials_metadata": {}, "inaccessible_topics": [], "too_long_videos": [], "effective_course_id": effective_course_id, "pipeline_log": log_step(state, "material_fetcher", "warning", "api returned no content", time.time() - t0)}
        elif not user_topics and not supp_uploads_pending:
            print("[material_fetcher] No org_unit_id and no user topics, skipping")
            return {"embedded_materials": [], "materials_metadata": {}, "inaccessible_topics": [], "too_long_videos": [], "effective_course_id": 0, "pipeline_log": log_step(state, "material_fetcher", "done", "freeform, no topics", time.time() - t0)}

        downloadable_count = sum(1 for item in catalog if item.get("topic_type") == 1)
        link_count = sum(1 for item in catalog if item.get("topic_type") == 3)
        print(f"[material_fetcher] {downloadable_count} downloadable + {link_count} link topics in catalog")

        # Step 2: Fuzzy match references against full catalog (including links)
        print(f"[material_fetcher] Fuzzy matching {len(references)} references...")
        matched = _fuzzy_match(references, catalog)
        seen_ids = {m["id"] for m in matched}

        # Process user-selected topics (manual picks)
        local_file_topics = []  # Topics with path key (replaced link uploads)
        for topic in user_topics:
            topic_id = topic.get("id")
            title = topic.get("title", f"topic_{topic_id}")

            # If topic has a path, it's a local file (user replaced an external link)
            if topic.get("path"):
                local_file_topics.append({
                    "file_id": str(topic_id),
                    "file_name": topic.get("file_name") or title,
                    "path": topic["path"],
                })
                print(f"  [user-selected local] '{title}' (path={topic['path']})")
                continue

            if topic_id and topic_id not in seen_ids:
                matched.append({
                    "id": topic_id, "title": title, "topic_type": 1,
                    "url": None, "module_path": "user-selected",
                    "match_score": 100, "matched_ref": f"[user-selected] {title}",
                    "orgUnitId": topic.get("orgUnitId"),
                })
                seen_ids.add(topic_id)
                print(f"  [user-selected] '{title}' (topic_id={topic_id}, org={topic.get('orgUnitId') or org_unit_id})")

        # Separate link topics (inaccessible) from downloadable ones
        inaccessible_topics = []
        downloadable_matched = []
        for item in matched:
            if item.get("topic_type") == 3:
                inaccessible_topics.append({
                    "id": item["id"],
                    "title": item["title"],
                    "url": item.get("url", ""),
                })
                print(f"  [link] '{item['title']}' is an external link -- marking inaccessible")
            else:
                downloadable_matched.append(item)
        matched = downloadable_matched

        if not matched and not local_file_topics:
            print("[material_fetcher] No materials matched above threshold")
            return {"embedded_materials": [], "materials_metadata": {}, "inaccessible_topics": inaccessible_topics, "too_long_videos": [], "effective_course_id": effective_course_id, "pipeline_log": log_step(state, "material_fetcher", "done", "0 matched", time.time() - t0)}

        # Step 3: Check Chroma + manifest for dedup (effective_course_id=0 is valid for freeform)
        collection = get_course_materials_collection(effective_course_id)
        manifest = load_manifest(effective_course_id)
        to_embed = []

        for item in matched:
            topic_id = item["id"]
            title = item["title"]

            # Check Chroma first — if chunks already exist for this topic, skip
            if collection and _is_already_in_chroma(collection, topic_id, effective_course_id):
                print(f"  [skip] '{title}' already in Chroma (topic_id={topic_id})")
                # Ensure manifest is in sync
                if title not in manifest:
                    manifest[title] = {
                        "topic_id": topic_id,
                        "chunk_count": "?",
                        "embedded_at": "pre-existing",
                    }
                continue

            # Also check manifest as fallback
            if title in manifest:
                print(f"  [skip] '{title}' found in manifest ({manifest[title].get('chunk_count', '?')} chunks)")
                continue

            to_embed.append(item)

        # Step 4+5: Download, extract, chunk, embed
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        embeddings_model = _get_embeddings()
        embedded_names = []
        too_long_videos = []

        if not to_embed:
            print("[material_fetcher] All matched Brightspace materials already embedded")

        for item in to_embed:
            topic_id = item["id"]
            title = item["title"]
            item_org_id = item.get("orgUnitId") or org_unit_id
            dl_timeout = 120 if is_video_file(title) else 30
            print(f"  [download] '{title}' (topic_id={topic_id}, org={item_org_id})...")

            raw_bytes, text = _download_and_extract(topic_id, item_org_id, bs_token, title, timeout=dl_timeout)

            # Handle video files
            if text == "__VIDEO__":
                import tempfile
                file_ext = item.get("file_extension") or os.path.splitext(title)[1] or ".mp4"
                with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
                    tmp.write(raw_bytes)
                    tmp_path = tmp.name
                try:
                    actual_dur = get_duration_minutes(tmp_path)
                    duration_est = actual_dur if actual_dur is not None else estimate_duration_minutes(len(raw_bytes))
                    print(f"  [video] '{title}' duration: {duration_est:.1f}min {'(actual)' if actual_dur else '(estimate)'}")
                    if duration_est > MAX_DURATION_MINUTES:
                        too_long_videos.append({"id": topic_id, "title": title, "duration_estimate_min": round(duration_est, 1)})
                        print(f"  [skip] Video '{title}' {duration_est:.1f}min (>{MAX_DURATION_MINUTES}min limit)")
                        continue
                    text = transcribe_video(tmp_path)
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                if not text:
                    too_long_videos.append({"id": topic_id, "title": title, "duration_estimate_min": round(duration_est, 1), "reason": "transcription_failed"})
                    print(f"  [skip] Could not transcribe video '{title}'")
                    continue
                print(f"  [transcribed] Video '{title}' -- {len(text)} chars")

            if not text:
                print(f"  [skip] Could not extract text from '{title}'")
                continue

            chunks = splitter.split_text(text)
            if not chunks:
                continue

            if collection:
                try:
                    vectors = embeddings_model.embed_documents(chunks)
                    content_hash = hashlib.md5(raw_bytes).hexdigest()

                    collection.upsert(
                        ids=[f"material_{effective_course_id}_{topic_id}_chunk_{i}" for i in range(len(chunks))],
                        documents=chunks,
                        embeddings=vectors,
                        metadatas=[
                            {
                                "source": title,
                                "course_id": str(effective_course_id),
                                "material_type": item.get("matched_ref", "other"),
                                "chunk_index": i,
                                "topic_id": str(topic_id),
                            }
                            for i in range(len(chunks))
                        ],
                    )

                    manifest[title] = {
                        "topic_id": topic_id,
                        "content_hash": content_hash,
                        "chunk_count": len(chunks),
                        "embedded_at": datetime.now(timezone.utc).isoformat(),
                    }
                    embedded_names.append(title)
                    print(f"  [embedded] '{title}' — {len(chunks)} chunks")

                except Exception as e:
                    print(f"  [error] Failed to embed '{title}': {e}")

        # Step 6: Process supplementary uploaded files (from pdf_parser) + local file topics
        supp_uploads = (state.get("supplementary_uploads") or []) + local_file_topics
        for upload in supp_uploads:
            path = upload.get("path", "")
            title = upload.get("file_name", "uploaded_file")
            file_id = upload.get("file_id", title)

            if title in manifest:
                print(f"  [skip] Supplementary '{title}' already in manifest")
                if title not in embedded_names:
                    embedded_names.append(title)
                continue

            try:
                if is_video_file(title):
                    size_bytes = os.path.getsize(path)
                    actual_dur = get_duration_minutes(path)
                    duration = actual_dur if actual_dur is not None else estimate_duration_minutes(size_bytes)
                    if duration > MAX_DURATION_MINUTES:
                        too_long_videos.append({"id": file_id, "title": title, "duration_estimate_min": round(duration, 1), "reason": "too_long"})
                        print(f"  [skip] Supplementary video '{title}' estimated {duration:.1f}min (>{MAX_DURATION_MINUTES}min limit)")
                        continue
                    text = transcribe_video(path)
                    if not text:
                        too_long_videos.append({"id": file_id, "title": title, "duration_estimate_min": round(duration, 1), "reason": "transcription_failed"})
                        print(f"  [skip] Could not transcribe video '{title}'")
                        continue
                    print(f"  [transcribed] Supplementary video '{title}' -- {len(text)} chars")
                    with open(path, "rb") as fh:
                        raw_bytes = fh.read()
                else:
                    with open(path, "rb") as fh:
                        raw_bytes = fh.read()
                    text = extract_text_from_bytes(raw_bytes)
                    if len(text.strip()) < 100:
                        text = extract_text_with_ocr_bytes(raw_bytes)
                
                if not text:
                    print(f"  [skip] Could not extract text from supplementary '{title}'")
                    continue

                chunks = splitter.split_text(text)
                if not chunks or not collection:
                    continue

                vectors = embeddings_model.embed_documents(chunks)
                content_hash = hashlib.md5(raw_bytes).hexdigest()
                collection.upsert(
                    ids=[f"material_{effective_course_id}_{file_id}_chunk_{i}" for i in range(len(chunks))],
                    documents=chunks,
                    embeddings=vectors,
                    metadatas=[{
                        "source": title,
                        "course_id": str(effective_course_id),
                        "material_type": "user-upload",
                        "chunk_index": i,
                        "topic_id": str(file_id),
                    } for i in range(len(chunks))],
                )
                manifest[title] = {
                    "topic_id": file_id,
                    "content_hash": content_hash,
                    "chunk_count": len(chunks),
                    "embedded_at": datetime.now(timezone.utc).isoformat(),
                }
                embedded_names.append(title)
                print(f"  [embedded] Supplementary '{title}' -- {len(chunks)} chunks")
            except Exception as e:
                print(f"  [error] Failed to embed supplementary '{title}': {e}")

        # Step 7: Save manifest (effective_course_id=0 is valid for freeform)
        if effective_course_id is not None and manifest:
            save_manifest(effective_course_id, manifest)

        all_embedded = [m["title"] for m in matched if m["title"] in manifest] + [
            u.get("file_name", "") for u in supp_uploads if u.get("file_name", "") in manifest
        ]
        all_embedded = list(dict.fromkeys(all_embedded))  # dedup preserving order
        elapsed = time.time() - t0
        print(f"[material_fetcher] Done in {elapsed:.1f}s — {len(embedded_names)} new, {len(all_embedded)} total embedded")

        return {
            "embedded_materials": all_embedded,
            "materials_metadata": manifest,
            "inaccessible_topics": inaccessible_topics,
            "too_long_videos": too_long_videos,
            "effective_course_id": effective_course_id,
            "pipeline_log": log_step(state, "material_fetcher", "done", f"{len(embedded_names)} new embedded", elapsed)
        }

    except Exception as e:
        print(f"[material_fetcher] CRITICAL ERROR during fetch/embed: {e}")
        return {
            "embedded_materials": [],
            "materials_metadata": {},
            "inaccessible_topics": [],
            "too_long_videos": [],
            "effective_course_id": 0,
            "pipeline_log": log_step(state, "material_fetcher", "error", str(e), time.time() - t0)
        }
