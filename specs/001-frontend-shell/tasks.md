# Tasks: Webinar2Ebook Ground Zero - Frontend Shell

**Input**: Design documents from `/specs/001-frontend-shell/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Tests are NOT explicitly requested in this feature specification. Tasks focus on implementation only.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app (frontend-only)**: `frontend/src/`, `frontend/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create Vite React-TypeScript project in `frontend/` directory
- [x] T002 Install core dependencies: @headlessui/react, @dnd-kit/core, @dnd-kit/sortable per research.md
- [x] T003 [P] Install dev dependencies: tailwindcss, postcss, autoprefixer, vitest, @testing-library/react, jsdom
- [x] T003a [P] Install and configure ESLint + Prettier for React TypeScript in `frontend/`
      - [x] Add eslint + prettier devDeps
      - [x] Add `.eslintrc`, `.prettierrc`, and relevant ignore files
      - [x] Wire `npm run lint` script to ESLint
- [x] T004 [P] Configure Tailwind CSS with tailwind.config.js and update frontend/src/index.css
- [x] T005 [P] Configure Vitest with frontend/vitest.config.ts and frontend/tests/setup.ts
- [x] T006 Create directory structure per plan.md: components/{common,layout,tab1,tab2,tab3,tab4}, context, pages, types, data, utils
- [x] T007 [P] Update frontend/package.json scripts: dev, build, test, lint

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T008 Create TypeScript interfaces in frontend/src/types/project.ts per data-model.md (Project, OutlineItem, Resource, Visual, StyleConfig, WebinarType, enums)
- [x] T009 Create ID generator utility in frontend/src/utils/idGenerator.ts
- [x] T010 Implement ProjectContext with useReducer in frontend/src/context/ProjectContext.tsx per data-model.md action types
- [x] T011 [P] Create Button component in frontend/src/components/common/Button.tsx per contracts
- [x] T012 [P] Create Input component in frontend/src/components/common/Input.tsx per contracts
- [x] T013 [P] Create Textarea component in frontend/src/components/common/Textarea.tsx per contracts
- [x] T014 [P] Create Select component with Headless UI Listbox in frontend/src/components/common/Select.tsx per contracts
- [x] T015 [P] Create Modal component with Headless UI Dialog in frontend/src/components/common/Modal.tsx per contracts
- [x] T016 [P] Create Card component in frontend/src/components/common/Card.tsx per contracts
- [x] T017 Wire up App.tsx with ProjectProvider and basic routing structure in frontend/src/App.tsx

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Create Project and Navigate Tabs (Priority: P1) MVP

**Goal**: User can create a project from landing screen and navigate between 4 tabs via tab bar and Next/Previous buttons

**Independent Test**: Create a project with name "Test Project", verify 4 tabs visible and labeled correctly, click through all tabs using both tab bar and navigation buttons

**Acceptance Criteria**:
- Landing screen with project name input and Create button
- 4-tab view with Tab 1 active after creation
- Tab bar shows all 4 tabs: "Transcript, Outline & Resources", "Visuals", "Draft", "Final & Export"
- Next/Previous buttons navigate between tabs
- Clicking tabs in tab bar navigates directly

### Implementation for User Story 1

- [x] T018 [US1] Create LandingPage component with project name input and webinar type select in frontend/src/pages/LandingPage.tsx
- [x] T019 [US1] Implement CREATE_PROJECT action handler in ProjectContext reducer
- [x] T020 [P] [US1] Create TabBar component displaying 4 tabs with active state in frontend/src/components/layout/TabBar.tsx
- [x] T021 [P] [US1] Create TabNavigation component with Next/Previous buttons in frontend/src/components/layout/TabNavigation.tsx
- [x] T022 [P] [US1] Create ProjectHeader component showing project title and webinar type in frontend/src/components/layout/ProjectHeader.tsx
- [x] T023 [US1] Create WorkspacePage container with tab rendering logic in frontend/src/pages/WorkspacePage.tsx
- [x] T024 [US1] Implement SET_ACTIVE_TAB action handler in ProjectContext reducer
- [x] T025 [US1] Update App.tsx to render LandingPage when no project, WorkspacePage when project exists

**Checkpoint**: User Story 1 complete - can create project and navigate all 4 tabs

---

## Phase 4: User Story 2 - Edit Transcript, Outline and Resources (Priority: P1)

**Goal**: User can edit transcript text, manage outline items (add/remove/reorder), manage resources (add/remove), and fill with sample data on Tab 1

**Independent Test**: Navigate to Tab 1, type in transcript, add 3 outline items, reorder them via drag, add 2 resources, navigate to Tab 3 and back, verify all data persisted

**Acceptance Criteria**:
- Transcript textarea saves text to context
- Outline list with add/remove/reorder (drag-drop) functionality
- Resources list with add/remove functionality
- "Fill with sample data" button populates all three sections
- Data persists across tab navigation

### Implementation for User Story 2

- [x] T026 [P] [US2] Create sample data constants in frontend/src/data/sampleData.ts (SAMPLE_TRANSCRIPT, SAMPLE_OUTLINE, SAMPLE_RESOURCES)
- [x] T027 [US2] Create TranscriptEditor component in frontend/src/components/tab1/TranscriptEditor.tsx
- [x] T028 [US2] Implement UPDATE_TRANSCRIPT action handler in ProjectContext reducer
- [x] T029 [P] [US2] Create OutlineItem component with drag handle in frontend/src/components/tab1/OutlineItem.tsx
- [x] T030 [US2] Create OutlineEditor component with @dnd-kit sortable in frontend/src/components/tab1/OutlineEditor.tsx
- [x] T031 [US2] Implement ADD_OUTLINE_ITEM, UPDATE_OUTLINE_ITEM, REMOVE_OUTLINE_ITEM, REORDER_OUTLINE_ITEMS actions in ProjectContext reducer
- [x] T032 [P] [US2] Create ResourceItem component in frontend/src/components/tab1/ResourceItem.tsx
- [x] T033 [US2] Create ResourceList component in frontend/src/components/tab1/ResourceList.tsx
- [x] T034 [US2] Implement ADD_RESOURCE, UPDATE_RESOURCE, REMOVE_RESOURCE actions in ProjectContext reducer
- [x] T035 [US2] Implement FILL_SAMPLE_DATA action handler in ProjectContext reducer
- [x] T036 [US2] Create Tab1Content container integrating all Tab 1 components in frontend/src/pages/WorkspacePage.tsx (or separate Tab1Content.tsx)

**Checkpoint**: User Story 2 complete - full Tab 1 functionality working

---

## Phase 5: User Story 3 - Select and Manage Visuals (Priority: P2)

**Goal**: User can view visual gallery with 4-8 example cards, toggle selection, and add custom visuals on Tab 2

**Independent Test**: Navigate to Tab 2, see 6 example visuals, toggle 3 to selected, add 1 custom visual, navigate away and back, verify selections persisted

**Acceptance Criteria**:
- Gallery displays 4-8 example visual cards with title, description, selection toggle
- Toggle changes visual selection state
- "Add custom visual" creates new text-only entry
- Selections persist across tab navigation

### Implementation for User Story 3

- [x] T037 [P] [US3] Add EXAMPLE_VISUALS constant to frontend/src/data/sampleData.ts (6 example visuals per data-model.md)
- [x] T038 [US3] Update CREATE_PROJECT action to populate visuals with EXAMPLE_VISUALS
- [x] T039 [P] [US3] Create VisualCard component with selection toggle in frontend/src/components/tab2/VisualCard.tsx
- [x] T040 [US3] Create VisualGallery component displaying visual grid in frontend/src/components/tab2/VisualGallery.tsx
- [x] T041 [US3] Implement TOGGLE_VISUAL_SELECTION action handler in ProjectContext reducer
- [x] T042 [US3] Create AddCustomVisual component with title/description inputs in frontend/src/components/tab2/AddCustomVisual.tsx
- [x] T043 [US3] Implement ADD_CUSTOM_VISUAL action handler in ProjectContext reducer
- [x] T044 [US3] Create Tab2Content container integrating all Tab 2 components in WorkspacePage

**Checkpoint**: User Story 3 complete - full Tab 2 functionality working

---

## Phase 6: User Story 4 - Configure Style and Edit Draft (Priority: P2)

**Goal**: User can configure style options (audience, tone, depth, target pages), edit draft text, and generate sample draft on Tab 3

**Independent Test**: Navigate to Tab 3, change audience to "technical", set target pages to 30, click "Generate draft", edit the draft text, navigate away and back, verify all settings and draft persisted

**Acceptance Criteria**:
- Style controls for audience, tone, depth (dropdowns), target pages (number input)
- Large draft editor textarea
- "Generate draft" populates editor with sample content
- Style settings and draft text persist across tab navigation

### Implementation for User Story 4

- [x] T045 [P] [US4] Add SAMPLE_DRAFT_TEXT constant to frontend/src/data/sampleData.ts
- [x] T046 [US4] Create StyleControls component with 4 controls in frontend/src/components/tab3/StyleControls.tsx
- [x] T047 [US4] Implement UPDATE_STYLE_CONFIG action handler in ProjectContext reducer
- [x] T048 [US4] Create DraftEditor component with large textarea and generate button in frontend/src/components/tab3/DraftEditor.tsx
- [x] T049 [US4] Implement UPDATE_DRAFT action handler in ProjectContext reducer
- [x] T050 [US4] Implement GENERATE_SAMPLE_DRAFT action handler in ProjectContext reducer
- [x] T051 [US4] Create Tab3Content container integrating all Tab 3 components in WorkspacePage

**Checkpoint**: User Story 4 complete - full Tab 3 functionality working

---

## Phase 7: User Story 5 - Set Final Metadata and Export (Priority: P3)

**Goal**: User can set final title/subtitle/credits, see structure preview (chapters from outline, selected visuals), and export to Markdown file on Tab 4

**Independent Test**: Navigate to Tab 4, enter final title "My Ebook", see chapters from Tab 1 outline and selected visuals from Tab 2 in preview, click Export, verify Markdown file downloads with correct content

**Acceptance Criteria**:
- Input fields for final title, subtitle, credits
- Structure preview shows chapters derived from outline items
- Structure preview shows selected visuals from Tab 2
- Export button downloads Markdown file per contracts/README.md format
- Metadata persists across tab navigation

### Implementation for User Story 5

- [x] T052 [P] [US5] Create MetadataForm component with title/subtitle/credits inputs in frontend/src/components/tab4/MetadataForm.tsx
- [x] T053 [US5] Implement UPDATE_FINAL_TITLE, UPDATE_FINAL_SUBTITLE, UPDATE_CREDITS actions in ProjectContext reducer
- [x] T054 [US5] Create StructurePreview component showing chapters and selected visuals in frontend/src/components/tab4/StructurePreview.tsx
- [x] T055 [US5] Create exportHelpers utility for Markdown generation in frontend/src/utils/exportHelpers.ts per contracts/README.md
- [x] T056 [US5] Create ExportButton component triggering Markdown download in frontend/src/components/tab4/ExportButton.tsx
- [x] T057 [US5] Implement TOGGLE_EXPORT_MODAL action handler in ProjectContext reducer (if using modal)
- [x] T058 [US5] Create Tab4Content container integrating all Tab 4 components in WorkspacePage

**Checkpoint**: User Story 5 complete - full Tab 4 functionality with export working

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T059 [P] Add empty state messaging for empty outline in Tab 4 preview
- [x] T060 [P] Add empty state messaging for no selected visuals in Tab 4 preview
- [x] T061 [P] Add project name validation (required, non-empty) on LandingPage
- [x] T062 [P] Add scrolling support for long transcript text in Tab 1
- [x] T063 Style polish: ensure consistent Tailwind styling across all components
- [x] T064 Verify state persistence across all tab navigation paths
- [x] T065 Run quickstart.md validation checklist
- [x] T066 [P] Add optional localStorage persistence for Project in ProjectContext
      - Hydrate initial Project state from localStorage if present
      - Persist Project to localStorage on relevant state changes
      - Make behaviour opt-in via a simple flag or environment/config setting


---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-7)**: All depend on Foundational phase completion
  - US1 and US2 are both P1 priority but US1 must complete first (provides navigation)
  - US3 and US4 (both P2) can run in parallel after US1 completes
  - US5 (P3) depends on US2 (outline data) and US3 (visual selections) for preview
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1: Setup
    ↓
Phase 2: Foundational (types, context, common components)
    ↓
Phase 3: US1 - Create Project and Navigate Tabs (P1)
    ↓
Phase 4: US2 - Edit Transcript, Outline and Resources (P1)
    ↓ (US2 provides outline data)
   ┌──────────┴──────────┐
   ↓                     ↓
Phase 5: US3           Phase 6: US4
Visuals (P2)           Draft (P2)
   ↓ (US3 provides      [independent]
   ↓  selected visuals)
   └──────────┬──────────┘
              ↓
Phase 7: US5 - Final Metadata and Export (P3)
              ↓
Phase 8: Polish
```

### Within Each User Story

- Context actions before UI components that use them
- Container components after their child components
- All [P] tasks within a phase can run in parallel

### Parallel Opportunities

**Phase 1 (Setup)**:
- T003, T004, T005, T007 can run in parallel after T001, T002

**Phase 2 (Foundational)**:
- T011, T012, T013, T014, T015, T016 can all run in parallel (common components)

**Phase 3 (US1)**:
- T020, T021, T022 can run in parallel (layout components)

**Phase 4 (US2)**:
- T026, T029, T032 can run in parallel

**Phase 5 (US3)**:
- T037, T039 can run in parallel

**Phase 6 (US4)**:
- T045 can run in parallel with Phase 5 tasks (different story)

**Phase 7 (US5)**:
- T052 can start while other US5 tasks are blocked

**Phase 8 (Polish)**:
- T059, T060, T061, T062 can all run in parallel

---

## Parallel Example: Phase 2 Common Components

```bash
# Launch all common components together:
Task: "Create Button component in frontend/src/components/common/Button.tsx"
Task: "Create Input component in frontend/src/components/common/Input.tsx"
Task: "Create Textarea component in frontend/src/components/common/Textarea.tsx"
Task: "Create Select component in frontend/src/components/common/Select.tsx"
Task: "Create Modal component in frontend/src/components/common/Modal.tsx"
Task: "Create Card component in frontend/src/components/common/Card.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Can create project and navigate 4 empty tabs
5. Demo navigation flow

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test navigation → Demo (MVP!)
3. Add User Story 2 → Test Tab 1 editing → Demo
4. Add User Story 3 → Test Tab 2 visuals → Demo
5. Add User Story 4 → Test Tab 3 draft → Demo
6. Add User Story 5 → Test Tab 4 export → Demo (Feature Complete!)
7. Polish → Final testing → Release

### Task Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| Phase 1: Setup | T001-T007 (7) | Project initialization |
| Phase 2: Foundational | T008-T017 (10) | Types, context, common components |
| Phase 3: US1 | T018-T025 (8) | Project creation, tab navigation |
| Phase 4: US2 | T026-T036 (11) | Transcript, outline, resources |
| Phase 5: US3 | T037-T044 (8) | Visual gallery and selection |
| Phase 6: US4 | T045-T051 (7) | Style controls and draft editor |
| Phase 7: US5 | T052-T058 (7) | Metadata form and export |
| Phase 8: Polish | T059-T065 (7) | Edge cases and validation |
| **Total** | **65 tasks** | |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All file paths are relative to repository root (prefix with `frontend/`)
