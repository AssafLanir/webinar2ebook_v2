# Tasks: Evidence-Grounded Drafting

**Input**: Design documents from `/specs/009-evidence-grounded/`

**Tests**: Included for core functionality (evidence map, constraints, rewrite)

**Organization**: Tasks grouped by user story. US1 and US2 are both P1 and tightly coupled (Content Mode enables grounded generation), so they share a phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Paths: `backend/` for Python, `frontend/` for TypeScript

---

## Phase 1: Setup

**Purpose**: Create new model files and extend existing models

- [ ] T001 [P] Add ContentMode enum to backend/src/models/style_config.py
- [ ] T002 [P] Add strict_grounded field to StyleConfig in backend/src/models/style_config.py
- [ ] T003 [P] Create EvidenceMap, ChapterEvidence, EvidenceEntry models in backend/src/models/evidence_map.py
- [ ] T004 [P] Create RewritePlan, RewriteSection, RewriteResult models in backend/src/models/rewrite_plan.py
- [ ] T005 [P] Add ContentMode type to frontend/src/types/style.ts

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Job pipeline updates that MUST be complete before user stories

**⚠️ CRITICAL**: Evidence Map phase integration blocks US1/US2 implementation

- [ ] T006 Add "evidence_map" value to JobStatus enum in backend/src/models/generation_job.py
- [ ] T007 Add evidence_map, content_mode, constraint_warnings fields to GenerationJob in backend/src/models/generation_job.py
- [ ] T008 Update job_store.py to handle new GenerationJob fields in backend/src/services/job_store.py
- [ ] T009 [P] Add evidenceMap field to Project model in backend/src/models/project.py (FR-007a: persist for rewrite/debugging)
- [ ] T010 [P] Create schema contract tests for EvidenceMap in backend/tests/unit/test_evidence_map_schema.py
- [ ] T011 [P] Create schema contract tests for RewritePlan in backend/tests/unit/test_rewrite_plan_schema.py

**Checkpoint**: Foundation ready - models and job pipeline support Evidence Map

---

## Phase 3: User Story 1 + 2 - Evidence-Grounded Generation with Content Mode (Priority: P1) 🎯 MVP

**Goal**: Generate drafts grounded in Evidence Map with Content Mode controlling structure

**Independent Test**: Generate draft with Content Mode = "Interview", Strict Grounded = true → Verify no Action Steps, no invented bio, Evidence Map visible in job status

### Tests for US1/US2

> **NOTE: Write tests FIRST, ensure they FAIL before implementation**

- [ ] T012 [P] [US1] Create unit tests for evidence extraction in backend/tests/unit/test_evidence_service.py
- [ ] T013 [P] [US2] Create unit tests for interview mode constraints in backend/tests/unit/test_content_mode_constraints.py
- [ ] T014 [P] [US1] Create unit tests for empty evidence handling in backend/tests/unit/test_evidence_service.py (FR-009a: skip/merge)
- [ ] T015 [P] [US1] Create integration tests for grounded generation in backend/tests/integration/test_grounded_generation.py

### Implementation for US1/US2

**Evidence Map Generation (US1)**

- [ ] T016 [US1] Create evidence extraction system prompt in backend/src/services/prompts.py (EVIDENCE_EXTRACTION_SYSTEM_PROMPT)
- [ ] T017 [US1] Create claim extraction user prompt builder in backend/src/services/prompts.py (build_claim_extraction_prompt)
- [ ] T018 [US1] Implement generate_evidence_map function in backend/src/services/evidence_service.py
- [ ] T019 [US1] Implement extract_claims_for_chapter helper in backend/src/services/evidence_service.py
- [ ] T020 [US1] Implement find_supporting_quotes helper in backend/src/services/evidence_service.py
- [ ] T021 [US1] Implement handle_empty_evidence function (FR-009a: skip/merge chapter, emit warning) in backend/src/services/evidence_service.py
- [ ] T022 [US1] Add content mode detection warning in backend/src/services/evidence_service.py (detect_content_type, generate_mode_warning)

**Interview Mode Constraints (US2)**

- [ ] T023 [US2] Add INTERVIEW_FORBIDDEN_PATTERNS regex list to backend/src/services/prompts.py
- [ ] T024 [US2] Implement check_interview_constraints function in backend/src/services/evidence_service.py
- [ ] T025 [US2] Create interview mode system prompt additions in backend/src/services/prompts.py (INTERVIEW_MODE_CONSTRAINTS)
- [ ] T026 [US2] Create essay mode prompt template in backend/src/services/prompts.py
- [ ] T027 [US2] Create tutorial mode prompt template in backend/src/services/prompts.py

**Pipeline Integration (US1)**

- [ ] T028 [US1] Integrate evidence_map phase into _generate_draft_task in backend/src/services/draft_service.py
- [ ] T029 [US1] Update generate_chapter to accept and use Evidence Map in backend/src/services/draft_service.py
- [ ] T030 [US1] Modify build_chapter_user_prompt to include evidence entries in backend/src/services/prompts.py
- [ ] T031 [US1] Update get_job_status to return evidence_map in backend/src/services/draft_service.py

**Frontend Updates (US2)**

- [ ] T032 [P] [US2] Add Content Mode dropdown to StyleControls in frontend/src/components/tab3/StyleControls.tsx
- [ ] T033 [P] [US2] Add Strict Grounded toggle to StyleControls in frontend/src/components/tab3/StyleControls.tsx
- [ ] T034 [US2] Update useDraftGeneration hook to handle content_mode in frontend/src/hooks/useDraftGeneration.ts
- [ ] T035 [US1] Display Evidence Map summary in GenerateProgress in frontend/src/components/tab3/GenerateProgress.tsx

**Make Tests Pass**

- [ ] T036 [US1] Implement evidence extraction tests (make tests pass) in backend/tests/unit/test_evidence_service.py
- [ ] T037 [US2] Implement constraint tests (make tests pass) in backend/tests/unit/test_content_mode_constraints.py
- [ ] T038 [US1] Implement integration tests (make tests pass) in backend/tests/integration/test_grounded_generation.py

**Checkpoint**: Evidence-grounded generation works. Interview mode prevents Action Steps and hallucinations. MVP complete.

---

## Phase 4: User Story 3 - Targeted Rewrite Pass (Priority: P2)

**Goal**: Fix QA-flagged issues without changing verified content

**Independent Test**: Generate draft → QA flags issues → Click "Fix Flagged Issues" → Verify only flagged sections changed, faithfulness preserved

### Tests for US3

- [ ] T039 [P] [US3] Create unit tests for section boundary detection in backend/tests/unit/test_rewrite_service.py
- [ ] T040 [P] [US3] Create integration tests for rewrite flow in backend/tests/integration/test_rewrite_flow.py

### Implementation for US3

**Backend Rewrite Service**

- [ ] T041 [US3] Implement parse_markdown_sections function in backend/src/services/rewrite_service.py
- [ ] T042 [US3] Implement find_sections_for_issues function in backend/src/services/rewrite_service.py
- [ ] T043 [US3] Implement create_rewrite_plan function in backend/src/services/rewrite_service.py
- [ ] T044 [US3] Implement execute_targeted_rewrite function in backend/src/services/rewrite_service.py
- [ ] T045 [US3] Implement generate_section_diff function in backend/src/services/rewrite_service.py
- [ ] T046 [US3] Add rewrite system prompt in backend/src/services/prompts.py (REWRITE_SYSTEM_PROMPT)

**API Endpoint**

- [ ] T047 [US3] Add POST /qa/rewrite endpoint in backend/src/api/routes/qa.py
- [ ] T048 [US3] Add GET /qa/rewrite/{job_id} status endpoint in backend/src/api/routes/qa.py
- [ ] T049 [US3] Implement multi-pass warning logic in rewrite endpoint

**Frontend Rewrite UI**

- [ ] T050 [P] [US3] Create RewriteDiffView component in frontend/src/components/tab3/RewriteDiffView.tsx
- [ ] T051 [US3] Add "Fix Flagged Issues" button to QAPanel in frontend/src/components/tab3/QAPanel.tsx
- [ ] T052 [US3] Create useRewrite hook in frontend/src/hooks/useRewrite.ts
- [ ] T053 [US3] Add rewrite API client functions in frontend/src/services/qaApi.ts
- [ ] T054 [US3] Integrate RewriteDiffView into Tab3Content in frontend/src/components/tab3/Tab3Content.tsx

**Make Tests Pass**

- [ ] T055 [US3] Implement rewrite service tests (make tests pass)
- [ ] T056 [US3] Implement rewrite integration tests (make tests pass)

**Checkpoint**: Targeted rewrite available. Fixes QA issues without breaking faithfulness. Full feature complete.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Validation and cleanup

- [ ] T057 Run all backend tests: `python -m pytest backend/tests/ -v`
- [ ] T058 Run frontend build: `npm run build`
- [ ] T059 Run quickstart.md validation (manual test in browser)
- [ ] T060 [P] Code review and cleanup
- [ ] T061 Update Spec 008 tasks.md to mark US3/US4 as superseded

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **US1+US2 (Phase 3)**: Depends on Foundational - Core grounded generation
- **US3 (Phase 4)**: Depends on US1+US2 (needs Evidence Map and QA system)
- **Polish (Phase 5)**: Depends on desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational - Evidence Map generation
- **US2 (P1)**: Tightly coupled with US1 - Content Mode controls Evidence Map behavior
- **US3 (P2)**: Depends on US1+US2 - Rewrite uses Evidence Map + QA issues

### Within Phase 3 (US1+US2)

1. Tests first (T012-T015) - should fail initially
2. Evidence extraction prompts (T016-T017)
3. Evidence service implementation (T018-T022)
4. Interview mode constraints (T023-T027)
5. Pipeline integration (T028-T031)
6. Frontend updates (T032-T035) - can parallel with backend
7. Make tests pass (T036-T038)

### Parallel Opportunities

```
# Phase 1 parallel (all different files):
T001 (ContentMode) || T002 (strict_grounded) || T003 (evidence_map.py) || T004 (rewrite_plan.py) || T005 (frontend types)

# Phase 2 parallel:
T009 (project.evidenceMap) || T010 (evidence schema tests) || T011 (rewrite schema tests)

# Phase 3 tests parallel:
T012 (evidence tests) || T013 (constraint tests) || T014 (empty evidence tests) || T015 (integration tests)

# Phase 3 frontend parallel with backend:
T032 (Content Mode dropdown) || T033 (Strict toggle) can run while backend tasks proceed

# Phase 4 tests parallel:
T039 (rewrite unit tests) || T040 (rewrite integration tests)
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T011)
3. Complete Phase 3: US1+US2 (T012-T038)
4. **STOP and VALIDATE**: Test in browser with interview transcript
5. MVP complete - grounded generation works!

### Full Feature (US1 + US2 + US3)

1. Complete MVP (Phases 1-3)
2. Complete Phase 4: US3 Targeted Rewrite (T039-T056)
3. Complete Phase 5: Polish (T057-T061)
4. Full feature ready for deployment

---

## File Summary

| File | Action | Phase |
|------|--------|-------|
| backend/src/models/style_config.py | UPDATE | Setup |
| backend/src/models/evidence_map.py | NEW | Setup |
| backend/src/models/rewrite_plan.py | NEW | Setup |
| frontend/src/types/style.ts | UPDATE | Setup |
| backend/src/models/generation_job.py | UPDATE | Foundational |
| backend/src/models/project.py | UPDATE | Foundational |
| backend/src/services/job_store.py | UPDATE | Foundational |
| backend/tests/unit/test_evidence_map_schema.py | NEW | Foundational |
| backend/tests/unit/test_rewrite_plan_schema.py | NEW | Foundational |
| backend/src/services/evidence_service.py | NEW | US1+US2 |
| backend/src/services/prompts.py | UPDATE | US1+US2 |
| backend/src/services/draft_service.py | UPDATE | US1+US2 |
| frontend/src/components/tab3/StyleControls.tsx | UPDATE | US1+US2 |
| frontend/src/components/tab3/GenerateProgress.tsx | UPDATE | US1+US2 |
| backend/tests/unit/test_evidence_service.py | NEW | US1+US2 |
| backend/tests/unit/test_content_mode_constraints.py | NEW | US1+US2 |
| backend/tests/integration/test_grounded_generation.py | NEW | US1+US2 |
| backend/src/services/rewrite_service.py | NEW | US3 |
| backend/src/api/routes/qa.py | UPDATE | US3 |
| frontend/src/components/tab3/RewriteDiffView.tsx | NEW | US3 |
| frontend/src/components/tab3/QAPanel.tsx | UPDATE | US3 |
| frontend/src/hooks/useRewrite.ts | NEW | US3 |
| frontend/src/services/qaApi.ts | UPDATE | US3 |
| backend/tests/unit/test_rewrite_service.py | NEW | US3 |
| backend/tests/integration/test_rewrite_flow.py | NEW | US3 |

---

## Notes

- [P] tasks = different files, no dependencies
- [US1], [US2], [US3] labels map tasks to user stories for traceability
- US1 and US2 are both P1 and tightly coupled - implemented together
- US3 (P2) supersedes Spec 008 US3 (Editor Pass)
- Evidence Map stored in job during generation AND persisted to project.evidenceMap on completion (FR-007a)
- Interview mode uses existing `include_action_steps=false` as baseline
- Constraint violations are warnings in strict mode, errors could block generation
- Empty evidence handling: skip/merge chapter and emit warning, not generate filler (FR-009a)
