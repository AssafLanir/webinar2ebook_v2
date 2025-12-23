# Data Model: Tab 3 AI Draft Generation

**Feature**: 004-tab3-ai-draft
**Date**: 2025-12-17
**Source of Truth**: `backend/src/models/`

---

## Entity Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Project                                  │
│  (existing from 001/002)                                        │
├─────────────────────────────────────────────────────────────────┤
│  + draftText: string           # Markdown draft                  │
│  + draftPlan: DraftPlan?       # Generation plan                 │
│  + visualPlan: VisualPlan?     # Visual opportunities/assets    │
│  + styleConfig: StyleConfigEnvelope?  # Style settings          │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DraftPlan                                 │
├─────────────────────────────────────────────────────────────────┤
│  version: int                  # Schema version (1)              │
│  book_title: string                                              │
│  chapters: ChapterPlan[]                                         │
│  visual_plan: VisualPlan                                         │
│  generation_metadata: GenerationMetadata                         │
└─────────────────────────────────────────────────────────────────┘
         │
         ├──────────────────────┬──────────────────────┐
         ▼                      ▼                      ▼
┌─────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   ChapterPlan   │  │    VisualPlan       │  │ GenerationMetadata  │
├─────────────────┤  ├─────────────────────┤  ├─────────────────────┤
│ chapter_number  │  │ opportunities[]     │  │ estimated_total_words│
│ title           │  │ assets[]            │  │ estimated_gen_time   │
│ outline_item_id │  └─────────────────────┘  │ transcript_utilization│
│ goals[]         │           │               └─────────────────────┘
│ key_points[]    │           │
│ transcript_segs[]│          ▼
│ estimated_words │  ┌─────────────────────┐
└─────────────────┘  │ VisualOpportunity   │
         │           ├─────────────────────┤
         ▼           │ id                  │
┌─────────────────┐  │ chapter_index       │
│TranscriptSegment│  │ visual_type         │
├─────────────────┤  │ title, prompt       │
│ start_char      │  │ caption, confidence │
│ end_char        │  └─────────────────────┘
│ relevance       │
└─────────────────┘
```

---

## Core Entities

### DraftPlan

The complete generation plan for an ebook draft. Generated before chapters are written.

**Source**: `backend/src/models/draft_plan.py`
**JSON Schema**: `specs/004-tab3-ai-draft/schemas/DraftPlan.json`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | int | No (default: 1) | Schema version for migrations |
| `book_title` | string | Yes | Title of the generated ebook |
| `chapters` | ChapterPlan[] | No (default: []) | Planned chapters with mappings |
| `visual_plan` | VisualPlan | No (default: empty) | Visual opportunities |
| `generation_metadata` | GenerationMetadata | Yes | Generation statistics |

**Validation**:
- `version` >= 1
- `book_title` non-empty

**State transitions**: Created during planning phase, referenced during chapter generation

---

### ChapterPlan

Plan for generating a single chapter.

**Source**: `backend/src/models/draft_plan.py`
**JSON Schema**: `specs/004-tab3-ai-draft/schemas/ChapterPlan.json`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `chapter_number` | int | Yes | 1-based chapter number |
| `title` | string | Yes | Chapter title |
| `outline_item_id` | string | Yes | Reference to source outline item |
| `goals` | string[] | No (default: []) | 2-4 learning objectives |
| `key_points` | string[] | No (default: []) | 3-6 main points to cover |
| `transcript_segments` | TranscriptSegment[] | No (default: []) | Mapped transcript portions |
| `estimated_words` | int | No (default: 1500) | Estimated word count |

**Validation**:
- `chapter_number` >= 1
- `estimated_words` >= 100

**Relationships**:
- References `OutlineItem` via `outline_item_id`
- Contains `TranscriptSegment[]` for content mapping

---

### TranscriptSegment

A mapped segment of the source transcript.

**Source**: `backend/src/models/draft_plan.py`
**JSON Schema**: `specs/004-tab3-ai-draft/schemas/TranscriptSegment.json`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `start_char` | int | Yes | Starting character index (0-based) |
| `end_char` | int | Yes | Ending character index (exclusive) |
| `relevance` | enum | No (default: "primary") | Segment relevance to chapter |

**Relevance enum**:
- `primary` - Main content for this chapter
- `supporting` - Additional context
- `reference` - Cited but not expanded

**Validation**:
- `start_char` >= 0
- `end_char` >= 0
- Typically `end_char` > `start_char`

---

### GenerationMetadata

Metadata about the generation plan.

**Source**: `backend/src/models/draft_plan.py`
**JSON Schema**: `specs/004-tab3-ai-draft/schemas/GenerationMetadata.json`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `estimated_total_words` | int | Yes | Total estimated word count |
| `estimated_generation_time_seconds` | int | Yes | Estimated generation time |
| `transcript_utilization` | float | Yes | Fraction of transcript used (0.0-1.0) |

**Validation**:
- All fields >= 0
- `transcript_utilization` in [0.0, 1.0]

---

## Visual Entities

### VisualPlan

Container for visual opportunities and assets.

**Source**: `backend/src/models/visuals.py`
**JSON Schema**: `specs/004-tab3-ai-draft/schemas/VisualPlan.json`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `opportunities` | VisualOpportunity[] | No (default: []) | AI-suggested visual placements |
| `assets` | VisualAsset[] | No (default: []) | Available image assets |

**Usage**:
- `opportunities` populated by Tab 3 (this spec)
- `assets` populated by Tab 2 (Spec 005)

---

### VisualOpportunity

A suggested visual placement in the ebook.

**Source**: `backend/src/models/visuals.py`
**JSON Schema**: `specs/004-tab3-ai-draft/schemas/VisualOpportunity.json`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Stable UUID for UI selection |
| `chapter_index` | int | Yes | 1-based chapter index |
| `section_path` | string? | No | Section identifier (e.g., "2.3") |
| `placement` | enum | No (default: "after_heading") | Where to place visual |
| `visual_type` | enum | Yes | Type of visual needed |
| `source_policy` | enum | No (default: "client_assets_only") | Where visual can come from |
| `title` | string | Yes | Short title (figure label) |
| `prompt` | string | Yes | Description for visual |
| `caption` | string | Yes | Caption text |
| `required` | bool | No (default: false) | Must include placeholder |
| `candidate_asset_ids` | string[] | No (default: []) | Matching assets |
| `confidence` | float | No (default: 0.6) | LLM confidence (0.0-1.0) |
| `rationale` | string? | No | Why this visual helps |

**Enums**:
- `VisualPlacement`: "after_heading", "inline", "end_of_section", "end_of_chapter", "sidebar"
- `VisualType`: "screenshot", "diagram", "chart", "table", "icon", "photo", "other"
- `VisualSourcePolicy`: "client_assets_only", "allow_new_suggestions"

**Validation**:
- `chapter_index` >= 1
- `confidence` in [0.0, 1.0]

---

### VisualAsset

An image or media asset for the ebook.

**Source**: `backend/src/models/visuals.py`
**JSON Schema**: `specs/004-tab3-ai-draft/schemas/VisualAsset.json`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Stable UUID |
| `filename` | string | Yes | Original filename |
| `media_type` | string | Yes | MIME type (e.g., "image/png") |
| `origin` | enum | No (default: "client_provided") | Asset source |
| `source_url` | string? | No | External URL if applicable |
| `storage_key` | string? | No | Internal storage path |
| `width` | int? | No | Image width in pixels |
| `height` | int? | No | Image height in pixels |
| `alt_text` | string? | No | Accessibility text |
| `tags` | string[] | No (default: []) | Categorization tags |

**Enums**:
- `VisualAssetOrigin`: "client_provided", "user_uploaded", "generated", "external_link"

**Note**: Asset attachment to opportunities happens in Tab 2 (Spec 005).

---

## Style Entities

### StyleConfigEnvelope

Versioned wrapper for style configuration.

**Source**: `backend/src/models/style_config.py`
**JSON Schema**: `specs/004-tab3-ai-draft/schemas/StyleConfigEnvelope.json`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | int | No (default: 1) | Schema version |
| `preset_id` | string | No (default: "default_webinar_ebook_v1") | Preset identifier |
| `style` | StyleConfig | No (default: defaults) | Configuration values |

**Presets available**:
- `default_webinar_ebook_v1`
- `saas_marketing_ebook_v1`
- `training_tutorial_handbook_v1`
- `executive_brief_v1`
- `course_notes_v1`

---

### StyleConfig

Comprehensive style configuration (~35 fields).

**Source**: `backend/src/models/style_config.py`
**JSON Schema**: `specs/004-tab3-ai-draft/schemas/StyleConfig.json`

**Key field categories**:

| Category | Fields |
|----------|--------|
| Audience | `target_audience`, `reader_role`, `primary_goal`, `reader_takeaway_style` |
| Tone | `tone`, `formality`, `brand_voice`, `perspective`, `reading_level` |
| Structure | `book_format`, `chapter_count_target`, `chapter_length_target` |
| Content | `include_summary_per_chapter`, `include_key_takeaways`, `include_action_steps`, `include_checklists`, `include_templates`, `include_examples` |
| Fidelity | `faithfulness_level`, `allowed_extrapolation`, `source_policy`, `citation_style`, `avoid_hallucinations` |
| Visuals | `visual_density`, `preferred_visual_types`, `visual_source_policy`, `caption_style`, `diagram_style` |
| Transcript | `resolve_repetitions`, `handle_q_and_a`, `include_speaker_quotes` |
| Output | `output_format`, `heading_style`, `callout_blocks`, `table_preference` |

See `backend/src/models/style_config.py` for full field definitions.

---

## API Entities

### GenerationJob (NEW - to be implemented)

In-memory job state for async generation.

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | string | UUID identifier |
| `project_id` | string | Associated project |
| `status` | enum | Current state |
| `created_at` | datetime | Job creation time |
| `current_chapter` | int? | Chapter being generated |
| `total_chapters` | int? | Total chapter count |
| `chapters_completed` | string[] | Markdown for completed chapters |
| `draft_plan` | DraftPlan? | Generated plan |
| `visual_plan` | VisualPlan? | Generated visuals |
| `draft_markdown` | string? | Final assembled draft |
| `error` | string? | Error message if failed |
| `cancel_requested` | bool | Cancellation flag |

**Status enum** (`JobStatus`):
- `queued` - Job created, not started
- `planning` - Generating DraftPlan
- `generating` - Generating chapters
- `completed` - All done
- `cancelled` - User cancelled
- `failed` - Error occurred

---

### API Request/Response Models

**Already defined in** `backend/src/models/api_responses.py`:

| Model | Purpose |
|-------|---------|
| `DraftGenerateRequest` | Input for draft generation |
| `DraftGenerateData` | Data payload for generate response |
| `DraftStatusData` | Data payload for status response |
| `DraftCancelData` | Data payload for cancel response |
| `DraftRegenerateData` | Data payload for regenerate response |
| `DraftGenerateResponse` | Envelope for generate endpoint |
| `DraftStatusResponse` | Envelope for status endpoint |
| `DraftCancelResponse` | Envelope for cancel endpoint |
| `DraftRegenerateResponse` | Envelope for regenerate endpoint |
| `ErrorDetail` | Error structure |
| `GenerationProgress` | Progress info during generation |
| `GenerationStats` | Statistics after completion |
| `TokenUsage` | Token usage tracking |

All responses use the `{ data, error }` envelope pattern.

---

## Relationships

```
Project
  └── draftText (string)
  └── draftPlan (DraftPlan)
        └── chapters[] (ChapterPlan)
              └── transcript_segments[] (TranscriptSegment)
        └── visual_plan (VisualPlan)
              └── opportunities[] (VisualOpportunity)
              └── assets[] (VisualAsset)
        └── generation_metadata (GenerationMetadata)
  └── visualPlan (VisualPlan) - same as draftPlan.visual_plan
  └── styleConfig (StyleConfigEnvelope)
        └── style (StyleConfig)
```

---

## Validation Summary

| Entity | Key Constraints |
|--------|-----------------|
| DraftPlan | version >= 1, book_title required |
| ChapterPlan | chapter_number >= 1, estimated_words >= 100 |
| TranscriptSegment | start_char >= 0, end_char >= 0 |
| GenerationMetadata | all fields >= 0, transcript_utilization in [0, 1] |
| VisualOpportunity | chapter_index >= 1, confidence in [0, 1] |
| VisualAsset | width >= 1, height >= 1 (if provided) |
| StyleConfigEnvelope | version >= 1 |
| StyleConfig | chapter_count_target in [3, 20] |

All models use Pydantic `extra="forbid"` to prevent schema drift.
