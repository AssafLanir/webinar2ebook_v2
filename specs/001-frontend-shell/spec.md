# Feature Specification: Webinar2Ebook Ground Zero - Frontend Shell

**Feature Branch**: `001-frontend-shell`
**Created**: 2025-12-09
**Status**: Draft
**Input**: Build a frontend-only prototype shell of Webinar2Ebook with a single-project, 4-tab workflow to validate UX, navigation, and stage modularity before investing in real AI and backend integration.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create Project and Navigate Tabs (Priority: P1)

A user wants to start a new webinar-to-ebook project and understand the overall conversion process by seeing the complete 4-stage workflow. They create a project from a landing screen and can immediately navigate between all four tabs to explore what each stage involves.

**Why this priority**: This is the foundational user journey. Without project creation and tab navigation, no other functionality can be tested. It establishes the core structure that all other features depend on.

**Independent Test**: Can be fully tested by creating a project and clicking through all 4 tabs. Delivers value by allowing users to understand the complete workflow and validate the overall UX structure.

**Acceptance Scenarios**:

1. **Given** the user is on the landing screen, **When** they enter a project name and click "Create project", **Then** they are taken to a 4-tab view with Tab 1 active
2. **Given** the user is viewing any tab, **When** they click on a different tab in the tab bar, **Then** they navigate to that tab immediately
3. **Given** the user is on Tab 1, **When** they click "Next", **Then** they move to Tab 2
4. **Given** the user is on Tab 4, **When** they click "Previous", **Then** they move to Tab 3
5. **Given** the user is on Tab 1, **When** they look at the tab bar, **Then** they see all 4 tabs clearly labeled: "Transcript, Outline & Resources", "Visuals", "Draft", "Final & Export"

---

### User Story 2 - Edit Transcript, Outline and Resources (Priority: P1)

A user wants to manually enter or edit the transcript, outline, and resources for their webinar conversion. They need to be able to type content into dedicated areas for each data type, with their edits preserved as they navigate between tabs.

**Why this priority**: Tab 1 contains the foundational content that flows through the entire conversion process. Without editable transcript, outline, and resources, the prototype cannot demonstrate data flow between stages.

**Independent Test**: Can be fully tested by entering text in each field on Tab 1, navigating away, and returning to verify persistence. Delivers value by validating the content entry experience for the first stage of the workflow.

**Acceptance Scenarios**:

1. **Given** the user is on Tab 1, **When** they type in the transcript textarea, **Then** their text appears in the field
2. **Given** the user is on Tab 1, **When** they add an outline item, **Then** a new item appears in the outline list
3. **Given** the user is on Tab 1, **When** they remove an outline item, **Then** the item is deleted from the list
4. **Given** the user is on Tab 1, **When** they add a resource, **Then** a new resource entry appears in the resources list
5. **Given** the user has entered data on Tab 1, **When** they navigate to Tab 3 and back to Tab 1, **Then** all their entered data remains intact
6. **Given** the user is on Tab 1, **When** they click "Fill with sample data", **Then** the transcript, outline, and resources are populated with example content

---

### User Story 3 - Select and Manage Visuals (Priority: P2)

A user wants to select which visuals to include in their ebook from a gallery of available options. They can toggle selections on example visuals and add custom visual entries with descriptions.

**Why this priority**: Visual selection demonstrates how content flows from Tab 2 to Tab 4's preview. It's essential for showing the complete workflow but depends on having the basic navigation working first.

**Independent Test**: Can be fully tested by toggling visual selections, adding a custom visual, navigating away and back, and verifying selections persist. Delivers value by validating the visual curation experience.

**Acceptance Scenarios**:

1. **Given** the user is on Tab 2, **When** they view the page, **Then** they see 4-8 example visual cards with titles and descriptions
2. **Given** the user is on Tab 2, **When** they toggle "Include" on a visual, **Then** the visual's selection state changes
3. **Given** the user has selected 3 visuals on Tab 2, **When** they navigate to Tab 4, **Then** they see those 3 visuals listed in the preview
4. **Given** the user is on Tab 2, **When** they click "Add custom visual" and enter text, **Then** a new text-only visual entry appears in the list
5. **Given** the user has toggled selections on Tab 2, **When** they navigate away and return, **Then** their selection states are preserved

---

### User Story 4 - Configure Style and Edit Draft (Priority: P2)

A user wants to configure style options for their ebook and edit the draft content. They need controls for audience, tone, depth, and target length, plus a large editor for the draft text that persists their edits.

**Why this priority**: The draft stage is where the ebook content takes shape. Style configuration and draft editing are core to the user experience but require Tab 1 content to be meaningful in the full workflow.

**Independent Test**: Can be fully tested by setting style options, generating a draft, editing it, navigating away and back, and verifying all changes persist. Delivers value by validating the draft editing experience.

**Acceptance Scenarios**:

1. **Given** the user is on Tab 3, **When** they view the page, **Then** they see style controls for audience, tone, depth, and target pages
2. **Given** the user is on Tab 3, **When** they change the audience setting, **Then** the new value is saved
3. **Given** the user is on Tab 3, **When** they click "Generate draft", **Then** the draft editor is populated with sample content
4. **Given** the user is on Tab 3 with draft content, **When** they edit the draft text, **Then** their changes appear immediately
5. **Given** the user has edited the draft on Tab 3, **When** they navigate to Tab 1 and back to Tab 3, **Then** their draft edits remain intact

---

### User Story 5 - Set Final Metadata and Export (Priority: P3)

A user wants to finalize their ebook metadata and trigger an export. They need to see a preview of the structure (chapters from outline, selected visuals) and be able to set title, subtitle, and credits before exporting.

**Why this priority**: This is the culmination of the workflow but depends on all previous stages having content. It validates the end-to-end data flow and export experience.

**Independent Test**: Can be fully tested by entering metadata, viewing the structure preview, and triggering the export action. Delivers value by validating the final review and export experience.

**Acceptance Scenarios**:

1. **Given** the user is on Tab 4, **When** they view the page, **Then** they see fields for final title, subtitle, and credits
2. **Given** the user has outline items on Tab 1, **When** they view Tab 4, **Then** they see chapters listed based on the outline
3. **Given** the user has selected visuals on Tab 2, **When** they view Tab 4, **Then** they see those visuals listed in the preview
4. **Given** the user is on Tab 4, **When** they click "Export", **Then** either a simple text/markdown file downloads OR a summary modal appears showing what would be exported
5. **Given** the user has entered a final title on Tab 4, **When** they navigate away and return, **Then** their entered title remains

---

### Edge Cases

- What happens when the user tries to navigate with no project name? System should prevent project creation without a name.
- How does the system handle an empty outline when showing chapters on Tab 4? Display a message indicating no chapters defined.
- What happens when no visuals are selected on Tab 2? Tab 4 preview shows an empty visuals section with appropriate messaging.
- How does the system handle very long transcript text? The textarea should allow scrolling without page layout issues.
- What happens if the user refreshes the browser during a session? Data may be lost (acceptable for Ground Zero - session persistence only).

## Requirements *(mandatory)*

### Functional Requirements

**General**

- **FR-001**: System MUST maintain a single Project object in memory that is shared across all four tabs
- **FR-002**: System MUST allow navigation between tabs via both tab bar clicks and "Next/Previous" buttons
- **FR-003**: System MUST preserve all field changes when switching between tabs during a session
- **FR-004**: System MUST display a landing screen for project creation with a project name input field
- **FR-005**: System MUST support a webinar type selection (Standard Presentation / Training)

**Tab 1 - Transcript, Outline & Resources**

- **FR-006**: System MUST provide a textarea for entering transcript text
- **FR-007**: System MUST provide a list editor for outline items with add, remove, and reorder capabilities
- **FR-008**: Each outline item MUST have an id, title, level, and optional notes
- **FR-009**: System MUST provide a list editor for resources with add and remove capabilities
- **FR-010**: Each resource MUST have an id, label, and URL or note field
- **FR-011**: System MUST provide a "Fill with sample data" button that populates transcript, outline, and resources with example content

**Tab 2 - Visuals**

- **FR-012**: System MUST display 4-8 example visual cards with title, description, and selection toggle
- **FR-013**: System MUST persist visual selection state in the Project object
- **FR-014**: System MUST provide an "Add custom visual" button that appends a text-only entry to the visuals list

**Tab 3 - Draft**

- **FR-015**: System MUST display style controls for audience, tone, depth, and target pages
- **FR-016**: System MUST display a large text editor area for the draft content
- **FR-017**: System MUST provide a "Generate draft" button that populates the editor with sample text
- **FR-018**: System MUST store draft edits in the Project object

**Tab 4 - Final & Export**

- **FR-019**: System MUST display input fields for final title, subtitle, and credits
- **FR-020**: System MUST display a structural preview showing chapters derived from Tab 1 outline items
- **FR-021**: System MUST display a structural preview showing selected visuals from Tab 2
- **FR-022**: System MUST provide an "Export" button that either downloads a simple text/markdown file OR displays a summary modal

### Key Entities

- **Project**: The central data container holding all ebook conversion data including identity (projectId, title, webinarType), stage-specific data, and configuration. One project exists at a time during a session.
- **OutlineItem**: A single chapter or section in the ebook structure with id, title, hierarchical level, and optional notes.
- **Resource**: A reference item such as a link or note with id, label, and URL or descriptive note.
- **Visual**: An image or diagram entry with id, title, description, and selection state indicating inclusion in the ebook.
- **StyleConfig**: Draft generation preferences including audience type, tone, depth level, and target page count.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can create a new project and reach the 4-tab view in under 30 seconds
- **SC-002**: Users can navigate through all 4 tabs without any data loss within a session
- **SC-003**: 100% of user edits in any tab are preserved when navigating to other tabs and returning
- **SC-004**: Users can complete a full walkthrough of all 4 stages (entering sample data, selecting visuals, editing draft, triggering export) in under 10 minutes
- **SC-005**: The structural preview on Tab 4 accurately reflects 100% of the outline items from Tab 1 and selected visuals from Tab 2
- **SC-006**: All interactive elements (buttons, toggles, inputs) respond to user actions within 200ms perceived latency
- **SC-007**: Users can understand the purpose of each tab and the overall workflow without external documentation

## Assumptions

- This is a single-user, single-project prototype - no multi-user or multi-project management required
- Session-only persistence is acceptable; data does not need to survive browser refresh
- "Generate" buttons insert hardcoded sample content rather than performing any real processing
- "Export" provides a placeholder experience (simple file download or summary modal) rather than real PDF/ePub generation
- No real file processing is required; video upload fields are visual only
- No authentication or user accounts are needed
- The application will run in modern web browsers (Chrome, Firefox, Safari, Edge)

## Out of Scope

- Real AI integration (transcription, outline generation, visual generation, draft generation)
- Real file processing (video parsing, image extraction)
- Real export formats (PDF, ePub)
- Multi-project management
- User accounts and authentication
- Data persistence beyond the current session
- Collaboration features
- Mobile-optimized layouts
