# Research: Tab 3 AI Draft Generation

**Feature**: 004-tab3-ai-draft
**Date**: 2025-12-17

This document resolves the unknowns identified in plan.md for implementing ebook draft generation.

---

## 1. Chunked Generation Strategy

### Decision: Sequential chapter generation with context window

**Rationale**: Generate DraftPlan first (single request), then generate each chapter sequentially with surrounding context for continuity.

**Approach**:
1. **DraftPlan generation** (single LLM call):
   - Input: Full transcript + outline + style config
   - Output: Structured DraftPlan with chapter mappings
   - Uses `draft_plan.openai.strict.schema.json` for OpenAI structured output
   - Maps transcript segments to each chapter

2. **Chapter generation** (one call per chapter):
   - Input: Mapped transcript segment + chapter plan + style config + context
   - Context includes:
     - Previous chapter's last 2 paragraphs (continuity)
     - Next chapter's title and first outline point (setup)
   - Output: Markdown for single chapter
   - Target: <8,000 input tokens per request

3. **Transcript segment mapping**:
   - DraftPlan identifies `start_char` and `end_char` for each chapter
   - Segments may overlap for shared context
   - If mapping ambiguous, fallback to full transcript with chapter-focus instruction

**Alternatives Considered**:
- **Single mega-prompt**: Rejected - exceeds context limits for long transcripts
- **Batch generation (all chapters at once)**: Rejected - no progress tracking, harder to cancel
- **Recursive summarization**: Rejected - loses source fidelity

---

## 2. Job Management Pattern

### Decision: In-memory job store with asyncio background tasks

**Rationale**: For MVP with single-user focus, in-memory storage is simplest. No external dependencies (Redis, Celery). Can upgrade to persistent store later.

**Approach**:
```python
# Job store (singleton dict)
_jobs: dict[str, GenerationJob] = {}

class GenerationJob:
    job_id: str
    status: JobStatus  # queued, planning, generating, completed, cancelled, failed
    project_id: str
    created_at: datetime

    # Progress tracking
    current_chapter: int | None
    total_chapters: int | None
    chapters_completed: list[str]  # Markdown for completed chapters

    # Results
    draft_plan: DraftPlan | None
    visual_plan: VisualPlan | None
    draft_markdown: str | None
    error: str | None

    # Control
    cancel_requested: bool
```

**Lifecycle**:
1. `POST /generate` → Create job, start background task, return job_id
2. Background task runs generation, updates job state
3. `GET /status/:job_id` → Poll job state
4. `POST /cancel/:job_id` → Set `cancel_requested=True`, task checks between chapters

**Background task pattern**:
```python
async def generate_draft_task(job_id: str, request: DraftGenerateRequest):
    job = _jobs[job_id]
    try:
        # Phase 1: Generate DraftPlan
        job.status = JobStatus.planning
        draft_plan = await generate_draft_plan(request)
        job.draft_plan = draft_plan
        job.total_chapters = len(draft_plan.chapters)

        # Phase 2: Generate chapters
        job.status = JobStatus.generating
        for i, chapter_plan in enumerate(draft_plan.chapters):
            if job.cancel_requested:
                job.status = JobStatus.cancelled
                break

            job.current_chapter = i + 1
            chapter_md = await generate_chapter(chapter_plan, ...)
            job.chapters_completed.append(chapter_md)

        # Assemble final draft
        job.draft_markdown = assemble_chapters(job.chapters_completed)
        job.status = JobStatus.completed
    except Exception as e:
        job.status = JobStatus.failed
        job.error = str(e)
```

**Alternatives Considered**:
- **Celery**: Rejected - overkill for MVP, requires Redis/RabbitMQ
- **ARQ (async Redis queue)**: Rejected - external dependency
- **Database-backed jobs**: Considered for future - enables persistence across restarts

**Future upgrade path**: Add `persistence_backend` abstraction when multi-user or scaling needed.

---

## 3. Progress Updates

### Decision: HTTP polling with 2-second interval

**Rationale**: Simplest to implement, works with existing FastAPI setup, sufficient for multi-minute operations.

**Approach**:
- Frontend polls `GET /status/:job_id` every 2 seconds during generation
- Response includes:
  - `status`: Current state
  - `progress`: { current_chapter, total_chapters, current_chapter_title, estimated_remaining_seconds }
  - Partial results when available

**Frontend pattern**:
```typescript
const useDraftGeneration = () => {
  const [jobId, setJobId] = useState<string | null>(null)
  const [status, setStatus] = useState<DraftStatus | null>(null)

  useEffect(() => {
    if (!jobId) return

    const poll = async () => {
      const result = await fetchDraftStatus(jobId)
      setStatus(result)

      if (result.status === 'completed' || result.status === 'failed' || result.status === 'cancelled') {
        return // Stop polling
      }

      setTimeout(poll, 2000) // Poll every 2 seconds
    }

    poll()
  }, [jobId])

  return { startGeneration, cancelGeneration, status }
}
```

**Progress calculation**:
- `estimated_remaining_seconds = (total_chapters - current_chapter) * avg_chapter_time`
- Initial estimate: 15 seconds per chapter
- Refine based on actual generation times

**Alternatives Considered**:
- **Server-Sent Events (SSE)**: Rejected for MVP - more complex, polling is adequate
- **WebSocket**: Rejected - overkill for unidirectional updates
- **Long polling**: Rejected - no significant advantage over regular polling

---

## 4. DraftPlan LLM Prompting

### Decision: OpenAI structured output with strict JSON schema

**Rationale**: OpenAI's `response_format.json_schema` with `strict: true` guarantees valid JSON matching our schema. The `draft_plan.openai.strict.schema.json` was specifically created for this.

**System prompt for DraftPlan**:
```
You are an expert ebook architect. Given a webinar transcript and outline, create a detailed generation plan.

Your task:
1. Analyze the transcript content and map it to the provided outline
2. For each chapter, identify the relevant transcript segments (character ranges)
3. Define 2-4 learning goals and 3-6 key points per chapter
4. Suggest visual opportunities where images would enhance understanding
5. Estimate word counts based on source material density

Rules:
- Map ALL substantial transcript content to chapters
- transcript_segments use character indices (start_char, end_char)
- Visual opportunities are suggestions only - no placeholders in content
- Respect the style configuration for tone and structure
- Be precise with transcript mappings - no hallucinated quotes
```

**User prompt structure**:
```
## Transcript
{transcript}

## Outline
{outline_json}

## Style Configuration
{style_config_json}

## Available Visual Assets
{asset_list}  // For candidate_asset_ids matching

Generate a DraftPlan following the provided schema.
```

**Schema loading**:
```python
from src.llm import load_draft_plan_schema

schema = load_draft_plan_schema(provider="openai")  # Uses strict schema
# Logs: "Using DraftPlan openai schema: ..."

request = LLMRequest(
    messages=[...],
    response_format=ResponseFormat(
        type="json_schema",
        json_schema=schema
    )
)
```

**Alternatives Considered**:
- **Anthropic tool_use**: Good alternative, uses internal schema with allOf
- **Function calling**: Similar to tool_use, more verbose
- **Plain JSON mode**: Rejected - no schema validation guarantee

---

## 5. Visual Opportunities Generation

### Decision: Generate during DraftPlan phase, not during chapter generation

**Rationale**: Visual opportunities are about the overall content structure. Generating them alongside DraftPlan (before chapters) means:
- Available even if generation is cancelled
- Consistent with chapter boundaries
- Single pass over transcript for analysis

**Generation rules** (from style config):
- `visual_density: "none"` → Generate 0 opportunities
- `visual_density: "light"` → 1-2 per 3 chapters
- `visual_density: "medium"` → 1-2 per chapter
- `visual_density: "heavy"` → 2-4 per chapter

**VisualOpportunity fields** (from spec):
```python
VisualOpportunity(
    id=str(uuid4()),           # Stable ID for UI
    chapter_index=2,           # 1-based
    section_path="2.1",        # Optional section reference
    placement="after_heading", # Default
    visual_type="diagram",     # From style.preferred_visual_types
    source_policy="client_assets_only",  # From style.visual_source_policy
    title="System Architecture",
    prompt="A diagram showing the overall system architecture with...",
    caption="Figure 2.1: System Architecture Overview",
    required=False,
    candidate_asset_ids=[],    # Matched from provided assets
    confidence=0.8,            # LLM confidence
    rationale="Helps readers visualize the system structure"
)
```

**Asset matching** (if assets provided):
- Compare `prompt` keywords with asset `tags` and `alt_text`
- Populate `candidate_asset_ids` with potential matches
- Tab 2 (Spec 005) handles final attachment

---

## 6. Chapter Generation Prompting

### Decision: Focused prompts with context windows

**System prompt for chapter generation**:
```
You are writing chapter {chapter_number} of an ebook titled "{book_title}".

Writing style:
- Target audience: {target_audience}
- Tone: {tone}
- Formality: {formality}
- Reading level: {reading_level}

Structure guidelines:
- Chapter heading: ## Chapter {n}: {title}
- Use ### for sections, #### for subsections (no deeper)
- {include_summary_per_chapter ? "Include a brief summary at chapter start" : ""}
- {include_key_takeaways ? "End with key takeaways" : ""}
- {include_action_steps ? "Include actionable steps" : ""}

Source fidelity:
- Faithfulness: {faithfulness_level}
- {avoid_hallucinations ? "Only include information from the provided transcript" : ""}
- {citation_style != "none" ? "Cite sources: " + citation_style : ""}

DO NOT include visual placeholders like [IMAGE] or VISUAL_SLOT.
```

**User prompt for chapter**:
```
## Your Goals for This Chapter
{goals}

## Key Points to Cover
{key_points}

## Source Material (Transcript Segment)
{transcript_segment}

## Context: Previous Chapter Ending
{previous_chapter_last_paragraphs}

## Context: Next Chapter Preview
Next chapter: "{next_chapter_title}"
Topics: {next_chapter_first_points}

Write Chapter {chapter_number}: {title}
```

**Token budget per chapter**:
- System prompt: ~500 tokens
- Transcript segment: ~3,000-5,000 tokens
- Context: ~500-1,000 tokens
- Goals/points: ~200 tokens
- Total input: <8,000 tokens
- Output: ~2,000-3,000 tokens (1,500 words target)

---

## 7. Error Handling Strategy

### Decision: Graceful degradation with partial results

**Error scenarios and handling**:

| Error | Detection | Recovery |
|-------|-----------|----------|
| DraftPlan generation fails | LLM error/timeout | Fail entire job, retry button |
| Chapter N fails | LLM error | Skip chapter, continue with N+1, mark partial |
| Rate limit (429) | HTTP status | Auto-retry with exponential backoff (3 attempts) |
| Provider down (5xx) | HTTP status | Fallback to alternate provider |
| Invalid structured output | JSON validation | Retry same provider once, then fail |
| Timeout (>60s per chapter) | asyncio.timeout | Treat as provider error, fallback |

**Partial results handling**:
- If cancelled or chapter fails, `chapters_completed` contains what's done
- Assemble partial draft with note: "Generation incomplete. Chapters 1-N available."
- User can apply partial results or retry

**Fallback chain** (from existing LLM client):
1. Primary: OpenAI (gpt-4o-mini for cost, gpt-4o for quality)
2. Fallback: Anthropic (claude-3-5-sonnet)
3. No fallback on: 400 (bad request), 401/403 (auth), content policy

---

## 8. Testing Strategy

### Unit Tests (backend/tests/unit/)

**test_draft_service.py**:
- `test_generate_draft_plan_structure` - DraftPlan has required fields
- `test_chapter_generation_uses_mapped_segment` - Correct transcript portions
- `test_visual_opportunities_count_by_density` - Respects style config
- `test_cancel_stops_after_current_chapter` - Graceful cancellation
- `test_partial_results_on_failure` - Completed chapters preserved

**test_draft_api.py**:
- `test_generate_returns_job_id` - Async pattern works
- `test_status_shows_progress` - Progress fields populated
- `test_cancel_sets_cancelled_status` - Cancellation works
- `test_regenerate_single_section` - Section replacement works

### Integration Tests (backend/tests/integration/)

**test_draft_generation.py** (with mocked LLM):
- `test_full_generation_flow` - End-to-end with mock responses
- `test_provider_fallback` - Fallback on provider error
- `test_large_transcript_chunking` - Handles 50k char transcript

### Contract Tests (existing)

Already have 63 tests in `test_schemas_contract.py` validating:
- Schema structure
- Envelope pattern
- OpenAI strict compliance
- Round-trip serialization

---

## Summary of Decisions

| Topic | Decision | Key Rationale |
|-------|----------|---------------|
| Chunked generation | Sequential chapters with context | Progress tracking, cancellation |
| Job management | In-memory with asyncio tasks | MVP simplicity, no dependencies |
| Progress updates | HTTP polling (2s interval) | Simple, adequate for UX |
| DraftPlan prompting | OpenAI structured output | Schema guarantee |
| Visual opportunities | Generate in DraftPlan phase | Available even if cancelled |
| Error handling | Graceful degradation | Partial results preserved |

All decisions prioritize MVP simplicity while maintaining upgrade paths for future scaling.
