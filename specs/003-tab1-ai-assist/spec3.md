# 003 – Tab 1 AI Assist: Transcript Cleanup & Structure Suggestions

**Spec Input File**: `spec2.md`  
**Feature ID (suggested)**: `003-tab1-ai-assist`  
**Status**: Draft  
**Depends On**:  
- `001-frontend-shell` (Tab 1 UI: Transcript, Outline, Resources)  
- `002-backend-foundation` (Project persistence, project CRUD, auto-save)

---

## 1. Overview

Tab 1 currently allows users to manually:

- Paste or type a **transcript**
- Build an **outline** item by item
- Add **resources** one by one

This works, but is slow and cognitively heavy when starting from a long, messy webinar transcript.

**This feature introduces an AI-assisted workflow for Tab 1**:

1. Clean up the raw transcript into a readable version.
2. Suggest a structured outline derived from the transcript.
3. Suggest relevant resources (links or topics) based on the transcript.

The focus is on **assistance and suggestions**, not automation:

- AI never silently overwrites user content.
- Users always see a **preview** of AI output and choose whether and how to apply it.
- Existing project persistence and auto-save continue to work as-is.

---

## 2. Goals & Non-Goals

### 2.1 Goals

- **G1 – Faster “First Pass”**: Reduce the time from “raw transcript” to a decent **starting point** for ebook structure.
- **G2 – Non-Destructive AI**: Ensure AI suggestions are always **previewed first**, and only applied when explicitly confirmed.
- **G3 – Integrated UX**: Keep all AI actions within **Tab 1**; no new pages or modes required.
- **G4 – Predictable Errors**: When AI fails or is unavailable, show clear, consistent messages and allow easy retry.
- **G5 – Reuse Existing Model**: Use the existing Project fields (transcriptText, outlineItems, resources) as the destination for accepted suggestions.

### 2.2 Non-Goals

- **NG1 – Full Automation**: Not trying to automatically create the entire ebook or replace human editing.
- **NG2 – Perfect Summarization**: We do not require the AI to produce “perfect” outlines or resources; suggestions only need to be **useful starting points**.
- **NG3 – Advanced Editing UI**: No diff viewer, rich track-changes, or advanced merge tools in this feature (simple preview/accept flows only).
- **NG4 – Multi-language Support**: Only English is in scope for this feature. Non-English content might still work but is not a requirement.
- **NG5 – AI Provider Management**: No UI for selecting providers or editing prompts (implementation detail).

---

## 3. User Stories

### Priority Legend

- **P1** – Must have for this feature to be considered complete.  
- **P2** – Nice to have if not too expensive.  
- **P3** – Optional polish.

---

### US1 (P1) – Clean Transcript (Preview & Apply)

> As a content creator, when I paste a raw webinar transcript into Tab 1, I want to click a button and see a **cleaned version** (less filler, normalized punctuation, better paragraphing) so I can quickly replace my messy transcript with a more readable one **after reviewing it**.

- Trigger: “Clean Transcript (AI)” button in Tab 1.
- Behaviour:
  - Shows a clear “processing” state.
  - Displays a preview of the cleaned transcript.
  - Offers actions: **Apply**, **Copy**, **Discard**, **Edit**.
  - Never overwrites the current transcript unless I click **Apply**.

---

### US2 (P1) – Suggest Outline from Transcript

> As a content creator, once I have a transcript, I want the system to suggest a **structured outline** (sections & subsections) based on the transcript, so I can quickly get a chapter structure instead of starting from an empty list.

- Trigger: “Suggest Outline (AI)” button in Tab 1.
- Behaviour:
  - Uses the current transcript as input.
  - Use underlying AI to analyze and extract structure based on the transcript and standard shared outlines.
  - Returns a proposed outline as a list of items (title + level + optional notes).
  - Shows suggestions in a preview area with checkboxes.
  - I can:
    - **Insert all** items, or
    - **Insert selected** items.
    - **Cancel** to discard suggestions.
    - **Edit** to modify suggestions before inserting.
  - Suggestions are **appended** to the existing outline; they do not automatically delete or overwrite existing items.

---

### US3 (P2) – Suggest Resources

> As a content creator, I want the system to suggest a small set of **resources** (links or topics) relevant to the transcript, so I can seed the “Resources” section without searching from scratch.

- Trigger: “Suggest Resources (AI)” button in Tab 1.
- Behaviour:
  - Uses the current transcript as input.
  - Extracts key topics, references, URLs mentioned in the transcript, and relevant external resources - articles, tools, websites.
  - Returns 3–5 suggestions, each with:
    - A short label, and
    - Either a URL **or** a short note.
  - Shows suggestions in a preview area with checkboxes.
  - I can add selected suggestions into the existing Resources list.

---

### US4 (P1) – Robust Failure Handling

> As a user, if the AI service fails (time-out, no configuration, server error), I want to see a **clear, non-technical message** and have the option to **retry** or continue manually, without losing any of my content.

- AI buttons show:
  - Disabled state when inputs are missing (e.g., empty transcript).
  - “Loading…” state while waiting.
  - Error state with user-friendly message and a retry option.
- No changes are applied to transcript/outline/resources if AI fails.

---

### US5 (P3) – Persisted Results, Not Raw AI Logs

> As a user, I don’t care about raw AI JSON or logs; I just want the **applied results** (clean transcript, outline items, resources) to be saved with the project and available when I reopen it later.

- Only the **final applied** content is stored with the project.
- AI preview data can be transient (no requirement to store it in the DB).
- On reopen, I see my latest transcript, outline, and resources, as usual.


---

## 4. Functional Requirements

### 4.1 General / Integration

- **FR-001**: Tab 1 MUST expose three distinct AI actions:
  - “Clean Transcript (AI)”
  - “Suggest Outline (AI)”
  - “Suggest Resources (AI)”
- **FR-002**: Each action MUST have:
  - A clear button or call-to-action.
  - A visible loading/processing indicator.
  - A visible error state on failure.
- **FR-003**: AI action buttons MUST be disabled when their required inputs are missing:
  - Clean Transcript / Suggest Outline / Suggest Resources MUST require non-empty transcript text.
- **FR-004**: At most ONE AI action MAY be in progress at a time on Tab 1 (no concurrent calls).
- **FR-005**: All AI actions MUST operate on the **current in-memory project state** and, once applied, MUST trigger existing persistence mechanisms (auto-save or manual save, per 002).

---

### 4.2 Transcript Cleanup (US1)

- **FR-010**: When “Clean Transcript (AI)” is clicked with a non-empty transcript:
  - System MUST send the transcript text to an AI suggestion service.
  - System MUST show a “processing” state until a response or error is received.
- **FR-011**: On successful AI response, system MUST present the cleaned transcript in a **preview UI**, without altering the existing transcriptText field.
- **FR-012**: The preview MUST offer at least these actions:
  - **Apply**: Replace the current transcriptText with the cleaned version.
  - **Copy**: Copy the cleaned transcript to clipboard (if supported by browser APIs).
  - **Discard / Close**: Close the preview without changing transcriptText.
- **FR-013**: When **Apply** is confirmed:
  - System MUST replace the transcriptText field for the current project with the cleaned transcript.
  - Existing persistence rules MUST ensure this new transcript is saved (per 002 auto-save behaviour).
- **FR-014**: If the AI service returns an error or times out:
  - System MUST show an error message and keep the current transcriptText unchanged.
  - System MUST allow the user to retry from the same Tab 1 context.

---

### 4.3 Outline Suggestion (US2)

- **FR-020**: When “Suggest Outline (AI)” is clicked with a non-empty transcript:
  - System MUST send the transcript text to an AI suggestion service.
  - System MUST show a “processing” state until a response or error is received.
- **FR-021**: On success, the AI MUST return a list of suggested outline items, each with:
  - `title` (string, required)
  - `level` (e.g., 1–3 or similar; mapping to existing outline levels)
  - `notes` (optional string)
- **FR-022**: System MUST display the suggested outline items in a preview UI with:
  - Checkbox or similar control per item.
  - “Select all” / “Deselect all” functionality.
- **FR-023**: The preview MUST offer at least:
  - **Insert selected**: Append only the selected suggested items to the existing outlineItems list.
  - **Insert all**: Append all suggested items to the existing outlineItems list.
  - **Cancel / Close**: Do nothing and close preview.
- **FR-024**: Applying suggestions MUST **append** items to the outlineItems list; it MUST NOT delete or modify existing items automatically.
- **FR-025**: The order of appended items MUST respect the order returned by the AI suggestion service.
- **FR-026**: After applying suggestions, changes MUST propagate through existing persistence (auto-save on tab switch etc.).

---

### 4.4 Resource Suggestion (US3)

- **FR-030**: When “Suggest Resources (AI)” is clicked with a non-empty transcript:
  - System MUST send the transcript text to an AI suggestion service.
  - System MUST show a “processing” state until a response or error is received.
- **FR-031**: On success, the AI MUST return 3–5 suggested resources, each with:
  - `label` (short descriptive string, required)
  - `urlOrNote` (string; either a URL or short note)
- **FR-032**: System MUST display suggested resources in a preview UI with:
  - Checkbox or similar control per resource.
  - “Select all” / “Deselect all”.
- **FR-033**: The preview MUST offer:
  - **Add selected**: Append selected suggestions as Resource items to the existing resources list.
  - **Add all**: Append all suggestions.
  - **Cancel / Close**: No changes.
- **FR-034**: Applying suggestions MUST NOT remove or edit existing resources automatically.
- **FR-035**: After applying suggestions, the resources list MUST be persisted via existing mechanisms.
- **FR-036**: AI-suggested resources MUST always be created as `resourceType = "url_or_note"` entries (label + urlOrNote).  
  AI MUST NOT create `resourceType = "file"` resources, since those correspond only to actual uploaded files.

---

### 4.5 Error Handling & Unavailability (US4)

- **FR-040**: If the AI backend is unreachable, misconfigured, or returns a server error, the UI MUST show a human-readable message, such as:
  - “AI suggestions are temporarily unavailable. Please try again later.”
  - “Cannot reach AI service. Check your connection or try again.”
- **FR-041**: Generic “Failed to fetch” or raw technical error messages MUST NOT be shown directly to the user.
- **FR-042**: The AI action UI MUST always allow:
  - **Retry** (if the underlying cause might be transient), and
  - Returning to manual editing without data loss.
- **FR-043**: AI action buttons MUST be disabled while an AI request is in progress to prevent duplicate requests.

---

### 4.6 Persistence & State

- **FR-050**: Once AI suggestions are applied (for transcript, outline, or resources), the resulting Project state MUST be treated like any manual edit:
  - It MUST be eligible for auto-save on tab change.
  - It MUST be fully recoverable when reopening the project later.
- **FR-051**: The system MUST NOT rely on storing raw AI responses or logs to reconstruct the project; only the fields already defined in the Project model are required for future sessions.
- **FR-052**: Any temporary AI preview data MAY be kept in UI state only and is not required to survive a full page reload.

---

## 5. Non-Functional Requirements (NFRs)

- **NFR-001 (Performance)**: For transcripts up to ~15,000 characters, AI actions SHOULD complete within **20 seconds** in typical conditions. If they exceed this, the UI MUST clearly indicate that the request is still running and allow cancellation.
- **NFR-002 (Resilience)**: AI features MUST degrade gracefully when unavailable:
  - User can always continue manual editing.
  - No data loss occurs due to AI action failures.
- **NFR-003 (Privacy)**: No new logging of full transcript content is required for this feature. Any implementation MUST avoid logging full transcripts or AI responses beyond what is necessary for debugging under development configurations.
- **NFR-004 (Vendor-Agnostic)**: This spec does NOT mandate any specific AI provider or protocol. Implementation MAY choose any provider as long as it satisfies the functional and error-handling requirements.
- **NFR-005 (Accessibility)**: Buttons and status indicators for AI actions SHOULD be accessible via keyboard and screen readers (e.g., proper ARIA labels for loading/error states).

---

## 6. UX & Interaction Details

### 6.1 Tab 1 Layout Additions

- Existing sections:
  - Transcript textarea
  - Outline editor
  - Resources editor
  - “Fill with sample data” button
- Additions:
  - An **“AI Assist” subsection** in Tab 1, grouping:
    - “Clean Transcript (AI)”
    - “Suggest Outline (AI)”
    - “Suggest Resources (AI)”
  - Visual separation (e.g., subheading and subtle border) to clarify that these are optional helpers.

*(Exact layout and styling are left to implementation as long as the above controls are clearly discoverable and grouped.)*

---

### 6.2 Transcript Cleanup Flow (US1)

1. User enters or pastes transcript text.
2. User clicks “Clean Transcript (AI)”.
3. System:
   - Validates there is text.
   - Shows a loading indicator near the button or in an AI Assist status area.
4. On success:
   - A modal or side panel opens with:
     - Original transcript (optional, if space allows).
     - Cleaned transcript (required).
     - Buttons: **Apply**, **Copy**, **Discard**.
5. On **Apply**:
   - Modal closes.
   - Transcript textarea is updated with cleaned text.
   - Existing saving mechanisms handle persistence.
6. On **Discard/close**:
   - Modal closes.
   - Transcript remains unchanged.

---

### 6.3 Outline Suggestion Flow (US2)

1. User ensures transcript is present.
2. User clicks “Suggest Outline (AI)”.
3. System:
   - Validates transcript presence.
   - Shows loading state.
4. On success:
   - Opens a modal/side panel listing suggested outline items.
   - Each item shows `title`, `level`, and optional `notes`.
   - Controls:
     - Checkbox per item.
     - “Select all” / “Deselect all”.
     - “Insert selected”, “Insert all”, “Cancel”.
5. On “Insert selected” / “Insert all”:
   - Selected items are appended to the existing outline list.
   - Outline editor reflects the updated list.
6. On “Cancel”:
   - No changes are made.

---

### 6.4 Resource Suggestion Flow (US3)

1. User ensures transcript is present.
2. User clicks “Suggest Resources (AI)”.
3. System:
   - Validates transcript presence.
   - Shows loading state.
4. On success:
   - Shows a modal/panel listing suggested resources with:
     - Label
     - URL or note
     - Checkbox per item
   - Controls:
     - “Add selected”, “Add all”, “Cancel”.
5. On apply:
   - Selected resources are appended to the existing resources list.
6. On cancel:
   - No changes.

---

### 6.5 Error & Unavailable States

- If AI returns a known error (e.g., “service unavailable”, validation failure), the UI SHOULD:
  - Display a concise message in the panel or a toast area (e.g., top-right).
  - Offer a “Retry” button where appropriate.
- If AI is completely disabled or unreachable (e.g., configuration missing in backend), the UI SHOULD:
  - Show a consistent message like “AI features are currently unavailable” and disable AI buttons.

---

## 7. Data Model & API Impact (High-Level)

> Note: Detailed endpoint design and request/response schemas will be defined in `specs/003-tab1-ai-assist/data-model.md` and `contracts/` by spec-kit.

- No **required** changes to the persisted Project schema:
  - We continue to use:
    - `transcriptText`
    - `outlineItems[]`
    - `resources[]`
- Implementations MAY introduce:
  - Internal backend routes for AI suggestions (e.g., “suggest_transcript_cleanup”, “suggest_outline”, “suggest_resources”).
  - Temporary frontend state to hold AI preview results.
- The persistent Project document MUST remain valid and compatible with versions created under features 001 and 002.

---

## 8. Dependencies & Assumptions

- Feature 003 assumes:
  - 001: Tab 1 UI exists and is functional (manual editing).
  - 002: Project persistence, list, open, auto-save, and delete are working and tested.
- Feature 003 MAY introduce:
  - New backend endpoints for AI suggestions.
  - Configuration toggles (e.g., “AI_ENABLED”) to disable AI in certain environments.
- AI functionality is assumed to be **best-effort**:
  - When disabled or failing, users can still fully use the existing manual workflow.

---

## 9. Success Criteria

This feature is considered successful when:

- **SC-001**: In manual QA, a test user can:
  - Paste a raw transcript.
  - Use “Clean Transcript (AI)” to get a usable cleaned version.
  - Use “Suggest Outline (AI)” and apply suggestions.
  - Use “Suggest Resources (AI)” and apply suggestions.
  - Refresh and reopen the project and see the applied content as expected.
- **SC-002**: AI failures (backend unavailable, timeouts) result in clear user messages with no data loss and no uncaught errors in logs.
- **SC-003**: At least one automated test covers a full flow:
  - Create project → paste transcript → use at least one AI action → apply suggestions → verify saved content after reopen.
- **SC-004**: The existing flows from 001 and 002 (create, list, open, auto-save, delete) remain functional and stable.

---

## 10. Open Questions / TBD

These do not block implementation but should be clarified during planning if possible:

- **OQ-003-1**: Should we support **“Replace existing outline”** as an option when applying suggestions, or keep this version strictly append-only?
- **OQ-003-2**: Should transcript cleanup also offer a “Append cleaned transcript below original” option, or is “Replace vs. Copy” sufficient for this iteration?
- **OQ-003-3**: Do we need any explicit indication in the UI that certain outline items/resources came from AI vs. manual, or is this irrelevant to the user?
- **OQ-003-4**: Is a **hard per-request timeout** (e.g., 20 seconds) required at the UX level, or is backend-level timeout sufficient as long as the UI shows loading/error states?

## 11. Future Work

- **US6 (P2) – Video to Transcript** — *explicitly out of scope for 003; will be specified in a separate feature (e.g. `004 – Video to Transcript`).*

  > As a content creator, I want to be able to upload a video file and have the system automatically generate a transcript for me, so I can skip manual transcription.

  - **Trigger**: “Upload Video” button in Tab 1.
  - **Behaviour**:
    - Accepts common video formats (MP4, AVI, MOV).
    - Uses a backend service to extract audio.
    - Transcribes the audio to text using an AI transcription service.
    - Populates the transcript textarea with the generated transcript.
    - Shows a loading indicator while processing.
    - Displays an error message if transcription fails.
