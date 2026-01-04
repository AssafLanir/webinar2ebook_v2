# Tasks: Draft Quality System

**Input**: Design documents from `/specs/008-draft-quality/`

**Tests**: Included for core functionality (QA analysis, API endpoints)

**Organization**: Tasks grouped by user story (US1: QA Report, US2: QA UI, US3: Editor Pass, US4: Regression Suite)

---

## ⚠️ SUPERSEDED NOTICE

**US3 (Editor Pass)** and **US4 (Regression Suite)** are **SUPERSEDED** by Spec 009: Evidence-Grounded Drafting.

- **US3 → Spec 009 US3**: Targeted Rewrite Pass (uses Evidence Map + QA issues)
- **US4**: Deferred - can be implemented after Spec 009 if needed

**Do not implement Phase 5 or Phase 6 from this spec.** Use `/specs/009-evidence-grounded/tasks.md` instead.

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Paths: `backend/` for Python, `frontend/` for TypeScript

---

## Phase 1: Setup

**Purpose**: Project structure and shared dependencies

- [x] T001 Create QA report JSON schema at specs/008-draft-quality/schemas/qa_report.schema.json
- [x] T002 [P] Create TypeScript types for QA at frontend/src/types/qa.ts

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Models and utilities that all user stories depend on

**⚠️ CRITICAL**: Both QA Report and UI stories depend on these models

- [x] T003 Create QAReport, QAIssue, RubricScores, IssueCounts models in backend/src/models/qa_report.py (include truncated, total_issue_count fields)
- [x] T004 [P] Add qaReport field to Project model in backend/src/models/project.py
- [x] T005 [P] Create schema contract tests in backend/tests/unit/test_qa_models.py

**Checkpoint**: Foundation ready - QA models available for all stories

---

## Phase 3: User Story 1 - QA Report Generation (Priority: P1) 🎯 MVP

**Goal**: Generate structured QA reports with scores and issues after draft completion

**Independent Test**: Run QA analysis on a project → Get report with overall score, rubric breakdown, and issue list

### Tests for User Story 1

> **NOTE: Write tests FIRST, ensure they FAIL before implementation**

- [x] T006 [P] [US1] Create unit tests for structural analysis in backend/tests/unit/test_qa_structural.py
- [x] T007 [P] [US1] Create unit tests for semantic analysis in backend/tests/unit/test_qa_semantic.py
- [x] T008 [P] [US1] Create integration tests for QA API in backend/tests/integration/test_qa_api.py

### Implementation for User Story 1

- [x] T009 [P] [US1] Implement n-gram repetition detection in backend/src/services/qa_structural.py
- [x] T010 [P] [US1] Implement heading hierarchy validation in backend/src/services/qa_structural.py
- [x] T011 [P] [US1] Implement paragraph length analysis in backend/src/services/qa_structural.py
- [x] T012 [P] [US1] Implement chapter balance analysis in backend/src/services/qa_structural.py
- [x] T013 [US1] Implement faithfulness scoring (LLM-based) in backend/src/services/qa_semantic.py
- [x] T014 [US1] Implement clarity assessment (LLM-based) in backend/src/services/qa_semantic.py
- [x] T015 [US1] Create QA evaluator service combining structural + semantic in backend/src/services/qa_evaluator.py (cap issues at 300, compute issue_counts, set truncated flag)
- [x] T016 [US1] Create QA job store for async job tracking in backend/src/services/qa_job_store.py (reuse pattern from draft_service)
- [x] T017 [US1] Create QA API routes (analyze → job_id, status/{job_id}, report) in backend/src/api/routes/qa.py
- [x] T018 [US1] Register QA routes in backend/src/api/main.py
- [x] T019 [US1] Integrate QA auto-trigger after draft completion in backend/src/services/draft_service.py
- [x] T020 [US1] Implement unit tests (make tests pass) in backend/tests/unit/test_qa_structural.py
- [x] T021 [US1] Implement integration tests (make tests pass) in backend/tests/integration/test_qa_api.py

**Checkpoint**: QA reports generate automatically after draft completion. Can test via API.

---

## Phase 4: User Story 2 - QA Display in UI (Priority: P1)

**Goal**: Display QA results in a panel in Tab3 with summary badge and expandable issue list

**Independent Test**: View Tab3 after draft completion → See QA badge → Expand to see issues grouped by severity

### Implementation for User Story 2

- [x] T022 [P] [US2] Create QA API client in frontend/src/services/qaApi.ts (include polling for job status)
- [x] T023 [P] [US2] Create useQA hook for state management in frontend/src/hooks/useQA.ts
- [x] T024 [US2] Create QAIssueList component in frontend/src/components/tab3/QAIssueList.tsx (handle truncated display)
- [x] T025 [US2] Create QAPanel component with badge and expandable list in frontend/src/components/tab3/QAPanel.tsx
- [x] T026 [US2] Integrate QAPanel into Tab3Content in frontend/src/components/tab3/Tab3Content.tsx
- [x] T027 [US2] Add severity icons and color coding to issue display
- [x] T028 [US2] Test QA panel displays correctly after draft generation

**Checkpoint**: QA results visible in Tab3 UI. MVP complete (US1 + US2).

---

## Phase 5: User Story 3 - Editor Pass (Priority: P2) ❌ SUPERSEDED

> **⚠️ SUPERSEDED BY SPEC 009**: Do not implement this phase.
> See `/specs/009-evidence-grounded/tasks.md` Phase 4: US3 - Targeted Rewrite Pass

~~**Goal**: Optional improvement pass that rewrites text to fix issues without adding facts~~

~~**Independent Test**: Click "Run Improve Pass" → See progress → View before/after → Verify repetition reduced~~

### ~~Tests for User Story 3~~

- [x] ~~T029 [P] [US3] Create unit tests for editor pass~~ → SUPERSEDED
- [x] ~~T030 [P] [US3] Create integration tests for improve endpoint~~ → SUPERSEDED

### ~~Implementation for User Story 3~~

- [x] ~~T031 [US3] Create EditorPassResult model~~ → SUPERSEDED
- [x] ~~T032 [US3] Implement editor pass service~~ → SUPERSEDED
- [x] ~~T033 [US3] Add improve endpoint to QA routes~~ → SUPERSEDED
- [x] ~~T034 [US3] Add faithfulness verification after edit~~ → SUPERSEDED
- [x] ~~T035 [US3] Add "Run Improve Pass" button to QAPanel~~ → SUPERSEDED
- [x] ~~T036 [US3] Create before/after diff view component~~ → SUPERSEDED
- [x] ~~T037 [US3] Implement editor pass tests~~ → SUPERSEDED

**Checkpoint**: ~~Editor pass available~~ → See Spec 009 for Targeted Rewrite Pass

---

## Phase 6: User Story 4 - Regression Suite (Priority: P2) ⏸️ DEFERRED

> **⏸️ DEFERRED**: This phase is deferred until after Spec 009 is complete.
> Can be implemented later if regression testing is needed.

**Goal**: Regression suite with golden projects to track quality over time

**Independent Test**: Run regression suite in CI → See score comparison → Flag if below baseline

### Implementation for User Story 4 (DEFERRED)

- [ ] T038 [P] [US4] Create golden projects fixture at specs/008-draft-quality/fixtures/golden_projects.json
- [ ] T039 [US4] Create regression test runner in backend/tests/fixtures/test_qa_regression.py
- [ ] T040 [US4] Implement score comparison with tolerance in regression runner
- [ ] T041 [US4] Add CI-compatible output (pass/fail status)
- [ ] T042 [US4] Document regression suite usage in specs/008-draft-quality/quickstart.md

**Checkpoint**: ~~Regression suite runnable in CI~~ → Deferred to post-Spec 009

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validation and cleanup

- [ ] T043 Run all backend tests: `python -m pytest backend/tests/ -v`
- [ ] T044 Run frontend build: `npm run build`
- [ ] T045 Run quickstart.md validation (manual QA test in browser)
- [ ] T046 [P] Code review and cleanup

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational - Core QA functionality
- **US2 (Phase 4)**: Depends on US1 API being complete - Frontend display
- **US3 (Phase 5)**: Depends on US1 + US2 - Editor improvement
- **US4 (Phase 6)**: Depends on US1 - Regression testing
- **Polish (Phase 7)**: Depends on US1 + US2 minimum

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational - No dependencies on other stories
- **US2 (P1)**: Depends on US1 API endpoints being complete
- **US3 (P2)**: Depends on US1 (QA report) + US2 (UI to trigger)
- **US4 (P2)**: Depends on US1 (QA evaluator) only - can run parallel to US2/US3

### Within User Story 1

1. Tests first (T006-T008) - should fail initially
2. Parallel structural analysis (T009-T012) - no dependencies on each other
3. Sequential semantic analysis (T013-T014) - depends on LLM patterns
4. Evaluator service (T015) - combines T009-T014, caps issues at 300
5. Job store (T016) - async job tracking pattern
6. API routes (T017) - depends on T015, T016
7. Route registration (T018) - depends on T017
8. Draft integration (T019) - depends on T017
9. Make tests pass (T020-T021)

### Parallel Opportunities

```
# Phase 2 parallel:
T003 (models) || T004 (project update) || T005 (schema tests)

# US1 structural analysis parallel:
T009 (repetition) || T010 (headings) || T011 (paragraphs) || T012 (balance)

# US1 tests parallel:
T006 (structural tests) || T007 (semantic tests) || T008 (API tests)

# US2 frontend parallel:
T022 (API client) || T023 (hook)
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T005)
3. Complete Phase 3: US1 QA Report (T006-T021)
4. Complete Phase 4: US2 QA UI (T022-T028)
5. **STOP and VALIDATE**: Test QA in browser
6. MVP complete - users can see quality reports!

### Full Feature (US1 + US2 + US3 + US4)

1. Complete MVP (Phases 1-4)
2. Complete Phase 5: US3 Editor Pass (T029-T037)
3. Complete Phase 6: US4 Regression Suite (T038-T042)
4. Complete Phase 7: Polish (T043-T046)
5. Full feature ready for deployment

---

## File Summary

| File | Action | Phase |
|------|--------|-------|
| specs/008-draft-quality/schemas/qa_report.schema.json | NEW | Setup |
| frontend/src/types/qa.ts | NEW | Setup |
| backend/src/models/qa_report.py | NEW | Foundational |
| backend/src/models/project.py | UPDATE | Foundational |
| backend/tests/unit/test_qa_models.py | NEW | Foundational |
| backend/src/services/qa_structural.py | NEW | US1 |
| backend/src/services/qa_semantic.py | NEW | US1 |
| backend/src/services/qa_evaluator.py | NEW | US1 |
| backend/src/services/qa_job_store.py | NEW | US1 |
| backend/src/api/routes/qa.py | NEW | US1 |
| backend/src/api/main.py | UPDATE | US1 |
| backend/src/services/draft_service.py | UPDATE | US1 |
| frontend/src/services/qaApi.ts | NEW | US2 |
| frontend/src/hooks/useQA.ts | NEW | US2 |
| frontend/src/components/tab3/QAIssueList.tsx | NEW | US2 |
| frontend/src/components/tab3/QAPanel.tsx | NEW | US2 |
| frontend/src/components/tab3/Tab3Content.tsx | UPDATE | US2 |
| backend/src/services/editor_pass.py | NEW | US3 |
| frontend/src/components/tab3/DraftDiffView.tsx | NEW | US3 |
| backend/tests/fixtures/test_qa_regression.py | NEW | US4 |

---

## Notes

- [P] tasks = different files, no dependencies
- [US1/US2/US3/US4] label maps task to user story for traceability
- Hybrid approach: regex for structural (fast), LLM for semantic (accurate)
- QA report stored in project.qaReport field (no new collection)
- Issue list capped at 300 items to prevent MongoDB document bloat; issue_counts always accurate
- Always-async: analyze returns job_id, poll status/{job_id} for completion
- Editor pass bounded to single pass to prevent content drift
- Regression suite uses tolerance ranges for natural variation
