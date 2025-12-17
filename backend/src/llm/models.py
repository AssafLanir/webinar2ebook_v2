"""LLM data models.

Vendor-neutral request and response models for LLM interactions.
These models abstract away provider-specific details.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in the conversation."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[dict[str, Any]]  # text or content parts (multimodal)
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ResponseFormat(BaseModel):
    """Structured output format configuration."""

    type: Literal["text", "json_object", "json_schema"]
    json_schema: dict[str, Any] | None = None


class LLMRequest(BaseModel):
    """Vendor-neutral LLM request."""

    messages: list[ChatMessage]
    model: str
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    max_tokens: int | None = None
    response_format: ResponseFormat | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    stop: list[str] | None = None
    metadata: dict[str, Any] | None = None


class Usage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class LLMResponse(BaseModel):
    """Vendor-neutral LLM response."""

    text: str | None
    tool_calls: list[dict[str, Any]] | None = None
    finish_reason: str
    usage: Usage
    model: str
    provider: str
    latency_ms: int
    request_id: str | None = None
    raw: dict[str, Any] | None = None
