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
from utils.pdf import extract_text_from_bytes

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


def _download_and_extract(topic_id: int, org_unit_id: int, bs_token: str) -> tuple[bytes, str]:
    """Download a file from Brightspace and extract text. Returns (raw_bytes, extracted_text)."""
    with httpx.Client(
        base_url=BS_BASE,
        headers={"Authorization": f"Bearer {bs_token}"},
        timeout=30,
        follow_redirects=True,
    ) as client:
        resp = client.get(f"/d2l/api/le/{LE_VER}/{org_unit_id}/content/topics/{topic_id}/file")
        if resp.status_code != 200:
            print(f"  [download] Failed for topic {topic_id}: {resp.status_code}")
            return b"", ""

        raw = resp.content
        content_type = resp.headers.get("content-type", "")

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

    # Skip entirely if cached AND no user-selected topics to process
    if state.get("embedded_materials") is not None and not user_topics:
        print("[material_fetcher] Skipping -- materials already cached, no new selections")
        return {"pipeline_log": log_step(state, "material_fetcher", "skipped", "materials already cached", time.time() - t0)}

    org_unit_id = state.get("org_unit_id")
    bs_token = state.get("bs_token", "")
    course_id = state.get("course_id")

    if not org_unit_id or not bs_token:
        print("[material_fetcher] Missing org_unit_id or bs_token, skipping")
        return {"embedded_materials": [], "materials_metadata": {}, "pipeline_log": log_step(state, "material_fetcher", "error", "missing org_unit_id or token", time.time() - t0)}

    # If cached but user added new topics: skip catalog fetch + fuzzy match, only process user selections
    if state.get("embedded_materials") is not None and user_topics:
        print(f"[material_fetcher] Cache hit but {len(user_topics)} user-selected topic(s) need processing")
        try:
            existing_embedded = list(state["embedded_materials"])
            collection = get_course_materials_collection(course_id) if course_id else None
            manifest = load_manifest(course_id) if course_id else {}
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            embeddings_model = _get_embeddings()
            new_names = []

            for topic in user_topics:
                topic_id = topic.get("id")
                title = topic.get("title", f"topic_{topic_id}")
                if not topic_id:
                    continue

                if collection and _is_already_in_chroma(collection, topic_id, course_id):
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

                print(f"  [download] '{title}' (topic_id={topic_id})...")
                raw_bytes, text = _download_and_extract(topic_id, org_unit_id, bs_token)
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
                            ids=[f"material_{course_id}_{topic_id}_chunk_{i}" for i in range(len(chunks))],
                            documents=chunks,
                            embeddings=vectors,
                            metadatas=[{"source": title, "course_id": str(course_id), "material_type": "user-selected", "chunk_index": i, "topic_id": str(topic_id)} for i in range(len(chunks))],
                        )
                        manifest[title] = {"topic_id": topic_id, "content_hash": content_hash, "chunk_count": len(chunks), "embedded_at": datetime.now(timezone.utc).isoformat()}
                        existing_embedded.append(title)
                        new_names.append(title)
                        print(f"  [embedded] '{title}' -- {len(chunks)} chunks")
                    except Exception as e:
                        print(f"  [error] Failed to embed '{title}': {e}")

            if course_id and manifest:
                save_manifest(course_id, manifest)

            elapsed = time.time() - t0
            detail = f"{len(new_names)} new user-selected embedded" if new_names else "all user-selected already cached"
            print(f"[material_fetcher] Done in {elapsed:.1f}s -- {detail}")
            return {
                "embedded_materials": existing_embedded,
                "materials_metadata": manifest,
                "pipeline_log": log_step(state, "material_fetcher", "done", detail, elapsed),
            }
        except Exception as e:
            print(f"[material_fetcher] Error processing user-selected topics: {e}")
            return {
                "embedded_materials": list(state.get("embedded_materials") or []),
                "materials_metadata": {},
                "pipeline_log": log_step(state, "material_fetcher", "error", str(e), time.time() - t0),
            }

    references = state.get("material_references") or []
    if not references and not user_topics:
        print("[material_fetcher] No material references to fetch")
        return {"embedded_materials": [], "materials_metadata": {}, "pipeline_log": log_step(state, "material_fetcher", "done", "no references", time.time() - t0)}

    try:
        # Step 1: Get content catalog from Brightspace
        print(f"[material_fetcher] Walking content tree for org_unit {org_unit_id}...")
        catalog = get_content_catalog(org_unit_id, bs_token)
        if not catalog:
            print("[material_fetcher] Empty content catalog -- token may be expired or user lacks access.")
            return {"embedded_materials": [], "materials_metadata": {}, "pipeline_log": log_step(state, "material_fetcher", "warning", "api returned no content", time.time() - t0)}

        # Filter to downloadable files only (TopicType 1)
        downloadable = [item for item in catalog if item.get("topic_type") == 1]
        print(f"[material_fetcher] {len(downloadable)} downloadable files in catalog")

        # Step 2: Fuzzy match references against catalog
        print(f"[material_fetcher] Fuzzy matching {len(references)} references...")
        matched = _fuzzy_match(references, downloadable)
        seen_ids = {m["id"] for m in matched}

        # Process user-selected topics (manual picks)
        for topic in user_topics:
            topic_id = topic.get("id")
            title = topic.get("title", f"topic_{topic_id}")
            if topic_id and topic_id not in seen_ids:
                matched.append({
                    "id": topic_id, "title": title, "topic_type": 1,
                    "url": None, "module_path": "user-selected",
                    "match_score": 100, "matched_ref": f"[user-selected] {title}",
                })
                seen_ids.add(topic_id)
                print(f"  [user-selected] '{title}' (topic_id={topic_id})")

        if not matched:
            print("[material_fetcher] No materials matched above threshold")
            return {"embedded_materials": [], "materials_metadata": {}, "pipeline_log": log_step(state, "material_fetcher", "done", "0 matched", time.time() - t0)}

        # Step 3: Check Chroma + manifest for dedup
        collection = get_course_materials_collection(course_id) if course_id else None
        manifest = load_manifest(course_id) if course_id else {}
        to_embed = []

        for item in matched:
            topic_id = item["id"]
            title = item["title"]

            # Check Chroma first — if chunks already exist for this topic, skip
            if collection and _is_already_in_chroma(collection, topic_id, course_id):
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

        if not to_embed:
            print("[material_fetcher] All matched materials already embedded")
            return {
                "embedded_materials": [m["title"] for m in matched],
                "materials_metadata": manifest,
                "pipeline_log": log_step(state, "material_fetcher", "done", f"all {len(matched)} cached", time.time() - t0)
            }

        # Step 4+5: Download, extract, chunk, embed
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        embeddings_model = _get_embeddings()
        embedded_names = []

        for item in to_embed:
            topic_id = item["id"]
            title = item["title"]
            print(f"  [download] '{title}' (topic_id={topic_id})...")

            raw_bytes, text = _download_and_extract(topic_id, org_unit_id, bs_token)
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
                        ids=[f"material_{course_id}_{topic_id}_chunk_{i}" for i in range(len(chunks))],
                        documents=chunks,
                        embeddings=vectors,
                        metadatas=[
                            {
                                "source": title,
                                "course_id": str(course_id),
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

        # Step 6: Save manifest
        if course_id and manifest:
            save_manifest(course_id, manifest)

        all_embedded = [m["title"] for m in matched if m["title"] in manifest]
        elapsed = time.time() - t0
        print(f"[material_fetcher] Done in {elapsed:.1f}s — {len(embedded_names)} new, {len(all_embedded)} total embedded")

        return {
            "embedded_materials": all_embedded,
            "materials_metadata": manifest,
            "pipeline_log": log_step(state, "material_fetcher", "done", f"{len(embedded_names)} new embedded", elapsed)
        }

    except Exception as e:
        print(f"[material_fetcher] CRITICAL ERROR during fetch/embed: {e}")
        return {
            "embedded_materials": [],
            "materials_metadata": {},
            "pipeline_log": log_step(state, "material_fetcher", "error", str(e), time.time() - t0)
        }
