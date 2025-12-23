# Tasks: Tab 2 Visuals - Upload Library + Assign Assets

**Input**: Design documents from `/specs/005-tab2-visuals/`
**Prerequisites**: spec.md

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

**Purpose**: Backend dependencies and GridFS configuration

- [x] T001 Add Pillow to backend dependencies in `backend/pyproject.toml`
- [x] T002 [P] Create GridFS service module in `backend/src/services/gridfs_service.py`
- [x] T003 [P] Add GridFS connection helper to `backend/src/db/mongo.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extend existing models and add shared infrastructure

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Extend VisualAsset model with new fields (original_filename, size_bytes, caption, sha256, created_at) in `backend/src/models/visuals.py`
- [x] T005 [P] Create VisualAssignment model in `backend/src/models/visuals.py`
- [x] T006 Add assignments field to VisualPlan model in `backend/src/models/visuals.py`
- [x] T007 [P] Update VisualPlan default handling in project load (treat missing assignments as []) in `backend/src/services/project_service.py`
- [x] T008 [P] Create frontend types for VisualAsset extensions in `frontend/src/types/visuals.ts`
- [x] T009 [P] Create frontend VisualAssignment type in `frontend/src/types/visuals.ts`
- [x] T010 Update frontend VisualPlan type with assignments array in `frontend/src/types/visuals.ts`
- [x] T011 [P] Add legacy project.visuals → visualPlan.assets migration helper in `frontend/src/utils/visualMigration.ts`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Upload Client Visuals (Priority: P1) 🎯 MVP

**Goal**: User can upload PNG/JPG/WebP images and see them as thumbnails in Tab 2

**Independent Test**: Upload an image file, see thumbnail appear in library grid, refresh page and verify it persists

### Implementation for User Story 1

- [x] T012 [P] [US1] Implement thumbnail generation utility (Pillow, max 512px, PNG/JPEG) in `backend/src/services/image_utils.py`
- [x] T013 [P] [US1] Implement sha256 hash computation utility in `backend/src/services/image_utils.py`
- [x] T014 [US1] Create upload endpoint POST `/api/projects/{project_id}/visuals/assets/upload` in `backend/src/api/routes/visuals.py`
- [x] T014a [US1] Enforce backend validation in upload endpoint: file type (PNG/JPG/WebP), size (≤10MB), count (≤10 per project) - return `{data:null, error:{code:"UPLOAD_TOO_LARGE"|"UNSUPPORTED_MEDIA_TYPE"|"TOO_MANY_ASSETS"}}` in `backend/src/api/routes/visuals.py`
- [x] T015 [US1] Store original + thumbnail in GridFS via gridfs_service; set default caption (filename without extension) if none provided in `backend/src/services/visual_asset_service.py`
- [x] T016 [US1] Create serve endpoint GET `/api/projects/{project_id}/visuals/assets/{asset_id}/content` with project ownership check in `backend/src/api/routes/visuals.py`
- [x] T017 [US1] Register visuals router in `backend/src/api/main.py`
- [x] T017a [US1] Create backend integration tests for upload/serve in `backend/tests/integration/test_visuals_endpoints.py`:
  - Upload validation (rejects wrong type/size/count with proper error envelope)
  - Upload sets default caption (filename without extension) if none provided
  - Project-scoped serving (404 if asset not referenced by project's visualPlan.assets)
- [x] T018 [P] [US1] Create FileUploadDropzone component in `frontend/src/components/tab2/FileUploadDropzone.tsx`
- [x] T019 [P] [US1] Create AssetCard component (thumbnail, filename, dimensions) in `frontend/src/components/tab2/AssetCard.tsx`
- [x] T020 [US1] Create AssetGrid component in `frontend/src/components/tab2/AssetGrid.tsx`
- [x] T021 [US1] Create visualsApi service (upload, getContentUrl) in `frontend/src/services/visualsApi.ts`
- [x] T022 [US1] Integrate upload + grid into Tab2Content with visualPlan.assets state in `frontend/src/components/tab2/Tab2Content.tsx`
- [x] T023 [US1] Add ProjectContext actions for ADD_VISUAL_ASSET in `frontend/src/context/ProjectContext.tsx`
- [x] T024 [US1] Wire up debounced saveProject after upload completes in `frontend/src/components/tab2/Tab2Content.tsx`

**Checkpoint**: User can upload images, see thumbnails, and data persists on refresh

---

## Phase 4: User Story 2 - Assign Asset to Opportunity (Priority: P1)

**Goal**: User can pick an image from the library and attach it to a visual opportunity (or skip)

**Independent Test**: With visual opportunities from Tab 3, assign an asset to one, mark another as skipped, refresh and verify assignments persist

**MVP Scope**: Assignment is **opportunity-driven only** - user clicks "Assign" on an OpportunityCard and picks from library. The reverse flow (AssetCard → "Assign to opportunity...") is **P2** and not included in this phase.

### Implementation for User Story 2

- [ ] T025 [P] [US2] Create OpportunityCard component (title, type, rationale, assignment state) in `frontend/src/components/tab2/OpportunityCard.tsx`
- [ ] T026 [P] [US2] Create OpportunityList component (grouped by chapter) in `frontend/src/components/tab2/OpportunityList.tsx`
- [ ] T027 [US2] Create AssetPickerModal component (select asset for opportunity) in `frontend/src/components/tab2/AssetPickerModal.tsx`
- [ ] T028 [US2] Add empty state for no opportunities in OpportunityList in `frontend/src/components/tab2/OpportunityList.tsx`
- [ ] T029 [US2] Add ProjectContext actions for SET_VISUAL_ASSIGNMENT, REMOVE_VISUAL_ASSIGNMENT in `frontend/src/context/ProjectContext.tsx`
- [ ] T030 [US2] Implement assign/unassign/skip handlers in Tab2Content in `frontend/src/components/tab2/Tab2Content.tsx`
- [ ] T031 [US2] Wire up debounced saveProject after assignment changes in `frontend/src/components/tab2/Tab2Content.tsx`

**Checkpoint**: User can assign assets to opportunities, skip opportunities, and assignments persist

---

## Phase 5: User Story 3 - Persist Library + Assignments (Priority: P1)

**Goal**: Refresh page and see same assets and assignments

**Independent Test**: Upload assets, make assignments, refresh browser, verify all data intact

### Implementation for User Story 3

- [ ] T032 [US3] Ensure visualPlan.assets and visualPlan.assignments are included in project save payload in `frontend/src/services/api.ts`
- [ ] T033 [US3] Add delete asset endpoint DELETE `/api/projects/{project_id}/visuals/assets/{asset_id}` in `backend/src/api/routes/visuals.py`
- [ ] T034 [US3] Implement delete handler that removes GridFS bytes in `backend/src/services/visual_asset_service.py`
- [ ] T034a [US3] Add delete integration test (removes GridFS bytes, returns success envelope) in `backend/tests/integration/test_visuals_endpoints.py`
- [ ] T035 [US3] Add delete button to AssetCard with confirmation in `frontend/src/components/tab2/AssetCard.tsx`
- [ ] T036 [US3] Add ProjectContext action for REMOVE_VISUAL_ASSET in `frontend/src/context/ProjectContext.tsx`
- [ ] T037 [US3] Remove assignment records referencing deleted asset (delete the VisualAssignment entry, not set status) in `frontend/src/context/ProjectContext.tsx`
- [ ] T038 [US3] Wire up delete + saveProject in Tab2Content in `frontend/src/components/tab2/Tab2Content.tsx`

**Checkpoint**: Full CRUD for assets, assignments auto-cleared on delete, persistence complete

---

## Phase 6: User Story 4 - Download/Copy Asset (Priority: P2)

**Goal**: User can download an uploaded image or copy its URL/markdown snippet

**Independent Test**: Click download on an asset, verify file downloads with correct name; click "Copy URL", verify clipboard contains the asset content URL

**Note**: "Copy image to clipboard" (binary) is **not included** due to browser permission complexity. Instead we implement:
- **Copy URL**: Copies the project-scoped content URL to clipboard
- **Copy Markdown**: Copies `![caption](url)` snippet for pasting into external docs

### Implementation for User Story 4

- [ ] T039 [US4] Add download button to AssetCard in `frontend/src/components/tab2/AssetCard.tsx`
- [ ] T040 [US4] Implement download handler (fetch full size, trigger browser download) in `frontend/src/components/tab2/AssetCard.tsx`
- [ ] T041 [US4] Add "Copy URL" button to AssetCard (copies content endpoint URL to clipboard) in `frontend/src/components/tab2/AssetCard.tsx`
- [ ] T042 [US4] Add "Copy Markdown" button to AssetCard (copies `![caption](url)` to clipboard) in `frontend/src/components/tab2/AssetCard.tsx`

**Checkpoint**: User can download any uploaded asset and copy URL/markdown to clipboard

---

## Phase 7: User Story 5 - Metadata Editing (Priority: P2)

**Goal**: User can edit caption/alt text for an image

**Independent Test**: Edit caption on an asset, refresh, verify caption persists

### Implementation for User Story 5

- [ ] T043 [P] [US5] Create AssetMetadataModal component (edit caption, alt_text) in `frontend/src/components/tab2/AssetMetadataModal.tsx`
- [ ] T044 [US5] Add "Edit metadata" button to AssetCard in `frontend/src/components/tab2/AssetCard.tsx`
- [ ] T045 [US5] Add ProjectContext action for UPDATE_VISUAL_ASSET_METADATA in `frontend/src/context/ProjectContext.tsx`
- [ ] T046 [US5] Wire up metadata edit + saveProject in Tab2Content in `frontend/src/components/tab2/Tab2Content.tsx`

**Checkpoint**: User can edit and persist asset metadata

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Error handling, regeneration warning, cleanup

- [ ] T047 Add upload validation error handling (file type, size) with toast notifications in `frontend/src/components/tab2/FileUploadDropzone.tsx`
- [ ] T048 Add regeneration warning modal (clear assignments on confirm) in `frontend/src/components/tab3/Tab3Content.tsx`
- [ ] T049 [P] Add error codes (UNSUPPORTED_MEDIA_TYPE, UPLOAD_TOO_LARGE, etc.) to backend in `backend/src/api/exceptions.py`
- [ ] T050 [P] Clean up legacy Tab2Content components (VisualGallery, AddCustomVisual) in `frontend/src/components/tab2/`
- [ ] T051 Run manual acceptance scenarios AS-001 through AS-007 from spec

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 → US2 → US3 form the P1 MVP chain
  - US4 and US5 can proceed after US3 in parallel
- **Polish (Phase 8)**: Depends on all P1 user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Upload - Foundation for all other stories
- **User Story 2 (P1)**: Assign - Depends on US1 (need assets to assign)
- **User Story 3 (P1)**: Persist - Depends on US1+US2 (need assets and assignments to persist)
- **User Story 4 (P2)**: Download - Depends on US1 (need assets to download)
- **User Story 5 (P2)**: Metadata - Depends on US1 (need assets to edit)

### Within Each User Story

- Backend before frontend (endpoints before UI)
- Services before routes
- Components before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel
- Within US1: T012+T013 (utilities), T018+T019 (components) can run in parallel
- US4 and US5 can run in parallel after US3 completes

---

## Parallel Example: User Story 1

```bash
# Backend utilities in parallel:
Task: "Implement thumbnail generation utility in backend/src/services/image_utils.py"
Task: "Implement sha256 hash computation utility in backend/src/services/image_utils.py"

# Frontend components in parallel:
Task: "Create FileUploadDropzone component in frontend/src/components/tab2/FileUploadDropzone.tsx"
Task: "Create AssetCard component in frontend/src/components/tab2/AssetCard.tsx"
```

---

## Implementation Strategy

### MVP First (User Stories 1-3)

1. Complete Phase 1: Setup (Pillow, GridFS)
2. Complete Phase 2: Foundational (models, types, migration)
3. Complete Phase 3: US1 - Upload
4. Complete Phase 4: US2 - Assign
5. Complete Phase 5: US3 - Persist + Delete
6. **STOP and VALIDATE**: Test all P1 acceptance scenarios (AS-001 through AS-005)
7. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Models and infrastructure ready
2. Add US1 → Upload works → Demo
3. Add US2 → Assignment works → Demo
4. Add US3 → Full persistence → Demo (MVP Complete!)
5. Add US4 → Download feature → Demo
6. Add US5 → Metadata editing → Demo
7. Polish → Production ready

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- GridFS stores both original and thumbnail variants
- Project-scoped endpoints enforce ownership checks
- **Assignments are records; "unassigned" = no record exists** - when unassigning or deleting an asset, DELETE the VisualAssignment document (do NOT set `status: "unassigned"`)
- Legacy project.visuals migrated in-memory, not mutated
- Backend is the enforcement layer for validations (type/size/count) - frontend shows errors but curl must also be blocked
- **Default caption on upload**: Server sets `caption = filename (without extension)` if none provided, so UI never shows blank captions
