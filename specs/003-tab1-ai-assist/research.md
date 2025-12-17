# Research: Tab 1 AI Assist

**Feature**: 003-tab1-ai-assist
**Date**: 2025-12-17
**Status**: Complete

---

## 1. LLM Provider Selection

### Decision
Use OpenAI as primary provider with Anthropic as automatic fallback.

### Rationale
- OpenAI has native `response_format.json_schema` support for structured outputs (outline items, resources)
- Anthropic supports structured output via tool_use pattern but requires different handling
- Both providers have Python SDKs (`openai`, `anthropic`) that are well-maintained
- Automatic fallback provides resilience without user intervention

### Alternatives Considered
| Alternative | Rejected Because |
| ----------- | ---------------- |
| OpenAI only | No fallback = single point of failure |
| Anthropic only | No native JSON schema mode; less structured output support |
| Google Gemini | Added complexity; deferred to future version |
| LangChain abstraction | Unnecessary dependency; simple adapter contract is sufficient |

---

## 2. Structured Output Strategy

### Decision
Use JSON Schema mode for outline and resource suggestions; plain text for transcript cleanup.

### Rationale
- Outline items have a defined schema: `{title, level, notes}`
- Resources have a defined schema: `{label, url_or_note}`
- Transcript cleanup is free-form text; no schema needed
- OpenAI's `response_format.json_schema` guarantees valid JSON matching schema
- For Anthropic fallback: use tool_use pattern to achieve same result

### Implementation
```python
# Outline schema
outline_schema = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "level": {"type": "integer", "minimum": 1, "maximum": 3},
                    "notes": {"type": "string"}
                },
                "required": ["title", "level"]
            }
        }
    },
    "required": ["items"]
}

# Resources schema
resources_schema = {
    "type": "object",
    "properties": {
        "resources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "url_or_note": {"type": "string"}
                },
                "required": ["label", "url_or_note"]
            },
            "minItems": 3,
            "maxItems": 5
        }
    },
    "required": ["resources"]
}
```

---

## 3. Error Handling & Retry Strategy

### Decision
Implement retry with exponential backoff per provider, then automatic fallback.

### Rationale
- Transient errors (429, 5xx, timeout) are common with LLM APIs
- Automatic fallback is transparent to frontend code
- 2 retries per provider balances reliability vs. latency
- Correlation ID enables debugging across retry attempts

### Implementation
Per `docs/llm_adapter_contract.md`:
- Max retries per provider: 2
- Total provider attempts: 2 (OpenAI → Anthropic)
- Backoff strategy: Exponential with jitter
- Non-retryable: AuthenticationError, InvalidRequestError, ContentFilterError

---

## 4. Frontend Preview Pattern

### Decision
Use modal-based preview with explicit Apply/Discard actions.

### Rationale
- Spec requirement: AI never silently overwrites user content
- Modal provides clear separation between preview and current state
- Consistent pattern for all three AI actions
- Ephemeral state (not persisted until Apply)

### Implementation
- `AIPreviewModal` component handles all three action types
- Different content rendering based on action type (text vs. list)
- Apply triggers existing `dispatch()` actions (UPDATE_TRANSCRIPT, ADD_OUTLINE_ITEM, ADD_RESOURCE)
- Discard closes modal with no side effects

---

## 5. System Prompts

### Decision
Define specific system prompts for each AI action.

### Rationale
- Clear instructions improve output quality
- Different goals for each action (cleanup vs. structure extraction vs. research)
- Prompts can be tuned independently

### Draft Prompts

**Transcript Cleanup:**
```
You are a transcript editor. Clean up the following raw transcript by:
- Removing filler words (um, uh, like, you know)
- Fixing punctuation and capitalization
- Organizing into logical paragraphs
- Preserving the speaker's meaning and tone
- Keeping technical terms and proper nouns intact

Return only the cleaned transcript text, no explanations.
```

**Outline Suggestion:**
```
You are a content strategist. Analyze the following transcript and suggest a structured outline for an ebook.
- Extract 5-15 main topics/sections
- Use levels 1-3 (1=chapter, 2=section, 3=subsection)
- Add brief notes where helpful
- Order logically for reader comprehension

Return as JSON matching the provided schema.
```

**Resource Suggestion:**
```
You are a research assistant. Based on the following transcript, suggest 3-5 relevant resources.
- Include URLs mentioned in the transcript
- Suggest related articles, tools, or references
- Each resource needs a short descriptive label
- Prioritize actionable, high-value resources

Return as JSON matching the provided schema.
```

---

## 6. API Endpoint Design

### Decision
Three dedicated POST endpoints under `/api/ai/` prefix.

### Rationale
- Clear separation from project CRUD endpoints
- Each action has distinct input/output shapes
- POST method appropriate for LLM processing
- Consistent error response format

### Endpoints
| Endpoint | Input | Output |
| -------- | ----- | ------ |
| `POST /api/ai/clean-transcript` | `{transcript: string}` | `{cleaned_transcript: string}` |
| `POST /api/ai/suggest-outline` | `{transcript: string}` | `{items: OutlineItem[]}` |
| `POST /api/ai/suggest-resources` | `{transcript: string}` | `{resources: Resource[]}` |

All endpoints return `{error: string}` on failure with appropriate HTTP status.

---

## 7. Concurrency Control

### Decision
Frontend mutex prevents concurrent AI actions; backend is stateless.

### Rationale
- Spec requirement: Only one AI action at a time
- Simpler than backend queue for single-user workflow
- Disabled buttons provide clear UX feedback
- No need for request cancellation in v1

### Implementation
- `ProjectContext` tracks `aiActionInProgress: string | null`
- AI buttons disabled when `aiActionInProgress !== null`
- Set on action start, cleared on success/failure

---

## 8. Token Limits & Chunking

### Decision
No chunking in v1; reject transcripts exceeding model context limits.

### Rationale
- 50,000 characters ≈ 12,500 tokens (well within GPT-4o's 128k context)
- Chunking adds complexity for cleanup (context loss at boundaries)
- Error message guides user to shorten transcript if needed
- Can add chunking in future version if needed

### Limits
- Max transcript: 50,000 characters (hard limit in API, enforced via Pydantic validation)
- Timeout: 60 seconds per request
- Max output tokens: 16,000 (cleanup), 4,000 (outline), 1,000 (resources)

---

## Summary

All research items resolved. No "NEEDS CLARIFICATION" markers remain.

| Topic | Decision |
| ----- | -------- |
| Provider | OpenAI primary, Anthropic fallback |
| Structured Output | JSON Schema for outline/resources |
| Retry Strategy | 2 retries/provider, exponential backoff |
| Preview Pattern | Modal with Apply/Discard |
| System Prompts | Action-specific prompts defined |
| API Design | Three POST endpoints under /api/ai/ |
| Concurrency | Frontend mutex |
| Token Limits | 50k chars max, no chunking |
