# Spec 004 — Tab 3 AI Draft

**Feature ID**: `004-tab3-ai-draft`
**Status**: Draft
**Depends On**:
- `001-frontend-shell` (Tab 3 UI: Style config, Draft editor)
- `002-backend-foundation` (Project persistence)
- `003-tab1-ai-assist` (LLM abstraction layer, Clean transcript, Outline, Resources)

---

## 0. Summary

Add the core product capability: generate an **editable ebook draft** in **Tab 3** from the user's prepared inputs (clean transcript + outline + resources + style config). The user can preview and apply generated content, regenerate specific chapters/sections, and see AI-generated **visual suggestions** as metadata (no hard placements yet).

---

## 1. Goals

### 1.1 Primary Goal (Core Value) — P1
- **Generate Draft (Markdown)** in Tab 3 using:
  - Clean transcript (from Tab 1)
  - Outline (from Tab 1)
  - Optional resources (from Tab 1)
  - Style configuration (Tab 3)
- Draft is written into the existing Tab 3 editor for human editing.

### 1.2 Editing Workflow Goals — P1/P2
- **Preview-before-apply** for full draft generation (P1)
- **Regenerate** a selected chapter/section without regenerating the whole book (P2)
- **Progress indicator + cancel** for long-running operations (P1)

### 1.3 Secondary Goal (Prep for Tab 2) — P2
- Generate a list of **Visual Opportunities** (suggestions) alongside the draft, without committing to exact placements.

---

## 2. Non-Goals (for this spec)

- No AI image generation.
- No automatic screenshot extraction from video.
- No PDF/ePub export work (unless already present as placeholder).
- No Tab 2 "attach visual to opportunity" workflow yet (that will be Spec 005).
- No enforced pagination/layout rules.
- No undo/redo for draft editor (use browser native).

---

## 3. User Stories

### Priority Legend
- **P1** — Must have for this feature to be considered complete.
- **P2** — Nice to have if not too expensive.
- **P3** — Optional polish.

---

### US1 (P1) — Generate an Ebook Draft

> As a user, I want to click "Generate Draft" in Tab 3 and receive a complete markdown ebook draft based on my transcript and outline, so I can quickly get a first draft without writing from scratch.

**Acceptance Scenarios:**
1. **Given** user has transcript (≥500 chars) and outline (≥3 items), **When** they click "Generate Draft", **Then** system shows progress and generates a markdown draft
2. **Given** draft generation completes, **When** preview modal opens, **Then** user sees rendered markdown with word count and chapter list
3. **Given** user clicks "Apply" in preview, **Then** draft replaces editor content and is persisted
4. **Given** user clicks "Discard" in preview, **Then** modal closes with no changes to editor

---

### US2 (P2) — Regenerate a Chapter/Section

> As a user, I want to select a chapter and regenerate only that part, keeping my edits to other sections intact.

**Acceptance Scenarios:**
1. **Given** user has an applied draft in editor, **When** they select a chapter in outline panel and click "Regenerate", **Then** only that chapter is regenerated
2. **Given** user has manually edited the selected chapter, **When** they click "Regenerate", **Then** system warns "This will overwrite your edits to this section. Continue?"
3. **Given** regeneration completes, **When** user clicks "Apply", **Then** only the selected section is replaced; other content is unchanged

---

### US3 (P2) — Visual Suggestions (Metadata Only)

> As a user, I want to see suggested visuals that could improve the ebook, so I can plan what images to gather without the system inserting placeholders into my draft.

**Acceptance Scenarios:**
1. **Given** draft generation completes, **When** user views the project, **Then** visual opportunities are listed (separate panel or tab)
2. **Given** visual opportunities exist, **When** user views them, **Then** each shows: section reference, suggested type, description, priority
3. **Given** visual opportunities exist, **Then** no `[IMAGE]` or `VISUAL_SLOT` markers appear in the markdown

---

### US4 (P1) — Reliability and UX

> As a user, I want clear progress indication, the ability to cancel, and helpful error messages so I understand what's happening and can recover from failures.

**Acceptance Scenarios:**
1. **Given** generation is in progress, **When** user views UI, **Then** they see "Generating chapter 3 of 8: Pricing Strategy..." with progress bar
2. **Given** generation is in progress, **When** user clicks "Cancel", **Then** generation stops after current chapter and partial results are available
3. **Given** AI service returns an error, **When** error is displayed, **Then** message is user-friendly with "Retry" option
4. **Given** an AI action is in progress, **When** user tries to start another, **Then** button is disabled (one action at a time)

---

## 4. Inputs and Outputs

### 4.1 Inputs
| Field | Type | Required | Source |
|-------|------|----------|--------|
| `transcript` | string (≥500 chars) | Yes | Tab 1 |
| `outline` | OutlineItem[] (≥3 items) | Yes | Tab 1 |
| `resources` | Resource[] | No | Tab 1 |
| `style_config` | StyleConfig | Yes | Tab 3 |
| `existing_draft` | string | No | For regenerate flows |

### 4.2 Outputs
| Field | Type | Description |
|-------|------|-------------|
| `draft_markdown` | string | Full ebook draft in markdown |
| `draft_plan` | DraftPlan | Structured generation plan (internal) |
| `visual_opportunities` | VisualOpportunity[] | Suggested visuals |

### 4.3 Input Validation

- **FR-INPUT-01**: "Generate Draft" button MUST be disabled if transcript < 500 characters
- **FR-INPUT-02**: "Generate Draft" button MUST be disabled if outline has < 3 items
- **FR-INPUT-03**: If inputs are insufficient, tooltip MUST explain: "Add more content to transcript (min 500 chars) and outline (min 3 items)"
- **FR-INPUT-04**: System SHOULD warn if transcript > 50,000 characters: "Large transcript may take several minutes to process"

---

## 5. Generation Flow (Detailed)

### 5.1 Single-Step Flow (v1)

```
┌─────────────────────────────────────────────────────────────────┐
│  User clicks "Generate Draft"                                    │
└─────────────────┬───────────────────────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. Validate inputs (transcript ≥500, outline ≥3)               │
│     → If invalid: show error, stop                               │
└─────────────────┬───────────────────────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. Generate DraftPlan (internal, not shown to user)            │
│     - Map transcript segments to outline items                   │
│     - Generate visual opportunities                              │
│     - Estimate chapter lengths                                   │
└─────────────────┬───────────────────────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Generate chapters one-by-one                                 │
│     - Progress: "Generating chapter 3 of 8: Pricing Strategy..." │
│     - Each chapter uses mapped transcript segment                │
│     - Cancel stops after current chapter                         │
└─────────────────┬───────────────────────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. Show Preview Modal                                           │
│     - Rendered markdown (scrollable)                             │
│     - Word count + chapter count                                 │
│     - Actions: Apply | Copy | Discard                            │
└─────────────────┬───────────────────────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. On Apply: Replace editor content, persist to project         │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Progress UI Requirements

- **FR-PROG-01**: Progress indicator MUST show current chapter number and title: "Generating chapter 3 of 8: Pricing Strategy..."
- **FR-PROG-02**: Progress bar MUST reflect chapters completed (not time)
- **FR-PROG-03**: Cancel button MUST be visible during generation
- **FR-PROG-04**: Cancel MUST stop after current chapter completes (no partial chapters)
- **FR-PROG-05**: After cancel, partial results MUST be available in preview (chapters 1-N)

### 5.3 DraftPlan Visibility

- **FR-PLAN-01**: DraftPlan is stored but NOT shown in preview modal (too technical for most users)
- **FR-PLAN-02**: (P3) Advanced users MAY view DraftPlan via "Show generation details" expander

---

## 6. Regenerate Selection Mechanics

### 6.1 Selection Methods

- **FR-REGEN-01**: Primary method: User clicks a chapter/section in the **outline panel** → "Regenerate" button becomes active
- **FR-REGEN-02**: (P3) Secondary method: User places cursor in editor heading → system detects enclosing section

### 6.2 Context for Regeneration

When regenerating a section, the AI receives:
- The section's outline item (title, level, notes)
- Mapped transcript segment from original DraftPlan
- Surrounding context: previous section's last paragraph + next section's first paragraph (for continuity)
- Style config (unchanged)
- Instruction: "Regenerate this section to fit between the surrounding content"

### 6.3 Merge Behavior

- **FR-REGEN-03**: Regenerated content REPLACES from the section heading to the next heading of same or higher level
- **FR-REGEN-04**: Content outside the selected section MUST be preserved exactly
- **FR-REGEN-05**: If user has edited the selected section, show warning: "This will overwrite your edits to this section. Continue?" with "Regenerate" / "Cancel" options

---

## 7. Preview Modal Specification

### 7.1 Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Draft Preview                                    [X] Close      │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────────────────────────────────┐   │
│  │ Chapters    │  │                                         │   │
│  │             │  │   # My Ebook Title                      │   │
│  │ 1. Intro    │  │                                         │   │
│  │ 2. Setup    │  │   ## Chapter 1: Introduction            │   │
│  │ 3. Core  ←  │  │                                         │   │
│  │ 4. Mail     │  │   Lorem ipsum dolor sit amet...         │   │
│  │ 5. Tips     │  │                                         │   │
│  │             │  │   ### Key Concepts                      │   │
│  │ ─────────── │  │                                         │   │
│  │ 8 chapters  │  │   ...                                   │   │
│  │ 12,450 words│  │                                         │   │
│  └─────────────┘  └─────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│  [Apply to Editor]  [Copy to Clipboard]  [Discard]              │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 Features

- **FR-PREVIEW-01**: Left sidebar shows table of contents (clickable to scroll)
- **FR-PREVIEW-02**: Right panel shows rendered markdown (read-only, scrollable)
- **FR-PREVIEW-03**: Footer shows total word count and chapter count
- **FR-PREVIEW-04**: Each chapter in TOC shows individual word count

### 7.3 Apply Behavior

- **FR-PREVIEW-05**: If editor is empty → insert draft directly
- **FR-PREVIEW-06**: If editor has content → show confirmation dialog:
  - "Replace existing draft?"
  - Options: "Replace all" (primary) | "Cancel"
- **FR-PREVIEW-07**: After apply, draft is persisted via existing auto-save

---

## 8. Draft Plan (Structured Output)

### 8.1 Purpose

The DraftPlan reduces hallucinations and enables chunked generation:
- Confirms intended chapter list and scope before writing
- Maps transcript segments to chapters for focused generation
- Produces visual suggestions as separate metadata
- Enables regeneration of individual sections with correct context

### 8.2 DraftPlan Schema

```typescript
interface DraftPlan {
  version: 1;
  book_title: string;
  chapters: ChapterPlan[];
  visual_opportunities: VisualOpportunity[];
  generation_metadata: {
    estimated_total_words: number;
    estimated_generation_time_seconds: number;
    transcript_utilization: number; // 0.0-1.0, how much transcript is used
  };
}

interface ChapterPlan {
  chapter_number: number;
  title: string;
  outline_item_id: string; // Reference to source outline item
  goals: string[]; // 2-4 learning objectives
  key_points: string[]; // 3-6 main points to cover
  transcript_segments: TranscriptSegment[];
  estimated_words: number;
}

interface TranscriptSegment {
  start_char: number;
  end_char: number;
  relevance: "primary" | "supporting" | "reference";
}
```

### 8.3 Transcript-Outline Mapping

- **FR-PLAN-03**: During DraftPlan generation, AI MUST identify which transcript portions relate to each chapter
- **FR-PLAN-04**: Each chapter's `transcript_segments` MUST cover the relevant content
- **FR-PLAN-05**: Segments MAY overlap if content is relevant to multiple chapters
- **FR-PLAN-06**: If mapping fails or is ambiguous, system SHOULD send full transcript with chapter-focus instruction (fallback)

---

## 9. Visual Opportunities

### 9.1 Goal

Generate **visual suggestions** alongside the draft, without inserting placeholders. Tab 2 (Spec 005) will later allow users to attach actual images to these opportunities.

### 9.2 VisualOpportunity Schema

```typescript
interface VisualOpportunity {
  id: string; // UUID
  section_ref: string; // e.g., "Chapter 2 > Pricing Strategy > Tier Comparison"
  suggested_type: "screenshot" | "diagram" | "chart" | "table" | "photo" | "icon" | "other";
  prompt: string; // What it should depict (clear and specific)
  rationale?: string; // Why it helps the reader
  priority: "high" | "medium" | "low";
  constraints?: string[]; // e.g., ["client_assets_only"]

  // Reserved for Spec 005
  attached_visual_id: string | null;
  status: "suggested" | "attached" | "skipped";
}
```

### 9.3 VisualAsset Schema (Reserved for Spec 005)

```typescript
interface VisualAsset {
  id: string; // UUID
  kind: "custom" | "gallery";
  source: "client" | "internal" | "generated" | "stock" | "unknown";
  original_filename: string;
  mime_type: string; // e.g., "image/png"
  storage_url: string;
  thumb_url?: string;
  title?: string;
  caption?: string;
  alt_text?: string;
  credit?: string;
  license?: string;
  selected_for_export: boolean;
  created_at: string; // ISO datetime
  updated_at: string;
}
```

### 9.4 Visual Requirements (MVP)

- **FR-VIS-01**: DraftPlan MUST include `visual_opportunities[]` (may be empty for short content)
- **FR-VIS-02**: Visual opportunities are generated during DraftPlan phase (available even if generation is cancelled)
- **FR-VIS-03**: Do NOT insert `[IMAGE]`, `VISUAL_SLOT_01`, or similar markers in markdown
- **FR-VIS-04**: Persist `visual_opportunities` in project state for Tab 2
- **FR-VIS-05**: Initialize `visual_assets: []` in project if not present

---

## 10. Style Config

### 10.1 Purpose

Style config tells the model what kind of ebook to write. It shapes tone, structure, depth, and visual suggestions.

### 10.2 StyleConfig Schema

```typescript
interface StyleConfig {
  // Book structure
  book_format: "playbook" | "handbook" | "tutorial" | "guide" | "ebook_marketing" | "executive_brief" | "course_notes" | "interview_qa";
  chapter_count_target: number; // 3-20

  // Writing style
  tone: "friendly" | "professional" | "authoritative" | "conversational" | "academic";
  target_audience: "beginners" | "intermediate" | "advanced" | "mixed";
  reader_role: "founder" | "marketer" | "sales" | "product" | "engineer" | "hr" | "finance" | "educator" | "general";

  // Content policy
  faithfulness_level: "strict" | "balanced" | "creative";
  // strict: Only information explicitly in transcript
  // balanced: Transcript + reasonable inferences
  // creative: May add examples and elaboration

  source_policy: "transcript_only" | "transcript_plus_provided_resources";

  // Visuals
  visual_density: "none" | "light" | "medium" | "heavy";
  // none: 0 suggestions, light: 1-3, medium: 4-8, heavy: 9+
  visual_source_policy: "client_assets_only" | "allow_new_suggestions";

  // Output
  output_format: "markdown"; // Only markdown for v1
}
```

### 10.3 Default Values

```json
{
  "book_format": "guide",
  "chapter_count_target": 8,
  "tone": "professional",
  "target_audience": "mixed",
  "reader_role": "general",
  "faithfulness_level": "balanced",
  "source_policy": "transcript_only",
  "visual_density": "medium",
  "visual_source_policy": "client_assets_only",
  "output_format": "markdown"
}
```

### 10.4 Presets

| Preset Name | Format | Tone | Audience | Chapters | Visual Density |
|-------------|--------|------|----------|----------|----------------|
| Default Webinar Ebook | guide | professional | mixed | 8 | medium |
| SaaS Marketing Ebook | ebook_marketing | friendly | beginners | 6 | heavy |
| Training Handbook | handbook | conversational | mixed | 10 | medium |
| Executive Brief | executive_brief | authoritative | advanced | 4 | light |
| Course Notes | course_notes | academic | intermediate | 12 | light |
| Interview Q&A | interview_qa | conversational | mixed | - | light |

#### 10.4.1 Interview Q&A Format Details

The `interview_qa` format is designed for interview transcripts where the goal is to preserve the conversational Q&A structure rather than transform content into traditional chapters.

**Characteristics:**
- Uses questions from the interview as section headers
- Preserves the speaker's voice and direct quotes
- Groups related Q&A exchanges into thematic sections
- Does NOT add artificial "Key Takeaways", "Action Steps", or "Summary" sections
- Minimal editorial transformation - stays faithful to what was said
- Chapter count is determined by natural topic groupings, not a fixed target

**When to use:**
- Interviews with thought leaders, experts, or founders
- Philosophical or exploratory conversations
- Content where the speaker's exact words and perspective are the value
- When readers want to "hear" the interviewee, not a summary

**Automatic behaviors when `interview_qa` is selected:**
- `include_key_takeaways`: false
- `include_action_steps`: false
- `include_checklists`: false
- `faithfulness_level`: "strict"
- `content_mode`: "interview" (from Spec 009)

### 10.5 Validation Rules

- **FR-STYLE-01**: `chapter_count_target` MUST be 3-20
- **FR-STYLE-02**: If outline has N level-1 items and `chapter_count_target` > N, show warning: "Target chapters (X) exceeds outline chapters (Y). Some chapters may be split or expanded."
- **FR-STYLE-03**: Style config MUST be persisted with project

---

## 11. Markdown Output Structure

### 11.1 Standard Structure (Default)

```markdown
# {Book Title}

## Chapter 1: {Chapter Title}

{Chapter content with paragraphs, lists, etc.}

### {Section Title}

{Section content}

## Chapter 2: {Chapter Title}

...
```

### 11.2 Interview Q&A Structure

When `book_format: "interview_qa"` is selected, use this structure:

```markdown
# {Book Title}: A Conversation with {Speaker Name}

## Introduction

{Brief context: who the speaker is, what the conversation covers, when/where it took place}

## {Topic/Theme 1}

### {Question from interviewer}

{Speaker's response - preserving their voice, using direct quotes where impactful}

> "{Particularly notable quote}" — {Speaker Name}

### {Follow-up question}

{Speaker's response}

## {Topic/Theme 2}

### {Question}

{Response}

...

## Closing Thoughts

### {Final question or wrap-up}

{Speaker's closing remarks}
```

**Key differences from standard structure:**
- Questions become `###` section headers (not invented section titles)
- Responses preserve the speaker's voice and phrasing
- Blockquotes (`>`) highlight particularly notable quotes
- Topics/themes are `##` headers that group related Q&A
- No "Key Takeaways" or "Action Steps" sections
- Introduction provides context, not a summary
- Closing captures the speaker's own wrap-up, not an editorial conclusion

### 11.3 Formatting Rules

- **FR-MD-01**: Book title MUST be `# ` (h1)
- **FR-MD-02**: Chapters MUST be `## ` (h2)
- **FR-MD-03**: Sections within chapters MUST be `### ` (h3)
- **FR-MD-04**: Subsections MAY be `#### ` (h4)
- **FR-MD-05**: No deeper than h4 (avoid h5, h6)
- **FR-MD-06**: Use standard markdown: `**bold**`, `*italic*`, `- lists`, `1. numbered`, `> blockquotes`, `` `code` ``

---

## 12. Error Handling

### 12.1 Error Categories

| Error Type | User Message | Action |
|------------|--------------|--------|
| Input validation | "Add more content to transcript (min 500 chars)" | Disable button |
| Rate limit (429) | "AI service is busy. Retrying in X seconds..." | Auto-retry with backoff |
| Provider error (5xx) | "AI service temporarily unavailable. Please try again." | Show Retry button |
| Timeout | "Generation is taking longer than expected. Continue waiting or cancel?" | Continue / Cancel |
| Auth error (401/403) | "AI service configuration error. Please contact support." | No retry |
| Content blocked | "Content could not be processed. Try simplifying the transcript." | No auto-retry |
| Partial failure | "Generation stopped at chapter 4. You can apply partial results or retry." | Apply Partial / Retry / Cancel |

### 12.2 Error Handling Requirements

- **FR-ERR-01**: If DraftPlan generation fails, system MUST NOT proceed to chapter generation
- **FR-ERR-02**: If chapter generation fails mid-way, system MUST preserve successfully generated chapters
- **FR-ERR-03**: Partial results MUST be available in preview with clear indication of what's missing
- **FR-ERR-04**: Rate limit errors MUST show estimated wait time if available from provider
- **FR-ERR-05**: All errors MUST be logged with request_id for debugging
- **FR-ERR-06**: User content (transcript, outline) MUST never be lost due to AI errors

---

## 13. Backend / API Requirements

### 13.1 Endpoints

#### POST /api/ai/draft/generate

Generate a complete ebook draft.

**Request:**
```json
{
  "transcript": "string (≥500 chars)",
  "outline": [{ "id": "string", "title": "string", "level": 1, "notes": "string?" }],
  "resources": [{ "label": "string", "url_or_note": "string" }],
  "style_config": { StyleConfig }
}
```

**Response:**
```json
{
  "data": {
    "draft_markdown": "# My Ebook\n\n## Chapter 1...",
    "draft_plan": { DraftPlan },
    "visual_opportunities": [{ VisualOpportunity }],
    "generation_stats": {
      "chapters_generated": 8,
      "total_words": 12450,
      "generation_time_ms": 45000,
      "tokens_used": { "prompt": 15000, "completion": 20000 }
    }
  },
  "error": null
}
```

#### POST /api/ai/draft/regenerate

Regenerate a single section.

**Request:**
```json
{
  "section_outline_item_id": "string",
  "draft_plan": { DraftPlan },
  "existing_draft": "string (full markdown)",
  "style_config": { StyleConfig }
}
```

**Response:**
```json
{
  "data": {
    "section_markdown": "## Chapter 3: Pricing Strategy\n\n...",
    "section_start_line": 145,
    "section_end_line": 210
  },
  "error": null
}
```

### 13.2 Provider Policy

- Primary: OpenAI (gpt-4o or gpt-4o-mini for cost)
- Fallback: Anthropic (claude-3-5-sonnet)
- Fallback triggers: 429, 5xx, timeout, network errors
- No fallback on: 400 (invalid request), 401/403 (auth), content policy violations
- On invalid structured output: retry same provider once before fallback

### 13.3 Chunking Strategy

- **FR-API-01**: Generate DraftPlan in single request (structured output)
- **FR-API-02**: Generate each chapter as separate request using mapped transcript segments
- **FR-API-03**: Each chapter request SHOULD stay under 8,000 input tokens
- **FR-API-04**: Include previous chapter's last paragraph and next chapter's outline for continuity

---

## 14. Persistence

### 14.1 Project Fields (additions)

```typescript
interface Project {
  // ... existing fields from 001/002 ...

  // New fields for 004
  draft_markdown: string | null;
  draft_plan: DraftPlan | null;
  visual_opportunities: VisualOpportunity[];
  visual_assets: VisualAsset[]; // Empty for 004, populated in 005
  style_config: {
    version: number;
    preset_id: string | null;
    config: StyleConfig;
  };
}
```

### 14.2 Persistence Rules

- **FR-PERSIST-01**: `draft_markdown` MUST be persisted when user clicks "Apply"
- **FR-PERSIST-02**: `draft_plan` MUST be persisted alongside draft for regeneration
- **FR-PERSIST-03**: `visual_opportunities` MUST be persisted for Tab 2
- **FR-PERSIST-04**: `style_config` MUST be persisted and restored when project is opened
- **FR-PERSIST-05**: Existing project fields MUST remain unchanged (backward compatible)

---

## 15. Non-Functional Requirements

- **NFR-001 (Performance)**: Full draft generation for 8-chapter book from 15,000-char transcript SHOULD complete within 3 minutes
- **NFR-002 (Chunk Size)**: Individual chapter requests SHOULD stay under 8,000 input tokens
- **NFR-003 (Resilience)**: Generation failure MUST NOT corrupt existing draft in editor
- **NFR-004 (Partial Results)**: Cancelled or failed generation MUST make completed chapters available
- **NFR-005 (Cost Tracking)**: System SHOULD log token usage per generation for monitoring
- **NFR-006 (Idempotency)**: Regenerating same section with same inputs SHOULD produce similar (not identical) output
- **NFR-007 (Accessibility)**: Progress indicator and buttons MUST be keyboard accessible with ARIA labels

---

## 16. Acceptance Scenarios

### AS-001: Basic Generation (Happy Path)
**Given**: User has transcript (5,000 chars), outline (6 items), default style config
**When**: User clicks "Generate Draft"
**Then**:
- Progress shows "Generating chapter 1 of 6..."
- After ~60 seconds, preview modal opens
- Draft has 6 chapters with content derived from transcript
- Word count shown (e.g., "8,234 words")
- "Apply" replaces editor content

### AS-002: Cancel Mid-Generation
**Given**: Generation is in progress at chapter 4 of 8
**When**: User clicks "Cancel"
**Then**:
- Generation stops after chapter 4 completes
- Preview shows chapters 1-4 with note "Generation cancelled. 4 of 8 chapters available."
- User can "Apply partial draft" or "Discard"

### AS-003: Regenerate After Edits
**Given**: User has applied draft and manually edited Chapter 3
**When**: User selects Chapter 3 in outline and clicks "Regenerate"
**Then**:
- Warning: "This will overwrite your edits to Chapter 3. Continue?"
- On confirm: Only Chapter 3 is regenerated
- Chapters 1, 2, 4+ remain exactly as before

### AS-004: Insufficient Inputs
**Given**: Transcript has 200 characters (below 500 minimum)
**When**: User views Tab 3
**Then**:
- "Generate Draft" button is disabled
- Tooltip shows "Add more content to transcript (min 500 chars)"

### AS-005: Provider Fallback
**Given**: OpenAI returns 503 during chapter 5 generation
**When**: System detects error
**Then**:
- System automatically retries with Anthropic
- Generation continues seamlessly
- User sees brief "Retrying..." indicator
- Final draft includes all chapters

### AS-006: Large Transcript Warning
**Given**: Transcript has 60,000 characters
**When**: User clicks "Generate Draft"
**Then**:
- Warning shown: "Large transcript may take several minutes. Continue?"
- On confirm: Generation proceeds with extended timeout

### AS-007: Visual Opportunities
**Given**: Draft generation completes for 8-chapter book with visual_density="medium"
**When**: User views visual opportunities
**Then**:
- 4-8 visual opportunities are listed
- Each has section_ref, suggested_type, prompt, priority
- No image placeholders appear in markdown

### AS-008: Interview Q&A Format
**Given**: User has interview transcript with clear Q&A structure, selects `book_format: "interview_qa"`
**When**: User clicks "Generate Draft"
**Then**:
- Draft uses questions as section headers (### level)
- Topics are grouped under thematic ## headers
- Speaker's voice is preserved with direct quotes
- Blockquotes highlight notable statements
- NO "Key Takeaways" or "Action Steps" sections appear
- NO invented biography or background for the speaker
- Content stays faithful to what was actually said

### AS-009: Interview Q&A Auto-Configuration
**Given**: User selects `book_format: "interview_qa"` in style config
**When**: Generation begins
**Then**:
- `include_key_takeaways` is automatically set to false
- `include_action_steps` is automatically set to false
- `faithfulness_level` is automatically set to "strict"
- `content_mode` is automatically set to "interview"
- User cannot override these settings while interview_qa is selected

---

## 17. Open Questions

- **OQ-001**: Should "Apply" offer "Append to end" option, or only "Replace"?
  - *Recommendation*: Replace only for v1; append adds complexity

- **OQ-002**: Should visual opportunities be user-editable (add/remove/edit) in Tab 3?
  - *Recommendation*: Read-only in Tab 3; editing in Tab 2 (Spec 005)

- **OQ-003**: Should regenerate preserve original transcript mapping or re-analyze?
  - *Recommendation*: Preserve original mapping for consistency

- **OQ-004**: Should we show estimated cost before generation?
  - *Recommendation*: P3 for v1; log costs internally first

---

## 18. Future Work (Spec 005+)

### Spec 005 — Tab 2 Visuals
- Upload client-provided visuals (PNG/JPG/WebP)
- Caption / alt text / credit fields
- Attach VisualAsset to VisualOpportunity
- "Selected for export" behavior

### Later
- Export formats (PDF/ePub with visuals)
- Video → transcript pipeline
- AI-assisted visual generation
- Collaborative editing
- Version history for drafts