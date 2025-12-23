# Tasks: Tab 4 Final Assembly + Preview + PDF Export

**Input**: Design documents from `/specs/006-tab4-export/`
**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/src/`, `backend/tests/`
- **Frontend**: `frontend/src/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies and project structure for export feature

- [x] T001 Add WeasyPrint and markdown dependencies to `backend/pyproject.toml`
- [x] T002 [P] Verify WeasyPrint system dependencies are installed (cairo, pango)
- [x] T003 [P] Create `frontend/src/components/tab4/` directory structure

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models and services that all user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Create ExportJob and ExportJobStatus models in `backend/src/models/export_job.py`
- [x] T005 Create export API response models (PreviewData, ExportStartData, ExportStatusData, ExportCancelData) in `backend/src/models/api_responses.py`
- [x] T006 Create ExportJobStore (MongoDB + in-memory) following job_store.py pattern in `backend/src/services/export_job_store.py`
- [x] T007 [P] Create frontend TypeScript types for export in `frontend/src/types/export.ts`
- [x] T008 Create ebook router skeleton and register in `backend/src/api/routes/ebook.py` + `backend/src/api/main.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Preview Assembled Ebook (Priority: P1) 🎯 MVP

**Goal**: User can see a rendered preview of their ebook in Tab 4 with cover page, TOC, chapters, and assigned images

**Independent Test**: Open Tab 4 with a project that has draft + assigned images → preview shows chapters with images in place

### Implementation for User Story 1

- [x] T009 [P] [US1] Create CSS styles for ebook preview (cover, TOC, chapters, figures) in `backend/src/services/ebook_styles.py`
- [x] T010 [US1] Create EbookRenderer service (markdown → HTML with TOC, cover, image insertion) in `backend/src/services/ebook_renderer.py`
- [x] T011 [US1] Implement image insertion logic in EbookRenderer (match assignments to opportunities, insert at chapter/section)
- [x] T012 [US1] Implement GET `/api/projects/{project_id}/ebook/preview` endpoint in `backend/src/api/routes/ebook.py`
- [x] T013 [P] [US1] Create exportApi service with getPreview function in `frontend/src/services/exportApi.ts`
- [x] T014 [P] [US1] Create PreviewPanel component (HTML iframe/container, loading state) in `frontend/src/components/tab4/PreviewPanel.tsx`
- [x] T015 [US1] Create Tab4Content component (layout container) in `frontend/src/components/tab4/Tab4Content.tsx`
- [x] T016 [US1] Create tab4 index.ts exports in `frontend/src/components/tab4/index.ts`
- [x] T017 [US1] Wire Tab4Content into main app tabs (replace placeholder if exists) in `frontend/src/App.tsx` or tab navigation

**Checkpoint**: User can view HTML preview of ebook with cover, TOC, chapters, and assigned images

---

## Phase 4: User Story 2 - Export Ebook as PDF (Priority: P1)

**Goal**: User can download their assembled ebook as a PDF file with all content and images embedded

**Independent Test**: Click "Download PDF" → progress shows → PDF file downloads with correct content and images

### Implementation for User Story 2

- [x] T018 [US2] Create PdfGenerator service (WeasyPrint wrapper with base64 image embedding) in `backend/src/services/pdf_generator.py`
- [x] T019 [US2] Create filename sanitization utility in `backend/src/services/pdf_generator.py`
- [x] T020 [US2] Implement POST `/api/projects/{project_id}/ebook/export` endpoint (start job) in `backend/src/api/routes/ebook.py`
- [x] T021 [US2] Implement GET `/api/projects/{project_id}/ebook/export/status/{job_id}` endpoint in `backend/src/api/routes/ebook.py`
- [x] T022 [US2] Implement GET `/api/projects/{project_id}/ebook/export/download/{job_id}` endpoint (stream PDF) in `backend/src/api/routes/ebook.py`
- [x] T023 [US2] Implement POST `/api/projects/{project_id}/ebook/export/cancel/{job_id}` endpoint in `backend/src/api/routes/ebook.py`
- [x] T024 [US2] Implement background PDF generation task with progress updates in `backend/src/services/pdf_generator.py`
- [x] T025 [P] [US2] Add export API functions (startExport, getExportStatus, downloadExport, cancelExport) to `frontend/src/services/exportApi.ts`
- [x] T026 [P] [US2] Create useExport hook (start, poll status, download, cancel) in `frontend/src/hooks/useExport.ts`
- [x] T027 [US2] Create ExportActions component (Download PDF button, progress bar, cancel) in `frontend/src/components/tab4/ExportActions.tsx`
- [x] T028 [US2] Integrate ExportActions into Tab4Content in `frontend/src/components/tab4/Tab4Content.tsx`

**Checkpoint**: User can export PDF with progress tracking, cancellation, and automatic download on completion

---

## Phase 5: User Story 3 - Edit Final Metadata (Priority: P2)

**Goal**: User can edit title, subtitle, and credits that appear on cover page before exporting

**Independent Test**: Edit title in Tab 4 → preview updates → export PDF shows new title

### Implementation for User Story 3

- [x] T029 [P] [US3] Create MetadataForm component (editable fields for finalTitle, finalSubtitle, creditsText) in `frontend/src/components/tab4/MetadataForm.tsx`
- [x] T030 [US3] Add ProjectContext actions for UPDATE_FINAL_TITLE, UPDATE_FINAL_SUBTITLE, UPDATE_CREDITS if not already present in `frontend/src/context/ProjectContext.tsx`
- [x] T031 [US3] Wire MetadataForm into Tab4Content with Save button in `frontend/src/components/tab4/Tab4Content.tsx`
- [x] T032 [US3] Implement preview refresh on metadata change in `frontend/src/components/tab4/Tab4Content.tsx`

**Checkpoint**: User can edit metadata, see preview update, and export PDF with customized cover

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Error handling, edge cases, validation

- [x] T033 [P] Add empty state handling to PreviewPanel (no draft → show message, disable export) in `frontend/src/components/tab4/PreviewPanel.tsx`
- [x] T034 [P] Add error handling for export failures with retry button in `frontend/src/components/tab4/ExportActions.tsx`
- [x] T035 Add graceful handling for missing images in EbookRenderer (skip missing, log warning) in `backend/src/services/ebook_renderer.py`
- [x] T036 [P] Create integration test for preview endpoint in `backend/tests/integration/test_ebook_preview.py`
- [x] T037 [P] Create integration test for export flow in `backend/tests/integration/test_pdf_export.py`
- [x] T038 Run manual acceptance scenarios AS-001 through AS-003 from spec (verified via integration tests)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1 (Preview) → US2 (Export) → US3 (Metadata) is the recommended order
  - US2 depends on US1's renderer
  - US3 can start after US1 if needed
- **Polish (Phase 6)**: Depends on all P1 user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - Creates renderer used by US2
- **User Story 2 (P1)**: Depends on US1 (needs EbookRenderer for PDF generation)
- **User Story 3 (P2)**: Can start after US1 (needs preview to show changes)

### Within Each User Story

- Backend services before API endpoints
- API endpoints before frontend integration
- Frontend components before wiring
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- T007 (frontend types) can run parallel with backend foundational work
- Within US1: T009 (styles) and T013/T014 (frontend components) can run in parallel
- Within US2: T025/T026 (frontend API/hooks) can run in parallel
- US3 tasks T029 (MetadataPanel) can start while US2 finishes

---

## Parallel Example: User Story 1

```bash
# Backend styles + frontend components in parallel:
Task: "Create CSS styles for ebook preview in backend/src/services/ebook_styles.py"
Task: "Create PreviewPanel component in frontend/src/components/tab4/PreviewPanel.tsx"
Task: "Create exportApi service in frontend/src/services/exportApi.ts"
```

---

## Implementation Strategy

### MVP First (User Stories 1-2)

1. Complete Phase 1: Setup (dependencies)
2. Complete Phase 2: Foundational (models, job store)
3. Complete Phase 3: US1 - Preview (core value!)
4. Complete Phase 4: US2 - PDF Export (deliverable!)
5. **STOP and VALIDATE**: Test preview + export flow end-to-end
6. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Infrastructure ready
2. Add US1 (Preview) → Users can preview ebook → Demo
3. Add US2 (Export) → Users can download PDF → Demo (MVP Complete!)
4. Add US3 (Metadata) → Users can customize cover → Demo
5. Polish → Production ready

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- WeasyPrint requires system-level dependencies (cairo, pango) - see quickstart.md
- PDF generation is async with job-based pattern (same as Spec 004 draft generation)
- Images embedded as base64 data URIs in PDF (not HTTP URLs) per research.md decision
- Preview uses HTTP URLs for images (faster), PDF uses embedded data URIs
- Temporary PDF files cleaned up by job TTL (1 hour after completion)
