# Tech Stack (Shared)

This document is a repo-wide tech reference used across specs (including Spec 3).

## Backend

### Language & Runtime
- Python (3.11+)

### Web API
- FastAPI (ASGI framework)
- Uvicorn (ASGI server)

### Data Modeling & Config
- Pydantic (v2) for:
  - Domain models (e.g. `Project`)
  - Request/response schemas
- `pydantic-settings` (or equivalent) for typed settings
- YAML (`PyYAML`) for environment/config files

### NLP / Text Processing (Deterministic glue)
- Python stdlib `re` for cleanup + normalization rules
- `ftfy` (optional) for fixing encoding/Unicode weirdness
- Sentence/paragraph segmentation:
  - Lightweight: `blingfire` (fast), or
  - Heavier: `spacy` (if you need richer parsing later)
- Language detection (optional): `langdetect` or fastText-based detector
- Fuzzy matching / cleanup helpers (optional): `rapidfuzz`
- Token counting & chunking for LLM calls: `tiktoken` + internal chunker utilities

### Persistence
- Primary: MongoDB
  - Access via `motor` or an ODM like **Beanie**
- Optional local mode (config-driven):
  - Local MongoDB container, or
  - Simple JSON/SQLite-based storage for Projects

### Background Jobs (Spec 3+ recommended)
- Redis + RQ (simple) or Celery (heavier) for long-running steps (transcribe/outline/ebook), retries, and status polling.

### Logging & Observability
- Loguru for structured, ergonomic logging
- Prometheus Python client for metrics (e.g. `/metrics` endpoint)
- (Later) Grafana or similar for dashboards (optional)

---

## LLM Providers & Orchestration (Spec 3+)

### Goal
Support multiple LLM vendors (OpenAI, Anthropic) behind a single internal interface, so Spec 3 can swap providers/models without rewriting business logic.

### SDKs (Python)
- OpenAI: `openai` (official `openai-python` SDK)
- Anthropic (Claude): `anthropic`

### Provider abstraction
- Add a thin internal interface, e.g. `llm/providers/base.py`:
  - `generate(...) -> LLMResult`
  - `stream(...) -> Iterator[LLMEvent]` (optional for v1)
  - `supports(feature) -> bool` (tools, JSON schema, multimodal, etc.)
- Implement adapters:
  - `OpenAIProvider`
  - `AnthropicProvider`

### Normalized request/response
- Define a vendor-neutral request model (Pydantic), e.g.:
  - `messages: list[ChatMessage]` where `ChatMessage = {role, content_parts}`
  - `content_parts` supports at least text (later: images/audio)
  - `response_format` supports “JSON schema” / “JSON mode” when available
- Normalize output into:
  - `text`
  - `tool_calls` (if applicable)
  - `usage` (tokens/cost if available)
  - `raw` (vendor payload for debugging)

### Reliability & ops
- Retries with exponential backoff for 429/5xx and transient network errors
- Per-request timeouts + a hard cap on total retries
- Log (structured): `provider`, `model`, `latency_ms`, `tokens_in/out`, and a correlation id

### Documentation references (for implementation)
- Keep "canonical" vendor docs as the source of truth.
- Store local snapshots used by Speckit/Claude for quick lookup:
  - `docs/refs/openai/chat_completions.md`
  - `docs/refs/anthropic/messages.md`
- Adapter contract: `docs/llm_adapter_contract.md`

---

## Frontend

### Core
- React
- TypeScript
- Vite (bundler/dev server) — SPA-style app

### UI & Styling
- Tailwind CSS
- (Optional but recommended) Headless component helpers:
  - Headless UI / Radix UI for primitives
  - Simple custom components for tabs, forms, modals

### State & Data Flow
- React Context for shared `Project` object across tabs (“Ground Zero” state)
- (Spec 3+) TanStack Query / React Query for async AI runs:
  - start run → poll status → fetch results
  - caching keyed by `project_id` / `run_id`

---

## DevOps / Tooling

### Version Control & CI
- GitHub + GitHub Actions for:
  - Linting & tests
  - Building Docker images

### Containerization & Env
- Docker for backend, frontend, MongoDB
- docker-compose for local multi-service dev

### Developer Experience
- Makefile for common tasks:
  - `make dev` (start stack)
  - `make test`
  - `make lint`
  - `make build`