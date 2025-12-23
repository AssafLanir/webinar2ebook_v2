# Implementation Plan: Tab 3 AI Draft Generation

**Branch**: `004-tab3-style-visuals-schemas` | **Date**: 2025-12-17 | **Spec**: [spec4.md](../../spec4.md)
**Input**: Feature specification from `/spec4.md`

## Summary

Add the core product capability: generate an editable ebook draft in Tab 3 from user's prepared inputs (clean transcript + outline + resources + style config). The implementation uses a chunked generation approach with async job pattern for long-running operations, enabling progress tracking, cancellation, and partial results. Visual suggestions are generated as metadata alongside the draft without inserting placeholders.

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**:
- Backend: FastAPI, Pydantic v2, OpenAI SDK, Anthropic SDK, motor (async MongoDB)
- Frontend: React 18, Vite, Tailwind CSS, React Context
**Storage**: MongoDB (projects), local filesystem (file uploads)
**Testing**: pytest (backend), Vitest (frontend)
**Target Platform**: Web application (Linux server backend, modern browsers frontend)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: 8-chapter draft from 15k char transcript in <3 minutes
**Constraints**:
- Individual chapter requests <8,000 input tokens
- Support cancellation with partial results
- Maintain existing draft on generation failure
**Scale/Scope**: Single-user projects, 500-50,000 char transcripts

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Note**: Constitution template has placeholders, so applying sensible defaults:

| Principle | Status | Notes |
|-----------|--------|-------|
| Existing patterns | PASS | Follows established LLM abstraction, API patterns from 003-tab1-ai-assist |
| Test coverage | PASS | Contract tests already exist; unit tests will be added |
| Single source of truth | PASS | Pydantic models are canonical; JSON schemas are derived |
| Error handling | PASS | Envelope pattern { data, error } established |

## Project Structure

### Documentation (this feature)

```text
specs/004-tab3-ai-draft/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API contracts)
├── schemas/             # JSON schemas (already created)
│   ├── draft_plan.internal.schema.json
│   ├── draft_plan.openai.strict.schema.json
│   ├── DraftPlan.json
│   ├── DraftGenerateRequest.json
│   ├── DraftGenerateResponse.json
│   └── ... (other model schemas)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── draft_plan.py          # DraftPlan, ChapterPlan, etc. (EXISTS)
│   │   ├── api_responses.py       # API envelope models (EXISTS)
│   │   ├── style_config.py        # StyleConfig, StyleConfigEnvelope (EXISTS)
│   │   └── visuals.py             # VisualPlan, VisualOpportunity (EXISTS)
│   ├── services/
│   │   ├── ai_service.py          # Tab 1 AI functions (EXISTS)
│   │   └── draft_service.py       # NEW: Draft generation service
│   ├── api/
│   │   └── routes/
│   │       └── ai.py              # Existing AI routes (EXISTS)
│   │       └── draft.py           # NEW: Draft generation endpoints
│   └── llm/
│       ├── schemas.py             # Schema loader utility (EXISTS)
│       └── ... (providers)
└── tests/
    ├── unit/
    │   ├── test_schemas_contract.py  # EXISTS (63 tests)
    │   ├── test_draft_service.py     # NEW
    │   └── test_draft_api.py         # NEW
    └── integration/
        └── test_draft_generation.py  # NEW

frontend/
├── src/
│   ├── components/
│   │   ├── tab3/
│   │   │   ├── Tab3Content.tsx        # EXISTS (update for Generate button)
│   │   │   ├── DraftEditor.tsx        # EXISTS
│   │   │   ├── StyleControls.tsx      # EXISTS
│   │   │   ├── GenerateProgress.tsx   # NEW: Progress indicator
│   │   │   └── DraftPreviewModal.tsx  # NEW: Preview modal
│   │   └── common/
│   │       └── Modal.tsx              # EXISTS
│   ├── hooks/
│   │   └── useDraftGeneration.ts      # NEW: Generation hook
│   ├── services/
│   │   └── draftApi.ts                # NEW: API client
│   └── types/
│       └── draft.ts                   # NEW: TypeScript types
└── tests/
    └── ... (component tests)
```

**Structure Decision**: Web application with existing backend/frontend split. This feature adds draft generation service layer and frontend components.

## Complexity Tracking

No violations requiring justification. The implementation follows established patterns from 003-tab1-ai-assist.

---

## Phase 0: Research Required

### Unknowns to Resolve

1. **Chunked generation strategy**: How to split transcript segments and maintain context between chapters
2. **Job management pattern**: In-memory vs Redis vs database for async job tracking
3. **Progress streaming**: Polling vs SSE vs WebSocket for progress updates
4. **DraftPlan LLM prompting**: System prompt design for structured output
5. **Visual opportunities generation**: When and how to generate visual suggestions

### Research Tasks

| Topic | Question | Output |
|-------|----------|--------|
| Chunked generation | Best practices for LLM content generation >8K tokens | research.md section |
| Job management | Async job patterns for FastAPI (celery vs background tasks vs polling) | research.md section |
| Progress updates | Polling interval and UX patterns for progress indicators | research.md section |
| Structured output | OpenAI JSON mode vs tool_use for DraftPlan | research.md section |
| Context windows | How much surrounding context for chapter continuity | research.md section |

---

## Phase 1: Design Artifacts

### Entities (data-model.md)

From spec4.md, the following entities need detailed documentation:

| Entity | Source | Status |
|--------|--------|--------|
| DraftPlan | backend/src/models/draft_plan.py | EXISTS - document |
| ChapterPlan | backend/src/models/draft_plan.py | EXISTS - document |
| TranscriptSegment | backend/src/models/draft_plan.py | EXISTS - document |
| GenerationMetadata | backend/src/models/draft_plan.py | EXISTS - document |
| VisualPlan | backend/src/models/visuals.py | EXISTS - document |
| VisualOpportunity | backend/src/models/visuals.py | EXISTS - document |
| StyleConfigEnvelope | backend/src/models/style_config.py | EXISTS - document |
| DraftGenerateRequest | backend/src/models/api_responses.py | EXISTS - document |
| Job state model | NEW | NEEDS DESIGN |

### API Contracts (contracts/)

| Endpoint | Method | Schema File | Status |
|----------|--------|-------------|--------|
| /api/ai/draft/generate | POST | DraftGenerateRequest.json | Schema EXISTS, endpoint NEW |
| /api/ai/draft/status/:job_id | GET | DraftStatusResponse.json | Schema EXISTS, endpoint NEW |
| /api/ai/draft/cancel/:job_id | POST | DraftCancelResponse.json | Schema EXISTS, endpoint NEW |
| /api/ai/draft/regenerate | POST | DraftRegenerateRequest.json | Schema EXISTS, endpoint NEW |

### Quickstart (quickstart.md)

Local development setup steps for implementing this feature.

---

## What Already Exists

### Backend (from previous work)

- **Models** (all in `backend/src/models/`):
  - `DraftPlan`, `ChapterPlan`, `TranscriptSegment`, `GenerationMetadata`
  - `VisualPlan`, `VisualOpportunity`, `VisualAsset`
  - `StyleConfig`, `StyleConfigEnvelope`, presets
  - API envelope models: `DraftGenerateData`, `DraftStatusData`, etc.

- **LLM Layer** (`backend/src/llm/`):
  - `LLMClient` with OpenAI/Anthropic providers
  - Automatic fallback on errors
  - `load_draft_plan_schema()` utility for provider-specific schemas

- **Schemas** (`specs/004-tab3-ai-draft/schemas/`):
  - `draft_plan.internal.schema.json` (tests/docs)
  - `draft_plan.openai.strict.schema.json` (production)
  - All API request/response schemas

- **Contract Tests** (`backend/tests/unit/test_schemas_contract.py`):
  - 63 tests validating schemas and envelope pattern

### Frontend (from previous work)

- Tab 3 UI with preset dropdown and customize toggle
- `StyleControls` component
- `DraftEditor` component (basic)
- Type definitions in `frontend/src/types/`

### What Needs Building

1. **Draft generation service** (`draft_service.py`)
2. **Draft API endpoints** (`routes/draft.py`)
3. **Job management** (in-memory or persistent)
4. **LLM prompts** for DraftPlan and chapter generation
5. **Frontend** progress indicator, preview modal, API hooks

---

## Next Steps

1. **Phase 0**: Generate `research.md` to resolve unknowns
2. **Phase 1**: Generate `data-model.md`, `contracts/`, `quickstart.md`
3. **Phase 2**: Run `/speckit.tasks` to generate implementation tasks
