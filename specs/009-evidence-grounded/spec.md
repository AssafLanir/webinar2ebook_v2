# Feature Specification: Evidence-Grounded Drafting

**Feature Branch**: `009-evidence-grounded`
**Created**: 2026-01-04
**Status**: Draft
**Input**: Fix core failure modes in ebook drafts: wrong structure for interviews, hallucinated content, generic filler/platitudes, missing key points. Implement prevention-first approach with Evidence Map grounding.

## 1. Overview

This feature fundamentally changes the draft generation approach from "write freely then check" to "ground then write". Instead of detecting hallucinations post-generation (Spec 008), this prevents them by requiring every claim to be grounded in source material before generation begins.

### Goals

- Eliminate hallucinated content by grounding all claims in Evidence Map before writing
- Support different content structures via Content Mode (Interview/Essay/Tutorial)
- Provide targeted rewrite capability for any remaining flagged issues
- Integrate with existing QA system for verification

### Non-Goals

- No changes to existing draft generation endpoints (reuse pipeline, add `POST /qa/rewrite` for targeted fixes)
- No major UI overhaul (only: Content Mode dropdown, Strict Grounded toggle, Fix Flagged Issues button, diff view for rewrites)
- No multi-pass rewrite loops (single targeted pass only)
- No Gamma/MCP/Design Pack integration
- No changes to export or preview functionality
- No changes to outline/planning structure (Content Mode affects chapter prose, not outline)

### Relationship to Spec 008

- **Spec 008 US1 (QA Report)**: Remains - used for verification after grounded generation
- **Spec 008 US2 (QA UI)**: Remains - displays any issues found
- **Spec 008 US3 (Editor Pass)**: **SUPERSEDED** - replaced by targeted rewrite in this spec
- **Spec 008 US4 (Regression Suite)**: Deferred - can be implemented later

## 2. User Scenarios & Testing

### User Story 1 - Evidence-Grounded Interview Draft (Priority: P1)

As a content creator working with interview/webinar transcripts, I want the system to generate chapter content that is strictly grounded in what was actually said, so that the ebook accurately represents the source material without hallucinations or generic filler.

**Why this priority**: This addresses the core quality failures reported: hallucinated content, generic platitudes, and missing key points. Prevention is more effective than detection.

**Independent Test**: Generate a draft with Content Mode = "Interview" and Strict Grounded = true → Verify no "Key Action Steps" section, no biography unless mentioned in transcript, no motivational platitudes, all claims traceable to transcript quotes.

**Acceptance Scenarios**:

1. **Given** a transcript and Content Mode = "Interview", **When** I generate a draft, **Then** each chapter's content maps directly to evidence from the transcript
2. **Given** Strict Grounded = true, **When** generating content, **Then** no claims appear that aren't supported by transcript quotes in the Evidence Map
3. **Given** an interview transcript, **When** I generate a draft, **Then** no "Key Action Steps" or "Action Items" sections are created
4. **Given** a transcript without biographical information, **When** I generate a draft, **Then** no biography or speaker background is invented
5. **Given** generation completes, **When** I view the job status, **Then** I can see the Evidence Map that was used for grounding

---

### User Story 2 - Content Mode Selection (Priority: P1)

As a content creator, I want to select the type of source material (Interview, Essay, Tutorial), so that the generated ebook uses appropriate structure and tone for that content type.

**Why this priority**: Different source types require fundamentally different structures. An interview should read as a conversation/narrative, not a how-to guide.

**Independent Test**: Generate drafts with each Content Mode → Verify structure matches mode (Interview = narrative/quotes, Essay = argument flow, Tutorial = step-by-step).

**Acceptance Scenarios**:

1. **Given** Content Mode = "Interview", **When** I generate a draft, **Then** chapters are structured around speaker insights and quotes, not action steps
2. **Given** Content Mode = "Essay", **When** I generate a draft, **Then** chapters follow argument/thesis structure with supporting points
3. **Given** Content Mode = "Tutorial", **When** I generate a draft, **Then** chapters include step-by-step instructions and action items
4. **Given** no Content Mode is selected, **When** I generate a draft, **Then** it defaults to "Interview" mode

---

### User Story 3 - Targeted Rewrite Pass (Priority: P2)

As a content creator, after QA identifies remaining issues in my grounded draft, I want to run a single targeted rewrite pass that fixes only the flagged sections without changing verified content or adding new claims.

**Why this priority**: Even with Evidence Map grounding, some issues may slip through (clarity, repetition). This provides a controlled fix mechanism. P2 because the grounding should catch most issues.

**Independent Test**: Generate draft → QA flags 3 issues → Run rewrite pass → Verify only those 3 sections changed, no new claims added, faithfulness score maintained or improved.

**Acceptance Scenarios**:

1. **Given** a QA report with flagged issues, **When** I click "Fix Flagged Issues", **Then** only sections containing those issues are rewritten
2. **Given** a rewrite pass completes, **When** I compare before/after, **Then** non-flagged sections are unchanged
3. **Given** a rewrite pass completes, **When** QA runs again, **Then** faithfulness score is not decreased
4. **Given** a rewrite pass, **When** it completes, **Then** I can see a diff of what changed
5. **Given** I already ran a rewrite pass, **When** I try to run another, **Then** I see a warning that multiple passes may cause drift

---

### Edge Cases

- What happens when transcript is very short (<500 words)? → Evidence Map may have sparse entries; generate shorter chapters with available material only
- What happens when Evidence Map finds no key claims for a chapter? → Flag chapter as "insufficient source material" and skip or merge with adjacent chapter
- What happens when Content Mode doesn't match source type? → Proceed but warn user (e.g., "Tutorial mode selected but source appears to be an interview")
- What happens when rewrite pass times out? → Original content preserved, partial changes discarded, user can retry
- What happens to existing projects without Content Mode? → Default to "Interview" mode on next generation

## 3. Requirements

### Functional Requirements

**Content Mode & Grounding**
- **FR-001**: System MUST support Content Mode enum: "interview" | "essay" | "tutorial"
- **FR-002**: System MUST support `strict_grounded` boolean toggle (default: true for interview mode)
- **FR-003**: System MUST store Content Mode and strict_grounded in StyleConfig
- **FR-004**: System MUST default to "interview" mode when not specified

**Evidence Map Generation**
- **FR-005**: System MUST generate an Evidence Map before chapter content generation
- **FR-006**: Evidence Map MUST contain per-chapter: claims[], support[] (transcript quotes with char offsets), must_include[]
- **FR-007**: System MUST expose Evidence Map in job status for transparency
- **FR-007a**: System MUST persist Evidence Map to project.evidenceMap after generation (not just in job store)
- **FR-008**: System MUST use only Evidence Map entries + referenced transcript segments for chapter generation
- **FR-009**: When strict_grounded=true, System MUST NOT generate content without supporting evidence
- **FR-009a**: When strict_grounded=true AND a chapter has zero or insufficient evidence entries, System MUST skip/merge chapter and emit warning (NOT generate filler)

**Interview Mode Constraints**
- **FR-010**: In Interview mode, System MUST NOT generate "Key Action Steps" or "Action Items" sections
- **FR-011**: In Interview mode, System MUST NOT generate biography/background unless explicitly in transcript
- **FR-012**: In Interview mode, System MUST NOT generate motivational platitudes or generic advice
- **FR-013**: In Interview mode, System MUST NOT introduce topics not present in Evidence Map

**Targeted Rewrite**
- **FR-014**: System MUST provide "Fix Flagged Issues" action when QA report has issues
- **FR-015**: Rewrite MUST only modify sections containing flagged issues
- **FR-016**: Rewrite MUST NOT add claims not in the original Evidence Map
- **FR-017**: Rewrite MUST preserve markdown structure (headings, lists, code blocks)
- **FR-018**: System MUST limit to one rewrite pass per user action (no auto-loops)
- **FR-019**: System MUST show before/after diff of rewritten sections
- **FR-020**: System MUST warn if user attempts multiple rewrite passes

**Integration**
- **FR-021**: System MUST integrate with existing async job pipeline (job_id, status polling)
- **FR-022**: System MUST trigger QA analysis after generation (reuse Spec 008 T019)
- **FR-023**: System MUST add "evidence_map" phase to job status progression

### Key Entities

- **ContentMode**: Enum - "interview" | "essay" | "tutorial"
- **EvidenceMap**: Per-chapter grounding data with claims, support quotes, must_include items
- **EvidenceEntry**: Single claim with transcript quote reference and confidence score
- **ChapterEvidence**: Collection of evidence entries for one chapter
- **RewritePlan**: Sections to rewrite with issue references and constraints

## 4. Success Criteria

### Measurable Outcomes

- **SC-001**: Interview mode drafts contain zero "Action Steps" sections (100% compliance)
- **SC-002**: Interview mode drafts with strict_grounded=true have faithfulness score >= 85
- **SC-003**: Evidence Map generation adds < 30 seconds to total generation time
- **SC-004**: Targeted rewrite pass reduces flagged issues by >= 50% without decreasing faithfulness
- **SC-005**: Users can see Evidence Map in job status within 5 seconds of planning phase completion
- **SC-006**: Zero hallucinated biographical content in interview mode when bio not in transcript

## 5. Assumptions

- Existing LLM abstraction (OpenAI primary, Anthropic fallback) is sufficient for Evidence Map generation
- Transcript text is available in project.transcriptText field
- StyleConfig model can be extended with content_mode and strict_grounded fields
- Existing job store pattern can accommodate new "evidence_map" phase
- Single rewrite pass is sufficient; users who need more can regenerate

## 6. Dependencies

- Spec 004: Draft generation pipeline (job store, chapter generation)
- Spec 008 US1/US2: QA report generation and display (for verification and rewrite triggers)
- Existing StyleConfig model in backend/src/models/style_config.py
- Existing draft_service.py async job pattern

## 7. Out of Scope

- Custom Content Mode definitions (only 3 predefined modes)
- User-editable Evidence Map (read-only for transparency)
- Real-time evidence display during generation
- Multiple rewrite passes in single action
- Automatic Content Mode detection from transcript
- Citation/footnote generation linking to transcript timestamps
