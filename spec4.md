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

**Canonical schema** (from `backend/src/models/draft_plan.py`):
**JSON Schema**: [`specs/004-tab3-ai-draft/schemas/DraftPlan.json`](./specs/004-tab3-ai-draft/schemas/DraftPlan.json)

```typescript
interface DraftPlan {
  version: number;                         // Schema version (default: 1)
  book_title: string;                      // Title of the generated ebook
  chapters: ChapterPlan[];                 // Planned chapters
  visual_plan: VisualPlan;                 // Visual opportunities (default: empty)
  generation_metadata: GenerationMetadata; // Metadata about the plan
}

interface ChapterPlan {
  chapter_number: number;                  // 1-based chapter number
  title: string;                           // Chapter title
  outline_item_id: string;                 // Reference to source outline item
  goals: string[];                         // 2-4 learning objectives
  key_points: string[];                    // 3-6 main points to cover
  transcript_segments: TranscriptSegment[]; // Mapped transcript portions
  estimated_words: number;                 // Estimated word count (default: 1500)
}

interface TranscriptSegment {
  start_char: number;                      // Starting character index (>= 0)
  end_char: number;                        // Ending character index (>= 0)
  relevance: "primary" | "supporting" | "reference"; // Segment relevance
}

interface GenerationMetadata {
  estimated_total_words: number;           // Total estimated word count
  estimated_generation_time_seconds: number; // Estimated generation time
  transcript_utilization: number;          // Fraction of transcript used (0.0-1.0)
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

**Canonical schema** (from `backend/src/models/visuals.py`):
**JSON Schema**: [`specs/004-tab3-ai-draft/schemas/VisualOpportunity.json`](./specs/004-tab3-ai-draft/schemas/VisualOpportunity.json)

```typescript
// Enums
type VisualType = "screenshot" | "diagram" | "chart" | "table" | "icon" | "photo" | "other";
type VisualSourcePolicy = "client_assets_only" | "allow_new_suggestions";
type VisualPlacement = "after_heading" | "inline" | "end_of_section" | "end_of_chapter" | "sidebar";

interface VisualOpportunity {
  id: string;                              // Stable UUID for UI selection
  chapter_index: number;                   // 1-based chapter index
  section_path: string | null;             // Optional: "2.3" or heading slug
  placement: VisualPlacement;              // Default: "after_heading"

  visual_type: VisualType;                 // What kind of visual
  source_policy: VisualSourcePolicy;       // Default: "client_assets_only"

  title: string;                           // Short title (figure label)
  prompt: string;                          // What visual should show (LLM description)
  caption: string;                         // Caption text under visual

  required: boolean;                       // Default: false
  candidate_asset_ids: string[];           // Known assets that fit (default: [])

  confidence: number;                      // 0.0-1.0, default: 0.6
  rationale: string | null;                // Why this helps the reader
}
```

**Note**: No `attached_visual_id` or `status` fields — attachment happens in Tab 2 (Spec 005) via `VisualPlan.assets`.

### 9.3 VisualAsset Schema

**Canonical schema** (from `backend/src/models/visuals.py`):
**JSON Schema**: [`specs/004-tab3-ai-draft/schemas/VisualAsset.json`](./specs/004-tab3-ai-draft/schemas/VisualAsset.json)

```typescript
type VisualAssetOrigin = "client_provided" | "user_uploaded" | "generated" | "external_link";

interface VisualAsset {
  id: string;                     // Stable UUID for referencing
  filename: string;               // Original filename (or derived name)
  media_type: string;             // MIME type, e.g. "image/png"
  origin: VisualAssetOrigin;      // Default: "client_provided"

  // Storage (exactly one typically present)
  source_url: string | null;      // External link if applicable
  storage_key: string | null;     // Internal storage path if stored by app

  // Dimensions (optional)
  width: number | null;           // >= 1
  height: number | null;          // >= 1

  alt_text: string | null;        // Accessibility / SEO
  tags: string[];                 // Default: []
}
```

### 9.4 VisualPlan Schema

**Canonical schema** (from `backend/src/models/visuals.py`):
**JSON Schema**: [`specs/004-tab3-ai-draft/schemas/VisualPlan.json`](./specs/004-tab3-ai-draft/schemas/VisualPlan.json)

```typescript
interface VisualPlan {
  opportunities: VisualOpportunity[];  // Default: []
  assets: VisualAsset[];               // Default: []
}
```

The `VisualPlan` is the top-level container persisted in the project. Tab 3 populates `opportunities`; Tab 2 (Spec 005) attaches `assets`.

### 9.5 Visual Requirements (MVP)

- **FR-VIS-01**: DraftPlan MUST produce a `VisualPlan` with `opportunities[]` (may be empty for short content)
- **FR-VIS-02**: Visual opportunities are generated during DraftPlan phase (available even if generation is cancelled)
- **FR-VIS-03**: Do NOT insert `[IMAGE]`, `VISUAL_SLOT_01`, or similar markers in markdown — visuals are metadata only
- **FR-VIS-04**: Persist `VisualPlan` in project state for Tab 2
- **FR-VIS-05**: Initialize `VisualPlan(opportunities=[], assets=[])` in project if not present

---

## 10. Style Config

### 10.1 Purpose

Style config tells the model what kind of ebook to write. It shapes tone, structure, depth, and visual suggestions.

### 10.2 StyleConfigEnvelope Schema

**Canonical schema** (from `backend/src/models/style_config.py`):
**JSON Schema**: [`specs/004-tab3-ai-draft/schemas/StyleConfigEnvelope.json`](./specs/004-tab3-ai-draft/schemas/StyleConfigEnvelope.json)

The style config is wrapped in an envelope for versioning and preset tracking:

```typescript
interface StyleConfigEnvelope {
  version: number;           // Current: 1, for migrations
  preset_id: string;         // e.g., "default_webinar_ebook_v1"
  style: StyleConfig;        // The actual configuration
}
```

### 10.3 StyleConfig Schema

The comprehensive `StyleConfig` includes ~35 fields across several categories. Key fields shown below (see `backend/src/models/style_config.py` for full schema):

```typescript
interface StyleConfig {
  // Audience & Goal
  target_audience: "beginners" | "intermediate" | "experts" | "mixed";
  reader_role: "founder" | "marketer" | "sales" | "product" | "engineer" | "hr" | "finance" | "educator" | "general";
  primary_goal: "inform" | "teach" | "persuade" | "enable_action";
  reader_takeaway_style: "principles" | "how_to_steps" | "analysis" | "reference";

  // Tone & Voice
  tone: "friendly" | "professional" | "authoritative" | "conversational" | "academic";
  formality: "low" | "medium" | "high";
  brand_voice: "neutral" | "casual" | "premium" | "technical";
  perspective: "you" | "we" | "third_person";
  reading_level: "simple" | "standard" | "advanced";

  // Book Structure
  book_format: "guide" | "tutorial" | "handbook" | "playbook" | "ebook_marketing" | "executive_brief" | "course_notes" | "whitepaper";
  chapter_count_target: number;              // 3-20
  chapter_length_target: "short" | "medium" | "long";

  // Content Inclusions
  include_summary_per_chapter: boolean;
  include_key_takeaways: boolean;
  include_action_steps: boolean;
  include_checklists: boolean;
  include_templates: boolean;
  include_examples: boolean;

  // Source Fidelity
  faithfulness_level: "strict" | "balanced" | "creative";
  allowed_extrapolation: "none" | "light" | "moderate";
  source_policy: "transcript_only" | "transcript_plus_provided_resources";
  citation_style: "none" | "inline_links" | "footnotes_light" | "academic";
  avoid_hallucinations: boolean;

  // Visuals
  visual_density: "none" | "light" | "medium" | "heavy";
  preferred_visual_types: VisualType[];      // e.g., ["diagram", "table", "screenshot"]
  visual_source_policy: "client_assets_only" | "allow_new_suggestions";
  caption_style: "short" | "explanatory" | "instructional";
  diagram_style: "simple" | "detailed" | "technical";

  // Transcript Handling
  resolve_repetitions: "keep" | "reduce" | "consolidate";
  handle_q_and_a: "omit" | "append_as_faq" | "weave_into_chapters";
  include_speaker_quotes: "never" | "sparingly" | "freely";

  // Output
  output_format: "markdown";                 // Only markdown for v1
  heading_style: "numbered" | "plain";
  callout_blocks: "none" | "tips_only" | "tips_and_warnings";
  table_preference: "avoid" | "when_helpful" | "prefer";
}
```

### 10.4 Presets

**Canonical presets** (from `frontend/src/constants/stylePresets.ts`):

| Preset ID | Label | Description |
|-----------|-------|-------------|
| `default_webinar_ebook_v1` | Default webinar ebook | Balanced, readable, action-oriented. Light visuals. |
| `saas_marketing_ebook_v1` | SaaS marketing ebook | Persuasive narrative with checklists/templates. Medium visuals. |
| `training_tutorial_handbook_v1` | Training / tutorial handbook | Step-by-step learning. Heavy screenshots/diagrams. Very strict. |
| `executive_brief_v1` | Executive brief | Short, punchy, high signal. Minimal fluff. Light citations. |
| `course_notes_v1` | Course notes | Structured learning notes: summaries + takeaways + practice steps. |

### 10.5 Validation Rules

- **FR-STYLE-01**: `chapter_count_target` MUST be 3-20
- **FR-STYLE-02**: If outline has N level-1 items and `chapter_count_target` > N, show warning: "Target chapters (X) exceeds outline chapters (Y). Some chapters may be split or expanded."
- **FR-STYLE-03**: `StyleConfigEnvelope` MUST be persisted with project
- **FR-STYLE-04**: Extra fields are forbidden (Pydantic `extra="forbid"`) to prevent schema drift

---

## 11. Markdown Output Structure

### 11.1 Required Structure

```markdown
# {Book Title}

## Chapter 1: {Chapter Title}

{Chapter content with paragraphs, lists, etc.}

### {Section Title}

{Section content}

## Chapter 2: {Chapter Title}

...
```

### 11.2 Formatting Rules

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

### 13.1 Endpoints (Async Job Pattern)

Draft generation uses an async job pattern for long-running operations:
1. Client submits request → receives `job_id`
2. Client polls status endpoint for progress
3. Client can cancel mid-generation
4. Completed results include partial drafts if cancelled

**All responses use the standard `{ data, error }` envelope pattern.**

**JSON Schemas**: See [`specs/004-tab3-ai-draft/schemas/`](./specs/004-tab3-ai-draft/schemas/) for all request/response schemas.

**LLM Schemas**: Two self-contained schemas are maintained:
- [`draft_plan.internal.schema.json`](./specs/004-tab3-ai-draft/schemas/draft_plan.internal.schema.json) - Internal schema (tests, docs, Anthropic)
- [`draft_plan.openai.strict.schema.json`](./specs/004-tab3-ai-draft/schemas/draft_plan.openai.strict.schema.json) - OpenAI strict mode (production)

#### POST /api/ai/draft/generate

Start draft generation (returns immediately with job_id).

**Request**: [`DraftGenerateRequest.json`](./specs/004-tab3-ai-draft/schemas/DraftGenerateRequest.json)
```json
{
  "transcript": "string (≥500 chars)",
  "outline": [{ "id": "string", "title": "string", "level": 1, "notes": "string?" }],
  "resources": [{ "label": "string", "url_or_note": "string" }],
  "style_config": { StyleConfigEnvelope }
}
```

**Response**: [`DraftGenerateResponse.json`](./specs/004-tab3-ai-draft/schemas/DraftGenerateResponse.json)
```json
{
  "data": {
    "job_id": "job-uuid-123",
    "status": "queued",
    "progress": null,
    "draft_markdown": null,
    "draft_plan": null,
    "visual_plan": null,
    "generation_stats": null
  },
  "error": null
}
```

#### GET /api/ai/draft/status/:job_id

Poll generation progress.

**Response**: [`DraftStatusResponse.json`](./specs/004-tab3-ai-draft/schemas/DraftStatusResponse.json)

**Status: generating**
```json
{
  "data": {
    "job_id": "job-uuid-123",
    "status": "generating",
    "progress": {
      "current_chapter": 3,
      "total_chapters": 8,
      "current_chapter_title": "Pricing Strategy",
      "chapters_completed": 2,
      "estimated_remaining_seconds": 90
    },
    "draft_markdown": null,
    "draft_plan": null,
    "visual_plan": null,
    "generation_stats": null,
    "partial_draft_markdown": null,
    "chapters_available": null
  },
  "error": null
}
```

**Status: completed**
```json
{
  "data": {
    "job_id": "job-uuid-123",
    "status": "completed",
    "progress": null,
    "draft_markdown": "# My Ebook\n\n## Chapter 1...",
    "draft_plan": {
      "version": 1,
      "book_title": "My Ebook",
      "chapters": [...],
      "visual_plan": { "opportunities": [...], "assets": [] },
      "generation_metadata": {
        "estimated_total_words": 12000,
        "estimated_generation_time_seconds": 120,
        "transcript_utilization": 0.85
      }
    },
    "visual_plan": {
      "opportunities": [
        {
          "id": "vo-uuid-1",
          "chapter_index": 2,
          "section_path": "2.1",
          "placement": "after_heading",
          "visual_type": "diagram",
          "source_policy": "client_assets_only",
          "title": "System Architecture",
          "prompt": "A diagram showing the overall system architecture",
          "caption": "Figure 2.1: System Architecture Overview",
          "required": false,
          "candidate_asset_ids": [],
          "confidence": 0.8,
          "rationale": "Helps readers visualize the system structure"
        }
      ],
      "assets": []
    },
    "generation_stats": {
      "chapters_generated": 8,
      "total_words": 12450,
      "generation_time_ms": 45000,
      "tokens_used": { "prompt_tokens": 15000, "completion_tokens": 20000, "total_tokens": 35000 }
    },
    "partial_draft_markdown": null,
    "chapters_available": null
  },
  "error": null
}
```

**Status: failed**
```json
{
  "data": null,
  "error": {
    "code": "GENERATION_FAILED",
    "message": "AI service temporarily unavailable. Please try again."
  }
}
```

#### POST /api/ai/draft/cancel/:job_id

Cancel generation (stops after current chapter completes).

**Response**: [`DraftCancelResponse.json`](./specs/004-tab3-ai-draft/schemas/DraftCancelResponse.json)
```json
{
  "data": {
    "job_id": "job-uuid-123",
    "status": "cancelled",
    "cancelled": true,
    "message": "Generation cancelled after chapter 4 of 8",
    "partial_draft_markdown": "# My Ebook\n\n## Chapter 1...",
    "chapters_available": 4
  },
  "error": null
}
```

#### POST /api/ai/draft/regenerate

Regenerate a single section (synchronous, typically fast).

**Request**: [`DraftRegenerateRequest.json`](./specs/004-tab3-ai-draft/schemas/DraftRegenerateRequest.json)
```json
{
  "section_outline_item_id": "string",
  "draft_plan": { DraftPlan },
  "existing_draft": "string (full markdown)",
  "style_config": { StyleConfigEnvelope }
}
```

**Response**: [`DraftRegenerateResponse.json`](./specs/004-tab3-ai-draft/schemas/DraftRegenerateResponse.json)
```json
{
  "data": {
    "section_markdown": "## Chapter 3: Pricing Strategy\n\n...",
    "section_start_line": 145,
    "section_end_line": 210,
    "generation_stats": {
      "chapters_generated": 1,
      "total_words": 1500,
      "generation_time_ms": 8000,
      "tokens_used": { "prompt_tokens": 3000, "completion_tokens": 2000, "total_tokens": 5000 }
    }
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

**Canonical schema** (from `backend/src/models/project.py`):

```typescript
interface Project {
  // ... existing fields from 001/002 ...

  // New fields for 004
  draftText: string;                                    // Full markdown draft (was draft_markdown)
  draftPlan: DraftPlan | null;                          // Internal generation plan
  visualPlan: VisualPlan | null;                        // Contains opportunities[] and assets[]
  styleConfig: StyleConfigEnvelope | LegacyStyleConfig | null;  // Wrapped style config
}
```

**Note on backward compatibility**: The `styleConfig` field accepts both `StyleConfigEnvelope` (new canonical) and `LegacyStyleConfig` (old simple format). On load, legacy formats MUST be normalized to `StyleConfigEnvelope`. See Section 14.3.

### 14.2 Persistence Rules

- **FR-PERSIST-01**: `draftText` MUST be persisted when user clicks "Apply"
- **FR-PERSIST-02**: `draftPlan` MUST be persisted alongside draft for regeneration
- **FR-PERSIST-03**: `visualPlan` MUST be persisted for Tab 2 (contains both opportunities and assets)
- **FR-PERSIST-04**: `styleConfig` MUST be persisted as `StyleConfigEnvelope` (canonical format only)
- **FR-PERSIST-05**: Existing project fields MUST remain unchanged (backward compatible)

### 14.3 Normalization on Load

When loading a project from persistence:

- **FR-NORM-01**: If `styleConfig` is null/missing → initialize with default `StyleConfigEnvelope`
- **FR-NORM-02**: If `styleConfig` is `LegacyStyleConfig` (old format) → migrate to `StyleConfigEnvelope(version=1, preset_id="legacy", style=...)`
- **FR-NORM-03**: If `visualPlan` is null/missing → initialize with `VisualPlan(opportunities=[], assets=[])`
- **FR-NORM-04**: On save, always persist the canonical shapes only (no legacy formats)

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
- 4-8 visual opportunities are listed in `visualPlan.opportunities`
- Each has: `chapter_index`, `visual_type`, `title`, `prompt`, `caption`, `confidence`
- No image placeholders appear in markdown (visuals are metadata only)

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
.