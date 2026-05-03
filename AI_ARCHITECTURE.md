# TruStudy - Agent Architecture

TruStudy uses a **LangGraph StateGraph** pipeline to process university assignments and answer student questions with grounded, RAG-backed responses. Every chat message flows through the full pipeline; nodes skip work when results are already cached from a prior turn.

---

## Pipeline Diagram

```mermaid
flowchart TD
    START([User Message]) --> PP

    PP["**pdf_parser**\nExtract text from instructions,\nPDF attachments, uploaded files,\nvideo transcripts (Whisper)"]

    PP --> TG{Token Gate}
    TG -- "< threshold\n(inject mode)" --> SCH
    TG -- "≥ threshold\n(RAG mode)" --> LCH

    SCH["**small_context_handler**\nInject full text into context\nGenerate exhaustive LLM summary"]
    LCH["**large_context_handler**\nGenerate concise LLM summary\nChunk + embed → assignment_{id} (ChromaDB)"]

    SCH --> ME
    LCH --> ME

    ME["**material_extractor**\nLLM structured output\nFind referenced chapters, slides, labs\nin assignment text"]

    ME --> TP

    TP["**task_planner**\nLLM structured output\nGenerate ordered to-do checklist\nfor the student (first turn only)"]

    TP --> MF

    MF["**material_fetcher**\nFuzzy-match references → Brightspace\ncontent tree (rapidfuzz, threshold 60)\nDownload + chunk + embed new files\n→ course_materials_{id} (ChromaDB)\nAlso processes supplementary uploads\nand sidebar-selected topics"]

    MF --> QR

    QR["**query_rewriter**\nLLM generates 2-3 semantically\ndiverse retrieval queries from\nprompt + summary + chat history"]

    QR --> R

    R["**responder**\nMulti-query ChromaDB retrieval\nfrom course_materials + assignment\ncollections. Dedup + rank chunks.\nToken-budgeted message assembly.\nLLM response in Learning / Buddy / Lazy mode"]

    R --> END([Streaming Response])

    style PP fill:#1e1e2e,stroke:#aa3bff,color:#f3f4f6
    style SCH fill:#1e1e2e,stroke:#aa3bff,color:#f3f4f6
    style LCH fill:#1e1e2e,stroke:#aa3bff,color:#f3f4f6
    style ME fill:#1e1e2e,stroke:#aa3bff,color:#f3f4f6
    style TP fill:#1e1e2e,stroke:#aa3bff,color:#f3f4f6
    style MF fill:#1e1e2e,stroke:#aa3bff,color:#f3f4f6
    style QR fill:#1e1e2e,stroke:#aa3bff,color:#f3f4f6
    style R fill:#1e1e2e,stroke:#aa3bff,color:#f3f4f6
    style TG fill:#2e2e3e,stroke:#c084fc,color:#f3f4f6
    style START fill:#aa3bff,stroke:#aa3bff,color:#fff
    style END fill:#aa3bff,stroke:#aa3bff,color:#fff
```

---

## Shared State

All nodes read from and write to a single `GraphState` TypedDict. LangGraph merges each node's returned dict into the shared state - nodes only return the keys they modify.

Key state fields:

| Field | Set by | Used by |
|---|---|---|
| `assignment_text` | `pdf_parser` | `context_handler`, `material_extractor` |
| `assignment_summary` | `context_handler` | `task_planner`, `query_rewriter`, `responder` |
| `context_mode` (`inject`/`rag`) | `context_handler` | `responder` |
| `material_references` | `material_extractor` | `material_fetcher` |
| `task_plan` | `task_planner` | cached in session, returned to frontend |
| `supplementary_uploads` | `pdf_parser` | `material_fetcher` |
| `user_selected_topics` | request input | `material_fetcher` |
| `embedded_materials` | `material_fetcher` | cached in session |
| `effective_course_id` | `material_fetcher` | `responder` |
| `retrieval_queries` | `query_rewriter` | `responder` |
| `response` | `responder` | returned to frontend |

---

## Multi-Turn Caching

On the first message for an assignment, the full pipeline runs. Expensive results are persisted in a JSON session file (`storage/sessions/{session_id}.json`):

- `assignment_text`, `assignment_summary`, `assignment_token_count`, `context_mode`
- `material_references`, `embedded_materials`
- `task_plan`

On subsequent turns, `pdf_parser` and `context_handler` detect the cached summary and skip extraction and embedding entirely. `material_fetcher` skips re-downloading already-embedded materials (deduped by manifest + ChromaDB metadata).

`uploaded_files` and `supplementary_uploads` are **not** cached - they are re-derived from the request on every turn so uploads are always current.

---

## ChromaDB Collections

| Collection | Contains | Queried by |
|---|---|---|
| `assignment_{id}` | Chunked assignment text (RAG mode only) | `responder` |
| `course_materials_{course_id}` | Course files, selected topics, supplementary uploads | `responder` |
| `course_materials_0` | Freeform uploads (no assignment selected) | `responder` |

> **Gotcha:** `effective_course_id = 0` for freeform mode. All guards must use `is not None` checks - `if course_id:` treats 0 as falsy and silently skips retrieval.

---

## Response Modes

The `responder` node switches system prompts based on the `mode` field in the request:

| Mode | Behavior |
|---|---|
| `learning` | Socratic - asks what the student already knows, nudges rather than answers |
| `neutral` (Buddy) | Helpful and conversational, occasionally checks understanding |
| `lazy` | Gives the answer directly with minimal explanation |
