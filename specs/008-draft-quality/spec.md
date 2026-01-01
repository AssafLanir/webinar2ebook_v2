# Feature Specification: Draft Quality System

**Feature Branch**: `008-draft-quality`
**Created**: 2026-01-01
**Status**: Draft
**Input**: Systematic quality assessment for AI-generated ebook drafts with QA reports, editor pass, and regression suite

## 1. Overview

This feature adds a measurable quality assessment system for AI-generated ebook drafts. Instead of ad-hoc prompt tweaking, it implements an **instrument → diagnose → iterate** loop that produces structured QA reports with scores and issues, enabling systematic improvement over time.

### Goals

- Produce structured QA reports with scores, issues, and locations after draft generation
- Enable measurable improvement via regression suite of golden projects
- Provide optional "editor pass" to fix identified issues without adding new facts
- Create a repeatable improvement workflow with quantifiable metrics

### Non-Goals

- No new authentication system
- No image generation changes
- No large UI overhaul (minimal panel addition only)
- No changes to draft markdown as source of truth
- No real-time collaborative editing
- No recursive improvement passes (single pass only)

## 2. User Scenarios & Testing

### User Story 1 - QA Report Generation (Priority: P1)

As a content creator, after my draft is generated, I want to see a quality assessment report showing an overall score, issue counts, and specific problems with their locations, so I can understand what needs improvement before exporting.

**Why this priority**: This is the core instrumentation that enables all quality improvements. Without measurement, we cannot systematically improve.

**Independent Test**: Generate a draft for any project → QA report appears within 30 seconds → Report shows overall score (1-100), issue counts by severity, and rubric breakdown.

**Acceptance Scenarios**:

1. **Given** a completed draft generation, **When** the draft is saved, **Then** a QA analysis automatically runs and produces a structured report
2. **Given** a QA report, **When** I view it, **Then** I see an overall quality score from 1-100
3. **Given** a QA report, **When** I view issues, **Then** each issue shows severity (critical/warning/info), chapter location, and a clear message
4. **Given** a draft with repetitive content, **When** QA runs, **Then** the repetition score reflects the problem and specific repeated phrases are listed

---

### User Story 2 - QA Display in UI (Priority: P1)

As a content creator, I want to see QA results in a panel within Tab3 or Tab4 (not a modal) with a summary badge and expandable issue list, so I can quickly scan quality without interrupting my workflow.

**Why this priority**: The QA data is useless if users can't easily see and understand it. This is essential for the feedback loop.

**Independent Test**: Open Tab3 after draft completion → See "QA: X issues" badge → Click to expand issue list grouped by severity.

**Acceptance Scenarios**:

1. **Given** a completed QA report, **When** I view Tab3 or Tab4, **Then** I see a summary badge showing total issue count (e.g., "QA: 14 issues")
2. **Given** a QA panel, **When** I expand it, **Then** issues are grouped by severity (critical first, then warning, then info)
3. **Given** an issue in the list, **When** I view it, **Then** I see: severity icon, chapter/heading location, and short descriptive message
4. **Given** no issues found, **When** I view the QA panel, **Then** I see a success state with the overall score

---

### User Story 3 - Editor Pass (Priority: P2)

As a content creator, I want an optional "Run Improve Pass" button that rewrites text to fix identified issues without adding new facts, so I can automatically address common problems while maintaining faithfulness to the source material.

**Why this priority**: This is the "iterate" step. It's P2 because we need measurement (P1) before we can safely improve. Also requires careful implementation to avoid introducing errors.

**Independent Test**: Click "Run Improve Pass" → See progress → View before/after comparison → Verify repetition reduced without new claims added.

**Acceptance Scenarios**:

1. **Given** a QA report with issues, **When** I click "Run Improve Pass", **Then** the system rewrites problematic sections
2. **Given** an editor pass in progress, **When** it completes, **Then** I can see a before/after comparison
3. **Given** a completed editor pass, **When** I run QA again, **Then** the repetition score improves
4. **Given** a completed editor pass, **When** I compare to original, **Then** no new factual claims have been added
5. **Given** an editor pass, **When** it runs, **Then** markdown structure (headings, lists, code blocks) is preserved

---

### User Story 4 - Regression Suite (Priority: P2)

As a developer, I want a regression suite with golden projects that can regenerate drafts, compute QA scores, and compare against baselines, so we can measure quality improvements over time and catch regressions.

**Why this priority**: This enables systematic improvement tracking. P2 because it's primarily a development/CI tool, not end-user facing.

**Independent Test**: Run regression suite in CI → See score comparison table → Flag if any project regresses below baseline.

**Acceptance Scenarios**:

1. **Given** a list of golden project IDs, **When** I run the regression suite, **Then** each project gets a QA report
2. **Given** baseline scores for golden projects, **When** current scores are computed, **Then** I see a comparison table
3. **Given** a project with score below baseline threshold, **When** the suite runs, **Then** it flags a regression warning
4. **Given** the regression suite, **When** run in CI environment, **Then** it completes without requiring manual intervention

---

### Edge Cases

- What happens when draft is empty or very short? → QA report shows "insufficient content" warning with info severity
- What happens when source transcript is missing? → Faithfulness check is skipped, note added to report
- What happens when editor pass times out? → Original draft preserved, user notified, can retry
- What happens when QA analysis fails? → Graceful degradation, draft still usable, error logged
- What happens when LLM is unavailable? → Fallback to regex-only structural analysis with reduced rubric

## 3. Requirements

### Functional Requirements

**QA Report Generation**
- **FR-001**: System MUST generate a QA report for every completed draft
- **FR-002**: System MUST compute an overall quality score from 1-100
- **FR-003**: System MUST identify issues with severity levels: critical, warning, info
- **FR-004**: System MUST provide chapter/heading location for each issue
- **FR-005**: System MUST compute rubric scores for: structure, clarity, faithfulness, repetition, completeness

**Issue Detection**
- **FR-006**: System MUST detect repeated phrases/sentences across chapters (3+ word sequences appearing 3+ times)
- **FR-007**: System MUST detect structural issues: improper heading hierarchy, unbalanced chapters (>3x length variance), paragraphs over 300 words
- **FR-008**: System MUST detect potential hallucinations by comparing claims against source transcript/resources
- **FR-009**: System MUST detect clarity issues: sentences over 50 words, excessive passive voice (>30% of sentences)

**UI Display**
- **FR-010**: System MUST display QA summary badge in Tab3 showing issue count
- **FR-011**: System MUST provide expandable issue list grouped by severity
- **FR-012**: System MUST show issue details: severity icon, location, message, and suggested action

**Editor Pass (P2)**
- **FR-013**: System MUST provide optional "Run Improve Pass" button when issues exist
- **FR-014**: System MUST rewrite text without adding new factual claims not in source
- **FR-015**: System MUST preserve markdown structure (headings, lists, code blocks, links)
- **FR-016**: System MUST limit to single improvement pass per user action
- **FR-017**: System MUST show diff/comparison between original and improved versions

**Regression Suite (P2)**
- **FR-018**: System MUST store golden project IDs and baseline scores in fixture file
- **FR-019**: System MUST compute QA scores for golden projects on demand
- **FR-020**: System MUST compare current scores against stored baselines with 5% tolerance
- **FR-021**: System MUST output pass/fail status suitable for CI integration

### Key Entities

- **QAReport**: Overall score, rubric scores, issue list, metadata (project_id, generated_at, draft_hash)
- **QAIssue**: Severity (critical/warning/info), issue_type, chapter_index, heading, message, suggestion
- **RubricScores**: Structure (1-100), clarity (1-100), faithfulness (1-100), repetition (1-100), completeness (1-100)
- **GoldenProject**: Project ID, name, baseline scores, expected issue ranges, last_validated timestamp
- **EditorPassResult**: Original draft hash, improved draft, changes summary, faithfulness_preserved flag

## 4. Success Criteria

### Measurable Outcomes

- **SC-001**: QA report generated within 30 seconds of draft completion for drafts under 50,000 words
- **SC-002**: Users can view QA summary without navigating away from their current tab
- **SC-003**: Editor pass reduces repetition issue count by at least 50% on test fixtures
- **SC-004**: Editor pass maintains or improves faithfulness score (no decrease)
- **SC-005**: Regression suite processes 5 golden projects in under 10 minutes
- **SC-006**: 90% of detected issues include actionable improvement suggestions

## 5. Assumptions

- Existing LLM abstraction (OpenAI primary, Anthropic fallback) is sufficient for QA analysis
- Source transcript and resources are available in project data for faithfulness comparison
- Users prefer inline panel display over modal dialogs for QA workflow
- Single-pass editor improvement is sufficient; recursive passes would risk content drift
- Regex-based structural analysis can catch 60%+ of issues without LLM calls
- 3-5 golden projects are sufficient to detect quality regressions

## 6. Dependencies

- Existing draft generation pipeline (Spec 004)
- Existing LLM client with retry/fallback logic
- Project data model with transcript, resources, and draftText fields
- Tab3 UI components for panel integration

## 7. Out of Scope

- Real-time quality feedback during draft generation
- User-customizable QA rubrics or thresholds
- Multi-language quality analysis
- Plagiarism detection against external sources
- SEO optimization scoring
- Reading level analysis (Flesch-Kincaid, etc.)
- Grammar/spelling checking (defer to user's tools)

## 8. Future Work (Explicitly Deferred)

- **Post-MVP**: Custom rubric weights per webinar type
- **Post-MVP**: Quality trend dashboards across all projects
- **Post-MVP**: A/B testing framework for prompt improvements
- **Post-MVP**: Human-in-the-loop approval for editor pass suggestions
- **Post-MVP**: Integration with external writing quality APIs
- **Post-MVP**: Automated prompt tuning based on regression results
