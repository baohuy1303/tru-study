# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TruStudy is an AI study platform for Truman State University students. It integrates with Brightspace (D2L) LMS via Playwright-automated SSO login and the Valence REST API, then provides an AI-assisted learning interface with a LangGraph RAG pipeline that extracts assignment content, discovers referenced course materials, and generates grounded responses.

## Development Commands

### Frontend (from `frontend/`)
```bash
npm run dev        # Vite dev server on http://localhost:5173
npm run build      # TypeScript check + Vite production build
npm run lint       # ESLint
npx tsc --noEmit   # Type-check only
```

### Backend (from `backend/`)
```bash
source venv/Scripts/activate          # Activate Python venv (Windows/Git Bash)
uvicorn app:app --reload              # FastAPI dev server on http://localhost:8000
python test_graph.py                  # Pipeline tests (no API key needed for Phase 1)
python test_graph.py --with-llm       # Full tests including LLM calls (requires OPENAI_API_KEY)
python test_brightspace.py            # Brightspace API integration test (requires BS_USER/BS_PASS)
pip install -r requirements.txt       # Install dependencies
```

Both servers must run simultaneously. Frontend proxies `/api` calls to `http://localhost:8000`.

## Architecture

### Auth Flow
Frontend → `POST /api/auth/login` with username/password → Backend runs **Playwright** (`sync_playwright` in `ThreadPoolExecutor`) to automate Truman CAS SSO login → intercepts Bearer token from Brightspace API traffic → returns token to frontend → frontend stores in `localStorage` → all subsequent API calls include `Authorization: Bearer <token>` header.

### LangGraph Pipeline (`backend/agents/`)

The core AI system is a LangGraph `StateGraph` with conditional routing. All nodes share `GraphState` (TypedDict in `agents/state.py`).

**Flow:**
```
pdf_parser → token_gate (conditional)
  ├── small (<TOKEN_THRESHOLD tokens) → small_context_handler
  └── large (≥TOKEN_THRESHOLD tokens) → large_context_handler
→ material_extractor → task_planner → material_fetcher → query_rewriter → responder → END
```

**Nodes** (in `agents/nodes/`):
1. **`pdf_parser`** — Extracts text from: Brightspace instructions, auto-downloaded PDF attachments, manually uploaded files. Uses `pymupdf` with OCR fallback (`extract_text_with_ocr`) for image-based PDFs. Supports video files via Whisper transcription (10-min limit, 25MB limit). Separates `uploaded_files` into `main_file` (text injected) and `supplementary_uploads` (sent to ChromaDB via `material_fetcher`). Always emits `supplementary_uploads` (even empty) to clear stale LangGraph state.
2. **`context_handler`** (`handle_small_context` / `handle_large_context`) — Small: injects full assignment text + generates exhaustive LLM summary stored in `assignment_summary`. Large: generates concise summary + chunks/embeds into `assignment_{id}` ChromaDB collection (`context_mode = "rag"`).
3. **`material_extractor`** — LLM structured output (`with_structured_output(ExtractedReferences)`) to find referenced course materials (chapters, slides, labs) in assignment text.
4. **`task_planner`** — LLM structured output to generate an ordered to-do checklist from the assignment. Only runs on first turn (skips when `task_plan` is cached). Skips in freeform mode (no `assignment_id`). Result returned to frontend in SSE `result` payload and persisted in session.
5. **`material_fetcher`** — Walks Brightspace content tree, fuzzy-matches references against catalog (`rapidfuzz`, threshold 60), checks Chroma for existing embeddings, downloads new files, chunks/embeds into `course_materials_{effective_course_id}` collection. Also processes `supplementary_uploads` (non-main user files) and `user_selected_topics` (sidebar selections). Contains multiple skip/fast-path conditions guarded by `supp_uploads_pending` checks.
6. **`query_rewriter`** — Generates 2–3 semantically diverse LLM queries from the user prompt, assignment summary, and chat history for ChromaDB retrieval. Falls back to original prompt on error.
7. **`responder`** — Multi-query ChromaDB retrieval from `course_materials_{course_id}` and (in RAG mode) `assignment_{id}` collections. Deduplicates and ranks chunks. Assembles token-budgeted message list (system prompt + assignment context + retrieved chunks + chat history + user prompt). Generates response via LLM. Supports three modes: `learning` (Socratic), `neutral` (buddy), `lazy` (direct answers).

**Entry point:** `POST /api/chat/stream` in `routes/chat.py` → `build_graph()` in `agents/graph.py` → SSE stream.

**Critical `course_id` gotcha:** `effective_course_id = 0` in freeform mode (no assignment selected). All guards that use `if effective_course_id:` or `if course_id:` will incorrectly skip freeform — always use `if effective_course_id is not None:` and `if course_id is not None:` instead.

### Backend Utilities (`backend/utils/`)
- **`chroma.py`** — Persistent ChromaDB client (`storage/chroma/`). Two collection types: `assignment_{id}` and `course_materials_{id}`. `course_materials_0` is used for freeform uploads.
- **`manifest.py`** — JSON dedup manifests at `storage/manifests/{course_id}.json` tracking embedded materials (content_hash, chunk_count, timestamp).
- **`brightspace.py`** — Recursive content tree walker. `get_content_catalog()` returns flat list of all topics with module paths.
- **`pdf.py`** — `extract_text_from_pdf(path)` and `extract_text_from_bytes(bytes)` via `pymupdf`. `extract_text_with_ocr` / `extract_text_with_ocr_bytes` for image-based PDFs.
- **`video.py`** — `transcribe_video(path)` via OpenAI Whisper API. 10-min / 25MB hard limits. `is_video_file(filename)` extension check.
- **`tokens.py`** — `count_tokens(text)` via `tiktoken`.
- **`session.py`** — JSON session persistence at `storage/sessions/{session_id}.json`. Stores chat history and caches expensive pipeline state across turns. `_CACHEABLE_FIELDS` lists what is persisted (does NOT include `uploaded_files` or `supplementary_uploads`). Key functions: `build_session_id()`, `load_session()`, `save_session()`, `append_turn()`, `cache_pipeline_state()`, `get_task_plan()`, `update_task_plan()`, `delete_session()`, `delete_all_sessions()`, `wipe_storage_only()`, `wipe_all_data()`.
- **`pipeline_log.py`** — `log_step()` produces structured log entries (node name, status, duration, detail) returned to the frontend for pipeline execution visualization.

### Backend Routes & App
- **`app.py`** — FastAPI app, CORS middleware (allows `localhost:5173`), mounts all routers
- **`routes/brightspace.py`** — Brightspace API proxy routes under `/api`
- **`routes/chat.py`** — LangGraph pipeline + session management + to-do APIs under `/api`
- **`routes/upload.py`** — `POST /api/upload` — saves file to `storage/uploads/` with UUID name; returns `{file_id, file_name, path}`
- **`routes/calendar.py`** — `POST /api/add-event` — Google Calendar integration via Clerk OAuth tokens
- **`dependencies.py`** — `get_bs_token()` extracts Bearer token from request headers
- **`brightspace_auth.py`** — Playwright SSO automation in `ThreadPoolExecutor`
- **`database.py`** — Async Supabase client factory

### Frontend (React + TypeScript + Tailwind)
- **`src/App.tsx`** — Root component, manages auth state
- **`src/lib/api.ts`** — Axios instance with baseURL `http://localhost:8000/api`, auto-injects Bearer token
- **`src/components/Dashboard.tsx`** — Three-column layout: course sidebar, chat area, collapsible tasks sidebar. Manages `checkedTopicsMap` (selected topics), `assignmentUploadsMap` (persisted upload metadata for link-only assignments, stored in `localStorage` as `assignment_upload_{taskId}`).
- **`src/components/Sidebar.tsx`** — Course list + recursive content tree (lazy-loads modules/topics). Emits `onTopicToggle` for each selectable topic.
- **`src/components/TasksSidebar.tsx`** — Fetches `/api/dashboard/work`; groups tasks by course sorted by due date; color-codes urgency (red = overdue, amber = ≤3 days, gray = normal). Collapsible. Shows AI-generated to-do checklist per assignment.
- **`src/components/ChatArea.tsx`** — Full chat implementation with SSE streaming. Sends to `/api/chat/stream` with assignment context + selected topics + chat history + `uploaded_files`. Renders `react-markdown` with `remark-gfm`, `remark-math`, and `rehype-katex`. Shows pipeline log trace. Handles `hasOnlyExternalLinks` (link-only assignment banner) — blocks chat until file uploaded. Persists history per-task in `localStorage` (`chat_{task_id}`).

## API Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/auth/login` | None | Login via Playwright SSO, returns Bearer token |
| GET | `/api/courses` | Bearer | List active semester courses |
| GET | `/api/dashboard/work` | Bearer | Pending assignments & quizzes across all courses |
| GET | `/api/courses/{id}/modules` | Bearer | Root content modules for a course |
| GET | `/api/courses/{id}/modules/{mid}` | Bearer | Children of a module |
| GET | `/api/courses/{id}/files/{tid}/download` | Bearer | Stream file download |
| GET | `/api/assignments/{org_unit_id}/{folder_id}` | Bearer | Assignment detail (instructions, attachments, scoring) |
| GET | `/api/courses/{org_unit_id}/assignments/{folder_id}/attachments/{file_id}/download` | Bearer | Download assignment attachment |
| POST | `/api/upload` | Bearer | Upload file to local storage, returns `{file_id, file_name, path}` |
| POST | `/api/chat/stream` | Bearer | LangGraph pipeline via SSE; emits `progress` + final `result` events |
| DELETE | `/api/sessions/id/{session_id}` | Bearer | Delete session by session_id string |
| DELETE | `/api/sessions/{course_id}/{assignment_id}` | Bearer | Delete session by course+assignment IDs |
| DELETE | `/api/sessions` | Bearer | Delete all session JSON files |
| DELETE | `/api/data` | Bearer | Wipe all data (sessions + storage) |
| DELETE | `/api/storage` | Bearer | Wipe only heavy storage (uploads + chroma + manifests) |
| GET | `/api/sessions/{session_id}/todos` | Bearer | Fetch to-do list for session |
| PATCH | `/api/sessions/{session_id}/todos` | Bearer | Update full to-do list for session |
| POST | `/api/add-event` | Clerk | Create Google Calendar event |

## SSE Stream Protocol

`POST /api/chat/stream` sends `text/event-stream`:
- `data: {"type": "progress", "node": "..."}` — emitted after each pipeline node completes
- `data: {"type": "result", "response": "...", "session_id": "...", "pipeline_log": [...], "inaccessible_topics": [...], "too_long_videos": [...], "task_plan": [...], "context_mode": "..."}` — final payload

## Brightspace API Details
- **Base URL**: `https://learn.truman.edu`
- **API versions**: LP `1.57`, LE `1.92`
- **Course filtering**: `Access.IsActive == True` AND `Type.Code == "Course Offering"` AND name starts with `SP`/`SM`/`FA`
- **Content tree**: Type 0 = module (recurse), Type 1 = topic (leaf). TopicType 1 = downloadable file, TopicType 3 = link
- **Pagination**: Enrollments use `Bookmark` in `PagingInfo`, quizzes use `Next`

## Environment Variables (`backend/.env`)
```
BS_USER, BS_PASS                            # Truman SSO credentials
SUPABASE_URL, SUPABASE_KEY                  # Supabase connection
OPENAI_API_KEY                              # Required for LLM calls, embeddings, Whisper transcription
TOKEN_THRESHOLD=4000                        # Token gate: below = inject, above = RAG
LLM_MODEL=gpt-4o                            # Model for summaries, extraction, rewriting, responses
EMBEDDING_MODEL=text-embedding-3-small      # Model for ChromaDB embeddings
MAX_CONTEXT_TOKENS=60000                    # Token budget for responder message assembly
```

## Key Constraints

- Playwright must use `sync_playwright` in a `ThreadPoolExecutor` on Windows — `async_playwright` causes `NotImplementedError` under uvicorn's event loop
- The Brightspace token is opaque and short-lived; passed through from client to Brightspace on every request (no server-side storage)
- Students don't have access to `/orgstructure/` endpoints (returns 403), so course filtering uses the name-prefix heuristic
- All LangGraph nodes run synchronously (sync httpx, sync pymupdf); the graph is invoked via `astream()` from the async FastAPI route
- `effective_course_id = 0` for freeform mode — never guard ChromaDB calls with `if course_id:` (falsy); use `if course_id is not None:`
- `supplementary_uploads` (non-main uploaded files) must always be emitted by `pdf_parser` even when empty, to prevent stale LangGraph state carrying over across turns
- Material fetcher skip conditions must check `supp_uploads_pending` before skipping, or supplementary files get silently dropped
- Runtime print statements must avoid Unicode arrows/special chars on Windows (cp1252 console encoding)
- Video transcription via Whisper: 10-minute / 25MB hard limits enforced before API call

## Implementation Status

All core phases complete:
- **Phase 1** (PDF parsing): done — pymupdf + OCR fallback + video transcription
- **Phase 2** (context handling): done — inject vs. RAG routing based on token count
- **Phase 3** (material extraction): done — LLM structured output
- **Phase 4** (material fetching): done — fuzzy match + Chroma embed + dedup manifest
- **Phase 5** (query rewriting): done — 2-3 diverse LLM queries
- **Phase 6** (RAG response): done — multi-query ChromaDB retrieval + grounded LLM response
- **Phase 7** (chat persistence): done — `utils/session.py` (backend JSON) + `localStorage` (frontend per-task)
- **Phase 8** (error handling): not started
- **Task planner**: done — AI-generated to-do checklist per assignment, editable from frontend
