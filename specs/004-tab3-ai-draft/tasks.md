# Tasks: Tab 3 AI Draft Generation

**Input**: Design documents from `/specs/004-tab3-ai-draft/`
**Prerequisites**: plan.md, spec4.md, research.md, data-model.md, contracts/

**Tests**: Unit tests are included based on the testing strategy in research.md.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## User Stories (from spec4.md)

| Story | Priority | Description |
|-------|----------|-------------|
| US1 | P1 | Generate an Ebook Draft |
| US2 | P2 | Regenerate a Chapter/Section |
| US3 | P2 | Visual Suggestions (Metadata Only) |
| US4 | P1 | Reliability and UX (progress, cancel, errors) |

**Note**: US1 and US4 are tightly coupled (can't generate without progress/cancel), so they form the MVP together.

---

## Phase 1: Setup ✅

**Purpose**: Project structure verification (most already exists)

- [x] T001 Verify existing models in backend/src/models/ match data-model.md
- [x] T002 Verify existing schemas in specs/004-tab3-ai-draft/schemas/ are current
- [x] T003 [P] Verify LLM client and schema loader work in backend/src/llm/

**Checkpoint**: Existing infrastructure verified ✅

---

## Phase 2: Foundational (Blocking Prerequisites) ✅

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

### Backend Infrastructure

- [x] T004 [P] Create GenerationJob model in backend/src/models/generation_job.py
- [x] T005 [P] Create job store module (in-memory with TTL cleanup) in backend/src/services/job_store.py
- [x] T006 [P] Create prompts module in backend/src/services/prompts.py with DraftPlan and chapter prompts
- [x] T007 Create base draft_service.py structure in backend/src/services/draft_service.py
- [x] T008 [P] Create stub draft router in backend/src/api/routes/draft.py (empty router, endpoints added in Phase 3)
- [x] T009 Register draft router in backend/src/api/main.py

### Frontend Infrastructure

- [x] T010 [P] Create draft TypeScript types in frontend/src/types/draft.ts
- [x] T011 [P] Create draft API client in frontend/src/services/draftApi.ts

**Checkpoint**: Foundation ready - user story implementation can now begin ✅

**Job Storage Decision**: MVP uses in-memory job store with 1-hour TTL cleanup. Jobs are lost on server restart. Future: Add MongoDB persistence when multi-user support needed.

---

## Phase 3: User Story 1 + 4 - Generate Draft with Progress/Cancel (Priority: P1) 🎯 MVP

**Goal**: User clicks "Generate Draft", sees progress, can cancel, previews result, and applies to editor

**Independent Test**:
1. Create project with 500+ char transcript and 3+ outline items
2. Go to Tab 3, click "Generate Draft"
3. See progress indicator with chapter info
4. Wait for completion OR click Cancel
5. Preview modal shows draft with word count
6. Click Apply - draft appears in editor

### Unit Tests for US1+US4

- [ ] T012 [P] [US1] Create test_draft_service.py in backend/tests/unit/test_draft_service.py
- [ ] T013 [P] [US4] Create test_draft_api.py in backend/tests/unit/test_draft_api.py

### Backend Implementation

- [ ] T014 [US1] Implement generate_draft_plan() in backend/src/services/draft_service.py
- [ ] T015 [US1] Implement generate_chapter() in backend/src/services/draft_service.py
- [ ] T016 [US1] Implement assemble_chapters() in backend/src/services/draft_service.py
- [ ] T017 [US4] Implement start_generation() with background task in backend/src/services/draft_service.py
- [ ] T018 [US4] Implement get_job_status() in backend/src/services/draft_service.py
- [ ] T019 [US4] Implement cancel_job() in backend/src/services/draft_service.py
- [ ] T020 [US1] Create POST /ai/draft/generate endpoint in backend/src/api/routes/draft.py
- [ ] T021 [US4] Create GET /ai/draft/status/{job_id} endpoint in backend/src/api/routes/draft.py
- [ ] T022 [US4] Create POST /ai/draft/cancel/{job_id} endpoint in backend/src/api/routes/draft.py

### Frontend Implementation

- [ ] T023 [P] [US4] Create useDraftGeneration hook in frontend/src/hooks/useDraftGeneration.ts
- [ ] T024 [P] [US4] Create GenerateProgress component in frontend/src/components/tab3/GenerateProgress.tsx
- [ ] T025 [P] [US1] Create DraftPreviewModal component in frontend/src/components/tab3/DraftPreviewModal.tsx
- [ ] T026 [US1] Update Tab3Content.tsx to wire Generate button with hook in frontend/src/components/tab3/Tab3Content.tsx
- [ ] T027 [US1] Add input validation (transcript ≥500, outline ≥3) in frontend/src/components/tab3/Tab3Content.tsx
- [ ] T028 [US4] Add error display and retry logic in frontend/src/components/tab3/Tab3Content.tsx

### Integration

- [ ] T029 [US1] Create integration test in backend/tests/integration/test_draft_generation.py

**Checkpoint**: Users can generate, track progress, cancel, preview, and apply drafts

---

## Phase 4: User Story 3 - Visual Suggestions (Priority: P2)

**Goal**: Visual opportunities are generated alongside draft and displayed in a separate panel

**Independent Test**:
1. Generate a draft with visual_density != "none"
2. After generation, visual opportunities are listed
3. Each shows chapter reference, type, title, prompt, confidence
4. No [IMAGE] placeholders in the markdown

### Implementation

- [ ] T030 [P] [US3] Create VisualOpportunitiesPanel component in frontend/src/components/tab3/VisualOpportunitiesPanel.tsx
- [ ] T031 [US3] Add visual opportunities display to Tab3Content in frontend/src/components/tab3/Tab3Content.tsx
- [ ] T032 [US3] Add VisualPlan persistence when applying draft in frontend/src/context/ProjectContext.tsx

**Checkpoint**: Visual suggestions are visible and persisted

---

## Phase 5: User Story 2 - Regenerate Section (Priority: P2)

**Goal**: User can select a chapter and regenerate only that section

**Independent Test**:
1. Have an applied draft in editor
2. Select a chapter in outline panel
3. Click "Regenerate" button
4. Confirm overwrite warning (if edited)
5. Only selected chapter is regenerated
6. Apply replaces only that section

### Backend Implementation

- [ ] T033 [P] [US2] Add regenerate tests to test_draft_service.py in backend/tests/unit/test_draft_service.py
- [ ] T034 [US2] Implement regenerate_section() in backend/src/services/draft_service.py
- [ ] T035 [US2] Implement find_section_boundaries() in backend/src/services/draft_service.py
- [ ] T036 [US2] Create POST /ai/draft/regenerate endpoint in backend/src/api/routes/draft.py

### Frontend Implementation

- [ ] T037 [P] [US2] Create RegenerateConfirmModal component in frontend/src/components/tab3/RegenerateConfirmModal.tsx
- [ ] T038 [US2] Add regenerate button to outline panel in frontend/src/components/tab3/Tab3Content.tsx
- [ ] T039 [US2] Wire regenerate flow with section replacement in frontend/src/components/tab3/Tab3Content.tsx

**Checkpoint**: Users can regenerate individual chapters while preserving other content

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T040 [P] Add large transcript warning (>50k chars) in frontend/src/components/tab3/Tab3Content.tsx
- [ ] T041 [P] Add keyboard accessibility and ARIA labels to progress/modal components
- [ ] T042 [P] Add token usage logging in backend/src/services/draft_service.py
- [ ] T043 Run full test suite and fix any failures
- [ ] T044 Validate quickstart.md instructions work end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

```
Setup (Phase 1)
    ↓
Foundational (Phase 2) ← BLOCKS ALL USER STORIES
    ↓
    ├── US1+US4: Generate Draft (Phase 3) ← MVP
    │       ↓
    ├── US3: Visual Suggestions (Phase 4) ← Can start after Phase 2
    │       ↓
    └── US2: Regenerate Section (Phase 5) ← Depends on Phase 3
            ↓
        Polish (Phase 6)
```

### User Story Dependencies

- **US1+US4 (P1)**: Can start after Foundational - No dependencies on other stories
- **US3 (P2)**: Can start after Foundational - Visual data comes from DraftPlan (Phase 3)
- **US2 (P2)**: Depends on US1 completion - Needs existing draft to regenerate

### Within Each Phase

- Tests can run in parallel [P]
- Models/components can run in parallel [P]
- Services depend on models
- Endpoints depend on services
- Integration depends on all components

### Parallel Opportunities

**Phase 2 (Foundational)**:
```bash
# All can run in parallel:
T004: Create GenerationJob model
T005: Create job store module
T006: Create prompts module
T008: Create stub draft router
T010: Create draft TypeScript types
T011: Create draft API client
```

**Phase 3 (US1+US4)**:
```bash
# Tests in parallel:
T012: test_draft_service.py
T013: test_draft_api.py

# Frontend components in parallel:
T023: useDraftGeneration hook
T024: GenerateProgress component
T025: DraftPreviewModal component
```

---

## Implementation Strategy

### MVP First (US1+US4 Only)

1. Complete Phase 1: Setup verification
2. Complete Phase 2: Foundational infrastructure
3. Complete Phase 3: US1+US4 (Generate Draft with Progress/Cancel)
4. **STOP and VALIDATE**: Test full generation flow
5. Deploy/demo if ready - users can generate ebooks!

### Incremental Delivery

1. **MVP**: Setup + Foundational + US1+US4 → Core generation works
2. **+US3**: Add visual suggestions panel → Users see visual opportunities
3. **+US2**: Add regenerate → Users can refine individual chapters
4. **Polish**: Accessibility, logging, edge cases

### Task Count Summary

| Phase | Tasks | Parallelizable |
|-------|-------|----------------|
| Phase 1: Setup | 3 (T001-T003) | 1 |
| Phase 2: Foundational | 8 (T004-T011) | 6 |
| Phase 3: US1+US4 (MVP) | 18 (T012-T029) | 5 |
| Phase 4: US3 | 3 (T030-T032) | 1 |
| Phase 5: US2 | 7 (T033-T039) | 2 |
| Phase 6: Polish | 5 (T040-T044) | 3 |
| **Total** | **44** | **18** |

---

## Notes

- Models already exist in backend/src/models/ - no new model files needed except GenerationJob
- Schemas already exist in specs/004-tab3-ai-draft/schemas/
- Contract tests (63) already pass - focus on service/API unit tests
- Use existing LLM client with load_draft_plan_schema() for OpenAI calls
- Follow existing { data, error } envelope pattern for all responses
- Frontend uses existing Modal, Button, Card components
