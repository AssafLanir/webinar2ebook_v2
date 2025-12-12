# Tasks: Backend Foundation

**Input**: Design documents from `/specs/002-backend-foundation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml

**Tests**: Included per spec requirements (backend API tests + frontend E2E test)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/src/`, `backend/tests/`
- **Frontend**: `frontend/src/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Backend project initialization and basic structure

- [X] T001 Create backend directory structure: `backend/src/models/`, `backend/src/services/`, `backend/src/api/routes/`, `backend/src/db/`, `backend/tests/`
- [X] T002 Initialize Python project with pyproject.toml in `backend/pyproject.toml` (FastAPI, Pydantic, Motor, pytest dependencies)
- [X] T003 [P] Create backend README with setup instructions in `backend/README.md`
- [X] T004 [P] Configure Python linting (ruff) and formatting in `backend/pyproject.toml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core backend infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Implement MongoDB connection setup with Motor async driver in `backend/src/db/mongo.py`
- [X] T006 [P] Implement response envelope helpers (success/error wrappers) in `backend/src/api/response.py`
- [X] T007 [P] Implement custom exception classes (ProjectNotFoundError, ValidationError) in `backend/src/api/exceptions.py`
- [X] T008 Create FastAPI app with CORS middleware in `backend/src/api/main.py`
- [X] T009 [P] Implement health check route (GET /health) in `backend/src/api/routes/health.py`
- [X] T010 [P] Create Pydantic models for Project, OutlineItem, Resource, WebinarType in `backend/src/models/project.py`
- [X] T011 Register routes in main app and verify startup in `backend/src/api/main.py`
- [X] T012 [P] Create pytest conftest with test database fixtures in `backend/tests/conftest.py`
- [X] T013 [P] Create API client module for frontend in `frontend/src/services/api.ts`
- [X] T014 Update frontend types to align with backend model in `frontend/src/types/project.ts`

**Checkpoint**: Foundation ready - Backend runs, health endpoint works, frontend can make API calls

---

## Phase 3: User Story 1 - Create and Persist a New Project (Priority: P1) 🎯 MVP

**Goal**: Users can create a new project that persists to the database and opens in workspace

**Independent Test**: Create a project via POST /projects, verify it returns valid Project with ID and timestamps

### Tests for User Story 1

- [X] T015 [P] [US1] Create POST /projects contract test in `backend/tests/test_projects.py::test_create_project_success`
- [X] T016 [P] [US1] Create POST /projects validation error test in `backend/tests/test_projects.py::test_create_project_invalid`

### Implementation for User Story 1

- [X] T017 [US1] Implement ProjectService.create() method in `backend/src/services/project_service.py`
- [X] T018 [US1] Implement POST /projects endpoint in `backend/src/api/routes/projects.py`
- [X] T019 [US1] Add createProject() function to frontend API client in `frontend/src/services/api.ts`
- [X] T020 [US1] Update ProjectContext to call createProject API on form submit in `frontend/src/context/ProjectContext.tsx`
- [X] T021 [US1] Verify existing create project form works with backend persistence in `frontend/src/pages/LandingPage.tsx`

**Checkpoint**: Create project via UI → Project persisted to MongoDB → Project opens in workspace

---

## Phase 4: User Story 2 - View and Open Existing Projects (Priority: P1)

**Goal**: Users see a list of existing projects on app load and can open any project

**Independent Test**: GET /projects returns list, GET /projects/{id} returns full project, opening loads into workspace

### Tests for User Story 2

- [X] T022 [P] [US2] Create GET /projects list test in `backend/tests/test_projects.py::test_list_projects`
- [X] T023 [P] [US2] Create GET /projects/{id} success test in `backend/tests/test_projects.py::test_get_project_success`
- [X] T024 [P] [US2] Create GET /projects/{id} not found test in `backend/tests/test_projects.py::test_get_project_not_found`

### Implementation for User Story 2

- [X] T025 [US2] Implement ProjectService.list() method (sorted by updatedAt desc) in `backend/src/services/project_service.py`
- [X] T026 [US2] Implement ProjectService.get(id) method in `backend/src/services/project_service.py`
- [X] T027 [US2] Implement GET /projects endpoint in `backend/src/api/routes/projects.py`
- [X] T028 [US2] Implement GET /projects/{id} endpoint in `backend/src/api/routes/projects.py`
- [X] T029 [US2] Add fetchProjects() and fetchProject(id) to frontend API client in `frontend/src/services/api.ts`
- [X] T030 [US2] Transform LandingPage into ProjectListPage with project list display in `frontend/src/pages/LandingPage.tsx`
- [X] T031 [US2] Add loading state and error handling for project list fetch in `frontend/src/pages/LandingPage.tsx`
- [X] T032 [US2] Implement Open button that calls fetchProject and loads into context in `frontend/src/pages/LandingPage.tsx`
- [X] T033 [US2] Update ProjectContext.openProject() to load from API in `frontend/src/context/ProjectContext.tsx`
- [X] T034 [US2] Add "Back to projects" button in workspace header in `frontend/src/components/layout/ProjectHeader.tsx`

**Checkpoint**: App loads → Shows project list (or empty state) → Click Open → Project loads in workspace with all data

---

## Phase 5: User Story 3 - Auto-Save on Tab Navigation (Priority: P2)

**Goal**: Edits are automatically saved when user navigates between tabs

**Independent Test**: Edit Tab 1 → Click Tab 2 → PUT request sent → Refresh → Reopen → Data preserved

### Tests for User Story 3

- [X] T035 [P] [US3] Create PUT /projects/{id} success test in `backend/tests/test_projects.py::test_update_project_success`
- [X] T036 [P] [US3] Create PUT /projects/{id} not found test in `backend/tests/test_projects.py::test_update_project_not_found`
- [X] T037 [P] [US3] Create PUT /projects/{id} validation error test in `backend/tests/test_projects.py::test_update_project_invalid`

### Implementation for User Story 3

- [X] T038 [US3] Implement ProjectService.update(id, data) method in `backend/src/services/project_service.py`
- [X] T039 [US3] Implement PUT /projects/{id} endpoint in `backend/src/api/routes/projects.py`
- [X] T040 [US3] Add updateProject(id, project) to frontend API client in `frontend/src/services/api.ts`
- [X] T041 [US3] Implement saveProject() method in ProjectContext that calls updateProject API in `frontend/src/context/ProjectContext.tsx`
- [X] T042 [US3] Modify tab navigation to call saveProject() before switching tabs in `frontend/src/pages/WorkspacePage.tsx`
- [X] T043 [US3] Add save error handling: block tab switch, show error toast, provide retry in `frontend/src/pages/WorkspacePage.tsx`
- [X] T044 [US3] Create or update Toast/Banner component for error display in `frontend/src/components/common/Toast.tsx`

**Checkpoint**: Edit Tab 1 → Click Tab 2 → Save triggered → On failure: error shown, stays on Tab 1 → On success: moves to Tab 2

---

## Phase 6: User Story 4 - Delete a Project (Priority: P3)

**Goal**: Users can delete projects from the list with confirmation

**Independent Test**: Click Delete → Confirm → DELETE request → Project removed from list and database

### Tests for User Story 4

- [X] T045 [P] [US4] Create DELETE /projects/{id} success test in `backend/tests/test_projects.py::test_delete_project_success`
- [X] T046 [P] [US4] Create DELETE /projects/{id} not found test in `backend/tests/test_projects.py::test_delete_project_not_found`

### Implementation for User Story 4

- [X] T047 [US4] Implement ProjectService.delete(id) method in `backend/src/services/project_service.py`
- [X] T048 [US4] Implement DELETE /projects/{id} endpoint in `backend/src/api/routes/projects.py`
- [X] T049 [US4] Add deleteProject(id) to frontend API client in `frontend/src/services/api.ts`
- [X] T050 [US4] Add Delete button to project list items in `frontend/src/pages/LandingPage.tsx`
- [X] T051 [US4] Implement confirmation dialog before delete in `frontend/src/pages/LandingPage.tsx`
- [X] T052 [US4] Handle delete in ProjectContext and refresh list in `frontend/src/context/ProjectContext.tsx`
- [X] T053 [US4] Handle "project deleted" edge case during auto-save in `frontend/src/pages/WorkspacePage.tsx`

**Checkpoint**: Delete project → Confirm → Project gone → Refresh → Still gone → Deleted project save shows error

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Error handling improvements, edge cases, documentation

- [X] T054 [P] Add comprehensive error handling for backend unavailability in `frontend/src/services/api.ts`
- [X] T055 [P] Add empty state UI when no projects exist in `frontend/src/pages/LandingPage.tsx`
- [X] T056 [P] Add loading spinner/skeleton during API calls in `frontend/src/pages/LandingPage.tsx`
- [X] T057 [P] Update quickstart.md with actual setup verification steps in `specs/002-backend-foundation/quickstart.md`
- [X] T058 Create E2E test: create → edit → navigate → refresh → reopen flow in `frontend/tests/integration/project-lifecycle.spec.ts`
- [X] T059 Run all backend tests and fix any failures
- [X] T060 Run frontend lint and fix any issues
- [X] T061 Manual testing of full create → edit → save → refresh → reopen loop

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-6)**: All depend on Foundational phase completion
  - US1 and US2 can proceed in parallel (both P1 priority)
  - US3 depends on US1/US2 (needs create and open to test save)
  - US4 depends on US2 (needs list to show delete button)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Foundational → US1 (independent)
- **User Story 2 (P1)**: Foundational → US2 (independent, can parallel with US1)
- **User Story 3 (P2)**: Foundational → US1 or US2 → US3 (needs project to exist)
- **User Story 4 (P3)**: Foundational → US2 → US4 (needs list view)

### Within Each User Story

- Tests FIRST (verify they fail)
- Backend service before endpoint
- Backend endpoint before frontend API client
- Frontend API client before UI integration
- Core implementation before error handling

### Parallel Opportunities

**Phase 2 Parallel Group:**
```
T006, T007, T009, T010, T012, T013 can all run in parallel
```

**US1 + US2 Parallel (after Phase 2):**
```
Team A: T015-T021 (User Story 1)
Team B: T022-T034 (User Story 2)
```

**Within User Story Tests:**
```
All test tasks marked [P] within a story can run in parallel
```

---

## Parallel Example: Phase 2 Foundational

```bash
# Launch in parallel after T005 (MongoDB setup):
Task: "T006 [P] Implement response envelope helpers in backend/src/api/response.py"
Task: "T007 [P] Implement custom exception classes in backend/src/api/exceptions.py"
Task: "T009 [P] Implement health check route in backend/src/api/routes/health.py"
Task: "T010 [P] Create Pydantic models in backend/src/models/project.py"
Task: "T012 [P] Create pytest conftest in backend/tests/conftest.py"
Task: "T013 [P] Create API client module in frontend/src/services/api.ts"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: User Story 1 (Create project)
4. Complete Phase 4: User Story 2 (List and open projects)
5. **STOP and VALIDATE**: Can create, list, open projects
6. Deploy/demo MVP

### Full Feature

7. Complete Phase 5: User Story 3 (Auto-save)
8. Complete Phase 6: User Story 4 (Delete)
9. Complete Phase 7: Polish
10. Final validation against all success criteria

### Suggested MVP Scope

**Minimum Viable Product = Phase 1 + Phase 2 + Phase 3 + Phase 4**

This delivers:
- Backend API running with MongoDB
- Create new projects (persisted)
- List all projects
- Open existing projects
- Data survives browser refresh

---

## Notes

- Backend uses FastAPI + Motor (async MongoDB driver)
- Frontend extends existing React + TypeScript codebase
- All API responses use data/error envelope format
- Auto-save blocks tab navigation on failure (by design)
- No authentication required (single-user assumption)
- Total tasks: 61
- Test tasks: 10
- Implementation tasks: 51
