# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TruStudy is an AI study platform for Truman State University students. It integrates with Brightspace (D2L) LMS via Playwright-automated SSO login and the Valence REST API, then provides an AI-assisted learning interface with RAG capabilities.

## Development Commands

### Frontend (from `frontend/`)
```bash
npm run dev        # Vite dev server on http://localhost:5173
npm run build      # TypeScript check + Vite production build
npm run lint       # ESLint
npm run preview    # Preview production build
```

### Backend (from `backend/`)
```bash
source venv/Scripts/activate          # Activate Python venv (Windows/Git Bash)
uvicorn app:app --reload              # FastAPI dev server on http://localhost:8000
python test_brightspace.py            # Integration test (requires BS_USER/BS_PASS in .env)
pip install -r requirements.txt       # Install dependencies
```

Both servers must run simultaneously. Frontend proxies API calls to the backend.

## Architecture

### Auth Flow
Frontend → `POST /api/auth/login` with username/password → Backend runs **Playwright** (sync, in ThreadPoolExecutor) to automate Truman CAS SSO login → intercepts Bearer token from Brightspace API traffic → returns token to frontend → frontend stores in `localStorage` → all subsequent API calls include `Authorization: Bearer <token>` header.

### Backend (FastAPI + Python)
- **`app.py`** — FastAPI app, CORS middleware (allows localhost:5173), mounts router
- **`routes/brightspace.py`** — All API routes under `/api` prefix. Uses `httpx.AsyncClient` to call Brightspace Valence REST API
- **`dependencies.py`** — `get_bs_token()` FastAPI dependency extracts Bearer token from request headers
- **`brightspace_auth.py`** — Playwright SSO automation. Uses `sync_playwright` in `ThreadPoolExecutor` (not async) to avoid Windows uvicorn event loop issues
- **`database.py`** — Async Supabase client factory
- **`test_brightspace.py`** — Standalone integration test for all Brightspace API endpoints

### Frontend (React + TypeScript + Tailwind)
- **`src/App.tsx`** — Root component, manages auth state (logged in vs login screen)
- **`src/lib/api.ts`** — Axios instance with baseURL `http://localhost:8000/api`, auto-injects Bearer token from localStorage
- **`src/components/Login.tsx`** — SSO login form
- **`src/components/Dashboard.tsx`** — Three-column layout: course sidebar, chat area, tasks sidebar
- **`src/components/Sidebar.tsx`** — Course list + recursive content tree (lazy-loads modules/topics)
- **`src/components/TasksSidebar.tsx`** — Pending assignments/quizzes with urgency indicators
- **`src/components/ChatArea.tsx`** — AI chat placeholder (not yet connected)

### Brightspace API Details
- **Base URL**: `https://learn.truman.edu`
- **API versions**: LP `1.57`, LE `1.92`
- **Course filtering**: `Access.IsActive == True` AND `Type.Code == "Course Offering"` AND name starts with `SP`/`SM`/`FA` (Spring/Summer/Fall)
- **Work filtering**: Only items with `DueDate > now` (future due dates)
- **Content tree**: Type 0 = module (has children), Type 1 = topic (leaf). TopicType 1 = downloadable file
- **Pagination**: Enrollments use `Bookmark` in `PagingInfo`, quizzes use `Next`

## API Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/auth/login` | None | Login via Playwright SSO, returns Bearer token |
| GET | `/api/courses` | Bearer | List active semester courses |
| GET | `/api/dashboard/work` | Bearer | Pending assignments & quizzes across all courses |
| GET | `/api/courses/{id}/modules` | Bearer | Root content modules for a course |
| GET | `/api/courses/{id}/modules/{mid}` | Bearer | Children of a module (sub-modules + topics) |
| GET | `/api/courses/{id}/files/{tid}/download` | Bearer | Stream file download from Brightspace |

## Key Constraints

- Playwright must use `sync_playwright` in a `ThreadPoolExecutor` on Windows — `async_playwright` causes `NotImplementedError` under uvicorn's event loop
- The Brightspace token is opaque and short-lived; it's passed through from client to Brightspace on every request (no server-side storage)
- Students don't have access to `/orgstructure/` endpoints (returns 403), so course filtering uses the name-prefix heuristic
- Backend `.env` requires: `BS_USER`, `BS_PASS`, `SUPABASE_URL`, `SUPABASE_KEY`
