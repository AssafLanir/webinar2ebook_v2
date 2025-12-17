# Tasks: Tab 1 AI Assist

**Input**: Design documents from `/specs/003-tab1-ai-assist/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/ai-endpoints.yaml

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## User Stories Summary

| Story | Title | Priority | Description |
|-------|-------|----------|-------------|
| US1 | Clean Transcript Preview & Apply | P1 | Clean up raw transcripts via AI with preview |
| US2 | Suggest Outline from Transcript | P1 | Generate structured outline suggestions |
| US3 | Suggest Resources | P2 | Suggest relevant resources from transcript |
| US4 | Robust Failure Handling | P1 | Graceful error handling across all AI features |
| US5 | Persisted Results Only | P3 | Applied results persist (handled by existing persistence) |

---

## Phase 1: Setup

**Purpose**: Install dependencies and create project structure

- [x] T001 Install Python dependencies: `pip install openai anthropic` in backend/
- [x] T002 [P] Create LLM module directory structure: backend/src/llm/__init__.py, backend/src/llm/providers/__init__.py
- [x] T003 [P] Create frontend AI types file: frontend/src/types/ai.ts

---

## Phase 2: Foundational - LLM Abstraction Layer

**Purpose**: Multi-provider LLM client with fallback support

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### LLM Models & Errors

- [x] T004 [P] Create LLM data models (LLMRequest, LLMResponse, ChatMessage, Usage, ResponseFormat) in backend/src/llm/models.py per data-model.md
- [x] T005 [P] Create LLM error hierarchy (LLMError, AuthenticationError, RateLimitError, TimeoutError, InvalidRequestError, ContentFilterError, ProviderError) in backend/src/llm/errors.py

### LLM Providers

- [x] T006 Create abstract base provider (LLMProvider ABC with generate method) in backend/src/llm/providers/base.py
- [x] T007 Implement OpenAI provider with structured output support in backend/src/llm/providers/openai.py
- [x] T008 Implement Anthropic provider with tool_use pattern for structured output in backend/src/llm/providers/anthropic.py

### LLM Client

- [x] T009 Implement high-level LLM client with retry logic (2 retries, exponential backoff) and automatic fallback (OpenAI → Anthropic) in backend/src/llm/client.py

### Unit Tests

- [x] T010 [P] Create unit tests for LLM models and error classes in backend/tests/unit/llm/test_models.py
- [x] T011 [P] Create unit tests for OpenAI provider (mock API calls) in backend/tests/unit/llm/test_openai_provider.py
- [x] T012 [P] Create unit tests for Anthropic provider (mock API calls) in backend/tests/unit/llm/test_anthropic_provider.py
- [x] T013 Create unit tests for LLM client fallback behavior in backend/tests/unit/llm/test_client.py

**Checkpoint**: LLM abstraction layer complete - run `pytest backend/tests/unit/llm/ -v`

---

## Phase 3: User Story 1 - Clean Transcript (Priority: P1) 🎯 MVP

**Goal**: Users can clean up messy transcripts via AI and preview before applying

**Independent Test**: Paste raw transcript → Click "Clean Transcript (AI)" → Preview appears → Apply replaces transcript

### Backend Implementation

- [x] T014 [US1] Create AI service with `clean_transcript(transcript: str) -> str` function in backend/src/services/ai_service.py
- [x] T015 [US1] Add system prompt for transcript cleanup per research.md in backend/src/services/ai_service.py
- [x] T016 [US1] Create AI router with POST /api/ai/clean-transcript endpoint in backend/src/api/routes/ai.py
- [x] T017 [US1] Register AI router in backend/src/api/main.py: `app.include_router(ai_router, prefix="/api/ai", tags=["AI"])`

### Frontend API & Types

- [x] T018 [US1] Add CleanTranscriptResponse type and cleanTranscript() API function in frontend/src/services/api.ts
- [x] T019 [US1] Add AIActionState and AIPreviewState types (clean-transcript variant) to frontend/src/types/ai.ts

### Frontend Context

- [x] T020 [US1] Add aiAction and aiPreview state to ProjectContext in frontend/src/context/ProjectContext.tsx
- [x] T021 [US1] Add START_AI_ACTION, AI_ACTION_SUCCESS, AI_ACTION_ERROR action types to ProjectContext reducer
- [x] T022 [US1] Add APPLY_AI_PREVIEW, DISCARD_AI_PREVIEW action types to ProjectContext reducer

### Frontend Components

- [x] T023 [US1] Create AIAssistSection component with "Clean Transcript (AI)" button in frontend/src/components/tab1/AIAssistSection.tsx
- [x] T024 [US1] Create AIPreviewModal component with text preview for cleaned transcript in frontend/src/components/tab1/AIPreviewModal.tsx
- [x] T025 [US1] Add Copy to clipboard functionality in AIPreviewModal
- [x] T026 [US1] Integrate AIAssistSection into Tab1Content.tsx after "Fill with Sample Data" button

### Integration Test

- [x] T027 [US1] Create integration test for clean-transcript endpoint in backend/tests/integration/test_ai_endpoints.py

**Checkpoint**: Clean Transcript flow works end-to-end. Test manually: paste transcript → clean → preview → apply → verify update

---

## Phase 4: User Story 2 - Suggest Outline (Priority: P1)

**Goal**: Users can generate outline suggestions from transcript and selectively apply them

**Independent Test**: Have transcript → Click "Suggest Outline (AI)" → Preview with checkboxes → Select items → Insert appends to outline

### Backend Implementation

- [ ] T028 [US2] Add `suggest_outline(transcript: str) -> list[SuggestedOutlineItem]` function to backend/src/services/ai_service.py
- [ ] T029 [US2] Add JSON schema for outline response (items with title, level 1-3, notes) per research.md
- [ ] T030 [US2] Add POST /api/ai/suggest-outline endpoint to backend/src/api/routes/ai.py

### Frontend API & Types

- [ ] T031 [US2] Add SuggestedOutlineItem, SuggestOutlineResponse types and suggestOutline() API function in frontend/src/services/api.ts
- [ ] T032 [US2] Add suggest-outline variant to AIPreviewData type in frontend/src/types/ai.ts

### Frontend Components

- [ ] T033 [US2] Add "Suggest Outline (AI)" button to AIAssistSection in frontend/src/components/tab1/AIAssistSection.tsx
- [ ] T034 [US2] Add outline preview mode to AIPreviewModal with checkboxes and Select all/Deselect all in frontend/src/components/tab1/AIPreviewModal.tsx
- [ ] T035 [US2] Implement "Insert selected" / "Insert all" actions that append to existing outline via ADD_OUTLINE_ITEM dispatch

### Integration Test

- [ ] T036 [US2] Add integration test for suggest-outline endpoint in backend/tests/integration/test_ai_endpoints.py

**Checkpoint**: Suggest Outline flow works end-to-end. Test: transcript → suggest → select items → insert → verify appended

---

## Phase 5: User Story 3 - Suggest Resources (Priority: P2)

**Goal**: Users can generate resource suggestions and selectively add them

**Independent Test**: Have transcript → Click "Suggest Resources (AI)" → Preview with checkboxes → Select items → Add appends to resources

### Backend Implementation

- [ ] T037 [US3] Add `suggest_resources(transcript: str) -> list[SuggestedResource]` function to backend/src/services/ai_service.py
- [ ] T038 [US3] Add JSON schema for resources response (3-5 items with label, url_or_note) per research.md
- [ ] T039 [US3] Add POST /api/ai/suggest-resources endpoint to backend/src/api/routes/ai.py

### Frontend API & Types

- [ ] T040 [US3] Add SuggestedResource, SuggestResourcesResponse types and suggestResources() API function in frontend/src/services/api.ts
- [ ] T041 [US3] Add suggest-resources variant to AIPreviewData type in frontend/src/types/ai.ts

### Frontend Components

- [ ] T042 [US3] Add "Suggest Resources (AI)" button to AIAssistSection in frontend/src/components/tab1/AIAssistSection.tsx
- [ ] T043 [US3] Add resources preview mode to AIPreviewModal with checkboxes in frontend/src/components/tab1/AIPreviewModal.tsx
- [ ] T044 [US3] Implement "Add selected" / "Add all" actions that append resources via ADD_RESOURCE dispatch (resourceType = "url_or_note")

### Integration Test

- [ ] T045 [US3] Add integration test for suggest-resources endpoint in backend/tests/integration/test_ai_endpoints.py

**Checkpoint**: Suggest Resources flow works end-to-end. Test: transcript → suggest → select → add → verify appended

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Error handling verification (US4), persistence verification (US5), final testing

### Error Handling (US4)

- [ ] T046 [US4] Add user-friendly error messages to AI endpoints (wrap LLMError with AIErrorResponse) in backend/src/api/routes/ai.py
- [ ] T047 [US4] Add error display and retry button to AIAssistSection in frontend/src/components/tab1/AIAssistSection.tsx
- [ ] T048 [US4] Verify AI buttons disabled when transcript empty or action in progress
- [ ] T049 [US4] Add integration test for AI error handling scenarios in backend/tests/integration/test_ai_endpoints.py

### Persistence Verification (US5)

- [ ] T050 [US5] Manual test: Apply AI suggestions → Refresh page → Verify data persists via existing auto-save

### Final Validation

- [ ] T051 Run full backend test suite: `pytest backend/tests/ -v`
- [ ] T052 Manual E2E test per quickstart.md testing checklist
- [ ] T053 Verify existing Tab 1 functionality unchanged (backward compatibility)

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ─────────────────────────────────────────────────────┐
                                                                      │
Phase 2 (Foundational: LLM Layer) ←── BLOCKS ALL USER STORIES ──────┤
                                                                      │
     ┌──────────────────┬──────────────────┬──────────────────────────┘
     │                  │                  │
     ▼                  ▼                  ▼
Phase 3 (US1)     Phase 4 (US2)     Phase 5 (US3)
Clean Transcript  Suggest Outline   Suggest Resources
  (P1 MVP)           (P1)              (P2)
     │                  │                  │
     └──────────────────┴──────────────────┘
                        │
                        ▼
               Phase 6 (Polish)
               US4 + US5 + Tests
```

### User Story Dependencies

- **US1 (Clean Transcript)**: Depends on Phase 2 completion. No dependency on US2/US3.
- **US2 (Suggest Outline)**: Depends on Phase 2. Shares components with US1 but can be developed in parallel.
- **US3 (Suggest Resources)**: Depends on Phase 2. Can run in parallel with US1/US2.
- **US4 (Error Handling)**: Cross-cutting, verified in Phase 6 after all features implemented.
- **US5 (Persistence)**: Uses existing persistence, verified in Phase 6.

### Within Each Phase

- Backend implementation before frontend integration
- API function before component that uses it
- Context changes before components that dispatch actions
- Core implementation before tests

### Parallel Opportunities

**Phase 1**: T002 and T003 can run in parallel

**Phase 2**:
- T004 and T005 can run in parallel (models and errors)
- T010, T011, T012 can run in parallel (unit tests)

**After Phase 2 completes**:
- US1, US2, US3 can be worked on in parallel by different developers
- Within each story, backend tasks should complete before frontend integration

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: LLM Abstraction Layer (CRITICAL)
3. Complete Phase 3: US1 - Clean Transcript
4. **STOP and VALIDATE**: Test clean transcript flow end-to-end
5. User can clean transcripts - immediate value delivered

### Incremental Delivery

1. Setup + Foundational → LLM infrastructure ready
2. Add US1 (Clean Transcript) → Test → First AI feature working
3. Add US2 (Suggest Outline) → Test → Outline suggestions working
4. Add US3 (Suggest Resources) → Test → Full feature set complete
5. Polish Phase → Error handling verified, persistence verified

### Single Developer Strategy

Complete phases sequentially: 1 → 2 → 3 → 4 → 5 → 6

### Parallel Team Strategy

With 3 developers after Phase 2:
- Developer A: US1 (Clean Transcript)
- Developer B: US2 (Suggest Outline)
- Developer C: US3 (Suggest Resources)
- All converge for Phase 6 (Polish)

---

## Notes

- Environment variables required: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- Optional config: `LLM_DEFAULT_PROVIDER`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`
- Default models: OpenAI `gpt-4o`, Anthropic `claude-sonnet-4-5-20250929`
- Max transcript length: 50,000 characters (API validation)
- AI preview state is ephemeral (not persisted until applied)
