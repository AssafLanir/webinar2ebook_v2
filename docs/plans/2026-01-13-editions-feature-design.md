# Editions Feature Design

**Date:** 2026-01-13
**Status:** Draft
**Context:** [specs/NEXT-editions-feature-context.md](../../specs/NEXT-editions-feature-context.md)

## Problem Statement

User feedback on interview mode output: "That's basically a transcript."

The current interview mode produces Q&A format with speaker labels — which is correct for faithful reproduction. But users may want different outputs depending on use case:

- **Researchers/compliance** → want verbatim fidelity (current output)
- **Marketers/thought leadership** → want synthesized "ideas book"

## Solution: Two Editions

A single user-facing "Edition" selector that determines output structure.

| Edition | Output | Use Case |
|---------|--------|----------|
| **Q&A Edition** | Faithful interview format with HOST/GUEST labels | Compliance, reference, "let the expert speak" |
| **Ideas Edition** | Thematic chapters with synthesized prose + embedded quotes | Lead magnets, thought leadership, content repurposing |

### Q&A Edition Details

Preserves the interview structure. Two fidelity modes (under Advanced):

- **Faithful** (default) — Remove filler, tighten language, keep order and speakers
- **Verbatim** — Strict transcript assembly, minimal edits

Verbatim requires speaker-labeled transcript. If labels missing:
- Warn in Tab 1 next to Fidelity setting
- Offer: "Run speaker labeling (recommended)" vs "Use Faithful mode"

### Ideas Edition Details

Transforms interview content into thematic chapters.

**Output promise:** "Synthesizes the talk into a coherent mini-book. Quotes are verbatim; claims are grounded in source material."

**Chapter structure:**
```markdown
# Chapter 1: The Nature of Knowledge

[Synthesized prose explaining the ideas, grounded in transcript...]

As Deutsch explains: "Knowledge is not justified true belief..."

[More synthesis with embedded quotes...]
```

## UI Design

### Tab 1 — Edition Selection (Source of Truth)

```
┌─────────────────────────────────────────────────┐
│  Output Edition                                 │
│                                                 │
│  ● Q&A Edition                                  │
│    Faithful interview with speaker labels       │
│    Output: Q&A transcript-style                 │
│                                                 │
│  ○ Ideas Edition                                │
│    Thematic chapters, synthesized prose         │
│    Output: Mini-book chapters + quotes          │
│    (quotes verbatim, claims grounded)           │
│                                                 │
│  ℹ️ Detected Q&A format — recommended.          │
└─────────────────────────────────────────────────┘
```

- Radio button group (visible, intentional choice)
- Default-select based on transcript analysis (no separate "Use suggested" button)
- Hint text explains recommendation

**Conditional rendering:**
- If **Q&A Edition**: Outline optional ("for topic grouping only, won't change content"). Advanced section shows Fidelity toggle.
- If **Ideas Edition**: Outline section becomes Themes panel.

### Tab 1 — Themes Panel (Ideas Edition only)

```
┌─────────────────────────────────────────────────┐
│  Themes (chapter structure)                     │
│                                                 │
│  [Propose Themes]              [Add Suggestions]│
│                                                 │
│  ☰ 1. The Nature of Knowledge         [Strong] │
│      "How knowledge grows through conjecture"   │
│      ▶ 3 supporting segments                    │
│                                                 │
│  ☰ 2. Why Progress Requires Criticism  [Medium]│
│      "The role of error correction"             │
│      ▶ 2 supporting segments                    │
│                                                 │
│  ☰ 3. Optimism as a Moral Stance        [Weak] │
│      "Why pessimism is self-defeating"          │
│      ⚠️ Limited source material                 │
│      ▶ 1 supporting segment                     │
│                                                 │
│  [+ Add theme]                                  │
└─────────────────────────────────────────────────┘
```

**Per-theme display:**
- Drag handle (☰) for reordering
- Title (editable on click)
- One-liner description
- Coverage badge: Strong (green) / Medium (yellow) / Weak (red)
- Expandable snippet preview (2-3 excerpts)
- Delete button on hover

**Buttons:**
- "Propose Themes" — Initial analysis (or with confirmation if themes exist)
- "Add Suggestions" — Appends new themes without wiping existing

**Weak coverage behavior:**
- Warning icon + "Limited source material"
- At generation: omit by default, or user can toggle "Generate anyway (may be thin)"

### Tab 3 — Generation (Read-only Mirror)

```
┌─────────────────────────────────────────────────┐
│  Generating: Ideas Edition     [Change in Tab 1]│
│                                                 │
│  [Generate Draft]                               │
└─────────────────────────────────────────────────┘
```

For Q&A Edition, also show Fidelity:
```
│  Generating: Q&A Edition · Fidelity: Faithful   │
```

- Read-only display
- "Change in Tab 1" link navigates back
- Prevents surprise outputs

## Backend Design

### New Models

```python
from enum import Enum
from pydantic import BaseModel

class Edition(str, Enum):
    QA = "qa"
    IDEAS = "ideas"

class Fidelity(str, Enum):
    FAITHFUL = "faithful"
    VERBATIM = "verbatim"

class Coverage(str, Enum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"

class SegmentRef(BaseModel):
    start_offset: int  # Character offset into canonical transcript
    end_offset: int
    token_count: int   # Actual token count for coverage scoring
    text_preview: str  # First ~100 chars for display only

class Theme(BaseModel):
    id: str
    title: str
    one_liner: str
    keywords: list[str]
    coverage: Coverage
    supporting_segments: list[SegmentRef]
    include_in_generation: bool = True  # User can disable weak themes
```

### Project Model Additions

```python
class Draft(BaseModel):
    edition: Edition
    content: str
    created_at: datetime
    word_count: int

class Project(BaseModel):
    # ... existing fields ...
    edition: Edition = Edition.QA
    fidelity: Fidelity = Fidelity.FAITHFUL  # Q&A only
    themes: list[Theme] = []  # Ideas only
    drafts: list[Draft] = []  # Multiple drafts, different editions
    current_draft_id: str | None = None
    canonical_transcript: str | None = None  # Frozen transcript for offset validity
    canonical_transcript_hash: str | None = None  # SHA256 hash for verification
```

### New Endpoints

#### POST /api/ai/propose-themes

Job-based async endpoint (like PDF/EPUB export).

**Request:**
```json
{
  "project_id": "...",
  "existing_themes": []  // Optional: for "Add Suggestions"
}
```

**Response:**
```json
{
  "data": { "job_id": "..." },
  "error": null
}
```

**Job result:**
```json
{
  "themes": [
    {
      "title": "The Nature of Knowledge",
      "one_liner": "How knowledge grows through conjecture and refutation",
      "keywords": ["epistemology", "Popper", "conjecture"],
      "coverage": "strong",
      "supporting_segments": [
        { "start_offset": 1234, "end_offset": 1456, "text_preview": "..." }
      ]
    }
  ]
}
```

#### GET /api/jobs/{job_id}

Existing job status endpoint (reused).

### Coverage Scoring

Deterministic scoring based on:

```python
def score_coverage(segments: list[SegmentRef], transcript_length: int) -> Coverage:
    num_segments = len(segments)
    total_tokens = sum(s.token_count for s in segments)  # Use actual token count
    spread = calculate_spread(segments, transcript_length)  # How distributed

    score = (
        min(num_segments / 5, 1.0) * 0.4 +      # Up to 5 segments
        min(total_tokens / 500, 1.0) * 0.4 +    # Up to 500 tokens
        spread * 0.2                             # Distribution across transcript
    )

    if score >= 0.7:
        return Coverage.STRONG
    elif score >= 0.4:
        return Coverage.MEDIUM
    else:
        return Coverage.WEAK
```

### Ideas Edition Generation Pipeline

Per-theme, sequential pipeline:

```python
async def generate_ideas_edition(project: Project) -> Draft:
    chapters = []

    for theme in project.themes:
        if not theme.include_in_generation:
            continue  # User disabled weak theme

        # Step 1: Retrieve relevant segments
        segments = await retrieve_segments(
            theme=theme,
            transcript=project.transcript,
            method="embeddings",
            segment_size=300,  # tokens
            max_segments=12
        )

        # Step 2: Generate chapter (structured JSON output)
        chapter_data = await generate_chapter_structured(
            theme=theme,
            segments=segments
        )
        # Returns: { paragraphs: [...], quotes: [...], citations: [...] }

        # Step 3: Validate quotes
        validated_quotes = await validate_quotes(
            quotes=chapter_data.quotes,
            transcript=project.transcript
        )

        # Step 4: Faithfulness cleanup (delete unsupported, don't rewrite)
        cleaned = await faithfulness_cleanup(
            paragraphs=chapter_data.paragraphs,
            segments=segments,
            mode="delete"  # Remove unsupported sentences
        )

        # Step 5: Render to Markdown
        chapter_md = render_chapter(
            theme=theme,
            paragraphs=cleaned,
            quotes=validated_quotes
        )
        chapters.append(chapter_md)

    return Draft(
        edition=Edition.IDEAS,
        content="\n\n".join(chapters),
        created_at=datetime.utcnow(),
        word_count=count_words(chapters)
    )
```

### Quote Validation

Quotes stored as offsets into canonical transcript:

```python
class Quote(BaseModel):
    text: str
    start_offset: int
    end_offset: int
    speaker: str | None

def validate_quote(quote: Quote, transcript: str) -> bool:
    """Verify quote is exact substring at specified offsets."""
    canonical = canonicalize(transcript)
    expected = canonical[quote.start_offset:quote.end_offset]
    return normalize(quote.text) == normalize(expected)

def canonicalize(text: str) -> str:
    """Normalize whitespace, quotes, dashes for consistent offsets."""
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace('—', '-').replace('–', '-')
    return text.strip()

def normalize(text: str) -> str:
    """For comparison: lowercase, collapse whitespace, normalize punctuation."""
    return canonicalize(text).lower()
```

### Retrieval Strategy

Embedding-based semantic search:

```python
async def retrieve_segments(
    theme: Theme,
    transcript: str,
    method: str = "embeddings",
    segment_size: int = 300,  # tokens
    max_segments: int = 12
) -> list[SegmentRef]:
    # Chunk transcript into overlapping segments
    segments = chunk_transcript(
        transcript,
        size=segment_size,
        overlap=50
    )

    # Embed theme (title + one_liner + keywords)
    theme_embedding = await embed(
        f"{theme.title} {theme.one_liner} {' '.join(theme.keywords)}"
    )

    # Score and rank segments
    scored = []
    for seg in segments:
        seg_embedding = await embed(seg.text)
        score = cosine_similarity(theme_embedding, seg_embedding)
        scored.append((score, seg))

    # Return top segments
    scored.sort(reverse=True)
    return [seg for _, seg in scored[:max_segments]]
```

### Edition Switching Behavior

When user switches editions:

1. **Existing drafts preserved** — `drafts[]` stores all versions with edition + timestamp
2. **Current draft changes** — `current_draft_id` points to most recent draft of selected edition
3. **Regeneration** — Creates new draft, doesn't overwrite (history preserved)

```python
def switch_edition(project: Project, new_edition: Edition) -> Project:
    project.edition = new_edition

    # Find most recent draft for this edition
    edition_drafts = [d for d in project.drafts if d.edition == new_edition]
    if edition_drafts:
        project.current_draft_id = edition_drafts[-1].id
    else:
        project.current_draft_id = None

    return project
```

## Frontend Implementation

### New Components

1. **EditionSelector** — Radio group with descriptions, auto-suggestion hint
2. **ThemesPanel** — Theme list with coverage badges, drag-drop, snippets
3. **ThemeRow** — Individual theme with edit/delete/coverage
4. **EditionMirror** — Read-only display for Tab 3

### State Management

Add to ProjectContext:

```typescript
interface Project {
  // ... existing ...
  edition: 'qa' | 'ideas';
  fidelity: 'faithful' | 'verbatim';
  themes: Theme[];
  drafts: Draft[];
  currentDraftId: string | null;
}

interface Theme {
  id: string;
  title: string;
  oneLiner: string;
  keywords: string[];
  coverage: 'strong' | 'medium' | 'weak';
  supportingSegments: SegmentRef[];
  includeInGeneration: boolean;
}
```

### API Calls

```typescript
// Propose themes (returns job ID)
POST /api/ai/propose-themes
{ project_id, existing_themes? }

// Poll job status
GET /api/jobs/{job_id}

// Update project edition
PATCH /api/projects/{id}
{ edition, fidelity?, themes? }
```

## Implementation Notes

### Critical: Canonical Transcript Contract

SegmentRef offsets depend on a stable transcript. If the transcript is modified after themes are proposed, offsets become invalid.

**Contract:**
1. When themes are first proposed, freeze the transcript as `canonical_transcript`
2. Store SHA256 hash as `canonical_transcript_hash` for verification
3. All SegmentRef offsets refer to the canonical version
4. If user modifies transcript after themes exist, warn and offer to re-propose themes
5. Quote validation must use the canonical transcript, not any post-processed version

**Implementation:**
```python
def freeze_canonical_transcript(project: Project) -> Project:
    canonical = canonicalize(project.transcript)
    project.canonical_transcript = canonical
    project.canonical_transcript_hash = hashlib.sha256(canonical.encode()).hexdigest()
    return project

def verify_canonical(project: Project) -> bool:
    """Check if canonical transcript is still valid."""
    current_hash = hashlib.sha256(
        canonicalize(project.transcript).encode()
    ).hexdigest()
    return current_hash == project.canonical_transcript_hash
```

### Critical: Coverage Scoring Accuracy

Coverage scoring uses `token_count` stored in each SegmentRef, not derived from `text_preview`.

**Why this matters:**
- `text_preview` is truncated (~100 chars) for display
- Using `text_preview.split()` would systematically undercount tokens
- Real coverage requires the actual segment token count

**Implementation:**
```python
# When creating SegmentRef, calculate real token count
segment_ref = SegmentRef(
    start_offset=start,
    end_offset=end,
    token_count=len(tokenizer.encode(full_segment_text)),  # Real count
    text_preview=full_segment_text[:100]  # Truncated for display
)
```

## Validation Plan

### Unit Tests

- Theme proposal returns valid structure with coverage scores
- Coverage scoring thresholds work correctly
- Quote validation accepts exact matches, rejects fabrications
- Normalized matching handles whitespace/quote variations
- Faithfulness cleanup deletes (not rewrites) unsupported content

### Integration Tests

- Full Ideas Edition flow: propose → edit → generate → validate output
- Q&A Edition with both Fidelity modes
- Edition switching preserves drafts correctly
- Weak theme omission works

### Manual QA

- Run against David Deutsch interview
- Verify no hallucinated quotes
- Verify claims traceable to source
- Compare Q&A vs Ideas output quality

## Future Considerations (v2)

- **Key Takeaways format** — Executive summary style output
- **Narrative Essay format** — First-person voice, no Q&A structure
- **Multiple speakers** — Panel discussions with 3+ participants
- **Custom chapter templates** — User-defined chapter structure

## Non-Goals (Out of Scope)

- External diarization services
- Real-time processing
- Major UX redesign beyond Edition selector
- Breaking existing Q&A mode functionality
