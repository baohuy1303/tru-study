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

Both servers must run simultaneously. Frontend proxies API calls to the backend.

## Architecture

### Auth Flow
Frontend → `POST /api/auth/login` with username/password → Backend runs **Playwright** (sync, in ThreadPoolExecutor) to automate Truman CAS SSO login → intercepts Bearer token from Brightspace API traffic → returns token to frontend → frontend stores in `localStorage` → all subsequent API calls include `Authorization: Bearer <token>` header.

### LangGraph Pipeline (`backend/agents/`)

The core AI system is a LangGraph StateGraph with conditional routing. All nodes share `GraphState` (TypedDict in `agents/state.py`).

**Flow:**
```
pdf_parser → token_gate (conditional)
  ├── small (<4000 tokens) → small_context_handler
  └── large (≥4000 tokens) → large_context_handler
→ material_extractor → material_fetcher → query_rewriter → responder → END
```

**Nodes** (in `agents/nodes/`):
1. **`pdf_parser`** — Extracts text from 3 sources: Brightspace instructions, PDF attachments (auto-downloaded via API), uploaded PDFs. Uses `pymupdf`. Counts tokens with `tiktoken`.
2. **`context_handler`** — Two handlers based on token count. Small: injects full text + generates exhaustive LLM summary. Large: generates concise summary + chunks/embeds into ChromaDB (`assignment_{id}` collection).
3. **`material_extractor`** — LLM structured output (`with_structured_output(ExtractedReferences)`) to find referenced course materials (chapters, slides, labs) in assignment text.
4. **`material_fetcher`** — Walks Brightspace content tree, fuzzy-matches references against catalog (`rapidfuzz`, threshold 60), checks Chroma for existing embeddings, downloads new files, chunks/embeds into `course_materials_{id}` collection.
5. **`query_rewriter`** — *Placeholder (Phase 5 TODO)*. Currently passes user prompt through as-is.
6. **`responder`** — *Placeholder (Phase 6 TODO)*. Should do multi-query ChromaDB retrieval + grounded LLM response.

**Entry point:** `POST /api/chat` in `routes/chat.py` → `build_graph()` in `agents/graph.py`.

### Backend Utilities (`backend/utils/`)
- **`chroma.py`** — Persistent ChromaDB client (`storage/chroma/`). Two collection types: `assignment_{id}` and `course_materials_{id}`.
- **`manifest.py`** — JSON dedup manifests at `storage/manifests/{course_id}.json` tracking embedded materials (content_hash, chunk_count, timestamp).
- **`brightspace.py`** — Recursive content tree walker. `get_content_catalog()` returns flat list of all topics with module paths.
- **`pdf.py`** — `extract_text_from_pdf(path)` and `extract_text_from_bytes(bytes)` via `pymupdf`.
- **`tokens.py`** — `count_tokens(text)` via `tiktoken`.

### Backend Routes & App
- **`app.py`** — FastAPI app, CORS middleware (allows localhost:5173), mounts routers
- **`routes/brightspace.py`** — Brightspace API proxy routes under `/api`
- **`routes/chat.py`** — LangGraph pipeline endpoint under `/api`
- **`dependencies.py`** — `get_bs_token()` extracts Bearer token from request headers
- **`brightspace_auth.py`** — Playwright SSO automation in `ThreadPoolExecutor`
- **`database.py`** — Async Supabase client factory

### Frontend (React + TypeScript + Tailwind)
- **`src/App.tsx`** — Root component, manages auth state
- **`src/lib/api.ts`** — Axios instance with baseURL `http://localhost:8000/api`, auto-injects Bearer token
- **`src/components/Dashboard.tsx`** — Three-column layout: course sidebar, chat area, tasks sidebar
- **`src/components/Sidebar.tsx`** — Course list + recursive content tree (lazy-loads modules/topics)
- **`src/components/TasksSidebar.tsx`** — Pending assignments/quizzes with urgency indicators
- **`src/components/ChatArea.tsx`** — Assignment detail view with instructions, attachments, and chat input (chat not yet wired to `/api/chat`)

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
| POST | `/api/chat` | Bearer | LangGraph pipeline (prompt, course context, assignment) |

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
OPENAI_API_KEY                              # Required for LLM summaries, embeddings, material extraction
TOKEN_THRESHOLD=4000                        # Token gate: below = inject, above = RAG
LLM_MODEL=gpt-4o                            # Model for summaries & structured extraction
EMBEDDING_MODEL=text-embedding-3-small      # Model for vector embeddings
```

## Key Constraints

- Playwright must use `sync_playwright` in a `ThreadPoolExecutor` on Windows — `async_playwright` causes `NotImplementedError` under uvicorn's event loop
- The Brightspace token is opaque and short-lived; passed through from client to Brightspace on every request (no server-side storage)
- Students don't have access to `/orgstructure/` endpoints (returns 403), so course filtering uses the name-prefix heuristic
- All LangGraph nodes run synchronously (sync httpx, sync pymupdf); the graph is invoked via `ainvoke()` from the async FastAPI route
- Material fetcher checks Chroma metadata (`topic_id`) before re-downloading/embedding — manifest JSON is a secondary dedup layer
- Runtime print statements must avoid Unicode arrows/special chars on Windows (cp1252 console encoding)

## Implementation Status

Phases 1-4 of `langgraph-plan.md` are complete. Phases 5 (query rewriting) and 6 (retrieval + response) are placeholders. Phases 7 (chat persistence) and 8 (error handling) are not yet started.
