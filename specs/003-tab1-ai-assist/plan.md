# Implementation Plan: Tab 1 AI Assist

**Branch**: `003-tab1-ai-assist` | **Date**: 2025-12-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-tab1-ai-assist/spec.md`

## Summary

Add AI-assisted features to Tab 1 for transcript cleanup, outline suggestion, and resource suggestion. Users can preview AI-generated content before applying it. Implementation requires a multi-provider LLM abstraction layer (OpenAI primary, Anthropic fallback) with structured output support for outline and resource suggestions.

## Technical Context

**Language/Version**: Python 3.11+ (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, Pydantic v2, openai SDK, anthropic SDK (backend); React 18, Tailwind CSS, React Context (frontend)
**Storage**: MongoDB via motor (existing from Spec 002)
**Testing**: pytest (backend), Vitest (frontend)
**Target Platform**: Web application (Linux server backend, modern browsers frontend)
**Project Type**: Web application with separate backend/frontend
**Performance Goals**: AI actions complete within 20 seconds for typical transcripts (max 50,000 characters supported)
**Constraints**: Single AI action at a time; no data loss on failures; user-friendly error messages
**Scale/Scope**: Single-user workflow; transcript sizes up to 50k chars

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

No constitution violations. The constitution file contains only template placeholders.

## Project Structure

### Documentation (this feature)

```text
specs/003-tab1-ai-assist/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI specs)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   └── project.py       # Existing - no changes needed
│   ├── services/
│   │   ├── project_service.py  # Existing
│   │   └── ai_service.py       # NEW: AI feature orchestration
│   ├── api/
│   │   └── routes/
│   │       ├── projects.py     # Existing
│   │       └── ai.py           # NEW: AI action endpoints
│   └── llm/                    # NEW: LLM provider abstraction
│       ├── __init__.py
│       ├── models.py           # LLMRequest, LLMResponse, etc.
│       ├── errors.py           # LLMError hierarchy
│       ├── client.py           # High-level generate() with fallback
│       └── providers/
│           ├── __init__.py
│           ├── base.py         # LLMProvider ABC
│           ├── openai.py       # OpenAIProvider
│           └── anthropic.py    # AnthropicProvider
└── tests/
    ├── unit/
    │   └── llm/                # Provider unit tests
    └── integration/
        └── test_ai_endpoints.py  # AI endpoint integration tests

frontend/
├── src/
│   ├── components/
│   │   ├── tab1/
│   │   │   ├── Tab1Content.tsx      # Modify: add AI Assist section
│   │   │   ├── AIAssistSection.tsx  # NEW: AI action buttons
│   │   │   └── AIPreviewModal.tsx   # NEW: Preview/apply modal
│   │   └── common/
│   │       └── Modal.tsx            # Existing
│   ├── services/
│   │   └── api.ts                   # Modify: add AI endpoints
│   ├── context/
│   │   └── ProjectContext.tsx       # Modify: add AI state/actions
│   └── types/
│       └── ai.ts                    # NEW: AI-related types
└── tests/
    └── components/
        └── AIAssistSection.test.tsx # NEW
```

**Structure Decision**: Web application with existing `backend/` and `frontend/` directories. AI features extend existing structure with new modules (`backend/src/llm/`, `backend/src/services/ai_service.py`, `backend/src/api/routes/ai.py`) and frontend components (`AIAssistSection`, `AIPreviewModal`).

## Complexity Tracking

No constitution violations requiring justification.

## Key Implementation Decisions

### LLM Provider Abstraction

Per `docs/llm_adapter_contract.md`:
- OpenAI is primary provider, Anthropic is fallback
- Automatic failover on 429, 5xx, timeout, network errors
- 2 retries per provider, exponential backoff with jitter
- Structured output via `response_format.json_schema` for outline/resources

### AI Action Endpoints

Three new backend endpoints:
1. `POST /api/ai/clean-transcript` - Returns cleaned transcript text
2. `POST /api/ai/suggest-outline` - Returns structured outline items (JSON schema)
3. `POST /api/ai/suggest-resources` - Returns structured resources (JSON schema)

### Frontend State Management

- AI preview state is ephemeral (not persisted)
- Only one AI action in progress at a time (mutex in context)
- Applied results flow through existing `dispatch()` actions

### Error Handling

- Backend: Catch `LLMError` subtypes, return user-friendly messages
- Frontend: Display errors in toast/alert, enable retry
- No raw technical errors exposed to users

## Dependencies on Prior Features

- **001-frontend-shell**: Tab 1 UI exists (TranscriptEditor, OutlineEditor, ResourceList)
- **002-backend-foundation**: Project CRUD, auto-save, MongoDB persistence

## External References

- LLM Adapter Contract: `docs/llm_adapter_contract.md`
- OpenAI API Reference: `docs/refs/openai/chat_completions.md`
- Anthropic API Reference: `docs/refs/anthropic/messages.md`
- Tech Stack: `specs/001-frontend-shell/spec0_tech.md`
