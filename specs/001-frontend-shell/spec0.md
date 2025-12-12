# Feature: Webinar2Ebook Ground Zero — Frontend Shell

## 1. Summary — What & Why

**What (Ground Zero)**  
Build a **frontend-only shell** of Webinar2Eebook:

- A single-project flow with **four tabs**:
  1. Transcript, Outline & Resources  
  2. Visuals  
  3. Draft  
  4. Final & Export
- Each tab has:
  - Its own **screen**, **data fields**, and **editable UI**.
  - Simple, local “save” behaviour (no real AI, no real exports yet).

**Why**

- Validate the **overall UX, navigation, and stage modularity** before investing in real AI, transcription, and export.
- Give a place to **iterate on the content of each stage** (wording, fields, flows) while keeping tech extremely light.
- Provide a concrete skeleton that later implementations (backend + AI) can “plug into” without changing the structure.

Ground Zero is **not** about correctness of AI output. It’s about having a **clickable, editable prototype** where:

- You can create/open a project.
- You can move between the 4 stages.
- You can type/edit content at each stage.
- You can see how data “travels” between stages (even if it’s just mocked).

---

## 2. Scope for Ground Zero

### 2.1 In Scope (GZ)

- **Single-user, single-project experience**
  - One project at a time is enough for GZ (a very simple “Project List” is okay but not required to be robust).

- **4-tab layout + navigation**
  - Visible tab bar (or stepper) for Tabs 1–4.
  - “Next / Previous” buttons that move between tabs.

- **Editable forms & text areas**
  - Stage 1: textareas/fields for transcript, outline, resources.
  - Stage 2: static example visuals with selection toggles.
  - Stage 3: large editable draft area (Markdown-like or rich text).
  - Stage 4: basic fields for title, subtitle, credits and a structural preview.

- **Simple local persistence**
  - “Save” behaviour that keeps data at least while the app is open.
  - For GZ, it’s enough that data survives navigation between tabs for a single session.

- **Dummy actions**
  - Buttons like “Generate transcript”, “Generate visuals”, “Generate draft”, “Export” that:
    - Change UI state.
    - Insert placeholder content.
    - Show how the final product *will* behave, without doing real processing.

### 2.2 Out of Scope (GZ)

- Real AI integration:
  - No real transcription from video.
  - No real outline generation.
  - No real visual generation.
  - No real draft generation from transcript.

- Real file processing:
  - Video upload field may exist visually, but **no need** to actually parse the file.

- Real PDF/ePub export:
  - “Export” can just show a message or download a simple placeholder file.

- Multi-project management, user accounts, or collaboration.

---

## 3. High-Level Workflow (Ground Zero)

For Ground Zero, the workflow is about **moving through the stages with editable placeholders**:

1. **Create / Open Project**
   - Start a new “Webinar2Ebook Project” from a simple landing view.
   - Enter a project name and (optionally) webinar type.

2. **Tab 1: Transcript, Outline & Resources**
   - See project header (title + webinar type).
   - Fill in:
     - Transcript (textarea).
     - Outline (structured list editor).
     - Resources (simple list of items).
   - Optionally click “Generate transcript/outline/resources” to auto-fill with canned sample data.

3. **Tab 2: Visuals**
   - See a static gallery of 4–8 example visuals (images or cards).
   - Each visual has a fake title/description and a toggle for “Include in ebook”.
   - Can add a custom visual entry with just text (e.g. “Custom diagram for Chapter 2”).

4. **Tab 3: Draft**
   - See:
     - Style configuration controls (audience, tone, depth, target pages).
     - A large textarea / editor containing a placeholder ebook draft.
   - “Generate draft” replaces the placeholder text with some other sample content, just to show behaviour.
   - User can freely edit the draft and their edits persist while navigating tabs.

5. **Tab 4: Final & Export**
   - Fill in:
     - Ebook title & subtitle.
     - Credits info.
   - See a simple structural preview:
     - List of chapters (mirroring the outline from Tab 1).
     - List of selected visuals (from Tab 2).
   - “Export” button:
     - For GZ, can:
       - Download a very simple `.md` or `.txt` file composed from current content **or**
       - Just show a “Coming soon” dialog summarising what would be exported.

---

## 4. Minimal Conceptual Data Model (GZ)

Even for Ground Zero, keep a single **Project** object so everything is modular later.

### 4.1 Project (Ground Zero subset)

**Identity & Metadata**

- `projectId` (simple ID)
- `title` (working ebook title)
- `webinarType` (Standard Presentation / Training)

**Stage 1 (GZ)**

- `transcriptText` (string)
- `outlineItems`: list of `{ id, title, level, notes? }`
- `resources`: list of `{ id, label, urlOrNote }`

**Stage 2 (GZ)**

- `visuals`: list of `{ id, title, description, selected }`

**Stage 3 (GZ)**

- `draftText` (full ebook draft, plain text/Markdown)
- `styleConfig`:
  - `audience`
  - `tone`
  - `depth`
  - `targetPages`

**Stage 4 (GZ)**

- `finalTitle`
- `finalSubtitle`
- `creditsText`

> Ground Zero is satisfied if **all of these fields can be edited and preserved** during a session.

---

## 5. Ground Zero User Stories

### GZ-US1 — Create a Project and See the 4 Tabs

**As a** user  
**I want** to create a new project and immediately see the 4-step tabbed workflow  
**So that** I understand the overall conversion process.

**Acceptance Criteria**

- [ ] From the landing screen, I can enter a project name and click “Create project”.
- [ ] I am then taken to a view with four tabs (1–4) clearly labeled.
- [ ] The active tab is Tab 1 on first load.

---

### GZ-US2 — Edit Transcript, Outline & Resources (Manually)

**As a** user  
**I want** to manually enter and edit the transcript, outline, and resources  
**So that** I can simulate the inputs without any real AI.

**Acceptance Criteria**

- [ ] Tab 1 shows:
  - A textarea for transcript.
  - A simple list editor for outline items.
  - A simple list editor for resources.
- [ ] I can type in each field and see my changes.
- [ ] When I move to another tab and come back, my edits remain.
- [ ] “Generate sample data” button fills these fields with hard-coded example content (optional but helpful).

---

### GZ-US3 — Select Visuals from a Static Gallery

**As a** user  
**I want** to select or deselect visuals from a static gallery  
**So that** I can experience how visual selection will work.

**Acceptance Criteria**

- [ ] Tab 2 shows a grid/list of fixed example visuals (cards with title + description).
- [ ] Each visual has a toggle (checkbox or similar) for “Include”.
- [ ] I can toggle selection and the state is preserved when navigating away and back.
- [ ] There is a simple button “Add custom visual” that adds a text-only row to the list.

---

### GZ-US4 — Configure Style and Edit Draft

**As a** user  
**I want** to configure style options and edit a draft in place  
**So that** I see how style and draft editing will feel later.

**Acceptance Criteria**

- [ ] Tab 3 shows style controls:
  - Audience (e.g. select input).
  - Tone.
  - Depth.
  - Target pages.
- [ ] Tab 3 shows a large text editor for “Draft”.
- [ ] “Generate draft” fills the editor with hard-coded sample text (e.g. from a template).
- [ ] I can edit the draft and see edits persist across tab navigation.

---

### GZ-US5 — Final Metadata & Fake Export

**As a** user  
**I want** to set basic ebook metadata and trigger a fake export  
**So that** I understand how the final stage will look.

**Acceptance Criteria**

- [ ] Tab 4 shows fields for:
  - Final title.
  - Subtitle.
  - Credits.
- [ ] Tab 4 shows a simple preview:
  - Chapters (derived from outline items in Tab 1).
  - Visuals list (from selected visuals in Tab 2).
- [ ] “Export” button:
  - Either generates a simple merged text/Markdown file using the current draft + metadata **or**
  - Shows a modal summarising what would be exported (“Title X, Y chapters, Z visuals, draft length N characters”) with a “Coming soon” note.

---

## 6. Ground Zero Functional Requirements

### 6.1 General

- [ ] GZ-FR1: Maintain a Project object in memory that is shared by all four tabs.
- [ ] GZ-FR2: Navigation between tabs must be possible via both tab clicks and “Next/Previous” buttons.
- [ ] GZ-FR3: Changes to any field in any tab are preserved when switching tabs during the session.

### 6.2 Tab 1 (Transcript, Outline & Resources)

- [ ] GZ-FR4: Provide:
  - Transcript textarea.
  - Outline list editor (add/remove/reorder items).
  - Resources list editor (add/remove items).
- [ ] GZ-FR5: Optional: a single “Fill with sample data” button that populates all three sections with canned text.

### 6.3 Tab 2 (Visuals)

- [ ] GZ-FR6: Display 4–8 example visual cards with:
  - Title.
  - Short description.
  - Selection toggle.
- [ ] GZ-FR7: Persist selection state in the Project.
- [ ] GZ-FR8: Provide “Add custom visual” to append a text-only item to the list.

### 6.4 Tab 3 (Draft)

- [ ] GZ-FR9: Display style controls with simple inputs (no validation needed beyond “has some value”).
- [ ] GZ-FR10: Display a large draft editor area.
- [ ] GZ-FR11: “Generate draft” replaces draft editor content with fixed sample text.
- [ ] GZ-FR12: Edits to the draft are stored in the Project object.

### 6.5 Tab 4 (Final & Export)

- [ ] GZ-FR13: Display inputs for final title, subtitle, and credits.
- [ ] GZ-FR14: Display a structural preview:
  - Chapters = outline items from Tab 1.
  - Visuals = selected items from Tab 2.
- [ ] GZ-FR15: “Export” performs a fake export:
  - Either downloads a simple text/Markdown file **or**
  - Shows a modal summarising the current state.
