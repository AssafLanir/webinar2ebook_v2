# Feature Specification: Tab 1 AI Assist

**Feature Branch**: `003-tab1-ai-assist`
**Created**: 2025-12-14
**Status**: Draft
**Input**: User description: "Tab 1 AI Assist: Transcript Cleanup & Structure Suggestions"
**Depends On**:
- `001-frontend-shell` (Tab 1 UI: Transcript, Outline, Resources)
- `002-backend-foundation` (Project persistence, project CRUD, auto-save)

## Overview

Tab 1 currently allows users to manually paste/type a transcript, build an outline item by item, and add resources one by one. This feature introduces an AI-assisted workflow to:

1. Clean up raw transcripts into readable versions
2. Suggest structured outlines derived from the transcript
3. Suggest relevant resources based on the transcript

**Core Principle**: AI assists but never silently overwrites. Users always preview suggestions before applying them.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Clean Transcript Preview & Apply (Priority: P1)

As a content creator, when I paste a raw webinar transcript into Tab 1, I want to click a button and see a cleaned version (less filler, normalized punctuation, better paragraphing) so I can quickly replace my messy transcript with a more readable one after reviewing it.

**Why this priority**: This is the foundational AI assistance feature. Without a clean transcript, downstream suggestions (outline, resources) are less effective. Most users start with messy raw transcripts.

**Independent Test**: Can be fully tested by pasting any raw transcript text, clicking "Clean Transcript (AI)", reviewing the preview, and choosing to Apply or Discard. Delivers immediate value by reducing manual cleanup time.

**Acceptance Scenarios**:

1. **Given** I have pasted a raw transcript with filler words and inconsistent formatting, **When** I click "Clean Transcript (AI)", **Then** I see a loading indicator followed by a preview of the cleaned transcript without my original being changed.

2. **Given** the AI preview is displayed with a cleaned transcript, **When** I click "Apply", **Then** my transcript textarea is updated with the cleaned version and the preview closes.

3. **Given** the AI preview is displayed, **When** I click "Discard" or close the preview, **Then** my original transcript remains unchanged.

4. **Given** the AI preview is displayed, **When** I click "Copy", **Then** the cleaned transcript is copied to my clipboard (browser permitting).

---

### User Story 2 - Suggest Outline from Transcript (Priority: P1)

As a content creator, once I have a transcript, I want the system to suggest a structured outline (sections & subsections) based on the transcript, so I can quickly get a chapter structure instead of starting from an empty list.

**Why this priority**: Creating structure from a long transcript is time-consuming. An AI-suggested outline provides a meaningful starting point that users can refine.

**Independent Test**: Can be fully tested by having any transcript text, clicking "Suggest Outline (AI)", selecting some or all suggested items, and inserting them. Delivers value by jumpstarting the outline creation process.

**Acceptance Scenarios**:

1. **Given** I have a transcript with discernible topics and sections, **When** I click "Suggest Outline (AI)", **Then** I see a preview listing suggested outline items with title, level, and optional notes.

2. **Given** the outline suggestion preview is displayed, **When** I use "Select all" and click "Insert all", **Then** all suggested items are appended to my existing outline.

3. **Given** the outline suggestion preview is displayed with checkboxes, **When** I select only specific items and click "Insert selected", **Then** only those selected items are appended to my outline.

4. **Given** I already have some outline items, **When** I apply AI suggestions, **Then** the new items are appended (not replacing) my existing items.

5. **Given** the outline suggestion preview is displayed, **When** I click "Cancel", **Then** no changes are made to my outline.

---

### User Story 3 - Suggest Resources (Priority: P2)

As a content creator, I want the system to suggest a small set of resources (links or topics) relevant to the transcript, so I can seed the "Resources" section without searching from scratch.

**Why this priority**: While valuable, this is secondary to having a clean transcript and outline. Users can still manually add resources, but AI suggestions save research time.

**Independent Test**: Can be fully tested by having any transcript, clicking "Suggest Resources (AI)", selecting suggestions, and adding them. Delivers value by providing relevant starting points for resources.

**Acceptance Scenarios**:

1. **Given** I have a transcript mentioning specific topics or tools, **When** I click "Suggest Resources (AI)", **Then** I see 3-5 suggested resources with labels and URLs or notes.

2. **Given** the resource suggestion preview is displayed with checkboxes, **When** I select items and click "Add selected", **Then** selected resources are appended to my resources list.

3. **Given** I already have resources in my list, **When** I apply AI resource suggestions, **Then** the new suggestions are appended without removing or modifying existing resources.

4. **Given** the resource suggestion preview is displayed, **When** I click "Cancel", **Then** no changes are made to my resources.

---

### User Story 4 - Robust Failure Handling (Priority: P1)

As a user, if the AI service fails (time-out, no configuration, server error), I want to see a clear, non-technical message and have the option to retry or continue manually, without losing any of my content.

**Why this priority**: Core to user trust. AI features must fail gracefully without data loss or confusing error messages.

**Independent Test**: Can be tested by simulating AI service unavailability and verifying user-friendly error messages appear with retry options while all user content remains intact.

**Acceptance Scenarios**:

1. **Given** the AI service is unavailable, **When** I click any AI action button, **Then** I see a user-friendly message like "AI suggestions are temporarily unavailable" with a retry option.

2. **Given** an AI request times out, **When** the timeout occurs, **Then** I see an error message and my content remains unchanged.

3. **Given** an AI request fails, **When** I click "Retry", **Then** the request is attempted again.

4. **Given** no transcript text is present, **When** I view the AI action buttons, **Then** they are disabled with appropriate indication.

---

### User Story 5 - Persisted Results Only (Priority: P3)

As a user, I want applied AI results (clean transcript, outline items, resources) to be saved with my project and available when I reopen it later.

**Why this priority**: Polish requirement. The persistence mechanism from feature 002 should handle this automatically once AI results are applied.

**Independent Test**: Can be tested by applying AI suggestions, refreshing/reopening the project, and verifying all applied content persists correctly.

**Acceptance Scenarios**:

1. **Given** I have applied a cleaned transcript using AI, **When** I reopen the project later, **Then** I see the cleaned transcript (not the raw original).

2. **Given** I have applied AI-suggested outline items, **When** I reopen the project later, **Then** I see those outline items in my outline.

3. **Given** AI preview data is displayed but not applied, **When** I navigate away or refresh, **Then** the unapplied preview data is not persisted.

---

### Edge Cases

- What happens when the transcript is very long (approaching 50,000 character limit)?
  - AI actions should still work but may take longer; UI shows loading state throughout.

- What happens when the transcript exceeds 50,000 characters?
  - API returns validation error; UI should prevent submission or show clear error message.

- What happens when the AI returns an empty or malformed response?
  - System shows a user-friendly error and allows retry.

- What happens when I try to trigger multiple AI actions simultaneously?
  - Only one AI action can be in progress at a time; other buttons are disabled during processing.

- What happens if I close the preview modal while an AI request is still loading?
  - The request should be cancelled or the result ignored when complete.

- What happens if AI suggests outline items with invalid levels?
  - System should normalize/validate levels to acceptable range (1-3).

---

## Requirements *(mandatory)*

### Functional Requirements

**General / Integration**

- **FR-001**: Tab 1 MUST expose three distinct AI actions: "Clean Transcript (AI)", "Suggest Outline (AI)", and "Suggest Resources (AI)"
- **FR-002**: Each AI action MUST have a clear button, a visible loading/processing indicator, and a visible error state on failure
- **FR-003**: AI action buttons MUST be disabled when transcript text is empty (their required input)
- **FR-004**: At most ONE AI action MAY be in progress at a time on Tab 1 (no concurrent calls)
- **FR-005**: All AI actions MUST operate on the current in-memory project state and trigger existing persistence mechanisms when applied

**Transcript Cleanup**

- **FR-010**: When "Clean Transcript (AI)" is clicked with non-empty transcript, system MUST send transcript to AI service and show processing state
- **FR-011**: On successful AI response, system MUST present cleaned transcript in a preview UI without altering existing transcriptText
- **FR-012**: The preview MUST offer: Apply (replace transcript), Copy (to clipboard), Discard/Close (no changes)
- **FR-013**: When Apply is confirmed, system MUST replace transcriptText and trigger persistence
- **FR-014**: On AI error or timeout, system MUST show error message, keep transcript unchanged, and allow retry

**Outline Suggestion**

- **FR-020**: When "Suggest Outline (AI)" is clicked with non-empty transcript, system MUST send transcript to AI service and show processing state
- **FR-021**: On success, AI MUST return suggested outline items with: title (required), level (1-3), notes (optional)
- **FR-022**: System MUST display suggested items in preview with checkbox per item and select all/deselect all controls
- **FR-023**: The preview MUST offer: Insert selected, Insert all, Cancel/Close
- **FR-024**: Applying suggestions MUST append items to existing outline without deleting or modifying existing items
- **FR-025**: Order of appended items MUST respect order returned by AI service
- **FR-026**: After applying, changes MUST propagate through existing persistence

**Resource Suggestion**

- **FR-030**: When "Suggest Resources (AI)" is clicked with non-empty transcript, system MUST send transcript to AI service and show processing state
- **FR-031**: On success, AI MUST return 3-5 suggested resources with: label (required), urlOrNote (URL or short note)
- **FR-032**: System MUST display suggestions in preview with checkbox per item and select all/deselect all
- **FR-033**: The preview MUST offer: Add selected, Add all, Cancel/Close
- **FR-034**: Applying suggestions MUST NOT remove or edit existing resources
- **FR-035**: After applying, resources MUST be persisted via existing mechanisms
- **FR-036**: AI-suggested resources MUST be created as resourceType = "url_or_note" entries (not "file")

**Error Handling**

- **FR-040**: If AI backend is unreachable or returns error, UI MUST show human-readable message (e.g., "AI suggestions are temporarily unavailable")
- **FR-041**: Raw technical error messages MUST NOT be shown directly to users
- **FR-042**: AI action UI MUST always allow Retry and returning to manual editing without data loss
- **FR-043**: AI action buttons MUST be disabled while an AI request is in progress to prevent duplicate requests

**Persistence & State**

- **FR-050**: Once AI suggestions are applied, resulting Project state MUST be treated like any manual edit (eligible for auto-save)
- **FR-051**: System MUST NOT rely on storing raw AI responses; only existing Project model fields are needed
- **FR-052**: Temporary AI preview data MAY be kept in UI state only and is not required to survive page reload

---

### Key Entities

- **AIPreviewState**: Temporary UI state holding AI response data (cleaned transcript text, suggested outline items, or suggested resources) before user applies them. Not persisted.

- **OutlineItem**: Existing entity with title, level (1-3), and optional notes. AI suggestions use this same structure.

- **Resource**: Existing entity. AI suggestions create resources with resourceType = "url_or_note", label, and urlOrNote fields.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can paste a transcript, use "Clean Transcript (AI)", and have a readable cleaned version applied in under 30 seconds (for typical transcripts; max 50,000 characters supported)

- **SC-002**: Users can generate and apply an outline of 10+ suggested items from a transcript in under 45 seconds

- **SC-003**: Users can generate and apply 3-5 resource suggestions from a transcript in under 30 seconds

- **SC-004**: When AI service fails, 100% of failures show a user-friendly error message (no raw technical errors displayed)

- **SC-005**: Applied AI suggestions persist correctly across project reopen, with 100% data integrity

- **SC-006**: All existing Tab 1 manual editing flows continue to work unchanged (backward compatibility)

- **SC-007**: At least one automated test covers: create project, paste transcript, use AI action, apply suggestions, verify saved content after reopen

---

## Non-Functional Requirements

- **NFR-001 (Performance)**: AI actions SHOULD complete within 20 seconds for typical transcripts. Maximum supported transcript length is 50,000 characters. If processing exceeds 20 seconds, UI MUST indicate ongoing processing and allow cancellation.

- **NFR-002 (Resilience)**: AI features MUST degrade gracefully - users can always continue manual editing, no data loss on AI failures.

- **NFR-003 (Privacy)**: No logging of full transcript content beyond development debugging needs.

- **NFR-004 (Accessibility)**: AI action buttons and status indicators SHOULD be accessible via keyboard and screen readers (proper ARIA labels for loading/error states).

---

## Assumptions

- AI provider selection and configuration is an implementation detail; any provider satisfying the functional requirements is acceptable
- English language only for this feature (non-English may work but is not guaranteed)
- Existing auto-save mechanism from feature 002 handles persistence of applied AI results
- Browser clipboard API availability for Copy functionality (graceful degradation if unavailable)
- Backend will implement appropriate request timeouts and error handling
