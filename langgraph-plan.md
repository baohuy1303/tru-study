# LangGraph Multi-Agent Assignment Helper — Implementation Plan

## Overview

A multi-agent pipeline built with **LangGraph** and **LangChain** that ingests a student's assignment PDF, identifies referenced course materials, retrieves and embeds relevant content, and provides context-aware responses grounded in actual course materials.

**Stack:** LangGraph, LangChain, ChromaDB (local), JSON (local state), OpenAI/Anthropic LLM

---

## High-Level Flow

```
User Upload (PDF + prompt)
        │
        ▼
┌──────────────────────┐
│  Node 1: PDF Parser  │
│  & Token Evaluator   │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────────┐
│  Conditional: Token Gate │
│  ┌─────────┬───────────┐ │
│  │ SMALL   │ LARGE     │ │
│  │ <thresh │ ≥thresh   │ │
│  └────┬────┴─────┬─────┘ │
└───────┼──────────┼───────┘
        │          │
        ▼          ▼
   Inject as    Embed to Chroma
   context      + Generate Summary
        │          │
        ▼          ▼
   (both paths produce: assignment_summary + assignment_context_mode)
        │
        ▼
┌────────────────────────────┐
│  Node 2: Material          │
│  Reference Extractor       │
│  (Structured Output Agent) │
└──────────┬─────────────────┘
           │
           ▼
    List[MaterialReference]
           │
           ▼
┌────────────────────────────────┐
│  Node 3: Course Material       │
│  Fetcher & Embedder            │
│  - Hits course materials API   │
│  - Fuzzy matches references    │
│  - Checks Chroma metadata      │
│  - Downloads & embeds new ones │
└──────────┬─────────────────────┘
           │
           ▼
┌────────────────────────────────┐
│  Node 4: Query Rewriter       │
│  - Takes user prompt + chat    │
│    history + assignment summary│
│  - Generates 2-3 focused       │
│    retrieval queries           │
└──────────┬─────────────────────┘
           │
           ▼
┌────────────────────────────────┐
│  Node 5: Retriever + Response  │
│  - Queries Chroma with         │
│    rewritten queries           │
│  - Assembles final context     │
│  - Generates grounded response │
└────────────────────────────────┘
```

---

## Phase 1 — Project Scaffolding & State Definition

### Goal
Get the project structure, dependencies, and shared state model in place so every subsequent phase has a stable foundation.

### Tasks

**1.1 — Project structure.** Set up a clean directory layout separating graph logic, node implementations, utilities, storage, and config. Create a dedicated directory for local data (Chroma DB files, JSON manifests, chat history). Set up a `.env` for API keys, model names, token thresholds, and the course materials API base URL.

**1.2 — Dependencies.** Install and pin LangGraph, LangChain (core + community), ChromaDB, an embedding model package (OpenAI embeddings or `sentence-transformers`), `tiktoken` for token counting, `pymupdf` or `pdfplumber` for PDF parsing, `rapidfuzz` for string matching, and Pydantic for structured output schemas.

**1.3 — Shared state definition.** Define the `GraphState` TypedDict that flows through the entire graph. This is the contract every node reads from and writes to. Key fields: `user_prompt`, `chat_history`, `assignment_pdf_path`, `course_id`, `assignment_text`, `assignment_token_count`, `context_mode` (literal "inject" or "rag"), `assignment_summary`, `assignment_embedded` (bool), `material_references` (list of dicts), `embedded_materials` (list of filenames), `materials_metadata` (dict), `retrieval_queries` (list of strings), `retrieved_docs` (list of LangChain Documents), and `response` (string).

**1.4 — LangGraph skeleton.** Wire up the graph with placeholder nodes that just pass state through. Confirm the conditional routing works end-to-end by hardcoding a token count above and below threshold and verifying the correct path is taken. This gives you a runnable pipeline before any real logic exists.

**1.5 — Utility layer.** Build the small shared utilities you'll use everywhere: a token counting function (wrapping `tiktoken`), a ChromaDB client singleton that initializes the two collections (`course_materials` and `assignment`), and a JSON manifest loader/saver for the materials tracking file.

---

## Phase 2 — PDF Ingestion & Token Routing

### Goal
Take in a PDF, extract clean text, count tokens, and route to the correct processing path. At the end of this phase, the assignment is either fully available as injectable context or chunked and embedded in Chroma, and a summary always exists regardless of path.

### Tasks

**2.1 — PDF parser node.** Implement the first node using `pymupdf` (preferred for speed and table handling) or `pdfplumber` as a fallback. Strip headers, footers, page numbers, and encoding artifacts. Output cleaned `assignment_text` and `assignment_token_count` to state. Add a guard: if the PDF is image-based and extraction yields very little text, surface an error message rather than proceeding with garbage input.

**2.2 — Token gate conditional.** Implement the routing function. Define a `TOKEN_THRESHOLD` in config (start with ~4000, tune later based on your model's context window and how much budget you want to reserve for course materials and chat history). Return a string key that maps to the next node.

**2.3 — Small context handler node.** For PDFs under threshold: keep the full `assignment_text` in state for direct injection later, set `context_mode = "inject"` and `assignment_embedded = False`. Still generate an `assignment_summary` using an LLM call — this summary is used downstream by the query rewriter and the system prompt regardless of path. The summary should capture: what the assignment is asking, key deliverables, any grading criteria, and important constraints.

**2.4 — Large context handler node.** For PDFs over threshold: chunk the assignment text using `RecursiveCharacterTextSplitter` (start with chunk_size=1000, overlap=200), embed into Chroma's `assignment` collection with metadata (source, chunk_index, section if detectable), set `context_mode = "rag"` and `assignment_embedded = True`. Generate the same `assignment_summary` as the small path. This summary becomes the primary way the LLM "knows" the assignment without consuming the full token budget.

**2.5 — Validation.** Test with a short 1-page assignment (should route to inject) and a long 20-page syllabus-style PDF (should route to RAG). Verify the summary quality is sufficient in both cases by manually inspecting it. Confirm chunks in Chroma are retrievable with a basic similarity search.

---

## Phase 3 — Material Reference Extraction

### Goal
Parse the assignment text and produce a structured list of every course material referenced — slides, chapters, readings, papers, videos, labs — so the next phase knows what to fetch.

### Tasks

**3.1 — Define structured output schema.** Create Pydantic models: `MaterialReference` with fields `name` (string, e.g. "Chapter 5", "Week 3 Slides"), `material_type` (string, e.g. "chapter", "slides", "paper", "video", "lab"), and `context_hint` (string, the surrounding sentence for fuzzy matching context). Wrap in `ExtractedReferences` with a `references: list[MaterialReference]` field.

**3.2 — Build the extraction agent.** Use LangChain's `with_structured_output` on your LLM, passing the `ExtractedReferences` schema. Craft a system prompt that instructs the LLM to scan for both explicit references ("see Chapter 5", "refer to Lecture 3 slides") and implicit ones ("as discussed in class regarding normalization", "from the reading on distributed systems"). The `context_hint` field is important — it gives the fuzzy matcher in the next phase more signal than just a vague title.

**3.3 — Handle edge cases.** If the assignment has zero identifiable references, the node should return an empty list gracefully — this is valid (some assignments are self-contained). If the LLM hallucinates references that clearly don't exist (e.g. materials from a different course), the fuzzy matcher in Phase 4 will naturally filter them out via low confidence scores, so don't over-engineer validation here.

**3.4 — Feed the right input.** The agent should receive the full `assignment_text` (not the summary) regardless of context mode. The summary is lossy by design and might drop specific material references. Token cost here is a one-time expense per assignment, so it's worth it.

---

## Phase 4 — Course Material Fetching & Embedding

### Goal
Take the extracted references, match them against the actual course materials available via your backend API, download what's needed, and embed it into Chroma. Skip anything already embedded. This is the heaviest phase and where the most things can go wrong.

### Tasks

**4.1 — API integration.** Build a service layer that hits your course materials API (`GET /api/courses/{course_id}/materials` or whatever your endpoint looks like). Parse the response into a normalized list of available materials with at minimum: `material_id`, `name`, `file_type`, and a `download_url` or equivalent. Handle auth, timeouts, and error responses cleanly.

**4.2 — Fuzzy matching.** For each `MaterialReference` from Phase 3, score it against every item in the API catalog using `rapidfuzz` (token_sort_ratio works well for messy academic titles). Use both the `name` and `context_hint` fields. Set a confidence threshold (start at 0.6) — if the best match is below this, skip it and optionally log it for debugging. For anything above threshold, collect the matched `material_id` for download.

**4.3 — Manifest check (deduplication).** Before downloading any file, check the local `materials_manifest.json`. This file tracks every previously embedded file by filename and content hash. If the file exists in the manifest and the hash matches, skip it entirely. This makes subsequent runs for the same course near-instant. If the file exists but the hash differs (professor updated the file), mark it for re-embedding — delete old chunks from Chroma first, then re-embed.

**4.4 — Download and parse.** For each file that needs embedding: download from the API, parse to text (handle PDFs with `pymupdf`, DOCX with `python-docx`, PPTX with `python-pptx` — slides are common in courses). Normalize the text the same way you did for the assignment in Phase 2.

**4.5 — Chunk and embed.** Use `RecursiveCharacterTextSplitter` (same settings as Phase 2 for consistency). Attach metadata to every chunk: `source` (filename), `course_id`, `material_type`, `chunk_index`. Upsert into Chroma's `course_materials` collection. Update the local manifest with the filename, content hash, chunk count, and timestamp.

**4.6 — Conditional assignment embedding.** If `context_mode == "rag"` and the assignment hasn't been embedded yet (edge case: maybe the large context handler in Phase 2 failed partially), embed it here as a safety net. This keeps the embedding logic consolidated.

**4.7 — Empty state handling.** If no materials were matched or the API returned nothing, the node should still succeed and pass through cleanly. The response generator in Phase 6 can still work with just the assignment context.

---

## Phase 5 — Query Rewriting

### Goal
Transform the user's raw prompt into 2-3 semantically distinct retrieval queries that will actually return useful chunks from Chroma. This is the highest-leverage node in the pipeline for response quality.

### Tasks

**5.1 — Build the rewriter agent.** This is a focused LLM call, not a complex agent. Input: `user_prompt`, last 3-5 turns of `chat_history`, and `assignment_summary`. System prompt instructs the LLM to generate 2-3 search queries that are semantically diverse and optimized for embedding similarity search — meaning they should be descriptive, use relevant terminology from the course domain, and avoid vague language.

**5.2 — Use structured output.** Define a simple Pydantic model with a `queries: list[str]` field (min 2, max 3). This prevents the LLM from returning a paragraph instead of queries.

**5.3 — Quality considerations.** The rewriter should expand abbreviations and references. "Help with Q3" is useless for retrieval. But if the assignment summary mentions that Question 3 is about database normalization to third normal form, the rewriter should produce queries like "database normalization 1NF 2NF 3NF", "steps to normalize relational tables", and "normalization assignment question 3 requirements". Each query should target a different angle — one conceptual, one procedural, one assignment-specific. This diversity ensures you retrieve chunks that cover the topic from multiple perspectives.

**5.4 — Chat history awareness.** If the user is in a multi-turn conversation and says "what about the next part?", the rewriter needs chat history to understand what "next part" means. Feed the recent turns so the LLM can maintain continuity without you needing to do manual context tracking.

---

## Phase 6 — Retrieval & Response Generation

### Goal
Pull relevant chunks from Chroma using the rewritten queries, assemble a well-structured context window, and generate a final response that's grounded in actual course materials.

### Tasks

**6.1 — Multi-query retrieval.** For each query from Phase 5, run a similarity search against Chroma's `course_materials` collection (top_k=3 per query). If the assignment was embedded (RAG mode), also search the `assignment` collection (top_k=2 per query). Collect all results.

**6.2 — Deduplication and ranking.** Since multiple queries will often return overlapping chunks, deduplicate by chunk ID. If a chunk appears in results for multiple queries, boost its rank — it's likely highly relevant. Return the top 8-10 unique chunks sorted by combined relevance.

**6.3 — Context window assembly.** Build the final prompt in this order: system prompt (role definition, grounding instructions, citation guidance), assignment context (full text if inject mode, summary + retrieved assignment chunks if RAG mode), retrieved course material chunks (with source attribution so the LLM can cite them), recent chat history (last N turns, truncate oldest first if hitting token limits), and finally the current user prompt. Track cumulative tokens as you assemble — if you're approaching the model's context limit, drop chat history turns first, then reduce retrieved chunks, but never drop the assignment context or system prompt.

**6.4 — Response generation.** Call the LLM with the assembled prompt. The system prompt should instruct it to cite specific sources when possible ("According to Chapter 5...", "As shown in the Week 3 slides..."), provide step-by-step explanations when the user is working through problems, and avoid giving direct answers to graded questions — instead guide the student toward understanding.

**6.5 — State output.** Write the final `response` and `retrieved_docs` (for debugging and transparency) to state. The retrieved docs can optionally be surfaced to the user as "sources used" if your frontend supports it.

---

## Phase 7 — Chat Persistence & Multi-Turn Support

### Goal
Make the system work across multiple turns of conversation, not just a single prompt-response cycle. The graph currently runs once per user message — this phase makes subsequent runs fast and context-aware.

### Tasks

**7.1 — Chat history storage.** After each response, append both the user message and assistant response to `chat_history.json` (keyed by session ID). On the next invocation, load this history and inject it into the graph's initial state.

**7.2 — Skip redundant work on subsequent turns.** The first turn does the heavy lifting: PDF parsing, embedding, material fetching. On turns 2+, most of this is already done. Add early-exit logic: if `assignment_text` is already in state (loaded from a session cache or passed through), skip Node 1. If materials are already embedded (manifest check), Node 3 becomes a near-no-op. Only the query rewriter (Node 4) and retriever/responder (Node 5) need to run fresh every turn.

**7.3 — Session state caching.** Save the key state fields (assignment_text, assignment_summary, context_mode, material_references, embedded_materials) to a local JSON keyed by session ID. On subsequent turns, load this instead of re-running the pipeline from scratch. This turns a 30-second first run into a 2-3 second follow-up.

**7.4 — Conversation-aware retrieval.** The query rewriter already receives chat history, but verify it's actually using it well. Test with multi-turn scenarios: "explain normalization" → "can you give an example?" → "how does this apply to question 3?". Each query should build on prior context without the user needing to repeat themselves.

---

## Phase 8 — Error Handling, Edge Cases & Polish

### Goal
Harden the pipeline for demo reliability. At a hackathon, the demo gods are merciless — this phase is about making sure things degrade gracefully instead of crashing.

### Tasks

**8.1 — PDF parsing failures.** If `pymupdf` returns near-empty text (common with scanned/image PDFs), catch it and return a clear error: "This PDF appears to be image-based and couldn't be parsed. Please upload a text-based PDF." Optionally add `pytesseract` OCR as a fallback if you have time. (Add a placeholder function and we'll implement this later)

**8.2 — API failures.** If the course materials API is down or returns errors, the pipeline should still work — just skip material fetching and respond using only the assignment context. Then once the response is finished, tell the user to re-log in to refresh their token and try again. Log the failure but don't crash.

**8.3 — Empty retrieval results.** If Chroma returns no relevant chunks (low similarity scores across the board), the response generator should acknowledge this: "I couldn't find directly relevant course materials for this question, you can manually pick the files you'd like me to inspect as an alternative, but based on the assignment context and my general knowledge, here's my understanding..." rather than hallucinating citations. Or use the LLM own knowledge to answer the question the best way.

**8.4 — Token budget overflows.** Add a hard check before the final LLM call. If the assembled context exceeds the model's context window, truncate in priority order: chat history (oldest first), retrieved chunks (lowest relevance first), assignment context (switch from full text to summary if needed). Never truncate the system prompt.

**8.5 — Logging.** Add structured logging at each node boundary: what went in, what came out, how long it took, any errors. This is invaluable for debugging during the hackathon and for the demo Q&A.

**8.6 — Manifest corruption guard.** If the JSON manifest gets corrupted (partially written, invalid JSON), catch the parse error and rebuild from scratch rather than crashing. A simple try/except with a "re-embed everything" fallback is fine for a hackathon.

---

## Future Improvements (Post-Hackathon)

**Storage upgrades.** Swap local JSON for PostgreSQL (state, manifests, chat history). Swap ChromaDB for pgvector or Pinecone for better scalability and concurrent access.

**Smarter chunking.** Replace `RecursiveCharacterTextSplitter` with semantic chunking or document-structure-aware splitting (e.g., split by slide boundaries for PPTX, by section headers for textbooks).

**Reranking.** Add a cross-encoder reranker (like Cohere Rerank or a local `cross-encoder/ms-marco` model) between retrieval and response generation. This dramatically improves precision when you have lots of chunks.

**Async pipeline.** Make material downloads and embeddings parallel with `asyncio.gather`. Add a job queue for long-running first-time course setups.

**Dynamic token threshold.** Instead of a hardcoded threshold, calculate it based on the model's context window minus estimated budgets for course materials, chat history, and system prompt.

**User feedback loop.** Let users flag bad responses. Store these and use them to refine prompts, adjust retrieval parameters, or identify missing course materials.

**Multi-assignment support.** Allow students to switch between assignments within the same course without re-embedding shared materials. The manifest and Chroma metadata already support this — just need session management on top.
