# Feature Specification: Webinar2Ebook Project Persistence & Backend Foundation

**Feature Branch**: `002-backend-foundation`
**Created**: 2025-12-11
**Status**: Draft
**Input**: User description: "@spec1.md" - Backend foundation for project persistence, project list, and auto-save functionality

## Context & Background

### Delta vs Ground Zero (001-frontend-shell)

Ground Zero delivered:

- A single-project, frontend-only 4-tab shell (Transcript, Visuals, Draft, Final & Export)
- In-memory `Project` state via React context, lost on browser refresh
- Tab 1 fully functional with transcript, outline, resources, and sample-data button
- Tabs 2–4 as UI placeholders or partials

This feature introduces:

- A backend API for Projects (CRUD)
- Persistent storage of the `Project` object beyond browser refresh
- A Project List screen to select/open existing projects
- Auto-save on tab change (saving to backend, not just context)

What does NOT change:

- Overall 4-tab structure
- Current "Generate …" and "Export" buttons remain dummy/sample (no real AI, no real PDF/ePub yet)
- UX flow within each tab (we are only adding persistence & lifecycle)

### Important Constraints

- No real AI calls (no transcription, outline generation, draft generation, or visuals generation)
- No real video/file handling
- No real PDF/ePub export
- Focus is strictly: Project persistence + Project list + backend foundation

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create and Persist a New Project (Priority: P1)

As a content marketer, I want newly created projects to be persisted on the server so that I can refresh the browser or come back later and reopen them.

**Why this priority**: Without persistence, the app is just a demo. This is the foundational capability that makes the app useful.

**Independent Test**: Create a project, edit Tab 1 fields, refresh the browser, and verify the project appears in a list and can be reopened with all data intact.

**Acceptance Scenarios**:

1. **Given** I'm on the Project List, **When** I enter a project name and webinar type and click "Create project", **Then** a new Project is created via the backend and immediately opened in the 4-tab workspace.
2. **Given** I created a project and edited Tab 1 fields, **When** I refresh the browser, **Then** I return to the Project List and see that project listed.
3. **Given** I reopen that project from the list, **When** I navigate to Tab 1, **Then** I see the transcript, outline, and resources exactly as I left them.

---

### User Story 2 - View and Open Existing Projects (Priority: P1)

As a content marketer, I want to see a list of existing webinar→ebook projects and open one into the 4-tab workspace so that I can continue work where I left off.

**Why this priority**: Users need to access their saved work. This is essential for the persistence feature to be useful.

**Independent Test**: With at least one project saved, load the app and verify the project list displays correctly with the ability to open projects.

**Acceptance Scenarios**:

1. **Given** at least one project exists in the system, **When** I open the app, **Then** I see a Project List with each project's name, webinar type, and last updated time.
2. **Given** I'm on the Project List, **When** I click "Open" on a project, **Then** the app loads that project from the backend and opens it in the 4-tab workspace with Tab 1 active.
3. **Given** I opened an existing project, **When** I go to Tab 1, **Then** the transcript, outline, and resources reflect the last saved state.

---

### User Story 3 - Auto-Save on Tab Navigation (Priority: P2)

As a user, I want my edits to be automatically saved when I move between tabs so that I don't lose work if I refresh the page or my browser crashes.

**Why this priority**: Auto-save prevents data loss and improves user confidence, but requires the basic CRUD operations to work first.

**Independent Test**: Edit content on Tab 1, navigate to Tab 2, refresh browser, reopen project, and verify Tab 1 content is preserved.

**Acceptance Scenarios**:

1. **Given** I edit the transcript, outline, and resources on Tab 1, **When** I click another tab or Next/Previous, **Then** the app sends an update to the backend to save the current Project before switching tabs.
2. **Given** the save succeeds, **When** I refresh the browser and reopen the project from the Project List, **Then** my edits are preserved.
3. **Given** the save fails (e.g., backend unavailable), **When** I attempt to switch tabs, **Then** I see a clear error message (e.g., toast/banner), and the app does not switch tabs automatically; I can retry the save or stay on the current tab.

---

### User Story 4 - Delete a Project (Priority: P3)

As a user, I want to delete projects I no longer need so that my Project List stays manageable.

**Why this priority**: Deletion is important for list management but is less critical than creating, viewing, and saving projects.

**Independent Test**: Create a project, delete it from the list, refresh the browser, and verify it no longer appears.

**Acceptance Scenarios**:

1. **Given** I'm on the Project List, **When** I click "Delete" for a project and confirm, **Then** that project disappears from the list.
2. **Given** I deleted a project, **When** I refresh the browser, **Then** the project is still gone.
3. **Given** I have a workspace open for a project that has since been deleted (edge case), **When** I try to auto-save or manually save, **Then** I see a sensible error (e.g., "Project not found") and the app does not crash.

---

### Edge Cases

- What happens when the backend is unavailable during app load? Show error message with retry option; do not show blank screen or crash.
- What happens when a project is deleted while another browser tab has it open? Show "Project not found" error on save attempt; navigate back to Project List.
- What happens when network fails during auto-save? Block tab switch, show error with retry button, allow user to stay on current tab.
- What happens when invalid data is submitted to create/update? Show validation error message, prevent submission until corrected.
- What happens when Project List is empty? Show empty state message and the create project form.

## Requirements *(mandatory)*

### Functional Requirements

#### Backend Requirements

- **FR-001**: System MUST implement a Project data model with identity fields (id, name, webinarType, createdAt, updatedAt)
- **FR-002**: System MUST store Stage 1 data (transcriptText, outlineItems array with id/title/level/notes, resources array with id/label/urlOrNote) for each project
- **FR-003**: System MUST provide a health check endpoint that returns system status
- **FR-004**: System MUST provide an endpoint to list all projects, returning id, name, webinarType, and updatedAt, sorted by most recently updated first
- **FR-005**: System MUST provide an endpoint to create a new project with name and webinar type, returning the full created project
- **FR-006**: System MUST provide an endpoint to retrieve a single project by ID, returning the full project
- **FR-007**: System MUST provide an endpoint to update a project (full replacement), updating the updatedAt timestamp
- **FR-008**: System MUST provide an endpoint to delete a project by ID
- **FR-009**: System MUST return HTTP 404 with error code "PROJECT_NOT_FOUND" when accessing/updating/deleting a non-existent project
- **FR-010**: System MUST validate all inputs and return HTTP 400 with error code "VALIDATION_ERROR" for invalid data
- **FR-011**: System MUST persist projects to permanent storage (data survives backend restart)
- **FR-012**: System MUST return consistent JSON response format with data/error envelope for all endpoints

#### Frontend Requirements

- **FR-013**: App MUST show a Project List screen on initial load (not directly into a project workspace)
- **FR-014**: Project List MUST display project name, webinar type (human-readable label), and last updated time for each project
- **FR-015**: Project List MUST show an empty state message ("No projects yet") when no projects exist
- **FR-016**: Project List MUST include a "Create project" form with name and webinar type fields
- **FR-017**: Each project entry MUST have an Open action and a Delete action
- **FR-018**: Opening a project MUST load it from the backend into the 4-tab workspace with Tab 1 active
- **FR-019**: Workspace MUST include a "Back to projects" navigation element in the header
- **FR-020**: Deleting a project MUST show a confirmation dialog before executing the delete
- **FR-021**: Tab navigation (TabBar clicks or Next/Previous buttons) MUST trigger auto-save before switching tabs
- **FR-022**: If auto-save succeeds, the tab switch MUST proceed normally
- **FR-023**: If auto-save fails, the tab switch MUST be blocked, an error message MUST be shown, and a retry option SHOULD be available
- **FR-024**: System MUST handle backend unavailability gracefully with user-friendly error messages (no blank screens or JavaScript crashes)
- **FR-025**: Existing Ground Zero features (4-tab navigation, Tab 1 transcript/outline/resources editing, "Fill with sample data" button) MUST continue to work unchanged

### Key Entities

- **Project**: Represents a webinar-to-ebook conversion project with identity (id, name, webinarType, createdAt, updatedAt), Stage 1 content (transcriptText, outlineItems, resources), and forward-compatible fields for Stages 2-4 (visuals, draftText, styleConfig, finalTitle, finalSubtitle, creditsText)
- **OutlineItem**: A chapter or section in the ebook outline with id, title, level (1-3 for hierarchy depth), and optional notes
- **Resource**: A reference link or note attached to a project with id, label, and urlOrNote (URL or free-text note)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Creating a project, editing Tab 1, navigating to another tab (triggering auto-save), refreshing, and reopening from the Project List restores 100% of Tab 1 content
- **SC-002**: Project List always reflects the true set of Projects stored in the backend (no ghost entries, no missing entries after refresh)
- **SC-003**: Deleting a project removes it from both Project List display and persistent storage immediately and permanently
- **SC-004**: Ground Zero flows (project creation form, tab navigation, Tab 1 editing, sample data button) continue to work identically, now backed by real persistence
- **SC-005**: Users can complete a full create→edit→navigate→refresh→reopen loop in under 10 minutes without encountering blocking errors

## Assumptions

- Single-user environment (no authentication, no multi-tenant logic required)
- "Generate" and "Export" buttons remain dummy/sample behaviors in this feature
- Frontend is React + TypeScript with existing ProjectContext and tab layout from Ground Zero
- Backend will be accessible from the frontend development server

## Out of Scope

- AI-powered transcription, outline generation, visual generation, or draft generation
- Real video file upload/processing
- Real PDF/ePub export
- Multi-user accounts, permissions, roles, or collaboration features
- Debounced auto-save while typing (only tab-change saves required)
- Soft delete / archived flag (hard delete only)
- Filtering/search on the Project List
- Pagination for Project List
