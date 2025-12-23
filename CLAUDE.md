# webinar2ebook_v2 — Claude/Speckit Guidance (Minimal)

This file is intentionally minimal to avoid drift. Do not duplicate package versions here.

## Source of truth
- Tech stack: `specs/001-frontend-shell/spec0_tech.md`
- LLM adapter contract: `docs/llm_adapter_contract.md`
- Current feature plan/tasks: `specs/003-tab1-ai-assist/plan.md` and `specs/003-tab1-ai-assist/tasks.md`
- OpenAI snapshot ref: `docs/refs/openai/chat_completions.md`
- Anthropic snapshot ref: `docs/refs/anthropic/messages.md`

## Provider policy (Spec 3)
- Default LLM provider: **OpenAI**
- Fallback provider: **Anthropic**
- Fallback triggers: **429, 5xx, timeouts** (optionally invalid structured output when required)

## Repo basics
- Backend: FastAPI (Python 3.11+), Pydantic v2
- Frontend: React + TypeScript + Vite + Tailwind
- Database: MongoDB (motor)

## Commands
See `spec0_tech.md` (and repo README if present).

## Active Technologies
- Python 3.11 (backend), TypeScript 5.x (frontend) (004-tab3-style-visuals-schemas)
- MongoDB (projects), local filesystem (file uploads) (004-tab3-style-visuals-schemas)
- Python 3.11 (backend), TypeScript 5.x (frontend) + FastAPI, Pydantic v2, React, Tailwind CSS, Pillow, motor (MongoDB async) (005-tab2-visuals)
- MongoDB (projects collection) + GridFS (image binaries) (005-tab2-visuals)

## Recent Changes
- 004-tab3-style-visuals-schemas: Added Python 3.11 (backend), TypeScript 5.x (frontend)
