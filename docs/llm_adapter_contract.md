# LLM Adapter Contract

**Version**: 1.0
**Created**: 2025-12-17
**Status**: Draft
**Scope**: Defines the internal interface for multi-provider LLM integration (Spec 3+)

---

## Overview

This contract defines the abstraction layer between business logic (Spec 3 AI features) and LLM providers (OpenAI, Anthropic). The goal is to enable provider swapping without changing calling code.

---

## Request Model

### `LLMRequest`

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `messages` | `list[ChatMessage]` | Yes | Conversation history |
| `model` | `string` | Yes | Model identifier (provider-specific) |
| `temperature` | `float` | No | Sampling temperature (0-2). Default: 1.0 |
| `max_tokens` | `int` | No | Max output tokens. Default: provider default |
| `response_format` | `ResponseFormat` | No | Structured output format (JSON schema) |
| `tools` | `list[Tool]` | No | Available tools/functions |
| `tool_choice` | `string \| object` | No | Tool selection strategy |
| `stop` | `list[string]` | No | Stop sequences |
| `metadata` | `dict` | No | Pass-through metadata for logging |

### `ChatMessage`

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `role` | `string` | Yes | One of: `system`, `user`, `assistant`, `tool` |
| `content` | `string \| list[ContentPart]` | Yes | Text or multipart content |
| `name` | `string` | No | Optional name for multi-agent scenarios |
| `tool_call_id` | `string` | No | Reference to tool call (for `tool` role) |
| `tool_calls` | `list[ToolCall]` | No | Tool invocations (for `assistant` role) |

### `ContentPart` (for multimodal, v2+)

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `type` | `string` | Yes | `text`, `image_url`, `audio` |
| `text` | `string` | Conditional | Text content (when type=text) |
| `image_url` | `object` | Conditional | Image URL/base64 (when type=image_url) |

### `ResponseFormat`

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `type` | `string` | Yes | `text`, `json_object`, `json_schema` |
| `json_schema` | `object` | Conditional | JSON Schema definition (when type=json_schema) |

### `Tool`

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `type` | `string` | Yes | Always `function` for v1 |
| `function` | `FunctionDef` | Yes | Function definition |

### `FunctionDef`

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `name` | `string` | Yes | Function name |
| `description` | `string` | No | What the function does |
| `parameters` | `object` | Yes | JSON Schema for parameters |

---

## Response Model

### `LLMResponse`

| Field | Type | Always Present | Description |
| ----- | ---- | -------------- | ----------- |
| `text` | `string \| None` | Yes | Generated text content (None if only tool calls) |
| `tool_calls` | `list[ToolCall] \| None` | Yes | Tool invocations requested by model |
| `finish_reason` | `string` | Yes | `stop`, `length`, `tool_calls`, `content_filter` |
| `usage` | `Usage` | Yes | Token consumption |
| `model` | `string` | Yes | Actual model used (may differ from request) |
| `provider` | `string` | Yes | Provider name: `openai`, `anthropic` |
| `latency_ms` | `int` | Yes | Request duration in milliseconds |
| `request_id` | `string` | No | Provider's request ID for debugging |
| `raw` | `object` | No | Full provider response (for debugging) |

### `ToolCall`

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `id` | `string` | Yes | Unique call identifier |
| `type` | `string` | Yes | Always `function` for v1 |
| `function` | `FunctionCall` | Yes | Function invocation details |

### `FunctionCall`

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `name` | `string` | Yes | Function name to invoke |
| `arguments` | `string` | Yes | JSON string of arguments |

### `Usage`

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `prompt_tokens` | `int` | Yes | Input token count |
| `completion_tokens` | `int` | Yes | Output token count |
| `total_tokens` | `int` | Yes | Sum of prompt + completion |

---

## Provider Interface

### Base Class: `LLMProvider`

```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    """Base interface for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier: 'openai', 'anthropic'"""
        ...

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request and return the response."""
        ...

    @abstractmethod
    def supports(self, feature: str) -> bool:
        """Check if provider supports a capability."""
        ...

    # Optional for v1, required for v2
    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        """Stream response chunks. Raises NotImplementedError if not supported."""
        raise NotImplementedError("Streaming not supported by this provider")
```

---

## Capability Flags

Providers must report their capabilities via `supports(feature)`:

| Feature | Description | OpenAI | Anthropic |
| ------- | ----------- | ------ | --------- |
| `json_schema` | Structured outputs with JSON Schema | Yes | Yes (tool_use) |
| `json_object` | Basic JSON mode | Yes | No |
| `tools` | Function/tool calling | Yes | Yes |
| `vision` | Image inputs | Yes | Yes |
| `streaming` | Streaming responses | Yes | Yes |
| `system_message` | Dedicated system role | Yes | Yes (top-level param) |

### Usage Example

```python
provider = get_provider("openai")

if provider.supports("json_schema"):
    request.response_format = ResponseFormat(
        type="json_schema",
        json_schema=outline_schema
    )
else:
    # Fallback: parse JSON from text output
    request.messages.append({"role": "user", "content": "Respond in JSON format."})
```

---

## Error Handling

### `LLMError` Hierarchy

```python
class LLMError(Exception):
    """Base exception for LLM operations."""
    provider: str
    request_id: str | None

class RateLimitError(LLMError):
    """429 - Rate limit exceeded. Retry after backoff."""
    retry_after: float | None

class AuthenticationError(LLMError):
    """401/403 - Invalid or missing API key."""

class InvalidRequestError(LLMError):
    """400 - Malformed request (bad schema, too many tokens, etc.)."""

class ModelNotFoundError(LLMError):
    """Model identifier not recognized."""

class ContentFilterError(LLMError):
    """Response blocked by safety filters."""

class ProviderError(LLMError):
    """500/502/503 - Provider-side failure. May be transient."""

class TimeoutError(LLMError):
    """Request exceeded timeout threshold."""
```

### Retry Policy

| Error Type | Retry? | Strategy |
| ---------- | ------ | -------- |
| `RateLimitError` | Yes | Exponential backoff, respect `retry_after` |
| `ProviderError` (5xx) | Yes | Exponential backoff, max 3 attempts |
| `TimeoutError` | Yes | Once, with increased timeout |
| `AuthenticationError` | No | Fail immediately |
| `InvalidRequestError` | No | Fail immediately |
| `ContentFilterError` | No | Fail immediately |

---

## Spec 3 Usage Patterns

### Clean Transcript

```python
request = LLMRequest(
    model="gpt-4o",
    messages=[
        ChatMessage(role="system", content=CLEANUP_SYSTEM_PROMPT),
        ChatMessage(role="user", content=raw_transcript),
    ],
    temperature=0.3,
    max_tokens=16000,
)
response = await provider.generate(request)
cleaned_transcript = response.text
```

### Suggest Outline (Structured Output)

```python
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

request = LLMRequest(
    model="gpt-4o",
    messages=[
        ChatMessage(role="system", content=OUTLINE_SYSTEM_PROMPT),
        ChatMessage(role="user", content=transcript),
    ],
    response_format=ResponseFormat(type="json_schema", json_schema=outline_schema),
    temperature=0.5,
)
response = await provider.generate(request)
outline_items = json.loads(response.text)["items"]
```

### Suggest Resources (Structured Output)

```python
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

request = LLMRequest(
    model="gpt-4o",
    messages=[
        ChatMessage(role="system", content=RESOURCES_SYSTEM_PROMPT),
        ChatMessage(role="user", content=transcript),
    ],
    response_format=ResponseFormat(type="json_schema", json_schema=resources_schema),
    temperature=0.7,
)
response = await provider.generate(request)
resources = json.loads(response.text)["resources"]
```

---

## Configuration

### Environment Variables

| Variable | Description | Required |
| -------- | ----------- | -------- |
| `OPENAI_API_KEY` | OpenAI API key | If using OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic API key | If using Anthropic |
| `LLM_DEFAULT_PROVIDER` | Default provider name | No (default: openai) |
| `LLM_TIMEOUT_SECONDS` | Request timeout | No (default: 60) |
| `LLM_MAX_RETRIES` | Max retry attempts | No (default: 3) |

### Provider Selection

```python
# Get configured default
provider = get_default_provider()

# Get specific provider
provider = get_provider("anthropic")

# Check availability
if is_provider_available("anthropic"):
    provider = get_provider("anthropic")
```

---

## Provider Selection & Fallback Policy

**Default provider:** OpenAI

**Fallback provider:** Anthropic

**Fallback mode:** Automatic (transparent to calling code)

### Fallback Triggers

After retry attempts are exhausted on the primary provider, automatically fallback to the secondary:

| Trigger | Description |
| ------- | ----------- |
| HTTP 429 | Rate limit exceeded |
| HTTP 5xx | Provider/server errors |
| Timeout | Request exceeded `LLM_TIMEOUT_SECONDS` |
| Network error | Connection failures |

**Optional trigger** (can be enabled per-request):
- Invalid structured output when `response_format=json_schema` is required and response fails schema validation

### Limits

| Setting | Value |
| ------- | ----- |
| Max retries per provider | 2 |
| Total provider attempts | 2 (OpenAI → Anthropic) |
| Backoff strategy | Exponential with jitter |

### Behavior

1. Request goes to OpenAI (default)
2. On transient failure, retry up to 2 times with backoff
3. If still failing, automatically route to Anthropic
4. Retry up to 2 times on Anthropic
5. If both providers exhausted, raise `LLMError` to caller
6. All attempts logged with same `correlation_id`

### Usage

```python
# Automatic fallback (default behavior)
response = await llm.generate(request)  # Tries OpenAI, falls back to Anthropic

# Force specific provider (no fallback)
response = await llm.generate(request, provider="anthropic", fallback=False)
```

---

## Logging

All requests must log (structured, via Loguru):

| Field | Type | Description |
| ----- | ---- | ----------- |
| `correlation_id` | string | Request trace ID |
| `provider` | string | Provider name |
| `model` | string | Model used |
| `latency_ms` | int | Request duration |
| `prompt_tokens` | int | Input tokens |
| `completion_tokens` | int | Output tokens |
| `finish_reason` | string | How generation ended |
| `error` | string | Error type if failed |

---

## Provider Reference Docs

| Provider | Snapshot Location |
| -------- | ----------------- |
| OpenAI | `docs/refs/openai/chat_completions.md` |
| Anthropic | `docs/refs/anthropic/messages.md` |

---

## Version History

| Version | Date | Changes |
| ------- | ---- | ------- |
| 1.0 | 2025-12-17 | Initial contract for Spec 3 |
