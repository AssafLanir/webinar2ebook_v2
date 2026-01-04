# Tasks: Tab 4 EPUB Export

**Input**: Design documents from `/specs/007-tab4-epub-export/`

**Tests**: Included (explicitly required in plan.md "Integration Test Requirements" section)

**Organization**: Tasks grouped by user story (US1: EPUB Export, US2: Format Selection)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2)
- Paths: `backend/` for Python, `frontend/` for TypeScript

---

## Phase 1: Setup

**Purpose**: Install new dependency and prepare project

- [x] T001 Add ebooklib>=0.18 to backend/pyproject.toml dependencies
- [x] T002 Run pip install to verify ebooklib installs correctly

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Enum/type updates that MUST be complete before user story implementation

**⚠️ CRITICAL**: Both stories depend on the ExportFormat enum having "epub" value

- [x] T003 Add "epub" to ExportFormat enum in backend/src/models/export_job.py
- [x] T004 [P] Add "epub" to ExportFormat type in frontend/src/types/export.ts

**Checkpoint**: Foundation ready - EPUB format recognized by both backend and frontend

---

## Phase 3: User Story 1 - EPUB Export (Priority: P1) 🎯 MVP

**Goal**: User can export their ebook as an EPUB file with all content and images embedded

**Independent Test**: Click "Export EPUB" → EPUB file downloads → Opens correctly in e-reader app

### Tests for User Story 1

> **NOTE: Write tests FIRST, ensure they FAIL before implementation**

- [x] T005 [P] [US1] Create unit test file backend/tests/unit/test_epub_generator.py with test stubs for EpubGenerator including EPUB structure sanity test (verify: valid ZIP, mimetype="application/epub+zip", META-INF/container.xml exists, *.opf exists, nav.xhtml exists)
- [x] T006 [P] [US1] Create integration test file backend/tests/integration/test_epub_export.py with header assertions (Content-Type, Content-Disposition)

### Implementation for User Story 1

- [x] T007 [P] [US1] Create EPUB stylesheet as Python constant in backend/src/services/epub_styles.py (copy CSS from specs/007-tab4-epub-export/research.md section 5)
- [x] T008 [P] [US1] Create image conversion utilities (WebP→JPEG/PNG, downscale) in backend/src/services/image_utils.py
- [x] T009 [US1] Create EpubGenerator service in backend/src/services/epub_generator.py with generate() method that accepts progress_callback and checks for cancellation between stages
- [x] T010 [US1] Implement cover page generation in EpubGenerator (title, subtitle, credits) - call progress_callback(10)
- [x] T011 [US1] Implement chapter generation in EpubGenerator (markdown → XHTML, image insertion) - call progress_callback(30-60), check cancellation between chapters
- [x] T012 [US1] Implement TOC generation in EpubGenerator (flat H1-based navigation) - call progress_callback(70)
- [x] T013 [US1] Implement image embedding in EpubGenerator (fetch from GridFS, convert if WebP, add as EpubImage) - call progress_callback(80-90), check cancellation between images
- [x] T014 [US1] Update export endpoint in backend/src/api/routes/ebook.py to handle format="epub"
- [x] T015 [US1] Add EPUB Content-Type and Content-Disposition headers to download endpoint in backend/src/api/routes/ebook.py
- [x] T016 [US1] Implement unit tests in backend/tests/unit/test_epub_generator.py (make tests pass)
- [x] T017 [US1] Implement integration tests in backend/tests/integration/test_epub_export.py (make tests pass)

**Checkpoint**: EPUB export works end-to-end via API. Can test with curl or Postman.

---

## Phase 4: User Story 2 - Format Selection (Priority: P2)

**Goal**: User can choose between PDF and EPUB formats in the Tab 4 UI

**Independent Test**: Tab 4 shows both "Download PDF" and "Download EPUB" buttons → each produces correct file format

### Implementation for User Story 2

- [x] T018 [US2] Add "Download EPUB" button to frontend/src/components/tab4/ExportActions.tsx
- [x] T019 [US2] Wire EPUB button to useExport hook with format="epub" in frontend/src/components/tab4/ExportActions.tsx
- [x] T020 [US2] Verify both PDF and EPUB buttons share progress/cancel UI correctly

**Checkpoint**: Full feature complete - users can export as PDF or EPUB from UI

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Validation and cleanup

- [x] T021 Run backend tests: `python -m pytest backend/tests/ -v`
- [x] T022 Run quickstart.md validation (manual EPUB export test in browser)
- [ ] T023 [P] Validate generated EPUB with epubcheck (development validation only)
- [x] T024 Code review and cleanup

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational - Core EPUB functionality
- **US2 (Phase 4)**: Depends on Foundational + US1 backend complete - Frontend button
- **Polish (Phase 5)**: Depends on US1 + US2

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on US2
- **US2 (P2)**: Depends on US1 backend implementation (T014, T015) being complete for end-to-end testing

### Within User Story 1

1. Tests first (T005, T006) - should fail initially (T005 includes EPUB structure sanity test)
2. Parallel utilities (T007, T008) - no dependencies on each other
3. EpubGenerator core (T009) - depends on T007, T008; includes progress_callback + cancellation check skeleton
4. EpubGenerator features (T010-T013) - sequential, building on T009; each stage calls progress_callback and checks cancellation
5. API integration (T014, T015) - depends on T009
6. Make tests pass (T016, T017) - depends on implementation

### Parallel Opportunities

```
# Phase 2 parallel:
T003 (backend enum) || T004 (frontend type)

# US1 tests parallel:
T005 (unit tests) || T006 (integration tests)

# US1 utilities parallel:
T007 (CSS) || T008 (image utils)
```

---

## Parallel Example: User Story 1

```bash
# Launch test stubs in parallel:
Task: "Create unit test file backend/tests/unit/test_epub_generator.py"
Task: "Create integration test file backend/tests/integration/test_epub_export.py"

# Launch utilities in parallel:
Task: "Create EPUB stylesheet in backend/src/services/epub_styles.py"
Task: "Create image conversion utilities in backend/src/services/image_utils.py"
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T004)
3. Complete Phase 3: US1 EPUB Export (T005-T017)
4. **STOP and VALIDATE**: Test EPUB export via API
5. EPUB generation works - MVP complete!

### Full Feature (US1 + US2)

1. Complete MVP (Phases 1-3)
2. Complete Phase 4: US2 Format Selection (T018-T020)
3. Complete Phase 5: Polish (T021-T024)
4. Full feature ready for deployment

---

## File Summary

| File | Action | Phase |
|------|--------|-------|
| backend/pyproject.toml | UPDATE | Setup |
| backend/src/models/export_job.py | UPDATE | Foundational |
| frontend/src/types/export.ts | UPDATE | Foundational |
| backend/tests/unit/test_epub_generator.py | NEW | US1 |
| backend/tests/integration/test_epub_export.py | NEW | US1 |
| backend/src/services/epub_styles.py | NEW | US1 |
| backend/src/services/image_utils.py | NEW | US1 |
| backend/src/services/epub_generator.py | NEW | US1 |
| backend/src/api/routes/ebook.py | UPDATE | US1 |
| frontend/src/components/tab4/ExportActions.tsx | UPDATE | US2 |

---

## Notes

- [P] tasks = different files, no dependencies
- [US1/US2] label maps task to user story for traceability
- Tests written first (TDD) per plan.md requirements
- WebP conversion handles images from Tab 2 uploads (Spec 005)
- Reuse EbookRenderer from Spec 006 for chapter/image logic where applicable
- EPUB file lifecycle: `/tmp/webinar2ebook/exports/{job_id}.epub` with TTL cleanup
