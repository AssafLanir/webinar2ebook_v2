# Data Model: Tab 1 AI Assist

**Feature**: 003-tab1-ai-assist
**Date**: 2025-12-17

---

## Overview

This feature introduces AI-assisted actions but does **not** add new persistent entities. AI suggestions use existing entity structures (`OutlineItem`, `Resource`) and are only persisted when the user explicitly applies them.

---

## Existing Entities (No Changes)

### OutlineItem

Already defined in `backend/src/models/project.py`. AI-suggested outline items match this structure.

```python
class OutlineItem(BaseModel):
    id: str
    title: str  # min_length=1
    level: int  # 1-3
    notes: str | None = None
    order: int  # ge=0
```

### Resource

Already defined in `backend/src/models/project.py`. AI-suggested resources use `resourceType = "url_or_note"`.

```python
class Resource(BaseModel):
    id: str
    label: str  # min_length=1
    order: int  # ge=0
    resourceType: ResourceType = ResourceType.URL_OR_NOTE
    urlOrNote: str = ""
    # File fields not used for AI suggestions
    fileId: str | None = None
    fileName: str | None = None
    fileSize: int | None = None
    mimeType: str | None = None
    storagePath: str | None = None
```

---

## New Request/Response Schemas

### AI Request Schemas

```python
# backend/src/api/routes/ai.py

class CleanTranscriptRequest(BaseModel):
    """Request body for transcript cleanup."""
    transcript: Annotated[str, Field(min_length=1, max_length=50000)]


class SuggestOutlineRequest(BaseModel):
    """Request body for outline suggestion."""
    transcript: Annotated[str, Field(min_length=1, max_length=50000)]


class SuggestResourcesRequest(BaseModel):
    """Request body for resource suggestion."""
    transcript: Annotated[str, Field(min_length=1, max_length=50000)]
```

### AI Response Schemas

```python
class CleanTranscriptResponse(BaseModel):
    """Response body for transcript cleanup."""
    cleaned_transcript: str


class SuggestedOutlineItem(BaseModel):
    """A single suggested outline item (no id/order yet)."""
    title: str
    level: Annotated[int, Field(ge=1, le=3)]
    notes: str | None = None


class SuggestOutlineResponse(BaseModel):
    """Response body for outline suggestion."""
    items: list[SuggestedOutlineItem]


class SuggestedResource(BaseModel):
    """A single suggested resource (no id/order yet)."""
    label: str
    url_or_note: str


class SuggestResourcesResponse(BaseModel):
    """Response body for resource suggestion."""
    resources: list[SuggestedResource]


class AIErrorResponse(BaseModel):
    """Error response for AI actions."""
    error: str
    retry_allowed: bool = True
```

---

## LLM Layer Models

Defined per `docs/llm_adapter_contract.md`:

```python
# backend/src/llm/models.py

class ChatMessage(BaseModel):
    """A single message in the conversation."""
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[dict]  # text or content parts
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict] | None = None


class ResponseFormat(BaseModel):
    """Structured output format configuration."""
    type: Literal["text", "json_object", "json_schema"]
    json_schema: dict | None = None


class LLMRequest(BaseModel):
    """Vendor-neutral LLM request."""
    messages: list[ChatMessage]
    model: str
    temperature: float = 1.0
    max_tokens: int | None = None
    response_format: ResponseFormat | None = None
    tools: list[dict] | None = None
    tool_choice: str | dict | None = None
    stop: list[str] | None = None
    metadata: dict | None = None


class Usage(BaseModel):
    """Token usage statistics."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LLMResponse(BaseModel):
    """Vendor-neutral LLM response."""
    text: str | None
    tool_calls: list[dict] | None = None
    finish_reason: str
    usage: Usage
    model: str
    provider: str
    latency_ms: int
    request_id: str | None = None
    raw: dict | None = None
```

---

## Frontend Types

```typescript
// frontend/src/types/ai.ts

export type AIActionType = 'clean-transcript' | 'suggest-outline' | 'suggest-resources'

export interface AIActionState {
  inProgress: AIActionType | null
  error: string | null
}

// Response types
export interface CleanTranscriptResponse {
  cleaned_transcript: string
}

export interface SuggestedOutlineItem {
  title: string
  level: number
  notes?: string
}

export interface SuggestOutlineResponse {
  items: SuggestedOutlineItem[]
}

export interface SuggestedResource {
  label: string
  url_or_note: string
}

export interface SuggestResourcesResponse {
  resources: SuggestedResource[]
}

export interface AIErrorResponse {
  error: string
  retry_allowed: boolean
}

// Preview state (ephemeral, not in Project)
export type AIPreviewData =
  | { type: 'clean-transcript'; data: CleanTranscriptResponse }
  | { type: 'suggest-outline'; data: SuggestOutlineResponse; selected: Set<number> }
  | { type: 'suggest-resources'; data: SuggestResourcesResponse; selected: Set<number> }

export interface AIPreviewState {
  isOpen: boolean
  preview: AIPreviewData | null
}
```

---

## State Transitions

### AI Action Flow

```
[Idle] ---(click action button)---> [Loading]
   ^                                    |
   |                                    v
   +------(discard/close)--------- [Preview]
   |                                    |
   +------(apply)----------------> [Applied] ---> [Idle]
   |
   +------(error)----------------- [Error] ---(retry)---> [Loading]
```

### State Fields (in ProjectContext)

```typescript
// Added to ProjectState
aiAction: AIActionState
aiPreview: AIPreviewState
```

---

## Validation Rules

| Field | Validation |
| ----- | ---------- |
| `transcript` (input) | min 1 char, max 50,000 chars |
| `SuggestedOutlineItem.title` | non-empty string |
| `SuggestedOutlineItem.level` | integer 1-3 |
| `SuggestedResource.label` | non-empty string |
| `SuggestedResource.url_or_note` | non-empty string |
| `resources` array | 3-5 items (enforced by JSON schema) |

---

## Persistence Notes

- **AI preview data**: Ephemeral, stored only in React state
- **Applied suggestions**: Flow through existing persistence:
  - `UPDATE_TRANSCRIPT` → `project.transcriptText`
  - `ADD_OUTLINE_ITEM` (multiple) → `project.outlineItems`
  - `ADD_RESOURCE` (multiple) → `project.resources`
- **No new database collections or fields required**
