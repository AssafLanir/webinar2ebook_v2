# Feature Specification: Webinar2Ebook Project Persistence & Backend Foundation (spec1)

**Feature Branch**: `002-backend-foundation`  
**Status**: Draft  

**Input Documents**  
- Product PRD: `webinar2ebook_spec.md` (Webinar2Ebook Core Workflow – Frontend-First MVP)  
- Ground Zero spec: `spec0.md` (single-project, frontend-only 4-tab shell)

---

## 0. Delta vs Ground Zero (spec0)

Ground Zero (`spec0.md`) delivered:

- A single-project, frontend-only 4-tab shell (Transcript, Visuals, Draft, Final & Export).
- In-memory `Project` state via React context, lost on browser refresh.
- Tab 1 fully functional with transcript, outline, resources, and sample-data button.
- Tabs 2–4 as UI placeholders or partials (depending on implementation stage).

This feature (`spec1.md`) introduces:

- A backend API for Projects (CRUD).
- Persistent storage of the `Project` object beyond browser refresh.
- A Project List screen to select/open existing projects.
- Auto-save on tab change (saving to backend, not just context).

What does not change:

- Overall 4-tab structure.
- Current “Generate …” and “Export” buttons remain dummy/sample (no real AI, no real PDF/ePub yet).
- UX flow within each tab (we are only adding persistence & lifecycle).

Important constraints for this feature:

- No real AI calls (no transcription, outline generation, draft generation, or visuals generation).
- No real video/file handling.
- No real PDF/ePub export.
- Focus is strictly: Project persistence + Project list + backend foundation.

---

## 1. Purpose

Provide the minimal backend foundation and frontend integration needed so that:

1. A `Project` can be created, persisted, and re-opened later.
2. Users see a Project List on startup instead of a single, implicit project.
3. `Project` state is auto-saved on tab navigation (so refreshes and restarts don’t lose work).

This feature is the bridge from:

- “Nice demo that loses state” → “Real app where projects persist and can be resumed”.

---

## 2. User Scenarios (Acceptance-Level)

### US-P1 — See Existing Projects and Open One

As a content marketer  
I want to see a list of existing webinar→ebook projects and open one into the 4-tab workspace  
So that I can continue work where I left off.

Acceptance Scenarios:

1. Given at least one project exists in the system, when I open the app, then I see a Project List with each project’s name, webinar type, and last updated time.
2. Given I’m on the Project List, when I click “Open” on a project, then the app loads that project from the backend and opens it in the 4-tab workspace with Tab 1 active.
3. Given I opened an existing project, when I go to Tab 1, then the transcript, outline, and resources reflect the last saved state.

---

### US-P2 — Create a Project That Actually Persists

As a content marketer  
I want newly created projects to be persisted on the server  
So that I can refresh the browser or come back later and reopen them.

Acceptance Scenarios:

1. Given I’m on the Project List, when I enter a project name and webinar type and click “Create project”, then a new Project is created via the backend and immediately opened in the 4-tab workspace.
2. Given I created a project and edited Tab 1 fields, when I refresh the browser, then I return to the Project List and see that project listed.
3. Given I reopen that project from the list, when I navigate to Tab 1, then I see the transcript, outline, and resources exactly as I left them.

---

### US-P3 — Auto-Save on Tab Navigation

As a user  
I want my edits to be automatically saved when I move between tabs  
So that I don’t lose work if I refresh the page or my browser crashes.

Acceptance Scenarios:

1. Given I edit the transcript, outline, and resources on Tab 1, when I click another tab or Next/Previous, then the app sends an update to the backend to save the current Project before switching tabs.
2. Given the save succeeds, when I refresh the browser and reopen the project from the Project List, then my edits are preserved.
3. Given the save fails (e.g., backend unavailable), when I attempt to switch tabs, then:
   - I see a clear error message (e.g. toast/banner), and
   - The app does not switch tabs automatically; I can retry the save or stay on the current tab.

---

### US-P4 — Delete a Project

As a user  
I want to delete projects I no longer need  
So that my Project List stays manageable.

Acceptance Scenarios:

1. Given I’m on the Project List, when I click “Delete” for a project and confirm, then that project disappears from the list.
2. Given I deleted a project, when I refresh the browser, then the project is still gone.
3. Given I have a workspace open for a project that has since been deleted (edge case), when I try to auto-save or manually save, then I see a sensible error (e.g. “Project not found”) and the app does not crash.

---

## 3. Functional Requirements

### 3.1 Backend Requirements (FastAPI + Mongo)

#### 3.1.1 Project Data Model

Backend MUST implement a `Project` model consistent with the core PRD, but only fields needed now must be actively used.

Identity & Metadata (required):

- `id` — string, opaque project identifier (e.g. MongoDB ObjectId string).
- `name` — string, project/ebook working title (required).
- `webinarType` — string enum, one of:
  - `"standard_presentation"`
  - `"training_tutorial"`
- `createdAt` — ISO timestamp, set on creation.
- `updatedAt` — ISO timestamp, updated on any modification.

Stage 1 — Transcript, Outline & Resources (required for this feature):

- `transcriptText` — string, may be empty.
- `outlineItems` — array of objects:
  - `id` — string
  - `title` — string
  - `level` — number (e.g. 1, 2, 3 for chapter/section depth)
  - `notes` — string (optional)
- `resources` — array of objects:
  - `id` — string
  - `label` — string
  - `urlOrNote` — string (URL or free-text note)

Stage 2–4 — Forward Compatibility (optional in this feature; may be empty):

- `visuals` — array of `{ id, title, description, selected }`
- `draftText` — string
- `styleConfig` — object:
  - `audience` — string
  - `tone` — string
  - `depth` — string
  - `targetPages` — number
- `finalTitle` — string (optional)
- `finalSubtitle` — string (optional)
- `creditsText` — string (optional)

#### 3.1.2 API Endpoints & Conventions

All endpoints MUST return JSON with the following envelope.

Success:

    {
      "data": { ...payload },
      "error": null
    }

Error:

    {
      "data": null,
      "error": {
        "code": "SOME_ERROR_CODE",
        "message": "Human-readable message"
      }
    }

Endpoints:

- B-FR-001: GET /health  
  - Returns simple health info, e.g. `{ "data": { "status": "ok" }, "error": null }`.

- B-FR-002: GET /projects  
  - Returns a list of all projects.  
  - Response payload: array of summary objects:
    - `id`, `name`, `webinarType`, `updatedAt`  
  - List MUST be sorted by `updatedAt` descending (most recently updated first).  
  - No pagination required in this feature.

- B-FR-003: POST /projects  
  - Input payload:
    - `name` (required)
    - `webinarType` (required, enum)  
  - Backend creates a new Project with default values for all other fields.  
  - Response: full created Project as the `data` payload.

- B-FR-004: GET /projects/{id}  
  - Returns the full Project for the given id.  
  - If not found → HTTP 404 with error code `"PROJECT_NOT_FOUND"`.

- B-FR-005: PUT /projects/{id}  
  - Replaces the stored Project with the payload (full Project update).  
  - Request payload MUST conform to the Project Pydantic model.  
  - On success, updates `updatedAt`.  
  - If project does not exist → HTTP 404 with `"PROJECT_NOT_FOUND"`.

- B-FR-006: DELETE /projects/{id}  
  - Deletes the project.  
  - If project does not exist → HTTP 404 with `"PROJECT_NOT_FOUND"`.

Validation & Errors:

- B-FR-007: Backend MUST validate all inputs using Pydantic:
  - Invalid input → HTTP 400, with error code such as `"VALIDATION_ERROR"`.
- B-FR-008: Backend MUST respond with HTTP 500 and an error payload for unexpected exceptions, while logging details server-side (no internal stack traces in response).

Persistence:

- B-FR-009: Projects MUST be stored in a persistent backend (MongoDB or configured local backend).
- B-FR-010: Restarting the backend MUST NOT lose previously created projects.

---

### 3.2 Frontend Requirements (Integration with Backend)

The existing React + TypeScript frontend MUST be adapted to use the backend for project lifecycle, while keeping existing Ground Zero UX.

#### 3.2.1 Project List & Landing Flow

- F-FR-001: On app load, the frontend MUST show a Project List screen (not directly jump into a project).
  - It MUST call GET /projects and display:
    - Project name
    - Webinar type (human-readable label, e.g. “Standard Presentation”, “Training / Tutorial”)
    - Last updated time (e.g. “Updated 5 minutes ago” or a formatted timestamp)

- F-FR-002: If no projects exist, the Project List MUST show:
  - An “empty state” message (e.g. “No projects yet”).
  - A “Create project” form inline (name + webinar type).

- F-FR-003: If projects exist, the Project List MUST:
  - Show the list of projects plus the “Create project” form in the same screen.

- F-FR-004: Each project entry MUST include:
  - An Open action → loads project into the 4-tab workspace.
  - A Delete action → shows a confirmation; on confirm, calls DELETE /projects/{id}, then removes it from the list.

- F-FR-005: The workspace (4-tab view) MUST include a clear way to navigate back to the Project List (e.g. “Back to projects” button in the header).

#### 3.2.2 Creating & Loading Projects

- F-FR-006: When a user submits the “Create project” form:
  - Frontend MUST call POST /projects with `{ name, webinarType }`.
  - On success, frontend MUST:
    - Initialize the `ProjectContext` with the returned Project.
    - Switch to the workspace view with Tab 1 active.

- F-FR-007: When a user clicks “Open” on a project in the Project List:
  - Frontend MUST:
    - Call GET /projects/{id}.
    - Hydrate `ProjectContext` with the returned Project.
    - Show the workspace with Tab 1 active.

- F-FR-008: If GET /projects/{id} returns a 404, frontend MUST:
  - Show an error toast/banner (e.g. “Project not found or has been deleted”).
  - Navigate back to the Project List.

#### 3.2.3 Auto-Save on Tab Change

- F-FR-009: When user attempts to change tabs (via TabBar or Next/Previous):
  - Before switching the visible tab, frontend MUST:
    - Construct the full current Project object from `ProjectContext`.
    - Call PUT /projects/{id} with the full Project.

- F-FR-010: If the save succeeds:
  - Frontend MUST update `ProjectContext` with any returned Project data (e.g. updated timestamps).
  - Then switch to the requested tab.

- F-FR-011: If the save fails (network error or a non-2xx status):
  - Frontend MUST:
    - Show an error toast/banner explaining save failed.
    - Not switch tabs automatically (user remains on the current tab).
    - Optionally provide a “Retry save” control (e.g. a retry button in the banner).

- F-FR-012: Auto-save in this feature is only required on tab changes. Debounced saves while typing are not required and may be added in a later iteration.

#### 3.2.4 Backwards Compatibility with Ground Zero

- F-FR-013: The Project TypeScript model in the frontend MUST remain conceptually aligned with the backend Project model:
  - Field names and nesting should match (e.g. `styleConfig.targetPages`, not `pagesTarget`).

- F-FR-014: Existing Ground Zero behaviours MUST continue to work:
  - 4-tab navigation.
  - Tab 1 transcript/outline/resources editing.
  - “Fill with sample data” button.
  - All of these now operate on a server-backed Project instead of purely in-memory.

---

## 4. Non-Functional Requirements

- NFR-001: Typical Project API calls (GET /projects, POST /projects, PUT /projects/{id}) SHOULD respond in under 300 ms in a normal development environment.
- NFR-002: Backend MUST use structured logging for errors (e.g. Loguru), including:
  - Endpoint, HTTP status, error code, and stack trace.
- NFR-003: Backend SHOULD expose a /metrics endpoint (Prometheus-compatible) if instrumentation is set up, but this is optional for this feature.
- NFR-004: CORS MUST be configured so that the local Vite dev server (e.g. http://localhost:5173) can call the backend API.
- NFR-005: Frontend MUST handle backend unavailability gracefully (error messages instead of blank screens or JS crashes).

---

## 5. Testing Requirements

### 5.1 Backend Tests

At minimum, backend MUST include automated tests (e.g. pytest) for:

- POST /projects:
  - Creating a project with valid input → success.
  - Invalid input (missing name, invalid webinarType) → 400 with `"VALIDATION_ERROR"`.

- GET /projects:
  - Returns list of projects (empty list when none exist).

- GET /projects/{id}:
  - Existing id → returns the correct Project.
  - Non-existing id → 404 with `"PROJECT_NOT_FOUND"`.

- PUT /projects/{id}:
  - Existing id with valid Project payload → updates Project and `updatedAt`.
  - Non-existing id → 404 with `"PROJECT_NOT_FOUND"`.

- DELETE /projects/{id}:
  - Existing id → removes Project.
  - Non-existing id → 404 with `"PROJECT_NOT_FOUND"`.

### 5.2 Frontend Tests (Minimum)

At minimum, frontend SHOULD include at least one integration test that:

1. Loads the app → sees Project List (empty state).
2. Creates a project via the UI.
3. Opens the project into workspace.
4. Edits Tab 1 (transcript, outline, resources).
5. Navigates to another tab (triggering auto-save).
6. Simulates a reload + reopening (mocked GET /projects and GET /projects/{id}).
7. Confirms that Tab 1 content is restored.

---

## 6. Success Criteria

- SC-101: Creating a project, editing Tab 1, navigating to another tab (triggering auto-save), refreshing, and reopening from the Project List restores 100% of Tab 1 content.
- SC-102: Project List always reflects the true set of Projects stored in the backend (no ghost entries).
- SC-103: Deleting a project removes it from both Project List and persistence.
- SC-104: Ground Zero flows (project creation, tab navigation, Tab 1 editing) still behave as before, now backed by real persistence.
- SC-105: Users can complete a full loop (create → edit Tab 1 → navigate → refresh → reopen) in under 10 minutes without encountering blocking errors.

---

## 7. Assumptions

- Single-user environment (no authentication, no multi-tenant logic).
- Backend will be implemented in Python with FastAPI, Pydantic, and MongoDB (or a local storage backend configured by environment).
- Frontend is React + TypeScript with the existing ProjectContext and tab layout from Ground Zero.
- “Generate” and “Export” buttons remain dummy/sample behaviours in this feature.

---

## 8. Out of Scope (for this feature)

- AI-powered transcription, outline generation, visual generation, or draft generation.
- Real video file upload/processing.
- Real PDF/ePub export.
- Multi-user accounts, permissions, roles, or collaboration features.
- Advanced analytics, dashboards, or detailed metrics (beyond basic logging and optional Prometheus metrics).

---

## 9. Future Considerations (DO NOT IMPLEMENT IN THIS FEATURE)

The following items are explicitly out of scope for spec1, but may be revisited later:

- Debounced auto-save while typing (in addition to tab-change saves).
- Soft delete / archived flag in Project List instead of hard delete.
- Filtering/search on the Project List.