# Tasks: Interview Q&A Book Format

**Input**: Design documents from `/specs/004-tab3-ai-draft/`
**Branch**: `004-interview-qa-format`
**Spec Sections**: 10.4.1, 11.2, AS-008, AS-009

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 = AS-008 (Q&A Format), US2 = AS-009 (Auto-Configuration)

## User Stories

| ID | Title | Priority | Acceptance Scenario |
|----|-------|----------|---------------------|
| US1 | Interview Q&A Format | P1 | AS-008 |
| US2 | Auto-Configuration | P1 | AS-009 |

---

## Phase 1: Setup (Backend Model)

**Purpose**: Add `interview_qa` to BookFormat enum and sync types

- [ ] T001 Add `interview_qa` value to `BookFormat` enum in `backend/src/models/style_config.py`
- [ ] T002 [P] Add `interview_qa` to BookFormat type in `frontend/src/types/style.ts`
- [ ] T003 [P] Add "Interview Q&A" preset to `frontend/src/constants/stylePresets.ts`

**Checkpoint**: Types synchronized across backend and frontend

---

## Phase 2: User Story 1 - Q&A Generation (Priority: P1) 🎯 MVP

**Goal**: Generate ebooks with Q&A structure using questions as section headers

**Independent Test**: Generate draft with `book_format: "interview_qa"` and verify:
- Questions appear as `###` headers
- Topics grouped under `##` headers
- Speaker voice preserved with quotes
- No "Key Takeaways" or "Action Steps"

### Tests (Write First)

- [ ] T004 [US1] Create unit tests for Q&A prompts in `backend/tests/unit/test_interview_qa_prompts.py`
  - Test `INTERVIEW_QA_SYSTEM_PROMPT` contains Q&A structure instructions
  - Test `build_interview_qa_chapter_prompt()` includes question extraction
  - Test prompt forbids takeaways/action steps

- [ ] T005 [US1] Create unit tests for Q&A output validation in `backend/tests/unit/test_interview_qa_format.py`
  - Test output uses `###` for questions
  - Test output uses `##` for topic groupings
  - Test output contains blockquotes for notable statements
  - Test output excludes forbidden sections

### Implementation

- [ ] T006 [US1] Create `INTERVIEW_QA_SYSTEM_PROMPT` in `backend/src/services/prompts.py`
  - Instruct LLM to use Q&A structure
  - Specify question headers at `###` level
  - Specify topic groupings at `##` level
  - Include few-shot example of expected output format
  - Explicitly forbid "Key Takeaways", "Action Steps", "Summary" sections

- [ ] T007 [US1] Create `build_interview_qa_chapter_prompt()` in `backend/src/services/prompts.py`
  - Extract questions from transcript segment
  - Group by topic/theme
  - Include speaker name for attribution
  - Request blockquotes for notable statements

- [ ] T008 [US1] Update `generate_chapter()` in `backend/src/services/draft_service.py`
  - Check if `book_format == "interview_qa"`
  - Route to Q&A-specific prompt builder
  - Use `INTERVIEW_QA_SYSTEM_PROMPT` instead of default

- [ ] T009 [US1] Make tests pass - run `pytest backend/tests/unit/test_interview_qa_*.py -v`

**Checkpoint**: Q&A generation produces correct structure

---

## Phase 3: User Story 2 - Auto-Configuration (Priority: P1)

**Goal**: Automatically enforce strict settings when interview_qa is selected

**Independent Test**: Select `interview_qa` format and verify:
- `content_mode` forced to "interview"
- `faithfulness_level` forced to "strict"
- Takeaway/action step flags forced to false
- Settings locked in UI

### Tests (Write First)

- [ ] T010 [US2] Create unit tests for auto-configuration in `backend/tests/unit/test_interview_qa_autoconfig.py`
  - Test `normalize_style_config()` enforces settings for interview_qa
  - Test original settings preserved for other formats
  - Test all required fields are set correctly

### Implementation

- [ ] T011 [US2] Update `normalize_style_config()` in `backend/src/services/normalization.py`
  - If `book_format == "interview_qa"`:
    - Set `content_mode = "interview"`
    - Set `faithfulness_level = "strict"`
    - Set `include_key_takeaways = false`
    - Set `include_action_steps = false`
    - Set `include_checklists = false`

- [ ] T012 [P] [US2] Update StyleControls component in `frontend/src/components/tab3/StyleControls.tsx`
  - When `interview_qa` selected, disable/lock related controls
  - Show visual indicator that settings are auto-configured
  - Add tooltip explaining why settings are locked

- [ ] T013 [US2] Make tests pass - run `pytest backend/tests/unit/test_interview_qa_autoconfig.py -v`

**Checkpoint**: Settings automatically enforced and UI reflects locked state

---

## Phase 4: Integration Testing

**Purpose**: End-to-end validation with real interview transcript

- [ ] T014 Create integration test in `backend/tests/integration/test_interview_qa_generation.py`
  - Use sample interview transcript (Sarah Chen / DataFlow)
  - Generate draft with `interview_qa` format
  - Verify output structure matches AS-008 criteria
  - Verify no forbidden patterns (action steps, invented bio, platitudes)

- [ ] T015 Run full test suite and verify no regressions
  - `pytest backend/tests/ -v`
  - `npm run build` (frontend)

**Checkpoint**: Feature complete and tested

---

## Phase 5: Polish & Documentation

**Purpose**: Final touches and documentation updates

- [ ] T016 [P] Update quickstart.md with Interview Q&A testing scenario
- [ ] T017 [P] Add Interview Q&A example to API documentation (if applicable)

---

## Dependencies

```
T001 ─┬─► T004 ─► T006 ─► T007 ─► T008 ─► T009 ─► T014
      │
T002 ─┤
      │
T003 ─┴─► T010 ─► T011 ─► T012 ─► T013 ─► T014 ─► T015
```

**Parallel Opportunities**:
- T001, T002, T003 can run in parallel (different files)
- T004 and T010 can run in parallel (different test files)
- T012 can run in parallel with T011 (frontend vs backend)
- T016 and T017 can run in parallel

## MVP Scope

**Minimum Viable Product**: Phase 1 + Phase 2 (T001-T009)

This delivers:
- Working `interview_qa` book format
- Q&A structure in generated output
- No artificial takeaways/action steps

Auto-configuration (Phase 3) and integration tests (Phase 4) can follow.

## Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 1 | T001-T003 | Setup & Types |
| 2 | T004-T009 | Q&A Generation (US1) |
| 3 | T010-T013 | Auto-Configuration (US2) |
| 4 | T014-T015 | Integration Testing |
| 5 | T016-T017 | Polish |
| **Total** | **17 tasks** | |
