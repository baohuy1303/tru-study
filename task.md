# Backend API Routing & Implementation Plan

This document outlines the API routes we will build in FastAPI, mapping directly to the logic established in `test_brightspace.py`.

## Application Build Task List

- [x] Initial Infrastructure Setup (FastAPI, React, Tailwind, Supabase)
- [ ] Implement FastAPI Router structure (`routes/brightspace.py` and `dependencies.py`)
- [ ] `POST /api/auth/login`: SSO login via Playwright, capture token, return user info.
- [ ] `GET /api/courses`: Fetch and filter active enrollments.
- [ ] `GET /api/dashboard/work`: Aggregate pending assignments, quizzes, and overdue items cross-course.
- [ ] `GET /api/courses/{org_unit_id}/modules`: Fetch root content modules.
- [ ] `GET /api/courses/{org_unit_id}/modules/{module_id}`: Fetch children of a content module.
- [x] `GET /api/courses/{org_unit_id}/files/{topic_id}/download`: Simple proxy for downloading course files.

---

## Detailed Endpoint Logic

### 1. Authentication
**Endpoint**: `POST /api/auth/login`
- **Action**: Accepts `username` and `password`. Calls the existing `get_brightspace_token()` Playwright script. 
- **Follow-up**: Calls `/users/whoami` to verify identity and returns `Identifier` (userId), `FirstName`, `LastName`, and the `Bearer Token` to the frontend.

### 2. Courses
**Endpoint**: `GET /api/courses`
- **Action**: Uses the student's Bearer token to fetch `/enrollments/myenrollments/` (handling pagination).
- **Logic**: Filters for `IsActive == True`, `Type.Code == "Course Offering"`, and specific current-term prefixes (e.g., SP/SM/FA).
- **Returns**: A clean list of `[{id: orgUnitId, name: courseName, end_date: ...}]`.

### 3. Student Work Dashboard
**Endpoint**: `GET /api/dashboard/work`
- **Action**: Aggregates the student's entire workload for the active term.
- **Logic**: 
  - Resolves active courses via `GET /api/courses` logic internally.
  - Fetches cross-course overdue items (`/overdueItems/myItems`).
  - Iterates active `orgUnitId`s to fetch future, unsubmitted dropboxes (`/dropbox/folders/`) and quizzes (`/quizzes/`).
- **Returns**: A unified object grouped by course, indicating exactly what needs to be done.

### 4. Course Content Modules (Root)
**Endpoint**: `GET /api/courses/{org_unit_id}/modules`
- **Action**: Fetches the top-level content modules for a course.
- **Logic**: Calls Brightspace `/content/root/`.
- **Returns**: List of top-level modules. Frontend can display these as root folders for the user to click into.

### 5. Course Content Module Children
**Endpoint**: `GET /api/courses/{org_unit_id}/modules/{module_id}`
- **Action**: Fetches the children (sub-modules and file topics) of a specific module.
- **Logic**: Calls Brightspace `/content/modules/{moduleId}/structure/`.
- **Returns**: List of items (Type 0 = Module, Type 1 = Topic). Frontend can use this to let the user navigate the content tree step-by-step.

### 6. File Download Proxy
**Endpoint**: `GET /api/courses/{org_unit_id}/files/{topic_id}/download`
- **Action**: Proxies the raw binary download from Brightspace.
- **Logic**: A simple proxy using `httpx` to fetch the `/content/topics/{topicId}/file` streaming response and return it directly to the frontend.

---

## Proposed Project Structure Updates
1. Create directory `backend/routes/`.
2. Create `backend/routes/brightspace.py` containing an `APIRouter`.
3. Create `backend/dependencies.py` providing a dependency `get_bs_client(request: Request)` that abstracts `httpx.AsyncClient` setup with the incoming Bearer token from the frontend.
4. Mount `routes/brightspace.py` into `backend/app.py`.
