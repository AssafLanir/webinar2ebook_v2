# Anthropic Messages API Reference (Claude) — Create a Message (Beta)

**Source**: https://platform.claude.com/docs/en/api/python/beta/messages/create  
**Snapshot Date**: 2025-12-17  
**Scope**: `POST /v1/messages` via `client.beta.messages.create(...)` (Python)  
**Note**: If this snapshot conflicts with live Anthropic docs/SDK behavior, prefer the live docs.

---

## Endpoint

- **Method**: `POST`
- **Path**: `/v1/messages`
- **Python SDK call**: `client.beta.messages.create(...)`

## Example request (Python)

```python
from anthropic import Anthropic

client = Anthropic(api_key="YOUR_ANTHROPIC_API_KEY")

msg = client.beta.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Hello, world"}
    ],
)

print(msg.id)
```

## Example response (JSON)

```json
{
  "id": "msg_013Zva2CMHLNnXjNJJKqJ2EF",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "Hi! My name is Claude."
    }
  ],
  "model": "claude-sonnet-4-5-20250929",
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": {
    "input_tokens": 9,
    "output_tokens": 12
  }
}
```

---

## Request parameters

### max_tokens
- **Type**: `int`  
- **Required**: Yes  
- **Description**: The maximum number of tokens to generate before stopping. Minimum `1`.

### messages
- **Type**: `Iterable[BetaMessageParam]`  
- **Required**: Yes  
- **Description**: Input messages (prior turns). Models are trained on alternating `user` / `assistant` turns; consecutive same-role turns may be combined.

#### BetaMessageParam
Each message is an object:
- `role`: `"user"` | `"assistant"`
- `content`: `str` **or** `List[BetaContentBlockParam]`

`content="Hello"` is shorthand for `content=[{"type":"text","text":"Hello"}]`.

### model
- **Type**: `ModelParam`  
- **Required**: Yes  
- **Description**: Model name/ID to use.

### container
- **Type**: `Optional[Container]`  
- **Required**: No  
- **Description**: Container configuration.

### context_management
- **Type**: `Optional[BetaContextManagementConfigParam]`  
- **Required**: No  
- **Description**: Context management configuration (beta feature).

### mcp_servers
- **Type**: `Optional[Iterable[BetaRequestMCPServerURLDefinitionParam]]`  
- **Required**: No  
- **Description**: MCP server definitions (beta feature).

### metadata
- **Type**: `Optional[BetaMetadataParam]`  
- **Required**: No  
- **Description**: Arbitrary metadata for the request (beta feature).

### output_config
- **Type**: `Optional[BetaOutputConfigParam]`  
- **Required**: No  
- **Description**: Output configuration (beta feature).

### output_format
- **Type**: `Optional[BetaJSONOutputFormatParam]`  
- **Required**: No  
- **Description**: Structured output format configuration (beta feature).

### service_tier
- **Type**: `Optional[Literal["auto", "standard_only"]]`  
- **Required**: No  
- **Description**: Service tier selection.

### stop_sequences
- **Type**: `Optional[SequenceNotStr[str]]`  
- **Required**: No  
- **Description**: Custom stop sequences to halt generation.

### stream
- **Type**: `Optional[Literal[false]]`  
- **Required**: No  
- **Description**: Streaming flag (typed as `false` on this beta Python reference page). If you need streaming, use the SDK’s streaming APIs.

### system
- **Type**: `Optional[Union[str, Iterable[BetaTextBlockParam]]]`  
- **Required**: No  
- **Description**: System prompt. There is **no** `"system"` role in Messages input; use this top-level parameter instead.

### temperature
- **Type**: `Optional[float]`  
- **Required**: No  
- **Description**: Sampling temperature.

### thinking
- **Type**: `Optional[BetaThinkingConfigParam]`  
- **Required**: No  
- **Description**: Extended reasoning configuration (beta feature).

### tool_choice
- **Type**: `Optional[BetaToolChoiceParam]`  
- **Required**: No  
- **Description**: How the model should choose tools (beta feature).

### tools
- **Type**: `Optional[Iterable[BetaToolUnionParam]]`  
- **Required**: No  
- **Description**: Tool definitions (functions) the model may call (beta feature).

### top_k
- **Type**: `Optional[int]`  
- **Required**: No  
- **Description**: Top-k sampling.

### top_p
- **Type**: `Optional[float]`  
- **Required**: No  
- **Description**: Nucleus sampling probability mass.

### betas
- **Type**: `Optional[List[AnthropicBetaParam]]`  
- **Required**: No  
- **Description**: Beta feature flags.

---

## Content blocks (common shapes for adapters)

`messages[].content` can be a list of blocks (`BetaContentBlockParam`). For most adapters, you’ll mainly care about:

### Text block (input and output)
```json
{ "type": "text", "text": "Hello, Claude" }
```

### Image block (input)
```json
{
  "type": "image",
  "source": {
    "type": "base64",
    "media_type": "image/png",
    "data": "<BASE64_DATA>"
  }
}
```

### Tool use block (output)
When the model calls a tool, the assistant’s `content` can include:
```json
{
  "type": "tool_use",
  "id": "toolu_...",
  "name": "my_tool_name",
  "input": { "some": "json" }
}
```

### Tool result block (input)
To return results back to Claude, include a user message whose content contains:
```json
{
  "type": "tool_result",
  "tool_use_id": "toolu_...",
  "content": "Tool output as text (or blocks)"
}
```

### Thinking blocks (output)
If enabled, output may also include:
```json
{ "type": "thinking", "thinking": "...", "signature": "..." }
```
or
```json
{ "type": "redacted_thinking", "data": "..." }
```

> Note: The beta reference page defines many additional block types (citations, web search tool results, etc.). For a minimal Spec 3 adapter, you can safely treat unknown blocks as opaque objects and only extract the ones you need (`text`, `tool_use`, `tool_result`, `thinking`).

---

## Response object (BetaMessage)

The response is a `BetaMessage` object with (at least) these fields:

- `id: str`
- `type: "message"`
- `role: "assistant"`
- `content: List[BetaContentBlock]` (blocks like `text`, `tool_use`, `thinking`, etc.)
- `model: Model`
- `stop_reason: Optional[BetaStopReason]`
- `stop_sequence: Optional[str]`
- `usage: BetaUsage`
- `container: Optional[BetaContainer]`
- `context_management: Optional[BetaContextManagementResponse]`

### BetaUsage (common fields)
- `input_tokens: int`
- `output_tokens: int`

---

## Adapter mapping notes (practical)

- **“Chat text”**: join all `content` blocks where `type == "text"`.
- **Tool calls**: parse blocks where `type == "tool_use"`; send tool outputs back as a `tool_result` block inside a `user` message.
- **System prompt**: map your abstraction’s system prompt to the top-level `system` field (not a message role).
- **Streaming**: do not assume `stream=true` is supported by this create method; implement streaming through the SDK’s streaming interface.