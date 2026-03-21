# TruStudy 🎓
### AI Study Platform for Truman State Students
> Hackathon Build Plan

---

## Tech Stack

| Layer | Tech |
|---|---|
| Frontend | React, Tailwind CSS |
| Backend | FastAPI (Python) |
| AI | LangGraph + Claude/GPT-4o |
| RAG | Supabase pgvector + PyMuPDF |
| Database | Supabase (PostgreSQL) |
| Brightspace | Playwright (login) + Valence REST API |
| Calendar | Google Calendar MCP |

---

## Brightspace API Reference

| What you need | Endpoint | Docs |
|---|---|---|
| Auth concepts | OAuth 2.0 / token | [First Steps](https://docs.valence.desire2learn.com/basic/firstlist.html) |
| Student's courses | `GET /d2l/api/lp/{ver}/enrollments/myenrollments/` | [Enrollments](https://docs.valence.desire2learn.com/res/enroll.html) |
| Assignments + due dates | `GET /d2l/api/le/{ver}/{orgUnitId}/dropbox/folders/` | [Dropboxes](https://docs.valence.desire2learn.com/res/dropbox.html) |
| Quizzes + due dates | `GET /d2l/api/le/{ver}/{orgUnitId}/quizzes/` | [Quizzes](https://docs.valence.desire2learn.com/res/quiz.html) |
| Course files & slides | `GET /d2l/api/le/{ver}/{orgUnitId}/content/toc` | [Content](https://docs.valence.desire2learn.com/res/content.html) |
| Pending work (to-do) | `GET /d2l/api/le/{ver}/updates/myUpdates/` | [Updates](https://docs.valence.desire2learn.com/res/updates.html) |
| Calendar events | `GET /d2l/api/le/{ver}/{orgUnitId}/calendar/events/` | [Calendar](https://docs.valence.desire2learn.com/res/calendar.html) |

> **Auth strategy for hackathon:** Use Playwright to log in once via Truman SSO → intercept the `Authorization: Bearer <token>` header from any outgoing API call → use that token for all subsequent FastAPI → Brightspace API calls directly.

---

## Features (Priority Order)

### 🔴 P0 — Must Ship
- Brightspace login via Playwright → capture Bearer token (https://learn.truman.edu/d2l/login)
- Pull all courses, assignments, quizzes, and due dates
- Pull all uploaded course files per course
- Assignment dashboard (list, grouped by course, with deadlines)
- Per-assignment AI chat (assignment instructions fed as context)
- File selector (student ticks files → auto-download → RAG)
- Google Calendar MCP → push all deadlines automatically on login

### 🟡 P1 — Should Ship
- Learning Mode (AI teaches concepts, leads to answer, doesn't give it)
- Auto to-do checklist generated per assignment in Learning Mode
- Syllabus upload → extract exam dates → push to calendar
- Custom open chat (not tied to a specific assignment)

### 🟢 P2 — Nice to Have
- Danger week indicator (due date clustering visualized)
- AI-generated diagrams / multimodal explanations

---

## System Flow

```
Student logs in
      │
      ▼
Playwright → Truman SSO → capture Bearer token
      │
      ▼
FastAPI calls Brightspace REST API
      ├── Enrollments   → list of courses
      ├── Dropbox       → assignments + due dates + instructions
      ├── Quizzes       → quiz deadlines
      └── Content TOC   → all uploaded files per course
      │
      ▼
Store in Supabase (courses, assignments, file manifests)
Push deadlines → Google Calendar via MCP
      │
      ▼
Student clicks assignment
      │
      ├── Agent reads assignment instructions
      ├── Auto-suggests relevant course files
      ├── Student confirms / ticks additional files
      ├── Files downloaded → chunked → embedded → pgvector
      └── LangGraph agent answers (Answer Mode) or teaches (Learning Mode)
```

---

## Data Models (Supabase)

```
users             → id, brightspace_token, email
courses           → id, user_id, brightspace_org_unit_id, name
assignments       → id, course_id, name, instructions, due_date, type
course_files      → id, course_id, name, brightspace_url, indexed (bool)
chat_sessions     → id, assignment_id, user_id, mode (answer|learn), messages[]
```

> Vector embeddings stored in a separate `documents` table with pgvector.
> Delete embeddings after 7 days to keep storage clean.

---

## Build Timeline

### Day 1
| Time | Goal |
|---|---|
| 9–11am | Playwright login + token capture + Brightspace API calls working |
| 11am–1pm | FastAPI routes: courses, assignments, files |
| 1–2pm | Lunch + Supabase schema setup |
| 2–5pm | RAG pipeline: download → chunk → embed → query |
| 5–8pm | React frontend: login flow + assignment dashboard |

### Day 2
| Time | Goal |
|---|---|
| 9–11am | Per-assignment chat UI + AI integration (Answer Mode) |
| 11am–1pm | File selector UI + Learning Mode |
| 1–2pm | Lunch |
| 2–4pm | Google Calendar MCP integration |
| 4–5:30pm | Bug fixes, polish UI, inline code comments, README |
| 5:30–6pm | Record demo video, prep presentation |

---

## Presentation Structure
1. **The problem** — "Every Truman student copy-pastes PDFs into ChatGPT and loses context"
2. **Why existing tools fail** — generic, no Brightspace integration, manual work
3. **Live demo** — login → assignments appear → click one → tick files → AI helps
4. **Learning Mode demo** — show it teaching, not answering
5. **Google Calendar** — show deadline popping into calendar live
6. **Impact** — every Truman student, every semester, every course
